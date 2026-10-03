"""Zero-outbound counterexamples for the one-shot Spring measurement harness."""

from __future__ import annotations

import asyncio
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from threading import Thread
import time
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest

from agent_runtime.model.contracts import (
    ModelTaskId, StructuredFinishKind, StructuredModelRequest, StructuredModelResponse,
    StructuredModelTransport, StructuredOutputMode, StructuredToolMode,
)
from agent_runtime.model.settings import ModelApiKey, ModelProvider, ModelSettings
from agent_runtime.knowledge.contracts import RetrievalStageKind, RetrievalStageResult
from agent_runtime.knowledge.intent_contracts import (
    KnowledgeIntentOutcome, KnowledgeQueryIntent, KnowledgeQueryIntentInput, KnowledgeQueryMode,
)
from agent_runtime.knowledge.minimal_plan import MinimalKnowledgePlanBuilder, MinimalRetrievalSettings
from agent_runtime.knowledge.retrieval.http import BoundedHttpRequest, BoundedHttpResponse
from agent_runtime.bootstrap import LocalModelCompositionRoot
from agent_runtime.main import build_runtime
from tests.uat import knowledge_rebuild_measure_prepare as prepare
from tests.uat import knowledge_rebuild_measure_runner as runner
from tests.uat import knowledge_rebuild_measure_startup as startup


_HEAD = "a" * 40
_RUN = "knowledge-rebuild-measure-test-01"


def _write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def test_model_consumption_precedes_fake_send_and_retry_is_forbidden(tmp_path: Path) -> None:
    output = tmp_path / _RUN
    manifest = {"runId": _RUN, "frozenHead": _HEAD, "authorizationReference": "UAT_02:MEASURE-TEST"}
    ledger = runner.OneShotLedger(output_dir=output, manifest=manifest, manifest_sha256="b" * 64)
    sends = 0

    class FakeModel:
        async def complete(self, request: StructuredModelRequest, *, call_deadline: float) -> StructuredModelResponse:
            nonlocal sends
            assert (output / "authorization.consumed.json").is_file()
            assert (output / "attempts.jsonl").is_file()
            sends += 1
            return StructuredModelResponse(finish_kind=StructuredFinishKind.STOP, content="{}",
                                           tool_calls=(), usage_total_tokens=0)

    ledger.begin("case-1", "公共税务问题")
    ledger.claim_runtime(correlation_id="case-1", question="公共税务问题")
    guarded = ledger.model(FakeModel())
    request = StructuredModelRequest(task_id=ModelTaskId.ACTION_SELECTION,
        task_version="action-selection-v4", system_instruction="test", user_payload_json="{}",
        tools=(), tool_mode=StructuredToolMode.NONE, output_mode=StructuredOutputMode.JSON_OBJECT,
        max_output_tokens=8)
    asyncio.run(guarded.complete(request, call_deadline=1.0))
    with pytest.raises(runner.MeasurementError, match="task_forbidden_or_retry"):
        asyncio.run(guarded.complete(request, call_deadline=1.0))
    assert sends == 1
    assert ledger.total["model"] == 1
    assert (output / "authorization.consumed.json").read_text(encoding="utf-8").count("\n") == 1


def test_forbidden_model_task_and_wrong_spring_runtime_scope_make_zero_sends(tmp_path: Path) -> None:
    output = tmp_path / _RUN
    ledger = runner.OneShotLedger(output_dir=output,
        manifest={"runId": _RUN, "frozenHead": _HEAD, "authorizationReference": "UAT_02:MEASURE-TEST"},
        manifest_sha256="b" * 64)

    class FakeModel:
        async def complete(self, request: StructuredModelRequest, *, call_deadline: float) -> StructuredModelResponse:
            pytest.fail("forbidden task reached outbound")

    ledger.begin("case-1", "公共税务问题")
    with pytest.raises(runner.MeasurementError, match="runtime_scope_mismatch"):
        ledger.claim_runtime(correlation_id="other-case", question="公共税务问题")
    request = StructuredModelRequest(task_id=ModelTaskId.BUSINESS_QUERY_PLAN,
        task_version="7", system_instruction="test", user_payload_json="{}",
        tools=(), tool_mode=StructuredToolMode.NONE, output_mode=StructuredOutputMode.JSON_OBJECT,
        max_output_tokens=8)
    with pytest.raises(runner.MeasurementError, match="task_binding_drift"):
        asyncio.run(ledger.model(FakeModel()).complete(request, call_deadline=1.0))
    assert ledger.total["model"] == 0
    assert not (output / "authorization.consumed.json").exists()


def test_typed_and_bge_budget_reserve_before_fake_send(tmp_path: Path) -> None:
    output = tmp_path / _RUN
    ledger = runner.OneShotLedger(output_dir=output,
        manifest={"runId": _RUN, "frozenHead": _HEAD, "authorizationReference": "UAT_02:MEASURE-TEST"},
        manifest_sha256="b" * 64)
    calls = 0

    class FakeTransport:
        async def send(self, *, request: BoundedHttpRequest, timeout_s: float) -> BoundedHttpResponse:
            nonlocal calls
            assert ledger.total["embedding"] == calls + 1
            calls += 1
            return BoundedHttpResponse(status_code=200, content_type="application/json",
                                       content_encoding=None, body=b"{}")

    ledger.begin("case-1", "公共税务问题")
    request = BoundedHttpRequest(method="POST", relative_path="/embed", headers=(), body=b"{}",
                                 max_response_bytes=1024)
    asyncio.run(ledger.transport("embedding", FakeTransport()).send(request=request, timeout_s=1.0))
    with pytest.raises(runner.MeasurementError, match="budget_exhausted"):
        asyncio.run(ledger.transport("embedding", FakeTransport()).send(request=request, timeout_s=1.0))
    assert calls == 1


def test_zero_hit_retrieval_still_records_actual_mode_and_planned_domains(tmp_path: Path) -> None:
    ledger = runner.OneShotLedger(output_dir=tmp_path / _RUN,
        manifest={"runId": _RUN, "frozenHead": _HEAD, "authorizationReference": "UAT_02:MEASURE-TEST"},
        manifest_sha256="b" * 64)
    intent = KnowledgeQueryIntent(query_mode=KnowledgeQueryMode.LOOKUP,
        selected_domain_ids=("tax.policy",), missing_conditions=(), outcome=KnowledgeIntentOutcome.SEARCH)
    plan = MinimalKnowledgePlanBuilder().build(
        question=KnowledgeQueryIntentInput(minimized_question="增值税政策是什么"),
        intent=intent, settings=MinimalRetrievalSettings())
    calls = 0

    class FakeRetrieval:
        async def execute(self, *, plan: object, context: object, timeout_s: float) -> RetrievalStageResult[object]:
            nonlocal calls
            calls += 1
            return RetrievalStageResult(kind=RetrievalStageKind.NO_RESULT)

    ledger.begin("case-1", "增值税政策是什么")
    result = asyncio.run(ledger.retrieval(FakeRetrieval()).execute(
        plan=plan, context=SimpleNamespace(correlation_id="case-1"), timeout_s=1.0))
    assert result.kind is RetrievalStageKind.NO_RESULT
    assert calls == 1 and ledger.ranked == []
    assert ledger.planned_query_mode == "lookup"
    assert ledger.planned_domains == ["tax.policy"]
    assert runner._plan_comparison(expected_mode="lookup", expected_domains=["tax.policy"],
        observed_mode=ledger.planned_query_mode, observed_domains=ledger.planned_domains) == {
            "queryModeDiffers": False, "selectedDomainsDiffer": False}
    with pytest.raises(runner.MeasurementError, match="retrieval_plan_invalid_or_repeated"):
        asyncio.run(ledger.retrieval(FakeRetrieval()).execute(
            plan=plan, context=SimpleNamespace(correlation_id="case-1"), timeout_s=1.0))
    assert calls == 1


def test_expected_clarification_without_plan_is_not_misreported_as_domain_drift() -> None:
    assert runner._plan_comparison(expected_mode="applicability", expected_domains=[],
        observed_mode=None, observed_domains=None) == {
            "queryModeDiffers": None, "selectedDomainsDiffer": False}
    assert runner._plan_comparison(expected_mode="lookup", expected_domains=["tax.policy"],
        observed_mode=None, observed_domains=None) == {
            "queryModeDiffers": None, "selectedDomainsDiffer": True}


def test_run_assets_reject_directory_symlink_outside_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    asset_parent = root / "agent-runtime/tests/uat"
    resolve = Path.resolve

    def redirected_resolve(path: Path, strict: bool = False) -> Path:
        if path == asset_parent:
            return tmp_path / "outside"
        return resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", redirected_resolve)
    with pytest.raises(runner.MeasurementError, match="run_path_invalid"):
        runner._run_directories(root, _RUN)


def test_public_review_rejects_credentials_before_any_file_write(tmp_path: Path) -> None:
    review_path = tmp_path / "public-review.jsonl"
    with pytest.raises(runner.MeasurementError, match="sensitive_public_review"):
        runner._checked_public_review_size({"answer": "secret-for-test"}, secrets=("secret-for-test",))
    with pytest.raises(runner.MeasurementError, match="sensitive_public_review"):
        runner._checked_public_review_size({"answer": "Bearer eyJ.test.payload"}, secrets=())
    assert not review_path.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows owned-listener contract")
def test_spring_post_rejects_changed_owned_pid_before_sending_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    sends = 0

    class FakeClient:
        async def post(self, *args: object, **kwargs: object) -> httpx.Response:
            nonlocal sends
            sends += 1
            pytest.fail("JWT reached an unowned Spring listener")

    rows = [{"LocalPort": 19201, "OwningProcess": 11},
            {"LocalPort": 19202, "OwningProcess": 999}]
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: json.dumps(rows))
    with pytest.raises(runner.MeasurementError, match="owned_port_mismatch"):
        asyncio.run(runner._post_spring_owned(client=cast(httpx.AsyncClient, FakeClient()),
            question="增值税政策是什么", case_id="UAT-KM-001", token="jwt-test-only", es_pid=11, agent_pid=22))
    assert sends == 0


def test_alias_check_rejects_uuid_drift_without_search(tmp_path: Path) -> None:
    del tmp_path
    index, alias = "test-index", "test-read"
    mapping = {"_meta": {"mapping_version": "v1"}}
    mapping_sha = _hash((json.dumps(mapping, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")) + "\n").encode())
    manifest = {"aliasFlags": {}, "indexBindings": {"tax.policy": {
        "readAlias": alias, "indexName": index, "indexUuid": "wanted", "mappingVersion": "v1",
        "mappingSha256": mapping_sha}}}
    paths: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == f"/_alias/{alias}":
            return httpx.Response(200, json={index: {"aliases": {alias: {}}}})
        if request.url.path == f"/{index}":
            return httpx.Response(200, json={index: {"settings": {"index": {
                "uuid": "wrong", "blocks": {"write": "true"}}}, "mappings": mapping}})
        pytest.fail("unexpected query or external request")

    async def check() -> None:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:19313",
                                     transport=httpx.MockTransport(handle)) as client:
            await runner._alias_check(manifest, client)

    with pytest.raises(runner.MeasurementError, match="index_metadata_drift"):
        asyncio.run(check())
    assert paths == [f"/_alias/{alias}", f"/{index}"]


@pytest.mark.skipif(os.name != "nt", reason="Windows owned-listener contract")
def test_alias_check_rejects_unowned_proxy_before_any_get(monkeypatch: pytest.MonkeyPatch) -> None:
    sends = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal sends
        sends += 1
        pytest.fail(f"unowned proxy reached {request.url.path}")

    rows = [{"LocalPort": 19201, "OwningProcess": 11},
            {"LocalPort": 19202, "OwningProcess": 22},
            {"LocalPort": 19313, "OwningProcess": 999}]
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: json.dumps(rows))

    async def check() -> None:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:19313",
                                     transport=httpx.MockTransport(handle)) as client:
            await runner._alias_check({}, client, es_pid=11, agent_pid=22, proxy_pid=33)

    with pytest.raises(runner.MeasurementError, match="owned_port_mismatch"):
        asyncio.run(check())
    assert sends == 0


def test_freeze_generator_and_static_preflight_reject_secret_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    run_dir = root / "agent-runtime/tests/uat" / _RUN
    output_dir = root / "agent-runtime/tests/uat/results" / _RUN
    run_dir.mkdir(parents=True)
    dataset = Path(__file__).with_name("knowledge_rebuild_measure.v1.json").read_bytes()
    _write(root / prepare._DATASET, dataset)
    for path in (*prepare._ASSETS, *prepare._JARS.values(), *runner._DEPENDENCY_JARS):
        if path != prepare._DATASET:
            _write(root / path, ("fixed:" + path).encode())
    config = "config-service/src/main/resources/config/application.yml"
    _write(root / config, b"fixture: config\n")
    attestation = {"schemaVersion": 1, "status": "built_from_clean_head", "branch": "codex_0915",
                   "head": _HEAD,
                   "jarSha256": {path: runner._sha(root / path) for path in prepare._JARS.values()},
                   "dependencyJarSha256": {path: runner._sha(root / path)
                                            for path in runner._DEPENDENCY_JARS},
                   "commands": runner._BUILD_COMMANDS}
    runner._exclusive_json(run_dir / "build-attestation.json", attestation)

    def fake_git(args: list[str], **kwargs: object) -> str:
        del kwargs
        if args[3:] == ["rev-parse", "HEAD"]:
            return _HEAD + "\n"
        if args[3:] == ["branch", "--show-current"]:
            return "codex_0915\n"
        if args[3:] == ["status", "--porcelain", "--untracked-files=all"]:
            files = [run_dir / "build-attestation.json"]
            files.extend(path for path in (run_dir / "manifest.json", run_dir / "authorization.json") if path.exists())
            if output_dir.exists():
                files.extend(path for path in output_dir.iterdir() if path.is_file())
            return "".join("?? " + item.relative_to(root).as_posix() + "\n" for item in files)
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "check_output", fake_git)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0))
    source = json.loads(dataset)["sourceCorpus"]
    binding = {key: value for key, value in {
        "readAlias": source["readAlias"], "indexName": source["index"], "indexUuid": source["indexUuid"],
        "mappingVersion": "v1", "mappingSha256": source["mappingSha256"],
        "fullFingerprint": source["fullFingerprint"], "recordCount": source["recordCount"],
        "snapshotId": "a" * 64, "readPolicyVersion": "tax-public-authenticated-v1"}.items()}
    monkeypatch.setattr(prepare, "_binding", lambda root, dataset: ({
        "tax.policy": dict(binding), "tax.law": dict(binding)}, {}))
    prepare.freeze(root=root, run_dir=run_dir, run_id=_RUN,
                   authorization_reference="UAT_02:MEASURE-TEST")
    assert json.loads((run_dir / "manifest.json").read_bytes())["assetSha256"][config] == runner._sha(root / config)
    assert output_dir.parent.is_dir()
    assert not output_dir.exists()
    output_dir.parent.rmdir()
    env = dict(prepare._ENV)
    with pytest.raises(runner.MeasurementError, match="result_parent_missing"):
        runner.frozen_preflight(root=root, manifest_path=run_dir / "manifest.json",
            authorization_path=run_dir / "authorization.json", output_dir=output_dir, environ=env)
    prepare._prepare_result_parent(root)
    manifest, _, _ = runner.frozen_preflight(root=root,
        manifest_path=run_dir / "manifest.json", authorization_path=run_dir / "authorization.json",
        output_dir=output_dir, environ=env)
    assert manifest["answerDesign"] == "Summary9"
    assert manifest["subject"] == {"userId": "viewer_t", "role": "VIEWER"}
    assert manifest["jarBuildHead"] == _HEAD
    assert manifest["runtimeMetadataEsHttpMax"] == 72
    assert set(manifest["promptSha256"]) == {"action_selection", "knowledge_rewrite", "knowledge_summary"}
    manifest_path = run_dir / "manifest.json"
    original_manifest = manifest_path.read_bytes()
    outdated_manifest = json.loads(original_manifest)
    outdated_manifest["runtimeMetadataEsHttpMax"] = 48
    manifest_path.write_text(json.dumps(outdated_manifest), encoding="utf-8")
    with pytest.raises(runner.MeasurementError, match="manifest_binding_invalid"):
        runner.frozen_preflight(root=root, manifest_path=manifest_path,
            authorization_path=run_dir / "authorization.json", output_dir=output_dir, environ=env)
    manifest_path.write_bytes(original_manifest)
    dependency_path = root / sorted(runner._DEPENDENCY_JARS)[0]
    dependency_bytes = dependency_path.read_bytes()
    dependency_path.unlink()
    with pytest.raises(runner.MeasurementError, match="asset_missing"):
        runner.frozen_preflight(root=root, manifest_path=run_dir / "manifest.json",
            authorization_path=run_dir / "authorization.json",
            output_dir=output_dir, environ=env)
    _write(dependency_path, dependency_bytes)
    misplaced_output = root / "agent-runtime/tests/uat/other-results" / _RUN
    with pytest.raises(runner.MeasurementError, match="run_path_invalid"):
        runner.frozen_preflight(root=root, manifest_path=run_dir / "manifest.json",
            authorization_path=run_dir / "authorization.json",
            output_dir=misplaced_output, environ=env)
    assert not misplaced_output.exists()
    env["AGENT_KNOWLEDGE_ADMIN_JWT"] = "should-not-enter-manifest"
    with pytest.raises(runner.MeasurementError, match="runtime_configuration_drift"):
        runner.frozen_preflight(root=root, manifest_path=run_dir / "manifest.json",
            authorization_path=run_dir / "authorization.json",
            output_dir=output_dir, environ=env)
    assert "should-not-enter-manifest" not in (run_dir / "manifest.json").read_text(encoding="utf-8")
    env.pop("AGENT_KNOWLEDGE_ADMIN_JWT")
    output_dir.mkdir(parents=True)
    runner._exclusive_json(output_dir / "measurement.json", {
        "authorizationSha256": runner._sha(run_dir / "authorization.json")})
    runner.frozen_postflight(root=root, manifest_path=run_dir / "manifest.json",
        authorization_path=run_dir / "authorization.json", output_dir=output_dir, environ=env)
    with pytest.raises(runner.MeasurementError, match="postflight_run_missing"):
        runner.frozen_postflight(root=root, manifest_path=run_dir / "manifest.json",
            authorization_path=run_dir / "authorization.json", output_dir=run_dir, environ=env)
    with (run_dir / "authorization.json").open("ab") as stream:
        stream.write(b" ")
    with pytest.raises(runner.MeasurementError, match="authorization_drift"):
        runner.frozen_postflight(root=root, manifest_path=run_dir / "manifest.json",
            authorization_path=run_dir / "authorization.json", output_dir=output_dir, environ=env)


def test_model_wrapper_failure_closes_managed_client(monkeypatch: pytest.MonkeyPatch) -> None:
    from agent_runtime import bootstrap

    class FakeClient:
        closed = False

        async def aclose(self) -> None:
            self.closed = True

    client = FakeClient()
    monkeypatch.setattr(bootstrap, "build_deepseek_http_client", lambda settings: client)
    monkeypatch.setattr(bootstrap, "DeepSeekChatTransport", lambda **kwargs: object())

    async def exercise() -> None:
        with pytest.raises(ValueError, match="broken measurement wrapper"):
            LocalModelCompositionRoot.build(
                settings=ModelSettings(provider=ModelProvider.DEEPSEEK, api_key=ModelApiKey("test-only")),
                transport_wrapper=lambda delegate: (_ for _ in ()).throw(ValueError("broken measurement wrapper")),
                grounding_policies={},
            )
        await asyncio.sleep(0)
        assert client.closed

    asyncio.run(exercise())


def test_knowledge_wrapper_failure_closes_three_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    from agent_runtime import main

    clients: list[httpx.AsyncClient] = []

    def factory(origin: str) -> httpx.AsyncClient:
        client = httpx.AsyncClient(base_url=origin,
                                   transport=httpx.MockTransport(lambda request: pytest.fail("outbound")))
        clients.append(client)
        return client

    async def exercise() -> None:
        with pytest.raises(ValueError, match="broken knowledge wrapper"):
            build_runtime({
                "AGENT_MODEL_PROVIDER": "stub",
                "AGENT_KNOWLEDGE_ENABLED": "true",
                "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,tax.law",
                "AGENT_KNOWLEDGE_ES_BASE_URL": "http://127.0.0.1:19201",
            }, model_transport=cast(StructuredModelTransport, SimpleNamespace(complete=lambda *a, **k: None)),
                knowledge_http_client_factory=factory,
                knowledge_transport_wrapper=lambda name, transport: (_ for _ in ()).throw(
                    ValueError("broken knowledge wrapper")))
        await asyncio.sleep(0)
        assert len(clients) == 3 and all(client.is_closed for client in clients)

    asyncio.run(exercise())


@pytest.mark.skipif(os.name != "nt" or shutil.which("pwsh") is None, reason="Windows PowerShell launcher")
@pytest.mark.parametrize("invalid", ("traversal", "unsafe_env", "static_failure"))
def test_launcher_refuses_bad_run_without_environment_loss_or_file_escape(
    tmp_path: Path, invalid: str,
) -> None:
    repository = Path(__file__).resolve().parents[3]
    launcher = repository / "agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1"
    manifest_path = tmp_path / "manifest.json"
    authorization_path = tmp_path / "authorization.json"
    manifest = {"schemaVersion": 1, "branch": "codex_0915", "runId": _RUN,
                "model": "deepseek-flash", "springBaseUrl": "http://127.0.0.1:19202",
                "runtimePort": 19203, "budgets": runner._MAX,
                "subject": {"userId": "viewer_t", "role": "VIEWER"},
                "runtimeEnv": dict(prepare._ENV)}
    if invalid == "traversal":
        manifest["runId"] = "../escape"
    if invalid == "unsafe_env":
        cast(dict[str, str], manifest["runtimeEnv"])["AGENT_KNOWLEDGE_ADMIN_JWT"] = "forbidden-test-value"
    encoded = json.dumps(manifest, ensure_ascii=True).encode("utf-8")
    manifest_path.write_bytes(encoded)
    before = _hash(encoded)
    # The fake port inventory only lets static preflight execute; it starts no service.
    script = "\n".join((
        "function Get-NetTCPConnection { param($State,$LocalPort,$ErrorAction) "
        "if ($LocalPort -in @(9200,8908,8909)) { [pscustomobject]@{ OwningProcess=1 } } }",
        "$env:AGENT_KNOWLEDGE_ENABLED='original'; $env:PYTHONPATH='original-path'; "
        "$env:SPRING_APPLICATION_JSON='original-json'; $env:JAVA_TOOL_OPTIONS='original-jvm'; "
        "$env:ES_QUERY_KNOWLEDGE_PROFILE='original-profile'; $env:AUTH_USERS='original-auth'; "
        "$env:COMMON_SECURITY_SECRETS='original-security'",
        f"try {{ & '{launcher}' -RepositoryRoot '{repository}' -ManifestPath '{manifest_path}' "
        f"-AuthorizationPath '{authorization_path}' -ExpectedManifestSha256 '{before}' }} "
        "catch { 'caught:' + $_.Exception.Message }",
        "if ($env:AGENT_KNOWLEDGE_ENABLED -cne 'original' -or $env:PYTHONPATH -cne 'original-path' -or "
        "$env:SPRING_APPLICATION_JSON -cne 'original-json' -or $env:JAVA_TOOL_OPTIONS -cne 'original-jvm' -or "
        "$env:ES_QUERY_KNOWLEDGE_PROFILE -cne 'original-profile' -or $env:AUTH_USERS -cne 'original-auth' -or "
        "$env:COMMON_SECURITY_SECRETS -cne 'original-security') "
        "{ throw 'environment_not_restored' }",
        "'restored'",
    ))
    env = dict(os.environ)
    env["LLM_API_KEY"] = ""
    result = subprocess.run(["pwsh", "-NoProfile", "-Command", script],
                            text=True, capture_output=True, timeout=30, env=env, check=False)
    assert result.returncode == 0, result.stderr
    expected = {"traversal": "run_id_invalid", "unsafe_env": "runtime_env_invalid",
                "static_failure": "static_preflight_failed"}[invalid]
    assert "caught:knowledge.measure." + expected in result.stdout
    assert result.stdout.strip().endswith("restored")
    assert not (tmp_path / "escape").exists()
    assert not (repository / "agent-runtime/tests/uat/results" / _RUN).exists()


def test_launcher_rejects_inherited_java_overrides_and_binds_owned_ports() -> None:
    repository = Path(__file__).resolve().parents[3]
    launcher = (repository / "agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1").read_text(encoding="utf-8")
    assert "AUTH_|ES_QUERY_|SPRING_|EUREKA_|MANAGEMENT_|SERVER_|COMMON_" in launcher
    assert "JAVA_TOOL_OPTIONS', 'JDK_JAVA_OPTIONS', '_JAVA_OPTIONS'" in launcher
    assert "function Wait-Ready" in launcher and "knowledge.measure.port_owner_mismatch" in launcher
    assert "Where-Object { $_.OwningProcess -ne $Process.Id }" in launcher
    assert launcher.count("Wait-OwnedPort 18090 $authProcess") >= 2
    assert "Wait-OwnedPort 19201 $esProcess" in launcher
    assert launcher.count("Wait-OwnedPort 19202 $agentProcess") >= 2
    assert "KNOWLEDGE_MEASURE_OWNED_PROXY_PID = [string]$(if ($ownedPythonChildren.ContainsKey(19313))" in launcher


@pytest.mark.skipif(os.name != "nt" or shutil.which("pwsh") is None, reason="Windows venv redirector")
def test_measure_launcher_attests_venv_listener_child_and_cleans_unlistened_child() -> None:
    repository = Path(__file__).resolve().parents[3]
    launcher = (repository / "agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1").read_text(encoding="utf-8")
    listener_functions = launcher[launcher.index("function Test-ExpectedPythonChild"):
                                  launcher.index("function Wait-Ready")]
    cleanup_functions = launcher[launcher.index("function Add-CleanupIssue"):
                                 launcher.index("try {\n    if (-not $startup)")]
    script = r"""
$ErrorActionPreference='Stop'
$runtimePython='__RUNTIME_PYTHON__'
$pythonBaseExecutable='__BASE_PYTHON__'
$ownedPythonChildren=@{}
$ownedChildCleanupUnknown=$false
$runtimeProcess=$null; $agentProcess=$null; $esProcess=$null; $authProcess=$null
function New-VenvChild {
    $psi=[Diagnostics.ProcessStartInfo]::new()
    $psi.FileName=$runtimePython
    $psi.ArgumentList.Add('-c')
    $psi.ArgumentList.Add('import os,sys,time; print(str(os.getpid())+"|"+sys.prefix,flush=True); time.sleep(15)')
    $psi.UseShellExecute=$false
    $psi.RedirectStandardOutput=$true
    $parent=[Diagnostics.Process]::Start($psi)
    $parts=$parent.StandardOutput.ReadLine().Split('|')
    [pscustomobject]@{ Parent=$parent; ChildPid=[int]$parts[0]; Prefix=$parts[1] }
}
function Get-NetTCPConnection {
    param($State,$LocalPort,$ErrorAction)
    if ($script:ownerPid -gt 0) { [pscustomobject]@{ OwningProcess=$script:ownerPid } }
}
function Get-CimInstance {
    param($ClassName,$Filter,$ErrorAction)
    if ($script:cimFails) { throw 'cim_unavailable' }
    if ($Filter -notmatch '^(ProcessId|ParentProcessId)=') { throw 'unexpected_cim_query' }
    [pscustomobject]@{
        ProcessId=$script:childPid
        ParentProcessId=$(if ($script:wrongParent) { 1 } else { $script:proxyProcess.Id })
        ExecutablePath=$pythonBaseExecutable
        CommandLine=$(if ($script:wrongRole) { 'python -m tests.uat.knowledge_rebuild_measure_startup runtime --test' }
                      else { 'python -m tests.uat.knowledge_rebuild_measure_startup proxy --test' })
        CreationDate=$script:childCreated
    }
}
__LISTENER_FUNCTIONS__
__CLEANUP_FUNCTIONS__
function Assert-Rejected([string]$Label) {
    try { [void](Test-OwnedListener 19313 $script:proxyProcess) }
    catch { if ($_.Exception.Message -ceq 'knowledge.measure.port_owner_mismatch') { return } }
    throw "unexpected_accept:$Label"
}
$first=New-VenvChild
$proxyProcess=$first.Parent
$script:childPid=$first.ChildPid
$actualChild=CimCmdlets\Get-CimInstance Win32_Process -Filter "ProcessId=$script:childPid"
if ($actualChild.ParentProcessId -ne $proxyProcess.Id -or
    -not [IO.Path]::GetFullPath([string]$actualChild.ExecutablePath).Equals(
        $pythonBaseExecutable,[StringComparison]::OrdinalIgnoreCase)) { throw 'redirector_relation_invalid' }
$script:childCreated=$actualChild.CreationDate
$script:ownerPid=$first.ChildPid
try {
    if ($first.Prefix -cne '__VENV_ROOT__') { throw 'venv_prefix_lost' }
    $realChild=Microsoft.PowerShell.Management\Get-Process -Id $first.ChildPid
    if ($realChild.HasExited -or $first.ChildPid -eq $proxyProcess.Id) { throw 'not_redirected' }
    if (-not (Test-OwnedListener 19313 $proxyProcess)) { throw 'valid_child_rejected' }
    if ($ownedPythonChildren[19313].Id -ne $first.ChildPid) { throw 'wrong_listener_pid' }
    $script:childCreated=$actualChild.CreationDate.AddSeconds(-2)
    Assert-Rejected 'reused_pid_creation_time'
    $script:childCreated=$actualChild.CreationDate
    $script:wrongRole=$true; Assert-Rejected 'role'; $script:wrongRole=$false
    $script:wrongParent=$true; Assert-Rejected 'parent'; $script:wrongParent=$false
    $script:ownerPid=$PID; Assert-Rejected 'unrelated'; $script:ownerPid=$first.ChildPid
    if (-not (Test-OwnedListener 19313 $proxyProcess)) { throw 'recheck_failed' }
} finally {
    Stop-OwnedProcesses
}
if (-not (Test-OwnedProcessesStopped)) { throw 'captured_child_not_stopped' }
$ownedPythonChildren=@{}; $ownedChildCleanupUnknown=$false
$second=New-VenvChild
$proxyProcess=$second.Parent
$script:childPid=$second.ChildPid
$script:childCreated=(CimCmdlets\Get-CimInstance Win32_Process -Filter "ProcessId=$script:childPid").CreationDate
$script:ownerPid=0
try {
    Stop-OwnedProcesses
    if (-not (Test-OwnedProcessesStopped)) { throw 'unlistened_child_not_stopped' }
} finally {
    $remaining=Get-Process -Id $second.ChildPid -ErrorAction SilentlyContinue
    if ($remaining) { $remaining.Kill() }
    if (-not $second.Parent.HasExited) { $second.Parent.Kill() }
}
$ownedPythonChildren=@{}; $ownedChildCleanupUnknown=$false
$third=New-VenvChild
$proxyProcess=$third.Parent
$script:childPid=$third.ChildPid
$script:childCreated=(CimCmdlets\Get-CimInstance Win32_Process -Filter "ProcessId=$script:childPid").CreationDate
$script:cimFails=$true
try {
    Stop-OwnedProcesses
    if (Test-OwnedProcessesStopped) { throw 'unknown_child_claimed_clean' }
} finally {
    $script:cimFails=$false
    $remaining=Get-Process -Id $third.ChildPid -ErrorAction SilentlyContinue
    if ($remaining) { $remaining.Kill() }
    if (-not $third.Parent.HasExited) { $third.Parent.Kill() }
}
$ownedPythonChildren=@{}; $ownedChildCleanupUnknown=$false
$fourth=New-VenvChild
$proxyProcess=$fourth.Parent
$script:childPid=$fourth.ChildPid
$script:childCreated=(CimCmdlets\Get-CimInstance Win32_Process -Filter "ProcessId=$script:childPid").CreationDate.AddSeconds(-2)
try {
    Stop-OwnedProcesses
    if (Test-OwnedProcessesStopped -or $ownedPythonChildren.Count -ne 0) {
        throw 'drifted_child_claimed_or_killed'
    }
} finally {
    $remaining=Get-Process -Id $fourth.ChildPid -ErrorAction SilentlyContinue
    if ($remaining) { $remaining.Kill() }
    if (-not $fourth.Parent.HasExited) { $fourth.Parent.Kill() }
}
'attested-and-cleaned'
"""
    venv_root = repository / "agent-runtime/.venv"
    base_executable = ""
    for line in (venv_root / "pyvenv.cfg").read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition("=")
        if separator and name.strip().casefold() == "executable":
            base_executable = value.strip()
            break
    assert base_executable and Path(base_executable).is_file()
    substitutions = {
        "__RUNTIME_PYTHON__": str(venv_root / "Scripts/python.exe").replace("'", "''"),
        "__BASE_PYTHON__": base_executable.replace("'", "''"),
        "__VENV_ROOT__": str(venv_root).replace("'", "''"),
        "__LISTENER_FUNCTIONS__": listener_functions,
        "__CLEANUP_FUNCTIONS__": cleanup_functions,
    }
    for marker, value in substitutions.items():
        script = script.replace(marker, value)
    result = subprocess.run(["pwsh", "-NoProfile", "-Command", script],
                            text=True, capture_output=True, timeout=40, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("attested-and-cleaned")


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell cleanup contract")
def test_formal_cleanup_waits_for_owned_process_and_fails_closed_on_timeout() -> None:
    repository = Path(__file__).resolve().parents[3]
    launcher = (repository / "agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1").read_text(encoding="utf-8")
    cleanup_functions = launcher[launcher.index("function Add-CleanupIssue"):
                                 launcher.index("try {\n    if (-not $startup)")]
    script = r"""
$ErrorActionPreference='Stop'
$ownedPythonChildren=@{}
$ownedChildCleanupUnknown=$false
$runtimeProcess=$null; $esProcess=$null; $authProcess=$null; $proxyProcess=$null
__CLEANUP_FUNCTIONS__
$script:killCalls=0; $script:waitMs=-1
$agentProcess=[pscustomobject]@{ Id=123; HasExited=$false }
$agentProcess | Add-Member -MemberType ScriptMethod -Name Kill -Value { $script:killCalls++ }
$agentProcess | Add-Member -MemberType ScriptMethod -Name WaitForExit -Value {
    param($timeoutMs) $script:waitMs=$timeoutMs; return $false
}
Stop-OwnedProcesses
if ($script:killCalls -ne 1 -or $script:waitMs -ne 5000 -or
    -not $ownedChildCleanupUnknown -or (Test-OwnedProcessesStopped)) {
    throw 'stuck_process_claimed_stopped'
}
$ownedChildCleanupUnknown=$false
$agentProcess=[pscustomobject]@{ Id=124; HasExited=$false }
$agentProcess | Add-Member -MemberType ScriptMethod -Name Kill -Value { $this.HasExited=$true }
$agentProcess | Add-Member -MemberType ScriptMethod -Name WaitForExit -Value {
    param($timeoutMs) $script:waitMs=$timeoutMs; return $true
}
Stop-OwnedProcesses
if ($script:waitMs -ne 5000 -or -not (Test-OwnedProcessesStopped)) {
    throw 'stopped_process_rejected'
}
'bounded-cleanup'
""".replace("__CLEANUP_FUNCTIONS__", cleanup_functions)
    result = subprocess.run(["pwsh", "-NoProfile", "-Command", script],
                            text=True, capture_output=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("bounded-cleanup")


def test_formal_result_and_failure_witness_require_cleanup_outcome() -> None:
    repository = Path(__file__).resolve().parents[3]
    launcher = (repository / "agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1").read_text(encoding="utf-8")
    cleanup_gate = launcher.index("if (-not (Test-OwnedProcessesStopped)) { throw 'knowledge.measure.owned_cleanup_failed' }")
    assert launcher.index("Stop-OwnedProcesses", launcher.index("Copy-Item -LiteralPath $postSnapshotPath")) < cleanup_gate
    assert cleanup_gate < launcher.index("--phase postflight") < launcher.index("'measured_pending_human_rubric'")
    failure_path = launcher[launcher.index("} catch {\n    $launcherFailure"):]
    assert failure_path.index("Stop-OwnedProcesses") < failure_path.index("'es-proxy-witness.json'")
    assert failure_path.count("ownedProcessesStopped = $cleanupStopped") >= 3
    cleanup_functions = launcher[launcher.index("function Add-CleanupIssue"):
                                 launcher.index("try {\n    if (-not $startup)")]
    assert "Stop-Process -Id $process.Id" not in cleanup_functions


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell cleanup diagnostics")
@pytest.mark.parametrize("mode,expected", [
    ("inventory", "child_inventory_failed"),
    ("unexpected", "unexpected_child"),
    ("identity", "child_identity_drift"),
    ("attestation", "child_attestation_failed"),
    ("child_timeout", "child_stop_timeout"),
    ("child_error", "child_stop_failed"),
    ("parent_timeout", "parent_stop_timeout"),
    ("parent_error", "parent_stop_failed"),
])
def test_cleanup_reason_is_finite_and_does_not_relax_guard(mode: str, expected: str) -> None:
    repository = Path(__file__).resolve().parents[3]
    launcher = (repository / "agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1").read_text(encoding="utf-8")
    functions = launcher[launcher.index("function Add-CleanupIssue"):launcher.index("try {\n    if (-not $startup)")]
    functions = launcher[launcher.index("function Get-PythonChildObservation"):launcher.index("function Get-AttestedPythonProcess")] + functions
    program = r"""
$ErrorActionPreference='Stop'
$mode='__MODE__'
$cleanupIssues=@{}; $ownedChildCleanupUnknown=$false; $ownedPythonChildren=@{}
$runtimeProcess=$null; $agentProcess=$null; $esProcess=$null; $authProcess=$null
$created=[DateTime]::Now
$proxyProcess=[pscustomobject]@{Id=123; HasExited=$false}
$proxyProcess | Add-Member -MemberType ScriptMethod -Name Kill -Value {
    if($mode -ceq 'parent_error'){throw 'DO_NOT_PERSIST'}; $this.HasExited=$true
}
$proxyProcess | Add-Member -MemberType ScriptMethod -Name WaitForExit -Value {param($ms) return $mode -cne 'parent_timeout'}
$child=[pscustomobject]@{Id=456; HasExited=$false; StartTime=$created}
$child | Add-Member -MemberType ScriptMethod -Name Kill -Value {
    if($mode -ceq 'child_error'){throw 'DO_NOT_PERSIST'}; $this.HasExited=$true
}
$child | Add-Member -MemberType ScriptMethod -Name WaitForExit -Value {param($ms) return $mode -cne 'child_timeout'}
if($mode -ceq 'identity') {$child.Id=999; $ownedPythonChildren[19313]=$child}
function Get-CimInstance {
    param($ClassName,$Filter,$ErrorAction)
    if($mode -ceq 'inventory'){throw 'DO_NOT_PERSIST'}
    if($mode.StartsWith('parent_')){return}
    [pscustomobject]@{ProcessId=456; CreationDate=$created}
}
function Test-ExpectedPythonChild {return $mode -cne 'unexpected'}
function Get-AttestedPythonProcess {if($mode -ceq 'attestation'){return $null}; return $child}
__FUNCTIONS__
Stop-OwnedProcesses
[ordered]@{stopped=(Test-OwnedProcessesStopped); issues=@(Get-CleanupIssues)} | ConvertTo-Json -Compress
""".replace("__MODE__", mode).replace("__FUNCTIONS__", functions)
    result = subprocess.run(["pwsh", "-NoProfile", "-Command", program], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert "DO_NOT_PERSIST" not in result.stdout
    value = json.loads(result.stdout)
    assert value["stopped"] is False
    assert expected in value["issues"]
    assert set(value["issues"]) <= {expected, "process_still_running"}


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell counter diagnostics")
@pytest.mark.parametrize("live,snapshot,fail_read,source,count", [
    (False, True, False, "last_validated_snapshot", 8),
    (True, True, False, "live_proxy", 9),
    (True, True, True, "last_validated_snapshot", 8),
    (False, False, False, "unavailable", None),
])
def test_failure_proxy_counts_preserve_source(live: bool, snapshot: bool, fail_read: bool, source: str, count: int | None) -> None:
    repository = Path(__file__).resolve().parents[3]
    launcher = (repository / "agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1").read_text(encoding="utf-8")
    functions = launcher[launcher.index("function Get-FailureProxyObservation"):launcher.index("function Get-LocalPassword")]
    program = r"""
$ErrorActionPreference='Stop'
$proxyProcess=[pscustomobject]@{HasExited=__EXITED__}
$lastProxyCounts=__SNAPSHOT__
function Get-ProxyCounts {param([switch]$AllowViolations); if(__FAIL__){throw 'DO_NOT_PERSIST'}; [pscustomobject]@{metadataEsHttp=9}}
__FUNCTIONS__
$value=Get-FailureProxyObservation
$count=$null; if($null -ne $value.Counts){$count=$value.Counts.metadataEsHttp}
[ordered]@{source=$value.Source; count=$count} | ConvertTo-Json -Compress
""".replace("__EXITED__", "$false" if live else "$true").replace(
        "__SNAPSHOT__", "[pscustomobject]@{metadataEsHttp=8}" if snapshot else "$null"
    ).replace("__FAIL__", "$true" if fail_read else "$false").replace("__FUNCTIONS__", functions)
    result = subprocess.run(["pwsh", "-NoProfile", "-Command", program], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"source": source, "count": count}


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell validated counter snapshot")
def test_proxy_snapshot_updates_only_after_validation() -> None:
    repository = Path(__file__).resolve().parents[3]
    launcher = (repository / "agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1").read_text(encoding="utf-8")
    functions = launcher[launcher.index("function Get-ProxyCounts"):launcher.index("function Get-FailureProxyObservation")]
    program = r"""
$ErrorActionPreference='Stop'; $lastProxyCounts=$null
$proxyProcess=[pscustomobject]@{HasExited=$false}
$body='{"metadataEsHttp":3,"searchEsHttp":0,"proxyViolations":0,"healthEsHttp":1,"aliasEsHttp":2,"settingsEsHttp":0,"mappingEsHttp":0,"definitionEsHttp":0}'
function Wait-OwnedPort {return}
function Invoke-WebRequest {[pscustomobject]@{StatusCode=200;RawContentLength=$body.Length;Content=$body}}
__FUNCTIONS__
[void](Get-ProxyCounts)
if($lastProxyCounts.metadataEsHttp -ne 3){throw 'snapshot_missing'}
$body=$body.Replace('"metadataEsHttp":3','"metadataEsHttp":4')
$rejected=$false
try {[void](Get-ProxyCounts)} catch {if($_.Exception.Message -cne 'knowledge.measure.proxy_counts_invalid'){throw}; $rejected=$true}
if(-not $rejected -or $lastProxyCounts.metadataEsHttp -ne 3){throw 'invalid_snapshot_accepted'}
'validated-snapshot-retained'
""".replace("__FUNCTIONS__", functions)
    result = subprocess.run(["pwsh", "-NoProfile", "-Command", program], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "validated-snapshot-retained"


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell finite child identity projection")
@pytest.mark.parametrize("mode,image,reason", [
    ("valid", "python", "no_mismatch_observed"),
    ("parent", "python", "parent_mismatch"),
    ("executable", "console_host", "executable_mismatch"),
    ("command", "python", "command_marker_mismatch"),
    ("creation", "python", "creation_time_mismatch"),
    ("missing", "unknown", "metadata_unavailable"),
    ("other", "other", "executable_mismatch"),
])
def test_child_identity_projection_is_finite(mode: str, image: str, reason: str) -> None:
    repository = Path(__file__).resolve().parents[3]
    launcher = (repository / "agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1").read_text(encoding="utf-8")
    functions = launcher[launcher.index("function Test-ExpectedPythonChild"):launcher.index("function Get-AttestedPythonProcess")]
    program = r"""
$ErrorActionPreference='Stop'
$mode='__MODE__'; $pythonBaseExecutable='C:\Python\python.exe'
$process=[Diagnostics.Process]::GetCurrentProcess()
$info=[pscustomobject]@{Name='python.exe';ParentProcessId=$process.Id;ExecutablePath=$pythonBaseExecutable;CommandLine='-m tests.uat.knowledge_rebuild_measure_startup proxy sensitive-do-not-save';CreationDate=[DateTime]::Now}
switch($mode) {
 'parent' {$info.ParentProcessId=0}
 'executable' {$info.Name='conhost.exe';$info.ExecutablePath='C:\Windows\System32\conhost.exe'}
 'command' {$info.CommandLine='sensitive-do-not-save'}
 'creation' {$info.CreationDate=$process.StartTime.AddSeconds(-2)}
 'missing' {$info=$null}
 'other' {$info.Name='private-process.exe';$info.ExecutablePath='C:\private\private-process.exe'}
}
__FUNCTIONS__
[ordered]@{accepted=(Test-ExpectedPythonChild $info 19313 $process);observation=(Get-PythonChildObservation $info 19313 $process)} | ConvertTo-Json -Compress
""".replace("__MODE__", mode).replace("__FUNCTIONS__", functions)
    result = subprocess.run(["pwsh", "-NoProfile", "-Command", program], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert "sensitive-do-not-save" not in result.stdout
    assert "private-process" not in result.stdout
    value = json.loads(result.stdout)
    assert value["accepted"] is (mode == "valid")
    assert value["observation"] == {"role": "proxy", "imageKind": image, "identityFailure": reason}


def test_launcher_creates_fresh_snapshot_after_owned_services_before_key_read() -> None:
    repository = Path(__file__).resolve().parents[3]
    launcher = (repository / "agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1").read_text(encoding="utf-8")
    static_gate = launcher.index("--phase static")
    login = launcher.index("$userToken = Get-LoginToken")
    snapshot = launcher.index("--output $snapshotPath")
    key_read = launcher.index("GetEnvironmentVariable('LLM_API_KEY'")
    run_phase = launcher.index("--phase run")
    assert static_gate < login < snapshot < key_read < run_phase
    assert launcher.count("--output $snapshotPath") == 1
    assert launcher.index("Wait-Ready 'http://127.0.0.1:19201/actuator/health/knowledge-validation'") < snapshot
    assert launcher.index("Wait-OwnedPort 19202 $agentProcess") < snapshot
    # Do not weaken the age guard to accommodate slow Java startup.
    runner_source = (repository / "agent-runtime/tests/uat/knowledge_rebuild_measure_runner.py").read_text(encoding="utf-8")
    assert "<= 120_000" in runner_source


def test_launcher_limits_health_scope_without_disabling_knowledge_guards() -> None:
    repository = Path(__file__).resolve().parents[3]
    launcher = (repository / "agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1").read_text(encoding="utf-8")
    assert "--management.endpoint.health.group.knowledge-validation.include=readinessState,elasticsearch" in launcher
    assert "--management.endpoint.health.probes.enabled=true" in launcher
    assert "--management.health.elasticsearch.enabled=false" not in launcher
    assert "--management.health.db.enabled=false" not in launcher
    assert "Wait-Ready 'http://127.0.0.1:19201/actuator/health/knowledge-validation' $esProcess" in launcher
    assert "knowledge_rebuild_snapshot_preflight.py" in launcher
    assert "--spring.profiles.active=datasource,es,knowledge-live" in launcher


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell readiness diagnostic")
@pytest.mark.parametrize("responses,owner,expected_error,statuses,health,transport", [
    ([{"code": 503, "body": '{"status":"DOWN","details":"DO_NOT_PERSIST"}'}] * 2,
     True, "knowledge.measure.readiness_timeout", {"503": 2}, {"DOWN": 2}, 0),
    ([{"code": 403, "body": '{"error":"DO_NOT_PERSIST"}'},
      {"transport": True}, {"code": 503, "body": "not-json-DO_NOT_PERSIST"}],
     True, "knowledge.measure.readiness_timeout", {"403": 1, "503": 1}, {"unavailable": 2}, 1),
    ([{"code": 200, "body": '{"status":"UP"}'}],
     True, None, {"200": 1}, {"UP": 1}, 0),
    # Observation does not add a new body-shape readiness gate to the existing HTTP contract.
    ([{"code": 200, "body": "not-json-DO_NOT_PERSIST"}],
     True, None, {"200": 1}, {"unavailable": 1}, 0),
    ([{"code": 200, "body": '{"status":"UP"}'}],
     False, "knowledge.measure.port_owner_mismatch", {"200": 1}, {"UP": 1}, 0),
    ([{"code": 503, "body": '{"status":"UP"}'}],
     True, "knowledge.measure.readiness_timeout", {"503": 1}, {"UP": 1}, 0),
])
def test_readiness_diagnostic_is_bounded_and_preserves_failure_guard(
    responses: list[dict[str, Any]], owner: bool, expected_error: str | None,
    statuses: dict[str, int], health: dict[str, int], transport: int,
) -> None:
    repository = Path(__file__).resolve().parents[3]
    launcher = (repository / "agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1").read_text(encoding="utf-8")
    functions = launcher[launcher.index("function Get-FiniteHealthStatus"):
                         launcher.index("function Wait-OwnedPort")]
    # The current PowerShell process supplies the typed handle; every HTTP/sleep/owner operation is mocked.
    encoded = base64.b64encode(json.dumps(responses).encode()).decode()
    program = (
        "$ErrorActionPreference='Stop'; $script:calls=0; $script:sleeps=0; "
        f"$responses=ConvertFrom-Json ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded}'))); "
        "function Invoke-WebRequest { param($Uri,$Method,$TimeoutSec,[switch]$SkipHttpErrorCheck); "
        "if ($Uri -cne 'http://127.0.0.1:19201/actuator/health/knowledge-validation' -or "
        "$Method -cne 'Get' -or $TimeoutSec -ne 2 -or -not $SkipHttpErrorCheck) { throw 'bad_mock_call' }; "
        "$item=$responses[$script:calls]; $script:calls++; "
        "if ($item.transport) { throw 'DO_NOT_PERSIST' }; "
        "return [pscustomobject]@{StatusCode=$item.code; Content=$item.body} }; "
        f"function Test-OwnedListener {{ return ${str(owner).lower()} }}; "
        "function Start-Sleep { param($Milliseconds); if ($Milliseconds -ne 500) {exit 9}; $script:sleeps++ }; "
        + functions + "; $errorCode=$null; try { "
        "Wait-Ready 'http://127.0.0.1:19201/actuator/health/knowledge-validation' "
        f"([Diagnostics.Process]::GetCurrentProcess()) {len(responses)} "
        "} catch { $errorCode=$_.Exception.Message }; "
        "[ordered]@{errorCode=$errorCode; calls=$script:calls; sleeps=$script:sleeps; "
        "observation=$script:readinessObservation} | ConvertTo-Json -Depth 6 -Compress"
    )
    completed = subprocess.run(["pwsh", "-NoProfile", "-Command", program],
                               capture_output=True, text=True, timeout=20, check=False)
    assert completed.returncode == 0, completed.stderr
    assert "DO_NOT_PERSIST" not in completed.stdout
    value = json.loads(completed.stdout)
    assert value["errorCode"] == expected_error
    assert value["calls"] == len(responses)
    assert value["sleeps"] == (len(responses) if expected_error == "knowledge.measure.readiness_timeout" else 0)
    observation = value["observation"]
    assert set(observation) == {"endpointRole", "maximumAttempts", "attempts", "httpStatusCounts",
                                "healthStatusCounts", "transportFailures", "outcome"}
    assert observation["endpointRole"] == "es"
    assert observation["attempts"] == observation["maximumAttempts"] == len(responses)
    assert observation["httpStatusCounts"] == statuses
    assert observation["healthStatusCounts"] == health
    assert observation["transportFailures"] == transport
    assert observation["outcome"] == ("ready" if expected_error is None else
                                       "port_owner_mismatch" if not owner else "timeout")


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell finite health projection")
@pytest.mark.parametrize("as_bytes", [False, True])
@pytest.mark.parametrize("body,expected", [
    ('{"status":"DOWN","details":{"credential":"DO_NOT_PERSIST"}}', "DOWN"),
    ('{"status":"OUT_OF_SERVICE"}', "OUT_OF_SERVICE"),
    ('{"status":"UNKNOWN"}', "UNKNOWN"),
    ('{"status":"down"}', "unavailable"),
    ('{"status":"DO_NOT_PERSIST"}', "unavailable"),
    ('{"status":200}', "unavailable"),
    ('[{"status":"UP"}]', "unavailable"),
    ('{"status":"UP","details":"' + "中" * 1400 + '"}', "unavailable"),
])
def test_finite_health_projection_never_copies_details(body: str, expected: str, as_bytes: bool) -> None:
    repository = Path(__file__).resolve().parents[3]
    launcher = (repository / "agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1").read_text(encoding="utf-8")
    function = launcher[launcher.index("function Get-FiniteHealthStatus"):
                        launcher.index("function Wait-Ready")]
    encoded = base64.b64encode(body.encode()).decode()
    program = (
        "$ErrorActionPreference='Stop'; " + function
        + f"; $body=[Convert]::FromBase64String('{encoded}'); "
        + ("" if as_bytes else "$body=[Text.Encoding]::UTF8.GetString($body); ")
        + "Get-FiniteHealthStatus ([pscustomobject]@{Content=$body})"
    )
    completed = subprocess.run(["pwsh", "-NoProfile", "-Command", program],
                               capture_output=True, text=True, timeout=20, check=False)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == expected


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell finite health projection")
def test_finite_health_projection_rejects_invalid_utf8_bytes() -> None:
    repository = Path(__file__).resolve().parents[3]
    launcher = (repository / "agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1").read_text(encoding="utf-8")
    function = launcher[launcher.index("function Get-FiniteHealthStatus"):
                        launcher.index("function Wait-Ready")]
    encoded = base64.b64encode(b'{"status":"UP","details":"\xff"}').decode()
    program = (
        "$ErrorActionPreference='Stop'; " + function
        + f"; $body=[Convert]::FromBase64String('{encoded}'); "
        "Get-FiniteHealthStatus ([pscustomobject]@{Content=$body})"
    )
    completed = subprocess.run(["pwsh", "-NoProfile", "-Command", program],
                               capture_output=True, text=True, timeout=20, check=False)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "unavailable"


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell real-shaped Actuator response")
@pytest.mark.parametrize("media_type", ["application/json", "application/vnd.spring-boot.actuator.v3+json"])
def test_finite_health_projection_handles_actuator_http_media_type(media_type: str) -> None:
    repository = Path(__file__).resolve().parents[3]
    launcher = (repository / "agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1").read_text(encoding="utf-8")
    function = launcher[launcher.index("function Get-FiniteHealthStatus"):
                        launcher.index("function Wait-Ready")]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            body = b'{"status":"DOWN","details":"DO_NOT_PERSIST"}'
            self.send_response(503)
            self.send_header("Content-Type", media_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        program = (
            "$ErrorActionPreference='Stop'; " + function
            + f"; $response=Invoke-WebRequest -Uri 'http://127.0.0.1:{server.server_port}/health' "
            "-TimeoutSec 2 -SkipHttpErrorCheck; "
            "[ordered]@{code=$response.StatusCode; status=(Get-FiniteHealthStatus $response)} "
            "| ConvertTo-Json -Compress"
        )
        completed = subprocess.run(["pwsh", "-NoProfile", "-Command", program],
                                   capture_output=True, text=True, timeout=20, check=False)
        assert completed.returncode == 0, completed.stderr
        assert json.loads(completed.stdout) == {"code": 503, "status": "DOWN"}
        assert "DO_NOT_PERSIST" not in completed.stdout
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_failure_evidence_contains_only_projected_readiness_observation() -> None:
    repository = Path(__file__).resolve().parents[3]
    launcher = (repository / "agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1").read_text(encoding="utf-8")
    failure_path = launcher[launcher.index("} catch {\n    $launcherFailure"):]
    assert failure_path.count("readinessObservation = $readinessObservation") == 3
    assert "response.Content" not in failure_path and "Exception.Message" not in failure_path


def test_prepare_creates_only_shared_result_parent_and_retains_exclusive_run(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    asset_parent = root / "agent-runtime/tests/uat"
    asset_parent.mkdir(parents=True)
    prepare._prepare_result_parent(root)
    result_parent = asset_parent / "results"
    assert result_parent.is_dir()
    assert list(result_parent.iterdir()) == []
    prepare._prepare_result_parent(root)
    output = result_parent / _RUN
    manifest = {"runId": _RUN, "frozenHead": _HEAD, "authorizationReference": "UAT_02:MEASURE-TEST"}
    runner.OneShotLedger(output_dir=output, manifest=manifest, manifest_sha256="b" * 64)
    with pytest.raises(FileExistsError):
        runner.OneShotLedger(output_dir=output, manifest=manifest, manifest_sha256="b" * 64)
    assert not (output / "authorization.consumed.json").exists()


def test_prepare_rejects_result_parent_file_without_overwriting_it(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    parent = root / "agent-runtime/tests/uat/results"
    _write(parent, b"existing-user-file")
    with pytest.raises(ValueError, match="result_parent_unavailable"):
        prepare._prepare_result_parent(root)
    assert parent.read_bytes() == b"existing-user-file"


def test_launcher_preserves_preledger_failure_beside_validated_freeze() -> None:
    repository = Path(__file__).resolve().parents[3]
    launcher = (repository / "agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1").read_text(encoding="utf-8")
    assert "$staticPreflightPassed = $false" in launcher
    assert launcher.index("--phase static") < launcher.index("$staticPreflightPassed = $true")
    assert "if ($staticPreflightPassed -and -not (Test-Path -LiteralPath $outputRoot))" in launcher
    assert "Join-Path (Split-Path -Parent $manifestFull) 'launcher-failure.json'" in launcher
    assert "evidenceLocation = 'frozen_asset_directory'" in launcher
    assert "callCounts = $null" in launcher


def test_startup_input_is_temporary_and_bound_to_only_build_attestation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    run_dir = root / "agent-runtime/tests/uat" / _RUN
    run_dir.mkdir(parents=True)
    temp_root = tmp_path / "system-temp"
    temp_root.mkdir()
    startup_dir = temp_root / ("codex-knowledge-measure-startup-" + "a" * 32)
    startup_dir.mkdir()
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(temp_root))
    _write(root / prepare._DATASET, Path(__file__).with_name(
        "knowledge_rebuild_measure.v1.json").read_bytes())
    for path in (*prepare._ASSETS, *prepare._JARS.values(), *runner._DEPENDENCY_JARS):
        if path != prepare._DATASET:
            _write(root / path, ("fixture:" + path).encode())
    _write(root / "config-service/src/main/resources/config/application.yml", b"key: value\n")
    attestation = {"schemaVersion": 1, "status": "built_from_clean_head", "branch": "codex_0915",
                   "head": _HEAD,
                   "jarSha256": {path: runner._sha(root / path) for path in prepare._JARS.values()},
                   "dependencyJarSha256": {path: runner._sha(root / path)
                                            for path in runner._DEPENDENCY_JARS},
                   "commands": runner._BUILD_COMMANDS}
    runner._exclusive_json(run_dir / "build-attestation.json", attestation)

    def fake_git(args: list[str], **kwargs: object) -> str:
        del kwargs
        if args[3:] == ["rev-parse", "HEAD"]:
            return _HEAD + "\n"
        if args[3:] == ["branch", "--show-current"]:
            return "codex_0915\n"
        if args[3:] == ["status", "--porcelain", "--untracked-files=all"]:
            return "?? " + (run_dir / "build-attestation.json").relative_to(root).as_posix() + "\n"
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "check_output", fake_git)
    dataset = json.loads((root / prepare._DATASET).read_text(encoding="utf-8"))
    source = dataset["sourceCorpus"]
    item = {"readAlias": source["readAlias"], "indexName": source["index"],
            "indexUuid": source["indexUuid"], "mappingVersion": "v1",
            "mappingSha256": source["mappingSha256"],
            "fullFingerprint": source["fullFingerprint"], "recordCount": source["recordCount"],
            "snapshotId": "a" * 64, "readPolicyVersion": "tax-public-authenticated-v1"}
    bindings_called = 0

    def fake_binding(actual_root: Path, actual_dataset: dict[str, Any],
                     **kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        nonlocal bindings_called
        assert actual_root == root
        assert actual_dataset == dataset
        bindings_called += 1
        kwargs["before_read"]()
        kwargs["before_read"]()
        return {"tax.policy": dict(item), "tax.law": dict(item)}, {}

    monkeypatch.setattr(prepare, "_binding", fake_binding)
    output = startup_dir / "startup-input.json"
    value = prepare.startup_input(root=root, run_dir=run_dir, output_path=output)
    assert startup._load_startup_input(output, runner._sha(output)) == value
    with pytest.raises(startup.StartupError, match="startup_input_invalid"):
        startup._load_startup_input(output, "0" * 64)
    assert bindings_called == 1
    assert (startup_dir / "startup-metadata-attempts.jsonl").read_bytes() == (
        b'{"attempt":1}\n{"attempt":2}\n')
    assert value["head"] == _HEAD and value["modelRequests"] == 0
    assert value["runtimeEnv"] == prepare._ENV
    assert value["bindingMetadataEsHttp"] == 2
    assert set(path.name for path in run_dir.iterdir()) == {"build-attestation.json"}
    assert value["configSha256"] == {
        "config-service/src/main/resources/config/application.yml":
            runner._sha(root / "config-service/src/main/resources/config/application.yml")}
    with pytest.raises(ValueError, match="startup_path_invalid"):
        prepare.startup_input(root=root, run_dir=run_dir, output_path=output)
    (root / "auth-service/target/auth-service-0.0.1-SNAPSHOT.jar").write_bytes(b"changed")
    another_dir = temp_root / ("codex-knowledge-measure-startup-" + "b" * 32)
    another_dir.mkdir()
    with pytest.raises(ValueError, match="startup_build_attestation_drift"):
        prepare.startup_input(root=root, run_dir=run_dir,
                              output_path=another_dir / "startup-input.json")
    assert bindings_called == 1


@pytest.mark.parametrize("failed_attempt", [1, 2])
def test_binding_counts_failed_http_attempt_before_send(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed_attempt: int,
) -> None:
    original_client = httpx.Client
    attempts: list[int] = []
    sends = 0

    def backend(request: httpx.Request) -> httpx.Response:
        nonlocal sends
        sends += 1
        assert attempts == list(range(1, sends + 1))
        if sends == failed_attempt:
            raise httpx.ConnectError("fake failure", request=request)
        return httpx.Response(200, json={})

    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original_client(
        **kwargs, transport=httpx.MockTransport(backend)))
    with pytest.raises(httpx.ConnectError):
        prepare._binding(tmp_path, {"sourceCorpus": {"readAlias": "read-v1", "index": "index-v1"}},
                         before_read=lambda: attempts.append(len(attempts) + 1))
    assert sends == failed_attempt and len(attempts) == failed_attempt


def test_launcher_checks_exact_config_set_before_and_after_startup() -> None:
    repository = Path(__file__).resolve().parents[3]
    launcher = (repository / "agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1").read_text(encoding="utf-8")
    assert "function Assert-FrozenConfig" in launcher
    assert "function Assert-FrozenAssets" in launcher
    assert "$manifest.jarSha256.PSObject.Properties" in launcher
    assert "$manifest.dependencyJarSha256.PSObject.Properties" in launcher
    assert "git -C $repository status --porcelain --untracked-files=no" in launcher
    assert launcher.count("    Assert-FrozenAssets") == 5
    assert "$actual.Count -ne $expected.Count" in launcher
    assert "$file.LinkType" in launcher
    assert launcher.index("    Assert-FrozenConfig") < launcher.index("$authProcess = Start-Process")
    assert launcher.index("    Assert-FrozenConfig", launcher.index("$userToken = Get-LoginToken")) < launcher.index(
        "GetEnvironmentVariable('LLM_API_KEY'")
    assert "metadataEsHttp = $metadataAttempts" in launcher
    assert "startup-metadata-attempts.jsonl" in launcher
    assert "$leakDetected = Test-LogLeak\n        if ($leakDetected)" in launcher
    assert "if ($leakDetected) { $launcherFailure = 'sensitive_output_detected' }" in launcher


@pytest.mark.skipif(os.name != "nt" or shutil.which("pwsh") is None, reason="Windows PowerShell guard")
def test_config_guard_rejects_hash_and_added_file_drift_without_service(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).resolve().parents[3]
    launcher = (repository / "agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1").read_text(encoding="utf-8")
    guard = launcher[launcher.index("function Assert-FrozenConfig {"):launcher.index("function Stop-OwnedProcesses {")]
    config = tmp_path / "config-service/src/main/resources/config/application.yml"
    _write(config, b"frozen: yes\n")
    expected = runner._sha(config)
    program = (
        "$ErrorActionPreference='Stop'; $startup=$true; "
        f"$repository='{tmp_path}'; "
        "$manifest=[pscustomobject]@{configSha256=[pscustomobject]@{"
        f"'config-service/src/main/resources/config/application.yml'='{expected}'}}}}; "
        + guard + "; Assert-FrozenConfig; "
        f"[IO.File]::WriteAllText('{config}', 'changed'); "
        "try { Assert-FrozenConfig; exit 11 } catch { if ($_.Exception.Message -cne 'knowledge.measure.config_hash_drift') {exit 12} }; "
        f"[IO.File]::WriteAllText('{config}', \"frozen: yes`n\", [Text.Encoding]::UTF8); "
        f"[IO.File]::WriteAllText('{config.with_name('added.yaml')}', 'extra'); "
        "try { Assert-FrozenConfig; exit 13 } catch { if ($_.Exception.Message -cne 'knowledge.measure.config_hash_drift') {exit 14} }; exit 0"
    )
    completed = subprocess.run(["pwsh", "-NoProfile", "-Command", program],
                               capture_output=True, text=True, timeout=20, check=False)
    assert completed.returncode == 0, completed.stderr


@pytest.mark.skipif(os.name != "nt" or shutil.which("pwsh") is None, reason="Windows PowerShell guard")
def test_asset_guard_rejects_code_drift_before_service_without_outbound(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[3]
    launcher = (repository / "agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1").read_text(encoding="utf-8")
    guard = launcher[launcher.index("function Assert-FrozenAssets {"):launcher.index("function Stop-OwnedProcesses {")]
    asset = tmp_path / "helper.py"
    build = tmp_path / "build-attestation.json"
    _write(asset, b"frozen helper\n")
    _write(build, b"{}\n")
    program = (
        "$ErrorActionPreference='Stop'; $startup=$true; "
        f"$repository='{tmp_path}'; "
        "$manifest=[pscustomobject]@{"
        f"head='{_HEAD}'; assetSha256=[pscustomobject]@{{'helper.py'='{runner._sha(asset)}'}}; "
        "jarSha256=[pscustomobject]@{}; dependencyJarSha256=[pscustomobject]@{}; "
        f"buildAttestationPath='build-attestation.json'; buildAttestationSha256='{runner._sha(build)}'}}; "
        "function git { $global:LASTEXITCODE=0; if ($args -contains 'rev-parse') { "
        f"'{_HEAD}' "
        "} elseif ($args -contains 'branch') { 'codex_0915' } }; "
        + guard + "; Assert-FrozenAssets; "
        f"[IO.File]::WriteAllText('{asset}', 'drift'); "
        "try { Assert-FrozenAssets; exit 11 } catch { if ($_.Exception.Message -cne 'knowledge.measure.asset_hash_drift') {exit 12} }; exit 0"
    )
    completed = subprocess.run(["pwsh", "-NoProfile", "-Command", program],
                               capture_output=True, text=True, timeout=20, check=False)
    assert completed.returncode == 0, completed.stderr


def test_startup_proxy_denies_search_and_writes_before_fake_backend() -> None:
    calls: list[tuple[str, str]] = []

    def backend(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        return httpx.Response(200, json={"status": "green"})

    with httpx.Client(base_url="http://127.0.0.1:9200", follow_redirects=False,
                      trust_env=False, transport=httpx.MockTransport(backend)) as client:
        proxy = startup.MeasureEsProxy(index_name="index-v1", read_alias="read-v1", port=19313,
                                       metadata_limit=2, search_limit=0, backend=client)
        assert proxy.forward("GET", "/_cluster/health", b"")[0] == 200
        assert proxy.forward("GET", "/_alias/read-v1", b"")[0] == 200
        for method, path, body in (("GET", "/_cluster/health", b""),
                                   ("POST", "/read-v1/_search", b"{}"),
                                   ("DELETE", "/index-v1", b""),
                                   ("GET", "/other/_mapping", b"")):
            with pytest.raises(startup.StartupError, match="proxy_request_forbidden"):
                proxy.forward(method, path, body)
        assert calls == [("GET", "/_cluster/health"), ("GET", "/_alias/read-v1")]
        assert proxy.counts() == {"metadataEsHttp": 2, "searchEsHttp": 0, "proxyViolations": 4,
                                  "healthEsHttp": 1, "aliasEsHttp": 1,
                                  "settingsEsHttp": 0, "mappingEsHttp": 0,
                                  "definitionEsHttp": 0}


@pytest.mark.parametrize("product", [None, "Elasticsearch", "NotElasticsearch"])
def test_proxy_http_preserves_only_upstream_product_identity(product: str | None, unused_tcp_port: int) -> None:
    calls: list[str] = []

    def backend(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        headers = {"Content-Type": "application/json", "Set-Cookie": "DO_NOT_FORWARD",
                   "X-Unrelated": "DO_NOT_FORWARD"}
        if product is not None:
            headers["x-elastic-product"] = product
        return httpx.Response(200, content=b'{"status":"green"}', headers=headers)

    with httpx.Client(base_url="http://127.0.0.1:9200", follow_redirects=False,
                      trust_env=False, transport=httpx.MockTransport(backend)) as client:
        proxy = startup.MeasureEsProxy(index_name="index-v1", read_alias="read-v1", port=unused_tcp_port,
                                       metadata_limit=1, search_limit=0, backend=client)
        thread = Thread(target=proxy.serve, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 2
            while proxy._server is None and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert proxy._server is not None
            with httpx.Client(trust_env=False, timeout=2) as downstream:
                response = downstream.get(f"http://127.0.0.1:{unused_tcp_port}/_cluster/health")
            assert response.status_code == 200
            assert response.content == b'{"status":"green"}'
            assert response.headers.get("x-elastic-product") == product
            assert "set-cookie" not in response.headers
            assert "x-unrelated" not in response.headers
            assert "DO_NOT_FORWARD" not in str(response.headers)
            assert calls == ["/_cluster/health"]
            assert proxy.counts()["metadataEsHttp"] == 1
            assert proxy.counts()["proxyViolations"] == 0
        finally:
            if proxy._server is not None:
                proxy._server.shutdown()
            thread.join(timeout=5)
            assert not thread.is_alive()


@pytest.mark.parametrize("headers", [
    [("x-elastic-product", "Elasticsearch"), ("x-elastic-product", "Elasticsearch")],
    [("x-elastic-product", "a" * 65)],
    [("x-elastic-product", "")],
    [("x-elastic-product", "Elasticsearch\r\nSet-Cookie: DO_NOT_FORWARD")],
    [("x-elastic-product", "Elastic\tsearch")],
])
def test_proxy_rejects_unsafe_product_header_without_another_backend_call(headers: list[tuple[str, str]]) -> None:
    calls = 0

    def backend(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"status": "green"}, headers=headers)

    with httpx.Client(base_url="http://127.0.0.1:9200", follow_redirects=False,
                      trust_env=False, transport=httpx.MockTransport(backend)) as client:
        proxy = startup.MeasureEsProxy(index_name="index-v1", read_alias="read-v1", port=19313,
                                       metadata_limit=1, search_limit=0, backend=client)
        with pytest.raises(startup.StartupError, match="proxy_response_product_header_invalid"):
            proxy.forward("GET", "/_cluster/health", b"")
        assert calls == 1
        assert proxy.counts()["metadataEsHttp"] == 1
        assert proxy.counts()["proxyViolations"] == 1


def test_startup_proxy_counts_both_exact_health_paths_without_widening_routes() -> None:
    calls: list[str] = []

    def backend(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"status": "green"})

    with httpx.Client(base_url="http://127.0.0.1:9200", follow_redirects=False,
                      trust_env=False, transport=httpx.MockTransport(backend)) as client:
        proxy = startup.MeasureEsProxy(index_name="index-v1", read_alias="read-v1", port=19313,
                                       metadata_limit=2, search_limit=0, backend=client)
        assert proxy.forward("GET", "/_cluster/health", b"")[0] == 200
        assert proxy.forward("GET", "/_cluster/health/", b"")[0] == 200
        for path in ("/_cluster/health", "/_cluster/health/?pretty", "/_cluster/health/extra"):
            with pytest.raises(startup.StartupError, match="proxy_request_forbidden"):
                proxy.forward("GET", path, b"")
        with pytest.raises(startup.StartupError, match="proxy_request_forbidden"):
            proxy.forward("POST", "/_cluster/health/", b"{}")
        assert calls == ["/_cluster/health", "/_cluster/health/"]
        assert proxy.counts() == {"metadataEsHttp": 2, "searchEsHttp": 0, "proxyViolations": 4,
                                  "healthEsHttp": 2, "aliasEsHttp": 0,
                                  "settingsEsHttp": 0, "mappingEsHttp": 0,
                                  "definitionEsHttp": 0}


def test_formal_proxy_counts_each_alias_get_and_rejects_seventy_third_metadata_attempt() -> None:
    calls: list[str] = []

    def backend(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={})

    with httpx.Client(base_url="http://127.0.0.1:9200", follow_redirects=False,
                      trust_env=False, transport=httpx.MockTransport(backend)) as client:
        proxy = startup.MeasureEsProxy(index_name="index-v1", read_alias="read-v1", port=19313,
                                       metadata_limit=72, search_limit=48, backend=client)
        for _ in range(18):
            proxy.forward("GET", "/_cluster/health", b"")
        for _ in range(2):
            for path in ("/_alias/read-v1", "/index-v1/_settings", "/index-v1/_mapping"):
                proxy.forward("GET", path, b"")
        for _ in range(24):
            proxy.forward("GET", "/_alias/read-v1", b"")
            proxy.forward("GET", "/index-v1", b"")
        assert proxy.counts() == {"metadataEsHttp": 72, "searchEsHttp": 0,
                                  "proxyViolations": 0, "healthEsHttp": 18,
                                  "aliasEsHttp": 26, "settingsEsHttp": 2,
                                  "mappingEsHttp": 2, "definitionEsHttp": 24}
        with pytest.raises(startup.StartupError, match="proxy_request_forbidden"):
            proxy.forward("GET", "/index-v1", b"")
        assert len(calls) == 72
        assert proxy.counts()["proxyViolations"] == 1


def test_formal_proxy_records_failed_metadata_attempt_before_backend_error() -> None:
    def fail_backend(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("fake connection failure", request=request)

    with httpx.Client(base_url="http://127.0.0.1:9200", follow_redirects=False,
                      trust_env=False, transport=httpx.MockTransport(fail_backend)) as client:
        proxy = startup.MeasureEsProxy(index_name="index-v1", read_alias="read-v1", port=19313,
                                       metadata_limit=72, search_limit=48, backend=client)
        with pytest.raises(httpx.ConnectError):
            proxy.forward("GET", "/_alias/read-v1", b"")
        assert proxy.counts() == {"metadataEsHttp": 1, "searchEsHttp": 0,
                                  "proxyViolations": 1, "healthEsHttp": 0,
                                  "aliasEsHttp": 1, "settingsEsHttp": 0,
                                  "mappingEsHttp": 0, "definitionEsHttp": 0}


def test_startup_runtime_uses_only_frozen_nonsecret_environment_and_denies_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "violation.marker"
    monkeypatch.setenv("LLM_API_KEY", "real-key-must-not-be-read")
    with pytest.raises(startup.StartupError, match="startup_runtime_env_invalid"):
        startup.runtime_app(startup_input={"runtimeEnv": {"AGENT_MODEL_PROVIDER": "deepseek"}},
                            violation_marker=marker)
    app = startup.runtime_app(startup_input={"runtimeEnv": dict(prepare._ENV)},
                              violation_marker=marker)

    async def check_lifespan() -> None:
        async with app.router.lifespan_context(app):
            assert app.state.ready is True
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                         base_url="http://testserver") as client:
                response = await client.get("/internal/health/ready")
            assert response.status_code == 200
        assert app.state.ready is False

    asyncio.run(check_lifespan())
    assert not marker.exists()
