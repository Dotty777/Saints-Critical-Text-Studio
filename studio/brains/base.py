"""Base Protocol & Data Models for Pluggable Critical Text AI Brains.

Open-Source Extension Point:
Any developer or AI agent can implement `CriticalBrainProvider` (see `offline_philological.py`,
`local_llm.py`, and `gemini_cloud.py`) and register it in `studio/brains/__init__.py`.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class BrainConfig:
    provider_id: str = "offline_philological"  # also textual_analysis, openai_review, local_ollama, cloud_gemini
    offline_locked: bool = True                # Hard air-gap switch: blocks all non-localhost network I/O
    # Local offline LLM settings (127.0.0.1 only)
    local_endpoint: str = "http://127.0.0.1:11434/api/chat"
    local_model: str = "gemma4:latest"
    # Optional Cloud Gemini settings (used ONLY when offline_locked=False)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-4-carbon"      # gemini-4-carbon | gemini-4-argon | gemini-4-hydrogen | gemini-3.5-flash-lite
    gemini_thinking_level: str = "high"        # low | medium | high
    use_decision_model: bool = True            # Calls gemini-decision-1 (v1beta) for calibrated gatekeeping
    # Optional Claude review layer of the Textual Analysis Brain (used ONLY when offline_locked=False
    # and claude_review=True). Advisory: it never changes the text, it flags disagreements.
    claude_review: bool = False
    claude_model: str = "claude-opus-5-5"
    claude_effort: str = "high"                # low | medium | high | xhigh | max
    anthropic_api_key: str = ""                # blank = the SDK's own credential lookup
    # OpenAI Review Brain: advisory, never changes the deterministic text or confidence.
    openai_model: str = "gpt-6-astra"
    openai_effort: str = "high"
    openai_api_key: str = ""                   # blank = OPENAI_API_KEY environment variable


@dataclass
class GatekeeperVerdict:
    decision: str               # "ADMITTED" | "QUARANTINED_NC" | "DISREGARDED_DUPLICATE" | "DISREGARDED_CORRUPT"
    tier_assigned: int          # 1..4 for admitted, 5 for quarantined, 0 for disregarded
    recommended_weight: float   # 0.0 .. 1.0
    detected_license: str
    detected_text_type: str
    confidence: float
    scores: Dict[str, float]    # license_safe, independence, quality
    summary: str
    reasons: List[str] = field(default_factory=list)
    model_used: str = "Offline Philological Engine v1"


@dataclass
class ApparatusItem:
    slot_index: int
    lemma: str
    lemma_witnesses: List[str]
    variants: List[Dict[str, Any]]  # [{"reading": str, "witnesses": [str], "weight_sum": float}]
    note: str
    # Position of the lemma in the critical text (word offset and length; length 0 = the critical
    # text omits here). Lets a human adopt a variant without string search-and-replace.
    word_index: int = -1
    word_count: int = 0
    kind: str = "word"  # "word" | "verse" (whole verse present/absent)
    # Filled by the Textual Analysis Brain: what kind of variant this is, and internal-evidence
    # findings, each {"canon", "note", "favours": "lemma"|"variant"|"neither", "reading", "strength"}.
    variant_type: str = ""
    analysis: List[Dict[str, Any]] = field(default_factory=list)
    # Canonical key of the adopted reading ("om." for an omission), so later stages compare keys
    # instead of re-tokenising the display lemma (which may show a contraction or punctuation).
    lemma_key: str = ""
    # Calibrated confidence of this unit's adopted reading (0–1).
    confidence: float = 1.0
    # Witnesses not counted as omitting here because they have these words in a neighbouring unit
    # (omission credit); they appear in neither lemma_witnesses nor variants.
    credited_witnesses: List[str] = field(default_factory=list)


@dataclass
class DisregardedItem:
    slot_index: int
    kept_form: str
    disregarded_forms: List[str]
    witnesses: List[str]
    reason: str


@dataclass
class VerseAdjudication:
    verse: int
    critical_text: str
    confidence: float
    decision_source: str
    apparatus: List[ApparatusItem] = field(default_factory=list)
    disregarded: List[DisregardedItem] = field(default_factory=list)
    rationale: str = ""
    # Set when an AI model replaced the deterministic text: the apparatus still describes this one.
    baseline_text: str = ""
    # Verse-level findings of the Textual Analysis Brain (confidence basis, review flags, AI review).
    analysis: List[Dict[str, Any]] = field(default_factory=list)
    needs_review: bool = False


_DECISION_STRICTNESS = {"ADMITTED": 0, "DISREGARDED_DUPLICATE": 1, "QUARANTINED_NC": 2, "DISREGARDED_CORRUPT": 2}


def apply_model_gatekeeper_opinion(base: GatekeeperVerdict, res: Dict[str, Any], model_label: str) -> GatekeeperVerdict:
    """Merge an AI model's gatekeeper answer into the deterministic verdict.

    The model may make the verdict stricter (e.g. flag a duplicate or a licence problem the rules
    missed) and may adjust tier/weight of an admitted witness, but it can never admit a witness the
    deterministic checks rejected for licence, script or duplication reasons."""
    decision = str(res.get("decision") or base.decision)
    if decision not in _DECISION_STRICTNESS:
        decision = base.decision
    if _DECISION_STRICTNESS[decision] < _DECISION_STRICTNESS.get(base.decision, 0):
        base.reasons.append(f"{model_label} suggested {decision}; kept {base.decision} because the model may not relax the deterministic checks.")
        decision = base.decision
    if decision != base.decision:
        base.decision = decision
        base.tier_assigned = 5 if decision == "QUARANTINED_NC" else 0
        base.recommended_weight = 0.0
    elif decision == "ADMITTED":
        try:
            tier = int(res.get("tier_assigned", base.tier_assigned))
            weight = float(res.get("recommended_weight", base.recommended_weight))
            if 1 <= tier <= 4 and 0.0 < weight <= 1.0:
                base.tier_assigned, base.recommended_weight = tier, round(weight, 2)
        except (TypeError, ValueError):
            pass
    summary = res.get("summary")
    if summary:
        base.summary = str(summary)
    reason = res.get("rationale") or res.get("reason")
    if reason:
        base.reasons.append(f"{model_label}: {reason}")
    base.model_used = f"Offline Guard + {model_label}"
    return base


def check_model_text_is_attested(proposed: str, witness_texts: Dict[str, str], language: str) -> str:
    """Return "" if every word of an AI-proposed critical text is attested by some witness of the
    verse (after orthographic normalisation); otherwise a reason to reject it.

    Language models can silently normalise, translate, or invent wording. A critical text may
    only choose among readings the witnesses actually carry."""
    from ..collator import canonical_compare_key, tokenize_for_alignment

    proposed = (proposed or "").strip()
    if not proposed:
        return "model returned an empty text"
    attested = {
        canonical_compare_key(t, language)
        for txt in witness_texts.values()
        for t in tokenize_for_alignment(txt, language)
    }
    attested.discard("")
    unattested = [
        t for t in tokenize_for_alignment(proposed, language)
        if canonical_compare_key(t, language) and canonical_compare_key(t, language) not in attested
    ]
    if unattested:
        return "model text contains words no witness attests: " + ", ".join(unattested[:6])
    return ""


class CriticalBrainProvider(ABC):
    """Abstract interface for Witness Gatekeeping & Eclectic Variant Adjudication."""

    provider_id: str = "base"
    display_name: str = "Base Brain"
    requires_internet: bool = False

    @abstractmethod
    def evaluate_witness(
        self,
        language: str,
        title: str,
        declared_license: str,
        sample_text: str,
        file_meta: Dict[str, Any],
        existing_samples: Dict[str, str],
    ) -> GatekeeperVerdict:
        """Determine whether a newly supplied witness should be ADMITTED, QUARANTINED, or DISREGARDED."""

    @abstractmethod
    def adjudicate_chapter(
        self,
        language: str,
        book_title: str,
        chapter: int,
        collated_verses: List[Any],
    ) -> List[VerseAdjudication]:
        """Determine the Critical Text, Critical Apparatus, and Disregarded Noise for each verse."""
