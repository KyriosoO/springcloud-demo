from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Text = Annotated[str, StringConstraints(min_length=1, max_length=4096)]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Priority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class SourcePolicy(StrictModel):
    schema_version: Literal[1]
    allowed_hosts: tuple[Text, ...] = Field(min_length=1, max_length=32)
    max_asset_bytes: int = Field(gt=0, le=52_428_800)
    max_redirects: Literal[3]


class CorpusSource(StrictModel):
    document_id: Text
    document_number: Text
    title: Text
    source_url: str = Field(max_length=4096)
    official_replacement_proof: Text


class CorpusSourceCatalog(StrictModel):
    schema_version: Literal[1]
    priority: Priority
    assets: tuple[CorpusSource, ...] = Field(min_length=1, max_length=512)


class SourceStatus(StrEnum):
    OK = "ok"
    UNREACHABLE = "source_unreachable"
    URL_MISSING = "url_missing"
    UNVERIFIED = "source_unverified"


class IntegrityStatus(StrEnum):
    VERIFIED_COMPLETE = "verified_complete"
    VERIFIED_GAP = "verified_gap"
    NOT_ASSESSABLE = "not_assessable"


class OcrStatus(StrEnum):
    NOT_APPLIED = "not_applied"
    ACCEPTED = "accepted"
    REVIEW_REQUIRED = "review_required"
    REJECTED = "rejected"


class IndexInventory(StrictModel):
    index_name: Text
    profile_version: Text
    chunk_count: int = Field(ge=0)
    indexed_text_length: int = Field(ge=0)
    keyword_indexed: bool
    vector_indexed: bool


class SourceProbe(StrictModel):
    requested_url: str | None = Field(default=None, max_length=4096)
    final_url: str | None = Field(default=None, max_length=4096)
    status: SourceStatus
    http_status: int | None = Field(default=None, ge=100, le=599)
    redirect_count: int = Field(ge=0, le=3)
    checked_at_utc: datetime | None = None
    official_replacement_proof: Text | None = None

    @model_validator(mode="after")
    def validate_status(self) -> SourceProbe:
        if self.status is SourceStatus.OK and (self.http_status != 200 or self.final_url is None):
            raise ValueError("ok source requires final_url and HTTP 200")
        if self.status is SourceStatus.URL_MISSING and self.requested_url is not None:
            raise ValueError("url_missing cannot include requested_url")
        return self


class IntegrityFinding(StrictModel):
    status: IntegrityStatus
    official_text_length: int | None = Field(default=None, ge=0)
    body_empty: bool | None = None
    truncated_suspected: bool | None = None
    only_attachment_names_suspected: bool | None = None
    attachment_reference_count: int | None = Field(default=None, ge=0)
    reason: Literal[
        "none",
        "empty_body",
        "truncated_body",
        "only_attachment_names",
        "attachment_missing",
        "parse_failed",
        "source_not_readable",
    ]

    @model_validator(mode="after")
    def validate_assessability(self) -> IntegrityFinding:
        assessed = self.status is not IntegrityStatus.NOT_ASSESSABLE
        values = (
            self.official_text_length,
            self.body_empty,
            self.truncated_suspected,
            self.only_attachment_names_suspected,
            self.attachment_reference_count,
        )
        if assessed and any(value is None for value in values):
            raise ValueError("assessed integrity requires all measurement fields")
        if not assessed and self.reason != "source_not_readable":
            raise ValueError("not_assessable requires source_not_readable")
        return self


class AuditItem(StrictModel):
    schema_version: Literal[2]
    document_id: Text
    document_number: str | None = Field(default=None, max_length=512)
    title: Text
    issuing_authority: str | None = Field(default=None, max_length=1024)
    published_date: str | None = Field(default=None, max_length=32)
    effective_date: str | None = Field(default=None, max_length=32)
    expiry_or_repeal_date: str | None = Field(default=None, max_length=32)
    validity_status: Literal["ACTIVE", "AMENDED", "EXPIRED", "PENDING", "REPEALED", "UNKNOWN"]
    logical_domain_id: Literal["tax.policy", "tax.law"]
    priority: Priority
    priority_reason: Text
    inventory: IndexInventory | None
    source: SourceProbe
    integrity: IntegrityFinding
    requires_human_review: bool

    @model_validator(mode="after")
    def prevent_unreachable_inference(self) -> AuditItem:
        if self.source.status is not SourceStatus.OK and self.integrity.status is not IntegrityStatus.NOT_ASSESSABLE:
            raise ValueError("unreadable source cannot assert body integrity")
        return self


class AuditSummary(StrictModel):
    schema_version: Literal[2]
    generated_at_utc: datetime
    current_alias: Text
    current_index: Text
    current_index_uuid: Text
    current_document_count: int = Field(ge=0)
    current_chunk_count: int = Field(ge=0)
    audit_item_count: int = Field(ge=0)
    priority_counts: dict[Priority, int]
    source_status_counts: dict[SourceStatus, int]
    integrity_status_counts: dict[IntegrityStatus, int]
    es_read_requests: int = Field(ge=0)
    source_get_budget: int = Field(ge=0)
    source_get_used: int = Field(ge=0)
    retry_count: Literal[0]
    index_write_count: Literal[0]
    audit_jsonl_sha256: Sha256

    @model_validator(mode="after")
    def validate_counts(self) -> AuditSummary:
        if sum(self.priority_counts.values()) != self.audit_item_count:
            raise ValueError("priority counts must equal audit item count")
        if sum(self.source_status_counts.values()) != self.audit_item_count:
            raise ValueError("source counts must equal audit item count")
        if sum(self.integrity_status_counts.values()) != self.audit_item_count:
            raise ValueError("integrity counts must equal audit item count")
        if self.source_get_used > self.source_get_budget:
            raise ValueError("source GET budget exceeded")
        return self


class AssetManifest(StrictModel):
    schema_version: Literal[1]
    asset_id: Text
    asset_version: Sha256
    parent_document_id: Text
    source_url: str = Field(max_length=4096)
    source_final_url: str = Field(max_length=4096)
    fetched_at_utc: datetime
    filename: Text
    source_extension: Text | None = None
    extension: Text
    format_mismatch: bool = False
    declared_mime: str | None = Field(default=None, max_length=256)
    detected_mime: Text
    sha256: Sha256
    byte_count: int = Field(gt=0, le=52_428_800)
    storage_relative_path: Text
    official_source_proof: Text

    @model_validator(mode="after")
    def validate_version(self) -> AssetManifest:
        if self.asset_version != self.sha256:
            raise ValueError("assetVersion must equal raw SHA-256")
        return self


class AttachmentReference(StrictModel):
    schema_version: Literal[1]
    parent_document_id: Text
    source_page_url: str = Field(max_length=4096)
    attachment_url: str = Field(max_length=4096)
    filename: Text
    extension: Literal[".pdf", ".doc", ".docx", ".xls", ".xlsx"]
    ordinal: int = Field(ge=1, le=4096)


class StageAFailure(StrictModel):
    phase: Literal["source", "download", "parse", "ocr", "embedding", "index", "release", "uat"]
    asset_id: str | None = Field(default=None, max_length=4096)
    source_url_sha256: Sha256 | None = None
    reason: Literal[
        "source_unreachable",
        "unsafe_url",
        "invalid_mime",
        "asset_too_large",
        "parse_failed",
        "ocr_review_required",
        "quality_rejected",
        "embedding_failed",
        "candidate_conflict",
        "index_failed",
        "release_precondition_failed",
        "uat_failed",
    ]


class AcquisitionResult(StrictModel):
    schema_version: Literal[1]
    run_id: Text
    started_at_utc: datetime
    completed_at_utc: datetime
    source_get_budget: int = Field(ge=0)
    source_get_used: int = Field(ge=0)
    retry_count: Literal[0]
    parent_count: int = Field(ge=0)
    attachment_reference_count: int = Field(ge=0)
    downloaded_asset_count: int = Field(ge=0)
    failures: tuple[StageAFailure, ...] = Field(default_factory=tuple, max_length=4096)

    @model_validator(mode="after")
    def validate_get_budget(self) -> AcquisitionResult:
        if self.source_get_used > self.source_get_budget:
            raise ValueError("source GET budget exceeded")
        return self


class ProcessingResult(StrictModel):
    schema_version: Literal[1]
    run_id: Text
    asset_count: int = Field(ge=0)
    accepted_asset_count: int = Field(ge=0)
    review_required_asset_count: int = Field(ge=0)
    rejected_asset_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    failures: tuple[StageAFailure, ...] = Field(default_factory=tuple, max_length=4096)

    @model_validator(mode="after")
    def validate_asset_counts(self) -> ProcessingResult:
        if self.accepted_asset_count + self.review_required_asset_count + self.rejected_asset_count != self.asset_count:
            raise ValueError("processing asset counts must equal assetCount")
        return self


class BlockKind(StrEnum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    CLAUSE = "clause"
    TABLE = "table"
    PAGE_BOUNDARY = "page_boundary"


class ParsedBlock(StrictModel):
    ordinal: int = Field(ge=1)
    kind: BlockKind
    text: Annotated[str, StringConstraints(min_length=1, max_length=200_000)]
    section_path: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    page_number: int | None = Field(default=None, ge=1)
    table_id: str | None = Field(default=None, max_length=256)
    clause_id: str | None = Field(default=None, max_length=256)


class ParsedDocument(StrictModel):
    schema_version: Literal[1]
    asset_id: Text
    asset_sha256: Sha256
    parser_name: Text
    parser_version: Text
    ocr_status: OcrStatus
    blocks: tuple[ParsedBlock, ...]
    quality_status: Literal["accepted", "review_required", "rejected"]
    quality_reasons: tuple[Text, ...] = Field(default_factory=tuple, max_length=32)

    @model_validator(mode="after")
    def validate_blocks(self) -> ParsedDocument:
        expected = tuple(range(1, len(self.blocks) + 1))
        if tuple(block.ordinal for block in self.blocks) != expected:
            raise ValueError("block ordinals must be contiguous")
        if self.quality_status == "accepted" and not self.blocks:
            raise ValueError("accepted document requires blocks")
        return self


class CorpusChunk(StrictModel):
    schema_version: Literal[1]
    chunk_id: Text
    document_id: Text
    asset_id: Text
    asset_version: Sha256
    ordinal: int = Field(ge=1)
    content: Annotated[str, StringConstraints(min_length=1, max_length=1600)]
    content_sha256: Sha256
    section_path: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    clause_id: str | None = Field(default=None, max_length=256)
    table_id: str | None = Field(default=None, max_length=256)
    ocr_applied: bool
    ocr_confidence_status: OcrStatus

    @field_validator("content_sha256")
    @classmethod
    def hash_is_lowercase(cls, value: str) -> str:
        return value.lower()

    @model_validator(mode="after")
    def validate_content_hash(self) -> CorpusChunk:
        if hashlib.sha256(self.content.encode("utf-8")).hexdigest() != self.content_sha256:
            raise ValueError("chunk content SHA-256 mismatch")
        return self


class BuildManifest(StrictModel):
    schema_version: Literal[1]
    candidate_index: Text
    candidate_index_uuid: Text
    source_index: Text
    source_index_uuid: Text
    mapping_version: Text
    parser_versions: dict[str, Text]
    chunker_version: Text
    embedding_model: Text
    embedding_dimensions: Literal[1024]
    source_document_count: int = Field(ge=0)
    source_chunk_count: int = Field(ge=0)
    asset_count: int = Field(ge=0)
    new_chunk_count: int = Field(ge=0)
    total_chunk_count: int = Field(ge=0)
    normalized_fingerprint: Sha256
    source_manifest_sha256: Sha256
    mapping_sha256: Sha256
    tool_source_sha256: Sha256
    build_completed_at_utc: datetime


class ReleaseState(StrictModel):
    schema_version: Literal[1]
    alias: Text
    old_index: Text
    old_index_uuid: Text
    candidate_index: Text
    candidate_index_uuid: Text
    phase: Literal["candidate", "rolled_back", "published"]
    executed_at_utc: datetime


class StageAUatCase(StrictModel):
    case_id: Annotated[str, StringConstraints(pattern=r"^UAT-KCORPUS-A-(0[1-9]|1[0-4])$")]
    evidence_kind: Literal["live_direct", "automated_test", "existing_contract"]
    evidence_refs: tuple[Text, ...] = Field(min_length=1, max_length=8)
    status: Literal["passed", "failed", "blocked"]
    failure_reason: Literal[
        "none",
        "source_missing",
        "parse_failed",
        "index_incomplete",
        "retrieval_failed",
        "authorization_failed",
        "evidence_invalid",
    ]

    @model_validator(mode="after")
    def validate_uat_status(self) -> StageAUatCase:
        if (self.status == "passed") != (self.failure_reason == "none"):
            raise ValueError("passed UAT case must have no failure reason")
        return self


class StageAUatResult(StrictModel):
    schema_version: Literal[1]
    run_id: Text
    current_alias: Text
    old_index: Text
    candidate_index: Text
    candidate_index_uuid: Text
    p0_document_count: int = Field(ge=0)
    p0_attachment_count: int = Field(ge=0)
    p0_chunk_count: int = Field(ge=0)
    model_outbound_count: Literal[0]
    business_call_count: Literal[0]
    cases: tuple[StageAUatCase, ...] = Field(min_length=14, max_length=14)
    passed_count: int = Field(ge=0, le=14)
    failed_count: int = Field(ge=0, le=14)
    stage_b_findings: tuple[Literal["domain_selection", "query_rewrite", "ranking", "failure_semantics"], ...] = Field(default_factory=tuple, max_length=4)
    conclusion: Literal["passed", "failed", "blocked"]
    completed_at_utc: datetime

    @model_validator(mode="after")
    def validate_uat_counts(self) -> StageAUatResult:
        identifiers = [case.case_id for case in self.cases]
        if len(set(identifiers)) != 14:
            raise ValueError("UAT case IDs must be unique")
        passed = sum(case.status == "passed" for case in self.cases)
        failed = len(self.cases) - passed
        if self.passed_count != passed or self.failed_count != failed:
            raise ValueError("UAT counts do not match cases")
        if (self.conclusion == "passed") != (failed == 0):
            raise ValueError("UAT conclusion does not match cases")
        return self
