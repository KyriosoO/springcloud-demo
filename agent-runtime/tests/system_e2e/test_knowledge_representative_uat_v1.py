"""Real current ModelGateway/HTTP decoders, synthetic network only."""
import asyncio
from contextlib import contextmanager
import json
from types import SimpleNamespace

import httpx
import pytest

from agent_runtime import bootstrap
from agent_runtime.model.contracts import ModelTaskId
from agent_runtime.observation import observation_scope
from tests.helpers import scope
from tests.integration.knowledge import test_requirement_runtime_composition as production
from tests.system_e2e import knowledge_representative_uat_v1 as runner
from tests.system_e2e.test_knowledge_model_failure_probe_v1 import wire

KEY = "synthetic-representative-key"


def test_frozen_pool_keeps_originals_and_exact_anchor_scope():
    rows = runner.cases()
    assert len(rows) == len({r["caseId"] for r in rows}) == 10
    assert sum(r["split"] == "holdout" for r in rows) == 4
    assert list(rows[0]["required"]) == ["software_3", "vat_rate_1"]
    assert list(rows[1]["required"]) == ["small_2022_1", "small_2023_2"]
    assert runner.LIMITS["model"] + 57 == 87 and runner.LIMITS["e2e"] + 23 == 33


def test_whole_batch_maximum_and_eleventh_case_forbidden(tmp_path):
    with runner.bindings():
        budget = runner.Budget(tmp_path, "a" * 64, lambda _: None)
        try:
            for spec in runner.cases():
                budget.begin(spec)
                for kind, limit in runner.PER_CASE.items():
                    for _ in range(limit): budget.count(kind)
            assert budget.totals == runner.LIMITS
            with pytest.raises(ValueError, match="case_order_invalid"): budget.begin(runner.cases()[0])
        finally: budget.journal.close()


@pytest.mark.asyncio
async def test_bad_spring_status_stops_before_next_case(tmp_path):
    with runner.bindings():
        budget = runner.Budget(tmp_path, "a" * 64, lambda _: None)
        budget.begin(runner.cases()[0])
        try:
            with runner.bindings(budget):
                async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(502))) as client:
                    await client.post("http://127.0.0.1:18080/api/v1/agent/queries")
            assert budget.stopped and budget.totals["model"] == 0
            with pytest.raises(ValueError): budget.begin(runner.cases()[1])
        finally: budget.journal.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("url,method,headers", [
    ("http://127.0.0.1:19201/es/knowledge/search", "GET", {}),
    ("http://127.0.0.1:19201/es/knowledge/search?extra=1", "POST", {}),
    ("http://127.0.0.1:8908/embed", "POST", {"authorization": "synthetic"}),
    ("http://127.0.0.1:9210/employees/es/search", "POST", {}),
])
async def test_unapproved_downstream_blocked_before_count(tmp_path, url, method, headers):
    with runner.bindings():
        budget = runner.Budget(tmp_path, "a" * 64, lambda _: None)
        budget.begin(runner.cases()[0])
        try:
            with pytest.raises(ValueError): await budget.downstream_request(httpx.Request(method, url, headers=headers))
            assert budget.stopped and not any(v for k, v in budget.totals.items() if k != "e2e")
        finally: budget.journal.close()


@pytest.mark.parametrize("raw", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'])
def test_strict_json_rejects_ambiguous_values(raw):
    with pytest.raises(ValueError): runner.strict_json(raw)


@pytest.mark.parametrize("name", ["started.json", "authorization.json", "consumed.json", "result.json", "event-001.json"])
def test_no_retry_even_without_paid(tmp_path, monkeypatch, name):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    runner.save(tmp_path / "manifest.json", {})
    runner.save(tmp_path / name, {})
    monkeypatch.setattr(runner, "manifest", lambda: pytest.fail("must stop before preflight"))
    with pytest.raises(ValueError, match="retry_resume_forbidden"): runner.validate_frozen("a" * 64)


@pytest.mark.parametrize("mutation", [{"x": True}, {"x": 2}, {"x": 1, "extra": None}])
def test_exact_frozen_comparison_precedes_started(tmp_path, monkeypatch, mutation):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    runner.save(tmp_path / "manifest.json", {"x": 1})
    monkeypatch.setattr(runner, "manifest", lambda: mutation)
    with pytest.raises(ValueError, match="binding_changed"):
        runner.validate_frozen(runner.digest((tmp_path / "manifest.json").read_bytes()))
    assert not (tmp_path / "started.json").exists()


@pytest.mark.parametrize("kind,limit", list(runner.PER_CASE.items()))
def test_local_and_model_caps_stop_without_extra_attempt(tmp_path, kind, limit):
    with runner.bindings():
        budget = runner.Budget(tmp_path, "a" * 64, lambda _: None)
        try:
            budget.begin(runner.cases()[0])
            for _ in range(limit): budget.count(kind)
            with pytest.raises(ValueError, match="budget_exceeded"): budget.count(kind)
            assert budget.totals[kind] == limit and budget.stopped
        finally: budget.journal.close()


@pytest.mark.asyncio
async def test_exact_model_wire_and_journal_precedes_outbound(tmp_path):
    with runner.bindings():
        budget = runner.Budget(tmp_path, "a" * 64, lambda _: None)
        try:
            budget.begin(runner.cases()[0])
            budget.pending = (b"approved", False)
            request = httpx.Request("POST", runner.service_run.ModelSettings.BASE_URL + "/chat/completions", content=b"approved")
            await budget.model_request(request)
            assert (tmp_path / "consumed.json").exists()
            assert len((tmp_path / "journal.jsonl").read_text().splitlines()) == 1
            with pytest.raises(ValueError, match="unexpected_model_wire"): await budget.model_request(request)
            assert budget.totals["model"] == 1 and budget.stopped
        finally: budget.journal.close()


async def invoke(tmp_path, monkeypatch, fault=None):
    spec = dict(caseId="synthetic", question=production.QUESTION, domains=["tax.policy", "tax.law"],
        split="development", required={f"source_{i}": dict(chunk=f"chunk-{i}", sha256=runner.digest(c.encode()), clause=c)
                                      for i, c in enumerate(production.CONTENTS, 1)})
    monkeypatch.setattr(runner, "cases", lambda: [spec])
    local = production.Clients(multi=True, fault=fault if fault in {"denied", "partial", "policy", "all_failed"} else None)
    output = production.plan(multi=True)
    if fault == "invalid_plan": output["requirements"][0]["domain_id"] = "unknown"
    model = production.Model(output, fault=fault)
    requests, clients = [], []
    with runner.bindings():
        budget = runner.Budget(tmp_path, "a" * 64, lambda _: None)
        budget.begin(spec)

        async def handler(request):
            requests.append(request)
            assert budget.totals["model"] == len(requests)
            assert len((tmp_path / "journal.jsonl").read_text().splitlines()) == len(requests)
            if fault == "cancel": raise asyncio.CancelledError()
            if fault == "timeout" and len(requests) == 2: raise httpx.ReadTimeout("synthetic-private-error")
            body = json.loads(request.content)
            task, version = runner.TASKS[len(requests) - 1]
            response = await model.complete(SimpleNamespace(task_id=ModelTaskId(task), task_version=version,
                max_output_tokens=body["max_tokens"], user_payload_json=body["messages"][1]["content"]),
                call_deadline=asyncio.get_running_loop().time() + 5)
            return httpx.Response(200, content=wire("{" if fault == "invalid_output" and len(requests) == 2 else response.content),
                                  headers={"content-type": "application/json"})

        def model_client(settings):
            client = httpx.AsyncClient(base_url=settings.BASE_URL, transport=httpx.MockTransport(handler), trust_env=False,
                event_hooks={"request": [budget.model_request]})
            clients.append(client)
            return client
        def knowledge_client(url):
            client = local(url)
            client.event_hooks["request"].append(budget.downstream_request)
            return client
        monkeypatch.setattr(bootstrap, "build_deepseek_http_client", model_client)
        root = runner.service_run.build_runtime({**runner.service_run.ENV, "LLM_API_KEY": KEY},
            knowledge_http_client_factory=knowledge_client)
        try:
            with runner.bindings(budget), observation_scope() as collector:
                outcome = await root.ainvoke(question=spec["question"], scope=scope(spec["question"]))
            if fault == "missing_source": spec["required"]["source_1"]["clause"] = "synthetic-absent-anchor"
            # Match the real Spring HTTP JSON, not Runtime's immutable internal tuples.
            public = json.loads(runner.canonical_json_bytes(outcome.user_result)) if outcome.user_result else None
            response = dict(status=outcome.status.value, capabilityId=outcome.capability_id, result=public)
            verdict = runner.assess(spec, response, collector.snapshot(), budget)
            return verdict, dict(budget.totals), len(requests)
        finally:
            await root.aclose()
            budget.journal.close()
            assert all(c.is_closed for c in clients + local.clients)


@pytest.mark.asyncio
async def test_current_9_7_real_decoders_and_safe_evidence(tmp_path, monkeypatch, caplog):
    row, counts, requests = await invoke(tmp_path, monkeypatch)
    assert row["passed"], row
    assert row["taskBindingValid"] and row["retrievalComplete"]
    assert requests == counts["model"] == 3 and counts["search"] == 4
    assert counts["embedding"] == 1 and counts["rerank"] == 3
    visible = json.dumps(row, ensure_ascii=False) + caplog.text + "".join(p.read_text() for p in tmp_path.iterdir())
    assert all(term not in visible for term in production.CONTENTS + production.FOCUSES + (KEY, production.QUESTION, "header.payload.signature"))


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,paid,zero", [
    ("invalid_plan", 2, True), ("invalid_output", 2, True), ("timeout", 2, True), ("second_action", 1, True),
    ("denied", 2, False), ("policy", 2, False), ("all_failed", 2, False), ("partial", 3, False),
    ("quote", 3, False), ("missing_coverage", 3, False), ("duplicate", 3, False),
    ("wrong_domain", 3, False), ("insufficient", 3, False), ("missing_source", 3, False),
])
async def test_failure_never_passes_retries_or_leaks(tmp_path, monkeypatch, caplog, fault, paid, zero):
    row, counts, requests = await invoke(tmp_path, monkeypatch, fault)
    assert not row["passed"]
    assert counts["model"] == requests == paid
    if zero: assert counts["search"] == counts["embedding"] == counts["rerank"] == 0
    visible = json.dumps(row, ensure_ascii=False) + caplog.text + "".join(p.read_text() for p in tmp_path.iterdir())
    assert all(term not in visible for term in production.CONTENTS + production.FOCUSES + (KEY, production.QUESTION, "synthetic-private-error"))


@pytest.mark.asyncio
async def test_cancellation_closes_clients_keeps_attempt(tmp_path, monkeypatch):
    original = runner.DeepSeekChatTransport.complete
    with pytest.raises(asyncio.CancelledError): await invoke(tmp_path, monkeypatch, "cancel")
    assert runner.DeepSeekChatTransport.complete is original
    assert (tmp_path / "consumed.json").exists() and len((tmp_path / "journal.jsonl").read_text().splitlines()) == 1


@pytest.mark.parametrize("failure", [None, "case", "cleanup", "snapshot", "interrupted"])
def test_execution_preflight_stub_then_live_and_terminal_no_resume(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    frozen = {"frozenHead": "a" * 40, "indexBinding": {"readAlias": "synthetic"}}
    runner.save(tmp_path / "manifest.json", frozen)
    monkeypatch.setattr(runner, "manifest", lambda: frozen)
    monkeypatch.setattr(runner, "preflight", lambda _: None)
    events = []
    async def warmup():
        assert (tmp_path / "started.json").exists()
        events.append("warmup")
    monkeypatch.setattr(runner.runpy, "run_path", lambda _: {"warmup": warmup})
    @contextmanager
    def services(emit, **kwargs):
        events.append("services")
        try: yield "synthetic-token", frozen["indexBinding"]
        finally: emit(dict(stage="cleanup", ownedProcessesStopped=True, rawLogsDeleted=failure != "cleanup", secretScanPassed=True))
    monkeypatch.setattr(runner.services, "local_services", services)
    async def server(token, emit, budget):
        if budget is None:
            events.append("stub")
            return []
        assert events == ["warmup", "services", "stub"]
        events.append("live")
        for spec in runner.cases():
            budget.begin(spec)
            if failure == "interrupted": raise asyncio.CancelledError()
            row = dict(caseId=spec["caseId"], passed=failure != "case", httpStatus=200)
            budget.results.append(row)
            if not row["passed"]: budget.stopped = True; break
        return budget.results
    monkeypatch.setattr(runner.service_run, "run_server", server)
    monkeypatch.setattr(runner.support, "load_support", lambda: None)
    def final(*args):
        if failure == "snapshot": raise ValueError("private")
    monkeypatch.setattr(runner.support, "check_index", final)
    result = runner.execute(runner.digest((tmp_path / "manifest.json").read_bytes()))
    assert result["status"] == ("passed" if failure is None else "failed")
    assert len(result["cases"]) == (1 if failure in {"case", "interrupted"} else 10)
    if failure == "interrupted":
        assert result["cases"][0]["status"] == "request_incomplete"
        assert result["cases"][0]["caseId"] not in result["notExecuted"]
        assert result["failureReason"] == "interrupted"
    assert events == ["warmup", "services", "stub", "live"]
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError, match="retry_resume_forbidden"): runner.execute("a" * 64)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
