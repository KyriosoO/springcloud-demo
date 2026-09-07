"""Run-08 stopped at the first failed clarification case; never replay it."""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from tests.system_e2e import test_knowledge_stage_b_run_02_history as history
from tests.system_e2e import knowledge_stage_b_uat_v8 as runner

ROOT = Path(__file__).with_name("knowledge_stage_b_run_08")
HEAD = "1fbd62aeebc01af0951ddcd62281be589f6eba6a"
HASHES = {
    "manifest.json": "73a7fc36587211e211dbae43006207a33e8cc2e34ce6a4d97bfad44db3f5a210",
    "authorization.json": "0c153370e01d2b9f2f9c6f93d6d3846cde17b9f6720be9f27ef300217292476e",
    "environment.jsonl": "2d2c1e39beec6b038ef0b1b4dd727afab69fd0cf7ca44a4c8ac4fad608b9c15f",
    "consumed.json": "970a66e09b02294dbedeefb3c50ca2ef8ba4e9f2daa4265f83be61125537ea32",
    "journal.jsonl": "a5f25a7738064498fcdf9208b3113eccdfb884aead88d5ab0984fe206f67bae9",
    "evidence.jsonl": "f39f15495a1c0bc6557bccfe98102cc345d1238e19304836bc464fb8d29ed9cc",
    "result.json": "cdef650dd3aa78247b98073770635e659bfd92403cffaa3867523feba26253c9",
}


def read(name):
    return runner.strict_json((ROOT / name).read_bytes())


def rows(name):
    return [runner.strict_json(line) for line in (ROOT / name).read_bytes().splitlines()]


def test_bytes_manifest_and_authorization_remain_exact():
    assert {p.name for p in ROOT.iterdir()} == set(HASHES)
    for name, expected in HASHES.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    manifest = read("manifest.json")
    assert set(manifest) == {"schemaVersion", "runId", "frozenHead", "authorizationReference", "limits",
        "cases", "gold", "environment", "indexBinding", "assets", "executables", "taskVersions", "evaluation",
        "promptHashes", "maxOutputTokens", "priorRuns", "cumulativeLimits", "runRoot", "qualityVersion",
        "citationCheckVersion", "datasetSha256"}
    assert type(manifest["schemaVersion"]) is int and manifest["schemaVersion"] == 8
    assert manifest["runId"] == runner.RUN_ID and manifest["frozenHead"] == HEAD
    assert manifest["authorizationReference"] == runner.REFERENCE
    assert manifest["runRoot"] == rf"D:\codex\agent-runtime\target\{runner.RUN_ID}"
    assert len(manifest["assets"]) == 360 and len(manifest["executables"]) == 258
    assert runner.same_json(manifest["cases"], list(runner.CASES)) and manifest["gold"] == runner.GOLD
    assert manifest["taskVersions"] == dict(selection="action-selection-v4", rewrite="7", summary="6")
    assert manifest["qualityVersion"] == "knowledge-retrieval-quality-v3"
    assert manifest["citationCheckVersion"] == "stage-b-citation-binding-v2"
    assert manifest["promptHashes"] == runner.prompt_hashes()
    assert manifest["maxOutputTokens"] == runner.TOKENS
    assert manifest["limits"] == runner.LIMITS and manifest["cumulativeLimits"] == runner.TOTAL_LIMITS
    assert manifest["priorRuns"] == runner.prior_bindings()
    assert manifest["datasetSha256"] == hashlib.sha256(json.dumps(
        dict(cases=runner.CASES, gold=runner.GOLD), sort_keys=True).encode()).hexdigest()
    assert read("authorization.json") == runner.authorization(manifest, HASHES["manifest.json"])
    assert read("consumed.json") == dict(runId=runner.RUN_ID, manifestSha256=HASHES["manifest.json"],
        rule="first_model_http_attempt; no retry/resume")


def test_one_failure_nine_unexecuted_and_exact_budget():
    manifest, result = read("manifest.json"), read("result.json")
    assert set(result) == {"schemaVersion", "runId", "manifestSha256", "status", "failureKind", "cases", "totals", "notExecuted"}
    assert type(result["schemaVersion"]) is int and result["schemaVersion"] == 1
    assert result["runId"] == runner.RUN_ID and result["manifestSha256"] == HASHES["manifest.json"]
    assert result["status"] == "failed" and result["failureKind"] is None
    assert len(result["cases"]) == 1 and result["cases"][0]["caseId"] == "UAT-KB-001"
    assert result["notExecuted"] == [case["caseId"] for case in manifest["cases"]][1:]
    assert result["totals"] == dict(e2e=1, model=2, search=4, embedding=2, rerank=2, business=0, retry=0, resume=0)
    cumulative = dict(e2e=16, model=39, search=27, embedding=14, rerank=14, business=0, retry=0, resume=0)
    for key, value in result["totals"].items():
        assert type(value) is int and 0 <= value <= manifest["limits"][key]
        assert sum(row["calls"][key] for row in result["cases"]) == value
        assert value + sum(row["calls"][key] for row in manifest["priorRuns"]) == cumulative[key]
        assert cumulative[key] <= manifest["cumulativeLimits"][key]


def test_model_trace_is_not_the_http_attempt_ledger():
    row = read("result.json")["cases"][0]
    assert set(row) == {"caseId", "httpStatus", "passed", "status", "reason", "domains", "pointCount",
        "requiredClauseChecks", "citationBindingValid", "citationFailure", "citationCheckVersion",
        "taskBindingValid", "qualityBindingValid", "zeroRetrievalValid", "modelFailures", "calls",
        "modelTasks", "evidenceContentHashes", "retrievalStages"}
    assert row["passed"] is False and row["httpStatus"] == 502 and row["status"] == "downstream_failure"
    assert row["reason"] is None and row["domains"] == ["tax.policy", "tax.law"] and row["pointCount"] == 0
    assert row["requiredClauseChecks"] == {} and row["evidenceContentHashes"] == []
    assert row["taskBindingValid"] is row["qualityBindingValid"] is row["zeroRetrievalValid"] is False
    # These vacuous clarification-case flags do NOT prove Summary/citation success.
    assert row["citationBindingValid"] is True and row["citationFailure"] is None
    failed = dict(taskId="knowledge_summary", taskVersion="6", status="failed", failureKind="provider_failure")
    assert row["modelTasks"] == [
        dict(taskId="action_selection", taskVersion="action-selection-v4", status="succeeded", failureKind=None),
        dict(taskId="knowledge_rewrite", taskVersion="7", status="succeeded", failureKind=None), failed]
    assert row["modelFailures"] == [failed]
    assert rows("journal.jsonl") == [dict(caseId="UAT-KB-001", task=task, ordinal=i + 1)
        for i, task in enumerate(("action_selection", "knowledge_rewrite"))]
    # Summary was blocked locally before count/journal/outbound, not failed by DeepSeek.
    probes = row["retrievalStages"]
    paths = [item for item in probes if item["stage"] == "path"]
    assert {(p["domain"], p["path"]) for p in paths} == {
        (domain, path) for domain in ("tax.policy", "tax.law") for path in ("keyword", "vector")}
    assert [p["status"] for p in paths].count("candidates") == 3
    assert [p["status"] for p in paths].count("no_result") == 1
    assert len([p for p in probes if p["stage"] == "rerank"]) == 2
    assert probes[-1]["stage"] == "evidence" and probes[-1]["sufficient"] is True


def test_environment_cleanup_and_case_evidence_agree():
    environment, evidence = rows("environment.jsonl"), rows("evidence.jsonl")
    assert not any(row["stage"] == "failure" for row in environment + evidence)
    assert environment[0] == evidence[0] == dict(stage="local_model_readiness", embedding=True, rerank=True, model=0)
    assert environment[2] == dict(stage="spring_auth_stub_smoke", status="unsupported", model=0, knowledge=0)
    for records in (environment, evidence):
        assert records[-2:] == [dict(stage="runtime_cleanup", clientsClosed=True), dict(
            stage="cleanup", ownedProcessesStopped=True, rawLogsDeleted=True, secretScanPassed=True)]
    assert [{k: v for k, v in row.items() if k != "stage"} for row in evidence if row["stage"] == "case"] == read("result.json")["cases"]


def test_sources_reconstruct_from_frozen_commit():
    with patch.multiple(history, ROOT=ROOT, HEAD=HEAD):
        history.test_run_02_sources_match_frozen_git_not_current_worktree()


def test_finite_assets_do_not_store_raw_payloads():
    with patch.object(history, "ROOT", ROOT):
        history.test_run_02_finite_evidence_does_not_store_raw_payloads()
    text = "\n".join((ROOT / name).read_text() for name in HASHES if name != "manifest.json")
    assert all(case["question"] not in text for case in runner.CASES)
