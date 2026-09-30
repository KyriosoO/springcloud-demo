"""No-network contract tests for the isolated B identity-scan worker."""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx
import pytest

from tests.evaluation.knowledge import rebuild_b_mapping_worker as worker


INDEX = "agent-doc-tax-policy-v5-20260907-vector-b2"
UUID = "jJ5Ww3LCRWWycfDkUZvmdw"
SHA = "a" * 64
FINGERPRINT = "b" * 64


def _input(**changes: object) -> bytes:
    value: dict[str, object] = {
        "indexName": INDEX, "indexUuid": UUID, "mappingSha256": SHA,
        "sourceFingerprint": FINGERPRINT, "recordCount": 15521, "maxEsHttp": 64,
    }
    value.update(changes)
    return worker._canonical(value)


def _map() -> bytes:
    return worker._canonical({
        "schemaVersion": 1, "indexName": INDEX, "indexUuid": UUID,
        "sourceFingerprint": FINGERPRINT, "recordCount": 15521,
        "records": [{"id": f"id-{number:05d}", "documentId": "doc-1",
                     "chunkId": f"chunk-{number:05d}", "contentSha256": SHA}
                    for number in range(15521)],
    })


def _decode(raw: bytes) -> dict[str, Any]:
    assert raw.endswith(b"\n")
    value: dict[str, Any] = json.loads(raw)
    assert worker._canonical(value) == raw
    return value


def test_success_emits_only_canonical_id_hash_map_and_exact_64_attempts(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker, "_check_environment", lambda: None)
    paths: list[str] = []

    def backend(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200, json={})

    def scanner(spec: worker.ScanInput, client: httpx.Client) -> worker.ScanOutput:
        assert spec.record_count == 15521
        assert client.get(f"/{INDEX}").status_code == 200
        for _ in range(63):
            assert client.post(f"/{INDEX}/_search", json={}).status_code == 200
        return worker.ScanOutput(_map(), "knowledge-v1")

    result = _decode(worker.run_worker(_input(), delegate=httpx.MockTransport(backend), scanner=scanner))
    assert result["status"] == "scanned_read_only"
    assert result["reason"] is None and result["esHttp"] == 64
    assert result["mappingVersion"] == "knowledge-v1"
    assert set(result) == {"status", "reason", "esHttp", "rawBase64", "mappingVersion"}
    decoded = base64.b64decode(result["rawBase64"], validate=True)
    assert decoded == _map() and b'"content":' not in decoded and b'"embedding":' not in decoded
    assert paths == [f"/{INDEX}"] + [f"/{INDEX}/_search"] * 63


def test_failed_transport_counts_attempt_and_never_emits_body(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker, "_check_environment", lambda: None)
    calls = 0

    def backend(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("SECRET_RAW_RESPONSE")
        return httpx.Response(200, json={})

    def scanner(_: worker.ScanInput, client: httpx.Client) -> worker.ScanOutput:
        client.get(f"/{INDEX}")
        client.post(f"/{INDEX}/_search", json={})
        raise AssertionError("unreachable")

    encoded = worker.run_worker(_input(), delegate=httpx.MockTransport(backend), scanner=scanner)
    result = _decode(encoded)
    assert result == {"status": "failed", "reason": "worker_failed", "esHttp": 2,
                      "rawBase64": None, "mappingVersion": None}
    assert b"SECRET_RAW_RESPONSE" not in encoded


def test_budget_rejects_65th_request_before_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker, "_check_environment", lambda: None)
    sent = 0

    def backend(_: httpx.Request) -> httpx.Response:
        nonlocal sent
        sent += 1
        return httpx.Response(200, json={})

    def scanner(_: worker.ScanInput, client: httpx.Client) -> worker.ScanOutput:
        for _ in range(65):
            client.get(f"/{INDEX}")
        raise AssertionError("unreachable")

    result = _decode(worker.run_worker(_input(), delegate=httpx.MockTransport(backend), scanner=scanner))
    assert result["status"] == "failed" and result["reason"] == "scan_budget_exhausted"
    assert result["esHttp"] == sent == 64


@pytest.mark.parametrize("path,headers", [
    ("/other/_search", {}),
    (f"/{INDEX}/_update", {}),
    (f"/{INDEX}?refresh=true", {}),
    (f"/{INDEX}", {"Authorization": "Bearer SECRET"}),
])
def test_route_query_or_auth_is_rejected_without_http(
        monkeypatch: pytest.MonkeyPatch, path: str, headers: dict[str, str]) -> None:
    monkeypatch.setattr(worker, "_check_environment", lambda: None)
    sent = 0

    def backend(_: httpx.Request) -> httpx.Response:
        nonlocal sent
        sent += 1
        return httpx.Response(200, json={})

    def scanner(_: worker.ScanInput, client: httpx.Client) -> worker.ScanOutput:
        client.get(path, headers=headers)
        raise AssertionError("unreachable")

    result = _decode(worker.run_worker(_input(), delegate=httpx.MockTransport(backend), scanner=scanner))
    assert result["status"] == "failed" and result["reason"] == "route_forbidden"
    assert result["esHttp"] == sent == 0


def test_dependency_drift_fails_before_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker.sys, "prefix", str(worker.CORPUS / ".venv"))
    actual = worker.metadata.version
    monkeypatch.setattr(worker.metadata, "version",
                        lambda name: "0.0.0" if name == "beautifulsoup4" else actual(name))
    sent = 0

    def backend(_: httpx.Request) -> httpx.Response:
        nonlocal sent
        sent += 1
        return httpx.Response(200, json={})

    result = _decode(worker.run_worker(_input(), delegate=httpx.MockTransport(backend)))
    assert result["status"] == "failed" and result["reason"] == "environment_invalid"
    assert result["esHttp"] == sent == 0


@pytest.mark.parametrize("raw", [
    _input(indexName="bad/index"),
    _input(recordCount=15520),
    _input(maxEsHttp=65),
    _input(extra="unknown"),
    _input(recordCount=True),
    b'{"indexName":"one","indexName":"two"}\n',
    _input().rstrip(b"\n"),
])
def test_strict_input_rejected_before_environment_or_http(
        monkeypatch: pytest.MonkeyPatch, raw: bytes) -> None:
    checked = 0

    def check_environment() -> None:
        nonlocal checked
        checked += 1

    monkeypatch.setattr(worker, "_check_environment", check_environment)
    result = _decode(worker.run_worker(raw))
    assert result["status"] == "failed" and result["reason"] == "input_invalid"
    assert result["esHttp"] == checked == 0


def test_output_with_source_body_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker, "_check_environment", lambda: None)

    def scanner(_: worker.ScanInput, client: httpx.Client) -> worker.ScanOutput:
        client.get(f"/{INDEX}")
        for _ in range(63):
            client.post(f"/{INDEX}/_search", json={})
        value = json.loads(_map())
        value["records"][0]["content"] = "LEAK"
        return worker.ScanOutput(worker._canonical(value), "knowledge-v1")

    result = _decode(worker.run_worker(_input(),
        delegate=httpx.MockTransport(lambda _: httpx.Response(200, json={})), scanner=scanner))
    assert result["status"] == "failed" and result["reason"] == "scan_output_invalid"
    assert result["esHttp"] == 64 and result["rawBase64"] is None
