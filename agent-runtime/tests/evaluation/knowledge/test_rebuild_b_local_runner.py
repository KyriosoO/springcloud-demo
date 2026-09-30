"""No real Java, ES, BGE or model calls for the one-shot B launcher."""
from __future__ import annotations

import asyncio
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
from tests.evaluation.knowledge.test_rebuild_b_comparator import plan_payload, spec


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
    })


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
    jar = tmp_path / "frozen.jar"
    jar.write_bytes(b"fake-frozen-jar")
    digest = sha256(jar.read_bytes()).hexdigest()
    _attest(tmp_path, jar, artifact_hash=digest)
    monkeypatch.setattr(runner.shutil, "which", lambda _name: "java")
    monkeypatch.setattr(runner, "_port_guard", lambda _ports: None)

    class ExplodingLease:
        metadata_calls = 0
        alias_writes = 0

        def __init__(self, **_kwargs: object) -> None:
            pass

        def open(self) -> None:
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


def test_frozen_head_archive_build_attests_its_own_jar(tmp_path: Path, monkeypatch) -> None:
    payload = BytesIO()
    with ZipFile(payload, "w") as archive:
        archive.writestr("serviceCenter/mvnw.cmd", "@echo off\r\n")
        archive.writestr("serviceCenter/pom.xml", "<project/>\n")
    monkeypatch.setattr(runner, "_git", lambda *args: "a" * 40 if args[0] == "rev-parse" else "")
    monkeypatch.setattr(runner, "_git_bytes", lambda *_args: payload.getvalue())
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
    assert "$pythonProject = if ($ExecuteOnce) { 'agent-runtime' } else { 'knowledge-corpus-tools' }" in body
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
