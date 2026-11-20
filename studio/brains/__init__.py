"""Brain Provider Registry for Open-Source Extensibility."""

from __future__ import annotations
from typing import Dict, Type

from .base import BrainConfig, CriticalBrainProvider
from .gemini_cloud import CloudGeminiBrain
from .local_llm import LocalOllamaBrain
from .offline_philological import OfflinePhilologicalBrain
from .textual_analysis import TextualAnalysisBrain
from .openai_review import OpenAIReviewBrain

BRAIN_REGISTRY: Dict[str, Type[CriticalBrainProvider]] = {
    OfflinePhilologicalBrain.provider_id: OfflinePhilologicalBrain,
    TextualAnalysisBrain.provider_id: TextualAnalysisBrain,
    OpenAIReviewBrain.provider_id: OpenAIReviewBrain,
    LocalOllamaBrain.provider_id: LocalOllamaBrain,
    CloudGeminiBrain.provider_id: CloudGeminiBrain,
}


def create_brain(config: BrainConfig) -> CriticalBrainProvider:
    cls = BRAIN_REGISTRY.get(config.provider_id, OfflinePhilologicalBrain)
    if cls is OfflinePhilologicalBrain:
        return OfflinePhilologicalBrain()
    return cls(config)  # type: ignore[call-arg]
