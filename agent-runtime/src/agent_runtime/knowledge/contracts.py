from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, Protocol, TypeVar

from agent_runtime.capability_api.contracts import (
    CancellationSignal,
    JsonObject,
    ModelEgressResult,
    OpaqueUserToken,
)


class RetrievalPath(StrEnum):
    KEYWORD = "keyword"
    VECTOR = "vector"


class RewriteMode(StrEnum):
    MODEL = "model"
    ORIGINAL_FALLBACK = "original_fallback"


class RewriteCandidateSource(StrEnum):
    MODEL = "model"
    ORIGINAL_FALLBACK = "original_fallback"


class RewriteCandidateRejection(StrEnum):
    EMPTY = "empty"
    CONTROL = "control"
    TOO_LONG = "too_long"
    MISSING_CONSTRAINT = "missing_constraint"
    INTRODUCED_CONSTRAINT = "introduced_constraint"


class RewriteStageKind(StrEnum):
    SUCCESS = "success"
    QUESTION_DENIED = "question_denied"
    INPUT_INVALID = "input_invalid"
    TIMEOUT = "timeout"
    FAILURE = "failure"
    CLARIFICATION_REQUIRED = "clarification_required"


class RetrievalStageKind(StrEnum):
    SUCCESS = "success"
    NO_RESULT = "no_result"
    FORBIDDEN = "forbidden"
    TIMEOUT = "timeout"
    DOWNSTREAM_FAILURE = "downstream_failure"


class RetrievalStageCode(StrEnum):
    DOMAIN_FORBIDDEN = "domain_forbidden"
    READ_AUTHORITY_TIMEOUT = "read_authority_timeout"
    RETRIEVAL_TIMEOUT = "retrieval_timeout"
    RERANK_TIMEOUT = "rerank_timeout"
    READ_DECISION_UNVERIFIABLE = "read_decision_unverifiable"
    READ_AUTHORITY_FAILURE = "read_authority_failure"
    RETRIEVAL_FAILURE = "retrieval_failure"
    RERANK_FAILURE = "rerank_failure"
    INVALID_PROVIDER_RESULT = "invalid_provider_result"


class PathFailureKind(StrEnum):
    TIMEOUT = "timeout"
    DOWNSTREAM_FAILURE = "downstream_failure"


class EvidenceStageKind(StrEnum):
    SUCCESS = "success"
    NO_RESULT = "no_result"
    MODEL_EGRESS_DENIED = "model_egress_denied"
    FORBIDDEN = "forbidden"
    TIMEOUT = "timeout"
    DOWNSTREAM_FAILURE = "downstream_failure"


class EvidenceNoResultReason(StrEnum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NO_CANDIDATE = "no_candidate"


class EvidenceEgressDenialReason(StrEnum):
    QUESTION_DENIED = "question_denied"
    GLOBAL_DENIED = "global_denied"
    DOMAIN_DENIED = "domain_denied"
    DOCUMENT_DENIED = "document_denied"
    POLICY_MISSING = "policy_missing"
    POLICY_CONFLICT = "policy_conflict"


class EvidenceStageCode(StrEnum):
    EVIDENCE_READ_FORBIDDEN = "evidence_read_forbidden"
    EVIDENCE_TIMEOUT = "evidence_timeout"
    SUMMARY_TIMEOUT = "summary_timeout"
    EVIDENCE_FAILURE = "evidence_failure"
    SUMMARY_FAILURE = "summary_failure"
    INVALID_SUMMARY = "invalid_summary"


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeQueryArguments:
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class LogicalKnowledgeDomain:
    domain_id: str
    display_name: str
    order: int
    anchor_terms: tuple[str, ...]
    classifier_terms: tuple[str, ...]
    classifier_pattern: str | None
    allowed_paths: tuple[RetrievalPath, ...]
    default_egress_policy_ref: str


@dataclass(frozen=True, slots=True, kw_only=True)
class LogicalDomainCatalog:
    version: str
    domains: tuple[LogicalKnowledgeDomain, ...]

    def enabled(self, domain_ids: tuple[str, ...]) -> tuple[LogicalKnowledgeDomain, ...]:
        requested = frozenset(domain_ids)
        return tuple(domain for domain in self.domains if domain.domain_id in requested)


@dataclass(frozen=True, slots=True, kw_only=True)
class ProtectedConstraintSet:
    numbers: tuple[str, ...]
    dates: tuple[str, ...]
    document_numbers: tuple[str, ...]
    article_refs: tuple[str, ...]
    negations: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class RewriteCandidateValidation:
    accepted: bool
    reason: RewriteCandidateRejection | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class RewriteCandidate:
    text: str
    source: RewriteCandidateSource
    ordinal: int


@dataclass(frozen=True, slots=True, kw_only=True)
class PlannedDomainQuery:
    domain_id: str
    query: str


KNOWLEDGE_QUALITY_VERSION = "knowledge-retrieval-quality-v1"


@dataclass(frozen=True, slots=True, kw_only=True)
class RewriteResult:
    original_question: str
    selected_query: str
    candidates: tuple[RewriteCandidate, ...]
    mode: RewriteMode
    question_policy_version: str
    question_egress_denied: bool
    domain_queries: tuple[PlannedDomainQuery, ...] = ()
    plan_version: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class RewriteStageResult:
    kind: RewriteStageKind
    rewrite: RewriteResult | None = None
    policy_version: str | None = None
    reason_code: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DomainSelection:
    selected_domain_ids: tuple[str, ...]
    catalog_version: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class RetrievalPlanItem:
    logical_domain_id: str
    path: RetrievalPath
    query_text: str
    candidate_limit: int
    ordinal: int


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeRetrievalPlan:
    items: tuple[RetrievalPlanItem, ...]
    selected_domain_ids: tuple[str, ...]
    config_version: str
    quality_version: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class PathRef:
    logical_domain_id: str
    path: RetrievalPath


@dataclass(frozen=True, slots=True, kw_only=True)
class FailedPath:
    logical_domain_id: str
    path: RetrievalPath
    failure_kind: PathFailureKind


@dataclass(frozen=True, slots=True, kw_only=True)
class DomainCandidateCount:
    logical_domain_id: str
    count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class RetrievalCoverage:
    successful_paths: tuple[PathRef, ...]
    no_result_paths: tuple[PathRef, ...]
    failed_paths: tuple[FailedPath, ...]
    candidate_count_by_domain: tuple[DomainCandidateCount, ...]
    complete: bool


TBatch = TypeVar("TBatch")


@dataclass(frozen=True, slots=True, kw_only=True)
class RetrievalStageResult(Generic[TBatch]):
    kind: RetrievalStageKind
    batch: TBatch | None = None
    coverage: RetrievalCoverage | None = None
    stage_code: RetrievalStageCode | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeRetrievalContext:
    request_id: str
    correlation_id: str
    subject: str
    user_token: OpaqueUserToken
    deadline_monotonic: float
    cancellation: CancellationSignal


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeEvidenceContext:
    request_id: str
    correlation_id: str
    subject: str
    deadline_monotonic: float
    cancellation: CancellationSignal


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeEvidenceInput(Generic[TBatch]):
    original_question: str
    selected_query: str
    selected_domain_ids: tuple[str, ...]
    coverage: RetrievalCoverage
    question_policy_version: str
    question_egress_denied: bool
    batch: TBatch
    quality_version: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceStageResult:
    kind: EvidenceStageKind
    domain_result: JsonObject | None = None
    egress: ModelEgressResult | None = None
    no_result_reason: EvidenceNoResultReason | None = None
    policy_version: str | None = None
    denial_reason: EvidenceEgressDenialReason | None = None
    stage_code: EvidenceStageCode | None = None


class KnowledgeQuestionRewriteStage(Protocol):
    async def rewrite(self, *, original_question: str, timeout_s: float) -> RewriteStageResult: ...


class KnowledgeRetrievalStage(Protocol[TBatch]):
    async def execute(
        self,
        *,
        plan: KnowledgeRetrievalPlan,
        context: KnowledgeRetrievalContext,
        timeout_s: float,
    ) -> RetrievalStageResult[TBatch]: ...


class KnowledgeEvidenceStage(Protocol[TBatch]):
    async def build_result(
        self,
        *,
        input: KnowledgeEvidenceInput[TBatch],
        context: KnowledgeEvidenceContext,
        timeout_s: float,
    ) -> EvidenceStageResult: ...
