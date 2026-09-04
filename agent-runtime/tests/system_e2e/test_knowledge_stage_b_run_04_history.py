"""Read-only audit of terminal V5 run-04; never executes or resumes a launcher."""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from tests.system_e2e import test_knowledge_stage_b_run_02_history as history
from tests.system_e2e import test_knowledge_stage_b_run_03_history as prior

ROOT = Path(__file__).with_name("knowledge_stage_b_run_04")
HEAD = "77dad25db25205b3242e5a3b937de318a82d1053"
RUN_ID = "knowledge-stage-b-uat-v4-20260904-run-04"
HASHES = {
    "manifest.json": "f6b745545e2808ea776744360bb9a879cc520e12717a6479f9b8086d671f5848",
    "environment.jsonl": "ae7eb72e35937dfa8a144093e7d69a408cb2b62c84f5c42885ee5eaad6e4f3c7",
    "consumed.json": "0d1448502f7b6d8016716cfdca8509bc4cb799b19eaa962bd6b8ddd7f233661b",
    "journal.jsonl": "176f84c787acbdb8f4083c852dc8ae7cb23612826bf9003a4edee61ce0fab433",
    "evidence.jsonl": "23f3e091e9a3816cf950f5736f14ad8b3fec23f1b7a4607b3aa6c1875100c9e3",
    "result.json": "969e3f8e22b47ea98e6c6230a6289d24e68e911facda967ac25ae296d6e28c48",
}


def read(name):
    return json.loads((ROOT / name).read_bytes())


def test_run_04_exact_bytes_and_frozen_authorization():
    assert {p.name for p in ROOT.iterdir()} == set(HASHES)
    for name, sha in HASHES.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha
    manifest, previous = read("manifest.json"), prior.read("manifest.json")
    assert set(manifest) == set(previous)
    assert type(manifest["schemaVersion"]) is int and manifest["schemaVersion"] == 4
    assert manifest["runId"] == RUN_ID and manifest["frozenHead"] == HEAD
    assert manifest["authorizationReference"] == "P3_00:WP-KRETRIEVAL-UAT-01/run-04"
    assert manifest["diagnosticVersion"] == "stage-b-failure-diagnostics-v2"
    assert manifest["taskVersions"] == dict(selection="action-selection-v4", rewrite="5", summary="5")
    assert manifest["promptHashes"] == {
        "action_selection": "fe0dc57fe758641e447fd4635f030b0b9d84225972dff9fef127d16fe04baf4f",
        "knowledge_rewrite": "560b69f354e300678e3e4accd031640473e84f33ed46a0e4da9ef62f1620b8b8",
        "knowledge_summary": "fee1a061fd68f49198a8832e222cdebdb6ec6f78cf95b48f5f10fd6bdc494e96",
    }
    for key in ("cases", "gold", "environment", "indexBinding", "limits", "cumulativeLimits", "evaluation"):
        assert manifest[key] == previous[key]
    assert manifest["priorRuns"][:2] == previous["priorRuns"]
    assert manifest["priorRuns"][2] == dict(runId=prior.RUN_ID, hashes=prior.HASHES,
                                           calls=prior.read("result.json")["totals"])
    assert manifest["runRoot"] == rf"D:\codex\agent-runtime\target\{RUN_ID}"
    assert len(manifest["assets"]) == 308 and len(manifest["executables"]) == 258
    assert read("consumed.json") == dict(runId=RUN_ID, manifestSha256=HASHES["manifest.json"],
        rule="first_model_http_attempt; no retry/resume")


def test_run_04_terminal_failure_counts_and_unexecuted_cases():
    manifest, result = read("manifest.json"), read("result.json")
    assert set(result) == {"schemaVersion", "runId", "manifestSha256", "status", "failureKind", "cases", "totals", "notExecuted"}
    assert type(result["schemaVersion"]) is int and result["schemaVersion"] == 1
    assert result["runId"] == RUN_ID and result["manifestSha256"] == HASHES["manifest.json"]
    assert result["status"] == "failed" and result["failureKind"] is None
    assert result["totals"] == dict(e2e=3, model=8, search=6, embedding=3, rerank=3, business=0, retry=0, resume=0)
    cumulative = dict(e2e=8, model=20, search=14, embedding=7, rerank=7, business=0, retry=0, resume=0)
    for key, value in result["totals"].items():
        assert type(value) is int and 0 <= value <= manifest["limits"][key]
        assert sum(row["calls"][key] for row in result["cases"]) == value
        assert value + sum(row["calls"][key] for row in manifest["priorRuns"]) == cumulative[key]
        assert cumulative[key] <= manifest["cumulativeLimits"][key]
    assert [row["caseId"] for row in result["cases"]] == ["UAT-KB-001", "UAT-KB-015a", "UAT-KB-004"]
    assert result["notExecuted"] == [row["caseId"] for row in manifest["cases"]][3:]
    first, second, third = result["cases"]
    assert [row["passed"] for row in result["cases"]] == [True, True, False]
    assert first["status"] == "no_result" and first["reason"] == "clarification_required"
    assert first["domains"] == first["retrievalStages"] == first["evidenceContentHashes"] == []
    assert first["calls"] == dict(e2e=1, model=2, search=0, embedding=0, rerank=0, business=0, retry=0, resume=0)
    assert second["status"] == third["status"] == "success"
    assert second["domains"] == second["citationDomains"] == ["tax.policy"]
    assert second["requiredClauseChecks"] == dict(lodging=True, living=True)
    assert third["domains"] == ["tax.policy", "tax.law"]
    assert third["citationDomains"] == ["tax.law", "tax.policy"]
    assert third["requiredClauseChecks"] == dict(lodging=False, living=False, law_rate=True)
    assert second["pointCount"] == third["pointCount"] == 2
    for row in result["cases"]:
        assert row["httpStatus"] == 200 and row["modelFailures"] == []
        assert row["taskBindingValid"] is True and row["zeroRetrievalValid"] is True
        tasks = [("action_selection", "action-selection-v4"), ("knowledge_rewrite", "5")]
        if not row["reason"]:
            tasks.append(("knowledge_summary", "5"))
        assert row["modelTasks"] == [dict(taskId=name, taskVersion=version, status="succeeded", failureKind=None)
                                     for name, version in tasks]
    journal = [json.loads(line) for line in (ROOT / "journal.jsonl").read_bytes().splitlines()]
    assert all(set(row) == {"ordinal", "caseId", "task"} for row in journal)
    assert [row["ordinal"] for row in journal] == list(range(1, 9))
    assert [row["task"] for row in journal] == ["action_selection", "knowledge_rewrite"] + [
        "action_selection", "knowledge_rewrite", "knowledge_summary"] * 2
    assert [row["caseId"] for row in journal] == ["UAT-KB-001"] * 2 + ["UAT-KB-015a"] * 3 + ["UAT-KB-004"] * 3


def ranks(row, gold):
    hashes = [item["sha256"] for item in row["candidates"]]
    return tuple(hashes.index(gold[label]["sha256"]) + 1 if gold[label]["sha256"] in hashes else None
                 for label in ("lodging", "living", "law_rate"))


def test_run_04_classification_case_passed_with_both_required_sources():
    gold, case = read("manifest.json")["gold"], read("result.json")["cases"][1]
    for stage in ("final_rank", "evidence"):
        row, = [item for item in case["retrievalStages"] if item["stage"] == stage]
        assert ranks(row, gold)[:2] == (2, 3)
    assert all(gold[label]["sha256"] in case["evidenceContentHashes"] for label in ("lodging", "living"))


def test_run_04_cross_domain_loss_is_observed_at_two_separate_boundaries():
    # These are frozen observations, not desirable online selection rules or gold used by production.
    gold, case = read("manifest.json")["gold"], read("result.json")["cases"][2]
    paths = {(row["domain"], row["path"]): row for row in case["retrievalStages"] if row["stage"] == "path"}
    assert ranks(paths["tax.policy", "keyword"], gold) == (3, 8, None)
    assert ranks(paths["tax.policy", "vector"], gold) == (None, None, None)
    reranks = [row for row in case["retrievalStages"] if row["stage"] == "rerank"]
    assert [(len(row["candidates"]), ranks(row, gold)) for row in reranks] == [
        (39, (4, 28, None)), (34, (None, None, 1))]
    final, = [row for row in case["retrievalStages"] if row["stage"] == "final_rank"]
    evidence, = [row for row in case["retrievalStages"] if row["stage"] == "evidence"]
    assert (len(final["candidates"]), ranks(final, gold)) == (20, (9, None, 4))
    assert (len(evidence["candidates"]), ranks(evidence, gold)) == (8, (None, None, 4))
    assert [gold[label]["sha256"] in case["evidenceContentHashes"] for label in ("lodging", "living", "law_rate")] == [False, False, True]


def test_run_04_sources_from_frozen_git():
    with patch.multiple(history, ROOT=ROOT, HEAD=HEAD):
        history.test_run_02_sources_match_frozen_git_not_current_worktree()


def test_run_04_cleanup_and_finite_payload_schema():
    with patch.object(history, "ROOT", ROOT):
        history.test_run_02_case_evidence_readiness_and_cleanup_are_consistent()
        history.test_run_02_finite_evidence_does_not_store_raw_payloads()
