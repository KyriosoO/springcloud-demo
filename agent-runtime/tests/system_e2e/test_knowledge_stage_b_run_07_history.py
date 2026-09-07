"""Immutable run07 facts: one measured failure, six unexecuted, no replay."""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from tests.system_e2e import test_knowledge_stage_b_run_02_history as history
from tests.system_e2e import test_knowledge_stage_b_run_06_history as prior

ROOT = Path(__file__).with_name("knowledge_stage_b_run_07")
HEAD = "806e1568c694a95769852a47e6c7ff00ec5b1f5a"
RUN_ID = "knowledge-stage-b-uat-v7-20260907-run-07"
HASHES = {
    "manifest.json": "ec02be380e4528ade13a6a4eb38a57436270a83b5c9fe78ad52a7b63b7a0e12c",
    "environment.jsonl": "ae7eb72e35937dfa8a144093e7d69a408cb2b62c84f5c42885ee5eaad6e4f3c7",
    "consumed.json": "c7af33c643f19ded61ea87f0b5410fa0cd4709735c08353e7e226a0e615e90dd",
    "journal.jsonl": "2f25b9a09b510579f02063ac88c7837ce58e68c3c4c7579119d58265420d45c3",
    "evidence.jsonl": "feeab5a3fa3bc26e8c1b75801e9ef7751524e694b39f42d99ab699a8d0e46d99",
    "result.json": "4fea1e2654825d18bd31b156b75cb8d5b6e2393b36504e5ec7c1a0c704e28aff",
}


def read(name):
    return json.loads((ROOT / name).read_bytes())


def rows(name):
    return [json.loads(line) for line in (ROOT / name).read_bytes().splitlines()]


def test_exact_bytes_and_seven_case_frozen_binding():
    assert {p.name for p in ROOT.iterdir()} == set(HASHES)
    for name, sha in HASHES.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha
    manifest, previous = read("manifest.json"), prior.read("manifest.json")
    assert set(manifest) == set(previous) | {"reusedEvidence"}
    assert type(manifest["schemaVersion"]) is int and manifest["schemaVersion"] == 7
    assert manifest["runId"] == RUN_ID and manifest["frozenHead"] == HEAD
    assert manifest["authorizationReference"] == "P3_00:WP-KRETRIEVAL-UAT-01/run-07"
    assert manifest["runRoot"] == rf"D:\codex\agent-runtime\target\{RUN_ID}"
    assert len(manifest["assets"]) == 342 and len(manifest["executables"]) == 258
    assert manifest["cases"] == previous["cases"][3:]
    for key in ("gold", "environment", "indexBinding", "evaluation", "executables", "diagnosticVersion",
                "downstreamDiagnosticVersion", "qualityVersion", "taskVersions", "promptHashes"):
        assert manifest[key] == previous[key]
    assert manifest["priorRuns"] == previous["priorRuns"] + [dict(
        runId=prior.RUN_ID, hashes=prior.HASHES, calls=prior.read("result.json")["totals"])]
    assert manifest["limits"] == dict(e2e=7, model=21, search=28, embedding=14, rerank=14, business=0, retry=0, resume=0)
    assert manifest["cumulativeLimits"] == {**previous["cumulativeLimits"], "e2e": 21}
    assert read("consumed.json") == dict(runId=RUN_ID, manifestSha256=HASHES["manifest.json"],
        rule="first_model_http_attempt; no retry/resume")


def test_reused_successes_are_not_new_execution_rows():
    from tests.system_e2e.knowledge_stage_b_uat_v7 import validate_reuse
    manifest = read("manifest.json")
    assert manifest["reusedEvidence"] == dict(runId=prior.RUN_ID, frozenHead=prior.HEAD,
        resultSha256=prior.HASHES["result.json"], caseIds=["UAT-KB-001", "UAT-KB-015a", "UAT-KB-004"],
        compatibilityVersion="stage-b-guard-reuse-v1",
        compatibleSourceCommit="550b012ad390463816372054d1c87f5877209f40")
    validate_reuse(manifest)  # Frozen manifest to frozen source, not current executables.
    assert all(row["passed"] is True for row in prior.read("result.json")["cases"][:3])
    assert {row["caseId"] for row in read("result.json")["cases"]} == {"UAT-KB-002"}


def test_terminal_failure_and_exact_cumulative_ledger():
    manifest, result = read("manifest.json"), read("result.json")
    assert set(result) == set(prior.read("result.json"))
    assert type(result["schemaVersion"]) is int and result["schemaVersion"] == 1
    assert result["runId"] == RUN_ID and result["manifestSha256"] == HASHES["manifest.json"]
    assert result["status"] == "failed" and result["failureKind"] is None
    assert result["totals"] == dict(e2e=1, model=3, search=2, embedding=1, rerank=1, business=0, retry=0, resume=0)
    cumulative = dict(e2e=15, model=37, search=23, embedding=12, rerank=12, business=0, retry=0, resume=0)
    for key, value in result["totals"].items():
        assert type(value) is int and 0 <= value <= manifest["limits"][key]
        assert sum(row["calls"][key] for row in result["cases"]) == value
        assert value + sum(row["calls"][key] for row in manifest["priorRuns"]) == cumulative[key]
        assert cumulative[key] <= manifest["cumulativeLimits"][key]
    assert len(result["cases"]) == 1
    assert result["notExecuted"] == [item["caseId"] for item in manifest["cases"]][1:]
    row = result["cases"][0]
    assert set(row) == set(prior.read("result.json")["cases"][0])
    assert row["caseId"] == "UAT-KB-002" and row["passed"] is False
    assert row["httpStatus"] == 200 and row["status"] == "success" and row["reason"] is None
    assert row["domains"] == row["citationDomains"] == ["tax.law"] and row["pointCount"] == 1
    assert row["requiredClauseChecks"] == dict(lodging=False, law_rate=True, law_effective=False)
    assert row["qualityBindingValid"] and row["taskBindingValid"] and row["zeroRetrievalValid"]
    assert row["modelFailures"] == []
    tasks = [("action_selection", "action-selection-v4"), ("knowledge_rewrite", "6"), ("knowledge_summary", "5")]
    assert row["modelTasks"] == [dict(taskId=task, taskVersion=version, status="succeeded", failureKind=None)
                                 for task, version in tasks]
    assert rows("journal.jsonl") == [dict(ordinal=i + 1, caseId="UAT-KB-002", task=task)
                                     for i, (task, _) in enumerate(tasks)]


def test_finite_rank_diagnosis_distinguishes_missing_domain_and_evidence_truncation():
    manifest, row = read("manifest.json"), read("result.json")["cases"][0]
    def ranks(probe, gold):
        return [i + 1 for i, item in enumerate(probe["candidates"])
                if item["sha256"] == manifest["gold"][gold]["sha256"]]
    probes = row["retrievalStages"]
    assert [p["stage"] for p in probes] == ["path", "path", "fusion", "fusion", "rerank", "final_rank", "evidence"]
    assert not any(ranks(p, "lodging") for p in probes)
    paths = {p["path"]: p for p in probes if p["stage"] == "path"}
    assert set(paths) == {"keyword", "vector"} and all(p["domain"] == "tax.law" for p in paths.values())
    assert ranks(paths["vector"], "law_rate") == [1] and ranks(paths["vector"], "law_effective") == [12]
    assert ranks(paths["keyword"], "law_effective") == []
    for probe in [p for p in probes if p["stage"] == "fusion"]:
        assert ranks(probe, "law_rate") == [8] and ranks(probe, "law_effective") == [21]
    for stage in ("rerank", "final_rank"):
        probe = next(p for p in probes if p["stage"] == stage)
        assert ranks(probe, "law_rate") == [3] and ranks(probe, "law_effective") == [15]
    evidence = probes[-1]
    assert evidence["sufficient"] is True and len(evidence["candidates"]) == 8
    assert ranks(evidence, "law_effective") == [] and ranks(evidence, "law_rate") == [3]
    assert row["evidenceContentHashes"] == [item["sha256"] for item in evidence["candidates"]]


def test_downstream_was_healthy_and_owned_resources_cleaned():
    row = read("result.json")["cases"][0]
    assert [call["operation"] for call in row["downstreamCalls"]] == [
        "knowledge.embedding", "knowledge.search", "knowledge.search", "knowledge.rerank"]
    for call in row["downstreamCalls"]:
        assert set(call) == {"operation", "status", "httpStatus", "durationMs"}
        assert call["status"] == "completed" and type(call["httpStatus"]) is int and call["httpStatus"] == 200
        assert type(call["durationMs"]) is int and 0 <= call["durationMs"] <= 2147483647
    environment, evidence = rows("environment.jsonl"), rows("evidence.jsonl")
    assert environment[1] == dict(stage="spring_auth_stub_smoke", status="unsupported", model=0, knowledge=0)
    assert [{k: v for k, v in item.items() if k != "stage"} for item in evidence if item["stage"] == "case"] == [row]
    for records in (environment, evidence):
        assert records[-2:] == [dict(stage="runtime_cleanup", clientsClosed=True), dict(
            stage="cleanup", ownedProcessesStopped=True, rawLogsDeleted=True, secretScanPassed=True)]


def test_sources_match_frozen_commit_not_current_worktree():
    with patch.multiple(history, ROOT=ROOT, HEAD=HEAD):
        history.test_run_02_sources_match_frozen_git_not_current_worktree()


def test_evidence_does_not_persist_raw_model_or_business_payloads():
    with patch.object(history, "ROOT", ROOT):
        history.test_run_02_finite_evidence_does_not_store_raw_payloads()
