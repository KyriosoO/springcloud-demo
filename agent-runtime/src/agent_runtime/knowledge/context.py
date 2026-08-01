from __future__ import annotations

from agent_runtime.capability_api.contracts import CapabilityExecutionContext, SubjectType
from agent_runtime.knowledge.contracts import KnowledgeEvidenceContext, KnowledgeRetrievalContext
from agent_runtime.knowledge.errors import KnowledgeInputError


def _validate(context: CapabilityExecutionContext) -> None:
    if context.subject_type is not SubjectType.USER or not context.subject_id:
        raise KnowledgeInputError("knowledge.invalid_context")


def to_retrieval_context(context: CapabilityExecutionContext) -> KnowledgeRetrievalContext:
    _validate(context)
    return KnowledgeRetrievalContext(
        request_id=context.request_id,
        correlation_id=context.correlation_id,
        subject=context.subject_id,
        user_token=context.user_token,
        deadline_monotonic=context.deadline_monotonic,
        cancellation=context.cancellation,
    )


def to_evidence_context(context: CapabilityExecutionContext) -> KnowledgeEvidenceContext:
    _validate(context)
    return KnowledgeEvidenceContext(
        request_id=context.request_id,
        correlation_id=context.correlation_id,
        subject=context.subject_id,
        deadline_monotonic=context.deadline_monotonic,
        cancellation=context.cancellation,
    )

