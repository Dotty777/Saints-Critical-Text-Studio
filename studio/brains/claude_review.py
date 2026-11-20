"""Optional Claude review layer for the Textual Analysis Brain (advisory only).

What it does
------------
For each contested verse it sends Claude the witnesses' own readings, their weights and edition
families, the deterministic critical text, and every apparatus unit with the brain's internal-
evidence findings. Claude answers, per unit, *which of the listed readings* it judges original —
by number — with a confidence and a short rationale.

Why it cannot corrupt the text
------------------------------
* Claude never writes Greek, Hebrew or Latin: it can only point at a reading the witnesses
  attest, so a hallucinated word is impossible by construction.
* Its answer is stored next to the deterministic decision. Where it disagrees, the verse is
  flagged for human review; the critical text itself is not changed.
* It runs only when the Strict Offline Lock is off, ``claude_review`` is switched on, and the
  ``anthropic`` package plus credentials are available. Otherwise it reports why it did not run.

The ``anthropic`` SDK is optional (``pip install anthropic``) and imported lazily, so the rest of
the Studio stays standard-library-only.
"""

from __future__ import annotations
import json
from typing import Any, Dict, List, Optional, Tuple

from .base import BrainConfig

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_UNITS_PER_REQUEST = 30

SYSTEM_PROMPT = """You are a senior textual critic of the Greek Old and New Testaments, the Hebrew Bible (Masoretic tradition) and the Latin Vulgate, reviewing decisions made by a deterministic collation program for an open-source critical edition.

For every variation unit you receive, decide which of the listed readings is most probably original (for the Hebrew: the best-attested Tiberian Masoretic form; for the Latin: the earliest recoverable Hieronymian text; for the Greek Old Testament: the Old Greek as attested by the listed witnesses), and answer with that reading's number.

Method (reasoned eclecticism):
- External evidence: weigh witnesses by date, quality and independence, not by count. Digital copies of one printed edition share a family and count once. Modern critical editions (SRGNT, SBLGNT, BHP, Nestle 1904) are largely built on the same early manuscripts (Sinaiticus 01, Vaticanus 03); the Robinson–Pierpont Byzantine text and the Textus Receptus (KJTR) represent the later ecclesiastical stream. Brenton's Greek follows the Sixtine edition; Swete prints Vaticanus (Alexandrinus where Vaticanus is lacking). MAM follows the Aleppo Codex, the WLC the Leningrad Codex. Amiatinus is an 8th-century Hieronymian pandect; the Clementine is the 1592/1598 edition.
- Transcriptional probability: prefer the reading that best explains the others. Omissions caused by eye-skip between similar endings or beginnings (homoeoteleuton, homoeoarcton), dittography and haplography, harmonisation to parallel passages, assimilation to familiar wording, expansion of sacred names and titles, liturgical additions, and conflation of two readings are scribal tendencies; the reading that would have produced the others is usually original.
- Intrinsic probability: the author's vocabulary, grammar and style, and the context.
- Digital-transcription errors (OCR slips, wrong breathings, misplaced letters) in one digital witness are not textual variants; if a listed reading looks like such an error, do not choose it and say so.
- The program's "analysis" findings are hints, not conclusions; check them.

Rules for your answer:
- Choose only by number among the readings given for that unit. Never propose a new reading, never translate, never modernise spelling.
- Give a calibrated confidence between 0 and 1. When the evidence is genuinely balanced, say so and use a confidence near 0.5.
- In "canons" list the short names of the principles you relied on (for example: "external: early witnesses", "homoeoteleuton", "harmonisation", "lectio difficilior", "scribal expansion", "conflation", "transcription error").
- Keep each rationale to two or three sentences, specific to the evidence in front of you.
- Return one entry for every unit you were given, keyed by its verse and unit numbers."""

REVIEW_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "units": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "verse": {"type": "integer"},
                    "unit": {"type": "integer"},
                    "choice": {"type": "integer"},
                    "confidence": {"type": "number"},
                    "canons": {"type": "array", "items": {"type": "string"}},
                    "rationale": {"type": "string"},
                },
                "required": ["verse", "unit", "choice", "confidence", "canons", "rationale"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["units"],
    "additionalProperties": False,
}


class ClaudeReviewUnavailable(RuntimeError):
    """Raised when the review layer cannot run; the message says why (shown to the user)."""


def _make_client(config: BrainConfig):
    try:
        import anthropic  # type: ignore
    except ImportError as exc:
        raise ClaudeReviewUnavailable("the 'anthropic' package is not installed (pip install anthropic)") from exc
    key = (config.anthropic_api_key or "").strip()
    return anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()


def _call(client: Any, config: BrainConfig, payload: Dict[str, Any]) -> Dict[str, Any]:
    """One structured-output request. Errors are translated into ClaudeReviewUnavailable."""
    try:
        import anthropic  # type: ignore
        error_chain: Tuple[type, ...] = (anthropic.APIError,)
    except ImportError:  # a test double is in use
        anthropic = None  # type: ignore
        error_chain = ()
    try:
        response = client.beta.messages.create(
            model=config.claude_model or DEFAULT_MODEL,
            max_tokens=16000,
            betas=[FALLBACK_BETA],
            fallbacks="default",  # server-side refusal fallback, routed by refusal category
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            output_config={
                "effort": config.claude_effort or "high",
                "format": {"type": "json_schema", "schema": REVIEW_SCHEMA},
            },
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)}],
        )
    except Exception as exc:  # map the SDK's typed errors (most specific first) to a readable reason
        if anthropic is not None and error_chain and isinstance(exc, error_chain):
            if isinstance(exc, anthropic.AuthenticationError):
                raise ClaudeReviewUnavailable("Claude rejected the credentials (check the API key or `ant auth login`)") from exc
            if isinstance(exc, anthropic.PermissionDeniedError):
                raise ClaudeReviewUnavailable("the credentials lack permission for this model") from exc
            if isinstance(exc, anthropic.NotFoundError):
                raise ClaudeReviewUnavailable(f"model '{config.claude_model}' not found") from exc
            if isinstance(exc, anthropic.RateLimitError):
                raise ClaudeReviewUnavailable("rate limited by the Claude API; try again later") from exc
            if isinstance(exc, anthropic.APIStatusError):
                raise ClaudeReviewUnavailable(f"Claude API error {exc.status_code}: {exc.message}") from exc
            if isinstance(exc, anthropic.APIConnectionError):
                raise ClaudeReviewUnavailable("could not reach the Claude API (network)") from exc
        raise
    if getattr(response, "stop_reason", "") == "refusal":
        details = getattr(response, "stop_details", None)
        raise ClaudeReviewUnavailable(f"Claude declined this request ({getattr(details, 'category', None) or 'refusal'})")
    if getattr(response, "stop_reason", "") == "max_tokens":
        raise ClaudeReviewUnavailable("Claude's answer was cut off (max_tokens); the chapter was reviewed in part")
    text = next((b.text for b in response.content if getattr(b, "type", "") == "text"), "")
    try:
        return json.loads(text)
    except ValueError as exc:
        raise ClaudeReviewUnavailable("Claude returned malformed JSON") from exc


def build_unit_payload(verse: int, witness_texts: Dict[str, str], weights: Dict[str, float],
                       families: Dict[str, str], critical_text: str, units: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "verse": verse,
        "critical_text": critical_text,
        "witnesses": {
            sig: {"text": txt, "weight": round(weights.get(sig, 0.5), 2), "edition_family": families.get(sig, sig)}
            for sig, txt in sorted(witness_texts.items())
        },
        "units": units,
    }


def review_chapter(
    config: BrainConfig,
    language: str,
    book_title: str,
    chapter: int,
    verse_payloads: List[Dict[str, Any]],
    client: Optional[Any] = None,
) -> Dict[Tuple[int, int], Dict[str, Any]]:
    """Ask Claude about every unit in ``verse_payloads``; returns {(verse, unit): answer}.

    Answers whose choice is not one of the offered readings are dropped (and so never used)."""
    if config.offline_locked:
        raise ClaudeReviewUnavailable("Strict Offline Lock is on")
    if not verse_payloads:
        return {}
    client = client or _make_client(config)

    batches: List[List[Dict[str, Any]]] = [[]]
    count = 0
    for vp in verse_payloads:
        if count and count + len(vp["units"]) > MAX_UNITS_PER_REQUEST:
            batches.append([])
            count = 0
        batches[-1].append(vp)
        count += len(vp["units"])

    offered = {(vp["verse"], u["unit"]): len(u["readings"]) for vp in verse_payloads for u in vp["units"]}
    answers: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for batch in batches:
        payload = {"language": language, "book": book_title, "chapter": chapter, "verses": batch}
        data = _call(client, config, payload)
        for a in data.get("units", []):
            try:
                key = (int(a["verse"]), int(a["unit"]))
                choice = int(a["choice"])
            except (KeyError, TypeError, ValueError):
                continue
            if key in offered and 0 <= choice < offered[key]:
                a["confidence"] = max(0.0, min(1.0, float(a.get("confidence", 0.5))))
                answers[key] = a
    return answers
