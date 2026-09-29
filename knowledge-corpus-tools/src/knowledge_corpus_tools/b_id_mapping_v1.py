"""Bounded read-only ES identity scan for a B representation comparison.

The returned map contains IDs and body hashes, never text or vectors.  A source
fingerprint is computed with the same full-record algorithm as the candidate
builder; a mapping cannot be fabricated from the typed search response.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Any

import httpx

from .rechunk_candidate_v1 import _Record, _fingerprint, _vector_bytes, _write_blocked
from .vector_candidate import canonical_bytes, mapping_fingerprint

_INDEX = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")
_SHA = re.compile(r"[0-9a-f]{64}")
_PAGE = 250
_MAX_RESPONSE = 16 * 1024 * 1024


class BIdMappingError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason if reason in {
            "scan_binding_invalid", "scan_http_invalid", "scan_records_invalid",
            "scan_fingerprint_drift", "scan_budget_exhausted",
        } else "scan_records_invalid"
        super().__init__(self.reason)


@dataclass(frozen=True, slots=True)
class MappingScanSpec:
    index_name: str
    index_uuid: str
    mapping_sha256: str
    source_fingerprint: str
    record_count: int
    max_http_requests: int

    def __post_init__(self) -> None:
        if (type(self.index_name) is not str or _INDEX.fullmatch(self.index_name) is None
                or type(self.index_uuid) is not str or not 1 <= len(self.index_uuid) <= 128
                or type(self.mapping_sha256) is not str
                or _SHA.fullmatch(self.mapping_sha256) is None
                or type(self.source_fingerprint) is not str
                or _SHA.fullmatch(self.source_fingerprint) is None
                or type(self.record_count) is not int
                or not 1 <= self.record_count <= 22000
                or type(self.max_http_requests) is not int
                or self.max_http_requests != 1 + (self.record_count + _PAGE - 1) // _PAGE):
            raise BIdMappingError("scan_binding_invalid")


@dataclass(frozen=True, slots=True)
class MappingScanResult:
    raw: bytes
    sha256: str
    http_requests: int
    record_count: int
    mapping_version: str


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise BIdMappingError("scan_http_invalid")
        out[key] = value
    return out


def _reject_constant(_: str) -> None:
    raise BIdMappingError("scan_http_invalid")


def _object(value: Any) -> dict[str, Any]:
    if type(value) is not dict:
        raise BIdMappingError("scan_records_invalid")
    return value


def scan_id_mapping_v1(spec: MappingScanSpec, *, client: httpx.Client) -> MappingScanResult:
    """One definition + ceil(count/250) search calls; no ES mutation or retries."""
    calls = 0

    def request(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        nonlocal calls
        if calls >= spec.max_http_requests:
            raise BIdMappingError("scan_budget_exhausted")
        calls += 1
        started = time.monotonic()
        try:
            with client.stream(method, path,
                    content=None if body is None else canonical_bytes(body),
                    headers={"Content-Type": "application/json"},
                    follow_redirects=False, timeout=30.0) as response:
                if response.status_code != 200:
                    raise BIdMappingError("scan_http_invalid")
                chunks = bytearray()
                for part in response.iter_bytes():
                    if len(chunks) + len(part) > _MAX_RESPONSE or time.monotonic() - started > 30:
                        raise BIdMappingError("scan_http_invalid")
                    chunks.extend(part)
                obj = json.loads(chunks, object_pairs_hook=_unique,
                                 parse_constant=_reject_constant)
                if type(obj) is not dict:
                    raise BIdMappingError("scan_http_invalid")
                return obj
        except BIdMappingError:
            raise
        except Exception:
            raise BIdMappingError("scan_http_invalid") from None

    definition = request("GET", f"/{spec.index_name}")
    if set(definition) != {spec.index_name}:
        raise BIdMappingError("scan_binding_invalid")
    details = _object(definition[spec.index_name])
    settings = _object(_object(details.get("settings")).get("index"))
    mappings = _object(details.get("mappings"))
    mapping_version = _object(mappings.get("_meta")).get("mapping_version")
    if (settings.get("uuid") != spec.index_uuid
            or type(mapping_version) is not str or not mapping_version
            or mapping_fingerprint(mappings) != spec.mapping_sha256
            or not _write_blocked(settings)):
        raise BIdMappingError("scan_binding_invalid")
    records: list[_Record] = []
    identities: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    seen_chunks: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    after: str | None = None
    while len(records) < spec.record_count:
        query: dict[str, Any] = {
            "size": min(_PAGE, spec.record_count - len(records)),
            "track_total_hits": True, "seq_no_primary_term": True,
            "_source": {"exclude_vectors": False},
            "sort": [{"chunkId": "asc"}], "query": {"match_all": {}},
        }
        if after is not None:
            query["search_after"] = [after]
        response = request("POST", f"/{spec.index_name}/_search", query)
        if response.get("timed_out") is not False:
            raise BIdMappingError("scan_records_invalid")
        shards = _object(response.get("_shards"))
        hits = _object(response.get("hits"))
        total = _object(hits.get("total"))
        entries = hits.get("hits")
        if (shards.get("failed") != 0 or type(shards.get("total")) is not int
                or shards["total"] < 1 or shards.get("successful") != shards["total"]
                or total.get("value") != spec.record_count or total.get("relation") != "eq"
                or type(entries) is not list or not entries
                or len(entries) > min(_PAGE, spec.record_count - len(records))):
            raise BIdMappingError("scan_records_invalid")
        for entry in entries:
            hit = _object(entry)
            fields = dict(_object(hit.get("_source")))
            identifier = hit.get("_id")
            chunk = fields.get("chunkId")
            document = fields.get("documentId")
            content = fields.get("content")
            if (type(identifier) is not str or not identifier or identifier in seen_ids
                    or type(chunk) is not str or not chunk or chunk in seen_chunks
                    or (after is not None and chunk <= after)
                    or type(document) is not str or not document
                    or type(content) is not str or not content
                    or unicodedata.normalize("NFC", content) != content
                    or (document, chunk) in seen_pairs
                    or hit.get("sort") != [chunk]
                    or hit.get("_index") != spec.index_name
                    or type(hit.get("_seq_no")) is not int or hit["_seq_no"] < 0
                    or type(hit.get("_primary_term")) is not int or hit["_primary_term"] < 1):
                raise BIdMappingError("scan_records_invalid")
            try:
                vector = _vector_bytes(fields.pop("embedding", None))
                canonical_bytes(fields)
            except Exception:
                raise BIdMappingError("scan_records_invalid") from None
            records.append(_Record(identifier, chunk, fields, vector,
                                   hit["_seq_no"], hit["_primary_term"]))
            identities.append({"id": identifier, "documentId": document,
                               "chunkId": chunk,
                               "contentSha256": hashlib.sha256(content.encode("utf-8")).hexdigest()})
            seen_ids.add(identifier)
            seen_chunks.add(chunk)
            seen_pairs.add((document, chunk))
            after = chunk
    if calls != spec.max_http_requests or _fingerprint(tuple(records)) != spec.source_fingerprint:
        raise BIdMappingError("scan_fingerprint_drift")
    identities.sort(key=lambda item: item["id"])
    raw = canonical_bytes({
        "schemaVersion": 1, "indexName": spec.index_name,
        "indexUuid": spec.index_uuid, "sourceFingerprint": spec.source_fingerprint,
        "recordCount": spec.record_count, "records": identities,
    })
    if len(raw) > _MAX_RESPONSE:
        raise BIdMappingError("scan_records_invalid")
    return MappingScanResult(raw, hashlib.sha256(raw).hexdigest(), calls,
                             len(records), mapping_version)
