"""Read-only terminal audit: run05 timed out; never resume it or reinterpret its gold."""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from tests.system_e2e import test_knowledge_stage_b_run_02_history as history
from tests.system_e2e import test_knowledge_stage_b_run_04_history as prior

ROOT = Path(__file__).with_name("knowledge_stage_b_run_05")
HEAD = "91c1266f2df913609406bc3b53127585923f0625"
RUN_ID = "knowledge-stage-b-uat-v5-20260904-run-05"
HASHES = {
    "manifest.json": "1910e8a1c3ef31aa232031b48c2df7e61edc1f41e74c3234cdbab880afd80bbd",
    "environment.jsonl": "9e54ca56bef6c43b53f99963b2bb5348f63672340bdb0c86aec79ccffbf3e681",
    "environment-recovered.jsonl": "ae7eb72e35937dfa8a144093e7d69a408cb2b62c84f5c42885ee5eaad6e4f3c7",
    "consumed.json": "9d01af797de6314a93840bc0c3904437757e227ea2a66a9f228a1d33a23ba73c",
    "journal.jsonl": "0bf32c39e1021482bcd71ef3ee46c2f8fecb54db14b983accfaf097d4b9aed67",
    "evidence.jsonl": "3bde6582172b6436d8ec65dbb5aab4d9e5f16128e399b8644ca23de8b7f9f455",
    "result.json": "075c2549f7545ab02961f872c37e8789176f7ad6c69b3f3773740ffd638e0c0c",
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
    assert set(manifest) == set(previous) | {"qualityVersion"}
    assert type(manifest["schemaVersion"]) is int and manifest["schemaVersion"] == 5
    assert manifest["runId"] == RUN_ID and manifest["frozenHead"] == HEAD
    assert manifest["authorizationReference"] == "P3_00:WP-KRETRIEVAL-UAT-01/run-05"
    assert manifest["diagnosticVersion"] == "stage-b-failure-diagnostics-v3"
    assert manifest["qualityVersion"] == "knowledge-retrieval-quality-v2"
    assert manifest["taskVersions"] == dict(selection="action-selection-v4", rewrite="6", summary="5")
    assert manifest["promptHashes"] == {
        "action_selection": "fe0dc57fe758641e447fd4635f030b0b9d84225972dff9fef127d16fe04baf4f",
        "knowledge_rewrite": "e27d645cb7816127e904ef9ea3c91453045b56f3f61507fd5c8fb93ce0725b2b",
        "knowledge_summary": "fee1a061fd68f49198a8832e222cdebdb6ec6f78cf95b48f5f10fd6bdc494e96",
    }
    for key in ("cases", "gold", "environment", "indexBinding", "limits", "cumulativeLimits", "evaluation"):
        assert manifest[key] == previous[key]
    assert manifest["priorRuns"][:3] == previous["priorRuns"]
    assert manifest["priorRuns"][3] == dict(runId=prior.RUN_ID, hashes=prior.HASHES,
                                           calls=prior.read("result.json")["totals"])
    assert manifest["runRoot"] == rf"D:\codex\agent-runtime\target\{RUN_ID}"
    assert len(manifest["assets"]) == 321 and len(manifest["executables"]) == 258
    assert read("consumed.json") == dict(runId=RUN_ID, manifestSha256=HASHES["manifest.json"],
        rule="first_model_http_attempt; no retry/resume")


def test_failure_and_cumulative_budget_never_imply_unexecuted_passed():
    manifest, result = read("manifest.json"), read("result.json")
    assert set(result) == {"schemaVersion", "runId", "manifestSha256", "status", "failureKind", "cases", "totals", "notExecuted"}
    assert type(result["schemaVersion"]) is int and result["schemaVersion"] == 1
    assert result["runId"] == RUN_ID and result["manifestSha256"] == HASHES["manifest.json"]
    assert result["status"] == "failed" and result["failureKind"] is None
    assert result["totals"] == dict(e2e=2, model=4, search=1, embedding=1, rerank=1, business=0, retry=0, resume=0)
    cumulative = dict(e2e=10, model=24, search=15, embedding=8, rerank=8, business=0, retry=0, resume=0)
    for key, value in result["totals"].items():
        assert type(value) is int and 0 <= value <= manifest["limits"][key]
        assert sum(row["calls"][key] for row in result["cases"]) == value
        assert value + sum(row["calls"][key] for row in manifest["priorRuns"]) == cumulative[key]
        assert cumulative[key] <= manifest["cumulativeLimits"][key]
    assert [row["caseId"] for row in result["cases"]] == ["UAT-KB-001", "UAT-KB-015a"]
    assert result["notExecuted"] == [row["caseId"] for row in manifest["cases"]][2:]
    first, second = result["cases"]
    assert [row["passed"] for row in result["cases"]] == [True, False]
    assert first["httpStatus"] == 200 and first["status"] == "no_result" and first["reason"] == "clarification_required"
    assert first["domains"] == first["retrievalStages"] == first["evidenceContentHashes"] == []
    assert second["httpStatus"] == 504 and second["status"] == "timeout" and second["reason"] is None
    assert second["domains"] == ["tax.policy"] and second["requiredClauseChecks"] == dict(lodging=False, living=False)
    assert second["taskBindingValid"] is False  # Missing summary, not a task-version mismatch.
    for row in result["cases"]:
        assert row["modelTasks"] == [dict(taskId=task, taskVersion=version, status="succeeded", failureKind=None)
                                     for task, version in (("action_selection", "action-selection-v4"), ("knowledge_rewrite", "6"))]
        assert row["modelFailures"] == [] and row["qualityBindingValid"] and row["zeroRetrievalValid"]
        assert row["pointCount"] == 0 and row["evidenceContentHashes"] == []
    assert rows("journal.jsonl") == [dict(ordinal=i + 1, caseId=case, task=task)
        for i, (case, task) in enumerate((case, task) for case in ("UAT-KB-001", "UAT-KB-015a")
                                       for task in ("action_selection", "knowledge_rewrite"))]


def test_probe_location_is_not_a_semantic_quality_verdict():
    second = read("result.json")["cases"][1]
    probes = second["retrievalStages"]
    assert [row["stage"] for row in probes] == ["path", "fusion", "fusion"]
    assert probes[0]["domain"] == "tax.policy" and probes[0]["path"] == "keyword"
    assert all(len(row["candidates"]) == 20 for row in probes)
    assert not any(row["stage"] in {"rerank", "final_rank", "evidence"} for row in probes)
    # The finite schema cannot distinguish the lost embedding path's exact exception.
    assert second["calls"]["rerank"] == 1 and second["calls"]["search"] == 1


def test_prior_environment_failure_and_recovery_both_retained():
    assert rows("environment.jsonl") == [dict(stage="failure", kind="PermissionError")]
    environment, evidence = rows("environment-recovered.jsonl"), rows("evidence.jsonl")
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
