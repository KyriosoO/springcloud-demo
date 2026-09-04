"""Validate consumed run-02 evidence without executing or resuming its launcher."""
import hashlib
import json
from pathlib import Path
import subprocess

from tests.system_e2e.test_knowledge_stage_b_run_01_history import HASHES as PRIOR_HASHES


ROOT = Path(__file__).with_name("knowledge_stage_b_run_02")
REPO = Path(__file__).resolve().parents[3]
HEAD = "501bca8b68c6efef9931c7dfbf3ad335c59d7f0b"
RUN_ID = "knowledge-stage-b-uat-v2-20260904-run-02"
HASHES = {
    "manifest.json": "e41585a4d43b58049aa64708906a460f324ddaea0d96aa5ee492cfbca1f62c20",
    "environment.jsonl": "ae7eb72e35937dfa8a144093e7d69a408cb2b62c84f5c42885ee5eaad6e4f3c7",
    "consumed.json": "7ba1b07c7b9f678cb5b604dcd84e1feda3971dcc280dcfe0aadbbb94c9ae2635",
    "journal.jsonl": "0bf32c39e1021482bcd71ef3ee46c2f8fecb54db14b983accfaf097d4b9aed67",
    "evidence.jsonl": "52ea41efc75a7ef56c1c3e88863c7a67d2717805e6254e14e3b02d210a5cf85b",
    "result.json": "48ec2dd512eac405e733e04b94f6095c5c0136d918c8472ea8022e4798a1c8aa",
}
# Observed line-ending layout only, not source content. Each current file first
# matched its frozen SHA and normalized Git blob exactly. Rebuild from Git alone
# so later worktree edits cannot make these historical checks pass or fail.
CRLF_RANGES = {
    "auth-service/src/main/resources/static/home.html": ((1, 15), (18, 169), (171, 172)),
    "common-security/src/main/java/com/dylan/common/security/FeignTokenRelayAutoConfiguration.java":
        ((1, 30), (39, 72)),
    "common-security/src/main/java/com/dylan/common/security/JwtConfig.java": ((1, 2), (46, 46), (57, 57)),
    "common-security/src/main/java/com/dylan/common/security/ReactiveResourceServerSecurityAutoConfiguration.java":
        ((1, 9), (11, 12), (14, 17), (23, 35)),
    "common-security/src/main/java/com/dylan/common/security/SecurityTokenUtils.java":
        ((6, 7), (9, 29), (44, 47)),
    "common-security/src/main/java/com/dylan/common/security/ServiceTokenProvider.java":
        ((1, 18), (24, 27), (38, 72), (76, 118)),
    "config-service/src/main/resources/config/application-emp.yml": ((3, 3), (6, 9)),
    "config-service/src/main/resources/config/application-es.yml": ((1, 8),),
}


def read(name):
    return json.loads((ROOT / name).read_bytes())


def rows(name):
    return [json.loads(line) for line in (ROOT / name).read_bytes().splitlines()]


def test_run_02_bytes_and_exact_frozen_bindings():
    assert {p.name for p in ROOT.iterdir()} == set(HASHES)
    for name, expected in HASHES.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    manifest = read("manifest.json")
    assert set(manifest) == {"schemaVersion", "runId", "frozenHead", "authorizationReference", "limits",
                             "cases", "gold", "environment", "indexBinding", "assets", "executables",
                             "taskVersions", "evaluation", "promptHashes", "priorRun", "cumulativeLimits", "runRoot"}
    assert type(manifest["schemaVersion"]) is int and manifest["schemaVersion"] == 2
    assert manifest["runId"] == RUN_ID and manifest["frozenHead"] == HEAD
    assert manifest["authorizationReference"] == "P3_00:WP-KRETRIEVAL-UAT-01/run-02"
    assert manifest["taskVersions"] == dict(selection="action-selection-v4", rewrite="4", summary="4")
    assert manifest["promptHashes"] == {
        "action_selection": "fe0dc57fe758641e447fd4635f030b0b9d84225972dff9fef127d16fe04baf4f",
        "knowledge_rewrite": "a3baf3dcdc55e645660fecf94434669c72b27e8ba0545a02867e45f9ccfbc07d",
        "knowledge_summary": "f71ab8e899fe7d33688270d026077f8a102585b6e19135e9d002962ad41d7ec6",
    }
    assert manifest["runRoot"] == rf"D:\codex\agent-runtime\target\{RUN_ID}"
    assert manifest["priorRun"]["hashes"] == PRIOR_HASHES
    assert len(manifest["cases"]) == 10
    assert len(manifest["assets"]) == 287 and len(manifest["executables"]) == 258
    assert read("consumed.json") == dict(
        runId=RUN_ID, manifestSha256=HASHES["manifest.json"], rule="first_model_http_attempt; no retry/resume")


def test_run_02_failure_stopped_after_two_cases_and_counted_every_request():
    manifest, result = read("manifest.json"), read("result.json")
    assert set(result) == {"schemaVersion", "runId", "manifestSha256", "status", "failureKind",
                           "cases", "totals", "notExecuted"}
    assert type(result["schemaVersion"]) is int and result["schemaVersion"] == 1
    assert result["runId"] == RUN_ID and result["manifestSha256"] == HASHES["manifest.json"]
    assert result["status"] == "failed" and result["failureKind"] is None
    assert result["totals"] == dict(e2e=2, model=4, search=0, embedding=0, rerank=0,
                                    business=0, retry=0, resume=0)
    assert manifest["limits"] == dict(e2e=10, model=30, search=40, embedding=20, rerank=20,
                                      business=0, retry=0, resume=0)
    assert manifest["cumulativeLimits"] == dict(e2e=20, model=60, search=80, embedding=40, rerank=40,
                                                business=0, retry=0, resume=0)
    for key, value in result["totals"].items():
        assert type(value) is int and 0 <= value <= manifest["limits"][key]
        assert sum(c["calls"][key] for c in result["cases"]) == value
        assert value + manifest["priorRun"]["calls"][key] <= manifest["cumulativeLimits"][key]
    assert [c["caseId"] for c in result["cases"]] == ["UAT-KB-001", "UAT-KB-015a"]
    assert result["notExecuted"] == [c["caseId"] for c in manifest["cases"]][2:]
    first, second = result["cases"]
    assert first["passed"] is True and first["httpStatus"] == 200
    assert first["status"] == "no_result" and first["reason"] == "clarification_required"
    assert first["taskBindingValid"] is True and first["zeroRetrievalValid"] is True
    assert second["passed"] is False and second["httpStatus"] == 502
    assert second["status"] == "downstream_failure" and second["reason"] is None
    assert second["modelTasks"][-1] == dict(taskId="knowledge_rewrite", taskVersion="4",
                                           status="failed", failureKind="invalid_output")
    # This flag also checks successful completion; false does not imply a wrong version.
    assert second["taskBindingValid"] is False
    for case in result["cases"]:
        assert [(m["taskId"], m["taskVersion"]) for m in case["modelTasks"]] == [
            ("action_selection", "action-selection-v4"), ("knowledge_rewrite", "4")]
        assert case["pointCount"] == 0
        assert case["domains"] == case["retrievalStages"] == case["evidenceContentHashes"] == []
    journal = rows("journal.jsonl")
    assert all(set(row) == {"ordinal", "caseId", "task"} for row in journal)
    assert [r["ordinal"] for r in journal] == [1, 2, 3, 4]
    assert [r["task"] for r in journal] == ["action_selection", "knowledge_rewrite"] * 2
    assert [r["caseId"] for r in journal] == ["UAT-KB-001"] * 2 + ["UAT-KB-015a"] * 2


def test_run_02_case_evidence_readiness_and_cleanup_are_consistent():
    result = read("result.json")
    evidence = rows("evidence.jsonl")
    assert [{k: v for k, v in row.items() if k != "stage"}
            for row in evidence if row["stage"] == "case"] == result["cases"]
    environment = rows("environment.jsonl")
    assert environment[1] == dict(stage="spring_auth_stub_smoke", status="unsupported", model=0, knowledge=0)
    for records in (environment, evidence):
        assert records[-2:] == [dict(stage="runtime_cleanup", clientsClosed=True), dict(
            stage="cleanup", ownedProcessesStopped=True, rawLogsDeleted=True, secretScanPassed=True)]


def test_run_02_sources_match_frozen_git_not_current_worktree():
    for path, expected in read("manifest.json")["assets"].items():
        source = subprocess.check_output(["git", "show", f"{HEAD}:{path}"], cwd=REPO)
        if path in CRLF_RANGES:
            assert b"\r\n" not in source
            crlf_lines = {line for lower, upper in CRLF_RANGES[path] for line in range(lower, upper + 1)}
            source_lines = source.splitlines(keepends=True)
            assert max(crlf_lines) <= len(source_lines)
            reconstructed = b"".join(line[:-1] + b"\r\n" if ordinal in crlf_lines else line
                                      for ordinal, line in enumerate(source_lines, 1))
            versions = (reconstructed,)
        else:
            versions = (source, source.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        assert expected in {hashlib.sha256(value).hexdigest() for value in versions}, path


def test_run_02_finite_evidence_does_not_store_raw_payloads():
    forbidden = {"apiKey", "api_key", "jwt", "token", "rawResponse", "modelResponse",
                 "content", "quote", "question", "queryText", "prompt"}

    def visit(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for name in ("result.json", "consumed.json"):
        visit(read(name))
    for name in ("environment.jsonl", "evidence.jsonl", "journal.jsonl"):
        for record in rows(name):
            visit(record)
