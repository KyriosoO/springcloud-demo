from __future__ import annotations

from typing import Generic, TypeVar

from agent_runtime.knowledge.contracts import (
    EvidenceStageResult,
    KnowledgeEvidenceContext,
    KnowledgeEvidenceInput,
    KnowledgeRetrievalContext,
    KnowledgeRetrievalPlan,
    RetrievalStageResult,
    RewriteStageResult,
)

TBatch = TypeVar("TBatch")


class FakeRewriteStage:
    def __init__(self, result: RewriteStageResult) -> None:
        self.result = result
        self.calls = 0

    async def rewrite(self, *, original_question: str, timeout_s: float) -> RewriteStageResult:
        del original_question, timeout_s
        self.calls += 1
        return self.result


class FakeRetrievalStage(Generic[TBatch]):
    def __init__(self, result: RetrievalStageResult[TBatch]) -> None:
        self.result = result
        self.calls = 0
        self.contexts: list[KnowledgeRetrievalContext] = []

    async def execute(self, *, plan: KnowledgeRetrievalPlan, context: KnowledgeRetrievalContext, timeout_s: float) -> RetrievalStageResult[TBatch]:
        del plan, timeout_s
        self.calls += 1
        self.contexts.append(context)
        return self.result


class FakeEvidenceStage(Generic[TBatch]):
    def __init__(self, result: EvidenceStageResult) -> None:
        self.result = result
        self.calls = 0
        self.inputs: list[KnowledgeEvidenceInput[TBatch]] = []
        self.contexts: list[KnowledgeEvidenceContext] = []

    async def build_result(self, *, input: KnowledgeEvidenceInput[TBatch], context: KnowledgeEvidenceContext, timeout_s: float) -> EvidenceStageResult:
        del timeout_s
        self.calls += 1
        self.inputs.append(input)
        self.contexts.append(context)
        return self.result

