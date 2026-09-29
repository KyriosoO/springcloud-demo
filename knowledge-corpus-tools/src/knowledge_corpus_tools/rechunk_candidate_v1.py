"""One-use, offline candidate builder for a frozen structure or representation comparison.

This module never publishes an alias or obtains a model client.  The caller owns
the loopback ES client and a preflighted, one-use vector preparation callback.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import secrets
import struct
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, NoReturn

import httpx

from .chunking_v2 import ChunkingResultV2, RetrievalChunkV2, StructureUnitV2
from .errors import ContractError
from .normalization_v2 import (
    CorpusDocumentV2, ParsedSourceV2, load_document_v2,
    load_parsed_source_v2, validate_source_span, v2_json_bytes,
)
from .retrieval_representation_v2 import (
    RetrievalRepresentationV2, build_retrieval_representation_v2,
)
from .vector_candidate import (
    ACL_FIELDS, POLICY_CATEGORIES, canonical_bytes, mapping_fingerprint,
)
from .vector_representation import VectorRepresentation, build_vector_representation

_HASH = re.compile(r"[0-9a-f]{64}")
_INDEX = re.compile(r"agent-doc-tax-policy-v[1-9][0-9]*-[0-9]{8}-[a-z0-9-]+")
_ALIAS = re.compile(r"agent-doc-tax-policy-v[1-9][0-9]*-read")
_OWNER_ALIAS = re.compile(r"agent-knowledge-build-owner-[0-9a-f]{32}")
_OWNER_FLAGS = {"is_hidden": True, "is_write_index": False}
_STRUCTURE_FIELDS = {
    "documentVersionId": {"type": "keyword"},
    "structureUnitId": {"type": "keyword"},
    "sourceTextSha256": {"type": "keyword"},
    "sourceStart": {"type": "long"},
    "sourceEnd": {"type": "long"},
}
_TRACE_FIELDS = (
    "vectorRepresentationVersion", "vectorInputSha256",
    "vectorBodySha256", "vectorModelSnapshotSha256",
)
_RECOMPUTED = frozenset({
    "content", "contentHash", "snippet", "chunkId", "chunkIndex", "chunkCount",
    "charStart", "charEnd", "section", "sectionPath", "clauseId", "tableId",
    "chunkStrategy", "chunkVersion", "indexVersion", "indexedAt", "parserVersion",
    "embedding", *_TRACE_FIELDS,
})
_EXIT = frozenset({"parentSectionId", "sourceChunkIds"})
_TYPED_REQUIRED = {
    "documentId": 256, "chunkId": 256, "title": 256, "materialType": 256,
    "aclRef": 256,
}
_TYPED_OPTIONAL = {"sourceUrl": 1024, "documentNo": 256}
_PAGE = 250
_BATCH = 32
_HTTP_LIMIT = 400
_MAX_RESPONSE = 16 * 1024 * 1024

Vector = tuple[float, ...]
Representation = VectorRepresentation | RetrievalRepresentationV2


class RechunkCandidateError(ContractError):
    """Finite, text-free failure; provider bodies and exceptions are never retained."""

    def __init__(self, reason: str, phase: str, seal_status: str = "not_needed") -> None:
        self.reason = reason if reason in {
            "spec_invalid", "client_invalid", "input_invalid", "source_changed",
            "alias_changed", "source_not_ready", "candidate_exists", "owner_alias_exists", "scan_invalid",
            "vector_invalid", "provenance_invalid", "inheritance_conflict",
            "source_span_invalid", "typed_projection_invalid", "mapping_invalid",
            "budget_exceeded", "preparation_invalid", "clone_unacknowledged",
            "model_identity_invalid",
            "candidate_ownership_unknown", "candidate_changed", "bulk_failed",
            "write_unacknowledged", "refresh_failed", "verify_failed", "http_invalid",
            "operation_invalid",
        } else "operation_invalid"
        self.phase = phase if phase in {
            "preflight", "prepare", "clone", "mutate", "verify",
        } else "preflight"
        self.seal_status = seal_status if seal_status in {
            "not_needed", "sealed", "candidate_seal_failed", "ownership_unknown",
        } else "candidate_seal_failed"
        super().__init__(f"{self.phase}:{self.reason}:{self.seal_status}")


def new_build_owner_alias() -> str:
    """Generate the one-use alias to freeze in a candidate build specification."""
    return "agent-knowledge-build-owner-" + secrets.token_hex(16)


@dataclass(frozen=True, slots=True)
class AssetChangeV1:
    document_id: str
    parent_document_id: str
    asset_id: str
    asset_version: str
    document_version_id: str
    old_ids: tuple[str, ...]
    asset_ref: str
    sidecar_ref: str
    sidecar_sha256: str
    parsed_source_ref: str
    parsed_source_sha256: str
    chunks_ref: str
    chunks_sha256: str


@dataclass(frozen=True, slots=True)
class RepresentationScopeV1:
    identifier: str
    document_id: str
    parent_document_id: str
    asset_id: str
    asset_version: str


@dataclass(frozen=True, slots=True)
class CandidateSpec:
    mode: Literal["rechunk", "representation"]
    source_index: str
    source_uuid: str
    source_mapping_sha256: str
    source_fingerprint: str
    source_count: int
    workspace: Path
    read_alias: str
    owner_alias: str
    online_index: str
    online_uuid: str
    online_mapping_sha256: str
    alias_snapshot_sha256: str
    candidate_index: str
    target_mapping_version: str
    target_mapping_sha256: str
    baseline_model_snapshot_sha256: str
    model_snapshot_sha256: str
    baseline_model_snapshot: bytes = field(repr=False)
    model_snapshot: bytes = field(repr=False)
    tokenizer_sha256: str
    baseline_representation_version: str
    representation_version: str
    indexed_at: str
    max_http_requests: int
    max_embedding_requests: int
    max_write_ops: int
    changes: tuple[AssetChangeV1, ...] = ()
    update_ids: tuple[str, ...] = ()
    representation_scope: tuple[RepresentationScopeV1, ...] = ()
    representation_binding_sha256: str | None = None

    def __post_init__(self) -> None:
        names_ok = (type(self.source_index) is str and type(self.candidate_index) is str
                    and type(self.online_index) is str
                    and _INDEX.fullmatch(self.source_index) is not None
                    and _INDEX.fullmatch(self.candidate_index) is not None
                    and _INDEX.fullmatch(self.online_index) is not None
                    and len(self.source_index) <= 255 and len(self.candidate_index) <= 255
                    and len(self.online_index) <= 255
                    and self.source_index != self.candidate_index
                    and self.online_index != self.candidate_index
                    and type(self.read_alias) is str and _ALIAS.fullmatch(self.read_alias) is not None
                    and type(self.owner_alias) is str
                    and _OWNER_ALIAS.fullmatch(self.owner_alias) is not None
                    and self.candidate_index != self.read_alias)
        hashes = (self.source_mapping_sha256, self.source_fingerprint,
                  self.online_mapping_sha256,
                  self.alias_snapshot_sha256, self.target_mapping_sha256,
                  self.baseline_model_snapshot_sha256, self.model_snapshot_sha256,
                  self.tokenizer_sha256)
        valid = names_ok and all(type(value) is str and _HASH.fullmatch(value) for value in hashes)
        valid = valid and all(type(value) is str and bool(re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value))
                              for value in (self.source_uuid, self.online_uuid))
        if self.online_index == self.source_index:
            valid = valid and (self.online_uuid == self.source_uuid
                               and self.online_mapping_sha256 == self.source_mapping_sha256)
        valid = valid and all(type(value) is int for value in (
            self.source_count, self.max_http_requests,
            self.max_embedding_requests, self.max_write_ops))
        valid = valid and isinstance(self.workspace, Path) and self.workspace.is_absolute()
        valid = valid and (type(self.changes) is tuple and type(self.update_ids) is tuple
                           and type(self.representation_scope) is tuple)
        valid = valid and all(type(change) is AssetChangeV1 for change in self.changes)
        valid = valid and all(type(identifier) is str and 0 < len(identifier) <= 256
                              for identifier in self.update_ids)
        valid = valid and (1 <= self.source_count <= 20000
                           and 1 <= self.max_http_requests <= _HTTP_LIMIT
                           and 1 <= self.max_embedding_requests <= 63
                           and 1 <= self.max_write_ops <= 4000)
        valid = valid and (type(self.target_mapping_version) is str
                           and bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,127}", self.target_mapping_version)))
        valid = valid and all(type(value) is str and 0 < len(value) <= 128 for value in (
            self.baseline_representation_version, self.representation_version))
        try:
            timestamp = datetime.fromisoformat(self.indexed_at)
            valid = valid and timestamp.utcoffset() is not None
        except (TypeError, ValueError):
            valid = False
        valid = valid and _model_snapshots_compatible(self)
        valid = valid and self.baseline_representation_version == "policy-title-section-body-v1"
        if self.mode == "rechunk":
            valid = valid and (1 <= len(self.changes) <= 30 and not self.update_ids
                               and not self.representation_scope
                               and self.online_index == self.source_index
                               and self.representation_binding_sha256 is None
                               and self.representation_version == self.baseline_representation_version)
            old_ids = tuple(identifier for change in self.changes for identifier in change.old_ids)
            valid = valid and 1 <= len(old_ids) <= 2000 and len(set(old_ids)) == len(old_ids)
            valid = valid and len({(c.document_id, c.asset_id, c.asset_version) for c in self.changes}) == len(self.changes)
            for change in self.changes:
                refs = ((change.asset_ref, "raw/"), (change.sidecar_ref, "manifests/"),
                        (change.parsed_source_ref, "parsed/"), (change.chunks_ref, "manifests/"))
                change_hashes = (change.asset_version, change.document_version_id,
                                 change.sidecar_sha256, change.parsed_source_sha256, change.chunks_sha256)
                valid = valid and type(change.old_ids) is tuple
                valid = valid and all(type(identifier) is str and 0 < len(identifier) <= 256
                                      for identifier in change.old_ids)
                valid = valid and len(set(change.old_ids)) == len(change.old_ids)
                valid = valid and bool(change.document_id and change.parent_document_id
                                       and change.asset_id and change.old_ids)
                valid = valid and all(type(ref) is str and ref.startswith(prefix)
                                      and ".." not in ref.split("/") and "\\" not in ref
                                      for ref, prefix in refs)
                valid = valid and all(type(value) is str and _HASH.fullmatch(value)
                                      for value in change_hashes)
        elif self.mode == "representation":
            valid = valid and (not self.changes and 1 <= len(self.update_ids) <= 2000
                               and len(set(self.update_ids)) == len(self.update_ids)
                               and len(self.representation_scope) == len(self.update_ids)
                               and all(type(scope) is RepresentationScopeV1
                                       for scope in self.representation_scope)
                               and tuple(scope.identifier for scope in self.representation_scope) == self.update_ids
                               and len({scope.parent_document_id for scope in self.representation_scope}) <= 30
                               and type(self.representation_binding_sha256) is str
                               and _HASH.fullmatch(self.representation_binding_sha256) is not None
                               and self.representation_version == "body-only-v2")
            for scope in self.representation_scope:
                valid = valid and all(type(value) is str and bool(value.strip())
                                      and len(value) <= 256
                                      for value in (scope.identifier, scope.document_id,
                                                    scope.parent_document_id, scope.asset_id))
                valid = valid and (type(scope.asset_version) is str
                                   and _HASH.fullmatch(scope.asset_version) is not None)
        else:
            valid = False
        if not valid:
            raise RechunkCandidateError("spec_invalid", "preflight")


@dataclass(frozen=True, slots=True)
class AssetPayloadV1:
    document: CorpusDocumentV2
    source: ParsedSourceV2
    chunking: ChunkingResultV2


@dataclass(frozen=True, slots=True)
class PreparedVectorsV1:
    vectors: tuple[Vector, ...] = field(repr=False)
    input_sha256: tuple[str, ...]
    body_sha256: tuple[str, ...]
    representation_versions: tuple[str, ...]
    token_counts: tuple[int, ...]
    max_input_tokens: int
    model_snapshot_sha256: str
    tokenizer_sha256: str
    embedding_requests: int


PrepareVectors = Callable[[tuple[Representation, ...]], PreparedVectorsV1]


@dataclass(frozen=True, slots=True)
class CandidateResultV1:
    candidate_index: str
    candidate_uuid: str
    source_count: int
    candidate_count: int
    deleted_count: int
    created_count: int
    updated_count: int
    candidate_fingerprint: str
    source_counts: dict[str, int]
    candidate_counts: dict[str, int]
    http_requests: int
    embedding_requests: int
    baseline_container_started: str
    current_container_started: str


@dataclass(frozen=True, slots=True)
class _Record:
    identifier: str = field(repr=False)
    chunk_id: str = field(repr=False)
    fields: dict[str, Any] = field(repr=False)
    vector: bytes = field(repr=False)
    seq_no: int
    primary_term: int

    def digest(self) -> str:
        return hashlib.sha256(canonical_bytes([self.identifier, self.fields]) + self.vector).hexdigest()


def _fingerprint(records: tuple[_Record, ...]) -> str:
    return hashlib.sha256("".join(record.digest() + "\n" for record in records).encode()).hexdigest()


def _inventory_counts(records: tuple[_Record, ...]) -> dict[str, int]:
    return {
        "policy": sum(record.fields.get("channel") in POLICY_CATEGORIES for record in records),
        "law": sum(record.fields.get("channel") in {"法律", "行政法规"} for record in records),
        "classification_missing": sum(
            not record.fields.get("documentType") and not record.fields.get("taxTypes")
            for record in records),
    }


def _vector_bytes(value: Any) -> bytes:
    if type(value) not in (tuple, list) or len(value) != 1024 or any(type(item) not in (int, float) for item in value):
        raise RechunkCandidateError("vector_invalid", "preflight")
    try:
        if all(math.isfinite(item) for item in value):
            packed = struct.pack("<1024f", *value)
            if any(struct.unpack("<1024f", packed)):
                return packed
    except (OverflowError, struct.error):
        pass
    raise RechunkCandidateError("vector_invalid", "preflight")


def _object(value: Any) -> dict[str, Any]:
    if type(value) is not dict:
        raise RechunkCandidateError("http_invalid", "preflight")
    return value


def _write_blocked(settings: dict[str, Any]) -> bool:
    nested = _object(settings.get("blocks", {})).get("write")
    flat = settings.get("blocks.write")
    return nested in (True, "true") or flat in (True, "true")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _model_snapshots_compatible(spec: CandidateSpec) -> bool:
    try:
        old = json.loads(spec.baseline_model_snapshot,
                         object_pairs_hook=_Build._unique_pairs,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        current = json.loads(spec.model_snapshot,
                             object_pairs_hook=_Build._unique_pairs,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if (type(old) is not dict or type(current) is not dict
                or set(old) != {"container", "model"} or set(current) != set(old)
                or canonical_bytes(old) != spec.baseline_model_snapshot
                or canonical_bytes(current) != spec.model_snapshot
                or _sha(spec.baseline_model_snapshot) != spec.baseline_model_snapshot_sha256
                or _sha(spec.model_snapshot) != spec.model_snapshot_sha256):
            return False
        old_container = _object(old["container"])
        current_container = _object(current["container"])
        if (set(old_container) != {"id", "image", "started", "running", "path", "args", "ports"}
                or set(current_container) != set(old_container)
                or set(_object(old["model"])) != {
                    "revision", "files", "service", "implementation", "max_length",
                    "packages", "cache_provenance",
                }
                or set(_object(current["model"])) != set(_object(old["model"]))
                or type(old_container.get("started")) is not str
                or type(current_container.get("started")) is not str
                or re.fullmatch(r"[0-9TZ:.+-]{20,40}", old_container["started"]) is None
                or re.fullmatch(r"[0-9TZ:.+-]{20,40}", current_container["started"]) is None):
            return False
        old_without_started = {key: value for key, value in old_container.items() if key != "started"}
        current_without_started = {key: value for key, value in current_container.items() if key != "started"}
        return (canonical_bytes(old_without_started) == canonical_bytes(current_without_started)
                and canonical_bytes(old["model"]) == canonical_bytes(current["model"]))
    except (TypeError, ValueError, UnicodeError, RechunkCandidateError):
        return False


def _typed_projection(fields: dict[str, Any]) -> None:
    for name, maximum in _TYPED_REQUIRED.items():
        value = fields.get(name)
        if type(value) is not str or (name != "title" and not value.strip()) or len(value) > maximum:
            raise RechunkCandidateError("typed_projection_invalid", "preflight")
        if not _nfc(value):
            raise RechunkCandidateError("typed_projection_invalid", "preflight")
    value = fields.get("content")
    if type(value) is not str or not value.strip() or len(value) > 4096 or not _nfc(value):
        raise RechunkCandidateError("typed_projection_invalid", "preflight")
    for name, maximum in _TYPED_OPTIONAL.items():
        value = fields.get(name)
        if value is not None and (type(value) is not str or len(value) > maximum or not _nfc(value)):
            raise RechunkCandidateError("typed_projection_invalid", "preflight")
    value = fields.get("writtenDate")
    if value is not None:
        if type(value) is not str or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
            raise RechunkCandidateError("typed_projection_invalid", "preflight")
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            raise RechunkCandidateError("typed_projection_invalid", "preflight") from None


def _nfc(value: str) -> bool:
    import unicodedata
    return value == unicodedata.normalize("NFC", value)


def _baseline_representation(record: _Record, spec: CandidateSpec) -> None:
    fields = record.fields
    try:
        representation = build_vector_representation(
            content=fields["content"], title=fields.get("title", ""),
            section=fields.get("section", ""),
        )
    except Exception:
        raise RechunkCandidateError("provenance_invalid", "preflight") from None
    expected = (representation.version, representation.input_sha256,
                representation.content_sha256, spec.baseline_model_snapshot_sha256)
    if tuple(fields.get(name) for name in _TRACE_FIELDS) != expected:
        raise RechunkCandidateError("provenance_invalid", "preflight")


def _validate_prepared(
    inputs: tuple[Representation, ...], result: PreparedVectorsV1, spec: CandidateSpec,
) -> tuple[bytes, ...]:
    if (type(result) is not PreparedVectorsV1 or type(result.vectors) is not tuple
            or len(result.vectors) != len(inputs) or type(result.max_input_tokens) is not int
            or not 1 <= result.max_input_tokens <= 1024
            or type(result.embedding_requests) is not int
            or result.embedding_requests != spec.max_embedding_requests
            or result.model_snapshot_sha256 != spec.model_snapshot_sha256
            or result.tokenizer_sha256 != spec.tokenizer_sha256):
        raise RechunkCandidateError("preparation_invalid", "prepare")
    expected_bodies = tuple(item.content_sha256 if isinstance(item, VectorRepresentation)
                            else item.body_sha256 for item in inputs)
    if (result.input_sha256 != tuple(item.input_sha256 for item in inputs)
            or result.body_sha256 != expected_bodies
            or result.representation_versions != tuple(item.version for item in inputs)
            or type(result.token_counts) is not tuple or len(result.token_counts) != len(inputs)
            or any(type(count) is not int or count < 1 or count > result.max_input_tokens
                   for count in result.token_counts)):
        raise RechunkCandidateError("preparation_invalid", "prepare")
    return tuple(_vector_bytes(vector) for vector in result.vectors)


@dataclass(frozen=True, slots=True)
class _Target:
    identifier: str
    base_fields: dict[str, Any] | None
    representation: Representation


def _verify_asset(spec: CandidateSpec, change: AssetChangeV1) -> None:
    try:
        root = spec.workspace.resolve(strict=True)
        path = (root / change.asset_ref).resolve(strict=True)
    except (OSError, RuntimeError):
        raise RechunkCandidateError("input_invalid", "preflight") from None
    if (not path.is_relative_to(root / "raw") or not path.is_file()
            or (root / change.asset_ref).is_symlink()):
        raise RechunkCandidateError("input_invalid", "preflight")
    digest = hashlib.sha256()
    count = 0
    try:
        with path.open("rb") as source:
            for part in iter(lambda: source.read(1024 * 1024), b""):
                count += len(part)
                if count > 50 * 1024 * 1024:
                    raise RechunkCandidateError("input_invalid", "preflight")
                digest.update(part)
    except OSError:
        raise RechunkCandidateError("input_invalid", "preflight") from None
    if digest.hexdigest() != change.asset_version:
        raise RechunkCandidateError("input_invalid", "preflight")


def _verify_artifact(spec: CandidateSpec, ref: str, partition: str, expected: bytes) -> None:
    try:
        root = spec.workspace.resolve(strict=True)
        path = (root / ref).resolve(strict=True)
    except (OSError, RuntimeError):
        raise RechunkCandidateError("input_invalid", "preflight") from None
    if (not path.is_relative_to(root / partition) or not path.is_file()
            or (root / ref).is_symlink()):
        raise RechunkCandidateError("input_invalid", "preflight")
    try:
        if path.stat().st_size > 50 * 1024 * 1024:
            raise RechunkCandidateError("input_invalid", "preflight")
        actual = path.read_bytes()
    except OSError:
        raise RechunkCandidateError("input_invalid", "preflight") from None
    if actual != expected:
        raise RechunkCandidateError("input_invalid", "preflight")


def _asset_group(records: tuple[_Record, ...], change: AssetChangeV1) -> tuple[_Record, ...]:
    return tuple(record for record in records
                 if record.fields.get("parentDocumentId") == change.parent_document_id
                 and record.fields.get("assetId") == change.asset_id
                 and record.fields.get("assetVersion") == change.asset_version)


def _inherited_fields(group: tuple[_Record, ...], properties: dict[str, Any]) -> dict[str, Any]:
    names = set(properties) - _RECOMPUTED - _EXIT
    if any(set(record.fields) - set(properties) for record in group):
        raise RechunkCandidateError("mapping_invalid", "preflight")
    inherited: dict[str, Any] = {}
    for name in names:
        present = [name in record.fields for record in group]
        if any(flag != present[0] for flag in present):
            raise RechunkCandidateError("inheritance_conflict", "preflight")
        if present[0]:
            value = group[0].fields[name]
            if any(canonical_bytes(record.fields[name]) != canonical_bytes(value)
                   for record in group[1:]):
                raise RechunkCandidateError("inheritance_conflict", "preflight")
            inherited[name] = value
    return inherited


def _covered(start: int, end: int, intervals: list[tuple[int, int]]) -> bool:
    position = start
    for left, right in sorted(intervals):
        if right <= position:
            continue
        if left > position:
            return False
        position = max(position, right)
        if position >= end:
            return True
    return False


def _validate_parsed_block_coverage(
    parsed: ParsedSourceV2, chunking: ChunkingResultV2,
    units: dict[str, StructureUnitV2],
) -> None:
    for block in parsed.blocks:
        if not any(unit.start <= block.start and block.end <= unit.end
                   for unit in units.values()):
            raise RechunkCandidateError("source_span_invalid", "preflight")
        intervals: list[tuple[int, int]] = []
        for chunk in chunking.chunks:
            left, right = max(block.start, chunk.start), min(block.end, chunk.end)
            if left >= right:
                continue
            owner = units[chunk.unit_id]
            if (not owner.start <= block.start < block.end <= owner.end
                    or not ((block.start <= chunk.start < chunk.end <= block.end)
                            or (chunk.start <= block.start < block.end <= chunk.end))):
                raise RechunkCandidateError("source_span_invalid", "preflight")
            intervals.append((left, right))
        cursor = block.start
        for left, right in sorted(intervals):
            if left != cursor:  # Reject both gaps and repeated/overlapping spans.
                raise RechunkCandidateError("source_span_invalid", "preflight")
            cursor = right
        if cursor != block.end:
            raise RechunkCandidateError("source_span_invalid", "preflight")
    if any(not any(chunk.start < block.end and block.start < chunk.end
                   for block in parsed.blocks) for chunk in chunking.chunks):
        raise RechunkCandidateError("source_span_invalid", "preflight")


def _rechunk_targets(
    spec: CandidateSpec, source: tuple[_Record, ...], properties: dict[str, Any],
    payloads: tuple[AssetPayloadV1, ...],
) -> tuple[tuple[_Target, ...], tuple[_Record, ...]]:
    if len(payloads) != len(spec.changes) or any(name in properties for name in _STRUCTURE_FIELDS):
        raise RechunkCandidateError("input_invalid", "preflight")
    if any(name not in properties for name in _RECOMPUTED):
        raise RechunkCandidateError("mapping_invalid", "preflight")
    source_by_id = {record.identifier: record for record in source}
    source_chunks = {record.chunk_id for record in source}
    new_ids: set[str] = set()
    targets: list[_Target] = []
    deletions: list[_Record] = []
    for change, payload in zip(spec.changes, payloads, strict=True):
        document, parsed, chunking = payload.document, payload.source, payload.chunking
        try:
            document_bytes = v2_json_bytes(document)
            parsed_bytes = v2_json_bytes(parsed)
            chunking_bytes = canonical_bytes(chunking.model_dump(mode="json", by_alias=True))
            if (load_document_v2(document_bytes) != document
                    or load_parsed_source_v2(parsed_bytes) != parsed
                    or ChunkingResultV2.model_validate_json(chunking_bytes) != chunking):
                raise ValueError("v2 replay mismatch")
        except Exception:
            raise RechunkCandidateError("source_span_invalid", "preflight") from None
        binding = document.parsed_source
        if (type(document) is not CorpusDocumentV2 or type(parsed) is not ParsedSourceV2
                or type(chunking) is not ChunkingResultV2 or binding is None
                or document.document_id != change.document_id
                or document.document_version_id != change.document_version_id
                or document.normalized_sha256 != change.sidecar_sha256
                or _sha(parsed_bytes) != change.parsed_source_sha256
                or _sha(chunking_bytes) != change.chunks_sha256
                or binding.source_ref != change.parsed_source_ref
                or binding.source_text_sha256 != parsed.source_text_sha256
                or binding.parser_version != parsed.parser_version
                or document.source.asset_id != change.asset_id
                or document.source.asset_version != change.asset_version
                or document.source.raw_hash_scope != "asset_bytes"
                or document.source.raw_sha256 != change.asset_version
                or parsed.asset_id != change.asset_id
                or parsed.asset_sha256 != change.asset_version
                or parsed.order_status != "verified"
                or parsed.structure_status != "verified"
                or document.relations.parent_document_id != change.parent_document_id
                or chunking.document_version_id != change.document_version_id
                or chunking.source_text_sha256 != parsed.source_text_sha256
                or not chunking.publishable or not chunking.chunks or chunking.unresolved):
            raise RechunkCandidateError("input_invalid", "preflight")
        _verify_asset(spec, change)
        _verify_artifact(spec, change.sidecar_ref, "manifests", document_bytes)
        _verify_artifact(spec, change.parsed_source_ref, "parsed", parsed_bytes)
        _verify_artifact(spec, change.chunks_ref, "manifests", chunking_bytes)
        group = _asset_group(source, change)
        if set(change.old_ids) != {record.identifier for record in group} or not group:
            raise RechunkCandidateError("input_invalid", "preflight")
        if any(source_by_id.get(identifier) not in group for identifier in change.old_ids):
            raise RechunkCandidateError("input_invalid", "preflight")
        for record in group:
            _baseline_representation(record, spec)
        inherited = _inherited_fields(group, properties)
        required_inherited = set(ACL_FIELDS) | {
            "documentId", "documentVersion", "assetId", "assetVersion",
            "assetSha256", "assetKind", "parentDocumentId", "relationType",
        }
        if any(type(inherited.get(name)) is not str or not inherited[name].strip()
               for name in required_inherited):
            raise RechunkCandidateError("inheritance_conflict", "preflight")
        if (inherited.get("assetKind") != "attachment"
                or inherited.get("channel") not in POLICY_CATEGORIES
                or inherited.get("documentId") != change.document_id
                or inherited.get("relationType") != "attachment_chunk"
                or inherited.get("parentDocumentId") != change.parent_document_id
                or inherited.get("assetId") != change.asset_id
                or inherited.get("assetVersion") != change.asset_version
                or inherited.get("assetSha256") != change.asset_version):
            raise RechunkCandidateError("inheritance_conflict", "preflight")
        if (document.source.final_url is not None
                and inherited.get("sourceFinalUrl") not in (None, document.source.final_url)):
            raise RechunkCandidateError("inheritance_conflict", "preflight")
        unit_by_id = {unit.unit_id: unit for unit in chunking.units}
        if (len(unit_by_id) != len(chunking.units)
                or any(unit.structure_status != "complete_verified" for unit in chunking.units)
                or any(unit.document_version_id != change.document_version_id
                       or unit.source_text_sha256 != parsed.source_text_sha256
                       or unit.parser_version != parsed.parser_version
                       for unit in chunking.units)
                or len(chunking.unit_coverage) != len(chunking.units)
                or {item.unit_id for item in chunking.unit_coverage} != set(unit_by_id)
                or any(item.status != "covered_parsed_source" for item in chunking.unit_coverage)):
            raise RechunkCandidateError("source_span_invalid", "preflight")
        for unit in chunking.units:
            if (not 0 <= unit.start < unit.end <= len(parsed.text)
                    or unit.body_sha256 != _sha(parsed.text[unit.start:unit.end].encode("utf-8"))):
                raise RechunkCandidateError("source_span_invalid", "preflight")
            seen: set[str] = {unit.unit_id}
            parent_id = unit.parent_unit_id
            while parent_id is not None:
                parent = unit_by_id.get(parent_id)
                if (parent is None or parent_id in seen
                        or not parent.start <= unit.start < unit.end <= parent.end):
                    raise RechunkCandidateError("source_span_invalid", "preflight")
                seen.add(parent_id)
                parent_id = parent.parent_unit_id
            intervals = [(chunk.start, chunk.end) for chunk in chunking.chunks
                         if unit.start <= chunk.start and chunk.end <= unit.end]
            if any(not _covered(block.start, block.end, intervals)
                   for block in parsed.blocks
                   if unit.start <= block.start and block.end <= unit.end):
                raise RechunkCandidateError("source_span_invalid", "preflight")
        for ordinal, chunk in enumerate(chunking.chunks, start=1):
            owner_unit = unit_by_id.get(chunk.unit_id)
            if (type(chunk) is not RetrievalChunkV2 or owner_unit is None
                    or chunk.ordinal != ordinal
                    or chunk.document_version_id != change.document_version_id
                    or chunk.asset_id != change.asset_id
                    or not owner_unit.start <= chunk.start < chunk.end <= owner_unit.end
                    or chunk.chunk_id in source_chunks or chunk.chunk_id in source_by_id
                    or chunk.chunk_id in new_ids
                    or "short_unresolved" in chunk.quality_flags
                    or "table_structure_unknown" in chunk.quality_flags):
                raise RechunkCandidateError("source_span_invalid", "preflight")
            try:
                validate_source_span(parsed, start=chunk.start, end=chunk.end,
                                     content=chunk.content, body_sha256=chunk.body_sha256)
            except ContractError:
                raise RechunkCandidateError("source_span_invalid", "preflight") from None
            section = " / ".join(chunk.section_path) or "附件"
            base = dict(inherited)
            base.update({
                "content": chunk.content, "contentHash": chunk.body_sha256,
                "snippet": chunk.content[:512], "chunkId": chunk.chunk_id,
                "chunkIndex": chunk.ordinal - 1, "chunkCount": len(chunking.chunks),
                "charStart": 0, "charEnd": len(chunk.content), "section": section,
                "sectionPath": list(chunk.section_path), "clauseId": chunk.clause_id,
                "tableId": chunk.table_id, "chunkStrategy": chunk.chunker_version,
                "chunkVersion": chunk.chunker_version, "indexVersion": spec.candidate_index,
                "indexedAt": spec.indexed_at, "parserVersion": parsed.parser_version,
                "documentVersionId": change.document_version_id,
                "structureUnitId": chunk.unit_id,
                "sourceTextSha256": parsed.source_text_sha256,
                "sourceStart": chunk.start, "sourceEnd": chunk.end,
            })
            _typed_projection(base)
            representation = build_vector_representation(
                content=chunk.content, title=base["title"], section=section)
            targets.append(_Target(chunk.chunk_id, base, representation))
            new_ids.add(chunk.chunk_id)
        _validate_parsed_block_coverage(parsed, chunking, unit_by_id)
        deletions.extend(group)
    if (not 1 <= len(targets) <= 2000 or len(deletions) != sum(len(c.old_ids) for c in spec.changes)
            or not 1 <= spec.source_count - len(deletions) + len(targets) <= 22000):
        raise RechunkCandidateError("budget_exceeded", "preflight")
    return tuple(targets), tuple(deletions)


def _representation_targets(
    spec: CandidateSpec, source: tuple[_Record, ...],
    representations: tuple[RetrievalRepresentationV2, ...],
) -> tuple[_Target, ...]:
    if (type(representations) is not tuple
            or (representations and len(representations) != len(spec.update_ids))):
        raise RechunkCandidateError("input_invalid", "preflight")
    source_by_id = {record.identifier: record for record in source}
    targets: list[_Target] = []
    binding: list[list[str]] = []
    for ordinal, (identifier, scope) in enumerate(zip(
        spec.update_ids, spec.representation_scope, strict=True,
    )):
        record = source_by_id.get(identifier)
        if record is None:
            raise RechunkCandidateError("input_invalid", "preflight")
        if tuple(record.fields.get(name) for name in (
            "documentId", "parentDocumentId", "assetId", "assetVersion",
        )) != (scope.document_id, scope.parent_document_id,
               scope.asset_id, scope.asset_version):
            raise RechunkCandidateError("input_invalid", "preflight")
        if record.fields.get("channel") not in POLICY_CATEGORIES:
            raise RechunkCandidateError("input_invalid", "preflight")
        _baseline_representation(record, spec)
        try:
            exact = build_retrieval_representation_v2(
                body=record.fields["content"], kind="body-only-v2")
        except (ContractError, KeyError):
            raise RechunkCandidateError("input_invalid", "preflight") from None
        if exact.version != spec.representation_version:
            raise RechunkCandidateError("input_invalid", "preflight")
        if representations and (type(representations[ordinal]) is not RetrievalRepresentationV2
                                or representations[ordinal] != exact):
            raise RechunkCandidateError("input_invalid", "preflight")
        targets.append(_Target(identifier, None, exact))
        binding.append([identifier, exact.version,
                        exact.input_sha256, exact.body_sha256])
    if _sha(canonical_bytes(binding)) != spec.representation_binding_sha256:
        raise RechunkCandidateError("input_invalid", "preflight")
    return tuple(targets)


class _Build:
    def __init__(self, spec: CandidateSpec, client: httpx.Client) -> None:
        self.spec = spec
        self.client = client
        self.calls = 0
        self.phase = "preflight"
        self.clone_attempted = False
        self.clone_acknowledged = False
        self.candidate_uuid: str | None = None
        self.sealed = False
        url = client.base_url
        timeouts = client.timeout.as_dict().values()
        if (url.scheme != "http" or url.host not in ("127.0.0.1", "localhost", "::1")
                or url.path != "/" or url.query or url.fragment or url.userinfo
                or client.follow_redirects or client.trust_env or client.is_closed
                or any(timeout is None or not math.isfinite(timeout) or not 0 < timeout <= 30
                       for timeout in timeouts)):
            raise RechunkCandidateError("client_invalid", self.phase)

    def fail(self, reason: str) -> NoReturn:
        raise RechunkCandidateError(reason, self.phase)

    @staticmethod
    def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def request(
        self, method: str, path: str, *, body: Any = None, raw: bytes | None = None,
        allow_missing: bool = False, sealing: bool = False,
    ) -> dict[str, Any] | None:
        reserve = 0 if sealing or self.sealed or not self.clone_attempted else 3
        if self.calls >= self.spec.max_http_requests - reserve:
            self.fail("budget_exceeded")
        self.calls += 1
        result: dict[str, Any] | None = None
        invalid = False
        started = time.monotonic()
        try:
            payload = raw if raw is not None else (None if body is None else canonical_bytes(body))
            headers = {"Content-Type": "application/x-ndjson" if raw is not None else "application/json"}
            with self.client.stream(method, path, content=payload, headers=headers,
                                    follow_redirects=False) as response:
                if response.status_code == 404 and allow_missing:
                    return None
                if response.status_code != 200:
                    invalid = True
                elif method == "HEAD":
                    return {}
                else:
                    data = bytearray()
                    for part in response.iter_bytes():
                        if len(data) + len(part) > _MAX_RESPONSE or time.monotonic() - started > 30:
                            invalid = True
                            break
                        data.extend(part)
                    if not invalid:
                        parsed = json.loads(data, object_pairs_hook=self._unique_pairs,
                                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                        if type(parsed) is dict:
                            result = parsed
                        else:
                            invalid = True
        except Exception:
            invalid = True
        if invalid:
            self.fail("http_invalid")
        return result

    def definition(self, name: str, *, sealing: bool = False) -> dict[str, Any]:
        response = self.request("GET", f"/{name}", sealing=sealing)
        if response is None or set(response) != {name}:
            self.fail("source_changed" if name == self.spec.source_index else
                      "alias_changed" if name == self.spec.online_index else "candidate_changed")
        assert response is not None
        definition = _object(response[name])
        if "data_stream" in definition:
            self.fail("source_changed" if name == self.spec.source_index else
                      "alias_changed" if name == self.spec.online_index else "candidate_changed")
        return definition

    def source(self) -> dict[str, Any]:
        definition = self.definition(self.spec.source_index)
        settings = _object(_object(definition.get("settings")).get("index"))
        if (settings.get("uuid") != self.spec.source_uuid
                or not _write_blocked(settings)
                or mapping_fingerprint(_object(definition.get("mappings"))) != self.spec.source_mapping_sha256):
            self.fail("source_changed")
        _object(definition.get("aliases"))
        return definition

    def alias(self) -> dict[str, Any]:
        value = self.request("GET", f"/_alias/{self.spec.read_alias}")
        if (value is None or set(value) != {self.spec.online_index}
                or _sha(canonical_bytes(value)) != self.spec.alias_snapshot_sha256):
            self.fail("alias_changed")
        assert value is not None
        target = _object(value[self.spec.online_index])
        alias = _object(_object(target.get("aliases")).get(self.spec.read_alias))
        if alias.get("is_write_index", False) is not False:
            self.fail("alias_changed")
        online = self.definition(self.spec.online_index)
        settings = _object(_object(online.get("settings")).get("index"))
        online_alias = _object(_object(online.get("aliases")).get(self.spec.read_alias))
        if (settings.get("uuid") != self.spec.online_uuid
                or not _write_blocked(settings)
                or mapping_fingerprint(_object(online.get("mappings")))
                   != self.spec.online_mapping_sha256
                or canonical_bytes(online_alias) != canonical_bytes(alias)):
            self.fail("alias_changed")
        return value

    def ready(self, name: str) -> None:
        status = self.request("GET", f"/_cluster/health/{name}?wait_for_status=green&timeout=30s")
        if status is None or status.get("timed_out") is not False or status.get("status") != "green":
            self.fail("source_not_ready")

    def absent(self) -> None:
        if self.request("HEAD", f"/{self.spec.candidate_index}", allow_missing=True) is not None:
            self.fail("candidate_exists")

    def owner_absent(self, *, final: bool = False) -> None:
        value = self.request("GET", f"/_alias/{self.spec.owner_alias}", allow_missing=True)
        if value is not None:
            self.fail("verify_failed" if final else "owner_alias_exists")

    def owner_target(self, *, sealing: bool = False) -> None:
        value = self.request("GET", f"/_alias/{self.spec.owner_alias}",
                             allow_missing=True, sealing=sealing)
        if value is None or set(value) != {self.spec.candidate_index}:
            self.fail("candidate_ownership_unknown")
        target = value[self.spec.candidate_index]
        if (type(target) is not dict or type(target.get("aliases")) is not dict
                or target["aliases"] != {self.spec.owner_alias: _OWNER_FLAGS}):
            self.fail("candidate_ownership_unknown")

    def candidate(self, *, sealing: bool = False) -> dict[str, Any]:
        self.owner_target(sealing=sealing)
        definition = self.definition(self.spec.candidate_index, sealing=sealing)
        settings = _object(_object(definition.get("settings")).get("index"))
        uuid = settings.get("uuid")
        parent = _object(_object(settings.get("resize", {})).get("source", {}))
        expected = {"name": self.spec.source_index, "uuid": self.spec.source_uuid}
        if (type(uuid) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", uuid) is None
                or uuid == self.spec.source_uuid
                or uuid == self.spec.online_uuid
                or (self.candidate_uuid is not None and uuid != self.candidate_uuid)
                or any(key not in expected or value != expected[key] for key, value in parent.items())
                or _object(definition.get("aliases")) != {self.spec.owner_alias: _OWNER_FLAGS}):
            self.fail("candidate_ownership_unknown")
        self.candidate_uuid = uuid
        return definition

    def candidate_unmarked(self) -> None:
        definition = self.definition(self.spec.candidate_index)
        settings = _object(_object(definition.get("settings")).get("index"))
        if (self.candidate_uuid is None or settings.get("uuid") != self.candidate_uuid
                or not _write_blocked(settings) or _object(definition.get("aliases"))):
            self.fail("verify_failed")

    def acknowledged(self, method: str, path: str, body: Any, *, sealing: bool = False) -> None:
        response = self.request(method, path, body=body, sealing=sealing)
        if response is None or response.get("acknowledged") is not True:
            self.fail("write_unacknowledged")

    def seal_on_failure(self) -> str:
        if not self.clone_attempted:
            return "not_needed"
        try:
            self.candidate(sealing=True)
        except Exception:
            return "ownership_unknown"
        try:
            self.acknowledged("PUT", f"/{self.spec.candidate_index}/_settings",
                              {"index.blocks.write": True}, sealing=True)
            self.sealed = True
        except Exception:
            return "candidate_seal_failed"
        return "sealed"

    def scan(self, name: str, expected_count: int) -> tuple[_Record, ...]:
        if not 1 <= expected_count <= 22000:
            self.fail("scan_invalid")
        records: list[_Record] = []
        seen_ids: set[str] = set()
        seen_chunks: set[str] = set()
        after: str | None = None
        while len(records) < expected_count:
            query: dict[str, Any] = {
                "size": min(_PAGE, expected_count - len(records)),
                "track_total_hits": True, "seq_no_primary_term": True,
                "_source": {"exclude_vectors": False},
                "sort": [{"chunkId": "asc"}], "query": {"match_all": {}},
            }
            if after is not None:
                query["search_after"] = [after]
            page = self.request("POST", f"/{name}/_search", body=query)
            if page is None or page.get("timed_out") is not False:
                self.fail("scan_invalid")
            assert page is not None
            shards = _object(page.get("_shards"))
            hits = _object(page.get("hits"))
            total = _object(hits.get("total"))
            entries = hits.get("hits")
            if (shards.get("failed") != 0 or type(shards.get("total")) is not int
                    or shards["total"] < 1 or shards.get("successful") != shards["total"]
                    or total.get("value") != expected_count or total.get("relation") != "eq"
                    or type(entries) is not list or not entries
                    or len(entries) > min(_PAGE, expected_count - len(records))):
                self.fail("scan_invalid")
            for entry in entries:
                hit = _object(entry)
                fields = dict(_object(hit.get("_source")))
                chunk = fields.get("chunkId")
                identifier = hit.get("_id")
                if (type(chunk) is not str or not chunk or (after is not None and chunk <= after)
                        or chunk in seen_chunks or hit.get("sort") != [chunk]
                        or type(identifier) is not str or not identifier or identifier in seen_ids
                        or hit.get("_index") != name
                        or type(hit.get("_seq_no")) is not int or hit["_seq_no"] < 0
                        or type(hit.get("_primary_term")) is not int or hit["_primary_term"] < 1):
                    self.fail("scan_invalid")
                vector = _vector_bytes(fields.pop("embedding", None))
                canonical_bytes(fields)
                records.append(_Record(identifier, chunk, fields, vector,
                                       hit["_seq_no"], hit["_primary_term"]))
                seen_ids.add(identifier)
                seen_chunks.add(chunk)
                after = chunk
        return tuple(records)

    def bulk(self, action: str, entries: tuple[tuple[_Record | str, dict[str, Any] | None], ...]) -> None:
        for start in range(0, len(entries), _BATCH):
            batch = entries[start:start + _BATCH]
            lines: list[bytes] = []
            expected_ids: list[str] = []
            for identity, document in batch:
                identifier = identity.identifier if isinstance(identity, _Record) else identity
                expected_ids.append(identifier)
                header: dict[str, Any] = {"_id": identifier}
                if isinstance(identity, _Record):
                    header["if_seq_no"] = identity.seq_no
                    header["if_primary_term"] = identity.primary_term
                lines.append(canonical_bytes({action: header}))
                if action == "create":
                    assert document is not None
                    lines.append(canonical_bytes(document))
                elif action == "update":
                    assert document is not None
                    lines.append(canonical_bytes({"doc": document}))
            self.candidate()
            response = self.request("POST", f"/{self.spec.candidate_index}/_bulk", raw=b"".join(lines))
            if response is None or response.get("errors") is not False:
                self.fail("bulk_failed")
            items = response.get("items")
            if type(items) is not list or len(items) != len(batch):
                self.fail("bulk_failed")
            for item, identifier in zip(items, expected_ids, strict=True):
                item_result = _object(_object(item).get(action))
                expected_status = 201 if action == "create" else 200
                expected_result = {"create": "created", "delete": "deleted", "update": "updated"}[action]
                if (item_result.get("status") != expected_status
                        or item_result.get("result") != expected_result
                        or item_result.get("_index") != self.spec.candidate_index
                        or item_result.get("_id") != identifier or "error" in item_result):
                    self.fail("bulk_failed")

    def run(
        self, *, payloads: tuple[AssetPayloadV1, ...],
        representations: tuple[RetrievalRepresentationV2, ...],
        prepare_vectors: PrepareVectors,
    ) -> CandidateResultV1:
        source_definition = self.source()
        self.ready(self.spec.source_index)
        self.alias()
        self.absent()
        self.owner_absent()
        original = self.scan(self.spec.source_index, self.spec.source_count)
        if _fingerprint(original) != self.spec.source_fingerprint:
            self.fail("source_changed")
        mapping = _object(source_definition.get("mappings"))
        properties = _object(mapping.get("properties"))
        vector_mapping = _object(properties.get("embedding"))
        chunk_id_mapping = _object(properties.get("chunkId"))
        if (vector_mapping.get("type") != "dense_vector"
                or vector_mapping.get("dims") != 1024
                or chunk_id_mapping.get("type") != "keyword"
                or chunk_id_mapping.get("doc_values", True) is False):
            self.fail("mapping_invalid")
        if self.spec.mode == "rechunk":
            if _object(mapping.get("_meta", {})).get("mapping_version") == self.spec.target_mapping_version:
                self.fail("mapping_invalid")
            if representations:
                self.fail("input_invalid")
            targets, deletions = _rechunk_targets(self.spec, original, properties, payloads)
        else:
            if payloads:
                self.fail("input_invalid")
            targets = _representation_targets(self.spec, original, representations)
            deletions = ()
            if any(name not in properties for name in _TRACE_FIELDS):
                self.fail("mapping_invalid")
        final_count = self.spec.source_count - len(deletions) + (
            len(targets) if self.spec.mode == "rechunk" else 0)
        writes = len(deletions) + len(targets)
        bulk_calls = ((len(deletions) + _BATCH - 1) // _BATCH
                      + (len(targets) + _BATCH - 1) // _BATCH)
        http_upper = (42 + 3 * ((self.spec.source_count + _PAGE - 1) // _PAGE)
                      + ((final_count + _PAGE - 1) // _PAGE) + 3 * bulk_calls)
        if (writes != self.spec.max_write_ops or http_upper != self.spec.max_http_requests
                or self.spec.max_embedding_requests != (len(targets) + _BATCH - 1) // _BATCH
                or http_upper > _HTTP_LIMIT or final_count > 22000):
            self.fail("budget_exceeded")
        additions = _STRUCTURE_FIELDS if self.spec.mode == "rechunk" else {}
        target_mapping = dict(mapping)
        target_meta = dict(_object(mapping.get("_meta", {})))
        target_meta["mapping_version"] = self.spec.target_mapping_version
        target_mapping["_meta"] = target_meta
        target_mapping["properties"] = {**properties, **additions}
        if mapping_fingerprint(target_mapping) != self.spec.target_mapping_sha256:
            self.fail("mapping_invalid")
        self.phase = "prepare"
        inputs = tuple(target.representation for target in targets)
        prepared = prepare_vectors(inputs)
        vectors = _validate_prepared(inputs, prepared, self.spec)
        expected: dict[str, tuple[dict[str, Any], bytes]] = {}
        for target, packed in zip(targets, vectors, strict=True):
            representation = target.representation
            fields = dict(target.base_fields or {})
            fields.update({
                "vectorRepresentationVersion": representation.version,
                "vectorInputSha256": representation.input_sha256,
                "vectorBodySha256": (representation.content_sha256
                                     if isinstance(representation, VectorRepresentation)
                                     else representation.body_sha256),
                "vectorModelSnapshotSha256": self.spec.model_snapshot_sha256,
            })
            expected[target.identifier] = (fields, packed)
        self.phase = "clone"
        if self.source() != source_definition:
            self.fail("source_changed")
        self.alias()
        self.absent()
        self.owner_absent()
        settings = _object(_object(source_definition.get("settings")).get("index"))
        self.clone_attempted = True
        clone_response = self.request(
            "POST", f"/{self.spec.source_index}/_clone/{self.spec.candidate_index}",
            body={"settings": {"index.number_of_replicas": settings.get("number_of_replicas"),
                               "index.blocks.write": True},
                  "aliases": {self.spec.owner_alias: dict(_OWNER_FLAGS)}},
        )
        if (clone_response is None or clone_response.get("acknowledged") is not True
                or clone_response.get("index") != self.spec.candidate_index
                or type(clone_response.get("shards_acknowledged")) is not bool):
            self.fail("clone_unacknowledged")
        self.clone_acknowledged = True
        self.candidate()
        self.ready(self.spec.candidate_index)
        clone_definition = self.candidate()
        clone_settings = _object(_object(clone_definition.get("settings")).get("index"))
        if (clone_settings.get("number_of_replicas") != settings.get("number_of_replicas")
                or clone_settings.get("number_of_shards") != settings.get("number_of_shards")
                or not _write_blocked(clone_settings)
                or mapping_fingerprint(_object(clone_definition.get("mappings"))) != self.spec.source_mapping_sha256):
            self.fail("candidate_changed")
        copied = self.scan(self.spec.candidate_index, self.spec.source_count)
        if _fingerprint(copied) != self.spec.source_fingerprint:
            self.fail("candidate_changed")
        self.phase = "mutate"
        self.candidate()
        self.acknowledged("PUT", f"/{self.spec.candidate_index}/_settings",
                          {"index.blocks.write": False})
        self.candidate()
        self.acknowledged("PUT", f"/{self.spec.candidate_index}/_mapping",
                          {"_meta": target_meta, "properties": additions})
        copied_by_id = {record.identifier: record for record in copied}
        if self.spec.mode == "rechunk":
            self.bulk("delete", tuple((copied_by_id[record.identifier], None)
                                      for record in deletions))
            self.bulk("create", tuple((target.identifier, {
                **expected[target.identifier][0],
                "embedding": list(struct.unpack("<1024f", expected[target.identifier][1])),
            }) for target in targets))
        else:
            self.bulk("update", tuple((copied_by_id[target.identifier], {
                **expected[target.identifier][0],
                "embedding": list(struct.unpack("<1024f", expected[target.identifier][1])),
            }) for target in targets))
        self.candidate()
        refreshed = self.request("POST", f"/{self.spec.candidate_index}/_refresh")
        if refreshed is None or _object(refreshed.get("_shards")).get("failed") != 0:
            self.fail("refresh_failed")
        self.candidate()
        self.acknowledged("PUT", f"/{self.spec.candidate_index}/_settings",
                          {"index.blocks.write": True})
        self.sealed = True
        self.phase = "verify"
        candidate_definition = self.candidate()
        candidate_settings = _object(_object(candidate_definition.get("settings")).get("index"))
        if (not _write_blocked(candidate_settings)
                or _object(candidate_definition.get("mappings")) != target_mapping):
            self.fail("verify_failed")
        final = self.scan(self.spec.candidate_index, final_count)
        final_by_id = {record.identifier: record for record in final}
        deleted_ids = {record.identifier for record in deletions}
        if (deleted_ids & final_by_id.keys()
                or set(final_by_id) != (set(copied_by_id) - deleted_ids)
                   | ({target.identifier for target in targets} if self.spec.mode == "rechunk" else set())):
            self.fail("verify_failed")
        for record in original:
            if record.identifier in deleted_ids:
                continue
            after = final_by_id[record.identifier]
            if record.identifier in expected:
                changed, vector = expected[record.identifier]
                fields = {**record.fields, **changed}
            else:
                fields, vector = record.fields, record.vector
            if canonical_bytes(after.fields) != canonical_bytes(fields) or after.vector != vector:
                self.fail("verify_failed")
        if self.spec.mode == "rechunk":
            for target in targets:
                after = final_by_id[target.identifier]
                fields, vector = expected[target.identifier]
                if canonical_bytes(after.fields) != canonical_bytes(fields) or after.vector != vector:
                    self.fail("verify_failed")
        if self.source() != source_definition:
            self.fail("source_changed")
        self.alias()
        source_final = self.scan(self.spec.source_index, self.spec.source_count)
        if _fingerprint(source_final) != self.spec.source_fingerprint:
            self.fail("source_changed")
        self.candidate()
        removed = self.request("POST", "/_aliases", body={"actions": [{"remove": {
            "index": self.spec.candidate_index, "alias": self.spec.owner_alias,
        }}]})
        if (removed is None or removed.get("acknowledged") is not True
                or removed.get("errors") is not False):
            self.fail("write_unacknowledged")
        self.candidate_unmarked()
        self.owner_absent(final=True)
        assert self.candidate_uuid is not None
        return CandidateResultV1(
            candidate_index=self.spec.candidate_index,
            candidate_uuid=self.candidate_uuid,
            source_count=self.spec.source_count,
            candidate_count=final_count,
            deleted_count=len(deletions),
            created_count=len(targets) if self.spec.mode == "rechunk" else 0,
            updated_count=len(targets) if self.spec.mode == "representation" else 0,
            candidate_fingerprint=_fingerprint(final),
            source_counts=_inventory_counts(original),
            candidate_counts=_inventory_counts(final),
            http_requests=self.calls,
            embedding_requests=prepared.embedding_requests,
            baseline_container_started=json.loads(self.spec.baseline_model_snapshot)["container"]["started"],
            current_container_started=json.loads(self.spec.model_snapshot)["container"]["started"],
        )


def build_rechunk_candidate_v1(
    spec: CandidateSpec, *, client: httpx.Client,
    prepare_vectors: PrepareVectors,
    payloads: tuple[AssetPayloadV1, ...] = (),
    representations: tuple[RetrievalRepresentationV2, ...] = (),
) -> CandidateResultV1:
    """Build exactly one new candidate; failures are sealed, never resumed."""
    build = _Build(spec, client)
    failure: tuple[str, str] | None = None
    try:
        return build.run(payloads=payloads, representations=representations,
                         prepare_vectors=prepare_vectors)
    except RechunkCandidateError as error:
        failure = (error.reason, build.phase)
    except Exception:
        failure = ("operation_invalid", build.phase)
    except BaseException as interruption:
        seal_status = build.seal_on_failure()
        interruption.add_note(f"candidate_cleanup:{seal_status}")
        raise
    assert failure is not None
    seal_status = build.seal_on_failure()
    reason = ("candidate_ownership_unknown"
              if seal_status == "ownership_unknown" and build.clone_attempted
              else failure[0])
    raise RechunkCandidateError(reason, failure[1], seal_status)
