from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum

from agent_runtime.capability_api.contracts import JsonObject
from agent_runtime.knowledge.contracts import FailedPath
from agent_runtime.knowledge.retrieval.contracts import AuthorizedKnowledgeCandidate


class KnowledgeEgressDisposition(StrEnum):
    ALLOW_MINIMAL = "allow_minimal"
    DENY = "deny"


class KnowledgeEgressField(StrEnum):
    CONTENT = "content"
    TITLE = "title"
    DOCUMENT_NUMBER = "document_number"
    WRITTEN_DATE = "written_date"
    MATERIAL_TYPE = "material_type"
    DOMAIN_IDS = "domain_ids"


class EvidencePolicyDenial(StrEnum):
    GLOBAL_DENIED = "global_denied"
    DOMAIN_DENIED = "domain_denied"
    DOCUMENT_DENIED = "document_denied"
    POLICY_MISSING = "policy_missing"
    POLICY_CONFLICT = "policy_conflict"


class SummaryOutcome(StrEnum):
    ANSWER = "answer"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeEvidenceLimits:
    max_evidence: int
    max_per_document: int
    max_summary_input_bytes: int
    max_summary_points: int
    max_quote_chars: int
    max_domain_result_bytes: int

    @classmethod
    def v1(cls) -> "KnowledgeEvidenceLimits":
        return cls(
            max_evidence=8,
            max_per_document=2,
            max_summary_input_bytes=32768,
            max_summary_points=5,
            max_quote_chars=512,
            max_domain_result_bytes=32768,
        )

    @classmethod
    def quality_v1(cls) -> "KnowledgeEvidenceLimits":
        return replace(cls.v1(), max_per_document=3)


@dataclass(frozen=True, slots=True, kw_only=True)
class VerifiedKnowledgeCandidate:
    rank: int
    candidate: AuthorizedKnowledgeCandidate
    domain_ids: tuple[str, ...]
    rerank_score: float
    profile_version: str
    coverage_anchor: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceSource:
    title: str
    source_url: str | None
    document_number: str | None
    written_date: date | None
    material_type: str


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeEvidence:
    evidence_id: str
    rank: int
    document_id: str
    chunk_id: str
    domain_ids: tuple[str, ...]
    content: str
    content_sha256: str
    source: EvidenceSource
    read_policy_version: str
    policy_ref: str
    index_snapshot_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceCoverage:
    retrieval_complete: bool
    selected_domain_ids: tuple[str, ...]
    represented_domain_ids: tuple[str, ...]
    missing_domain_ids: tuple[str, ...]
    failed_paths: tuple[FailedPath, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class QuestionEvidenceTrace:
    original_question: str
    selected_query: str
    minimized_question: str
    question_policy_version: str


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeEvidenceBundle:
    question_trace: QuestionEvidenceTrace
    coverage: EvidenceCoverage
    evidence: tuple[KnowledgeEvidence, ...]
    profile_version: str
    index_snapshot_ids: tuple[str, ...]
    maximal_summary_input_bytes: int


@dataclass(frozen=True, slots=True, kw_only=True)
class SummaryCoverageInput:
    retrieval_complete: bool
    domain_coverage_complete: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class SummaryEvidenceInput:
    evidence_ref: str
    content: str
    domain_ids: tuple[str, ...] | None = None
    title: str | None = None
    document_number: str | None = None
    written_date: str | None = None
    material_type: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeSummaryInput:
    schema_version: int
    question: str
    coverage: SummaryCoverageInput
    evidence: tuple[SummaryEvidenceInput, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeSummaryPoint:
    evidence_ref: str
    quote: str


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeSummaryOutput:
    outcome: SummaryOutcome
    points: tuple[KnowledgeSummaryPoint, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeEgressPolicy:
    policy_ref: str
    policy_version: str
    disposition: KnowledgeEgressDisposition
    allowed_fields: frozenset[KnowledgeEgressField]
    max_content_code_points: int


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentPolicyBinding:
    document_id: str
    policy_ref: str
    policy_version: str
    allowed_index_snapshot_ids: frozenset[str]


@dataclass(frozen=True, slots=True, kw_only=True)
class PolicyCatalogSnapshot:
    schema_version: int
    catalog_version: str
    authority_id: str
    export_id: str
    source_revision: str
    source_sha256: str
    canonical_fingerprint: str
    policies: tuple[KnowledgeEgressPolicy, ...]
    bindings: tuple[DocumentPolicyBinding, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidencePolicyDecision:
    allowed: bool
    summary_input: KnowledgeSummaryInput | None = None
    policy_version: str = "knowledge-evidence-egress-v1"
    denial_reason: EvidencePolicyDenial | None = None
    snapshot_fingerprint: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceSelectionResult:
    bundle: KnowledgeEvidenceBundle | None
    sufficient: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class SummaryValidationResult:
    domain_result: JsonObject | None
    insufficient: bool
