from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.system_e2e import knowledge_representative_human_uat_v1 as runner
from tests.system_e2e import test_knowledge_representative_uat_v1 as shared
from tests.system_e2e.test_knowledge_human_review import decision, pending, ready_session, sample
from tests.system_e2e.knowledge_human_review import ReviewSession

base = runner.base


def test_scope_and_restoration_do_not_mutate_frozen_runner(tmp_path):
    old = (base.RUN_ID, base.ROOT, base.REFERENCE, base.SELECTION, base.LIMITS)
    historical_bytes = Path(base.__file__).read_bytes()
    with runner.batch(), base.bindings():
        assert len(base.cases()) == 10
        assert base.cases()[0]["caseId"] == "KRB-015"
        assert base.LIMITS == runner.LIMITS
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
    assert (base.RUN_ID, base.ROOT, base.REFERENCE, base.SELECTION, base.LIMITS) == old
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
        initial, counts, requests = await shared.invoke(tmp_path, monkeypatch)
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
