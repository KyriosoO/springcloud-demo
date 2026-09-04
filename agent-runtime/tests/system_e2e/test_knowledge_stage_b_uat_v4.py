from __future__ import annotations

from dataclasses import replace
import json
from types import SimpleNamespace

import httpx
import pytest

from agent_runtime.knowledge.rewrite_v5 import KnowledgeRewriteTaskV5
from agent_runtime.model.contracts import InvalidModelOutput, StructuredFinishKind, StructuredModelResponse
from agent_runtime.model.deepseek.transport import DeepSeekChatTransport
from tests.integration.knowledge.test_rewrite_v4_provider_boundary import (
    test_wire_response_to_current_rewrite_runtime_fails_closed as wire_check,
)
from tests.system_e2e import knowledge_stage_b_failure_diagnostics as diag
from tests.system_e2e import knowledge_stage_b_uat as old
from tests.system_e2e import knowledge_stage_b_uat_v2 as v2
from tests.system_e2e import knowledge_stage_b_uat_v3 as v3
from tests.system_e2e import knowledge_stage_b_uat_v4 as new
from tests.system_e2e.test_knowledge_stage_b_uat_v2 import request as old_request
from tests.system_e2e.test_knowledge_stage_b_uat_v3 import (
    test_diagnostics_preserve_actual_wire_runtime_assertions as _historical_wire_test,
)


def request(task, question):
    prompts = {"action_selection": new.ACTION_SELECTION_SYSTEM_INSTRUCTION,
               "knowledge_rewrite": new.INSTRUCTION, "knowledge_summary": new.SUMMARY_PROMPT_V5}
    return old_request(task, question, instruction=prompts[task])


def test_scope_and_prior_budgets_restore_after_exception():
    before = (old.RUN_ID, old.Budget, old.assess, old.run_server, v2.prompt_hashes,
              diag.TASKS, diag.KnowledgeRewriteTaskV4)
    with pytest.raises(RuntimeError), new.run_04_bindings():
        assert old.RUN_ID == new.RUN_ID
        assert v2.prompt_hashes() == new.prompt_hashes()
        assert diag.KnowledgeRewriteTaskV4 is KnowledgeRewriteTaskV5
        rows = new.prior_bindings()
        assert len(rows) == 3
        assert [sum(row["calls"][key] for row in rows) for key in
                ("e2e", "model", "search", "embedding", "rerank")] == [5, 12, 8, 4, 4]
        for key, limit in v2.TOTAL_LIMITS.items():
            assert sum(row["calls"][key] for row in rows) + old.LIMITS[key] <= limit
        raise RuntimeError("synthetic")
    assert (old.RUN_ID, old.Budget, old.assess, old.run_server, v2.prompt_hashes,
            diag.TASKS, diag.KnowledgeRewriteTaskV4) == before


@pytest.mark.parametrize("calls", [True, -1, 60])
def test_invalid_or_exhausted_cumulative_budget_rejected(monkeypatch, calls):
    rows = v3.prior_bindings()
    rows[0]["calls"]["model"] = calls
    monkeypatch.setattr(v3, "prior_bindings", lambda: rows)
    with pytest.raises(ValueError, match="cumulative_budget_invalid"):
        new.prior_bindings()


def test_prior_hash_drift_rejected(monkeypatch):
    monkeypatch.setattr(new, "RUN03_HASHES", {**new.RUN03_HASHES, "result.json": "0" * 64})
    with pytest.raises(ValueError, match="prior_run_changed"):
        new.prior_bindings()


@pytest.fixture
def budget(tmp_path):
    with new.run_04_bindings():
        value = old.Budget(tmp_path, "a" * 64, lambda row: None)
        yield value
        value.journal.close()


@pytest.mark.asyncio
async def test_full_fake_budget_journal_and_stop(budget):
    for spec in old.CASES:
        budget.begin(spec)
        assert budget.per_case["e2e"] == 1 and budget.model_failures == []
        for task in ("action_selection", "knowledge_rewrite", "knowledge_summary"):
            await budget.model_request(request(task, spec["question"]))
    assert budget.totals["model"] == 30 and budget.totals["e2e"] == 10
    with pytest.raises(ValueError):
        budget.begin(old.CASES[0])
    assert json.loads((budget.root / "consumed.json").read_text())["runId"] == new.RUN_ID
    raw = (budget.root / "journal.jsonl").read_text()
    assert len(raw.splitlines()) == 30 and "synthetic public source" not in raw
    assert all(spec["question"] not in raw for spec in old.CASES)


@pytest.mark.asyncio
async def test_old_prompt_and_repeated_task_stop_before_outbound(budget):
    spec = old.CASES[0]
    budget.begin(spec)
    await budget.model_request(request("action_selection", spec["question"]))
    with pytest.raises(ValueError, match="model_request_rejected"):
        await budget.model_request(old_request("knowledge_rewrite", spec["question"]))
    assert budget.stopped and budget.totals["model"] == 1
    with pytest.raises(ValueError):
        await budget.model_request(request("knowledge_rewrite", spec["question"]))
    assert budget.totals["model"] == 1


@pytest.mark.asyncio
async def test_business_and_excess_search_forbidden(budget):
    budget.begin(old.CASES[0])
    req = httpx.Request("POST", "http://127.0.0.1:19201/es/knowledge/search")
    for _ in range(4):
        await budget.downstream_request(req)
    with pytest.raises(ValueError):
        await budget.downstream_request(req)
    with pytest.raises(ValueError):
        await budget.business_request()
    assert budget.totals["search"] == 4 and budget.totals["business"] == 0


@pytest.fixture
def manifest_root(tmp_path, monkeypatch):
    value = {"schemaVersion": 1, "runId": old.RUN_ID, "frozenHead": "a" * 40, "authorizationReference": "old",
             "limits": old.LIMITS, "cases": old.CASES, "gold": old.GOLD, "environment": old.ENV,
             "indexBinding": {}, "assets": {}, "executables": {}, "taskVersions": {}, "evaluation": "unchanged"}
    monkeypatch.setattr(v2, "_prepare", lambda root: value)
    monkeypatch.setattr(old, "git", lambda *args: "a" * 40 if args[0] == "rev-parse" else "")
    new.prepare(tmp_path)
    return tmp_path


def test_manifest_freezes_v5_unchanged_cases_gold_and_three_prior_runs(manifest_root):
    manifest, sha = new.validate_manifest(manifest_root, old.digest((manifest_root / "manifest.json").read_bytes()))
    assert manifest["schemaVersion"] == 4 and len(sha) == 64
    assert manifest["taskVersions"] == new.TASK_VERSIONS
    assert manifest["promptHashes"] == new.prompt_hashes()
    assert manifest["cases"] == list(old.CASES) and manifest["gold"] == old.GOLD
    assert len(manifest["priorRuns"]) == 3 and manifest["diagnosticVersion"] == new.DIAGNOSTIC_VERSION
    with pytest.raises(FileExistsError):
        new.prepare(manifest_root)


@pytest.mark.parametrize("field,value", [("schemaVersion", True), ("priorRuns", []), ("cumulativeLimits", {}),
    ("diagnosticVersion", "other"), ("authorizationReference", "old"), ("runRoot", "elsewhere"),
    ("taskVersions", v2.TASK_VERSIONS), ("promptHashes", {})])
def test_manifest_tamper_rejected(manifest_root, field, value):
    path = manifest_root / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest[field] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="run_04_binding_invalid"):
        new.validate_manifest(manifest_root)


@pytest.mark.parametrize("artifact", ["journal.jsonl", "consumed.json", "evidence.jsonl", "result.json"])
def test_execution_assets_reject_resume(manifest_root, artifact):
    (manifest_root / artifact).touch()
    with pytest.raises(ValueError, match="retry_resume_forbidden"):
        new.validate_manifest(manifest_root)


@pytest.mark.parametrize("failed", [False, True])
def test_v5_assessment_preserves_frozen_verdict(failed):
    observation = SimpleNamespace(plans=[], downstream_calls=[], model_calls=[
        {"taskId": "action_selection", "taskVersion": "action-selection-v4", "status": "succeeded"},
        {"taskId": "knowledge_rewrite", "taskVersion": "4", "status": "failed" if failed else "succeeded",
         "failureKind": "invalid_output" if failed else None}])
    result = {"status": "downstream_failure" if failed else "no_result", "capabilityId": "knowledge.query",
              "result": {"reason": "clarification_required", "points": []}}
    expected = v3.assess(old.CASES[0], result, observation, [])
    observation.model_calls[1]["taskVersion"] = "5"
    with new.run_04_bindings():
        actual = new.assess(old.CASES[0], result, observation, [])
    for row in expected["modelFailures"]:
        row["taskVersion"] = "5"
    assert actual == expected and actual["passed"] is not failed


@pytest.mark.parametrize("fault,status,failure,decoded,stage,reason",
    next(mark.args[1] for mark in _historical_wire_test.pytestmark if mark.name == "parametrize"))
@pytest.mark.asyncio
async def test_v5_diagnostics_with_current_production_root(monkeypatch, caplog, fault, status, failure, decoded, stage, reason):
    budget = SimpleNamespace(model_failures=[])
    before = DeepSeekChatTransport.complete, KnowledgeRewriteTaskV5.definition
    with new.run_04_bindings(), diag.diagnostic_scope(budget):
        await wire_check(monkeypatch, caplog, fault, status, failure, decoded)
        expected = [] if stage is None else [{"taskId": "knowledge_rewrite", "taskVersion": "5", "stage": stage, "reason": reason}]
        assert diag.validate_rows(budget.model_failures) == expected
    assert (DeepSeekChatTransport.complete, KnowledgeRewriteTaskV5.definition) == before
    assert "synthetic-response" not in json.dumps(budget.model_failures)


def test_v5_decoder_diagnostics_preserve_definition_and_exception():
    original = KnowledgeRewriteTaskV5.definition()
    value = StructuredModelResponse(finish_kind=StructuredFinishKind.STOP, content="not json", tool_calls=(), usage_total_tokens=1)
    with pytest.raises(InvalidModelOutput) as baseline:
        original.parse_response(value)
    budget = SimpleNamespace(model_failures=[])
    with new.run_04_bindings(), diag.diagnostic_scope(budget):
        definition = KnowledgeRewriteTaskV5.definition()
        assert replace(definition, parse_response=original.parse_response) == original
        with pytest.raises(InvalidModelOutput) as actual:
            definition.parse_response(value)
        assert str(actual.value) == str(baseline.value)
        assert diag.validate_rows(budget.model_failures) == [{"taskId": "knowledge_rewrite", "taskVersion": "5",
                                                           "stage": "task_decoder", "reason": "model.json_invalid"}]


@pytest.mark.parametrize("spec", old.CASES, ids=lambda spec: spec["caseId"])
def test_every_frozen_case_keeps_original_source_clause_verdict(spec):
    sources = [{"sha256": old.GOLD[g]["sha256"], "content": old.GOLD[g]["clause"]} for g in spec["requiredGold"]]
    points = [{"quote": source["content"], "citation": {"domainIds": spec["domains"]}} for source in sources]
    response = {"status": "no_result" if spec["reason"] else "success", "capabilityId": "knowledge.query",
                "result": {"reason": spec["reason"], "points": points}}
    plans = [] if spec["reason"] else [{"type": "knowledge_retrieval_plan", "plan": {"selected_domain_ids": spec["domains"]}}]
    tasks = [("action_selection", "action-selection-v4"), ("knowledge_rewrite", "5")]
    if not spec["reason"]:
        tasks.append(("knowledge_summary", "5"))
    observation = SimpleNamespace(plans=plans, downstream_calls=[], model_calls=[
        dict(taskId=task, taskVersion=version, status="succeeded") for task, version in tasks])
    with new.run_04_bindings():
        assert new.assess(spec, response, observation, sources)["passed"]
        response["result"]["points"] = []
        if spec["reason"]:
            observation.downstream_calls.append({"synthetic": True})
        assert not new.assess(spec, response, observation, sources)["passed"]


@pytest.mark.asyncio
async def test_actual_v5_summary_wire_projection_matches_frozen_prompt(budget):
    from agent_runtime.capability_api.contracts import canonical_json_bytes
    from agent_runtime.knowledge.evidence.summary_task_v5 import KnowledgeSummaryTaskV5
    from agent_runtime.model.deepseek.dto import project_deepseek_request
    from tests.contract.knowledge.test_summary_task_v4 import _input
    spec = old.CASES[0]
    budget.begin(spec)
    for task in ("action_selection", "knowledge_rewrite"):
        await budget.model_request(request(task, spec["question"]))
    structured = KnowledgeSummaryTaskV5.definition().build_request(replace(_input(), question=spec["question"]))
    payload = canonical_json_bytes(project_deepseek_request(structured).payload)
    await budget.model_request(httpx.Request("POST", old.ModelSettings.BASE_URL + "/chat/completions", content=payload))
    assert budget.totals["model"] == 3 and len(budget.summary_evidence) == 2
