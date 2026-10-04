"""Bounded fresh inventory acquisition for private document-number comparisons.

Only a caller-owned client is used. Full source records and float32 vectors stay
in memory; the returned canonical mapping contains identities and hashes only.
This is not a reader for, or a reconstruction of, historical run evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Any, NoReturn, Protocol

import httpcore
import httpx

from .http_client_safety import _single_send_client
from .rechunk_candidate_v1 import _Record, _fingerprint, _vector_bytes, _write_blocked
from .vector_candidate import canonical_bytes, mapping_fingerprint

_INDEX = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")
_UUID = re.compile(r"[A-Za-z0-9_-]{1,128}")
_SHA = re.compile(r"[0-9a-f]{64}")
_PAGE = 250
_MAX_RESPONSE = 16 * 1024 * 1024
_REASONS = frozenset({
    "scan_binding_invalid", "scan_client_invalid", "scan_http_invalid",
    "scan_records_invalid", "scan_budget_exhausted",
})


class FreshSnapshotError(Exception):
    """Finite failure code and actual HTTP attempts, without provider text."""

    def __init__(self, reason: str, http_requests: int = 0) -> None:
        self.reason = reason if type(reason) is str and reason in _REASONS else "scan_records_invalid"
        self.http_requests = http_requests if type(http_requests) is int and http_requests >= 0 else 0
        super().__init__(self.reason)


@dataclass(frozen=True, slots=True)
class FreshSnapshotSpec:
    index_name: str
    index_uuid: str
    mapping_sha256: str
    record_count: int
    max_http_requests: int

    def __post_init__(self) -> None:
        if (type(self.index_name) is not str or _INDEX.fullmatch(self.index_name) is None
                or type(self.index_uuid) is not str or _UUID.fullmatch(self.index_uuid) is None
                or type(self.mapping_sha256) is not str or _SHA.fullmatch(self.mapping_sha256) is None
                or type(self.record_count) is not int or not 1 <= self.record_count <= 22000
                or type(self.max_http_requests) is not int
                or self.max_http_requests != 1 + (self.record_count + _PAGE - 1) // _PAGE):
            raise FreshSnapshotError("scan_binding_invalid")


@dataclass(frozen=True, slots=True)
class FreshSnapshotResult:
    raw: bytes
    sha256: str
    http_requests: int
    record_count: int
    mapping_version: str
    source_fingerprint: str


class SnapshotAttempts(Protocol):
    """Caller-owned durable attempt boundary; never an execution grant."""
    def begin(self, method: str, path: str, body: bytes) -> int: ...
    def finish(self, ticket: int, status: int | None, failed: bool) -> None: ...
    def abort(self) -> None: ...


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def _reject_constant(_: str) -> NoReturn:
    raise ValueError("non_finite")


class _Scan:
    def __init__(self, spec: FreshSnapshotSpec, client: httpx.Client,
                 attempts: SnapshotAttempts | None) -> None:
        self.spec = spec
        self.client = client
        self.attempts = attempts
        self.calls = 0
        self.origin: str | None = None

    def fail(self, reason: str) -> NoReturn:
        if self.attempts is not None:
            self.attempts.abort()
        raise FreshSnapshotError(reason, self.calls)

    def check_client(self) -> None:
        url = self.client.base_url
        if (not _single_send_client(self.client)
                or url.scheme != "http" or url.host not in ("127.0.0.1", "localhost", "::1")
                or url.path != "/" or url.query or url.fragment or url.userinfo
                or self.client.trust_env or self.client.follow_redirects or self.client.is_closed
                or self.origin is not None and str(url) != self.origin
                or any(value is None or not math.isfinite(value) or not 0 < value <= 30
                       for value in self.client.timeout.as_dict().values())):
            self.fail("scan_client_invalid")
        self.origin = str(url)

    def object(self, value: Any) -> dict[str, Any]:
        if type(value) is not dict:
            self.fail("scan_records_invalid")
        return value

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        self.check_client()
        if self.calls >= self.spec.max_http_requests:
            self.fail("scan_budget_exhausted")
        payload = b"" if body is None else canonical_bytes(body)
        ticket = None if self.attempts is None else self.attempts.begin(method, path, payload)
        self.calls += 1  # A disconnect/status/JSON failure still consumes an attempt.
        parsed: Any = None
        invalid = False
        status: int | None = None
        started = time.monotonic()
        try:
            with self.client.stream(
                method, path, content=payload or None,
                headers={"Content-Type": "application/json", "Accept-Encoding": "identity"},
                follow_redirects=False, timeout=30.0,
            ) as response:
                status = response.status_code
                if (response.status_code != 200
                        or response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json"
                        or response.headers.get("Content-Encoding", "identity").strip().lower() != "identity"):
                    invalid = True
                else:
                    data = bytearray()
                    for part in response.iter_bytes():
                        if len(data) + len(part) > _MAX_RESPONSE or time.monotonic() - started > 30:
                            invalid = True
                            break
                        data.extend(part)
                    if not invalid:
                        parsed = json.loads(data, object_pairs_hook=_unique, parse_constant=_reject_constant)
                        invalid = type(parsed) is not dict
        except Exception:
            invalid = True
        if self.attempts is not None and ticket is not None:
            self.attempts.finish(ticket, status, invalid)
        # Raise outside the handler: do not retain a raw HTTP/JSON exception.
        if invalid:
            self.fail("scan_http_invalid")
        return self.object(parsed)

    def run(self) -> FreshSnapshotResult:
        self.check_client()
        spec = self.spec
        definition = self.request("GET", f"/{spec.index_name}")
        if set(definition) != {spec.index_name}:
            self.fail("scan_binding_invalid")
        details = self.object(definition[spec.index_name])
        settings = self.object(self.object(details.get("settings")).get("index"))
        mappings = self.object(details.get("mappings"))
        mapping_version = self.object(mappings.get("_meta")).get("mapping_version")
        if ("data_stream" in details or settings.get("uuid") != spec.index_uuid
                or type(mapping_version) is not str or not mapping_version
                or mapping_fingerprint(mappings) != spec.mapping_sha256
                or not _write_blocked(settings)):
            self.fail("scan_binding_invalid")
        # The reused helper supports flat/nested ES settings; reject JSON numbers
        # and contradictory forms instead of treating 1 as the boolean True.
        block_values = [value for value in (
            self.object(settings.get("blocks", {})).get("write"), settings.get("blocks.write")
        ) if value is not None]
        if not block_values or any(value is not True and value != "true" for value in block_values):
            self.fail("scan_binding_invalid")

        records: list[_Record] = []
        identities: list[dict[str, str]] = []
        seen_ids: set[str] = set()
        seen_chunks: set[str] = set()
        seen_pairs: set[tuple[str, str]] = set()
        after: str | None = None
        while len(records) < spec.record_count:
            size = min(_PAGE, spec.record_count - len(records))
            query: dict[str, Any] = {
                "size": size, "track_total_hits": True, "seq_no_primary_term": True,
                "_source": {"exclude_vectors": False}, "sort": [{"chunkId": "asc"}],
                "query": {"match_all": {}},
            }
            if after is not None:
                query["search_after"] = [after]
            response = self.request("POST", f"/{spec.index_name}/_search", query)
            shards = self.object(response.get("_shards"))
            hits = self.object(response.get("hits"))
            total = self.object(hits.get("total"))
            entries = hits.get("hits")
            if (response.get("timed_out") is not False
                    or type(shards.get("failed")) is not int or shards["failed"] != 0
                    or type(shards.get("total")) is not int or shards["total"] < 1
                    or type(shards.get("successful")) is not int or shards["successful"] != shards["total"]
                    or type(total.get("value")) is not int or total["value"] != spec.record_count
                    or total.get("relation") != "eq" or type(entries) is not list
                    or not entries or len(entries) > size):
                self.fail("scan_records_invalid")
            for entry in entries:
                hit = self.object(entry)
                fields = dict(self.object(hit.get("_source")))
                identifier, chunk = hit.get("_id"), fields.get("chunkId")
                document, content = fields.get("documentId"), fields.get("content")
                if (type(identifier) is not str or not identifier or identifier in seen_ids
                        or type(chunk) is not str or not chunk or chunk in seen_chunks
                        or (after is not None and chunk <= after)
                        or type(document) is not str or not document
                        or type(content) is not str or not content
                        or unicodedata.normalize("NFC", content) != content
                        or (document, chunk) in seen_pairs or hit.get("sort") != [chunk]
                        or hit.get("_index") != spec.index_name
                        or type(hit.get("_seq_no")) is not int or hit["_seq_no"] < 0
                        or type(hit.get("_primary_term")) is not int or hit["_primary_term"] < 1):
                    self.fail("scan_records_invalid")
                vector = _vector_bytes(fields.pop("embedding", None))
                canonical_bytes(fields)
                records.append(_Record(identifier, chunk, fields, vector, hit["_seq_no"], hit["_primary_term"]))
                identities.append({"id": identifier, "documentId": document, "chunkId": chunk,
                                   "contentSha256": hashlib.sha256(content.encode("utf-8")).hexdigest()})
                seen_ids.add(identifier)
                seen_chunks.add(chunk)
                seen_pairs.add((document, chunk))
                after = chunk
        if self.calls != spec.max_http_requests:
            self.fail("scan_records_invalid")
        fingerprint = _fingerprint(tuple(records))
        identities.sort(key=lambda item: item["id"])
        raw = canonical_bytes({
            "schemaVersion": 1, "indexName": spec.index_name, "indexUuid": spec.index_uuid,
            "sourceFingerprint": fingerprint, "recordCount": spec.record_count, "records": identities,
        })
        if len(raw) > _MAX_RESPONSE:
            self.fail("scan_records_invalid")
        return FreshSnapshotResult(raw, hashlib.sha256(raw).hexdigest(), self.calls,
                                   len(records), mapping_version, fingerprint)


def scan_fresh_snapshot(spec: FreshSnapshotSpec, *, client: httpx.Client,
                        attempts: SnapshotAttempts | None = None) -> FreshSnapshotResult:
    """One definition + at most ceil(N/250) searches, no discovery or retry."""
    scan = _Scan(spec, client, attempts)
    reason = "scan_records_invalid"
    try:
        return scan.run()
    except FreshSnapshotError as error:
        reason = error.reason
    except Exception:
        pass
    raise FreshSnapshotError(reason, scan.calls)
