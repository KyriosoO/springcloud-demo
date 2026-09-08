"""DR-KRET-025/032 replay guards; all HTTP and service processes are synthetic."""
import asyncio
from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import httpx
import pytest

from tests.system_e2e.test_policy_vector_typed_validation import fixture_catalog


@pytest.fixture
def runner():
    path = Path(__file__).parents[3] / "knowledge-corpus-tools/scripts/rehearse-policy-vector-rollback-v1.py"
    spec = importlib.util.spec_from_file_location("policy_rollback_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("fault", [None, "snapshot", "hash", "denied_body", "timeout"])
def test_actual_adapter_and_evidence_strictness_per_phase(runner, monkeypatch, fault):
    from agent_runtime.knowledge.retrieval import http as boundary
    support = runner.load_support()
    calls, clients = [], []
    def handle(request):
        calls.append(request.url.path)
        raw = json.loads(request.content)
        if request.url.path == "/embed":
            result, status = {"dim": 1024, "vectors": [[0.1] * 1024]}, 200
        elif request.headers.get("authorization") != "Bearer synthetic-admin":
            status = 403 if request.headers.get("authorization") else 401
            result = {"code": "denied"} if fault != "denied_body" else {"content": "private"}
        else:
            if fault == "timeout":
                raise httpx.ReadTimeout("private")
            content = "公开合成条款原文。"
            domain = raw["logicalDomainId"]
            status = 200
            result = {"schemaVersion": 1, "logicalDomainId": domain, "retrievalProfileId": raw["retrievalProfileId"],
                "path": raw["path"], "profileVersion": "tax-knowledge-search-v1",
                "indexSnapshotId": ("a" if domain == "tax.policy" else "b") * 64,
                "readPolicyVersion": "tax-public-authenticated-v1", "truncated": False,
                "candidates": [{"documentId": domain, "chunkId": "synthetic", "logicalDomainId": domain,
                    "title": "公开测试", "content": content, "sourceUrl": None, "documentNumber": None,
                    "writtenDate": "2026-01-01", "materialType": "fixture", "sourceRank": 1,
                    "contentSha256": hashlib.sha256(content.encode()).hexdigest(), "policyRef": "public:tax_policy"}]}
            if fault == "snapshot":
                result["indexSnapshotId"] = "0" * 64
            elif fault == "hash":
                result["candidates"][0]["contentSha256"] = "0" * 64
        return httpx.Response(status, stream=httpx.ByteStream(json.dumps(result).encode()),
                              headers={"content-type": "application/json"})
    def client(base_url):
        value = httpx.AsyncClient(base_url=base_url, transport=httpx.MockTransport(handle), trust_env=False)
        clients.append(value)
        return value
    monkeypatch.setattr(boundary, "build_knowledge_http_client", client)
    total, phase = {"typedCalls": 0, "embeddingCalls": 0}, {"checks": []}
    task = runner.check_phase(support, {"policySnapshotId": "a" * 64, "lawSnapshotId": "b" * 64},
        fixture_catalog(), {"admin": "synthetic-admin", "unknown": "synthetic-unknown", "missing": ""}, total, phase)
    if fault is None:
        asyncio.run(task)
        assert total == {"typedCalls": 8, "embeddingCalls": 2}
        assert len(phase["checks"]) == 8
        assert "公开合成条款" not in json.dumps(phase, ensure_ascii=False)
        assert "synthetic-admin" not in json.dumps(phase)
    else:
        with pytest.raises(ValueError):
            asyncio.run(task)
        assert total["typedCalls"] <= 3
    assert all(client.is_closed for client in clients)
    assert set(calls) <= {"/es/knowledge/search", "/embed"}


@pytest.mark.parametrize("counter,value", [("typedCalls", 24), ("embeddingCalls", 6), ("typedCalls", True), ("typedCalls", -1)])
def test_counter_limit_before_outbound(runner, counter, value):
    total = {counter: value}
    with pytest.raises(ValueError, match="budget_exceeded"):
        runner.take(total, counter)
    assert total[counter] == value


@pytest.mark.parametrize("failure", [None, "source_rollback", "cleanup", "prepare_output", "artifact_drift"])
def test_three_phases_stop_services_before_switch_and_never_replay(runner, monkeypatch, tmp_path, failure):
    support = runner.load_support()
    events = []
    source = {"expectedIndexName": "source", "expectedIndexUuid": "source-uuid", "readAlias": "published"}
    candidate = {**source, "expectedIndexName": "candidate", "expectedIndexUuid": "candidate-uuid"}
    monkeypatch.setattr(support, "preflight", lambda: (candidate, source, b"catalog"))
    monkeypatch.setattr(support, "checked_bytes", lambda *args: b"{}")
    monkeypatch.setattr(support, "IndexIdentity", lambda *args: args)
    artifact_calls = []
    def artifacts():
        artifact_calls.append(1)
        return {"fixture": "changed" if failure == "artifact_drift" and len(artifact_calls) > 1 else "initial"}
    monkeypatch.setattr(runner, "artifact_hashes", artifacts)
    class Lease:
        reads = 0
        writes = 0
        name = "temporary"
        def __init__(self, source, candidate, published_alias):
            self.source, self.candidate = source, candidate
            self.closed = False
        def __enter__(self):
            events.append("alias-create")
            return self.name
        def move(self, target):
            assert events[-1].startswith("stop-")
            events.append("move-" + target[0])
        def __exit__(self, *args):
            self.close()
        def close(self):
            if not self.closed:
                events.append("alias-remove" if "alias-create" in events else "close-unused-client")
                self.closed = True
    monkeypatch.setattr(support, "ValidationAlias", Lease)
    @contextmanager
    def services(binding, alias, phase):
        label = phase["phase"]
        events.append("start-" + label)
        try:
            yield {"admin": "private"}
        finally:
            events.append("stop-" + label)
            phase.update(profileVerifierStartupPassed=True, ownedProcessesStopped=True, rawLogsDeleted=True, secretScanPassed=True)
            if failure == "cleanup":
                raise ValueError("service_cleanup_failed")
    monkeypatch.setattr(support, "isolated_services", services)
    async def check(support, binding, catalog, tokens, total, phase):
        if phase["phase"] == failure:
            raise ValueError("typed_result_invalid")
        total["typedCalls"] += 8
        total["embeddingCalls"] += 2
    monkeypatch.setattr(runner, "check_phase", check)
    if failure == "prepare_output":
        def failed_emit(*args):
            raise ValueError("rehearsal_result_limit")
        monkeypatch.setattr(runner, "emit", failed_emit)
    total = {"typedCalls": 0, "embeddingCalls": 0, "phasesPassed": 0}
    path = tmp_path / "proof.jsonl"
    with path.open("xb") as stream:
        if failure:
            with pytest.raises(ValueError):
                runner.rehearse(support, stream, total)
        else:
            runner.rehearse(support, stream, total)
    records = [json.loads(line) for line in path.read_bytes().splitlines()]
    if failure == "prepare_output":
        assert not records and events == ["close-unused-client"]
        return
    assert records[0]["event"] == "prepared" and events[-1] == "alias-remove"
    assert "private" not in path.read_text()
    if failure in {"cleanup", "source_rollback"}:
        assert total["phasesPassed"] < 3 and records[-1]["status"] == "failed"
        assert "start-candidate_return" not in events
    else:
        assert total["phasesPassed"] == 3 and total["typedCalls"] == 24 and total["embeddingCalls"] == 6
        assert [row["phase"] for row in records[1:]] == ["candidate_initial", "source_rollback", "candidate_return"]
        assert all(row["status"] == "passed" for row in records[1:])
        assert events == ["alias-create", "start-candidate_initial", "stop-candidate_initial", "move-source",
            "start-source_rollback", "stop-source_rollback", "move-candidate", "start-candidate_return",
            "stop-candidate_return", "alias-remove"]
        if failure == "artifact_drift":
            assert total.get("status") != "passed"


def test_historical_support_hash_and_exclusive_result(runner, monkeypatch, tmp_path):
    helper = tmp_path / "support.py"
    helper.write_text("raise RuntimeError('must not execute')")
    monkeypatch.setattr(runner, "HELPER", helper)
    with pytest.raises(ValueError, match="support_hash_changed"):
        runner.load_support()
    output = tmp_path / "proof.jsonl"
    monkeypatch.setattr(sys, "argv", ["rehearse", "--result", str(output)])
    with pytest.raises(SystemExit):
        runner.main()
    assert not output.exists()
    monkeypatch.setattr(sys, "argv", ["rehearse", "--execute", "--result", str(output)])
    assert runner.main() == 1
    original = output.read_bytes()
    assert json.loads(original)["reason"] == "support_hash_changed"
    with pytest.raises(FileExistsError):
        runner.main()
    assert output.read_bytes() == original
