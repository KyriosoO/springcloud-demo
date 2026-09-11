from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json

import httpx
from agent_runtime import bootstrap
from agent_runtime.model.contracts import ModelTaskId
from agent_runtime.observation import observation_scope
from tests.helpers import scope
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.system_e2e import knowledge_representative_human_uat_v4 as runner
from tests.system_e2e import test_knowledge_representative_uat_v1 as shared
from tests.system_e2e.test_knowledge_human_review import decision, pending, ready_session, sample
from tests.system_e2e.knowledge_human_review import ReviewSession

base = runner.base


def test_new_backend_requires_all_ten_cases_without_reusing_old_passes():
    assert runner.LIMITS == dict(e2e=10, model=30, search=40, embedding=20, rerank=40, business=0, retry=0, resume=0)
    assert runner.RUN_ID == "knowledge-representative-human-uat-v4-20260911-07"
    assert runner.REFERENCE == "UAT_01:14.62"
    assert {"KRB-015", "KRB-006", "KRB-004"}.issubset(item[0] for item in runner.SELECTION)
    from tests.system_e2e import knowledge_model_failure_probe_v3
    with runner.batch():
        assert base.observe_failures is knowledge_model_failure_probe_v3.observe_failures


def test_manifest_binds_current_tools_diagnostic_enums_and_budget(monkeypatch):
    paths = ["agent-runtime/tests/system_e2e/" + name for name in (
        "knowledge_model_failure_probe_v3.py", "knowledge_representative_human_uat_v4.py",
        "test_knowledge_model_failure_probe_v3.py", "test_knowledge_representative_human_uat_v4.py")]
    monkeypatch.setattr(base, "manifest", lambda: dict(assets={}))
    monkeypatch.setattr(base.service_run, "git", lambda *args: "\n".join(paths))
    value = runner.manifest()
    assert value["assets"] == {p: base.digest((base.REPO / p).read_bytes()) for p in paths}
    assert value["knownBefore"] == dict(e2e=41, model=107)
    assert value["cumulativeLimits"] == dict(e2e=51, model=137)
    assert value["failureDiagnostics"] == dict(version=3, details=list(runner.DETAILS))
    assert value["humanReview"]["required"] is True
    assert value["modelWire"]["model"] == "deepseek-flash"
    assert value["modelWire"]["rewritePath"] == "/beta/chat/completions"
    assert value["modelWire"]["otherTaskPath"] == "/chat/completions"
    assert len(value["modelWire"]["outputToolsSha256"]) == 64


def test_scope_and_restoration_do_not_mutate_frozen_runner(tmp_path):
    old = (base.RUN_ID, base.ROOT, base.REFERENCE, base.SELECTION, base.LIMITS, base.TASKS, base.KnowledgeRewriteTaskV9)
    historical_bytes = Path(base.__file__).read_bytes()
    with runner.batch(), base.bindings():
        assert len(base.cases()) == 10
        assert [c["caseId"] for c in base.cases()] == [
            "KRB-015", "KRB-006", "KRB-004", "KRB-010", "KRB-011", "KRB-012", "KRB-017", "KRB-019", "KRB-021", "KRB-023"]
        assert base.LIMITS == runner.LIMITS
        assert base.TASKS == runner.TASKS
        assert base.KnowledgeRewriteTaskV9 is runner.KnowledgeRewriteTaskV10
        budget = base.Budget(tmp_path, "a" * 64, lambda _: None)
        try:
            for spec in base.cases():
                budget.begin(spec)
                for kind, cap in base.PER_CASE.items():
                    for _ in range(cap):
                        budget.count(kind)
            assert budget.totals == runner.LIMITS
            with pytest.raises(ValueError):
                budget.begin(base.cases()[0])
        finally:
            budget.journal.close()
    assert (base.RUN_ID, base.ROOT, base.REFERENCE, base.SELECTION, base.LIMITS, base.TASKS, base.KnowledgeRewriteTaskV9) == old
    assert Path(base.__file__).read_bytes() == historical_bytes


@pytest.mark.parametrize("asset", ["started.json", "authorization.json", "consumed.json", "result.json", "event-001.json"])
def test_never_resumes_historical_or_started_run(tmp_path, monkeypatch, asset):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    base.save(tmp_path / "manifest.json", {})
    base.save(tmp_path / asset, {})
    monkeypatch.setattr(runner, "manifest", lambda: pytest.fail("must stop before manifest computation"))
    with pytest.raises(ValueError, match="retry_resume_forbidden"):
        runner.validate_frozen("a" * 64)


def test_no_human_readiness_means_no_credential_or_services_or_consumption(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "validate_frozen", lambda _: {})
    monkeypatch.setattr(base, "preflight", lambda _: pytest.fail("no dependency access before human readiness"))
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(ValueError, match="human_not_ready"):
        runner.execute("a" * 64, ReviewSession(case_timeout=.01))
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("mutation", [{"x": True}, {"x": 2}, {"x": 1, "extra": None}])
def test_frozen_json_comparison_does_not_conflate_bool_and_int(tmp_path, monkeypatch, mutation):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    base.save(tmp_path / "manifest.json", {"x": 1})
    monkeypatch.setattr(runner, "manifest", lambda: mutation)
    with pytest.raises(ValueError, match="binding_changed"):
        runner.validate_frozen(base.digest((tmp_path / "manifest.json").read_bytes()))
    assert not (tmp_path / "started.json").exists()


@pytest.mark.parametrize("closed", [True, False])
def test_close_or_total_wait_exhaustion_blocks_next_outbound_and_case(tmp_path, closed):
    session = ready_session()
    with runner.batch(), base.bindings():
        budget = runner.HumanBudget(tmp_path, "a" * 64, lambda _: None, session=session)
        try:
            budget.begin(base.cases()[0])
            if closed:
                session.close()
            else:
                session.remaining = 0
            with pytest.raises(ValueError, match="review.stopped"):
                budget.count("model")
            assert budget.totals["model"] == 0
            with pytest.raises(ValueError, match="review.stopped"):
                budget.begin(base.cases()[1])
            assert budget.totals["e2e"] == 1
        finally:
            budget.journal.close()


@pytest.mark.parametrize("human", ["passed", "failed", "timeout"])
def test_automatic_and_human_verdicts_are_separate_and_finite(monkeypatch, human):
    auto = dict(passed=True, manualUsefulness="not_assessed")
    monkeypatch.setattr(base, "assess", lambda *args: dict(auto))
    case, response, summary = sample()
    budget = SimpleNamespace(summary_input=summary, stopped=False)
    session = ready_session(case_timeout=.02 if human == "timeout" else 3)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(runner.assess, case, response, None, budget, session)
        if human != "timeout":
            session.submit(decision(pending(session), useful=human == "passed"))
        result = future.result(timeout=4)
    assert result["automaticPassed"] is True
    assert result["passed"] is (human == "passed")
    assert budget.stopped is (human != "passed")
    assert result["humanReview"]["status"] == ("not_assessed" if human == "timeout" else "assessed")
    assert "合成" not in json.dumps(result, ensure_ascii=False)


def test_automatic_failure_never_opens_manual_approval(monkeypatch):
    monkeypatch.setattr(base, "assess", lambda *args: dict(passed=False, manualUsefulness="not_assessed"))
    session = SimpleNamespace(review=lambda *args: pytest.fail("human cannot override automatic failure"))
    result = runner.assess({}, {}, None, None, session)
    assert result["automaticPassed"] is False and not result["passed"]
    assert result["humanReview"] == dict(status="not_assessed", reason="automatic_failed")


@pytest.mark.asyncio
async def test_actual_current_root_decoders_then_human_wait_make_no_extra_outbound(tmp_path, monkeypatch):
    monkeypatch.setattr(shared, "runner", base)
    automatic = base.assess
    captured = []
    def capture(*args):
        captured.append(args)
        return automatic(*args)
    monkeypatch.setattr(base, "assess", capture)
    with runner.batch():
        initial, counts, requests = await invoke(tmp_path, monkeypatch)
        assert initial["passed"]
        monkeypatch.setattr(base, "assess", automatic)
        session = ready_session()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(runner.assess, *captured[0], session)
            state = pending(session)
            assert state["packet"]["question"] == shared.production.QUESTION
            assert all(e["content"] in shared.production.CONTENTS for e in state["packet"]["evidence"])
            session.submit(decision(state))
            row = future.result(timeout=2)
    assert row["passed"] and row["automaticPassed"] and row["manualUsefulness"] == "passed"
    assert counts["model"] == requests == 3 and counts["search"] == 4
    assert counts["embedding"] == 1 and counts["rerank"] == 3
    text = json.dumps(row, ensure_ascii=False) + "".join(p.read_text() for p in tmp_path.iterdir())
    assert all(v not in text for v in shared.production.CONTENTS + shared.production.FOCUSES +
               (shared.production.QUESTION, shared.KEY, session.token))


@pytest.mark.parametrize("failure", [None, "automatic", "human", "timeout", "cleanup", "snapshot", "cancel"])
def test_complete_or_stop_then_cleanup_terminal_and_no_resume(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    frozen = dict(frozenHead="a" * 40, indexBinding={"readAlias": "synthetic"})
    base.save(tmp_path / "manifest.json", frozen)
    monkeypatch.setattr(runner, "manifest", lambda: frozen)
    monkeypatch.setattr(base, "preflight", lambda _: None)
    events = []
    session = ready_session()
    async def warmup():
        assert session.ready and (tmp_path / "started.json").exists()
        events.append("warmup")
    monkeypatch.setattr(runner.runpy, "run_path", lambda _: {"warmup": warmup})
    @contextmanager
    def services(emit, **kwargs):
        events.append("services")
        try:
            yield "synthetic-jwt", frozen["indexBinding"]
        finally:
            emit(dict(stage="cleanup", ownedProcessesStopped=True,
                rawLogsDeleted=failure != "cleanup", secretScanPassed=True))
    monkeypatch.setattr(base.services, "local_services", services)
    monkeypatch.setattr(base.support, "load_support", lambda: None)
    def check(*args):
        if failure == "snapshot":
            raise ValueError("private source")
    monkeypatch.setattr(base.support, "check_index", check)
    async def server(token, emit, budget):
        if budget is None:
            events.append("stub")
            return []
        assert events == ["warmup", "services", "stub"]
        events.append("live")
        for spec in base.cases():
            budget.begin(spec)
            if failure == "cancel":
                raise asyncio.CancelledError()
            row = dict(caseId=spec["caseId"], passed=failure not in {"automatic", "human", "timeout"}, httpStatus=200)
            budget.results.append(row)
            if not row["passed"]:
                budget.stopped = True
                break
        return budget.results
    monkeypatch.setattr(base.service_run, "run_server", server)
    result = runner.execute(base.digest((tmp_path / "manifest.json").read_bytes()), session)
    assert result["status"] == ("passed" if failure is None else "failed")
    attempted = 1 if failure in {"automatic", "human", "timeout", "cancel"} else 10
    assert len(result["cases"]) == attempted and len(result["notExecuted"]) == 10 - attempted
    assert session.closed and session.token == ""
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError, match="retry_resume_forbidden"):
        runner.execute("a" * 64, ready_session())
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert "private source" not in json.dumps(result)

async def invoke(tmp_path, monkeypatch, fault=None):
    spec = dict(caseId="synthetic", question=shared.production.QUESTION, domains=["tax.policy", "tax.law"],
        split="development", required={f"source_{i}": dict(chunk=f"chunk-{i}", sha256=base.digest(c.encode()), clause=c)
                                      for i, c in enumerate(shared.production.CONTENTS, 1)})
    monkeypatch.setattr(base, "cases", lambda: [spec])
    local = shared.production.Clients(multi=True, fault=fault if fault in {"denied", "partial", "policy", "all_failed"} else None)
    output = shared.production.plan(multi=True)
    if fault == "invalid_plan": output["requirements"][0]["domain_id"] = "unknown"
    model = shared.production.Model(output, fault=fault)
    requests, clients = [], []
    with base.bindings():
        budget = runner.HumanBudget(tmp_path, "a" * 64, lambda _: None, session=ready_session())
        budget.begin(spec)

        async def handler(request):
            requests.append(request)
            assert budget.totals["model"] == len(requests)
            assert len((tmp_path / "journal.jsonl").read_text().splitlines()) == len(requests)
            if fault == "cancel": raise asyncio.CancelledError()
            if fault == "timeout" and len(requests) == 2: raise httpx.ReadTimeout("synthetic-private-error")
            body = json.loads(request.content)
            task, version = base.TASKS[len(requests) - 1]
            response = await model.complete(SimpleNamespace(task_id=ModelTaskId(task), task_version=version,
                max_output_tokens=body["max_tokens"], user_payload_json=body["messages"][1]["content"]),
                call_deadline=asyncio.get_running_loop().time() + 5)
            raw = shared.wire("{" if fault == "invalid_output" and len(requests) == 2 else response.content)
            if response.tool_calls and fault != "invalid_output":
                value = json.loads(raw)
                value["choices"][0]["finish_reason"] = "tool_calls"
                value["choices"][0]["message"]["content"] = None
                value["choices"][0]["message"]["tool_calls"] = [
                    {"id": "synthetic-output", "type": "function", "function":
                        {"name": call.name, "arguments": call.arguments_json}}
                    for call in response.tool_calls]
                raw = json.dumps(value).encode()
            return httpx.Response(200, content=raw, headers={"content-type": "application/json"})

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
        root = base.service_run.build_runtime({**base.service_run.ENV, "LLM_API_KEY": shared.KEY},
            knowledge_http_client_factory=knowledge_client)
        try:
            with base.bindings(budget), observation_scope() as collector:
                outcome = await root.ainvoke(question=spec["question"], scope=scope(spec["question"]))
            if fault == "missing_source": spec["required"]["source_1"]["clause"] = "synthetic-absent-anchor"
            # Match the real Spring HTTP JSON, not Runtime's immutable internal tuples.
            public = json.loads(base.canonical_json_bytes(outcome.user_result)) if outcome.user_result else None
            response = dict(status=outcome.status.value, capabilityId=outcome.capability_id, result=public)
            verdict = base.assess(spec, response, collector.snapshot(), budget)
            return verdict, dict(budget.totals), len(requests)
        finally:
            await root.aclose()
            budget.journal.close()
            assert all(c.is_closed for c in clients + local.clients)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,paid,zero", [
    ("invalid_plan", 2, True), ("invalid_output", 2, True), ("timeout", 2, True), ("second_action", 1, True),
    ("denied", 2, False), ("policy", 2, False), ("all_failed", 2, False), ("partial", 3, False),
    ("quote", 3, False), ("missing_coverage", 3, False), ("duplicate", 3, False),
    ("wrong_domain", 3, False), ("insufficient", 3, False), ("missing_source", 3, False),
])
async def test_current_root_failures_preserve_zero_calls_and_no_leak(tmp_path, monkeypatch, caplog, fault, paid, zero):
    with runner.batch():
        row, counts, requests = await invoke(tmp_path, monkeypatch, fault)
    assert not row["passed"] and counts["model"] == requests == paid
    if zero:
        assert counts["search"] == counts["embedding"] == counts["rerank"] == 0
    text = json.dumps(row, ensure_ascii=False) + caplog.text + "".join(p.read_text() for p in tmp_path.iterdir())
    assert all(v not in text for v in shared.production.CONTENTS + shared.production.FOCUSES +
               (shared.KEY, shared.production.QUESTION, "synthetic-private-error"))


@pytest.mark.asyncio
@pytest.mark.parametrize("ordinal,path", [
    (0, "/beta/chat/completions"), (1, "/chat/completions"), (2, "/beta/chat/completions"),
    (1, "/beta/chat/completions?extra=1"),
])
async def test_wrong_per_task_path_stops_before_payment(tmp_path, ordinal, path):
    with runner.batch(), base.bindings():
        budget = runner.HumanBudget(tmp_path, "a" * 64, lambda _: None, session=ready_session())
        try:
            budget.begin(base.cases()[0])
            budget.task_count = ordinal
            budget.pending = (b"approved", False)
            with pytest.raises(ValueError, match="unexpected_model_wire"):
                await budget.model_request(httpx.Request("POST", base.service_run.ModelSettings.BASE_URL + path, content=b"approved"))
            assert budget.totals["model"] == 0 and budget.stopped
            assert not (tmp_path / "consumed.json").exists()
        finally:
            budget.journal.close()


@pytest.mark.asyncio
async def test_exact_per_task_wire_is_counted_once_before_send(tmp_path):
    with runner.batch(), base.bindings():
        budget = runner.HumanBudget(tmp_path, "a" * 64, lambda _: None, session=ready_session())
        try:
            budget.begin(base.cases()[0])
            for ordinal, path in enumerate(("/chat/completions", "/beta/chat/completions", "/chat/completions"), 1):
                budget.pending = (b"approved", False)
                req = httpx.Request("POST", base.service_run.ModelSettings.BASE_URL + path, content=b"approved")
                await budget.model_request(req)
                assert budget.totals["model"] == ordinal
                assert len((tmp_path / "journal.jsonl").read_text().splitlines()) == ordinal
            with pytest.raises(ValueError, match="unexpected_model_wire"):
                await budget.model_request(req)
            assert budget.totals["model"] == 3
        finally:
            budget.journal.close()


def test_preflight_failure_is_sealed_without_warmup_key_or_outbound(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    frozen = dict(frozenHead="a" * 40, indexBinding={})
    base.save(tmp_path / "manifest.json", frozen)
    monkeypatch.setattr(runner, "manifest", lambda: frozen)
    def fail(_):
        assert (tmp_path / "started.json").exists()
        raise ValueError("private-preflight-detail")
    monkeypatch.setattr(base, "preflight", fail)
    monkeypatch.setattr(runner.runpy, "run_path", lambda _: pytest.fail("no warmup"))
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    session = ready_session()
    result = runner.execute(base.digest((tmp_path / "manifest.json").read_bytes()), session)
    assert result["status"] == "failed" and result["startupRerank"] == 0
    assert not any(result["totals"].values()) and result["cases"] == []
    assert len(result["notExecuted"]) == 10 and session.closed
    assert not (tmp_path / "consumed.json").exists()
    assert "private-preflight-detail" not in json.dumps(result)
    with pytest.raises(ValueError, match="retry_resume_forbidden"):
        runner.execute("a" * 64, ready_session())
