"""No real Java, ES, BGE or model calls for the one-shot B launcher."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import socket
from types import SimpleNamespace
from zipfile import ZipFile

import httpx
import pytest

from tests.evaluation.knowledge import rebuild_b_local_runner as runner
from tests.evaluation.knowledge.rebuild_b_local_transport import RequestWitness
from tests.evaluation.knowledge.test_rebuild_b_comparator import execute, plan_payload, spec


def _reuse_directory(tmp_path: Path, monkeypatch) -> Path:
    from tests.evaluation.knowledge.test_rebuild_b_reuse_binding import _intent, _scan_artifacts
    old = runner.reuse.load_old_build()
    raw = _intent(old)
    sidecars, _, _ = _scan_artifacts(old, raw)
    intent = json.loads(raw)
    monkeypatch.setattr(runner, "_STARTUP_EVIDENCE_ROOT", tmp_path)
    directory = tmp_path / intent["runId"]
    directory.mkdir()
    for key, filename in (("reuseIntent", "reuse-intent.json"),
            ("reuseFinal", "reuse-final.json"), ("sourceScanResult", "source-scan-result.json"),
            ("candidateScanResult", "candidate-scan-result.json"),
            ("reuseAttempt", "reuse-scan-attempt.json"),
            ("reuseTerminal", "reuse-scan-terminal.json")):
        (directory / filename).write_bytes(sidecars[key])
    for arm in ("source", "candidate"):
        (directory / f"{arm}-id-mapping.json").write_bytes(
            dict(old.blobs)[f"{arm}-id-mapping.json"])
    monkeypatch.setattr(runner, "_git", lambda *args:
        intent["frozenHead"] if args[0] == "rev-parse" else
        "codex_0915" if args[0] == "branch" else "")
    return directory


def test_load_new_reuse_branch_has_no_network(tmp_path: Path, monkeypatch) -> None:
    directory = _reuse_directory(tmp_path, monkeypatch)
    monkeypatch.setattr(runner.httpx, "Client", lambda **_kwargs:
        pytest.fail("network reached during frozen load"))
    loaded = runner.load_frozen_inputs(directory)
    assert loaded.run_id == directory.name
    assert set(loaded.sidecars) == runner.reuse.REUSE_SIDECARS
    assert len(loaded.baseline_map.records) == 15521
    assert loaded.baseline_map.records == loaded.candidate_map.records


def test_load_reuse_rejects_copied_run_outside_evidence_root(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = _reuse_directory(tmp_path, monkeypatch)
    expected_root = tmp_path / "official-evidence"
    expected_root.mkdir()
    monkeypatch.setattr(runner, "_STARTUP_EVIDENCE_ROOT", expected_root)
    monkeypatch.setattr(runner, "_load_reuse_inputs", lambda _directory:
        pytest.fail("copied run must be rejected before sidecar admission"))
    monkeypatch.setattr(runner.httpx, "Client", lambda **_kwargs:
        pytest.fail("network reached for copied run"))
    with pytest.raises(runner.BLocalRunError, match="run_preflight_invalid"):
        runner.load_frozen_inputs(directory)


@pytest.mark.parametrize("drift", ["receipt", "head", "map", "final", "consumed",
                                  "missing_attempt", "missing_terminal"])
def test_load_reuse_rejects_drift_before_alias_or_network(
        tmp_path: Path, monkeypatch, drift: str) -> None:
    directory = _reuse_directory(tmp_path, monkeypatch)
    if drift == "head":
        monkeypatch.setattr(runner, "_git", lambda *args:
            "0" * 40 if args[0] == "rev-parse" else "codex_0915" if args[0] == "branch" else "")
    elif drift == "consumed":
        (directory / "comparison-attempt.json").write_bytes(b"{}\n")
    elif drift in ("missing_attempt", "missing_terminal"):
        filename = "reuse-scan-attempt.json" if drift == "missing_attempt" else "reuse-scan-terminal.json"
        (directory / filename).unlink()
    else:
        filename = {"receipt": "source-scan-result.json", "map": "source-id-mapping.json",
                    "final": "reuse-final.json"}[drift]
        value = json.loads((directory / filename).read_bytes())
        key = {"receipt": "esHttp", "map": "sourceFingerprint",
               "final": "sourceIdMappingSha256"}[drift]
        value[key] = 63 if drift == "receipt" else "0" * 64
        (directory / filename).write_bytes(runner._canonical(value))
    monkeypatch.setattr(runner.httpx, "Client", lambda **_kwargs:
        pytest.fail("network reached during frozen load"))
    with pytest.raises(runner.BLocalRunError):
        runner.load_frozen_inputs(directory)


def test_prepare_reuse_rejects_dirty_head_or_existing_directory(
        tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "_STARTUP_EVIDENCE_ROOT", tmp_path)
    monkeypatch.setattr(runner, "_git", lambda *args:
        "codex_0915" if args[0] == "branch" else " M tracked.py")
    with pytest.raises(runner.BLocalRunError, match="reuse_preflight_invalid"):
        runner.prepare_reuse_inputs(tmp_path / "new-readonly-run")
    assert not (tmp_path / "new-readonly-run").exists()


@pytest.mark.parametrize("candidate_fails", [False, True])
def test_prepare_reuse_isolates_corpus_worker_and_preserves_actual_failed_counts(
        tmp_path: Path, monkeypatch, candidate_fails: bool) -> None:
    from tests.evaluation.knowledge.test_rebuild_b_reuse_binding import _head
    old = runner.reuse.load_old_build()
    head = _head()
    monkeypatch.setattr(runner, "_STARTUP_EVIDENCE_ROOT", tmp_path)
    monkeypatch.setattr(runner, "_git", lambda *args:
        head if args[0] == "rev-parse" else "codex_0915" if args[0] == "branch" else "")
    create, execute = runner.reuse.create_reuse_run, runner.reuse.execute_reuse_scans
    monkeypatch.setattr(runner.reuse, "create_reuse_run", lambda directory, raw:
        create(directory, raw, frozen_context=lambda _head: True))
    monkeypatch.setattr(runner.reuse, "execute_reuse_scans", lambda directory, **kwargs:
        execute(directory, **kwargs, frozen_context=lambda _head: True))
    monkeypatch.setenv("LLM_API_KEY", "synthetic-must-not-reach-scan-worker")
    sent: list[str] = []

    def worker(command, **kwargs):
        assert Path(command[0]) == runner.ROOT / "knowledge-corpus-tools/.venv/Scripts/python.exe"
        assert Path(command[1]).name == "rebuild_b_mapping_worker.py"
        assert "LLM_API_KEY" not in kwargs["env"]
        assert kwargs["env"]["PYTHONPATH"] == str(runner.ROOT / "knowledge-corpus-tools/src")
        identity = json.loads(kwargs["input"])
        assert identity["maxEsHttp"] == 64 and identity["recordCount"] == 15521
        arm = "source" if identity["indexName"] == old.spec.source_corpus.index_name else "candidate"
        sent.append(arm)
        failed = candidate_fails and arm == "candidate"
        envelope = {"status": "failed" if failed else "scanned_read_only",
            "reason": "scan_failed" if failed else None,
            "esHttp": 7 if failed else 64,
            "rawBase64": None if failed else runner.base64.b64encode(
                dict(old.blobs)[f"{arm}-id-mapping.json"]).decode(),
            "mappingVersion": None if failed else "agent-knowledge-tax-v3-policy-context-v1"}
        return SimpleNamespace(returncode=1 if failed else 0, stdout=runner._canonical(envelope), stderr=b"")

    original = runner.subprocess.run
    monkeypatch.setattr(runner.subprocess, "run", lambda command, **kwargs:
        worker(command, **kwargs) if Path(command[0]).name == "python.exe"
        else original(command, **kwargs))
    directory = tmp_path / "knowledge-b-isolated-worker-fake"
    if candidate_fails:
        with pytest.raises(runner.reuse.ReuseBindingError):
            runner.prepare_reuse_inputs(directory)
    else:
        assert runner.prepare_reuse_inputs(directory)["status"] == "reuse_scanned"
    assert sent == ["source", "candidate"]
    terminal = json.loads((directory / "reuse-scan-terminal.json").read_bytes())
    assert terminal["sourceEsHttp"] == 64
    assert terminal["candidateEsHttp"] == (7 if candidate_fails else 64)
    assert terminal["builderWriteOps"] == terminal["builderEmbeddingHttp"] == terminal["paid"] == 0
    assert terminal["status"] == ("failed" if candidate_fails else "scanned_read_only")


def _inputs() -> runner.FrozenInputs:
    frozen = spec()
    return runner.FrozenInputs(frozen, {}, None, None, "a" * 40, "local-run",
        "knowledge-read", "online-old", "online-old-uuid", "1" * 64,
        "2" * 64, ("map-v1", "map-v1"))


def _attest(directory: Path, jar: Path, *, artifact_hash: str) -> None:
    runner._write_once(directory / "comparison-java-attestation.json", {
        "schemaVersion": 1, "runId": "local-run", "frozenHead": "a" * 40,
        "archiveSha256": "3" * 64, "mavenExecutableSha256": "4" * 64,
        "command": ["mvn", "--offline", "--batch-mode", "-f",
                    "serviceCenter/pom.xml", "-pl", ":es-query-service", "-am",
                    "-DskipTests", "package"],
        "artifactSha256": artifact_hash,
        "artifactBytes": jar.stat().st_size, "buildExitCode": 0,
        "workingTreeTrackedClean": True,
        "runtimeConfigSha256": {name: sha256((name + " frozen\n").encode()).hexdigest()
                                for name in runner._RUNTIME_CONFIG_FILES},
    })


def _fake_frozen_jar(directory: Path, monkeypatch) -> Path:
    jar = directory / "es-query-service/target/es-query-service-0.0.1-SNAPSHOT.jar"
    jar.parent.mkdir(parents=True)
    jar.write_bytes(b"fake-frozen-jar")
    config_dir = directory / runner._RUNTIME_CONFIG_ROOT
    config_dir.mkdir(parents=True)
    for name in runner._RUNTIME_CONFIG_FILES:
        (config_dir / name).write_bytes((name + " frozen\n").encode())
    monkeypatch.setattr(runner, "_git_bytes", lambda _action, reference:
        (reference.rsplit("/", 1)[-1] + " frozen\n").encode())
    return jar


def test_plan_round_trip_and_bad_frozen_item_rejected() -> None:
    original = spec().cases[0].plan
    assert runner._plan(plan_payload(original)) == original
    changed = plan_payload(original)
    changed["items"][0]["queryText"] = "altered"
    with pytest.raises(runner.BLocalRunError, match="plan_invalid"):
        runner._plan(changed)


def test_arbitrary_jar_matching_caller_hash_is_not_admitted(tmp_path: Path, monkeypatch) -> None:
    jar = tmp_path / "arbitrary.jar"
    jar.write_bytes(b"not-built-from-frozen-head")
    _attest(tmp_path, jar, artifact_hash="f" * 64)
    monkeypatch.setattr(runner.shutil, "which", lambda _name: "java")
    with pytest.raises(runner.BLocalRunError, match="java_artifact_invalid"):
        asyncio.run(runner.execute_local_comparison(directory=tmp_path,
            inputs=_inputs(), jar=jar, jar_sha256=sha256(jar.read_bytes()).hexdigest(),
            ports=(19211, 19212), proxy_ports=(19311, 19312)))
    assert not (tmp_path / "comparison-attempt.json").exists()


def test_unexpected_failure_after_consumption_keeps_finite_terminal(tmp_path: Path, monkeypatch) -> None:
    jar = _fake_frozen_jar(tmp_path, monkeypatch)
    digest = sha256(jar.read_bytes()).hexdigest()
    _attest(tmp_path, jar, artifact_hash=digest)
    monkeypatch.setattr(runner.shutil, "which", lambda _name: "java")
    monkeypatch.setattr(runner, "_port_guard", lambda _ports: None)
    events: list[str] = []
    monkeypatch.setattr(runner, "_capture_model_identity",
                        lambda _inputs: events.append("model") or {"sha256": "model-fake"})

    class ExplodingLease:
        metadata_calls = 0
        alias_writes = 0

        def __init__(self, **_kwargs: object) -> None:
            pass

        def open(self) -> None:
            events.append("lease")
            raise RuntimeError("do-not-persist-raw-error-or-secret")

        def close(self) -> bool:
            return True

    monkeypatch.setattr(runner, "BIsolatedAliases", ExplodingLease)
    terminal = asyncio.run(runner.execute_local_comparison(directory=tmp_path,
        inputs=_inputs(), jar=jar, jar_sha256=digest,
        ports=(19211, 19212), proxy_ports=(19311, 19312)))
    assert terminal["status"] == "not_assessed"
    assert terminal["reason"] == "local_unexpected_failure"
    assert terminal["calls"] == {"typed_search": 0, "query_embedding": 0, "online_rerank": 0}
    assert (tmp_path / "comparison-attempt.json").is_file()
    assert (tmp_path / "comparison-result.json").is_file()
    assert not (tmp_path / "comparison-blind-label-pool.json").exists()
    assert b"do-not-persist" not in (tmp_path / "comparison-result.json").read_bytes()
    assert events == ["model", "lease"]


def _fake_completed_comparison(tmp_path: Path, monkeypatch, *, mismatch: bool = True):
    """Owned-process and proxy fakes; every possible HTTP request is denied."""
    jar = _fake_frozen_jar(tmp_path, monkeypatch)
    digest = sha256(jar.read_bytes()).hexdigest()
    _attest(tmp_path, jar, artifact_hash=digest)
    result, *_ = asyncio.run(execute())
    result = replace(result, evidence_kind="local_pending_postflight")
    snapshots = (("baseline", "1" * 64), ("candidate", "2" * 64))

    class FakeLease:
        metadata_calls = 8
        alias_writes = 4

        def __init__(self, **_kwargs):
            pass

        def open(self):
            return snapshots

        def postcheck(self):
            return snapshots

        def close(self):
            return True

    class FakeProxy:
        def __init__(self, *, identity, **_kwargs):
            empty = sha256(b"").hexdigest()
            canonical = ("d" if mismatch and identity.arm == "candidate" else "c") * 64
            raw = ("a" if identity.arm == "baseline" else "b") * 64
            self.requests = [RequestWitness("GET", f"/{identity.index_name}/_mapping",
                empty, empty, 200) for _ in range(6)] + [RequestWitness("POST",
                f"/{identity.index_name}/_search", raw, canonical, 200) for _ in range(22)]
            self.metadata_count = self.metadata_attempts = 6
            self.violations = 0

        @property
        def physical_search_paths(self):
            return tuple(item.path for item in self.requests if item.method == "POST")

        def start(self):
            pass

        def close(self):
            pass

    class FakeProcess:
        next_pid = 5000

        def __init__(self, *_args, **_kwargs):
            self.pid = FakeProcess.next_pid
            FakeProcess.next_pid += 1
            self.returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = 0

        def wait(self, **_kwargs):
            return self.returncode

    async def fake_comparison(**_kwargs):
        return result

    def deny_http(_request):
        pytest.fail("real HTTP request from a synthetic comparison")

    original_client = httpx.Client
    monkeypatch.setattr(runner.httpx, "Client", lambda **kwargs: original_client(
        **kwargs, transport=httpx.MockTransport(deny_http)))
    monkeypatch.setattr(runner, "build_knowledge_http_client", lambda url: httpx.AsyncClient(
        base_url=url, transport=httpx.MockTransport(deny_http)))
    monkeypatch.setattr(runner.shutil, "which", lambda _name: "java")
    monkeypatch.setattr(runner, "_port_guard", lambda _ports: None)
    monkeypatch.setattr(runner, "_ready", lambda _processes, _ports: None)
    monkeypatch.setattr(runner, "_capture_model_identity", lambda _inputs: {"sha256": "5" * 64})
    monkeypatch.setattr(runner, "BIsolatedAliases", FakeLease)
    monkeypatch.setattr(runner, "PhysicalEsProxy", FakeProxy)
    monkeypatch.setattr(runner.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(runner, "run_comparison", fake_comparison)
    return {"directory": tmp_path, "inputs": _inputs(), "jar": jar,
            "jar_sha256": digest, "ports": (19211, 19212), "proxy_ports": (19311, 19312)}


def test_postflight_failure_preserves_only_unadmitted_safe_diagnostics(tmp_path: Path, monkeypatch):
    args = _fake_completed_comparison(tmp_path, monkeypatch)
    terminal = asyncio.run(runner.execute_local_comparison(**args))
    assert terminal["status"] == "not_assessed"
    assert terminal["reason"] == "runtime_provenance_missing"
    assert terminal["evidenceKind"] == "local_unadmitted_diagnostic"
    assert terminal["phase"] == "postflight"
    assert terminal["postflightDiagnostic"] == "canonical_requests_mismatch"
    assert terminal["calls"] == {"typed_search": 44, "query_embedding": 10, "online_rerank": 22}
    assert terminal["receipt"]["arm_search_canonical_request_sha256"][1][1] == ("d" * 64,) * 22
    assert terminal["witness"]["candidate"][-1]["canonical_request_sha256"] == "d" * 64
    assert "traces" not in terminal
    assert not (tmp_path / "comparison-blind-label-pool.json").exists()
    saved = (tmp_path / "comparison-result.json").read_bytes()
    assert json.loads(saved)["receipt"] is not None
    assert b"original_question" not in saved and b"user_token" not in saved
    assert b"request_body" not in saved and b"COMMON_SECURITY_JWT" not in saved


def test_consumed_final_jar_hash_failure_still_persists_terminal(tmp_path: Path, monkeypatch):
    args = _fake_completed_comparison(tmp_path, monkeypatch, mismatch=False)
    original = runner._hash_file
    calls = 0

    def fail_final_hash(path):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise runner.BLocalRunError("java_artifact_missing")
        return original(path)

    monkeypatch.setattr(runner, "_hash_file", fail_final_hash)
    terminal = asyncio.run(runner.execute_local_comparison(**args))
    assert calls == 2
    assert terminal["status"] == "not_assessed"
    assert terminal["reason"] == "java_artifact_missing"
    assert terminal["phase"] == "artifact_postcheck"
    assert terminal["calls"]["typed_search"] == 44
    assert terminal["receipt"] is None
    assert len(terminal["witness"]["baseline"]) == 28
    assert (tmp_path / "comparison-attempt.json").is_file()
    assert (tmp_path / "comparison-result.json").is_file()
    assert not (tmp_path / "comparison-blind-label-pool.json").exists()
    assert "traces" not in terminal


@pytest.mark.parametrize("error_type", (OSError, ValueError))
def test_consumed_es_client_creation_failure_keeps_zero_call_terminal(
        tmp_path: Path, monkeypatch, error_type):
    args = _fake_completed_comparison(tmp_path, monkeypatch)

    def fail_client(**_kwargs):
        raise error_type("external-client-body-or-secret")

    monkeypatch.setattr(runner.httpx, "Client", fail_client)
    monkeypatch.setattr(runner, "_capture_model_identity",
                        lambda _inputs: pytest.fail("model identity reached after client failure"))
    terminal = asyncio.run(runner.execute_local_comparison(**args))
    assert terminal["status"] == "not_assessed"
    assert terminal["reason"] == "es_client_open_failed"
    assert terminal["phase"] == "es_client_open"
    assert terminal["calls"] == {"typed_search": 0, "query_embedding": 0, "online_rerank": 0}
    assert terminal["metadataEsHttp"] == terminal["aliasWrites"] == 0
    assert terminal["witness"] == {"baseline": None, "candidate": None}
    assert terminal["receipt"] is None
    assert (tmp_path / "comparison-attempt.json").is_file()
    assert (tmp_path / "comparison-result.json").is_file()
    assert not (tmp_path / "comparison-blind-label-pool.json").exists()
    assert "traces" not in terminal
    assert b"external-client-body-or-secret" not in (tmp_path / "comparison-result.json").read_bytes()


@pytest.mark.parametrize("before_comparison", (True, False))
def test_consumed_es_client_close_failure_keeps_finite_terminal(
        tmp_path: Path, monkeypatch, before_comparison):
    args = _fake_completed_comparison(tmp_path, monkeypatch, mismatch=False)

    class FailingCloseClient:
        def __enter__(self):
            pytest.fail("ES client must use the explicit finite lifecycle")

        def close(self):
            raise OSError("external-client-body-or-secret")

    monkeypatch.setattr(runner.httpx, "Client", lambda **_kwargs: FailingCloseClient())
    if before_comparison:
        def fail_identity(_inputs):
            raise runner.BLocalRunError("model_snapshot_invalid")
        monkeypatch.setattr(runner, "_capture_model_identity", fail_identity)
    terminal = asyncio.run(runner.execute_local_comparison(**args))
    assert terminal["status"] == "not_assessed"
    assert terminal["reason"] == "es_client_close_failed"
    assert terminal["phase"] == "es_client_close"
    assert terminal["calls"] == ({"typed_search": 0, "query_embedding": 0, "online_rerank": 0}
        if before_comparison else {"typed_search": 44, "query_embedding": 10, "online_rerank": 22})
    assert terminal["ownedProcessesStopped"] is True
    assert terminal["aliasesRemoved"] is (not before_comparison)
    assert terminal["receipt"] is None
    assert (tmp_path / "comparison-attempt.json").is_file()
    assert (tmp_path / "comparison-result.json").is_file()
    assert not (tmp_path / "comparison-blind-label-pool.json").exists()
    assert "traces" not in terminal
    assert b"external-client-body-or-secret" not in (tmp_path / "comparison-result.json").read_bytes()


def test_consumed_terminal_write_failure_is_explicit_not_preflight(tmp_path: Path, monkeypatch):
    args = _fake_completed_comparison(tmp_path, monkeypatch)
    original = runner._write_once

    def fail_terminal(path, value):
        if path.name == "comparison-result.json":
            raise runner.BLocalRunError("append_only_evidence_failed")
        original(path, value)

    monkeypatch.setattr(runner, "_write_once", fail_terminal)
    with pytest.raises(runner.BLocalEvidenceError, match="append_only_evidence_failed") as caught:
        asyncio.run(runner.execute_local_comparison(**args))
    assert caught.value.run_id == "local-run"
    assert caught.value.calls.typed_search == 44
    assert caught.value.phase == "terminal_write"
    assert (tmp_path / "comparison-attempt.json").is_file()
    assert not (tmp_path / "comparison-result.json").exists()
    assert not (tmp_path / "comparison-blind-label-pool.json").exists()


def test_cli_consumed_evidence_failure_prints_only_finite_state(tmp_path: Path, monkeypatch, capsys):
    @contextmanager
    def artifact(*_args):
        yield tmp_path / "fake.jar", "a" * 64

    async def fail_evidence(**_kwargs):
        raise runner.BLocalEvidenceError(run_id="local-run", calls=runner.CallTotals(44, 10, 22),
                                        phase="terminal_write")

    monkeypatch.setattr(runner.sys, "argv", ["rebuild-b", "--execute-once",
        "--run-directory", str(tmp_path), "--baseline-port", "19211", "--candidate-port", "19212",
        "--baseline-proxy-port", "19311", "--candidate-proxy-port", "19312"])
    monkeypatch.setattr(runner, "_require_locked_python_environment", lambda _role: None)
    monkeypatch.setattr(runner, "load_frozen_inputs", lambda _directory: _inputs())
    monkeypatch.setattr(runner, "frozen_java_artifact", artifact)
    monkeypatch.setattr(runner, "execute_local_comparison", fail_evidence)
    assert runner.main() == 1
    captured = capsys.readouterr()
    value = json.loads(captured.out)
    assert value == {"status": "evidence_failed", "runId": "local-run",
        "reason": "append_only_evidence_failed", "consumed": True, "phase": "terminal_write",
        "calls": {"typed_search": 44, "query_embedding": 10, "online_rerank": 22},
        "paid": 0, "retry": 0, "resume": 0}
    assert captured.err == ""
    assert "preflight_failed" not in captured.out


def test_model_identity_binds_old_embedding_and_fresh_rerank_without_inference(
        monkeypatch) -> None:
    old = runner.reuse.load_old_build()
    binding = json.loads(dict(old.blobs)["binding.json"])["spec"]
    prior = binding["model_snapshot"]
    rerank_id = "f" * 64
    new = {"schemaVersion": 1, "embedding": prior,
           "rerank": {"container": {"id": rerank_id}, "model": {"revision": "fixed"}}}
    new["sha256"] = sha256(runner._canonical({
        "embedding": new["embedding"], "rerank": new["rerank"]})).hexdigest()
    monkeypatch.setattr(runner, "_rerank_container_id", lambda: rerank_id)
    seen: list[dict[str, str]] = []

    def fake_worker(command: list[str], *, payload: bytes, corpus_python: bool) -> bytes:
        assert command[-2:] == ["-m", "knowledge_corpus_tools.b_model_identity_v1"]
        assert corpus_python is True
        seen.append(json.loads(payload))
        return runner._canonical(new)

    monkeypatch.setattr(runner, "_bounded_model_process", fake_worker)
    inputs = replace(_inputs(), sidecars={"reuseIntent": b"new-run"})
    assert runner._capture_model_identity(inputs) == new
    assert seen == [{"embeddingContainerId": prior["container"]["id"],
                     "rerankContainerId": rerank_id,
                     "expectedEmbeddingModelSha256": sha256(
                         runner._canonical(prior["model"])).hexdigest()}]
    changed = json.loads(runner._canonical(new))
    changed["embedding"]["container"]["id"] = "e" * 64
    changed["sha256"] = sha256(runner._canonical({
        "embedding": changed["embedding"], "rerank": changed["rerank"]})).hexdigest()
    monkeypatch.setattr(runner, "_bounded_model_process", lambda *_args, **_kwargs:
                        runner._canonical(changed))
    with pytest.raises(runner.BLocalRunError, match="model_identity_invalid"):
        runner._capture_model_identity(inputs)


def test_model_worker_subprocess_drops_ambient_credentials(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "must-not-inherit")

    def fake_run(_command: list[str], **kwargs: object) -> SimpleNamespace:
        assert "LLM_API_KEY" not in kwargs["env"]
        kwargs["stdout"].write(b'{"limited":true}\n')
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner._bounded_model_process(["fake"], corpus_python=True) == b'{"limited":true}\n'


def test_frozen_head_archive_build_attests_its_own_jar(tmp_path: Path, monkeypatch) -> None:
    payload = BytesIO()
    with ZipFile(payload, "w") as archive:
        archive.writestr("serviceCenter/mvnw.cmd", "@echo off\r\n")
        archive.writestr("serviceCenter/pom.xml", "<project/>\n")
        for name in runner._RUNTIME_CONFIG_FILES:
            archive.writestr(f"{runner._RUNTIME_CONFIG_ROOT}/{name}",
                             (name + " frozen\n").encode())
    monkeypatch.setattr(runner, "_git", lambda *args: "a" * 40 if args[0] == "rev-parse" else "")
    monkeypatch.setattr(runner, "_git_bytes", lambda action, *args: (
        payload.getvalue() if action == "archive" else
        (args[0].rsplit("/", 1)[-1] + " frozen\n").encode()))
    maven = tmp_path / "mvn.cmd"
    maven.write_bytes(b"@echo off\r\n")
    monkeypatch.setattr(runner.shutil, "which", lambda _name: str(maven))
    monkeypatch.setenv("MAVEN_OPTS", "-Duntrusted.extension=ignored")

    def fake_build(_command: list[str], *, cwd: Path, **_kwargs: object) -> SimpleNamespace:
        assert "MAVEN_OPTS" not in _kwargs["env"]
        output = cwd.parent / "es-query-service/target/es-query-service-0.0.1-SNAPSHOT.jar"
        output.parent.mkdir(parents=True)
        output.write_bytes(b"jar-from-archive")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner.subprocess, "run", fake_build)
    with runner.frozen_java_artifact(tmp_path, _inputs()) as (jar, digest):
        assert jar.read_bytes() == b"jar-from-archive"
        assert digest == sha256(b"jar-from-archive").hexdigest()
        attestation = json.loads((tmp_path / "comparison-java-attestation.json").read_bytes())
        assert attestation["artifactSha256"] == digest
        assert attestation["frozenHead"] == "a" * 40
        assert attestation["workingTreeTrackedClean"] is True
        assert attestation["runtimeConfigSha256"] == {
            name: sha256((name + " frozen\n").encode()).hexdigest()
            for name in runner._RUNTIME_CONFIG_FILES}


def test_frozen_build_rejects_missing_runtime_config_before_maven_or_alias(
        tmp_path: Path, monkeypatch) -> None:
    payload = BytesIO()
    with ZipFile(payload, "w") as archive:
        archive.writestr("serviceCenter/pom.xml", "<project/>\n")
    monkeypatch.setattr(runner, "_git", lambda *args: "a" * 40 if args[0] == "rev-parse" else "")
    monkeypatch.setattr(runner, "_git_bytes", lambda action, *args: (
        payload.getvalue() if action == "archive" else b"frozen config\n"))
    maven = tmp_path / "mvn.cmd"
    maven.write_bytes(b"@echo off\r\n")
    monkeypatch.setattr(runner.shutil, "which", lambda _name: str(maven))
    monkeypatch.setattr(runner.subprocess, "run", lambda *_args, **_kwargs:
        pytest.fail("Maven or alias operation reached"))
    with pytest.raises(runner.BLocalRunError, match="frozen_runtime_config_invalid"):
        with runner.frozen_java_artifact(tmp_path, _inputs()):
            pytest.fail("Java yielded without frozen config")
    assert not (tmp_path / "comparison-java-attestation.json").exists()
    assert not (tmp_path / "comparison-attempt.json").exists()


def test_frozen_config_drift_rejected_before_alias_operation(tmp_path: Path, monkeypatch) -> None:
    jar = _fake_frozen_jar(tmp_path, monkeypatch)
    digest = sha256(jar.read_bytes()).hexdigest()
    _attest(tmp_path, jar, artifact_hash=digest)
    (tmp_path / runner._RUNTIME_CONFIG_ROOT / "application-es.yml").write_bytes(b"drifted\n")
    monkeypatch.setattr(runner.shutil, "which", lambda _name: "java")
    monkeypatch.setattr(runner, "_port_guard", lambda _ports: pytest.fail("port guard reached"))
    monkeypatch.setattr(runner, "BIsolatedAliases", lambda **_kwargs:
        pytest.fail("alias operation reached"))
    with pytest.raises(runner.BLocalRunError, match="frozen_runtime_config_invalid"):
        asyncio.run(runner.execute_local_comparison(directory=tmp_path,
            inputs=_inputs(), jar=jar, jar_sha256=digest,
            ports=(19211, 19212), proxy_ports=(19311, 19312)))
    assert not (tmp_path / "comparison-attempt.json").exists()


def test_runtime_config_blob_changes_profile_hash(monkeypatch) -> None:
    files = {name: (name + " frozen\n").encode()
             for name in (*runner._RUNTIME_CONFIG_FILES, "application-knowledge-live.yml")}
    monkeypatch.setattr(runner, "_git_bytes", lambda _action, reference:
        files[reference.rsplit("/", 1)[-1]])
    before = runner._expected_profile_config_sha256("a" * 40, "tax.policy")
    files["application-datasource.yml"] = b"different datasource\n"
    assert runner._expected_profile_config_sha256("a" * 40, "tax.policy") != before


def test_both_java_arms_use_one_frozen_config_and_keep_fixed_cli_guards(tmp_path: Path) -> None:
    config_dir = tmp_path / "frozen config"
    identity = runner.ArmIdentity("baseline", "physical-index", "index-uuid",
                                  "1" * 64, "mapping-v1", "b-owned-baseline-0123456789abcdef-read")
    candidate = runner.ArmIdentity("candidate", "candidate-index", "candidate-uuid",
                                   "2" * 64, "mapping-v2", "b-owned-candidate-0123456789abcdef-read")
    args = [runner._java_args(jar=Path("frozen.jar"), config_dir=config_dir,
        port=port, proxy_port=proxy, identity=arm, run_id="frozen-run",
        policy_snapshot="policy-snapshot", law_snapshot="law-snapshot")
        for arm, port, proxy in ((identity, 19211, 19311), (candidate, 19212, 19312))]
    config_option = "--spring.config.additional-location=" + config_dir.as_uri().rstrip("/") + "/"
    for arm_args in args:
        assert arm_args.count(config_option) == 1
        assert "--management.endpoint.health.probes.enabled=true" in arm_args
        assert "--management.endpoint.health.group.knowledge-validation.include=readinessState" in arm_args
        assert "--spring.cloud.config.enabled=false" in arm_args
        assert "--es.query.knowledge.b-isolation-fixed-target=true" in arm_args
        assert "--common.security.secrets.allow-config-values=false" in arm_args
        assert "--common.security.secrets.jwt.keys.ACTIVE.value=" in arm_args
    assert "--spring.elasticsearch.uris=http://127.0.0.1:19311" in args[0]
    assert "--spring.elasticsearch.uris=http://127.0.0.1:19312" in args[1]
    assert "--es.query.knowledge.profiles.tax-policy-v1.expected-index-name=physical-index" in args[0]
    assert "--es.query.knowledge.profiles.tax-policy-v1.expected-index-name=candidate-index" in args[1]


def test_readiness_uses_b_only_group_and_still_requires_owned_pid(monkeypatch) -> None:
    paths: list[str] = []
    original_client = httpx.Client

    def respond(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200)

    monkeypatch.setattr(runner.httpx, "Client", lambda **kwargs: original_client(
        **kwargs, transport=httpx.MockTransport(respond)))
    owned_ports: list[int] = []

    def owner(port: int) -> int:
        owned_ports.append(port)
        return {19211: 11, 19212: 12}[port]

    monkeypatch.setattr(runner, "_listener_owner", owner)
    processes = [SimpleNamespace(pid=11, poll=lambda: None),
                 SimpleNamespace(pid=12, poll=lambda: None)]
    runner._ready(processes, (19211, 19212))
    assert paths == ["/actuator/health/knowledge-validation"] * 2
    assert owned_ports == [19211, 19212]


def test_foreign_java_listener_is_rejected_before_jwt_search(monkeypatch) -> None:
    calls: list[str] = []

    class FakeSearch:
        async def search(self, **_kwargs: object) -> None:
            calls.append("sent")

    class FakeProcess:
        pid = 3456

        def poll(self) -> None:
            return None

    monkeypatch.setattr(runner, "_listener_owner", lambda _port: 9999)
    owned = runner._OwnedSearch(FakeSearch(), FakeProcess(), 19211)
    with pytest.raises(runner.BLocalRunError, match="listener_owner_mismatch"):
        asyncio.run(owned.search(request=None, context=None, timeout_s=1.0))
    assert calls == []


def test_foreign_java_listener_rejects_whole_case_before_embedding(monkeypatch) -> None:
    class FakeProcess:
        pid = 3456

        def poll(self) -> None:
            return None

    monkeypatch.setattr(runner, "_listener_owner", lambda _port: 9999)
    with pytest.raises(runner.BLocalRunError, match="listener_owner_mismatch"):
        runner._require_owned_listeners([FakeProcess(), FakeProcess()], (19211, 19212))


def test_native_listener_owner_matches_one_loopback_socket() -> None:
    if os.name != "nt":
        pytest.skip("Windows owner table only")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        assert runner._listener_owner(listener.getsockname()[1]) == os.getpid()


def _prepare_fixture(tmp_path: Path, monkeypatch, *, budget: int = 30) -> Path:
    directory = tmp_path / "knowledge-b-fake-run"
    directory.mkdir()
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_bytes(b"manifest fixture\n")
    monkeypatch.setattr(runner, "_PREPARATION_MANIFEST", manifest)
    monkeypatch.setattr(runner, "_git", lambda *args: (
        "codex_0915" if args[0] == "branch" else
        "a" * 40 if args[0] == "rev-parse" else ""))
    monkeypatch.setattr(runner, "_git_bytes", lambda *_args: (
        runner.ROOT / "agent-runtime/tests/uat/knowledge_rebuild_measure.v1.json").read_bytes())
    parameters = {domain: {
        "profileId": profile_id,
        "profileVersion": runner._PROFILE_VERSION,
        "readPolicyVersion": runner._READ_POLICY_VERSION,
        "baselineMappingVersion": "baseline-map-v1",
        "candidateMappingVersion": "candidate-map-v1",
        "configSha256": runner._expected_profile_config_sha256("a" * 40, domain),
    } for domain, profile_id in runner._PROFILE_IDS.items()}
    runner._write_once(directory / "preparation.json", {
        "runId": directory.name, "frozenHead": "a" * 40,
        "comparisonMetadataEsHttp": budget, "profileParameters": parameters,
        "candidate": {"source_index": "source-index", "read_alias": "source-read"},
    })
    runner._write_once(directory / "selection.json", {"selection": "fake"})
    return directory


def test_profile_hash_binds_frozen_yaml_and_java_launch_overrides(monkeypatch) -> None:
    config = b"profile: frozen\n"
    monkeypatch.setattr(runner, "_git_bytes", lambda *_args: config)
    first = runner._expected_profile_config_sha256("a" * 40, "tax.policy")
    assert len(first) == 64
    monkeypatch.setattr(runner, "_git_bytes", lambda *_args: b"profile: changed\n")
    assert runner._expected_profile_config_sha256("a" * 40, "tax.policy") != first
    monkeypatch.setattr(runner, "_git_bytes", lambda *_args: config)
    original = runner._java_args
    monkeypatch.setattr(runner, "_java_args", lambda **kwargs: [*original(**kwargs),
        "--es.query.knowledge.profiles.tax-policy-v1.some-override=true"])
    assert runner._expected_profile_config_sha256("a" * 40, "tax.policy") != first


def test_profile_hash_mismatch_rejected_before_source_es(tmp_path: Path, monkeypatch) -> None:
    directory = _prepare_fixture(tmp_path, monkeypatch)
    preparation = json.loads((directory / "preparation.json").read_bytes())
    preparation["profileParameters"]["tax.policy"]["configSha256"] = "8" * 64
    (directory / "preparation.json").write_bytes(runner._canonical(preparation))
    with httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False,
            transport=httpx.MockTransport(lambda _request: pytest.fail("ES called"))) as client:
        with pytest.raises(runner.BLocalRunError, match="profile_config_drift"):
            runner.prepare_local_b_inputs(directory, client=client, observed_calls=lambda: 0,
                preparer=lambda **_kwargs: pytest.fail("preparer called"),
                git_state_factory=lambda head: head)
    assert not (directory / "comparison-preparation-attempt.json").exists()


def test_python_dependency_guard_rejects_wrong_runtime_lock(monkeypatch) -> None:
    original = runner.metadata.version
    monkeypatch.setattr(runner.metadata, "version", lambda name:
        "0.6.11" if name == "langgraph" else original(name))
    with pytest.raises(runner.BLocalRunError, match="python_environment_invalid"):
        runner._require_locked_python_environment("comparison")


def test_launcher_uses_distinct_locked_venvs_and_is_frozen_source() -> None:
    script = "agent-runtime/scripts/run-knowledge-b-comparison-v1.ps1"
    assert script in runner._EXECUTION_SOURCES
    body = (runner.ROOT / script).read_text(encoding="utf-8")
    assert "$pythonProject = if ($ExecuteOnce -or $StartupPreflightOnly -or $PrepareReuse) { 'agent-runtime' } else { 'knowledge-corpus-tools' }" in body
    assert "--startup-preflight-only" in body
    assert "knowledge-corpus-tools\\.venv\\Scripts\\python.exe" not in body


def test_prepare_entry_writes_append_only_limited_evidence(tmp_path: Path, monkeypatch) -> None:
    directory = _prepare_fixture(tmp_path, monkeypatch)
    calls = 0

    def fake_prepare(**kwargs: object) -> SimpleNamespace:
        nonlocal calls
        assert kwargs["git_state"] == "a" * 40
        calls = 7
        return SimpleNamespace(scoped_es_http=7, scoped_es_http_max=7,
            intent_raw=runner._canonical({"kind": "fake-intent"}),
            preliminary_raw=runner._canonical({"kind": "fake-preliminary"}))

    with httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False,
            transport=httpx.MockTransport(lambda _request: httpx.Response(500))) as client:
        result = runner.prepare_local_b_inputs(directory, client=client,
            observed_calls=lambda: calls, preparer=fake_prepare,
            git_state_factory=lambda head: head)
        assert result["status"] == "prepared"
        assert result["sourceEsHttp"] == 7
        assert (directory / "assessment-intent.json").read_bytes() == runner._canonical({"kind": "fake-intent"})
        assert (directory / "preliminary-request.json").read_bytes() == runner._canonical({"kind": "fake-preliminary"})
        with pytest.raises(runner.BLocalRunError, match="preparation_preflight_invalid"):
            runner.prepare_local_b_inputs(directory, client=client, observed_calls=lambda: calls,
                preparer=fake_prepare, git_state_factory=lambda head: head)


def test_prepare_rejects_budget_before_source_es(tmp_path: Path, monkeypatch) -> None:
    directory = _prepare_fixture(tmp_path, monkeypatch, budget=29)
    with httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False,
            transport=httpx.MockTransport(lambda _request: httpx.Response(500))) as client:
        with pytest.raises(runner.BLocalRunError, match="preparation_preflight_invalid"):
            runner.prepare_local_b_inputs(directory, client=client, observed_calls=lambda: 0,
                preparer=lambda **_kwargs: None, git_state_factory=lambda head: head)
    assert not (directory / "comparison-preparation-attempt.json").exists()


def test_prepare_error_after_attempt_is_finite(tmp_path: Path, monkeypatch) -> None:
    directory = _prepare_fixture(tmp_path, monkeypatch)

    def fake_prepare(**_kwargs: object) -> None:
        raise RuntimeError("raw-response-and-secret-must-not-persist")

    with httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False,
            transport=httpx.MockTransport(lambda _request: httpx.Response(500))) as client:
        result = runner.prepare_local_b_inputs(directory, client=client,
            observed_calls=lambda: 1, preparer=fake_prepare,
            git_state_factory=lambda head: head)
    assert result["status"] == "not_prepared"
    assert result["reason"] == "preparation_unexpected_failure"
    assert b"raw-response-and-secret" not in (directory / "comparison-preparation-result.json").read_bytes()


def test_prepare_transport_rejects_other_es_paths_without_network() -> None:
    transport = runner._PreparationTransport(index="source-index", alias="source-read")
    try:
        with pytest.raises(runner.BLocalRunError, match="preparation_scope_invalid"):
            transport.handle_request(httpx.Request("POST", "http://127.0.0.1:9200/_aliases"))
        assert transport.calls == 0
    finally:
        transport.close()


def test_source_mapping_binding_uses_frozen_map_without_network(tmp_path: Path, monkeypatch) -> None:
    directory = tmp_path / "knowledge-b-fake-run"
    directory.mkdir()
    intent = runner._canonical({"kind": "intent"})
    preliminary = runner._canonical({"runId": directory.name, "frozenHead": "a" * 40,
                                     "assessmentIntentSha256": sha256(intent).hexdigest()})
    source_map = runner._canonical({"kind": "full-source-map"})
    (directory / "assessment-intent.json").write_bytes(intent)
    (directory / "preliminary-request.json").write_bytes(preliminary)
    (directory / "source-id-mapping.json").write_bytes(source_map)
    runner._write_once(directory / "comparison-preparation-result.json", {
        "runId": directory.name, "status": "prepared", "sourceEsHttp": 7,
        "preliminaryRequestSha256": sha256(preliminary).hexdigest(),
        "assessmentIntentSha256": sha256(intent).hexdigest(),
    })
    monkeypatch.setattr(runner, "_git", lambda *args: (
        "codex_0915" if args[0] == "branch" else "a" * 40 if args[0] == "rev-parse" else ""))
    bound = runner._canonical({"kind": "request", "idMappingSha256": sha256(source_map).hexdigest()})

    def fake_binder(*, preliminary_raw: bytes, source_id_mapping_raw: bytes) -> bytes:
        assert preliminary_raw == preliminary
        assert source_id_mapping_raw == source_map
        return bound

    result = runner.bind_local_b_request(directory, binder=fake_binder)
    assert result["status"] == "source_bound"
    assert result["requestSha256"] == sha256(bound).hexdigest()
    assert (directory / "request.json").read_bytes() == bound
    with pytest.raises(runner.BLocalRunError, match="source_binding_preflight_invalid"):
        runner.bind_local_b_request(directory, binder=fake_binder)


def test_source_mapping_binding_refuses_unprepared_run(tmp_path: Path, monkeypatch) -> None:
    directory = tmp_path / "knowledge-b-fake-run"
    directory.mkdir()
    (directory / "assessment-intent.json").write_bytes(runner._canonical({"kind": "intent"}))
    (directory / "preliminary-request.json").write_bytes(runner._canonical({"kind": "preliminary"}))
    (directory / "source-id-mapping.json").write_bytes(runner._canonical({"kind": "map"}))
    runner._write_once(directory / "comparison-preparation-result.json", {
        "runId": directory.name, "status": "not_prepared", "sourceEsHttp": 1,
    })
    monkeypatch.setattr(runner, "_git", lambda *args: (
        "codex_0915" if args[0] == "branch" else "a" * 40 if args[0] == "rev-parse" else ""))
    with pytest.raises(runner.BLocalRunError, match="source_binding_preflight_invalid"):
        runner.bind_local_b_request(directory, binder=lambda **_kwargs: b"{}\n")
    assert not (directory / "request.json").exists()


def _startup_inputs(tmp_path: Path, monkeypatch) -> tuple[Path, runner.StartupInputs]:
    directory = tmp_path / "knowledge-b-startup-fake-01"
    directory.mkdir()
    monkeypatch.setattr(runner, "_STARTUP_EVIDENCE_ROOT", tmp_path)
    original_git = runner._git
    monkeypatch.setattr(runner, "_git", lambda *args:
        "" if args[0] == "status" else original_git(*args))
    return directory, runner.prepare_startup_inputs(directory)


def test_startup_input_binds_old_git_bundle_and_current_head_without_es(
        tmp_path: Path, monkeypatch) -> None:
    directory, inputs = _startup_inputs(tmp_path, monkeypatch)
    value = json.loads((directory / "startup-input.json").read_bytes())
    assert value["runId"] == directory.name
    assert value["frozenHead"] == runner._git("rev-parse", "HEAD")
    assert value["sourceBundleCommit"] == runner._STARTUP_SOURCE_COMMIT
    assert set(value["sourceBundleSha256"]) == set(runner._STARTUP_SOURCE_FILES)
    assert value["budget"] == runner._STARTUP_BUDGET
    assert inputs.input_sha256 == sha256((directory / "startup-input.json").read_bytes()).hexdigest()
    assert {identity.arm for identity in inputs.identities} == {"baseline", "candidate"}
    assert not any(path.name.startswith("comparison-") for path in directory.iterdir())
    with pytest.raises(runner.BLocalRunError, match="startup_preflight_invalid"):
        runner.prepare_startup_inputs(directory)


def test_startup_rejects_synthetic_old_attempt_before_any_es(
        tmp_path: Path, monkeypatch) -> None:
    directory = tmp_path / "knowledge-b-startup-fake-02"
    directory.mkdir()
    monkeypatch.setattr(runner, "_STARTUP_EVIDENCE_ROOT", tmp_path)
    original_git = runner._git
    original_git_bytes = runner._git_bytes
    monkeypatch.setattr(runner, "_git", lambda *args:
        "" if args[0] == "status" else original_git(*args))
    original_attempt = original_git_bytes("show", f"{runner._STARTUP_SOURCE_COMMIT}:"
        f"{runner._STARTUP_SOURCE_PATH}/attempt.json")
    altered = json.loads(original_attempt)
    altered["executionKind"] = "synthetic"
    tampered = runner._canonical(altered)
    monkeypatch.setattr(runner, "_git_bytes", lambda *args:
        tampered if args[0] == "show" and args[1].endswith("/attempt.json")
        else original_git_bytes(*args))
    with pytest.raises(runner.BLocalRunError, match="startup_source_invalid"):
        runner.prepare_startup_inputs(directory)
    assert list(directory.iterdir()) == []


@pytest.mark.parametrize("failure", ("none", "readiness", "forbidden_search"))
def test_startup_fake_lifecycle_has_no_search_jwt_or_model(
        tmp_path: Path, monkeypatch, failure: str) -> None:
    directory, inputs = _startup_inputs(tmp_path, monkeypatch)
    jar = tmp_path / "es-query-service-0.0.1-SNAPSHOT.jar"
    jar.write_bytes(b"synthetic java artifact")
    artifact_hash = sha256(jar.read_bytes()).hexdigest()
    runtime_hashes = {name: "5" * 64 for name in runner._RUNTIME_CONFIG_FILES}
    runner._write_once(directory / "startup-java-attestation.json", {
        "schemaVersion": 1, "runId": inputs.run_id, "frozenHead": inputs.frozen_head,
        "archiveSha256": "3" * 64, "mavenExecutableSha256": "4" * 64,
        "command": ["mvn", "--offline", "--batch-mode", "-f", "serviceCenter/pom.xml",
                    "-pl", ":es-query-service", "-am", "-DskipTests", "package"],
        "artifactSha256": artifact_hash, "artifactBytes": jar.stat().st_size,
        "buildExitCode": 0, "workingTreeTrackedClean": True,
        "runtimeConfigSha256": runtime_hashes,
    })
    monkeypatch.setattr(runner, "_frozen_runtime_config_hashes", lambda _head: runtime_hashes)
    monkeypatch.setattr(runner, "_frozen_runtime_config_dir",
        lambda _jar, _head: (tmp_path, runtime_hashes))
    monkeypatch.setattr(runner, "_port_guard", lambda _ports: None)
    monkeypatch.setattr(runner, "_require_owned_listeners", lambda _processes, _ports: None)
    monkeypatch.setattr(runner, "_jwt", lambda _secret: pytest.fail("JWT generated"))

    class FakeLease:
        def __init__(self, **kwargs: object) -> None:
            assert kwargs["metadata_budget"] == 18
            self.metadata_calls = 0
            self.alias_writes = 0

        def open(self) -> tuple[tuple[str, str], ...]:
            self.metadata_calls += 8
            self.alias_writes += 2
            return (("baseline", "a" * 64), ("candidate", "b" * 64))

        def postcheck(self) -> tuple[tuple[str, str], ...]:
            self.metadata_calls += 6
            return (("baseline", "a" * 64), ("candidate", "b" * 64))

        def close(self) -> bool:
            self.metadata_calls += 4
            self.alias_writes += 2
            return True

    class FakeProxy:
        def __init__(self, **kwargs: object) -> None:
            assert kwargs["maximum_metadata"] == 6
            assert kwargs["maximum_search"] == 0
            self.metadata_count = 6
            self.metadata_attempts = 6
            self.violations = 1 if failure == "forbidden_search" else 0
            self.physical_search_paths: tuple[str, ...] = ()

        def start(self) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeProcess:
        next_pid = 5000

        def __init__(self, _args: object, **kwargs: object) -> None:
            assert "COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE" in kwargs["env"]
            assert "LLM_API_KEY" not in kwargs["env"]
            self.pid = FakeProcess.next_pid
            FakeProcess.next_pid += 1
            self.returncode: int | None = None

        def poll(self) -> int | None:
            return self.returncode

        def terminate(self) -> None:
            self.returncode = 0

        def wait(self, **_kwargs: object) -> int:
            assert self.returncode is not None
            return self.returncode

    monkeypatch.setattr(runner, "BIsolatedAliases", FakeLease)
    monkeypatch.setattr(runner, "PhysicalEsProxy", FakeProxy)
    monkeypatch.setattr(runner.subprocess, "Popen", FakeProcess)
    def fake_ready(_processes: object, _ports: object, calls: list[int]) -> None:
        calls[:] = [1, 1]
        if failure == "readiness":
            raise runner.BLocalRunError("java_readiness_timeout")

    monkeypatch.setattr(runner, "_ready", fake_ready)
    with httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False,
            follow_redirects=False,
            transport=httpx.MockTransport(lambda _request: pytest.fail("ES called"))) as es:
        result = runner.execute_startup_preflight(directory=directory, inputs=inputs,
            jar=jar, jar_sha256=artifact_hash, ports=(19211, 19212),
            proxy_ports=(19311, 19312), es=es)
    assert result["status"] == ("ready" if failure == "none" else "not_ready")
    assert result["metadataEsHttp"] == (30 if failure == "none" else 24)
    assert result["aliasWrites"] == 4
    assert result["physicalSearchCount"] == 0
    assert result["paid"] == result["typedSearch"] == result["jwtHttp"] == 0
    assert result["ownedProcessesStopped"] is True
    assert result["aliasesRemoved"] is True
    assert result["reason"] == {"none": None, "readiness": "java_readiness_timeout",
                                "forbidden_search": "proxy_operation_forbidden"}[failure]
    assert not any(path.name.startswith("comparison-") for path in directory.iterdir())


def test_startup_source_failure_writes_finite_once_only_terminal_without_es(
        tmp_path: Path, monkeypatch) -> None:
    directory = tmp_path / "knowledge-b-startup-fake-03"
    directory.mkdir()
    monkeypatch.setattr(runner, "_STARTUP_EVIDENCE_ROOT", tmp_path)
    monkeypatch.setattr(runner, "_port_guard", lambda _ports: None)
    monkeypatch.setattr(runner, "prepare_startup_inputs",
        lambda _directory: (_ for _ in ()).throw(runner.BLocalRunError("startup_source_invalid")))
    monkeypatch.setattr(runner, "frozen_java_artifact",
        lambda *_args, **_kwargs: pytest.fail("Java build reached"))
    result = runner.run_startup_preflight(directory, ports=(19211, 19212),
        proxy_ports=(19311, 19312))
    assert result["status"] == "not_ready"
    assert result["reason"] == "startup_source_invalid"
    assert result["metadataEsHttp"] == result["aliasWrites"] == 0
    assert json.loads((directory / "startup-result.json").read_bytes()) == result
    with pytest.raises(runner.BLocalRunError, match="startup_preflight_invalid"):
        runner.run_startup_preflight(directory, ports=(19211, 19212),
            proxy_ports=(19311, 19312))
