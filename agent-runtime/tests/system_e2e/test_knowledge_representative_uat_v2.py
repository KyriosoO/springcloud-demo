"""New authorized batch metadata; reuse V1 fake safety tests without editing history."""
from pathlib import Path
import hashlib
from contextlib import contextmanager
import asyncio
import pytest

from tests.system_e2e import knowledge_representative_uat_v1 as historical_runner
from tests.system_e2e import knowledge_representative_uat_v2 as runner
from tests.system_e2e import test_knowledge_representative_uat_v1 as shared

REPLACEMENTS = [
    (
        "RUN_ID = \"knowledge-representative-uat-v1-20260910-01\"",
        "RUN_ID = \"knowledge-representative-uat-v2-20260910-02\"",
    ),
    (
        "REFERENCE = \"UAT_01:14.51\"",
        "REFERENCE = \"UAT_01:14.54\"",
    ),
    (
        "LIMITS = dict(e2e=10, model=30, search=40, embedding=20, rerank=40, business=0, retry=0, resume=0)",
        "LIMITS = dict(e2e=9, model=27, search=36, embedding=18, rerank=36, business=0, retry=0, resume=0)",
    ),
    (
        "    (\"KRB-015\", ((\"software\", 3), (\"vat_rate\", 1))),\n",
        "",
    ),
    (
        "agent-runtime/tests/system_e2e/test_knowledge_representative_uat_v1.py",
        "agent-runtime/tests/system_e2e/test_knowledge_representative_uat_v2.py",
    ),
    (
        "knownBefore=dict(e2e=23, model=57), cumulativeLimits=dict(e2e=33, model=87)",
        "knownBefore=dict(e2e=25, model=63), cumulativeLimits=dict(e2e=34, model=90)",
    ),
    (
        "cumulativeLimits=dict(e2e=33, model=87)))",
        "cumulativeLimits=dict(e2e=34, model=90)))",
    ),
    (
        "require(len(rows) == 10 and",
        "require(len(rows) == 9 and",
    ),
]


@pytest.fixture(autouse=True)
def current_runner(monkeypatch):
    monkeypatch.setattr(shared, "runner", runner)


def test_only_approved_batch_metadata_differs_from_frozen_runner():
    old = Path(historical_runner.__file__).read_bytes()
    assert hashlib.sha256(old).hexdigest() == "e026f310aadd26af92bbfad3e91682281a21e67c72af57084fc20d139d21adbb"
    expected = old.decode().replace("\r\n", "\n")
    for before, after in REPLACEMENTS:
        assert expected.count(before) == 1
        expected = expected.replace(before, after)
    assert Path(runner.__file__).read_text(encoding="utf-8") == expected


def test_nine_cases_and_cumulative_budget_are_not_an_old_resume():
    rows = runner.cases()
    assert [c["caseId"] for c in rows] == [
        "KRB-006", "KRB-004", "KRB-010", "KRB-011", "KRB-012",
        "KRB-017", "KRB-019", "KRB-021", "KRB-023"]
    assert rows == historical_runner.cases()[1:]
    assert sum(c["split"] == "holdout" for c in rows) == 4
    assert runner.RUN_ID == "knowledge-representative-uat-v2-20260910-02"
    assert runner.REFERENCE == "UAT_01:14.54"
    assert runner.ROOT != historical_runner.ROOT
    assert runner.LIMITS == dict(e2e=9, model=27, search=36, embedding=18,
                                rerank=36, business=0, retry=0, resume=0)


def test_nine_case_budget_and_tenth_attempt_blocked(tmp_path):
    with runner.bindings():
        budget = runner.Budget(tmp_path, "a" * 64, lambda _: None)
        try:
            for spec in runner.cases():
                budget.begin(spec)
                for kind, limit in runner.PER_CASE.items():
                    for _ in range(limit):
                        budget.count(kind)
            assert budget.totals == runner.LIMITS
            with pytest.raises(ValueError, match="case_order_invalid"):
                budget.begin(runner.cases()[0])
        finally:
            budget.journal.close()


test_bad_spring_status_stops_before_next_case = shared.test_bad_spring_status_stops_before_next_case
test_unapproved_downstream_blocked_before_count = shared.test_unapproved_downstream_blocked_before_count
test_strict_json_rejects_ambiguous_values = shared.test_strict_json_rejects_ambiguous_values
test_no_retry_even_without_paid = shared.test_no_retry_even_without_paid
test_exact_frozen_comparison_precedes_started = shared.test_exact_frozen_comparison_precedes_started
test_local_and_model_caps_stop_without_extra_attempt = shared.test_local_and_model_caps_stop_without_extra_attempt
test_exact_model_wire_and_journal_precedes_outbound = shared.test_exact_model_wire_and_journal_precedes_outbound
test_current_9_7_real_decoders_and_safe_evidence = shared.test_current_9_7_real_decoders_and_safe_evidence
test_failure_never_passes_retries_or_leaks = shared.test_failure_never_passes_retries_or_leaks
test_cancellation_closes_clients_keeps_attempt = shared.test_cancellation_closes_clients_keeps_attempt


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
    assert len(result["cases"]) == (1 if failure in {"case", "interrupted"} else 9)
    if failure == "interrupted":
        assert result["cases"][0]["status"] == "request_incomplete"
        assert result["cases"][0]["caseId"] not in result["notExecuted"]
        assert result["failureReason"] == "interrupted"
    assert events == ["warmup", "services", "stub", "live"]
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError, match="retry_resume_forbidden"): runner.execute("a" * 64)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
