"""Non-live guards for DR-KRET-032; no local services or model access."""
import asyncio
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys

import httpx
import pytest


@pytest.fixture
def runner():
    path = Path(__file__).parents[3] / "knowledge-corpus-tools/scripts/validate-policy-vector-typed-v1.py"
    spec = importlib.util.spec_from_file_location("policy_vector_typed_v1_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_artifact_tamper_fails_before_side_effect(runner, tmp_path):
    path = tmp_path / "binding.json"
    path.write_bytes(b"{}")
    with pytest.raises(ValueError, match="artifact_hash_changed"):
        runner.checked_bytes(path, "0" * 64)
    with pytest.raises(ValueError, match="artifact_size_invalid"):
        runner.checked_bytes(path, "0" * 64, 1)


def test_port_conflict_prevents_service_start(runner, monkeypatch):
    monkeypatch.setattr(runner, "checked_bytes", lambda *args: b"{}")
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        monkeypatch.setattr(runner, "PORTS", (occupied.getsockname()[1],))
        with pytest.raises(OSError):
            runner.preflight()


def test_signing_finite_roles_and_no_model_environment(runner, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "should-never-be-read")
    token = runner.sign_token(base64.b64encode(b"a" * 48).decode(), "UNKNOWN")
    claims = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
    assert claims["role"] == ["UNKNOWN"] and claims["token_type"] == "user"
    assert "should-never-be-read" not in token


@pytest.mark.parametrize("version", ["1.8.0", "21.0.2", "25.0.2"])
def test_java_home_selected_instead_of_path_java8(runner, monkeypatch, tmp_path, version):
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin/java.exe").write_bytes(b"synthetic")
    (tmp_path / "release").write_text(f'JAVA_VERSION="{version}"')
    monkeypatch.setenv("JAVA_HOME", str(tmp_path))
    if version.startswith("25."):
        assert runner.java_executable() == str(tmp_path / "bin/java.exe")
    else:
        with pytest.raises(ValueError, match="java_home_invalid"):
            runner.java_executable()


def test_every_owned_pid_attempted_when_first_termination_fails(runner):
    class Process:
        def __init__(self, fail):
            self.fail, self.stopped = fail, False
        def poll(self):
            return 0 if self.stopped else None
        def terminate(self):
            if self.fail:
                raise OSError("private")
            self.stopped = True
        def wait(self, timeout):
            pass
    first, second = Process(False), Process(True)
    assert not runner.stop_owned([first, second])
    assert first.stopped


def test_raw_log_scan_across_chunks_and_exact_path_cleanup(runner, tmp_path):
    log = tmp_path / "owned.log"
    secret = "synthetic-protected-token"
    log.write_bytes(b"x" * 65530 + secret.encode() + b"knowledge.profile")
    leaked, markers = runner.scan_log(log, tmp_path, (secret,))
    assert leaked and markers == {"knowledge.profile"} and not log.exists()
    outside = tmp_path / "not-owned"
    outside.mkdir()
    log.write_text("preserve")
    with pytest.raises(ValueError, match="cleanup_path_invalid"):
        runner.scan_log(log, outside, (secret,))
    assert log.read_text() == "preserve"


def fixture_catalog():
    return json.dumps({"schemaVersion": 1, "catalogVersion": "tax-egress-catalog-v3",
        "authorityId": "fixture", "exportId": "fixture", "sourceRevision": "fixture",
        "policies": [{"policyRef": "public:tax_policy", "policyVersion": "1",
            "disposition": "allow_minimal", "allowedFields": ["content", "title", "domain_ids"],
            "maxContentCodePoints": 4096}],
        "bindings": [{"documentId": domain, "policyRef": "public:tax_policy", "policyVersion": "1",
                      "allowedIndexSnapshotIds": [snapshot]} for domain, snapshot in (("tax.policy", "a" * 64), ("tax.law", "b" * 64))],
    }).encode()


@pytest.mark.parametrize("fault", [None, "hash", "snapshot", "denied_body", "timeout"])
def test_exact_java_shape_actual_runtime_decoder_evidence_and_denial(runner, monkeypatch, fault):
    from agent_runtime.knowledge.retrieval import http as boundary
    calls = []
    def response(request):
        calls.append(request.url.path)
        raw = json.loads(request.content)
        if request.url.path == "/embed":
            value, status = {"dim": 1024, "vectors": [[0.1] * 1024]}, 200
        else:
            assert request.url.path == "/es/knowledge/search"
            role = request.headers.get("authorization", "").removeprefix("Bearer ")
            if role not in {"admin", "viewer"}:
                status = 403 if role == "unknown" else 401
                value = {"code": "denied"} if fault != "denied_body" else {"content": "private"}
            else:
                if fault == "timeout":
                    raise httpx.ReadTimeout("private response")
                domain = raw["logicalDomainId"]
                content = "公开原文合成测试。"
                status = 200
                value = {"schemaVersion": 1, "logicalDomainId": domain, "retrievalProfileId": raw["retrievalProfileId"],
                    "path": raw["path"], "profileVersion": "tax-knowledge-search-v1",
                    "indexSnapshotId": ("a" if domain == "tax.policy" else "b") * 64,
                    "readPolicyVersion": "tax-public-authenticated-v1", "truncated": False,
                    "candidates": [{"documentId": domain, "chunkId": "chunk-1", "logicalDomainId": domain,
                        "title": "公开测试", "content": content, "sourceUrl": None, "documentNumber": None,
                        "writtenDate": "2026-01-01", "materialType": "fixture", "sourceRank": 1,
                        "contentSha256": hashlib.sha256(content.encode()).hexdigest(), "policyRef": "public:tax_policy"}]}
                if fault == "hash":
                    value["candidates"][0]["contentSha256"] = "0" * 64
                elif fault == "snapshot":
                    value["indexSnapshotId"] = "0" * 64
        return httpx.Response(status, stream=httpx.ByteStream(json.dumps(value).encode()),
                              headers={"content-type": "application/json"})
    clients = []
    def client(url):
        instance = httpx.AsyncClient(base_url=url, trust_env=False, transport=httpx.MockTransport(response))
        clients.append(instance)
        return instance
    monkeypatch.setattr(boundary, "build_knowledge_http_client", client)
    result = {"typedCalls": 0, "embeddingCalls": 0, "checks": []}
    tokens = {role: role for role in ("admin", "viewer", "unknown", "service", "malformed")}
    tokens["missing"] = ""
    run = runner.typed_checks({"policySnapshotId": "a" * 64, "lawSnapshotId": "b" * 64}, fixture_catalog(), tokens, result)
    if fault is None:
        asyncio.run(run)
        assert result["typedCalls"] == 16 and result["embeddingCalls"] == 2 and len(result["checks"]) == 16
        assert "公开原文" not in json.dumps(result, ensure_ascii=False)
        assert "admin" not in json.dumps(result.get("tokens", {}))
    else:
        with pytest.raises(ValueError):
            asyncio.run(run)
        assert result["typedCalls"] <= 5
    assert all(item.is_closed for item in clients)
    assert set(calls) <= {"/embed", "/es/knowledge/search"}


def test_no_execution_without_explicit_flag_or_replay(runner, monkeypatch, tmp_path):
    output = tmp_path / "result.json"
    monkeypatch.setattr(sys, "argv", ["runner", "--result", str(output)])
    with pytest.raises(SystemExit):
        runner.main()
    assert not output.exists()
    output.write_text("historical")
    monkeypatch.setattr(sys, "argv", ["runner", "--execute", "--result", str(output)])
    with pytest.raises(FileExistsError):
        runner.main()
    assert output.read_text() == "historical"
