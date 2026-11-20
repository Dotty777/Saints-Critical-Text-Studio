"""Optional Cloud Gemini 4 + Gemini Decision-1 Brain (Interactions & Decisions APIs).

IMPORTANT:
- Strictly respects `config.offline_locked`: if True, raises PermissionError before any network socket opens.
- Uses current 2026 Gemini Interactions API (`POST /v1/interactions` or `google-genai >= 3.2.0`)
  and Decisions API (`POST /v1beta/decisions` with `gemini-decision-1`).
- Never sends deprecated `temperature`, `top_p`, or `top_k` parameters; uses `thinking_level` and
  top-level `response_format={"type": "text", "mime_type": "application/json", "schema": ...}`.
"""

from __future__ import annotations
import json
import os
import urllib.request
from typing import Any, Dict, List

from .base import (
    BrainConfig,
    CriticalBrainProvider,
    GatekeeperVerdict,
    VerseAdjudication,
    apply_model_gatekeeper_opinion,
    check_model_text_is_attested,
)
from .offline_philological import OfflinePhilologicalBrain

ALLOWED_GEMINI_MODELS = (
    "gemini-4-carbon",
    "gemini-4-argon",
    "gemini-4-hydrogen",
    "gemini-3.5-flash-lite",
)


class CloudGeminiBrain(CriticalBrainProvider):
    provider_id = "cloud_gemini"
    display_name = "Cloud Gemini 4 + Decision-1 (Requires Internet Unlocked)"
    requires_internet = True

    def __init__(self, config: BrainConfig) -> None:
        self.config = config
        self.fallback = OfflinePhilologicalBrain()

    def _resolve_api_key(self) -> str:
        key = (self.config.gemini_api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        if not key:
            raise RuntimeError("No GEMINI_API_KEY configured.")
        return key

    def _check_online_allowed(self) -> None:
        if self.config.offline_locked:
            raise PermissionError(
                "Strict Offline Mode is LOCKED. Unlock Offline Mode in the top bar before calling Cloud Gemini."
            )

    def _post_interactions_json(
        self,
        system_instruction: str,
        prompt: str,
        schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        self._check_online_allowed()
        api_key = self._resolve_api_key()
        model = self.config.gemini_model if self.config.gemini_model in ALLOWED_GEMINI_MODELS else "gemini-4-hydrogen"
        thinking = self.config.gemini_thinking_level if self.config.gemini_thinking_level in ("low", "medium", "high") else "medium"

        # Prefer official google-genai >= 3.2.0 SDK when installed; fall back to zero-dep REST
        try:
            from google import genai  # type: ignore
            client = genai.Client(api_key=api_key)
            interaction = client.interactions.create(
                model=model,
                system_instruction=system_instruction,
                input=prompt,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": schema,
                },
                generation_config={
                    "thinking_level": thinking,
                    "max_output_tokens": 32768,
                },
                store=False,
            )
            return json.loads(interaction.output_text or "{}")
        except ImportError:
            pass

        payload = {
            "model": model,
            "system_instruction": system_instruction,
            "input": prompt,
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": schema,
            },
            "generation_config": {
                "thinking_level": thinking,
                "max_output_tokens": 32768,
            },
            "store": False,
        }
        req = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1/interactions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
                "Api-Revision": "2026-05-20",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        texts: List[str] = []
        for step in body.get("steps", []):
            if step.get("type") == "model_output":
                for part in step.get("content", []):
                    if part.get("type") == "text":
                        texts.append(part.get("text", ""))
        return json.loads("".join(texts) or "{}")

    def _post_decision_calibration(self, input_text: str) -> Dict[str, Any]:
        """Call gemini-decision-1 (v1beta) for calibrated yes/no gatekeeper probabilities."""
        self._check_online_allowed()
        api_key = self._resolve_api_key()
        questions = {
            "is_license_open": {
                "type": "noul",
                "instructions": "Is this text free of NonCommercial (NC), NoDerivatives (ND), and modern publisher copyright restrictions so it can be used in an open-source critical edition?",
            },
            "is_primary_usable_witness": {
                "type": "noul",
                "instructions": "Is this a genuine, non-corrupt biblical manuscript transcription or historic/open critical edition worthy of collation?",
            },
        }
        try:
            from google import genai  # type: ignore
            client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})
            res = client.decisions.create(
                model="gemini-decision-1",
                input=input_text,
                questions=questions,
            )
            ans_lic = res.answers["is_license_open"]
            ans_use = res.answers["is_primary_usable_witness"]
            return {
                "p_open": float(ans_lic.noul),
                "p_usable": float(ans_use.noul),
                "confidence": float(min(ans_lic.confidence, ans_use.confidence)),
            }
        except ImportError:
            payload = {
                "model": "gemini-decision-1",
                "input": input_text,
                "questions": questions,
            }
            req = urllib.request.Request(
                "https://generativelanguage.googleapis.com/v1beta/decisions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            answers = body.get("answers", {})
            a1 = answers.get("is_license_open", {})
            a2 = answers.get("is_primary_usable_witness", {})
            return {
                "p_open": float(a1.get("noul", 0.5)),
                "p_usable": float(a2.get("noul", 0.5)),
                "confidence": float(min(a1.get("confidence", 0.8), a2.get("confidence", 0.8))),
            }

    def evaluate_witness(
        self,
        language: str,
        title: str,
        declared_license: str,
        sample_text: str,
        file_meta: Dict[str, Any],
        existing_samples: Dict[str, str],
    ) -> GatekeeperVerdict:
        base = self.fallback.evaluate_witness(
            language, title, declared_license, sample_text, file_meta, existing_samples
        )
        if self.config.offline_locked:
            base.reasons.append("Offline Lock active: evaluated locally with zero internet traffic.")
            return base

        try:
            probe = f"Language: {language}\nTitle: {title}\nDeclared License: {declared_license}\nSample:\n{sample_text[:3000]}"
            if self.config.use_decision_model:
                cal = self._post_decision_calibration(probe)
                base.scores["license_safe"] = round(cal["p_open"], 3)
                base.confidence = round(cal["confidence"], 3)

            schema = {
                "type": "object",
                "properties": {
                    "decision": {
                        "type": "string",
                        "enum": ["ADMITTED", "QUARANTINED_NC", "DISREGARDED_DUPLICATE", "DISREGARDED_CORRUPT"],
                    },
                    "tier_assigned": {"type": "integer"},
                    "recommended_weight": {"type": "number"},
                    "detected_license": {"type": "string"},
                    "detected_text_type": {"type": "string"},
                    "summary": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["decision", "tier_assigned", "recommended_weight", "summary", "rationale"],
            }
            res = self._post_interactions_json(
                "You are the Gatekeeper Brain for an open-source trilingual Biblical Critical Text (Greek, Hebrew, Latin).Quarantine any NonCommercial or copyrighted text to Tier 5; disregard duplicates or corrupt OCR; admit clean open witnesses to Tiers 1-4.",
                f"{probe}\nLocal Pre-Check: {base.summary}",
                schema,
            )
            if base.decision == "ADMITTED":
                base.detected_text_type = res.get("detected_text_type") or base.detected_text_type
            label = f"Cloud {self.config.gemini_model}" + (" + gemini-decision-1" if self.config.use_decision_model else "")
            apply_model_gatekeeper_opinion(base, res, label)
            if self.config.use_decision_model and base.decision == "ADMITTED" and base.scores.get("license_safe", 1.0) < 0.5:
                base.reasons.append(
                    f"gemini-decision-1 gives only {base.scores['license_safe']:.0%} probability that the licence is open; review the licence before collating."
                )
        except Exception as exc:
            base.reasons.append(f"Cloud Gemini unavailable ({exc}); evaluated by the Offline Brain only.")
        return base

    def adjudicate_chapter(
        self,
        language: str,
        book_title: str,
        chapter: int,
        collated_verses: List[Any],
    ) -> List[VerseAdjudication]:
        results = self.fallback.adjudicate_chapter(language, book_title, chapter, collated_verses)
        # Only word-level disputes go to the model; whole-verse presence/absence stays with the
        # deterministic rules and the human editor.
        contested = [
            (adj, cv) for adj, cv in zip(results, collated_verses)
            if any(a.kind == "word" for a in adj.apparatus) and not any(a.kind == "verse" for a in adj.apparatus)
        ]
        if not contested:
            return results
        if self.config.offline_locked:
            for adj, _cv in contested:
                adj.rationale += " [Cloud Gemini not consulted: Strict Offline Lock is on.]"
            return results

        try:
            schema = {
                "type": "object",
                "properties": {
                    "decisions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "verse": {"type": "integer"},
                                "critical_text": {"type": "string"},
                                "confidence": {"type": "number"},
                                "rationale": {"type": "string"},
                            },
                            "required": ["verse", "critical_text", "confidence", "rationale"],
                        },
                    }
                },
                "required": ["decisions"],
            }
            payload_items = [
                {
                    "verse": cv.verse,
                    "witnesses": cv.witness_texts,
                    "weights": cv.witness_weights,
                    "baseline_critical_text": adj.critical_text,
                }
                for adj, cv in contested
            ]
            res = self._post_interactions_json(
                f"You are a senior reasoned-eclectic textual critic reconstructing the {language.title()} Critical Text of {book_title} chapter {chapter}. Weigh external manuscript antiquity/independence and internal transcriptional/intrinsic probability. Output strictly original-language critical text and concise philological rationale.",
                json.dumps(payload_items, ensure_ascii=False),
                schema,
            )
            by_verse = {int(d["verse"]): d for d in res.get("decisions", []) if "verse" in d}
        except Exception as exc:
            for adj, _cv in contested:
                adj.rationale += f" [Cloud Gemini unavailable ({exc}); deterministic result kept.]"
            return results

        label = f"Cloud Gemini ({self.config.gemini_model})"
        for adj, cv in contested:
            d = by_verse.get(adj.verse)
            if not d:
                continue
            proposed = str(d.get("critical_text") or "").strip()
            problem = check_model_text_is_attested(proposed, cv.witness_texts, language)
            if problem:
                adj.rationale += f" [{label} proposal rejected: {problem}.]"
                continue
            if proposed != adj.critical_text:
                adj.baseline_text = adj.critical_text
                adj.critical_text = proposed
                adj.decision_source = label
            try:
                adj.confidence = max(0.0, min(1.0, float(d.get("confidence", adj.confidence))))
            except (TypeError, ValueError):
                pass
            if d.get("rationale"):
                adj.rationale = f"{str(d['rationale']).strip()} [{label}] Deterministic analysis: {adj.rationale}"
        return results
