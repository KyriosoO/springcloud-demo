"""Isolated, read-only B identity scan. Run only with the corpus project venv.

stdin and stdout are bounded canonical JSON. No source text or vector is emitted.
The corpus scanner is imported only after the environment and input are checked.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from importlib import metadata
import json
from pathlib import Path
import re
import sys
import tomllib
from typing import Any, Callable

import httpx


ROOT = Path(__file__).resolve().parents[4]
CORPUS = ROOT / "knowledge-corpus-tools"
_INDEX = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([0-9][A-Za-z0-9._+-]*)\Z")
_MAX_INPUT = 4096
_MAX_OUTPUT = 16 * 1024 * 1024
_HTTP_LIMIT = 64
_REASONS = frozenset({
    "input_invalid", "environment_invalid", "route_forbidden", "scan_binding_invalid",
    "scan_http_invalid", "scan_records_invalid", "scan_fingerprint_drift",
    "scan_budget_exhausted", "scan_output_invalid", "worker_failed",
})


class WorkerError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason if reason in _REASONS else "worker_failed"
        super().__init__(self.reason)


@dataclass(frozen=True, slots=True)
class ScanInput:
    index_name: str
    index_uuid: str
    mapping_sha256: str
    source_fingerprint: str
    record_count: int
    max_es_http: int


@dataclass(frozen=True, slots=True)
class ScanOutput:
    raw: bytes
    mapping_version: str


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise WorkerError("input_invalid")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise WorkerError("input_invalid")


def _parse_input(raw: bytes) -> ScanInput:
    if not raw or len(raw) > _MAX_INPUT:
        raise WorkerError("input_invalid")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                           parse_constant=_reject_constant)
    except (UnicodeError, ValueError, WorkerError):
        raise WorkerError("input_invalid") from None
    if (type(value) is not dict or _canonical(value) != raw
            or set(value) != {"indexName", "indexUuid", "mappingSha256",
                              "sourceFingerprint", "recordCount", "maxEsHttp"}
            or type(value["indexName"]) is not str
            or _INDEX.fullmatch(value["indexName"]) is None
            or type(value["indexUuid"]) is not str
            or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value["indexUuid"]) is None
            or type(value["mappingSha256"]) is not str
            or _SHA.fullmatch(value["mappingSha256"]) is None
            or type(value["sourceFingerprint"]) is not str
            or _SHA.fullmatch(value["sourceFingerprint"]) is None
            or type(value["recordCount"]) is not int or value["recordCount"] != 15521
            or type(value["maxEsHttp"]) is not int or value["maxEsHttp"] != _HTTP_LIMIT):
        raise WorkerError("input_invalid")
    return ScanInput(value["indexName"], value["indexUuid"],
                     value["mappingSha256"], value["sourceFingerprint"],
                     value["recordCount"], value["maxEsHttp"])


def _check_environment() -> None:
    """Pin the entire corpus runtime dependency set before any ES HTTP attempt."""
    if (sys.version_info[:2] != (3, 12)
            or Path(sys.prefix).resolve() != (CORPUS / ".venv").resolve()):
        raise WorkerError("environment_invalid")
    try:
        with (CORPUS / "pyproject.toml").open("rb") as stream:
            manifest = tomllib.load(stream)
        dependencies = manifest["project"]["dependencies"]
        if type(dependencies) is not list or not dependencies:
            raise ValueError
        for dependency in dependencies:
            if type(dependency) is not str or (match := _PIN.fullmatch(dependency)) is None:
                raise ValueError
            if metadata.version(match.group(1)) != match.group(2):
                raise ValueError
    except (KeyError, OSError, ValueError, metadata.PackageNotFoundError):
        raise WorkerError("environment_invalid") from None


class RestrictedEsTransport(httpx.BaseTransport):
    """Admit exactly the scanner's two physical read routes, with no auth."""

    def __init__(self, index_name: str, *, delegate: httpx.BaseTransport | None = None) -> None:
        self.index_name = index_name
        self.delegate = delegate if delegate is not None else httpx.HTTPTransport(
            retries=0, trust_env=False)
        self.attempts = 0
        self.forbidden = False

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        allowed = {(b"GET", f"/{self.index_name}".encode("ascii")),
                   (b"POST", f"/{self.index_name}/_search".encode("ascii"))}
        method = request.method.encode("ascii", errors="ignore")
        path = request.url.raw_path
        sensitive_headers = {"authorization", "proxy-authorization", "cookie", "x-api-key"}
        if (request.url.scheme != "http" or request.url.host != "127.0.0.1"
                or request.url.port != 9200 or request.url.query
                or request.url.username or request.url.password
                or (method, path) not in allowed
                or any(header in request.headers for header in sensitive_headers)):
            self.forbidden = True
            raise WorkerError("route_forbidden")
        if self.attempts >= _HTTP_LIMIT:
            raise WorkerError("scan_budget_exhausted")
        self.attempts += 1
        return self.delegate.handle_request(request)

    def close(self) -> None:
        self.delegate.close()


def _real_scan(spec: ScanInput, client: httpx.Client) -> ScanOutput:
    from knowledge_corpus_tools.b_id_mapping_v1 import (
        BIdMappingError, MappingScanSpec, scan_id_mapping_v1,
    )

    try:
        result = scan_id_mapping_v1(MappingScanSpec(
            index_name=spec.index_name, index_uuid=spec.index_uuid,
            mapping_sha256=spec.mapping_sha256,
            source_fingerprint=spec.source_fingerprint,
            record_count=spec.record_count, max_http_requests=spec.max_es_http,
        ), client=client)
    except BIdMappingError as exc:
        raise WorkerError(exc.reason) from None
    return ScanOutput(result.raw, result.mapping_version)


def _validate_map(spec: ScanInput, result: ScanOutput) -> None:
    if (type(result.raw) is not bytes or not result.raw or len(result.raw) > _MAX_OUTPUT
            or type(result.mapping_version) is not str
            or re.fullmatch(r"[A-Za-z0-9._-]{1,128}", result.mapping_version) is None):
        raise WorkerError("scan_output_invalid")
    try:
        value = json.loads(result.raw.decode("utf-8"), object_pairs_hook=_unique,
                           parse_constant=_reject_constant)
    except (UnicodeError, ValueError, WorkerError):
        raise WorkerError("scan_output_invalid") from None
    if (type(value) is not dict or _canonical(value) != result.raw
            or set(value) != {"schemaVersion", "indexName", "indexUuid",
                              "sourceFingerprint", "recordCount", "records"}
            or value["schemaVersion"] != 1
            or value["indexName"] != spec.index_name
            or value["indexUuid"] != spec.index_uuid
            or value["sourceFingerprint"] != spec.source_fingerprint
            or value["recordCount"] != spec.record_count
            or type(value["records"]) is not list
            or len(value["records"]) != spec.record_count):
        raise WorkerError("scan_output_invalid")
    for row in value["records"]:
        if (type(row) is not dict
                or set(row) != {"id", "documentId", "chunkId", "contentSha256"}
                or any(type(row[key]) is not str or not row[key]
                       for key in ("id", "documentId", "chunkId"))
                or type(row["contentSha256"]) is not str
                or _SHA.fullmatch(row["contentSha256"]) is None):
            raise WorkerError("scan_output_invalid")


def _envelope(*, status: str, reason: str | None, es_http: int,
              raw: bytes | None = None, mapping_version: str | None = None) -> bytes:
    encoded = _canonical({"status": status, "reason": reason, "esHttp": es_http,
                          "rawBase64": None if raw is None else base64.b64encode(raw).decode("ascii"),
                          "mappingVersion": mapping_version})
    if len(encoded) > _MAX_OUTPUT:
        raise WorkerError("scan_output_invalid")
    return encoded


def run_worker(raw: bytes, *, delegate: httpx.BaseTransport | None = None,
               scanner: Callable[[ScanInput, httpx.Client], ScanOutput] | None = None) -> bytes:
    transport: RestrictedEsTransport | None = None
    try:
        spec = _parse_input(raw)
        _check_environment()
        transport = RestrictedEsTransport(spec.index_name, delegate=delegate)
        with httpx.Client(base_url="http://127.0.0.1:9200", transport=transport,
                          trust_env=False, follow_redirects=False, timeout=30.0) as client:
            result = (scanner if scanner is not None else _real_scan)(spec, client)
        if transport.forbidden or transport.attempts != spec.max_es_http:
            raise WorkerError("route_forbidden" if transport.forbidden
                              else "scan_budget_exhausted")
        _validate_map(spec, result)
        return _envelope(status="scanned_read_only", reason=None,
                         es_http=transport.attempts, raw=result.raw,
                         mapping_version=result.mapping_version)
    except WorkerError as exc:
        reason = "route_forbidden" if transport is not None and transport.forbidden else exc.reason
    except Exception:
        reason = "worker_failed"
    return _envelope(status="failed", reason=reason,
                     es_http=transport.attempts if transport is not None else 0)


def main() -> int:
    try:
        raw = sys.stdin.buffer.read(_MAX_INPUT + 1)
        result = run_worker(raw)
    except Exception:
        result = _envelope(status="failed", reason="worker_failed", es_http=0)
    sys.stdout.buffer.write(result)
    return 0 if b'"status":"scanned_read_only"' in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
