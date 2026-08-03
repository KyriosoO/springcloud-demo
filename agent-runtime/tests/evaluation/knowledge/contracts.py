from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agent_runtime.core.execution import RequestExecutionScope


_ASCII_SAFE = re.compile(r"^[A-Za-z0-9._:/+-]+$")
_LOWER_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_LOWER_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_RFC3339_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")

MetricValue = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)] | Literal["not_applicable"]
DeltaValue = Annotated[float, Field(ge=-1.0, le=1.0, allow_inf_nan=False)] | Literal["not_applicable"]
ModelTaskVersionKey = Literal["action_selection", "answer_generation", "knowledge_rewrite", "knowledge_summary"]


class StrictEvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, populate_by_name=True)


class EvaluationCase(StrictEvaluationModel):
    case_id: str = Field(alias="case_id", min_length=1, max_length=64)
    question: str = Field(min_length=1, max_length=4096)
    category: Literal["tax_policy", "tax_law", "mixed", "no_match", "insufficient", "security_negative"]
    expected_domain_ids: tuple[Literal["tax.policy", "tax.law"], ...]
    expected_answerability: Literal["answerable", "no_result", "model_egress_denied"]
    relevant_document_ids: tuple[str, ...]
    required_evidence_ids: tuple[str, ...]
    must_preserve_tokens: tuple[str, ...]

    @model_validator(mode="after")
    def validate_case(self) -> "EvaluationCase":
        if not _ASCII_SAFE.fullmatch(self.case_id):
            raise ValueError("evaluation.invalid_case_id")
        if len(set(self.expected_domain_ids)) != len(self.expected_domain_ids):
            raise ValueError("evaluation.duplicate_domain")
        for values in (self.relevant_document_ids, self.required_evidence_ids, self.must_preserve_tokens):
            if len(set(values)) != len(values) or any(not value or len(value) > 256 for value in values):
                raise ValueError("evaluation.invalid_gold")
        return self


class GateEvidenceRecord(StrictEvaluationModel):
    gate_id: Literal["SA-GATE-002", "CR-GATE-003", "SA-GATE-003", "SA-GATE-006"] = Field(alias="gateId")
    evidence_ref: str = Field(alias="evidenceRef", min_length=1, max_length=256)

    @field_validator("evidence_ref")
    @classmethod
    def validate_evidence_ref(cls, value: str) -> str:
        if not _ASCII_SAFE.fullmatch(value):
            raise ValueError("evaluation.invalid_evidence_ref")
        return value


class PathRankingRecord(StrictEvaluationModel):
    logical_domain_id: Literal["tax.policy", "tax.law"] = Field(alias="logicalDomainId")
    path: Literal["keyword", "vector"]
    document_ids: tuple[str, ...] = Field(alias="documentIds", max_length=10)

    @field_validator("document_ids")
    @classmethod
    def validate_document_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value) or any(not item or len(item) > 256 for item in value):
            raise ValueError("evaluation.invalid_document_ids")
        return value


class ModelCallCountRecord(StrictEvaluationModel):
    rewrite: int = Field(ge=0)
    embedding: int = Field(ge=0)
    keyword_retrieval: int = Field(alias="keywordRetrieval", ge=0)
    vector_retrieval: int = Field(alias="vectorRetrieval", ge=0)
    rerank: int = Field(ge=0)
    summary: int = Field(ge=0, le=1)
    core_answer: int = Field(alias="coreAnswer", ge=0, le=0)


class VariantCaseMetrics(StrictEvaluationModel):
    constraint_preserved: MetricValue = Field(alias="constraintPreserved")
    path_hit_at_10: MetricValue = Field(alias="pathHitAt10")
    fusion_recall_at_10: MetricValue = Field(alias="fusionRecallAt10")
    fusion_mrr_at_10: MetricValue = Field(alias="fusionMrrAt10")
    rerank_recall_at_10: MetricValue = Field(alias="rerankRecallAt10")
    rerank_mrr_at_10: MetricValue = Field(alias="rerankMrrAt10")
    required_evidence_coverage: MetricValue = Field(alias="requiredEvidenceCoverage")
    citation_validity_rate: MetricValue = Field(alias="citationValidityRate")


class EvaluationVariantResult(StrictEvaluationModel):
    variant: Literal["primary", "rewrite_ablation"]
    terminal_status: Literal[
        "success", "no_result", "invalid_argument", "forbidden", "timeout",
        "downstream_failure", "model_egress_denied", "internal_failure"
    ] = Field(alias="terminalStatus")
    rewrite_mode: Literal["model", "original_fallback"] = Field(alias="rewriteMode")
    selected_domain_ids: tuple[Literal["tax.policy", "tax.law"], ...] = Field(alias="selectedDomainIds")
    path_rankings: tuple[PathRankingRecord, ...] = Field(alias="pathRankings")
    fused_top_10_document_ids: tuple[str, ...] = Field(alias="fusedTop10DocumentIds", max_length=10)
    reranked_top_10_document_ids: tuple[str, ...] = Field(alias="rerankedTop10DocumentIds", max_length=10)
    adopted_evidence_ids: tuple[str, ...] = Field(alias="adoptedEvidenceIds")
    summary_status: Literal["answer", "insufficient_evidence", "not_called", "failed"] = Field(alias="summaryStatus")
    model_call_counts: ModelCallCountRecord = Field(alias="modelCallCounts")
    metrics: VariantCaseMetrics

    @model_validator(mode="after")
    def validate_variant(self) -> "EvaluationVariantResult":
        for values in (
            self.selected_domain_ids,
            self.fused_top_10_document_ids,
            self.reranked_top_10_document_ids,
            self.adopted_evidence_ids,
        ):
            if len(set(values)) != len(values):
                raise ValueError("evaluation.duplicate_result_id")
        if self.variant == "rewrite_ablation":
            if self.rewrite_mode != "original_fallback" or self.model_call_counts.rewrite != 0:
                raise ValueError("evaluation.invalid_ablation")
            if self.metrics.constraint_preserved != "not_applicable":
                raise ValueError("evaluation.invalid_ablation_metric")
        elif self.rewrite_mode != "model":
            raise ValueError("evaluation.invalid_primary")
        return self


class ComparisonMetrics(StrictEvaluationModel):
    rewrite_rerank_recall_delta: DeltaValue = Field(alias="rewriteRerankRecallDelta")
    rewrite_regression: bool = Field(alias="rewriteRegression")


class PrimaryHumanJudgment(StrictEvaluationModel):
    faithful: bool
    relevant: bool
    sufficient_for_initial_answer: bool = Field(alias="sufficientForInitialAnswer")
    useful: bool
    judgment_reason: Literal["none", "quote_context", "relevance", "coverage", "gold_issue"] = Field(alias="judgmentReason")


class EvaluationCaseResult(StrictEvaluationModel):
    case_id: str = Field(alias="caseId", min_length=1, max_length=64)
    primary: EvaluationVariantResult
    rewrite_ablation: EvaluationVariantResult = Field(alias="rewriteAblation")
    comparison_metrics: ComparisonMetrics = Field(alias="comparisonMetrics")
    primary_judgment: PrimaryHumanJudgment = Field(alias="primaryJudgment")

    @model_validator(mode="after")
    def validate_pair(self) -> "EvaluationCaseResult":
        if self.primary.variant != "primary" or self.rewrite_ablation.variant != "rewrite_ablation":
            raise ValueError("evaluation.invalid_variant_pair")
        return self


class SafetyGateResult(StrictEvaluationModel):
    denied_summary_call_count: int = Field(alias="deniedSummaryCallCount", ge=0)
    unauthorized_content_count: int = Field(alias="unauthorizedContentCount", ge=0)
    citation_validity_rate: MetricValue = Field(alias="citationValidityRate")
    constraint_preservation_rate: MetricValue = Field(alias="constraintPreservationRate")
    passed: bool


class PathHitAggregate(StrictEvaluationModel):
    tax_policy_keyword: MetricValue = Field(alias="taxPolicyKeyword")
    tax_policy_vector: MetricValue = Field(alias="taxPolicyVector")
    tax_law_keyword: MetricValue = Field(alias="taxLawKeyword")
    tax_law_vector: MetricValue = Field(alias="taxLawVector")


class EvaluationMetrics(StrictEvaluationModel):
    constraint_preservation_rate: MetricValue = Field(alias="constraintPreservationRate")
    rewrite_rerank_recall_delta: DeltaValue = Field(alias="rewriteRerankRecallDelta")
    rewrite_regression_rate: MetricValue = Field(alias="rewriteRegressionRate")
    domain_exact_match_rate: MetricValue = Field(alias="domainExactMatchRate")
    path_hit_at_10_by_domain_path: PathHitAggregate = Field(alias="pathHitAt10ByDomainPath")
    fusion_recall_at_10: MetricValue = Field(alias="fusionRecallAt10")
    fusion_mrr_at_10: MetricValue = Field(alias="fusionMrrAt10")
    rerank_recall_at_10: MetricValue = Field(alias="rerankRecallAt10")
    rerank_mrr_at_10: MetricValue = Field(alias="rerankMrrAt10")
    required_evidence_coverage: MetricValue = Field(alias="requiredEvidenceCoverage")
    summary_valid_completion_rate: MetricValue = Field(alias="summaryValidCompletionRate")
    citation_validity_rate: MetricValue = Field(alias="citationValidityRate")
    faithfulness_rate: MetricValue = Field(alias="faithfulnessRate")
    usefulness_rate: MetricValue = Field(alias="usefulnessRate")
    q1: bool
    q2: bool
    q3: bool
    q4: bool


class EvaluationRunResult(StrictEvaluationModel):
    schema_version: Literal[1] = Field(alias="schemaVersion")
    run_id: str = Field(alias="runId", min_length=1, max_length=64)
    started_at: str = Field(alias="startedAt")
    finished_at: str = Field(alias="finishedAt")
    dataset_version: str = Field(alias="datasetVersion", min_length=1, max_length=256)
    dataset_sha256: str = Field(alias="datasetSha256")
    git_commit: str = Field(alias="gitCommit")
    worktree_dirty: bool = Field(alias="worktreeDirty")
    provider_mode: Literal["stub", "live"] = Field(alias="providerMode")
    evaluation_variants: tuple[Literal["primary", "rewrite_ablation"], Literal["primary", "rewrite_ablation"]] = Field(alias="evaluationVariants")
    principal_profile_id: str = Field(alias="principalProfileId", min_length=1, max_length=256)
    read_authorization_evidence_ref: str = Field(alias="readAuthorizationEvidenceRef", min_length=1, max_length=256)
    gate_evidence: tuple[GateEvidenceRecord, GateEvidenceRecord, GateEvidenceRecord, GateEvidenceRecord] = Field(alias="gateEvidence")
    question_policy_version: str = Field(alias="questionPolicyVersion", min_length=1, max_length=256)
    domain_catalog_version: str = Field(alias="domainCatalogVersion", min_length=1, max_length=256)
    flow_config_version: str = Field(alias="flowConfigVersion", min_length=1, max_length=256)
    retrieval_profile_version: str = Field(alias="retrievalProfileVersion", min_length=1, max_length=256)
    index_snapshot_ids: tuple[str, ...] = Field(alias="indexSnapshotIds")
    embedding_model: str = Field(alias="embeddingModel", min_length=1, max_length=256)
    rerank_model: str = Field(alias="rerankModel", min_length=1, max_length=256)
    model_task_versions: dict[ModelTaskVersionKey, str] = Field(alias="modelTaskVersions")
    deep_seek_model: str = Field(alias="deepSeekModel", min_length=1, max_length=256)
    policy_catalog_version: str = Field(alias="policyCatalogVersion", min_length=1, max_length=256)
    policy_catalog_sha256: str = Field(alias="policyCatalogSha256")
    policy_authority_id: str = Field(alias="policyAuthorityId", min_length=1, max_length=256)
    policy_export_id: str = Field(alias="policyExportId", min_length=1, max_length=256)
    policy_source_revision: str = Field(alias="policySourceRevision", min_length=1, max_length=256)
    evidence_rules_version: str = Field(alias="evidenceRulesVersion", min_length=1, max_length=256)
    case_results: tuple[EvaluationCaseResult, ...] = Field(alias="caseResults", min_length=1)
    aggregate_metrics: EvaluationMetrics = Field(alias="aggregateMetrics")
    safety_gate: SafetyGateResult = Field(alias="safetyGate")
    conclusion: Literal["effective", "partially_effective", "ineffective", "invalid_run"]
    reviewer: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_run(self) -> "EvaluationRunResult":
        if not _ASCII_SAFE.fullmatch(self.run_id):
            raise ValueError("evaluation.invalid_run_id")
        if not _RFC3339_UTC.fullmatch(self.started_at) or not _RFC3339_UTC.fullmatch(self.finished_at):
            raise ValueError("evaluation.invalid_timestamp")
        started = datetime.fromisoformat(self.started_at.replace("Z", "+00:00"))
        finished = datetime.fromisoformat(self.finished_at.replace("Z", "+00:00"))
        if finished < started:
            raise ValueError("evaluation.invalid_timestamp_order")
        if not _LOWER_HEX_64.fullmatch(self.dataset_sha256) or not _LOWER_HEX_64.fullmatch(self.policy_catalog_sha256):
            raise ValueError("evaluation.invalid_sha256")
        if not _LOWER_HEX_40.fullmatch(self.git_commit):
            raise ValueError("evaluation.invalid_git_commit")
        if self.evaluation_variants != ("primary", "rewrite_ablation"):
            raise ValueError("evaluation.invalid_variants")
        expected_gates = ("SA-GATE-002", "CR-GATE-003", "SA-GATE-003", "SA-GATE-006")
        if tuple(item.gate_id for item in self.gate_evidence) != expected_gates:
            raise ValueError("evaluation.invalid_gate_order")
        if any(not _LOWER_HEX_64.fullmatch(item) for item in self.index_snapshot_ids):
            raise ValueError("evaluation.invalid_index_snapshot")
        if len(set(self.index_snapshot_ids)) != len(self.index_snapshot_ids):
            raise ValueError("evaluation.duplicate_index_snapshot")
        expected_tasks = {"action_selection", "answer_generation", "knowledge_rewrite", "knowledge_summary"}
        if set(self.model_task_versions) != expected_tasks or any(not value for value in self.model_task_versions.values()):
            raise ValueError("evaluation.invalid_task_versions")
        if len({item.case_id for item in self.case_results}) != len(self.case_results):
            raise ValueError("evaluation.duplicate_case_result")
        if self.provider_mode == "stub" and self.conclusion != "invalid_run":
            raise ValueError("evaluation.stub_must_be_invalid")
        version_values = (
            self.dataset_version,
            self.principal_profile_id,
            self.question_policy_version,
            self.domain_catalog_version,
            self.flow_config_version,
            self.retrieval_profile_version,
            self.embedding_model,
            self.rerank_model,
            self.deep_seek_model,
            self.policy_catalog_version,
            self.policy_authority_id,
            self.policy_export_id,
            self.policy_source_revision,
            self.evidence_rules_version,
            *self.model_task_versions.values(),
        )
        if any(
            value != unicodedata.normalize("NFC", value)
            or any(ord(character) < 32 or ord(character) == 127 for character in value)
            for value in version_values
        ):
            raise ValueError("evaluation.invalid_version_value")
        if not _ASCII_SAFE.fullmatch(self.reviewer):
            raise ValueError("evaluation.invalid_reviewer")
        return self


class EvaluationFailureRecord(StrictEvaluationModel):
    schema_version: Literal[1] = Field(alias="schemaVersion")
    run_id: str = Field(alias="runId", min_length=1, max_length=64)
    started_at: str = Field(alias="startedAt")
    finished_at: str = Field(alias="finishedAt")
    git_commit: str = Field(alias="gitCommit")
    dataset_sha256: str = Field(alias="datasetSha256")
    failure_code: Literal[
        "bootstrap_invalid", "dataset_invalid", "snapshot_changed", "execution_failed", "schema_invalid", "write_failed"
    ] = Field(alias="failureCode")

    @model_validator(mode="after")
    def validate_failure(self) -> "EvaluationFailureRecord":
        if not _ASCII_SAFE.fullmatch(self.run_id):
            raise ValueError("evaluation.invalid_run_id")
        if not _RFC3339_UTC.fullmatch(self.started_at) or not _RFC3339_UTC.fullmatch(self.finished_at):
            raise ValueError("evaluation.invalid_timestamp")
        if datetime.fromisoformat(self.finished_at.replace("Z", "+00:00")) < datetime.fromisoformat(
            self.started_at.replace("Z", "+00:00")
        ):
            raise ValueError("evaluation.invalid_timestamp_order")
        if not _LOWER_HEX_40.fullmatch(self.git_commit) or not _LOWER_HEX_64.fullmatch(self.dataset_sha256):
            raise ValueError("evaluation.invalid_failure_identity")
        return self


@dataclass(frozen=True, slots=True, kw_only=True)
class EvaluationSystemSnapshot:
    repository_root: str
    worktree_entries: tuple[str, ...]
    git_commit: str
    worktree_dirty: bool
    provider_mode: Literal["stub", "live"]
    principal_profile_id: str
    read_authorization_evidence_ref: str
    gate_evidence: tuple[GateEvidenceRecord, GateEvidenceRecord, GateEvidenceRecord, GateEvidenceRecord]
    question_policy_version: str
    domain_catalog_version: str
    flow_config_version: str
    retrieval_profile_version: str
    index_snapshot_ids: tuple[str, ...]
    embedding_model: str
    rerank_model: str
    model_task_versions: dict[ModelTaskVersionKey, str]
    deep_seek_model: str
    policy_catalog_version: str
    policy_catalog_sha256: str
    policy_authority_id: str
    policy_export_id: str
    policy_source_revision: str
    evidence_rules_version: str


@dataclass(frozen=True, slots=True, kw_only=True)
class EvaluationExecutionFixture:
    make_scope: Callable[[str, str, str], RequestExecutionScope]
    synthetic_only: bool


def finite_mean(values: list[float]) -> float | Literal["not_applicable"]:
    if not values:
        return "not_applicable"
    result = sum(values) / len(values)
    if not math.isfinite(result):
        raise ValueError("evaluation.non_finite_metric")
    return result
