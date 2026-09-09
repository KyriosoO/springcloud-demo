"""Finite immutable run-09 failure; this module never executes or resumes a run."""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput
from agent_runtime.knowledge.rewrite_v8 import KnowledgeRewriteTaskV8
from agent_runtime.model.contracts import InvalidModelOutput, StructuredFinishKind, StructuredModelResponse
from tests.system_e2e import knowledge_stage_b_uat_v9 as runner
from tests.system_e2e import test_knowledge_stage_b_run_02_history as history

ROOT = Path(__file__).with_name("knowledge_stage_b_run_09")
HEAD = "dab9fa118b3cf9effda1e89e985d61e30a527ac0"
HASHES = {
    "manifest.json": "c0411adab152939f09e5c06b866d017a0ade7c1382fb1c785d891454f6d39071",
    "authorization.json": "30d4aa9007e694de715118f3450945eec93654a0f3ccab399ce3a7390e74d71c",
    "startup.jsonl": "9484a41eaf700cd69675987afc22deddf10302fefff6a3108f3919b077c54d12",
    "environment.jsonl": "753c395c33e04976b05598a87d25ff00503cf5c174ac6bebd94665ad39d90ddf",
    "consumed.json": "ffe005f17400ab111103f135cc1d47ede32be0309e505bc14ca3d43b653bac3d",
    "journal.jsonl": "0bf32c39e1021482bcd71ef3ee46c2f8fecb54db14b983accfaf097d4b9aed67",
    "evidence.jsonl": "962c8ccde14b5706adb6621ef10a58ab25749a825e76a2e04ffbfccce49fc7cc",
    "result.json": "de416286b8ac6d416781f7e6f22b4cc57f6d84fa8dd5f03a25bb7fce6e3dd4b0",
}


def read(name):
    return runner.strict_json((ROOT / name).read_bytes())


def rows(name):
    return [runner.strict_json(line) for line in (ROOT / name).read_bytes().splitlines()]


def test_original_bytes_and_frozen_sources():
    assert {p.name for p in ROOT.iterdir()} == set(HASHES)
    for name, sha in HASHES.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha
    manifest = read("manifest.json")
    assert manifest["frozenHead"] == HEAD and manifest["schemaVersion"] == 9
    assert len(manifest["assets"]) == 382 and len(manifest["executables"]) == 258
    # Historical source binding is verified at its commit, never by requiring current files to stay old.
    with patch.multiple(history, ROOT=ROOT, HEAD=HEAD):
        history.test_run_02_sources_match_frozen_git_not_current_worktree()


def test_exact_original_cases_bindings_and_budgets():
    manifest, auth = read("manifest.json"), read("authorization.json")
    assert runner.same_json(manifest["cases"], runner.CASES) and manifest["gold"] == runner.GOLD
    assert manifest["taskVersions"] == dict(selection="action-selection-v4", rewrite="8", summary="6")
    assert manifest["rerankInputVersion"] == "authorized-body-first-metadata-v1"
    assert manifest["indexBinding"]["expectedIndexUuid"] == "jJ5Ww3LCRWWycfDkUZvmdw"
    with runner.bindings():
        assert manifest["priorRuns"] == runner.prior_bindings()
        assert manifest["promptHashes"] == runner.previous.prompt_hashes()
    assert auth == dict(schemaVersion=1, runId=runner.RUN_ID, frozenHead=HEAD,
        manifestSha256=HASHES["manifest.json"], authorizationReference=runner.REFERENCE,
        datasetSha256=manifest["datasetSha256"], limits=runner.LIMITS, cumulativeLimits=runner.TOTAL_LIMITS,
        live=True, startupLimits=dict(rerank=1), startupSha256=HASHES["startup.jsonl"],
        environmentSha256=HASHES["environment.jsonl"])


def test_failure_is_one_pass_one_fail_eight_unexecuted():
    result = read("result.json")
    assert set(result) == {"schemaVersion", "runId", "manifestSha256", "status", "failureKind", "cases", "totals", "notExecuted"}
    assert result["status"] == "failed" and result["failureKind"] is None
    assert result["runId"] == runner.RUN_ID and result["manifestSha256"] == HASHES["manifest.json"]
    assert [c["caseId"] for c in result["cases"]] == [c["caseId"] for c in runner.CASES[:2]]
    assert result["notExecuted"] == [c["caseId"] for c in runner.CASES[2:]]
    first, failed = result["cases"]
    assert first["passed"] is True and first["reason"] == "clarification_required" and first["httpStatus"] == 200
    assert first["zeroRetrievalValid"] is True
    assert failed["passed"] is False and failed["httpStatus"] == 502 and failed["status"] == "downstream_failure"
    assert failed["modelFailures"] == [dict(taskId="knowledge_rewrite", taskVersion="8", status="failed", failureKind="invalid_output")]
    assert failed["citationFailure"] == "input_binding_missing" and not any(failed["requiredClauseChecks"].values())
    assert result["totals"] == dict(e2e=2, model=4, search=0, embedding=0, rerank=0, business=0, retry=0, resume=0)
    for case in result["cases"]:
        assert case["calls"] == {**result["totals"], "e2e": 1, "model": 2}
        assert case["retrievalStages"] == case["evidenceContentHashes"] == []
        assert len(case["modelTasks"]) == 2
    assert [r["ordinal"] for r in rows("journal.jsonl")] == [1, 2, 3, 4]
    assert read("consumed.json")["manifestSha256"] == HASHES["manifest.json"]
    runner.validate_startup(ROOT, HASHES["manifest.json"])
    runner.validate_environment(ROOT)
    events = rows("evidence.jsonl")
    assert {k: events[-1][k] for k in ("ownedProcessesStopped", "rawLogsDeleted", "secretScanPassed")} == dict(
        ownedProcessesStopped=True, rawLogsDeleted=True, secretScanPassed=True)
    assert dict(stage="final_binding", unchanged=True) in events
    assert dict(stage="runtime_cleanup", clientsClosed=True) in events
    prior = runner.prior_bindings()
    totals = {k: sum(row["calls"][k] for row in prior) + result["totals"][k] for k in runner.LIMITS}
    totals["rerank"] += 1  # Independently reserved and completed startup request.
    assert totals == dict(e2e=18, model=43, search=27, embedding=14, rerank=15, business=0, retry=0, resume=0)
    with pytest.raises(ValueError, match="retry_resume_forbidden"):
        runner.validate_manifest(ROOT, HASHES["manifest.json"])


def test_finite_outputs_do_not_include_question_or_raw_payloads():
    forbidden = {"question", "content", "quote", "prompt", "focus", "messages", "token", "jwt", "apiKey", "password"}
    def scan(value):
        if isinstance(value, dict):
            assert not set(value).intersection(forbidden)
            for child in value.values(): scan(child)
        elif isinstance(value, list):
            for child in value: scan(child)
    for name in set(HASHES) - {"manifest.json"}:  # Manifest deliberately freezes the original public dataset/gold.
        raw = (ROOT / name).read_bytes()
        for line in raw.splitlines(): scan(runner.strict_json(line))
        assert all(case["question"].encode() not in raw for case in runner.CASES)
    # "No run-10" is a fact at this historical commit, not a permanent ban on
    # subsequently authorized work. Keep the original result and its hashes.
    assert runner.legacy.git("ls-tree", "--name-only", HEAD,
                             "agent-runtime/tests/system_e2e/knowledge_stage_b_run_10") == ""


def valid_lookup():
    # Synthetic contract counterexample, NOT a reconstruction of the discarded model output.
    return dict(outcome="search", question_kind="lookup", queries=[dict(domain_id="tax.policy", query=runner.CASES[1]["question"])],
        requirements=[dict(requirement_id="r1", domain_id="tax.policy", kind="subject_scope", focus="增值税政策中的住宿服务定义"),
                      dict(requirement_id="r2", domain_id="tax.policy", kind="subject_scope", focus="增值税生活服务分类")],
        missing_conditions=[])


def response(value):
    return StructuredModelResponse(finish_kind=StructuredFinishKind.STOP, content=json.dumps(value),
        tool_calls=(), usage_total_tokens=None)


def test_definition_lookup_is_expressible_without_missing_user_conditions():
    task = KnowledgeRewriteTaskV8.definition()
    request = task.build_request(KnowledgeSemanticPlanInput(minimized_question=runner.CASES[1]["question"],
        enabled_domain_ids=("tax.policy", "tax.law")))
    output = task.parse_response(response(valid_lookup()))
    assert request.task_version == "8" and output.outcome == "search" and output.question_kind.value == "lookup"
    assert not output.missing_conditions and len(output.evidence_requirements) == 2


@pytest.mark.parametrize("fault", ["invalid_json", "missing_field", "unknown_kind", "bad_id", "extra_field"])
def test_invalid_output_alone_cannot_identify_actual_branch(fault):
    value = valid_lookup()
    if fault == "missing_field": del value["requirements"]
    elif fault == "unknown_kind": value["requirements"][0]["kind"] = "not_configured"
    elif fault == "bad_id": value["requirements"][0]["requirement_id"] = "r2"
    elif fault == "extra_field": value["extra"] = True
    source = response(value) if fault != "invalid_json" else StructuredModelResponse(
        finish_kind=StructuredFinishKind.STOP, content="{", tool_calls=(), usage_total_tokens=None)
    with pytest.raises(InvalidModelOutput, match="knowledge.invalid_requirement_plan"):
        KnowledgeRewriteTaskV8.definition().parse_response(source)
