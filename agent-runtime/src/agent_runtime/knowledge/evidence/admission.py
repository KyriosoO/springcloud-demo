"""DR-KEV-034: optional tail admission, not a semantic sufficiency decision."""
from __future__ import annotations

import math
from typing import Final

from agent_runtime.knowledge.contracts import KNOWLEDGE_QUALITY_VERSION_V3, KnowledgeEvidenceInput
from agent_runtime.knowledge.evidence.builder import DeterministicEvidenceSelector, EvidenceIntegrityError
from agent_runtime.knowledge.evidence.contracts import (
    EvidenceSelectionResult, KnowledgeEvidenceLimits, VerifiedKnowledgeCandidate,
)
from agent_runtime.knowledge.retrieval.contracts import RankedKnowledgeBatch


class ScoreAwareEvidenceSelector(DeterministicEvidenceSelector):
    """Consume the complete verifier output; never replace the verifier itself."""

    VERSION: Final = "optional-evidence-score-v1"
    MIN_OPTIONAL_SCORE: Final = 0.5

    def select(
        self, *, candidates: tuple[VerifiedKnowledgeCandidate, ...],
        input: KnowledgeEvidenceInput[RankedKnowledgeBatch], minimized_question: str,
        limits: KnowledgeEvidenceLimits,
    ) -> EvidenceSelectionResult:
        if (
            input.quality_version != KNOWLEDGE_QUALITY_VERSION_V3
            or limits != KnowledgeEvidenceLimits.quality_v3()
            or type(candidates) is not tuple or len(candidates) > 20
            or any(
                type(item) is not VerifiedKnowledgeCandidate
                or type(item.rerank_score) not in (int, float)
                or not 0 <= item.rerank_score <= 1
                or not math.isfinite(item.rerank_score)
                for item in candidates
            )
        ):
            raise EvidenceIntegrityError("knowledge.evidence_admission_input_invalid")
        # V3 keeps the first-selection score. Do not recompute an any-focus max,
        # change rank/labels, or equate an anchor with sufficient direct evidence.
        admitted = tuple(item for item in candidates
                         if item.coverage_anchor or item.rerank_score >= self.MIN_OPTIONAL_SCORE)
        return super().select(candidates=admitted, input=input,
                              minimized_question=minimized_question, limits=limits)
