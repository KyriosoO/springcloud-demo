"""DR-KFLOW-401..403: actual formal runner, real codecs, only in-memory ports."""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time
from typing import Any

import httpx
import pytest

from agent_runtime.main import build_runtime
from agent_runtime.model.contracts import (ModelTaskId, StructuredModelRequest, StructuredModelResponse,
    StructuredFinishKind, StructuredToolCall)
from agent_runtime.knowledge.evidence.summary_task_v9 import OUTPUT_NAME
from tests.integration.knowledge.test_minimal_current_root import MinimalModel
from tests.integration.knowledge.test_production_runtime_wiring import _KnowledgeClientFactory, _SNAPSHOT_ID
from tests.uat import knowledge_rebuild_measure_runner as runner
from tests.uat.knowledge_rebuild_measure_budget import PLAN


class InMemoryServer:
    def __init__(self, config: Any) -> None:
        self.app = config.app
        self.started = False
        self.should_exit = False
        self.closed = False

    async def serve(self) -> None:
        async with self.app.router.lifespan_context(self.app):
            self.started = True
            while not self.should_exit:
                await asyncio.sleep(0.001)
        self.closed = True


class DryRun:
    def __init__(self, tmp: Path, monkeypatch: pytest.MonkeyPatch, fault: str | None = None) -> None:
        self.tmp, self.fault = tmp, fault
        self.servers: list[InMemoryServer] = []
        self.clients = _KnowledgeClientFactory()
        self.model = MinimalModel()
        self.posts: list[str] = []
        self.metadata = 0
        mapping = {"_meta": {"mapping_version": "synthetic-v1"}}
        mapping_sha = hashlib.sha256((json.dumps(mapping, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest()
        binding = {"readAlias": "synthetic-alias", "indexName": "synthetic-index", "indexUuid": "synthetic-uuid",
                   "mappingVersion": "synthetic-v1", "mappingSha256": mapping_sha, "snapshotId": _SNAPSHOT_ID}
        cases = [{"caseId": f"UAT-KM-{n:03}", "question": f"请查找增值税政策资料第{n}组",
                  "queryMode": "lookup", "expectedDomains": ["tax.policy"], "necessarySources": [],
                  "expectedPublicStatus": "success", "obligations": []} for n in range(1, 13)]
        self.manifest = {"runId": "knowledge-dryrun-synthetic-01", "executionKind": "non_live",
                         "liveConsumable": False, "frozenHead": "a" * 40,
                         "authorizationReference": runner._NON_LIVE_REFERENCE,
                         "fixtureSha256": hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest(),
                         "_sha256": "b" * 64, "_authorizationSha256": "c" * 64,
                         "springBaseUrl": "http://synthetic-spring.test", "cases": cases, "sources": [],
                         "aliasFlags": {}, "indexBindings": {"tax.policy": binding, "tax.law": binding}}

        def deny(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("real network forbidden in dryrun")

        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", deny)
        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", deny)
        monkeypatch.setattr(runner, "_owned_ports_match", lambda **kwargs: None)

        async def metadata(request: httpx.Request) -> httpx.Response:
            self.metadata += 1
            if (self.fault == "snapshot" and len(self.posts) == 3
                    or self.fault == "snapshot_before" and self.metadata == 9):
                return httpx.Response(200, json={"wrong-index": {}})
            if request.url.path == "/_alias/synthetic-alias":
                return httpx.Response(200, json={"synthetic-index": {"aliases": {"synthetic-alias": {}}}})
            assert request.url.path == "/synthetic-index"
            return httpx.Response(200, json={"synthetic-index": {"settings": {"index": {
                "uuid": "synthetic-uuid", "blocks": {"write": "true"}}}, "mappings": mapping}})

        self.ports = runner._NonLivePorts(runtime_builder=self.runtime_builder,
                                          metadata_transport=httpx.MockTransport(metadata))
        if fault == "invalid_quote":
            original = self.model.complete

            async def invalid(request: StructuredModelRequest, *, call_deadline: float) -> StructuredModelResponse:
                if request.task_id is ModelTaskId.KNOWLEDGE_SUMMARY and len(self.posts) == 3:
                    self.model.requests.append(request)
                    return StructuredModelResponse(finish_kind=StructuredFinishKind.TOOL_CALLS, content=None,
                        tool_calls=(StructuredToolCall(name=OUTPUT_NAME, arguments_json=json.dumps({
                            "outcome": "answer", "points": [{"evidence_ref": "e1", "quote": "DO_NOT_PERSIST", "claim": ""}]})),),
                        usage_total_tokens=0)
                return await original(request, call_deadline=call_deadline)
            self.model.complete = invalid  # type: ignore[method-assign]

    def runtime_builder(self, environ: Any, **kwargs: Any) -> Any:
        return build_runtime({"AGENT_MODEL_PROVIDER": "stub", "AGENT_KNOWLEDGE_ENABLED": "true",
                              "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy",
                              "AGENT_KNOWLEDGE_ES_BASE_URL": "http://synthetic-knowledge.test"},
                             model_transport=self.model, knowledge_http_client_factory=self.clients, **kwargs)

    def server(self, config: Any) -> InMemoryServer:
        value = InMemoryServer(config)
        self.servers.append(value)
        return value

    async def spring(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/actuator/health/readiness":
            return httpx.Response(200, json={"status": "UP"})
        assert request.url.path == "/api/v1/agent/queries"
        question = json.loads(request.content)["question"]
        case_id = request.headers["X-Correlation-Id"]
        self.posts.append(case_id)
        if len(self.posts) == 3:
            if self.fault == "http":
                return httpx.Response(502, json={"status": "downstream_failure", "correlationId": case_id,
                    "capabilityId": "knowledge.query", "error": {"code": "knowledge.retrieval_failure", "source": "downstream"},
                    "answer": "DO_NOT_PERSIST"})
            if self.fault == "malformed":
                return httpx.Response(502, content=b"DO_NOT_PERSIST")
            if self.fault == "timeout":
                raise httpx.ReadTimeout("DO_NOT_PERSIST")
            if self.fault == "cancel":
                raise asyncio.CancelledError("DO_NOT_PERSIST")
            if self.fault == "denied":
                return httpx.Response(403, json={"status": "forbidden", "capabilityId": "knowledge.query",
                    "correlationId": case_id, "error": {"code": "knowledge.evidence_read_forbidden", "source": "capability"}})
        # This is a synthetic Spring adapter, not proof of a real Java integration.
        async with httpx.AsyncClient(base_url="http://synthetic-runtime.test",
            transport=httpx.ASGITransport(app=self.servers[0].app)) as runtime:
            response = await runtime.post("/internal/v1/agent-runs:invoke", headers={
                "Authorization": request.headers["Authorization"], "X-Agent-Contract-Version": "1"},
                json={"contractVersion": 1, "requestId": case_id, "correlationId": case_id, "question": question,
                      "subject": {"id": "synthetic-viewer", "type": "user"},
                      "deadlineEpochMs": time.time_ns() // 1_000_000 + 30000, "remainingTimeoutMs": 30000})
        assert response.status_code == 200, response.text
        value = response.json()
        return httpx.Response(200, json={"requestId": case_id, "correlationId": case_id,
            "status": value["status"], "capabilityId": value["capabilityId"], "answer": value["answerText"] or "",
            "result": value["userResult"], "error": value["failure"]})

    async def execute(self) -> None:
        # Windows creates a loopback socketpair for event-loop teardown. Restrict
        # only the actual runner window, not pytest's unrelated loop lifecycle.
        with pytest.MonkeyPatch.context() as network:
            def deny(*args: Any, **kwargs: Any) -> Any:
                raise AssertionError("real socket forbidden in dryrun")
            network.setattr(socket.socket, "connect", deny)
            async with httpx.AsyncClient(base_url=self.manifest["springBaseUrl"],
                                         transport=httpx.MockTransport(self.spring)) as client:
                await runner.run_once(manifest=self.manifest, output_dir=self.tmp / "output", review_dir=self.tmp / "review",
                    token="synthetic-token-not-a-JWT", environ={}, client=client, es_pid=1, agent_pid=2, proxy_pid=3,
                    server_factory=self.server, _test_ports=self.ports)


@pytest.mark.asyncio
async def test_twelve_cases_use_formal_runner_real_decoders_ledger_and_cleanup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = DryRun(tmp_path, monkeypatch)
    await run.execute()
    result = json.loads((tmp_path / "output/measurement.json").read_bytes())
    records = [json.loads(line) for line in (tmp_path / "output/cases.jsonl").read_text().splitlines()]
    assert result["caseCount"] == 12 and len(records) == 12 and len(run.posts) == 12
    assert result["counts"] == {"model": 36, "search": 24, "embedding": 12, "rerank": 12}
    assert result["aliasChecks"] == 24 and run.metadata == 48
    assert result["executionKind"] == "non_live" and result["liveConsumable"] is False
    assert result["realCalls"] == {"model": 0, "ES": 0, "BGE": 0, "Business": 0}
    assert all(row["response"]["status"] == "success" and row["runtimeInvocations"] == 1 for row in records)
    assert all(row["observedPlan"]["selectedDomainIds"] == ["tax.policy"] for row in records)
    assert [request.task_version for request in run.model.requests] == ["action-selection-v5", "12", "9"] * 12
    assert run.servers[0].closed and all(client.is_closed for client in run.clients.clients)
    assert json.loads((tmp_path / "output/runner-cleanup.json").read_bytes())["passed"] is True
    assert not (tmp_path / "output/authorization.consumed.json").exists()
    assert not (tmp_path / "output/authorization.json").exists()
    assert (tmp_path / "output/synthetic-consumed.json").is_file()


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["http", "malformed", "timeout", "denied", "snapshot", "cancel", "invalid_quote"])
async def test_midrun_failure_stops_next_case_and_keeps_safe_finite_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str) -> None:
    run = DryRun(tmp_path, monkeypatch, fault)
    with pytest.raises((runner.MeasurementError, httpx.ReadTimeout, json.JSONDecodeError, asyncio.CancelledError)):
        await run.execute()
    failure = json.loads((tmp_path / "output/failure.json").read_bytes())
    assert failure["completedCases"] == 2
    assert run.posts == ["UAT-KM-001", "UAT-KM-002", "UAT-KM-003"]
    assert failure["unexecutedCases"] == [f"UAT-KM-{n:03}" for n in range(4, 13)]
    assert failure["reason"] in {"alias_drift", "case_technical_failure"}
    assert failure["counts"]["model"] == (9 if fault in {"snapshot", "invalid_quote"} else 6)
    assert not (tmp_path / "output/measurement.json").exists()
    assert run.servers[0].closed and all(client.is_closed for client in run.clients.clients)
    assert "DO_NOT_PERSIST" not in (tmp_path / "output/failure.json").read_text()


@pytest.mark.asyncio
async def test_partial_runtime_start_failure_has_zero_attempts_and_finite_terminal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = DryRun(tmp_path, monkeypatch)
    def failed_builder(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("DO_NOT_PERSIST")
    run.ports = runner._NonLivePorts(runtime_builder=failed_builder, metadata_transport=run.ports.metadata_transport)
    with pytest.raises(runner.MeasurementError):
        await run.execute()
    failure = json.loads((tmp_path / "output/failure.json").read_bytes())
    assert failure["counts"] == {"model": 0, "search": 0, "embedding": 0, "rerank": 0}
    assert failure["reason"] == "runtime_start_failed" and len(failure["unexecutedCases"]) == 12
    assert failure["stage"] == "runtime_start"
    assert not run.posts and run.metadata == 0
    assert "DO_NOT_PERSIST" not in (tmp_path / "output/failure.json").read_text()


@pytest.mark.asyncio
async def test_before_send_snapshot_failure_keeps_reason_case_and_unexecuted_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = DryRun(tmp_path, monkeypatch, "snapshot_before")
    with pytest.raises(runner.MeasurementError, match="alias_drift"):
        await run.execute()
    failure = json.loads((tmp_path / "output/failure.json").read_bytes())
    assert failure["reason"] == "alias_drift" and failure["stage"] == "case_snapshot_before"
    assert failure["failedCase"]["caseId"] == "UAT-KM-003"
    assert failure["failedCase"]["httpStatus"] is None
    assert failure["completedCases"] == 2 and len(run.posts) == 2
    assert failure["counts"]["model"] == 6
    assert failure["unexecutedCases"] == [f"UAT-KM-{n:03}" for n in range(3, 13)]


@pytest.mark.parametrize("exception", ["asyncio.CancelledError", "KeyboardInterrupt"])
def test_real_cli_cancellation_boundary_never_prints_arbitrary_exception_text(exception: str) -> None:
    import sys
    script = f"""
import asyncio, sys
from tests.uat import knowledge_rebuild_measure_runner as runner
async def cancelled(args):
    raise {exception}('DO_NOT_PERSIST')
runner._main = cancelled
sys.argv = ['runner', '--repository', '.', '--manifest', 'unused', '--authorization', 'unused', '--output', 'unused']
runner.main()
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=20)
    assert result.returncode != 0
    assert result.stderr.strip() == "knowledge.measure.cancelled"
    assert "DO_NOT_PERSIST" not in result.stdout + result.stderr


@pytest.mark.asyncio
async def test_synthetic_case_hash_drift_refuses_before_runtime_and_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = DryRun(tmp_path, monkeypatch)
    run.manifest["cases"][0]["question"] = "资料已变更"
    with pytest.raises(runner.MeasurementError, match="non_live_binding_invalid"):
        await run.execute()
    assert not run.servers and not run.posts and not (tmp_path / "output").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("writer", ["checkpoint", "failure"])
async def test_writer_failure_is_nonzero_no_retry_and_still_closes_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, writer: str) -> None:
    run = DryRun(tmp_path, monkeypatch, "http" if writer == "failure" else None)
    journal, exclusive = runner._journal, runner._exclusive_json

    def failing_journal(path: Path, value: Any) -> None:
        if path.name == "cases.jsonl":
            raise PermissionError("DO_NOT_PERSIST")
        journal(path, value)

    def failing_exclusive(path: Path, value: Any) -> None:
        if path.name == "failure.json":
            raise PermissionError("DO_NOT_PERSIST")
        exclusive(path, value)

    monkeypatch.setattr(runner, "_journal", failing_journal if writer == "checkpoint" else journal)
    monkeypatch.setattr(runner, "_exclusive_json", failing_exclusive if writer == "failure" else exclusive)
    with pytest.raises((PermissionError, runner.MeasurementError)):
        await run.execute()
    assert len(run.posts) == (1 if writer == "checkpoint" else 3)
    assert run.servers[0].closed and all(client.is_closed for client in run.clients.clients)
    assert not (tmp_path / "output/measurement.json").exists()


@pytest.mark.asyncio
async def test_fake_identity_cannot_enter_live_run_or_preflight_before_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = DryRun(tmp_path, monkeypatch)
    async with httpx.AsyncClient(base_url=run.manifest["springBaseUrl"], transport=httpx.MockTransport(run.spring)) as client:
        with pytest.raises(runner.MeasurementError, match="non_live_binding_invalid"):
            await runner.run_once(manifest=run.manifest, output_dir=tmp_path / "output", review_dir=tmp_path / "review",
                token="synthetic", environ={}, client=client, es_pid=1, agent_pid=2, proxy_pid=3)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(run.manifest), encoding="utf-8")
    with pytest.raises(runner.MeasurementError, match="non_live_asset_forbidden"):
        runner.frozen_preflight(root=tmp_path, manifest_path=path, authorization_path=tmp_path / "DO_NOT_READ",
                                output_dir=tmp_path / "output", environ={})
    assert not (tmp_path / "output").exists() and not run.posts


@pytest.mark.asyncio
async def test_output_conflict_refuses_before_runtime_or_transport(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = DryRun(tmp_path, monkeypatch)
    (tmp_path / "output").mkdir()
    with pytest.raises(FileExistsError):
        await run.execute()
    assert not run.servers and not run.posts and run.metadata == 0


@pytest.mark.asyncio
async def test_cleanup_hang_is_bounded_and_never_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = DryRun(tmp_path, monkeypatch)
    original_serve = InMemoryServer.serve

    async def hanging_serve(server: InMemoryServer) -> None:
        await original_serve(server)
        await asyncio.Event().wait()

    monkeypatch.setattr(InMemoryServer, "serve", hanging_serve)
    monkeypatch.setattr(runner, "_SERVER_CLOSE_SECONDS", 0.05)
    with pytest.raises(runner.MeasurementError, match="runtime_cleanup_failed"):
        await asyncio.wait_for(run.execute(), timeout=5)
    cleanup = json.loads((tmp_path / "output/runner-cleanup.json").read_bytes())
    assert cleanup == {"passed": False, "stopped": True, "reason": "runtime_close_timeout"}
    assert all(client.is_closed for client in run.clients.clients)


def test_budget_plan_is_single_immutable_definition_and_matches_approved_caps() -> None:
    assert PLAN.limits() == {"cases": 12, "model": 36, "search": 48, "embedding": 12, "rerank": 24}
    assert PLAN.per_case() == {"model": 3, "search": 4, "embedding": 1, "rerank": 2}
    assert PLAN.launcher_limits()["runtimeMetadataEsHttpMax"] == 72
    assert PLAN.launcher_limits()["startupMetadataMax"] == 48
    with pytest.raises(FrozenInstanceError):
        PLAN.case_count = 13  # type: ignore[misc]
    copy = PLAN.limits()
    copy["model"] = 100
    assert PLAN.limits()["model"] == 36


@pytest.mark.parametrize("cached", [False, True])
def test_actual_launcher_cleanup_refuses_reused_parent_pid_but_keeps_attested_handles(cached: bool) -> None:
    launcher = Path(__file__).resolve().parents[2] / "scripts/run-knowledge-rebuild-measure-v1.ps1"
    script = r"""
$ErrorActionPreference='Stop'
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile('__LAUNCHER__',[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw 'AST invalid' }
$names=@('Add-CleanupIssue','Stop-OwnedProcesses','Test-OwnedProcessesStopped','Get-CleanupIssues','Invoke-OwnedLifecycle')
foreach ($name in $names) {
    $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name },$true))
    if ($found.Count -ne 1) { throw 'function not unique' }
    Invoke-Expression $found[0].Extent.Text
}
$script:inventory=0; $script:attested=0; $script:killed=0
function Get-CimInstance { $script:inventory++; throw 'must not inspect reused PID' }
function Get-AttestedPythonProcess { $script:attested++; throw 'must not take new child' }
$ownedPythonChildren=@{}; $cleanupIssues=@{}; $ownedChildCleanupUnknown=$false; $pythonOutputDrains=@()
$authProcess=$null; $esProcess=$null; $agentProcess=$null; $runtimeProcess=$null
$proxyProcess=[pscustomobject]@{ Id=123; HasExited=$true }
if (__CACHED__) {
    $child=[pscustomobject]@{ Id=456; HasExited=$false }
    $child | Add-Member ScriptMethod Kill { $script:killed++; $this.HasExited=$true }
    $child | Add-Member ScriptMethod WaitForExit { param($ms) return $true }
    $ownedPythonChildren[19313]=$child
}
Stop-OwnedProcesses
if ($script:inventory -ne 0 -or $script:attested -ne 0) { throw 'PID reuse not rejected' }
if (__CACHED__) {
    if ($script:killed -ne 1 -or -not (Test-OwnedProcessesStopped)) { throw 'owned handle cleanup failed' }
} else {
    if ($script:killed -ne 0 -or (Test-OwnedProcessesStopped)) { throw 'unknown cleanup claimed success' }
}
'pid-generation-safe'
""".replace("__LAUNCHER__", launcher.as_posix()).replace("__CACHED__", "$true" if cached else "$false")
    result = subprocess.run(["pwsh", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("pid-generation-safe")


@pytest.mark.parametrize("fault", ["startup", "cancel", "cleanup_timeout"])
def test_formal_launcher_lifecycle_cleans_partial_start_and_fails_on_timeout(fault: str) -> None:
    launcher = Path(__file__).resolve().parents[2] / "scripts/run-knowledge-rebuild-measure-v1.ps1"
    source = launcher.read_text(encoding="utf-8")
    functions = source[source.index("function Add-CleanupIssue"):source.index("Invoke-OwnedLifecycle -Action {\ntry {")]
    assert "Invoke-OwnedLifecycle -Action {\ntry {" in source
    script = r"""
$ErrorActionPreference='Stop'
$ownedPythonChildren=@{}; $ownedChildCleanupUnknown=$false; $cleanupIssues=@{}; $pythonOutputDrains=@()
$runtimeProcess=$null; $proxyProcess=$null; $agentProcess=$null; $esProcess=$null; $authProcess=$null
__FUNCTIONS__
$script:kills=0; $script:waits=0; $caught=''
try {
    Invoke-OwnedLifecycle -Action {
        $authProcess=[pscustomobject]@{ Id=321; HasExited=$false }
        $authProcess | Add-Member ScriptMethod Kill { $script:kills++; if ('__FAULT__' -ne 'cleanup_timeout') { $this.HasExited=$true } }
        $authProcess | Add-Member ScriptMethod WaitForExit { param($ms) $script:waits++; return ('__FAULT__' -ne 'cleanup_timeout') }
        if ('__FAULT__' -eq 'cancel') { throw [OperationCanceledException]::new('synthetic cancel') }
        if ('__FAULT__' -eq 'startup') { throw 'synthetic start failure' }
    }
} catch { $caught=$_.Exception.Message }
if (-not $caught -or $script:kills -ne 1 -or $script:waits -ne 1) { throw 'failed lifecycle skipped cleanup' }
if ('__FAULT__' -eq 'cleanup_timeout' -and $caught -cne 'knowledge.measure.final_cleanup_failed') { throw 'cleanup falsely passed' }
'lifecycle-closed'
""".replace("__FUNCTIONS__", functions).replace("__FAULT__", fault)
    result = subprocess.run(["pwsh", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("lifecycle-closed")


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["search", "embedding", "rerank"])
async def test_exact_cap_plus_one_never_sends_and_failure_attempt_not_refunded(tmp_path: Path, kind: str) -> None:
    ledger = runner.OneShotLedger(output_dir=tmp_path / "output", manifest={}, manifest_sha256="a" * 64)
    calls = 0

    class Fake:
        async def send(self, **kwargs: Any) -> Any:
            nonlocal calls
            calls += 1
            raise httpx.ReadTimeout("DO_NOT_PERSIST")

    from agent_runtime.knowledge.retrieval.http import BoundedHttpRequest
    request = BoundedHttpRequest(method="POST", relative_path=runner._PATHS[kind], headers=(), body=b"{}", max_response_bytes=1024)
    ledger.begin("one", "公开税务政策")
    with pytest.raises(httpx.ReadTimeout):
        await ledger.transport(kind, Fake()).send(request=request, timeout_s=1)
    assert ledger.total[kind] == 1
    with pytest.raises(runner.MeasurementError, match="inactive_or_terminal"):
        await ledger.transport(kind, Fake()).send(request=request, timeout_s=1)
    assert calls == 1
    ledger = runner.OneShotLedger(output_dir=tmp_path / "cap", manifest={}, manifest_sha256="a" * 64)
    ledger.begin("one", "公开税务政策")
    ledger.total[kind] = PLAN.limits()[kind]
    with pytest.raises(runner.MeasurementError, match="budget_exhausted"):
        await ledger.transport(kind, Fake()).send(request=request, timeout_s=1)
    assert calls == 1
