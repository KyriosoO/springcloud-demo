"""Immutable run-03 audit; never loads credentials or executes the launcher."""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from tests.system_e2e import test_knowledge_stage_b_run_02_history as history

ROOT = Path(__file__).with_name("knowledge_stage_b_run_03")
HEAD = "4a095def4930810713314c15a34668a12fdf4a31"
RUN_ID = "knowledge-stage-b-uat-v3-20260904-run-03"
HASHES = {
    "manifest.json": "c0f111d48195e73c7c1f07a81dec24c127b23aff55c81431452addad99d717e0",
    "environment.jsonl": "ae7eb72e35937dfa8a144093e7d69a408cb2b62c84f5c42885ee5eaad6e4f3c7",
    "consumed.json": "0caa52c2adc38267fc25661bcc84df851ca123cf7740767b2a201c9317e4d079",
    "journal.jsonl": "ffac99686b316c68e34fe7d3a7ace3cc16409a79ba5c54ec422f6d1ef4f8a3d3",
    "evidence.jsonl": "cf824819278a1cd076e14d3224b27035f6a0d8b3a09914c290ed9a1522044b16",
    "result.json": "e414fc99138f75b9c278f5cb06df76d406eec8f6eaf866a5eebb4f152c0f712a",
}


def read(name):
    return json.loads((ROOT / name).read_bytes())


def test_run_03_exact_asset_and_manifest_bindings():
    assert {p.name for p in ROOT.iterdir()} == set(HASHES)
    for name, sha in HASHES.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha
    manifest = read("manifest.json")
    assert set(manifest) == {"schemaVersion", "runId", "frozenHead", "authorizationReference", "limits",
        "cases", "gold", "environment", "indexBinding", "assets", "executables", "taskVersions", "evaluation",
        "promptHashes", "priorRuns", "cumulativeLimits", "runRoot", "diagnosticVersion"}
    assert type(manifest["schemaVersion"]) is int and manifest["schemaVersion"] == 3
    assert manifest["runId"] == RUN_ID and manifest["frozenHead"] == HEAD
    assert manifest["authorizationReference"] == "P3_00:WP-KRETRIEVAL-UAT-01/run-03"
    assert manifest["diagnosticVersion"] == "stage-b-failure-diagnostics-v1"
    prior = history.read("manifest.json")
    for key in ("cases", "gold", "environment", "indexBinding", "taskVersions", "promptHashes", "limits", "cumulativeLimits"):
        assert manifest[key] == prior[key]
    assert manifest["priorRuns"][0] == prior["priorRun"]
    assert manifest["priorRuns"][1]["hashes"] == history.HASHES
    assert manifest["priorRuns"][1]["calls"] == history.read("result.json")["totals"]
    assert manifest["runRoot"] == rf"D:\codex\agent-runtime\target\{RUN_ID}"
    assert len(manifest["assets"]) == 297 and len(manifest["executables"]) == 258
    assert read("consumed.json") == dict(runId=RUN_ID, manifestSha256=HASHES["manifest.json"],
        rule="first_model_http_attempt; no retry/resume")


def test_run_03_failure_and_all_call_counters():
    manifest, result = read("manifest.json"), read("result.json")
    assert set(result) == {"schemaVersion", "runId", "manifestSha256", "status", "failureKind", "cases", "totals", "notExecuted"}
    assert type(result["schemaVersion"]) is int and result["schemaVersion"] == 1
    assert result["runId"] == RUN_ID and result["manifestSha256"] == HASHES["manifest.json"]
    assert result["status"] == "failed" and result["failureKind"] is None
    assert result["totals"] == dict(e2e=2, model=5, search=4, embedding=2, rerank=2, business=0, retry=0, resume=0)
    for key, value in result["totals"].items():
        assert type(value) is int and 0 <= value <= manifest["limits"][key]
        assert sum(row["calls"][key] for row in result["cases"]) == value
        assert value + sum(row["calls"][key] for row in manifest["priorRuns"]) <= manifest["cumulativeLimits"][key]
    assert [row["caseId"] for row in result["cases"]] == ["UAT-KB-001", "UAT-KB-015a"]
    assert result["notExecuted"] == [row["caseId"] for row in manifest["cases"]][2:]
    first, second = result["cases"]
    assert first["passed"] is True and first["status"] == "no_result" and first["reason"] == "clarification_required"
    assert second["passed"] is False and second["httpStatus"] == 200 and second["status"] == "success"
    assert second["domains"] == ["tax.policy", "tax.law"] != manifest["cases"][1]["domains"]
    assert second["requiredClauseChecks"] == dict(lodging=True, living=False)
    assert second["pointCount"] == 1 and second["citationDomains"] == ["tax.policy"]
    for row in result["cases"]:
        assert row["modelFailures"] == [] and row["taskBindingValid"] is True
        assert row["zeroRetrievalValid"] is True
        assert all(model["status"] == "succeeded" and model["failureKind"] is None for model in row["modelTasks"])
    journal = [json.loads(line) for line in (ROOT / "journal.jsonl").read_bytes().splitlines()]
    assert all(set(row) == {"ordinal", "caseId", "task"} for row in journal)
    assert [row["ordinal"] for row in journal] == list(range(1, 6))
    assert [row["task"] for row in journal] == ["action_selection", "knowledge_rewrite"] * 2 + ["knowledge_summary"]
    assert [row["caseId"] for row in journal] == ["UAT-KB-001"] * 2 + ["UAT-KB-015a"] * 3


def test_run_03_required_sources_reached_evidence_not_a_window_loss():
    manifest, result = read("manifest.json"), read("result.json")
    case = result["cases"][1]
    expected = {"path:tax.policy:keyword": (9, 2), "path:tax.policy:vector": (3, 16),
                "final_rank::": (2, 4), "evidence::": (2, 4)}
    found = set()
    for row in case["retrievalStages"]:
        key = ":".join((row["stage"], row.get("domain", ""), row.get("path", "")))
        if key in expected:
            hashes = [item["sha256"] for item in row["candidates"]]
            ranks = tuple(hashes.index(manifest["gold"][label]["sha256"]) + 1 for label in ("lodging", "living"))
            assert ranks == expected[key]
            found.add(key)
    assert found == set(expected)
    for label in ("lodging", "living"):
        assert manifest["gold"][label]["sha256"] in case["evidenceContentHashes"]


def test_run_03_sources_from_frozen_git():
    # Reuse the audited line-ending reconstruction, never current source bytes.
    with patch.multiple(history, ROOT=ROOT, HEAD=HEAD):
        history.test_run_02_sources_match_frozen_git_not_current_worktree()


def test_run_03_cleanup_and_finite_payload_schema():
    with patch.object(history, "ROOT", ROOT):
        history.test_run_02_case_evidence_readiness_and_cleanup_are_consistent()
        history.test_run_02_finite_evidence_does_not_store_raw_payloads()
