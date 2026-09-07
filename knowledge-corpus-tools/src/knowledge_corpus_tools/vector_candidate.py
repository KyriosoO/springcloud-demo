"""Offline, clone-only attachment vector migration (DR-KRET-031).

No alias publication, model loading, raw-data persistence or retry belongs here.
The caller owns the bounded HTTP client and the verified local model preparation.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import struct
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, NoReturn

import httpx

from knowledge_corpus_tools.errors import ContractError
from knowledge_corpus_tools.vector_representation import (
    REPRESENTATION_VERSION, VectorRepresentation, build_vector_representation,
)

POLICY_CATEGORIES = frozenset({
    "税务规范性文件", "财税文件", "工作通知", "其他文件", "政策解读",
    "税务部门规章", "国务院文件", "curated",
})
MAPPING_VERSION = "agent-knowledge-tax-v3-policy-context-v1"
TRACE_FIELDS = (
    "vectorRepresentationVersion", "vectorInputSha256",
    "vectorModelSnapshotSha256", "vectorBodySha256",
)
MAX_REQUESTS = 400
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
PAGE_SIZE = 250
ACL_FIELDS = ("aclRef", "aclVersion", "visibility", "channel", "tenantId",
              "corpusId", "domain", "materialType")
Vector = tuple[float, ...]
PrepareVectors = Callable[[tuple[VectorRepresentation, ...]], tuple[Vector, ...]]
_REASONS = frozenset({
    "spec_invalid", "vector_invalid", "schema_invalid", "client_invalid",
    "http_budget_exhausted", "http_status_invalid", "response_timeout",
    "response_limit_exceeded", "http_or_json_invalid", "index_identity_invalid",
    "data_stream_forbidden", "source_binding_changed", "index_not_ready",
    "candidate_exists", "scan_incomplete", "record_identity_invalid",
    "candidate_identity_invalid", "candidate_alias_forbidden", "write_not_acknowledged",
    "trace_fields_present", "source_fingerprint_changed", "attachment_metadata_invalid",
    "body_hash_invalid", "selection_count_changed", "prepared_shape_invalid",
    "clone_settings_changed", "clone_mapping_changed", "clone_content_changed",
    "bulk_failed", "refresh_failed", "candidate_not_sealed", "candidate_mapping_changed",
    "candidate_content_changed", "operation_invalid",
})


class CandidateError(ContractError):
    """Only finite diagnostic codes; never retain an HTTP/provider exception."""

    def __init__(self, reason: str, *, phase: str, seal_status: str = "not_needed"):
        self.reason = reason if type(reason) is str and reason in _REASONS else "operation_invalid"
        self.phase = phase if type(phase) is str and phase in {
            "preflight", "validation", "prepare", "clone", "update", "verify"} else "validation"
        self.seal_status = seal_status if type(seal_status) is str and seal_status in {
            "not_needed", "sealed", "candidate_seal_failed"} else "candidate_seal_failed"
        super().__init__(f"{self.phase}:{self.reason}:{self.seal_status}")


@dataclass(frozen=True, slots=True)
class VectorCandidateSpec:
    source_index: str
    source_uuid: str
    mapping_sha256: str
    source_fingerprint: str
    total_count: int
    policy_count: int
    attachment_count: int
    candidate_index: str
    model_snapshot_sha256: str

    def __post_init__(self) -> None:
        names = (self.source_index, self.candidate_index)
        valid = all(type(n) is str and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,254}", n)
                    for n in names)
        valid = valid and bool(re.fullmatch(
            r"agent-doc-tax-policy-v[1-9][0-9]*-[0-9]{8}-vector-b[1-9][0-9]*",
            self.candidate_index,
        )) and self.source_index != self.candidate_index
        valid = valid and type(self.source_uuid) is str and bool(
            re.fullmatch(r"[A-Za-z0-9_-]{1,128}", self.source_uuid))
        valid = valid and all(type(h) is str and re.fullmatch(r"[a-f0-9]{64}", h)
                              for h in (self.mapping_sha256, self.source_fingerprint,
                                        self.model_snapshot_sha256))
        valid = valid and all(type(c) is int for c in (
            self.total_count, self.policy_count, self.attachment_count))
        if not valid or not (1 <= self.attachment_count <= 1000
                             and self.attachment_count <= self.policy_count
                             <= self.total_count <= 20000):
            raise CandidateError("spec_invalid", phase="preflight")


@dataclass(frozen=True, slots=True)
class VectorCandidateResult:
    candidate_index: str
    candidate_uuid: str
    total_count: int
    policy_count: int
    updated_count: int
    source_fingerprint: str
    candidate_fingerprint: str
    model_snapshot_sha256: str
    representation_version: str
    http_requests: int


def canonical_bytes(value: Any) -> bytes:
    """Exact JSON values, no normalization; reject non-finite JSON numbers."""
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def mapping_fingerprint(mapping: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(mapping)).hexdigest()


def _vector_bytes(value: Any) -> bytes:
    if type(value) not in (list, tuple) or len(value) != 1024:
        raise CandidateError("vector_invalid", phase="validation")
    if any(type(x) not in (int, float) for x in value):
        raise CandidateError("vector_invalid", phase="validation")
    packed: bytes | None = None
    try:
        if all(math.isfinite(x) for x in value):
            packed = struct.pack("<1024f", *value)
    except (OverflowError, struct.error):
        pass
    if packed is None or not any(struct.unpack("<1024f", packed)):
        raise CandidateError("vector_invalid", phase="validation")
    return packed


@dataclass(frozen=True, slots=True)
class _Record:
    identifier: str = field(repr=False)
    chunk_id: str = field(repr=False)
    fields: dict[str, Any] = field(repr=False)
    vector: bytes = field(repr=False)
    seq_no: int
    primary_term: int

    def digest(self) -> str:
        return hashlib.sha256(canonical_bytes([self.identifier, self.fields])
                              + self.vector).hexdigest()


def _fingerprint(records: tuple[_Record, ...]) -> str:
    return hashlib.sha256("".join(r.digest() + "\n" for r in records).encode()).hexdigest()


def _object(value: Any) -> dict[str, Any]:
    if type(value) is not dict or any(type(k) is not str for k in value):
        raise CandidateError("schema_invalid", phase="validation")
    return value


def _write_blocked(settings: dict[str, Any]) -> bool:
    value = _object(settings.get("blocks")).get("write")
    return value is True or (type(value) is str and value == "true")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise ValueError("non_finite")


class _Build:
    def __init__(self, spec: VectorCandidateSpec, client: httpx.Client):
        self.spec = spec
        self.client = client
        self.calls = 0
        self.phase = "preflight"
        self.clone_attempted = False
        self.clone_acknowledged = False
        self.uuid: str | None = None
        url = client.base_url
        timeouts = client.timeout.as_dict().values()
        if (url.scheme != "http" or url.host not in ("127.0.0.1", "localhost", "::1")
                or url.path != "/" or url.query or url.fragment or url.userinfo
                or client.follow_redirects or client.trust_env or client.is_closed
                or any(t is None or not math.isfinite(t) or not 0 < t <= 30
                       for t in timeouts)):
            raise CandidateError("client_invalid", phase=self.phase)

    def fail(self, reason: str) -> NoReturn:
        raise CandidateError(reason, phase=self.phase)

    def request(self, method: str, path: str, *, body: Any = None,
                raw: bytes | None = None, allow_missing: bool = False,
                sealing: bool = False) -> dict[str, Any] | None:
        if self.calls >= MAX_REQUESTS - (0 if sealing else 1):
            self.fail("http_budget_exhausted")
        self.calls += 1
        reason: str | None = None
        result: dict[str, Any] | None = None
        started = time.monotonic()
        try:
            payload = raw if raw is not None else (None if body is None else canonical_bytes(body))
            headers = {"Content-Type": "application/x-ndjson" if raw is not None else "application/json"}
            with self.client.stream(method, path, content=payload, headers=headers,
                                    follow_redirects=False) as response:
                if response.status_code == 404 and allow_missing:
                    return None
                if response.status_code != 200:
                    reason = "http_status_invalid"
                elif method == "HEAD":
                    return {}
                else:
                    data = bytearray()
                    for part in response.iter_bytes():
                        if time.monotonic() - started > 30:
                            reason = "response_timeout"
                            break
                        if len(data) + len(part) > MAX_RESPONSE_BYTES:
                            reason = "response_limit_exceeded"
                            break
                        data.extend(part)
                    if reason is None:
                        parsed = json.loads(data, object_pairs_hook=_unique_pairs,
                                            parse_constant=_reject_constant)
                        if type(parsed) is dict:
                            result = parsed
                        else:
                            reason = "schema_invalid"
        except Exception:
            reason = "http_or_json_invalid"
        # Raising outside the handler avoids retaining raw request/response data.
        if reason is not None:
            self.fail(reason)
        return result

    def definition(self, name: str) -> dict[str, Any]:
        payload = self.request("GET", f"/{name}")
        if payload is None or set(payload) != {name}:
            self.fail("index_identity_invalid")
        assert payload is not None
        result = _object(payload[name])
        if "data_stream" in result:
            self.fail("data_stream_forbidden")
        return result

    def source(self) -> dict[str, Any]:
        data = self.definition(self.spec.source_index)
        settings = _object(_object(data["settings"])["index"])
        if (settings.get("uuid") != self.spec.source_uuid
                or not _write_blocked(settings)
                or mapping_fingerprint(_object(data["mappings"])) != self.spec.mapping_sha256):
            self.fail("source_binding_changed")
        _object(data["aliases"])
        return data

    def ready(self, name: str) -> None:
        health = self.request("GET", f"/_cluster/health/{name}?wait_for_status=green&timeout=30s")
        if (health is None or health.get("timed_out") is not False
                or health.get("status") != "green"):
            self.fail("index_not_ready")

    def absent(self) -> None:
        if self.request("HEAD", f"/{self.spec.candidate_index}", allow_missing=True) is not None:
            self.fail("candidate_exists")

    def scan(self, name: str) -> tuple[_Record, ...]:
        records: list[_Record] = []
        identifiers: set[str] = set()
        after: str | None = None
        while len(records) < self.spec.total_count:
            body: dict[str, Any] = {
                "size": PAGE_SIZE, "track_total_hits": True, "seq_no_primary_term": True,
                "_source": {"exclude_vectors": False}, "sort": [{"chunkId": "asc"}],
                "query": {"match_all": {}},
            }
            if after is not None:
                body["search_after"] = [after]
            page = self.request("POST", f"/{name}/_search", body=body)
            if page is None or page.get("timed_out") is not False:
                self.fail("scan_incomplete")
            assert page is not None
            shards = _object(page.get("_shards"))
            if (type(shards.get("failed")) is not int or shards["failed"] != 0
                    or type(shards.get("total")) is not int or shards["total"] < 1
                    or type(shards.get("successful")) is not int
                    or shards.get("successful") != shards["total"]):
                self.fail("scan_incomplete")
            hits = _object(page.get("hits"))
            total = _object(hits.get("total"))
            entries = hits.get("hits")
            if (type(total.get("value")) is not int or total["value"] != self.spec.total_count
                    or total.get("relation") != "eq" or type(entries) is not list
                    or not entries or len(entries) > PAGE_SIZE):
                self.fail("scan_incomplete")
            for entry in entries:
                hit = _object(entry)
                source = dict(_object(hit.get("_source")))
                chunk = source.get("chunkId")
                identifier = hit.get("_id")
                if (type(chunk) is not str or not chunk or (after is not None and chunk <= after)
                        or hit.get("sort") != [chunk] or type(identifier) is not str or not identifier
                        or identifier in identifiers or hit.get("_index") != name
                        or type(hit.get("_seq_no")) is not int or hit["_seq_no"] < 0
                        or type(hit.get("_primary_term")) is not int or hit["_primary_term"] < 1):
                    self.fail("record_identity_invalid")
                vector = _vector_bytes(source.pop("embedding", None))
                canonical_bytes(source)
                records.append(_Record(identifier, chunk, source, vector,
                                       hit["_seq_no"], hit["_primary_term"]))
                identifiers.add(identifier)
                after = chunk
            if len(records) > self.spec.total_count:
                self.fail("scan_incomplete")
        return tuple(records)

    def candidate(self) -> dict[str, Any]:
        data = self.definition(self.spec.candidate_index)
        settings = _object(_object(data["settings"])["index"])
        # ES removes resize source metadata after primaries become active.
        # A positive, target-bound clone response is the normal ownership proof.
        parent = _object(_object(settings.get("resize", {})).get("source", {}))
        expected_parent = {"name": self.spec.source_index, "uuid": self.spec.source_uuid}
        uuid = settings.get("uuid")
        if (any(key not in expected_parent or value != expected_parent[key]
                for key, value in parent.items())
                or (self.uuid is None and not self.clone_acknowledged and parent != expected_parent)
                or type(uuid) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", uuid)
                or uuid == self.spec.source_uuid or (self.uuid is not None and uuid != self.uuid)):
            self.fail("candidate_identity_invalid")
        self.uuid = uuid
        if _object(data.get("aliases")):
            self.fail("candidate_alias_forbidden")
        return data

    def acknowledged(self, method: str, path: str, body: Any, *, sealing: bool = False) -> None:
        result = self.request(method, path, body=body, sealing=sealing)
        if result is None or result.get("acknowledged") is not True:
            self.fail("write_not_acknowledged")

    def seal_on_failure(self) -> str:
        if not self.clone_attempted:
            return "not_needed"
        try:
            # Recheck UUID, even after successful clone: do not seal a replacement.
            self.candidate()
            self.acknowledged("PUT", f"/{self.spec.candidate_index}/_settings",
                              {"index.blocks.write": True}, sealing=True)
        except Exception:
            return "candidate_seal_failed"
        return "sealed"

    def run(self, prepare: PrepareVectors) -> VectorCandidateResult:
        source = self.source()
        mapping = _object(source["mappings"])
        properties = _object(mapping["properties"])
        if any(key in properties for key in TRACE_FIELDS):
            self.fail("trace_fields_present")
        self.ready(self.spec.source_index)
        self.absent()
        original = self.scan(self.spec.source_index)
        if _fingerprint(original) != self.spec.source_fingerprint:
            self.fail("source_fingerprint_changed")
        targets: dict[str, VectorRepresentation] = {}
        policy_count = 0
        for record in original:
            fields = record.fields
            if any(key in fields for key in TRACE_FIELDS):
                self.fail("trace_fields_present")
            if fields.get("channel") not in POLICY_CATEGORIES:
                continue
            policy_count += 1
            if fields.get("assetKind") != "attachment":
                continue
            if (fields.get("relationType") != "attachment_chunk"
                    or any(type(fields.get(key)) is not str or not fields[key].strip()
                           for key in (*ACL_FIELDS, "assetId", "parentDocumentId"))):
                self.fail("attachment_metadata_invalid")
            representation = build_vector_representation(
                content=fields["content"], title=fields.get("title", ""),
                section=fields.get("section", ""))
            if fields.get("contentHash") != representation.content_sha256:
                self.fail("body_hash_invalid")
            targets[record.identifier] = representation
        if policy_count != self.spec.policy_count or len(targets) != self.spec.attachment_count:
            self.fail("selection_count_changed")
        self.phase = "prepare"
        vectors = prepare(tuple(targets.values()))
        if type(vectors) is not tuple or len(vectors) != len(targets):
            self.fail("prepared_shape_invalid")
        prepared = {key: _vector_bytes(value) for key, value in zip(targets, vectors, strict=True)}
        self.phase = "clone"
        if self.source() != source:
            self.fail("source_binding_changed")
        self.absent()
        replicas = _object(_object(source["settings"])["index"])["number_of_replicas"]
        self.clone_attempted = True
        response = self.request("POST", f"/{self.spec.source_index}/_clone/{self.spec.candidate_index}",
                                body={"settings": {"index.number_of_replicas": replicas,
                                                   "index.blocks.write": True}})
        if (response is None or response.get("acknowledged") is not True
                or response.get("index") != self.spec.candidate_index
                or type(response.get("shards_acknowledged")) is not bool):
            self.fail("write_not_acknowledged")
        self.clone_acknowledged = True
        self.candidate()  # Bind UUID before waiting, so later replacement fails closed.
        self.ready(self.spec.candidate_index)
        clone = self.candidate()
        clone_settings = _object(_object(clone["settings"])["index"])
        if (not _write_blocked(clone_settings)
                or clone_settings.get("number_of_replicas") != replicas
                or clone_settings.get("number_of_shards") != _object(
                    _object(source["settings"])["index"]).get("number_of_shards")):
            self.fail("clone_settings_changed")
        if mapping_fingerprint(_object(clone["mappings"])) != self.spec.mapping_sha256:
            self.fail("clone_mapping_changed")
        copied = self.scan(self.spec.candidate_index)
        if _fingerprint(copied) != self.spec.source_fingerprint:
            self.fail("clone_content_changed")
        self.phase = "update"
        self.acknowledged("PUT", f"/{self.spec.candidate_index}/_settings", {"index.blocks.write": False})
        meta = dict(_object(mapping.get("_meta", {})))
        meta["mapping_version"] = MAPPING_VERSION
        additions = {key: {"type": "keyword"} for key in TRACE_FIELDS}
        self.acknowledged("PUT", f"/{self.spec.candidate_index}/_mapping",
                          {"_meta": meta, "properties": additions})
        updates: list[bytes] = []
        update_ids: list[str] = []
        for record in copied:
            if record.identifier not in targets:
                continue
            representation = targets[record.identifier]
            values = list(struct.unpack("<1024f", prepared[record.identifier]))
            doc: dict[str, Any] = dict(zip(TRACE_FIELDS, (REPRESENTATION_VERSION, representation.input_sha256,
                                         self.spec.model_snapshot_sha256, representation.content_sha256), strict=True))
            doc["embedding"] = values
            updates.append(canonical_bytes({"update": {
                "_id": record.identifier, "if_seq_no": record.seq_no,
                "if_primary_term": record.primary_term}}) + canonical_bytes({"doc": doc}))
            update_ids.append(record.identifier)
        for start in range(0, len(updates), 32):
            batch = updates[start:start + 32]
            result = self.request("POST", f"/{self.spec.candidate_index}/_bulk", raw=b"".join(batch))
            if result is None or result.get("errors") is not False:
                self.fail("bulk_failed")
            items = result.get("items")
            if type(items) is not list or len(items) != len(batch):
                self.fail("bulk_failed")
            for item, identifier in zip(items, update_ids[start:start + 32], strict=True):
                update = _object(_object(item).get("update"))
                if (update.get("status") != 200 or update.get("result") != "updated"
                        or update.get("_index") != self.spec.candidate_index
                        or update.get("_id") != identifier or "error" in update):
                    self.fail("bulk_failed")
        refresh = self.request("POST", f"/{self.spec.candidate_index}/_refresh")
        if refresh is None or _object(refresh.get("_shards")).get("failed") != 0:
            self.fail("refresh_failed")
        self.acknowledged("PUT", f"/{self.spec.candidate_index}/_settings", {"index.blocks.write": True})
        self.phase = "verify"
        final_definition = self.candidate()
        final_settings = _object(_object(final_definition["settings"])["index"])
        if not _write_blocked(final_settings):
            self.fail("candidate_not_sealed")
        expected_mapping = dict(mapping)
        expected_mapping["_meta"] = meta
        expected_mapping["properties"] = {**properties, **additions}
        if final_definition["mappings"] != expected_mapping:
            self.fail("candidate_mapping_changed")
        final = self.scan(self.spec.candidate_index)
        for before, after in zip(original, final, strict=True):
            expected_fields = dict(before.fields)
            expected_vector = before.vector
            if before.identifier in targets:
                representation = targets[before.identifier]
                expected_fields.update(dict(zip(TRACE_FIELDS, (
                    REPRESENTATION_VERSION, representation.input_sha256,
                    self.spec.model_snapshot_sha256, representation.content_sha256), strict=True)))
                expected_vector = prepared[before.identifier]
            if (before.identifier != after.identifier or before.chunk_id != after.chunk_id
                    or canonical_bytes(after.fields) != canonical_bytes(expected_fields)
                    or after.vector != expected_vector):
                self.fail("candidate_content_changed")
        if self.source() != source:
            self.fail("source_binding_changed")
        assert self.uuid is not None
        return VectorCandidateResult(
            self.spec.candidate_index, self.uuid, len(final), policy_count, len(targets),
            self.spec.source_fingerprint, _fingerprint(final), self.spec.model_snapshot_sha256,
            REPRESENTATION_VERSION, self.calls,
        )


def build_policy_vector_candidate(
    spec: VectorCandidateSpec, *, client: httpx.Client, prepare_vectors: PrepareVectors,
) -> VectorCandidateResult:
    """Build one new candidate. A failed attempt is never resumable."""
    build = _Build(spec, client)
    failure: tuple[str, str] | None = None
    try:
        return build.run(prepare_vectors)
    except CandidateError as error:
        failure = (error.reason, build.phase)
    except Exception:
        failure = ("operation_invalid", build.phase)
    except BaseException as interruption:
        seal_status = build.seal_on_failure()
        interruption.add_note(f"candidate_cleanup:{seal_status}")
        raise
    assert failure is not None
    seal_status = build.seal_on_failure()
    raise CandidateError(failure[0], phase=failure[1], seal_status=seal_status)
