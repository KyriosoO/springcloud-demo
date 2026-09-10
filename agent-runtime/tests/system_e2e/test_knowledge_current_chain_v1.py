"""Current root and all three real decoders; network responses are synthetic."""
import asyncio
from contextlib import contextmanager
from dataclasses import replace
import json
from types import SimpleNamespace

import httpx
import pytest

from agent_runtime.knowledge.evidence.requirement_validation import RequirementCoverageValidator
from agent_runtime.knowledge.evidence.summary_validation import ExtractiveSummaryValidator
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from agent_runtime.model.settings import ModelApiKey, ModelProvider, ModelSettings
from tests.integration.knowledge import test_requirement_runtime_composition as production
from tests.system_e2e import knowledge_current_chain_v1 as runner
from tests.system_e2e.test_knowledge_model_failure_probe_v1 import wire

KEY, TOKEN = "synthetic-current-chain-key", "header.payload.signature"


def fixture_case():
    # Deliberately wrong fixture requirements/domains. Only the question enters
    # the runtime; actual model output must determine the observed plan/counts.
    return replace(runner.load_dataset().cases[14], question=production.QUESTION,
                   domains=("tax.policy",), requirements=())


def sources():
    return {f"source_{i}": {"chunk": f"chunk-{i}", "sha256": runner.digest(content.encode()), "clause": content}
            for i, content in enumerate(production.CONTENTS, 1)}


async def invoke(tmp_path, monkeypatch, *, fault=None, distinct_queries=False, question=None):
    clients = production.Clients(multi=True, fault=fault if fault in {"denied", "partial", "policy", "all_failed"} else None)
    monkeypatch.setattr(runner.smoke, "build_knowledge_http_client", clients)
    value = production.plan(multi=True)
    if distinct_queries:
        value["queries"][1]["query"] = production.QUESTION + " 税务法律"
    if fault == "invalid_plan": value["requirements"][0]["domain_id"] = "not.enabled"
    if fault == "unsupported":
        value = {"outcome": "unsupported", "question_kind": "none", "queries": [], "requirements": [], "missing_conditions": []}
    model = production.Model(value, fault=fault if fault in {"quote", "wrong_domain", "unknown_ref", "missing_coverage", "insufficient", "second_action"} else None)
    outbound, model_clients = [], []

    async def handler(request):
        index = len(outbound)
        outbound.append(request)
        assert (tmp_path / f"journal-{index + 1:03d}.json").exists()
        assert (tmp_path / "consumed.json").exists()
        assert request.headers["authorization"] == "Bearer " + KEY
        payload = json.loads(request.content)
        if fault == "cancel": raise asyncio.CancelledError()
        if fault == "timeout" and index == 1: raise httpx.ReadTimeout("synthetic-private-error")
        task, version = runner.TASKS[index]
        response = await model.complete(SimpleNamespace(task_id=task, task_version=version,
            max_output_tokens=payload["max_tokens"], user_payload_json=payload["messages"][1]["content"]),
            call_deadline=asyncio.get_running_loop().time() + 5)
        return httpx.Response(200, content=wire("{" if fault == "invalid_output" and index == 1 else response.content),
                              headers={"Content-Type": "application/json"})

    def factory(settings):
        client = httpx.AsyncClient(base_url=ModelSettings.BASE_URL, transport=httpx.MockTransport(handler), trust_env=False)
        model_clients.append(client)
        return client

    required = sources()
    if fault == "source_missing": required["source_1"]["clause"] = "synthetic-absent-anchor"
    try:
        case = fixture_case() if question is None else replace(fixture_case(), question=question)
        row = await runner.measure(case, TOKEN, tmp_path, "a" * 64, runner.smoke.LocalBudget(),
            ModelSettings(provider=ModelProvider.DEEPSEEK, api_key=ModelApiKey(KEY)), required, client_factory=factory)
        return row, outbound
    finally:
        assert all(c.is_closed for c in clients.clients + model_clients)


@pytest.mark.asyncio
@pytest.mark.parametrize("distinct_queries", [False, True])
async def test_full_current_root_uses_actual_wire_planning_and_post_source_binding(tmp_path, monkeypatch, caplog, distinct_queries):
    original = runner.smoke.FixedModel.complete
    async def forbidden(*args, **kwargs): pytest.fail("fixed planning must be unreachable")
    monkeypatch.setattr(runner.smoke.FixedModel, "complete", forbidden)
    row, outbound = await invoke(tmp_path, monkeypatch, distinct_queries=distinct_queries)
    assert row["passed"] and row["status"] == "success", row
    assert len(outbound) == row["externalModelCalls"] == 3
    assert row["counts"] == {"search": 4, "embedding": 2 if distinct_queries else 1, "rerank": 3}
    assert row["retrievalPathsComplete"] and row["plan"]["domains"] == ["tax.policy", "tax.law"]
    assert len(row["plan"]["requirements"]) == 3  # Not the fixture's empty tuple.
    assert row["sourceCheck"]["binding_valid"] and all(hit for _, hit in row["sourceCheck"]["required_clauses"])
    assert row["validation"] == {"phases": ["coverage", "extractive"], "failures": []}
    assert [s["taskVersion"] for s in row["modelTaskStates"]] == ["action-selection-v4", "8", "7"]
    visible = json.dumps(row, ensure_ascii=False) + caplog.text + "".join(p.read_text() for p in tmp_path.iterdir())
    assert all(term not in visible for term in production.CONTENTS + production.FOCUSES + (production.QUESTION, KEY, TOKEN))
    assert runner.smoke.FixedModel.complete is forbidden and original is not forbidden


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,paid,status", [
    ("denied", 2, "forbidden"), ("policy", 2, "model_egress_denied"),
    ("partial", 2, "downstream_failure"), ("all_failed", 2, "downstream_failure"),
    ("invalid_plan", 2, "downstream_failure"), ("invalid_output", 2, "downstream_failure"),
    ("unsupported", 2, "no_result"), ("second_action", 1, "downstream_failure"),
    ("timeout", 2, "timeout"), ("quote", 3, "downstream_failure"),
    ("wrong_domain", 3, "downstream_failure"), ("unknown_ref", 3, "downstream_failure"),
    ("missing_coverage", 3, "downstream_failure"), ("insufficient", 3, "no_result"),
    ("source_missing", 3, "success"),
])
async def test_failure_never_passes_or_retries_and_remains_finite(tmp_path, monkeypatch, caplog, fault, paid, status):
    originals = (RequirementCoverageValidator.validate, ExtractiveSummaryValidator.validate, DefaultKnowledgeRetrievalStage.execute)
    row, outbound = await invoke(tmp_path, monkeypatch, fault=fault)
    assert not row["passed"] and row["status"] == status
    assert row["externalModelCalls"] == len(outbound) == paid
    assert len(list(tmp_path.glob("journal-*.json"))) == paid
    if fault in {"invalid_plan", "invalid_output", "unsupported", "second_action", "timeout"}:
        assert row["counts"] == {"search": 0, "embedding": 0, "rerank": 0}
    if fault == "partial": assert not row["retrievalPathsComplete"]
    assert (RequirementCoverageValidator.validate, ExtractiveSummaryValidator.validate, DefaultKnowledgeRetrievalStage.execute) == originals
    visible = json.dumps(row, ensure_ascii=False) + caplog.text + "".join(p.read_text() for p in tmp_path.iterdir())
    assert all(term not in visible for term in production.CONTENTS + production.FOCUSES +
               (production.QUESTION, KEY, TOKEN, "synthetic-private-error", "synthetic-absent-anchor"))


@pytest.mark.asyncio
async def test_cancel_preserves_attempt_and_restores_observers(tmp_path, monkeypatch):
    originals = (RequirementCoverageValidator.validate, DefaultKnowledgeRetrievalStage.execute)
    with pytest.raises(asyncio.CancelledError):
        await invoke(tmp_path, monkeypatch, fault="cancel")
    assert (RequirementCoverageValidator.validate, DefaultKnowledgeRetrievalStage.execute) == originals
    assert (tmp_path / "consumed.json").exists() and len(list(tmp_path.glob("journal-*.json"))) == 1


@pytest.mark.parametrize("extra", ["started.json", "consumed.json", "result.json", "journal-001.json"])
def test_restart_is_blocked_even_without_outbound(tmp_path, monkeypatch, extra):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    runner.save(tmp_path / "manifest.json", {})
    runner.save(tmp_path / extra, {})
    monkeypatch.setattr(runner, "manifest", lambda: pytest.fail("cannot reach preflight"))
    with pytest.raises(runner.smoke.SmokeFailure, match="retry_resume_forbidden"):
        runner.execute("a" * 64)


def test_frozen_binding_checked_before_started(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    runner.save(tmp_path / "manifest.json", {"version": 1})
    monkeypatch.setattr(runner, "manifest", lambda: {"version": 2})
    with pytest.raises(runner.smoke.SmokeFailure, match="binding_changed"):
        runner.execute(runner.digest((tmp_path / "manifest.json").read_bytes()))
    assert {p.name for p in tmp_path.iterdir()} == {"manifest.json"}


@pytest.mark.asyncio
async def test_wire_exact_url_payload_and_once_per_ordinal(tmp_path):
    settings = ModelSettings(provider=ModelProvider.DEEPSEEK, api_key=ModelApiKey(KEY))
    model = runner.CurrentModel(tmp_path, "a" * 64, settings, client_factory=lambda _: httpx.AsyncClient())
    try:
        model.calls = ["action_selection"]
        model.inflight, model.expected = True, b"approved"
        for url, raw in ((ModelSettings.BASE_URL + "/chat/completions", b"wrong"), ("https://example.org", b"approved")):
            with pytest.raises(runner.smoke.SmokeFailure, match="model_outbound_forbidden"):
                await model.outbound(httpx.Request("POST", url, content=raw))
        assert model.paid == 0 and not list(tmp_path.iterdir())
        request = httpx.Request("POST", ModelSettings.BASE_URL + "/chat/completions", content=b"approved")
        await model.outbound(request)
        with pytest.raises(runner.smoke.SmokeFailure, match="model_outbound_forbidden"):
            await model.outbound(request)
        assert model.paid == 1
    finally:
        await model.close()


def test_current_case_expectations_are_preexisting_and_finite():
    dataset = runner.load_dataset()
    case = next(c for c in dataset.cases if c.id == runner.CASE_ID)
    assert case.sources == ("software", "vat_rate")
    required = runner.required_sources(dataset, case)
    assert 1 <= len(required) <= 5
    assert len(required) == sum(len(s.anchors) for s in dataset.sources if s.id in case.sources)
    assert runner.LIMITS["model"] == 3 and runner.LIMITS["runtime"] == 1


@pytest.mark.asyncio
async def test_sensitive_input_zero_wire_and_zero_local(tmp_path, monkeypatch):
    row, outbound = await invoke(tmp_path, monkeypatch, question="税务test@example.com")
    assert row["status"] == "model_egress_denied" and not row["passed"]
    assert not outbound and not list(tmp_path.iterdir())
    assert row["counts"] == {"search": 0, "embedding": 0, "rerank": 0}


@pytest.mark.asyncio
async def test_task_order_and_local_total_cannot_be_extended(tmp_path, monkeypatch):
    model = runner.CurrentModel(tmp_path, "a" * 64,
        ModelSettings(provider=ModelProvider.DEEPSEEK, api_key=ModelApiKey(KEY)),
        client_factory=lambda _: httpx.AsyncClient())
    try:
        request = SimpleNamespace(task_id=runner.TASKS[2][0], task_version="7")
        with pytest.raises(runner.smoke.SmokeFailure, match="model_task_forbidden"):
            await model.complete(request, call_deadline=10)
        model.calls, model.paid = [t.value for t, _ in runner.TASKS], 3
        with pytest.raises(runner.smoke.SmokeFailure, match="model_task_forbidden"):
            await model.complete(request, call_deadline=10)
        assert not list(tmp_path.iterdir())
    finally:
        await model.close()
    monkeypatch.setattr(runner.smoke, "LIMITS", runner.LOCAL_LIMITS)
    budget = runner.smoke.LocalBudget()
    request = httpx.Request("POST", "http://127.0.0.1:19201/es/knowledge/search")
    for _ in range(4): await budget.request(request)
    with pytest.raises(runner.smoke.SmokeFailure, match="local_budget_exhausted"):
        await budget.request(request)
    assert budget.stopped and budget.counts["search"] == 4


@pytest.mark.parametrize("failure", [None, "case", "cleanup", "snapshot", "cancel"])
def test_execute_lifecycle_result_is_exclusive_finite_and_fail_closed(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "verify_compiled_profile", lambda: None)
    frozen = {"artifacts": {}, "localModels": {}}
    monkeypatch.setattr(runner, "manifest", lambda: frozen)
    runner.save(tmp_path / "manifest.json", frozen)
    binding = runner.digest((tmp_path / "manifest.json").read_bytes())
    events = []

    @contextmanager
    def services(binding, alias, terminal):
        events.append("ready")
        try:
            yield {"admin": TOKEN}
        finally:
            terminal.update(ownedProcessesStopped=True, rawLogsDeleted=failure != "cleanup", secretScanPassed=True)
            events.append("closed")

    support = SimpleNamespace(PORTS=(), checked_bytes=lambda *a: b'{"readAlias":"synthetic"}',
        java_executable=lambda: None, isolated_services=services)
    monkeypatch.setattr(runner.smoke.support_source, "load_support", lambda: support)
    def check_index(*args):
        if failure == "snapshot" and "closed" in events: raise ValueError("synthetic-private-error")
    monkeypatch.setattr(runner.smoke.support_source, "check_index", check_index)
    monkeypatch.setattr(runner.support_tools, "artifacts", lambda: {})
    monkeypatch.setattr(runner.smoke.support_source, "local_models", lambda: {})
    async def warmup(): events.append("warmup")
    monkeypatch.setattr(runner.runpy, "run_path", lambda *args: {"warmup": warmup})
    def settings(env):
        assert events == ["warmup", "ready"]
        events.append("key")
        return ModelSettings(provider=ModelProvider.DEEPSEEK, api_key=ModelApiKey(KEY))
    monkeypatch.setattr(runner.ModelSettings, "from_env", settings)
    monkeypatch.setenv("LLM_API_KEY", KEY)
    async def measure(*args):
        assert events[-1] == "key"
        runner.save(tmp_path / "consumed.json", {"runId": runner.RUN_ID})
        for ordinal in range(1, 4): runner.save(tmp_path / f"journal-{ordinal:03d}.json", {"ordinal": ordinal})
        if failure == "cancel": raise asyncio.CancelledError()
        return {"passed": failure != "case"}
    monkeypatch.setattr(runner, "measure", measure)
    result = runner.execute(binding)
    assert result["status"] == ("passed" if failure is None else "failed")
    assert result["modelAttempts"] == 3 and result["runtimeCalls"] == 1 and events[-1] == "closed"
    assert (tmp_path / "result.json").exists() and KEY not in (tmp_path / "result.json").read_text()
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(runner.smoke.SmokeFailure, match="retry_resume_forbidden"):
        runner.execute(binding)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
