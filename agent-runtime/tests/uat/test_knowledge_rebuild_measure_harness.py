"""Zero-outbound counterexamples for the one-shot Spring measurement harness."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
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
        async with httpx.AsyncClient(base_url="http://127.0.0.1:9200",
                                     transport=httpx.MockTransport(handle)) as client:
            await runner._alias_check(manifest, client)

    with pytest.raises(runner.MeasurementError, match="index_metadata_drift"):
        asyncio.run(check())
    assert paths == [f"/_alias/{alias}", f"/{index}"]


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
    env = dict(prepare._ENV)
    manifest, _, _ = runner.frozen_preflight(root=root,
        manifest_path=run_dir / "manifest.json", authorization_path=run_dir / "authorization.json",
        output_dir=output_dir, environ=env)
    assert manifest["answerDesign"] == "Summary9"
    assert manifest["subject"] == {"userId": "viewer_t", "role": "VIEWER"}
    assert manifest["jarBuildHead"] == _HEAD
    assert set(manifest["promptSha256"]) == {"action_selection", "knowledge_rewrite", "knowledge_summary"}
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
