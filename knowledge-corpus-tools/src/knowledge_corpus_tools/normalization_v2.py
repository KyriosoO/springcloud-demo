"""Offline, append-only source assertions for the corpus v2 work package.

This module deliberately has no parser, index, model, or online-runtime entrypoint.
The raw record and parsed source remain separate from the small document sidecar.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any, Literal
from urllib.parse import urljoin, urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from .errors import ContractError, StateConflict
from .jsonio import exclusive_write
from .models import BlockKind, ParsedDocument
from .safety import normalize_official_url

NORMALIZER_VERSION = "corpus-normalizer-v2"
SOURCE_TEXT_VERSION = "parsed-source-v2"
_SHA256 = r"^[0-9a-f]{64}$"
_MAX_RAW_RECORD_BYTES = 50 * 1024 * 1024
DATASET_RAW_FIELDS = frozenset({
    "title", "channel", "content", "document_number", "effect_level", "tax_type",
    "aging", "labels", "issuing_department", "written_date", "url",
})
_RAW_MULTI_VALUE_FIELDS = frozenset({"tax_type", "labels", "issuing_department"})


def _canonical(value: Any) -> bytes:
    """The v2 hash encoding has no terminal LF and never permits JSON NaN."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ContractError("duplicate JSON key")
        value[key] = item
    return value


def _reject_constant(_: str) -> None:
    raise ContractError("non-finite JSON number")


def strict_v2_json(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("invalid UTF-8 JSON") from exc


def _valid_raw_field_types(fields: dict[str, Any]) -> bool:
    for name, value in fields.items():
        if value is None or type(value) is str:
            continue
        if name in _RAW_MULTI_VALUE_FIELDS and type(value) is list and all(type(item) is str for item in value):
            continue
        return False
    return True


@dataclass(frozen=True)
class FrozenRawRecord:
    canonical_json: bytes
    canonical_sha256: str


def freeze_raw_record(raw: bytes) -> FrozenRawRecord:
    """Keep all 11 external fields intact; the sidecar stores only their hash/ref."""
    if len(raw) > _MAX_RAW_RECORD_BYTES:
        raise ContractError("source record exceeds asset budget")
    fields = strict_v2_json(raw)
    if type(fields) is not dict or fields.keys() != DATASET_RAW_FIELDS:
        raise ContractError("source record must contain the exact 11 dataset fields")
    if not _valid_raw_field_types(fields):
        raise ContractError("source record has invalid raw field types")
    canonical_json = _canonical(fields)
    return FrozenRawRecord(canonical_json=canonical_json, canonical_sha256=_sha256(canonical_json))


def resolve_official_source_url(
    source_url: str, *, verified_base_url: str, base_proof_ref: str,
    allowed_hosts: frozenset[str],
) -> str:
    """Resolve dataset-relative URLs only against an independently verified base."""
    if not base_proof_ref or len(base_proof_ref) > 2048:
        raise ContractError("relative URL requires verified official base source")
    base = normalize_official_url(verified_base_url, allowed_hosts)
    if urlsplit(source_url).scheme or urlsplit(source_url).netloc:
        return normalize_official_url(source_url, allowed_hosts)
    if not source_url.startswith("/") or source_url.startswith("//"):
        raise ContractError("relative official path must be root-relative")
    return normalize_official_url(urljoin(base, source_url), allowed_hosts)


class _StrictV2(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, alias_generator=to_camel,
        validate_by_alias=True, validate_by_name=False, serialize_by_alias=True,
    )


class SourceKind(StrEnum):
    DATASET = "dataset"
    OFFICIAL = "official"
    CURATED = "curated"


class TrustStatus(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    REVIEW_REQUIRED = "review_required"


class FieldOrigin(StrEnum):
    SOURCE = "source"
    MANUAL_VERIFIED = "manual_verified"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class FieldAssertion(_StrictV2):
    value: str | tuple[str, ...] | None
    origin: FieldOrigin
    source_ref: str | None = Field(default=None, max_length=2048)
    observed_at: datetime | None = None

    @model_validator(mode="after")
    def check_provenance(self) -> FieldAssertion:
        if self.origin is FieldOrigin.INFERRED:
            raise ValueError("inferred fields are not admitted in v2")
        if self.origin is FieldOrigin.UNKNOWN:
            if self.value is not None or self.source_ref is not None or self.observed_at is not None:
                raise ValueError("unknown field must not contain an assertion")
            return self
        if self.value is None or not self.source_ref or self.observed_at is None or self.observed_at.utcoffset() is None:
            raise ValueError("asserted field requires value, sourceRef and timezone-aware observedAt")
        values = (self.value,) if isinstance(self.value, str) else self.value
        if len(values) > 32 or any(not item or len(item) > 512 for item in values):
            raise ValueError("metadata value is empty or exceeds its bound")
        if len(set(values)) != len(values):
            raise ValueError("duplicate metadata values")
        return self


def unknown_field() -> FieldAssertion:
    return FieldAssertion.model_validate({"value": None, "origin": FieldOrigin.UNKNOWN})


def asserted_field(
    value: str | tuple[str, ...], *, origin: Literal["source", "manual_verified"],
    source_ref: str, observed_at: datetime,
) -> FieldAssertion:
    if isinstance(value, str):
        values: str | tuple[str, ...] = unicodedata.normalize("NFC", value)
    else:
        values = tuple(dict.fromkeys(unicodedata.normalize("NFC", item) for item in value))
    return FieldAssertion.model_validate(
        {"value": values, "origin": FieldOrigin(origin), "sourceRef": source_ref, "observedAt": observed_at}
    )


def asserted_raw_field(
    value: str | tuple[str, ...], *, source_ref: str, observed_at: datetime,
) -> FieldAssertion:
    return FieldAssertion.model_validate(
        {"value": value, "origin": FieldOrigin.SOURCE, "sourceRef": source_ref, "observedAt": observed_at}
    )


class MetadataV2(_StrictV2):
    title: FieldAssertion = Field(default_factory=unknown_field)
    document_number: FieldAssertion = Field(default_factory=unknown_field)
    channel_raw: FieldAssertion = Field(default_factory=unknown_field)
    channel_mapping_version: str | None = Field(default=None, max_length=512)
    document_type: FieldAssertion = Field(default_factory=unknown_field)
    effect_level_raw: FieldAssertion = Field(default_factory=unknown_field)
    effect_level_mapping_version: str | None = Field(default=None, max_length=512)
    tax_types: FieldAssertion = Field(default_factory=unknown_field)
    labels_raw: FieldAssertion = Field(default_factory=unknown_field)
    topics: FieldAssertion = Field(default_factory=unknown_field)
    issuers: FieldAssertion = Field(default_factory=unknown_field)
    applicable_regions: FieldAssertion = Field(default_factory=unknown_field)
    applicable_subjects: FieldAssertion = Field(default_factory=unknown_field)

    @model_validator(mode="after")
    def check_dimensions(self) -> MetadataV2:
        scalars = (self.title, self.document_number, self.channel_raw, self.document_type, self.effect_level_raw)
        lists = (self.tax_types, self.labels_raw, self.topics, self.issuers, self.applicable_regions, self.applicable_subjects)
        if any(item.value is not None and not isinstance(item.value, str) for item in scalars):
            raise ValueError("scalar metadata dimension requires a string")
        if any(item.value is not None and not isinstance(item.value, tuple) for item in lists):
            raise ValueError("label dimension requires an ordered tuple")
        if self.document_type.value not in (None, "law", "regulation", "policy", "interpretation", "other", "unknown"):
            raise ValueError("invalid documentType")
        normalized = (self.title, self.document_number, self.document_type, self.tax_types, self.topics, self.issuers, self.applicable_regions, self.applicable_subjects)
        for item in normalized:
            values = (item.value,) if isinstance(item.value, str) else item.value or ()
            if any(not unicodedata.is_normalized("NFC", value) for value in values):
                raise ValueError("normalized metadata must be NFC")
        if self.channel_mapping_version and self.channel_raw.value is None:
            raise ValueError("channel mapping without source value")
        if self.effect_level_mapping_version and self.effect_level_raw.value is None:
            raise ValueError("effect level mapping without source value")
        return self


class TemporalV2(_StrictV2):
    written_date: FieldAssertion = Field(default_factory=unknown_field)
    published_date: FieldAssertion = Field(default_factory=unknown_field)
    effective_from: FieldAssertion = Field(default_factory=unknown_field)
    effective_to: FieldAssertion = Field(default_factory=unknown_field)
    validity_raw: FieldAssertion = Field(default_factory=unknown_field)
    validity_status: FieldAssertion = Field(default_factory=unknown_field)
    validity_mapping_version: str | None = Field(default=None, max_length=512)
    legacy_effective_date_raw: FieldAssertion = Field(default_factory=unknown_field)
    snapshot_at: datetime
    status_verified_at: datetime | None = None

    @model_validator(mode="after")
    def check_dates(self) -> TemporalV2:
        if self.snapshot_at.utcoffset() is None or (self.status_verified_at and self.status_verified_at.utcoffset() is None):
            raise ValueError("source times must have a timezone")
        for item in (self.written_date, self.published_date, self.effective_from, self.effective_to):
            if item.value is None:
                continue
            if not isinstance(item.value, str):
                raise ValueError("date must be a scalar")
            try:
                parsed = date.fromisoformat(item.value)
            except ValueError as exc:
                raise ValueError("date must be ISO YYYY-MM-DD") from exc
            if parsed.isoformat() != item.value:
                raise ValueError("date must be ISO YYYY-MM-DD")
        if self.validity_status.value not in (None, "active", "partially_invalid", "repealed", "pending", "unknown"):
            raise ValueError("invalid validityStatus")
        if self.validity_status.value is not None and not self.validity_mapping_version:
            raise ValueError("validity mapping version is required")
        if self.status_verified_at is not None:
            if self.validity_status.origin is not FieldOrigin.MANUAL_VERIFIED or self.validity_status.observed_at != self.status_verified_at:
                raise ValueError("statusVerifiedAt requires the actual status verification assertion")
        return self


def _inverted_effective_dates(temporal: TemporalV2) -> bool:
    start = temporal.effective_from.value
    end = temporal.effective_to.value
    return isinstance(start, str) and isinstance(end, str) and start > end


_RAW_ASSERTION_FIELDS = {
    "metadata.title": ("title", True),
    "metadata.document_number": ("document_number", True),
    "metadata.channel_raw": ("channel", False),
    "metadata.effect_level_raw": ("effect_level", False),
    "metadata.tax_types": ("tax_type", True),
    "metadata.labels_raw": ("labels", False),
    "metadata.issuers": ("issuing_department", True),
    "temporal.written_date": ("written_date", True),
    "temporal.validity_raw": ("aging", False),
}


def _check_source_fields(metadata: MetadataV2, temporal: TemporalV2,
                         raw_record: FrozenRawRecord | None) -> bool:
    raw = strict_v2_json(raw_record.canonical_json) if raw_record is not None else None
    all_source_assertions_checked = True
    for group_name, group in (("metadata", metadata), ("temporal", temporal)):
        for name in type(group).model_fields:
            assertion = getattr(group, name)
            if not isinstance(assertion, FieldAssertion) or assertion.origin is not FieldOrigin.SOURCE:
                continue
            mapping = _RAW_ASSERTION_FIELDS.get(f"{group_name}.{name}")
            if assertion.source_ref is None or not assertion.source_ref.startswith("raw:"):
                all_source_assertions_checked = False
                continue
            if raw is None or mapping is None or assertion.source_ref != f"raw:{mapping[0]}":
                raise ContractError("source field has no verifiable raw field binding")
            actual = raw[mapping[0]]
            if mapping[1]:
                if isinstance(actual, str):
                    actual = unicodedata.normalize("NFC", actual)
                elif isinstance(actual, list) and all(isinstance(item, str) for item in actual):
                    actual = tuple(dict.fromkeys(unicodedata.normalize("NFC", item) for item in actual))
            elif isinstance(actual, list):
                actual = tuple(actual)
            if assertion.value != actual:
                raise ContractError("source field value does not match frozen raw record")
    return all_source_assertions_checked


def _check_dataset_source_url(source: SourceAssertionV2, raw_record: FrozenRawRecord | None) -> bool:
    if source.kind is not SourceKind.DATASET:
        return True
    if raw_record is None:
        raise ContractError("dataset source requires its frozen raw record")
    original = strict_v2_json(raw_record.canonical_json)["url"]
    if not isinstance(original, str) or not original.strip():
        if source.original_url is not None:
            raise ContractError("dataset original URL differs from frozen raw field")
        return False
    if source.original_url != original:
        raise ContractError("dataset original URL differs from frozen raw field")
    return True


def _check_dataset_core_text(source: SourceAssertionV2, raw_record: FrozenRawRecord | None) -> bool:
    if source.kind is not SourceKind.DATASET:
        return True
    if raw_record is None:
        raise ContractError("dataset source requires its frozen raw record")
    raw = strict_v2_json(raw_record.canonical_json)
    return all(isinstance(raw[name], str) and bool(raw[name].strip()) for name in ("title", "content"))


class RelationV2(_StrictV2):
    parent_document_id: str | None = Field(default=None, max_length=512)
    parent_asset_id: str | None = Field(default=None, max_length=512)
    relation_type: Literal["attachment"] | None = None
    parent_source_ref: str | None = Field(default=None, max_length=2048)
    revises: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    replaces: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    revision_source_ref: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def check_provenance(self) -> RelationV2:
        if self.relation_type == "attachment":
            if not self.parent_document_id or not self.parent_source_ref:
                raise ValueError("attachment requires parent identity and source")
        elif self.parent_document_id or self.parent_asset_id or self.parent_source_ref:
            raise ValueError("parent identity requires attachment relation")
        if bool(self.revises or self.replaces) != bool(self.revision_source_ref):
            raise ValueError("revision links require an exact source")
        if len(set(self.revises)) != len(self.revises) or len(set(self.replaces)) != len(self.replaces):
            raise ValueError("duplicate revision target")
        return self


class SourceAssertionV2(_StrictV2):
    kind: SourceKind
    source_record_id: str | None = Field(default=None, max_length=512)
    source_snapshot: str = Field(min_length=1, max_length=512)
    dataset_repo: str | None = Field(default=None, max_length=512)
    dataset_revision: str | None = Field(default=None, max_length=512)
    collected_at: datetime | None = None
    original_url: str | None = Field(default=None, max_length=2048)
    final_url: str | None = Field(default=None, max_length=2048)
    official_publisher: str | None = Field(default=None, max_length=512)
    official_proof_ref: str | None = Field(default=None, max_length=2048)
    license_ref: str | None = Field(default=None, max_length=2048)
    raw_record_ref: str | None = Field(default=None, max_length=2048)
    raw_hash_scope: Literal["asset_bytes", "source_record_canonical_json_v1"]
    raw_sha256: str = Field(pattern=_SHA256)
    asset_id: str | None = Field(default=None, max_length=512)
    asset_version: str | None = Field(default=None, pattern=_SHA256)

    @model_validator(mode="after")
    def check_identity(self) -> SourceAssertionV2:
        if self.collected_at is not None and self.collected_at.utcoffset() is None:
            raise ValueError("collectedAt must have a timezone")
        if bool(self.asset_id) != bool(self.asset_version):
            raise ValueError("asset identity requires both assetId and assetVersion")
        if self.kind is SourceKind.DATASET:
            if not all((self.source_record_id, self.dataset_repo, self.dataset_revision, self.raw_record_ref)) or self.raw_hash_scope != "source_record_canonical_json_v1":
                raise ValueError("dataset requires frozen repo/revision/record and canonical raw hash")
        if self.raw_hash_scope == "asset_bytes":
            if not self.asset_id or self.asset_version != self.raw_sha256:
                raise ValueError("asset bytes require matching asset identity and SHA")
        elif not self.raw_record_ref:
            raise ValueError("source record hash requires immutable record ref")
        if self.kind is SourceKind.OFFICIAL and (not self.official_publisher or not self.official_proof_ref or not self.final_url):
            raise ValueError("official source requires publisher and verification source")
        return self


class SourceTextBindingV2(_StrictV2):
    source_ref: str = Field(min_length=1, max_length=2048)
    source_text_version: Literal["parsed-source-v2"]
    source_text_sha256: str = Field(pattern=_SHA256)
    parser_version: str = Field(min_length=1, max_length=512)
    span_unit: Literal["unicode_code_point"]
    span_scope: Literal["parsed_source"]
    order_status: TrustStatus
    structure_status: TrustStatus


class CorpusDocumentV2(_StrictV2):
    schema_version: Literal[2]
    normalizer_version: Literal["corpus-normalizer-v2"]
    document_id: str = Field(min_length=1, max_length=512)
    document_version_id: str = Field(pattern=_SHA256)
    source: SourceAssertionV2
    metadata: MetadataV2
    temporal: TemporalV2
    relations: RelationV2
    parsed_source: SourceTextBindingV2 | None = None
    review_status: TrustStatus
    normalized_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def check_hashes(self) -> CorpusDocumentV2:
        if self.document_version_id != document_version_id(self.document_id, self.source):
            raise ValueError("documentVersionId mismatch")
        content = self.model_dump(mode="json", by_alias=True, exclude={"normalized_sha256"})
        if self.normalized_sha256 != _sha256(_canonical(content)):
            raise ValueError("normalizedSha256 mismatch")
        if _inverted_effective_dates(self.temporal) and self.review_status is not TrustStatus.REVIEW_REQUIRED:
            raise ValueError("contradictory effective dates require review")
        if self.relations.parent_document_id == self.document_id:
            raise ValueError("attachment cannot name itself as parent document")
        if self.parsed_source is None and self.review_status is TrustStatus.VERIFIED:
            raise ValueError("missing parsed source cannot be verified")
        if self.parsed_source and self.review_status is TrustStatus.VERIFIED and self.parsed_source.structure_status is not TrustStatus.VERIFIED:
            raise ValueError("unverified structure cannot be promoted")
        return self


def document_version_id(document_id: str, source: SourceAssertionV2) -> str:
    identity = {
        "documentId": document_id,
        "sourceKind": source.kind.value,
        "sourceRecordId": source.source_record_id,
        "sourceSnapshot": source.source_snapshot,
        "rawHashScope": source.raw_hash_scope,
        "rawSha256": source.raw_sha256,
        "assetId": source.asset_id,
        "assetVersion": source.asset_version,
    }
    return _sha256(_canonical(identity))


class ParsedSourceBlockV2(_StrictV2):
    block_ordinal: int = Field(ge=1)
    kind: BlockKind
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    block_sha256: str = Field(pattern=_SHA256)


class ParsedSourceV2(_StrictV2):
    schema_version: Literal[2]
    source_text_version: Literal["parsed-source-v2"]
    asset_id: str = Field(min_length=1, max_length=512)
    asset_sha256: str = Field(pattern=_SHA256)
    parser_name: str = Field(min_length=1, max_length=512)
    parser_version: str = Field(min_length=1, max_length=512)
    text: str = Field(min_length=1)
    source_text_sha256: str = Field(pattern=_SHA256)
    span_unit: Literal["unicode_code_point"]
    span_scope: Literal["parsed_source"]
    blocks: tuple[ParsedSourceBlockV2, ...] = Field(min_length=1)
    order_status: TrustStatus
    structure_status: TrustStatus
    order_proof_ref: str | None = Field(default=None, max_length=2048)
    structure_proof_ref: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def check_replay(self) -> ParsedSourceV2:
        if self.source_text_sha256 != _sha256(self.text.encode("utf-8")):
            raise ValueError("parsed source hash mismatch")
        position = 0
        for ordinal, block in enumerate(self.blocks, start=1):
            if block.block_ordinal != ordinal or block.start != position or block.end <= block.start or block.end > len(self.text):
                raise ValueError("parsed block order/span mismatch")
            if _sha256(self.text[block.start:block.end].encode("utf-8")) != block.block_sha256:
                raise ValueError("parsed block text hash mismatch")
            position = block.end
            if ordinal < len(self.blocks):
                if self.text[position:position + 1] != "\n":
                    raise ValueError("parsed blocks require one LF separator")
                position += 1
        if position != len(self.text):
            raise ValueError("parsed source has unclaimed text")
        if self.order_status is TrustStatus.VERIFIED and not self.order_proof_ref:
            raise ValueError("verified order requires independent source proof")
        if self.parser_name == "python-docx" and self.parser_version == "1.2.0" and self.order_status is TrustStatus.VERIFIED:
            raise ValueError("legacy DOCX order cannot be verified")
        if self.structure_status is TrustStatus.VERIFIED and self.order_status is not TrustStatus.VERIFIED:
            raise ValueError("structure cannot outrank source order")
        if self.structure_status is TrustStatus.VERIFIED and not self.structure_proof_ref:
            raise ValueError("verified structure requires independent source proof")
        if any(block.kind is BlockKind.TABLE for block in self.blocks) and self.structure_status is TrustStatus.VERIFIED:
            raise ValueError("legacy flattened table cannot be verified")
        return self


def parsed_source_v2(
    parsed: ParsedDocument, *, order_proof_ref: str | None = None,
    structure_proof_ref: str | None = None,
) -> ParsedSourceV2:
    if parsed.quality_status != "accepted" or not parsed.blocks:
        raise ContractError("parsed source requires accepted ordered blocks")
    legacy_docx = parsed.parser_name == "python-docx" and parsed.parser_version == "1.2.0"
    if legacy_docx and order_proof_ref is not None:
        raise ContractError("legacy DOCX requires the later parser-order repair")
    text = "\n".join(block.text for block in parsed.blocks)
    blocks: list[dict[str, Any]] = []
    position = 0
    for block in parsed.blocks:
        end = position + len(block.text)
        blocks.append({"blockOrdinal": block.ordinal, "kind": block.kind, "start": position, "end": end, "blockSha256": _sha256(block.text.encode("utf-8"))})
        position = end + 1
    has_table = any(block.kind is BlockKind.TABLE for block in parsed.blocks)
    if structure_proof_ref and (not order_proof_ref or has_table or legacy_docx):
        raise ContractError("structure proof requires verified order and non-flattened blocks")
    order_status = TrustStatus.VERIFIED if order_proof_ref else TrustStatus.REVIEW_REQUIRED if legacy_docx and has_table else TrustStatus.UNVERIFIED
    structure_status = TrustStatus.REVIEW_REQUIRED if has_table else TrustStatus.VERIFIED if structure_proof_ref else TrustStatus.UNVERIFIED
    return ParsedSourceV2.model_validate_json(_canonical({
        "schemaVersion": 2, "sourceTextVersion": SOURCE_TEXT_VERSION,
        "assetId": parsed.asset_id, "assetSha256": parsed.asset_sha256,
        "parserName": parsed.parser_name, "parserVersion": parsed.parser_version,
        "text": text, "sourceTextSha256": _sha256(text.encode("utf-8")),
        "spanUnit": "unicode_code_point", "spanScope": "parsed_source",
        "blocks": blocks, "orderStatus": order_status, "structureStatus": structure_status,
        "orderProofRef": order_proof_ref, "structureProofRef": structure_proof_ref,
    }))


def build_document_v2(
    *, document_id: str, source: SourceAssertionV2, metadata: MetadataV2,
    temporal: TemporalV2, relations: RelationV2, raw_record: FrozenRawRecord | None = None,
    parsed_source: ParsedSourceV2 | None = None, parsed_source_ref: str | None = None,
) -> CorpusDocumentV2:
    if source.raw_hash_scope == "source_record_canonical_json_v1":
        if raw_record is None or raw_record.canonical_sha256 != source.raw_sha256:
            raise ContractError("frozen source record hash mismatch")
    elif raw_record is not None:
        raise ContractError("asset bytes and source record hash scopes must not be mixed")
    fields_checked = _check_source_fields(metadata, temporal, raw_record)
    url_checked = _check_dataset_source_url(source, raw_record)
    core_checked = _check_dataset_core_text(source, raw_record)
    all_source_assertions_checked = fields_checked and url_checked and core_checked
    if parsed_source is not None:
        if not parsed_source_ref or source.asset_id != parsed_source.asset_id or source.asset_version != parsed_source.asset_sha256:
            raise ContractError("parsed source must bind the same immutable asset")
        binding: dict[str, Any] | None = {
            "sourceRef": parsed_source_ref, "sourceTextVersion": SOURCE_TEXT_VERSION,
            "sourceTextSha256": parsed_source.source_text_sha256,
            "parserVersion": parsed_source.parser_version,
            "spanUnit": "unicode_code_point", "spanScope": "parsed_source",
            "orderStatus": parsed_source.order_status,
            "structureStatus": parsed_source.structure_status,
        }
        review_status = parsed_source.structure_status
    else:
        if parsed_source_ref is not None:
            raise ContractError("parsed source ref without parsed source")
        binding = None
        review_status = TrustStatus.UNVERIFIED
    if _inverted_effective_dates(temporal):
        review_status = TrustStatus.REVIEW_REQUIRED
    elif not all_source_assertions_checked and review_status is TrustStatus.VERIFIED:
        review_status = TrustStatus.UNVERIFIED
    payload: dict[str, Any] = {
        "schemaVersion": 2, "normalizerVersion": NORMALIZER_VERSION,
        "documentId": document_id, "documentVersionId": document_version_id(document_id, source),
        "source": source.model_dump(mode="json", by_alias=True),
        "metadata": metadata.model_dump(mode="json", by_alias=True),
        "temporal": temporal.model_dump(mode="json", by_alias=True),
        "relations": relations.model_dump(mode="json", by_alias=True),
        "parsedSource": binding, "reviewStatus": review_status.value,
    }
    payload["normalizedSha256"] = _sha256(_canonical(payload))
    return CorpusDocumentV2.model_validate_json(_canonical(payload))


def load_document_v2(raw: bytes) -> CorpusDocumentV2:
    strict_v2_json(raw)
    return CorpusDocumentV2.model_validate_json(raw)


def load_parsed_source_v2(raw: bytes) -> ParsedSourceV2:
    strict_v2_json(raw)
    return ParsedSourceV2.model_validate_json(raw)


def v2_json_bytes(value: CorpusDocumentV2 | ParsedSourceV2) -> bytes:
    return _canonical(value.model_dump(mode="json", by_alias=True))


def _workspace_artifact(workspace: Path, ref: str, *, partition: str) -> Path:
    if "\\" in ref:
        raise ContractError("v2 artifact ref must use POSIX separators")
    relative = PurePosixPath(ref)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.parts[0] != partition:
        raise ContractError("v2 artifact ref escaped its workspace partition")
    target = (workspace / Path(*relative.parts)).resolve()
    partition_root = (workspace / partition).resolve()
    if partition_root not in target.parents:
        raise ContractError("v2 artifact path escaped workspace partition")
    return target


def _write_immutable(path: Path, raw: bytes) -> None:
    if path.exists():
        if path.read_bytes() != raw:
            raise StateConflict("existing immutable v2 artifact differs")
        return
    exclusive_write(path, raw)


def _verify_local_asset(path: Path, expected_sha256: str) -> None:
    if not path.is_absolute() or not path.is_file():
        raise ContractError("immutable local asset path is required")
    digest = hashlib.sha256()
    total = 0
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                total += len(block)
                if total > _MAX_RAW_RECORD_BYTES:
                    raise ContractError("local asset exceeds acquisition byte budget")
                digest.update(block)
    except OSError as exc:
        raise ContractError("local asset could not be read") from exc
    if total == 0 or digest.hexdigest() != expected_sha256:
        raise ContractError("local asset bytes SHA-256 mismatch")


def _source_claim(document: CorpusDocumentV2) -> tuple[str, bytes]:
    source = document.source
    identity = {
        "documentId": document.document_id, "sourceKind": source.kind.value,
        "sourceRecordId": source.source_record_id, "sourceSnapshot": source.source_snapshot,
        "assetId": source.asset_id,
    }
    claim = {
        **identity, "rawHashScope": source.raw_hash_scope, "rawSha256": source.raw_sha256,
        "assetVersion": source.asset_version, "documentVersionId": document.document_version_id,
    }
    return f"manifests/corpus-source-claims-v2/{_sha256(_canonical(identity))}.json", _canonical(claim)


def write_v2_artifacts(
    *, workspace: Path, document: CorpusDocumentV2,
    raw_record: FrozenRawRecord | None = None, parsed_source: ParsedSourceV2 | None = None,
    asset_path: Path | None = None,
    all_parent_document_ids: frozenset[str] | None = None,
    all_parent_asset_ids: frozenset[str] = frozenset(),
    frozen_relation_records: tuple[CorpusDocumentV2, ...] | None = None,
) -> Path:
    """Publish the small sidecar last; an interrupted run cannot expose an unbacked one."""
    if not workspace.is_absolute():
        raise ContractError("v2 workspace must be explicit and absolute")
    root = workspace.resolve()
    if document.relations.parent_document_id or document.relations.revises or document.relations.replaces:
        if all_parent_document_ids is None or frozen_relation_records is None:
            raise ContractError("linked sidecar requires frozen full relation inventory")
        validate_relations_v2(
            (*frozen_relation_records, document), all_parent_document_ids=all_parent_document_ids,
            all_parent_asset_ids=all_parent_asset_ids,
        )
    if document.source.raw_hash_scope == "source_record_canonical_json_v1":
        fields_checked = _check_source_fields(document.metadata, document.temporal, raw_record)
        url_checked = _check_dataset_source_url(document.source, raw_record)
        core_checked = _check_dataset_core_text(document.source, raw_record)
        checked = fields_checked and url_checked and core_checked
        if not checked and document.review_status is TrustStatus.VERIFIED:
            raise ContractError("unverified source assertion cannot publish as verified")
    elif _check_source_fields(document.metadata, document.temporal, None) is False and document.review_status is TrustStatus.VERIFIED:
        raise ContractError("unverified source assertion cannot publish as verified")
    if document.source.asset_id is not None or parsed_source is not None or document.source.raw_hash_scope == "asset_bytes":
        if asset_path is None or document.source.asset_version is None:
            raise ContractError("asset-backed sidecar requires a local asset and version")
        _verify_local_asset(asset_path, document.source.asset_version)
        if document.source.raw_hash_scope == "asset_bytes" and document.source.raw_sha256 != document.source.asset_version:
            raise ContractError("raw asset hash and asset version mismatch")
    elif asset_path is not None:
        raise ContractError("unbound local asset path")
    if document.source.raw_hash_scope == "source_record_canonical_json_v1":
        if raw_record is None or raw_record.canonical_sha256 != document.source.raw_sha256 or not document.source.raw_record_ref:
            raise ContractError("sidecar source record does not match frozen raw record")
        raw_path = _workspace_artifact(root, document.source.raw_record_ref, partition="raw")
    else:
        if raw_record is not None:
            raise ContractError("asset sidecar must not duplicate raw bytes as a source record")
        raw_path = None
    if document.parsed_source is not None:
        binding = document.parsed_source
        if (parsed_source is None or parsed_source.source_text_sha256 != binding.source_text_sha256
                or parsed_source.asset_id != document.source.asset_id
                or parsed_source.asset_sha256 != document.source.asset_version
                or parsed_source.parser_version != binding.parser_version
                or parsed_source.order_status is not binding.order_status
                or parsed_source.structure_status is not binding.structure_status):
            raise ContractError("sidecar parsed source binding mismatch")
        parsed_path = _workspace_artifact(root, binding.source_ref, partition="parsed")
    else:
        if parsed_source is not None:
            raise ContractError("unbound parsed source is not a sidecar artifact")
        parsed_path = None
    sidecar_path = _workspace_artifact(
        root, f"manifests/corpus-document-v2/{document.document_version_id}.json", partition="manifests"
    )
    claim_ref, claim_bytes = _source_claim(document)
    claim_path = _workspace_artifact(root, claim_ref, partition="manifests")
    raw_bytes = raw_record.canonical_json if raw_record else None
    parsed_bytes = v2_json_bytes(parsed_source) if parsed_source else None
    sidecar_bytes = v2_json_bytes(document)
    if raw_path and raw_path.exists() and raw_path.read_bytes() != raw_bytes:
        raise StateConflict("existing immutable raw record differs")
    if parsed_path and parsed_path.exists() and parsed_path.read_bytes() != parsed_bytes:
        raise StateConflict("existing immutable parsed source differs")
    if sidecar_path.exists() and sidecar_path.read_bytes() != sidecar_bytes:
        raise StateConflict("existing immutable sidecar differs")
    if claim_path.exists() and claim_path.read_bytes() != claim_bytes:
        raise StateConflict("same source assertion has conflicting raw content")
    _write_immutable(claim_path, claim_bytes)
    if raw_path and raw_bytes is not None:
        _write_immutable(raw_path, raw_bytes)
    if parsed_path and parsed_bytes is not None:
        _write_immutable(parsed_path, parsed_bytes)
    _write_immutable(sidecar_path, sidecar_bytes)
    return sidecar_path


def validate_source_span(source: ParsedSourceV2, *, start: int, end: int, content: str, body_sha256: str) -> None:
    if not 0 <= start < end <= len(source.text) or source.text[start:end] != content or _sha256(content.encode("utf-8")) != body_sha256:
        raise ContractError("source span is not an exact continuous body substring")


def validate_relations_v2(
    records: tuple[CorpusDocumentV2, ...], *, all_parent_document_ids: frozenset[str],
    all_parent_asset_ids: frozenset[str] = frozenset(),
) -> None:
    """Validate against the frozen full parent inventory, never a sample subset."""
    seen_versions: dict[str, str] = {}
    seen_assertions: dict[tuple[str, str, str | None, str, str | None], tuple[str, str, str | None]] = {}
    known_documents = all_parent_document_ids | frozenset(record.document_id for record in records)
    edges: dict[str, set[str]] = {}
    for record in records:
        previous = seen_versions.setdefault(record.document_version_id, record.normalized_sha256)
        if previous != record.normalized_sha256:
            raise ContractError("duplicate document version has conflicting normalized content")
        source = record.source
        assertion_key = (record.document_id, source.kind.value, source.source_record_id, source.source_snapshot, source.asset_id)
        raw_identity = (source.raw_hash_scope, source.raw_sha256, source.asset_version)
        prior_raw = seen_assertions.setdefault(assertion_key, raw_identity)
        if prior_raw != raw_identity:
            raise ContractError("same source assertion has conflicting raw content")
        relation = record.relations
        if relation.parent_document_id == record.document_id:
            raise ContractError("attachment cannot name itself as parent document")
        if relation.parent_document_id and relation.parent_document_id not in all_parent_document_ids:
            raise ContractError("attachment parent is absent from the frozen full inventory")
        if relation.parent_asset_id and relation.parent_asset_id not in all_parent_asset_ids:
            raise ContractError("attachment parent asset is absent from the frozen full inventory")
        targets = relation.revises + relation.replaces
        if any(target not in known_documents for target in targets):
            raise ContractError("revision target is absent from the frozen full inventory")
        edges.setdefault(record.document_id, set()).update(targets)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(document_id: str) -> None:
        if document_id in visiting:
            raise ContractError("revision relationship cycle")
        if document_id in visited:
            return
        visiting.add(document_id)
        for target in edges.get(document_id, ()):
            visit(target)
        visiting.remove(document_id)
        visited.add(document_id)

    for document_id in edges:
        visit(document_id)
