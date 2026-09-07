"""Immutable run06 terminal facts; no replay or retrospective model reconstruction."""
import hashlib
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from tests.system_e2e import test_knowledge_stage_b_run_02_history as history
from tests.system_e2e import test_knowledge_stage_b_run_05_history as prior

ROOT = Path(__file__).with_name("knowledge_stage_b_run_06")
HEAD = "9a288f575da110c8127bae05d539780f772c48d3"
RUN_ID = "knowledge-stage-b-uat-v6-20260907-run-06"
HASHES = {
    "manifest.json": "315e129634b0b437336ac632d31755aa5112baecba7a2aeb501a886dc670eee3",
    "environment.jsonl": "ae7eb72e35937dfa8a144093e7d69a408cb2b62c84f5c42885ee5eaad6e4f3c7",
    "consumed.json": "812cd5fc7a29c7bd0596fa237f6a0e67028803db668b412aab44fe7021dfbd1c",
    "journal.jsonl": "436251a9d346c7b91e2083d30ca0ff2271dcd48baf367bb0fb00d5e467b32674",
    "evidence.jsonl": "0a38058905b4171911585faef0225d01674d3d6da4a3d83c11b36e5068abe562",
    "result.json": "20254e46db4c86d6b666b365ec0ecfdf6d260947ebe36288bb71b6440dc14897",
}


def read(name):
    return json.loads((ROOT / name).read_bytes())


def rows(name):
    return [json.loads(line) for line in (ROOT / name).read_bytes().splitlines()]


def test_exact_bytes_and_frozen_bindings():
    assert {p.name for p in ROOT.iterdir()} == set(HASHES)
    for name, sha in HASHES.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha
    manifest, previous = read("manifest.json"), prior.read("manifest.json")
    assert set(manifest) == set(previous) | {"downstreamDiagnosticVersion"}
    assert type(manifest["schemaVersion"]) is int and manifest["schemaVersion"] == 6
    assert manifest["runId"] == RUN_ID and manifest["frozenHead"] == HEAD
    assert manifest["authorizationReference"] == "P3_00:WP-KRETRIEVAL-UAT-01/run-06"
    assert manifest["downstreamDiagnosticVersion"] == "knowledge-downstream-diagnostics-v1"
    for key in ("cases", "gold", "environment", "indexBinding", "limits", "cumulativeLimits", "evaluation",
                "diagnosticVersion", "qualityVersion", "taskVersions", "promptHashes"):
        assert manifest[key] == previous[key]
    assert manifest["priorRuns"][:4] == previous["priorRuns"]
    assert manifest["priorRuns"][4] == dict(runId=prior.RUN_ID, hashes=prior.HASHES,
                                           calls=prior.read("result.json")["totals"])
    assert manifest["runRoot"] == rf"D:\codex\agent-runtime\target\{RUN_ID}"
    assert len(manifest["assets"]) == 332 and len(manifest["executables"]) == 258
    assert read("consumed.json") == dict(runId=RUN_ID, manifestSha256=HASHES["manifest.json"],
        rule="first_model_http_attempt; no retry/resume")


def test_terminal_cases_original_gold_and_cumulative_budget():
    manifest, result = read("manifest.json"), read("result.json")
    assert set(result) == {"schemaVersion", "runId", "manifestSha256", "status", "failureKind", "cases", "totals", "notExecuted"}
    assert type(result["schemaVersion"]) is int and result["schemaVersion"] == 1
    assert result["runId"] == RUN_ID and result["manifestSha256"] == HASHES["manifest.json"]
    assert result["status"] == "failed" and result["failureKind"] is None
    assert result["totals"] == dict(e2e=4, model=10, search=6, embedding=3, rerank=3, business=0, retry=0, resume=0)
    cumulative = dict(e2e=14, model=34, search=21, embedding=11, rerank=11, business=0, retry=0, resume=0)
    for key, value in result["totals"].items():
        assert type(value) is int and 0 <= value <= manifest["limits"][key]
        assert sum(row["calls"][key] for row in result["cases"]) == value
        assert value + sum(row["calls"][key] for row in manifest["priorRuns"]) == cumulative[key]
        assert cumulative[key] <= manifest["cumulativeLimits"][key]
    assert [r["caseId"] for r in result["cases"]] == [r["caseId"] for r in manifest["cases"]][:4]
    assert result["notExecuted"] == [r["caseId"] for r in manifest["cases"]][4:]
    assert [r["passed"] for r in result["cases"]] == [True, True, True, False]
    assert [r["pointCount"] for r in result["cases"]] == [0, 2, 3, 0]
    expected_tasks = [("action_selection", "action-selection-v4"), ("knowledge_rewrite", "6")]
    for i, row in enumerate(result["cases"]):
        assert set(row) == set(prior.read("result.json")["cases"][0]) | {"downstreamCalls"}
        assert row["modelTasks"] == [dict(taskId=task, taskVersion=version, status="succeeded", failureKind=None)
                                    for task, version in expected_tasks + ([("knowledge_summary", "5")] if i in (1, 2) else [])]
        assert row["modelFailures"] == [] and row["zeroRetrievalValid"]
        assert row["qualityBindingValid"] is (i != 3) and row["taskBindingValid"] is (i != 3)
    first, single, dual, rejected = result["cases"]
    assert first["status"] == "no_result" and first["reason"] == "clarification_required"
    assert single["status"] == dual["status"] == "success"
    assert single["domains"] == ["tax.policy"] and dual["domains"] == ["tax.policy", "tax.law"]
    assert single["requiredClauseChecks"] == dict(lodging=True, living=True)
    assert dual["requiredClauseChecks"] == dict(lodging=True, living=True, law_rate=True)
    assert rejected["httpStatus"] == 502 and rejected["status"] == "downstream_failure"
    assert rejected["requiredClauseChecks"] == dict(lodging=False, law_rate=False, law_effective=False)
    for row in (first, rejected):
        assert row["domains"] == row["retrievalStages"] == row["evidenceContentHashes"] == row["downstreamCalls"] == []
        assert row["calls"] == dict(e2e=1, model=2, search=0, embedding=0, rerank=0, business=0, retry=0, resume=0)
    journal = [dict(ordinal=i + 1, caseId=case, task=task) for i, (case, task) in enumerate(
        (r["caseId"], task["taskId"]) for r in result["cases"] for task in r["modelTasks"])]
    assert rows("journal.jsonl") == journal and len(journal) == 10


def test_downstream_finite_contract_and_successful_evidence_probes():
    operation_counts = {"knowledge.embedding": ("embedding", 2), "knowledge.search": ("search", 4),
                        "knowledge.rerank": ("rerank", 2)}
    for row in read("result.json")["cases"]:
        for operation, (key, maximum) in operation_counts.items():
            calls = [item for item in row["downstreamCalls"] if item["operation"] == operation]
            assert len(calls) == row["calls"][key] <= maximum
        for call in row["downstreamCalls"]:
            assert set(call) == {"operation", "status", "httpStatus", "durationMs"}
            assert call["operation"] in operation_counts
            assert call["status"] == "completed" and type(call["httpStatus"]) is int and call["httpStatus"] == 200
            assert type(call["durationMs"]) is int and 0 <= call["durationMs"] <= 2147483647
        if row["pointCount"]:
            assert {"path", "fusion", "rerank", "final_rank", "evidence"}.issubset({p["stage"] for p in row["retrievalStages"]})
            assert row["evidenceContentHashes"]  # Evidence presence is distinct from HTTP success.


def test_readiness_case_evidence_and_owned_cleanup():
    environment, evidence = rows("environment.jsonl"), rows("evidence.jsonl")
    assert environment[1] == dict(stage="spring_auth_stub_smoke", status="unsupported", model=0, knowledge=0)
    assert [{k: v for k, v in row.items() if k != "stage"} for row in evidence if row["stage"] == "case"] == read("result.json")["cases"]
    for records in (environment, evidence):
        assert records[-2:] == [dict(stage="runtime_cleanup", clientsClosed=True), dict(
            stage="cleanup", ownedProcessesStopped=True, rawLogsDeleted=True, secretScanPassed=True)]


def test_sources_from_frozen_git_not_current_root():
    with patch.multiple(history, ROOT=ROOT, HEAD=HEAD):
        history.test_run_02_sources_match_frozen_git_not_current_worktree()


def test_finite_evidence_contains_no_raw_payloads():
    with patch.object(history, "ROOT", ROOT):
        history.test_run_02_finite_evidence_does_not_store_raw_payloads()


def test_frozen_guard_counterexample_is_not_reconstruction_of_live_output():
    path = "agent-runtime/src/agent_runtime/knowledge/question_semantics.py"
    source = subprocess.check_output(["git", "show", f"{HEAD}:{path}"], cwd=history.REPO)
    namespace = {"__name__": "frozen_run06_guard"}
    exec(compile(source, f"{HEAD}:{path}", "exec"), namespace)
    guard = namespace["QuestionSemanticGuard"]()
    original = "一般纳税人采用一般计税方法，2026年提供住宿服务适用何种增值税税率？"
    reordered = "2026年一般纳税人采用一般计税方法提供住宿服务的增值税税率"
    constraints = guard.extract(original)
    assert constraints.numbers == ("一", "一", "2026")
    assert guard.extract(reordered).numbers == ("2026", "一", "一")
    assert guard.validate_candidate(candidate=original, constraints=constraints, max_chars=1024).accepted
    assert not guard.validate_candidate(candidate=reordered, constraints=constraints, max_chars=1024).accepted
    # Never recover a query from hashes, or assert that the model produced this synthetic example.
