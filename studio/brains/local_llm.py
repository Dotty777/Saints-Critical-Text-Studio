"""100% Offline Local LLM Brain (Ollama / llama.cpp over 127.0.0.1).

Strictly enforces loopback-only URLs (`127.0.0.1` / `localhost` / `::1`) so it never touches the internet.
"""

from __future__ import annotations
import json
import urllib.parse
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


def _assert_loopback(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise PermissionError(
            f"LocalOfflineLLMBrain refuses non-loopback host '{host}'. Use 127.0.0.1 or localhost."
        )


class LocalOllamaBrain(CriticalBrainProvider):
    provider_id = "local_ollama"
    display_name = "Local Offline LLM (Ollama / llama.cpp · 127.0.0.1)"
    requires_internet = False

    def __init__(self, config: BrainConfig) -> None:
        self.config = config
        self.fallback = OfflinePhilologicalBrain()

    def _call_local_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        _assert_loopback(self.config.local_endpoint)
        payload = {
            "model": self.config.local_model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        req = urllib.request.Request(
            self.config.local_endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        content = body.get("message", {}).get("content") or body.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        return json.loads(content)

    def evaluate_witness(
        self,
        language: str,
        title: str,
        declared_license: str,
        sample_text: str,
        file_meta: Dict[str, Any],
        existing_samples: Dict[str, str],
    ) -> GatekeeperVerdict:
        # Deterministic licence / script / duplicate checks first; the model can only tighten them.
        base_verdict = self.fallback.evaluate_witness(
            language, title, declared_license, sample_text, file_meta, existing_samples
        )
        try:
            res = self._call_local_json(
                "You are a biblical textual criticism gatekeeper. Return JSON with keys: decision (ADMITTED|QUARANTINED_NC|DISREGARDED_DUPLICATE|DISREGARDED_CORRUPT), tier_assigned (1-4 if admitted), recommended_weight (0.0-1.0), summary, reason.",
                "\n".join([
                    f"Language: {language}",
                    f"Title: {title}",
                    f"License: {declared_license}",
                    f"Baseline Audit: {base_verdict.summary}",
                    "Sample:",
                    sample_text[:2000],
                ]),
            )
            apply_model_gatekeeper_opinion(base_verdict, res, f"Local LLM ({self.config.local_model})")
        except Exception as exc:
            base_verdict.reasons.append(
                f"Local LLM endpoint ({self.config.local_endpoint}) unavailable ({exc}); used the air-gapped Offline Philological Brain."
            )
        return base_verdict

    def adjudicate_chapter(
        self,
        language: str,
        book_title: str,
        chapter: int,
        collated_verses: List[Any],
    ) -> List[VerseAdjudication]:
        results = self.fallback.adjudicate_chapter(language, book_title, chapter, collated_verses)
        label = f"Local LLM ({self.config.local_model})"
        for adj, cv in zip(results, collated_verses):
            word_level = [a for a in adj.apparatus if a.kind == "word"]
            if not word_level or any(a.kind == "verse" for a in adj.apparatus):
                continue  # whole-verse questions stay with the deterministic rules and the human editor
            try:
                res = self._call_local_json(
                    "You are a senior textual critic of Greek, Hebrew, and Latin scripture. Choose among the witnesses' readings only; never add, translate or modernise words. Return JSON: {\"critical_text\": \"...\", \"rationale\": \"...\", \"confidence\": 0.92}.",
                    "\n".join([
                        f"{book_title} {chapter}:{cv.verse} ({language})",
                        f"Witnesses: {json.dumps(cv.witness_texts, ensure_ascii=False)}",
                        f"Baseline critical text: {adj.critical_text}",
                    ]),
                )
            except Exception as exc:
                adj.rationale += f" [{label} unavailable ({exc}); deterministic result kept.]"
                break
            proposed = str(res.get("critical_text") or "").strip()
            problem = check_model_text_is_attested(proposed, cv.witness_texts, language)
            if problem:
                adj.rationale += f" [{label} proposal rejected: {problem}.]"
                continue
            if proposed != adj.critical_text:
                adj.baseline_text = adj.critical_text
                adj.critical_text = proposed
                adj.decision_source = label
            if res.get("rationale"):
                adj.rationale = f"{str(res['rationale']).strip()} [{label}] Deterministic analysis: {adj.rationale}"
            if isinstance(res.get("confidence"), (int, float)):
                adj.confidence = max(0.0, min(1.0, float(res["confidence"])))
        return results
