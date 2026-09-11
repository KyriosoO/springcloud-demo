"""Four independently authorized cases; immutable V2 plus finite failure observation."""
from pathlib import Path
import hashlib
from contextlib import contextmanager
import asyncio
import json
import pytest

from tests.system_e2e import knowledge_representative_uat_v2 as historical_runner
from tests.system_e2e import knowledge_representative_uat_v3 as runner
from tests.system_e2e import test_knowledge_representative_uat_v1 as shared
from tests.system_e2e import knowledge_model_failure_probe_v1 as probe
from agent_runtime.model import gateway

REPLACEMENTS = [
    [
        "RUN_ID = \"knowledge-representative-uat-v2-20260910-02\"",
        "RUN_ID = \"knowledge-representative-uat-v3-20260911-03\""
    ],
    [
        "REFERENCE = \"UAT_01:14.54\"",
        "REFERENCE = \"UAT_01:14.57\""
    ],
    [
        "LIMITS = dict(e2e=9, model=27, search=36, embedding=18, rerank=36, business=0, retry=0, resume=0)",
        "LIMITS = dict(e2e=4, model=12, search=16, embedding=8, rerank=16, business=0, retry=0, resume=0)"
    ],
    [
        "    (\"KRB-006\", ((\"small_2022\", 1), (\"small_2023\", 2))),\n    (\"KRB-004\", ((\"software\", 2),)), (\"KRB-010\", ((\"iit_deductions\", 1),)),\n    (\"KRB-011\", ((\"declaration\", 1),)), (\"KRB-012\", ((\"resource_use\", 1),)),\n",
        ""
    ],
    [
        "agent-runtime/tests/system_e2e/test_knowledge_representative_uat_v2.py",
        "agent-runtime/tests/system_e2e/test_knowledge_representative_uat_v3.py"
    ],
    [
        "knownBefore=dict(e2e=25, model=63), cumulativeLimits=dict(e2e=34, model=90)",
        "knownBefore=dict(e2e=31, model=80), cumulativeLimits=dict(e2e=35, model=92)"
    ],
    [
        "cumulativeLimits=dict(e2e=34, model=90)))",
        "cumulativeLimits=dict(e2e=35, model=92)))"
    ],
    [
        "require(len(rows) == 9 and",
        "require(len(rows) == 4 and"
    ],
    [
        "from tests.system_e2e.knowledge_summary_diagnostic_v1 import save, validation_observer",
        "from tests.system_e2e.knowledge_summary_diagnostic_v1 import save, validation_observer\nfrom tests.system_e2e.knowledge_model_failure_probe_v1 import observe_failures"
    ],
    [
        "class Budget(service_run.Budget):\n    def begin(self, case):",
        "class Budget(service_run.Budget):\n    def __init__(self, *args, **kwargs):\n        super().__init__(*args, **kwargs)\n        self.failure_collector = None\n        self.failure_start = 0\n\n    def model_failures(self):\n        collector = self.failure_collector\n        if collector is None:\n            return dict(records=[], overflowed=False)\n        if collector.overflowed:\n            self.stopped = True\n        return dict(records=[asdict(item) for item in collector.records[self.failure_start:]],\n                    overflowed=collector.overflowed)\n\n    def begin(self, case):"
    ],
    [
        "        self.validation = dict(phases=[], failures=[])\n",
        "        self.validation = dict(phases=[], failures=[])\n        self.failure_start = len(self.failure_collector.records) if self.failure_collector is not None else 0\n"
    ],
    [
        "        with validation_observer(CurrentValidation()):\n            yield",
        "        with validation_observer(CurrentValidation()), observe_failures() as collector:\n            budget.failure_collector = collector\n            yield"
    ],
    [
        "def assess(case, response, observation, budget):\n",
        "def assess(case, response, observation, budget):\n    model_failure = budget.model_failures()\n"
    ],
    [
        "        requiredSourcesByStage=stage_hits, manualUsefulness=\"not_assessed\")",
        "        requiredSourcesByStage=stage_hits, manualUsefulness=\"not_assessed\", modelFailure=model_failure)"
    ],
    [
        "                           httpStatus=None, calls=dict(budget.per_case), validation=budget.validation)",
        "                           httpStatus=None, calls=dict(budget.per_case), validation=budget.validation,\n                           modelFailure=budget.model_failures())"
    ]
]


ISOLATION_REPLACEMENTS = [
    [
        "from tests.system_e2e import knowledge_stage_b_services as services",
        "from tests.system_e2e import knowledge_representative_services_v3 as services"
    ],
    [
        "digest = service_run.digest",
        "digest = service_run.digest\nENV = {**service_run.ENV, \"AGENT_KNOWLEDGE_ES_BASE_URL\": \"http://127.0.0.1:19401\"}"
    ],
    [
        "patch.multiple(service_run, RUN_ID=RUN_ID, CASES=cases(), LIMITS=LIMITS, REPO=ServiceRoot())",
        "patch.multiple(service_run, RUN_ID=RUN_ID, CASES=cases(), LIMITS=LIMITS, ENV=ENV, REPO=ServiceRoot())"
    ],
    [
        "            require(request.url.port == 19201 or \"authorization\" not in request.headers, \"local_auth_leak\")\n            await super().downstream_request(request)",
        "            endpoints = {\"http://127.0.0.1:19401/es/knowledge/search\": \"search\",\n                         \"http://127.0.0.1:8908/embed\": \"embedding\", \"http://127.0.0.1:8909/rerank\": \"rerank\"}\n            require(request.url.port == 19401 or \"authorization\" not in request.headers, \"local_auth_leak\")\n            kind = endpoints.get(str(request.url))\n            require(request.method == \"POST\" and kind is not None, \"unexpected_downstream\")\n            self.count(kind)"
    ],
    [
        "with patch.multiple(service_run, RUN_ID=RUN_ID, CASES=cases(), LIMITS=LIMITS,\n",
        "with patch.multiple(service_run, RUN_ID=RUN_ID, CASES=cases(), LIMITS=LIMITS, ENV=ENV,\n"
    ],
    [
        "for port in (18090, 19201, 18080, 19091):",
        "for port in (18090, 19401, 18080, 19091):"
    ]
]


@pytest.fixture(autouse=True)
def current_runner(monkeypatch):
    monkeypatch.setattr(shared, "runner", runner)


def test_only_approved_batch_metadata_differs_from_frozen_runner():
    old = Path(historical_runner.__file__).read_bytes()
    assert hashlib.sha256(old).hexdigest() == "5b28659a63f1df60681ceafb2f87137725891e529b0d71743b05bd011b8e2751"
    expected = old.decode().replace("\r\n", "\n").rstrip() + "\n"
    for before, after in REPLACEMENTS + ISOLATION_REPLACEMENTS:
        assert expected.count(before) == 1
        expected = expected.replace(before, after)
    assert Path(runner.__file__).read_text(encoding="utf-8") == expected


def test_four_cases_and_cumulative_budget_are_not_an_old_resume():
    rows = runner.cases()
    assert [c["caseId"] for c in rows] == [
        "KRB-017", "KRB-019", "KRB-021", "KRB-023"]
    assert rows == historical_runner.cases()[5:]
    assert sum(c["split"] == "holdout" for c in rows) == 4
    assert runner.RUN_ID == "knowledge-representative-uat-v3-20260911-03"
    assert runner.REFERENCE == "UAT_01:14.57"
    assert runner.ROOT != historical_runner.ROOT
    assert runner.LIMITS == dict(e2e=4, model=12, search=16, embedding=8,
                                rerank=16, business=0, retry=0, resume=0)


def test_four_case_budget_and_fifth_attempt_blocked(tmp_path):
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
    assert len(result["cases"]) == (1 if failure in {"case", "interrupted"} else 4)
    if failure == "interrupted":
        assert result["cases"][0]["status"] == "request_incomplete"
        assert result["cases"][0]["caseId"] not in result["notExecuted"]
        assert result["failureReason"] == "interrupted"
    assert events == ["warmup", "services", "stub", "live"]
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError, match="retry_resume_forbidden"): runner.execute("a" * 64)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}

@pytest.mark.asyncio
@pytest.mark.parametrize("fault,records", [
    (None, []),
    ("invalid_plan", [dict(phase="rewrite_decoder", code="knowledge.invalid_requirement_plan", cause="semantic_contract")]),
    ("invalid_output", [dict(phase="rewrite_decoder", code="knowledge.invalid_requirement_plan", cause="json_syntax")]),
    ("timeout", []),
])
async def test_failure_projection_is_wired_to_actual_runner_without_raw_data(tmp_path, monkeypatch, caplog, fault, records):
    original = gateway.model_call_failed
    row, counts, requests = await shared.invoke(tmp_path, monkeypatch, fault)
    assert row["modelFailure"] == dict(records=records, overflowed=False)
    assert gateway.model_call_failed is original
    assert counts["model"] == requests == (3 if fault is None else 2)
    assert row["passed"] is (fault is None)
    if fault is not None:
        assert counts["search"] == counts["embedding"] == counts["rerank"] == 0
    visible = json.dumps(row) + caplog.text
    assert all(value not in visible for value in shared.production.CONTENTS + shared.production.FOCUSES +
               (shared.KEY, shared.production.QUESTION, "synthetic-private-error", "header.payload.signature"))


def test_failure_projection_does_not_carry_records_across_cases(tmp_path):
    with runner.bindings():
        budget = runner.Budget(tmp_path, "a" * 64, lambda _: None)
        try:
            with runner.observe(budget):
                budget.begin(runner.cases()[0])
                budget.failure_collector.record(None)
                assert budget.model_failures() == dict(records=[dict(phase="unknown", code="unknown", cause="unknown")], overflowed=False)
                budget.begin(runner.cases()[1])
                assert budget.model_failures() == dict(records=[], overflowed=False)
                for _ in range(8):
                    budget.failure_collector.record(None)
                result = budget.model_failures()
                assert result["overflowed"] and budget.stopped and len(result["records"]) <= 8
        finally:
            budget.journal.close()


def test_service_lifecycle_changes_only_reserved_local_es_port():
    old = (Path(runner.__file__).parent / "knowledge_stage_b_services.py").read_bytes()
    assert hashlib.sha256(old).hexdigest() == "cbdd191ee878ee8c1f9c6c3e71d45817362e7cfd1f42337026b6eddae758ff8c"
    expected = old.decode().replace("\r\n", "\n").rstrip().replace("19201", "19401") + "\n"
    assert Path(runner.services.__file__).read_text(encoding="utf-8") == expected
    assert runner.ENV["AGENT_KNOWLEDGE_ES_BASE_URL"] == "http://127.0.0.1:19401"


@pytest.mark.asyncio
@pytest.mark.parametrize("url,allowed", [
    ("http://127.0.0.1:19401/es/knowledge/search", True),
    ("http://127.0.0.1:19201/es/knowledge/search", False),
    ("http://127.0.0.1:19401/es/knowledge/search?x=1", False),
    ("http://127.0.0.1:19401/es/knowledge/other", False),
])
async def test_relocated_endpoint_is_exact_and_old_endpoint_is_denied(tmp_path, url, allowed):
    import httpx
    with runner.bindings():
        budget = runner.Budget(tmp_path, "a" * 64, lambda _: None)
        budget.begin(runner.cases()[0])
        try:
            request = httpx.Request("POST", url, headers={"authorization": "synthetic"})
            if allowed:
                await budget.downstream_request(request)
            else:
                with pytest.raises(ValueError):
                    await budget.downstream_request(request)
            assert budget.totals["search"] == int(allowed)
            assert budget.stopped is not allowed
        finally:
            budget.journal.close()
