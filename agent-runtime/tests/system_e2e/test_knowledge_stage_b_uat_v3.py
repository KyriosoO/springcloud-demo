from __future__ import annotations

import asyncio
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput
from agent_runtime.knowledge.rewrite_v4 import KnowledgeRewriteTaskV4
from agent_runtime.model.contracts import InvalidModelOutput, StructuredFinishKind, StructuredModelResponse
from agent_runtime.model.deepseek.transport import DeepSeekChatTransport
from tests.integration.knowledge.test_rewrite_v4_provider_boundary import (
    test_wire_response_to_current_rewrite_runtime_fails_closed as wire_check,
)
from tests.system_e2e import knowledge_stage_b_failure_diagnostics as diag
from tests.system_e2e import knowledge_stage_b_uat as old
from tests.system_e2e import knowledge_stage_b_uat_v2 as v2
from tests.system_e2e import knowledge_stage_b_uat_v3 as new
from tests.system_e2e.test_knowledge_stage_b_uat_v2 import request


@pytest.mark.parametrize("fault,status,failure,decoded,stage,reason", [
    ("none", CapabilityStatus.SUCCESS, None, True, None, None),
    ("clarification", CapabilityStatus.NO_RESULT, None, True, None, None),
    ("content_type", CapabilityStatus.DOWNSTREAM_FAILURE, "invalid_output", False, "provider", "model.provider_content_type_invalid"),
    ("outer_json", CapabilityStatus.DOWNSTREAM_FAILURE, "invalid_output", False, "provider", "model.json_invalid"),
    ("provider_model", CapabilityStatus.DOWNSTREAM_FAILURE, "invalid_output", False, "provider", "model.provider_response_mismatch"),
    ("finish_length", CapabilityStatus.DOWNSTREAM_FAILURE, "invalid_output", False, "provider", "model.provider_finish_reason_invalid"),
    ("task_json", CapabilityStatus.DOWNSTREAM_FAILURE, "invalid_output", True, "task_decoder", "model.json_invalid"),
    ("task_duplicate_key", CapabilityStatus.DOWNSTREAM_FAILURE, "invalid_output", True, "task_decoder", "model.json_duplicate_key"),
    ("task_extra_field", CapabilityStatus.DOWNSTREAM_FAILURE, "invalid_output", True, "task_decoder", "top_level_contract_invalid"),
    ("task_unknown_condition", CapabilityStatus.DOWNSTREAM_FAILURE, "invalid_output", True, "task_decoder", "missing_conditions_invalid"),
    ("semantic_date", CapabilityStatus.DOWNSTREAM_FAILURE, None, True, None, None),
    ("http_error", CapabilityStatus.DOWNSTREAM_FAILURE, "provider_failure", False, "provider", "provider_failure"),
    ("timeout", CapabilityStatus.TIMEOUT, "provider_timeout", False, "provider", "provider_timeout"),
])
@pytest.mark.asyncio
async def test_diagnostics_preserve_actual_wire_runtime_assertions(monkeypatch, caplog, fault, status, failure, decoded, stage, reason):
    budget = SimpleNamespace(model_failures=[])
    original = DeepSeekChatTransport.complete, KnowledgeRewriteTaskV4.definition
    with diag.diagnostic_scope(budget):
        # Reuse all original real-decoder/production-root assertions with HTTP fake.
        await wire_check(monkeypatch, caplog, fault, status, failure, decoded)
    assert (DeepSeekChatTransport.complete, KnowledgeRewriteTaskV4.definition) == original
    expected = [] if stage is None else [{"taskId": "knowledge_rewrite", "taskVersion": "4", "stage": stage, "reason": reason}]
    assert diag.validate_rows(budget.model_failures) == expected
    assert "synthetic-response" not in json.dumps(budget.model_failures)


def response(content):
    return StructuredModelResponse(finish_kind=StructuredFinishKind.STOP, content=content, tool_calls=(), usage_total_tokens=1)


@pytest.mark.parametrize("content,reason", [
    ('[]', "model.json_object_required"),
    ('{"outcome":"invalid","queries":[],"missing_conditions":[]}', "outcome_invalid"),
    ('{"outcome":"search","queries":[],"missing_conditions":[]}', "queries_contract_invalid"),
    ('{"outcome":"search","queries":[{}],"missing_conditions":[]}', "queries_contract_invalid"),
    ('{"outcome":"search","queries":[{"domain_id":"unknown","query":"safe"}],"missing_conditions":[]}', "task_contract_invalid"),
    ('{"outcome":"clarification_required","queries":[],"missing_conditions":["subject","subject"]}', "missing_conditions_invalid"),
    ('{"outcome":"unsupported","queries":[],"missing_conditions":null}', "missing_conditions_invalid"),
])
def test_task_classifier_runs_only_after_original_rejection(content, reason):
    original = KnowledgeRewriteTaskV4.definition()
    value = response(content)
    with pytest.raises(InvalidModelOutput) as baseline:
        original.parse_response(value)
    budget = SimpleNamespace(model_failures=[])
    with diag.diagnostic_scope(budget), pytest.raises(InvalidModelOutput) as observed:
        definition = KnowledgeRewriteTaskV4.definition()
        assert replace(definition, parse_response=original.parse_response) == original
        definition.parse_response(value)
    assert str(observed.value) == str(baseline.value)
    assert budget.model_failures[0]["reason"] == reason


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_original_exception_identity_restoration_and_no_free_text(monkeypatch, cancel):
    error = asyncio.CancelledError() if cancel else InvalidModelOutput("private-response-must-not-persist")
    async def failing(self, request, *, call_deadline):
        raise error
    monkeypatch.setattr(DeepSeekChatTransport, "complete", failing)
    budget = SimpleNamespace(model_failures=[])
    value = KnowledgeRewriteTaskV4.definition().build_request(KnowledgeSemanticPlanInput(
        minimized_question="安全测试", enabled_domain_ids=("tax.policy",)))
    with diag.diagnostic_scope(budget), pytest.raises(type(error)) as caught:
        await DeepSeekChatTransport.complete(None, value, call_deadline=1)
    assert caught.value is error
    assert DeepSeekChatTransport.complete is failing
    assert "private-response" not in json.dumps(budget.model_failures)
    assert budget.model_failures[0]["reason"] == ("cancelled" if cancel else "provider_invalid_output")


def test_diagnostic_contexts_are_isolated_and_fallback_is_finite():
    outer, inner = SimpleNamespace(model_failures=[]), SimpleNamespace(model_failures=[])
    failed = SimpleNamespace(model_calls=[{"taskId": "knowledge_rewrite", "taskVersion": "4", "status": "failed", "failureKind": "private-marker"}])
    with diag.diagnostic_scope(outer):
        with diag.diagnostic_scope(inner), pytest.raises(InvalidModelOutput):
            KnowledgeRewriteTaskV4.definition().parse_response(response("not json"))
        assert outer.model_failures == []
        assert len(inner.model_failures) == 1
        rows = diag.failure_rows(failed)
        assert rows[0]["reason"] == "unknown_failure" and rows[0]["stage"] == "gateway"
    assert "private-marker" not in json.dumps(rows)


@pytest.mark.parametrize("mutate", [
    lambda rows: rows[0].update(extra="private"),
    lambda rows: rows[0].update(reason="private"),
    lambda rows: rows[0].update(taskVersion="3"),
    lambda rows: rows[0].update(stage="private"),
    lambda rows: rows.extend(rows * 3),
    lambda rows: rows.append(dict(rows[0])),
])
def test_output_schema_rejects_unbounded_or_unknown_diagnostics(mutate):
    rows = [{"taskId": "knowledge_rewrite", "taskVersion": "4", "stage": "gateway", "reason": "invalid_output"}]
    mutate(rows)
    with pytest.raises(ValueError, match="diagnostic_schema_invalid"):
        diag.validate_rows(rows)


def test_prior_budgets_and_scoped_bindings_restore():
    rows = new.prior_bindings()
    assert [sum(row["calls"][key] for row in rows) for key in ("e2e", "model", "search", "embedding", "rerank")] == [3, 7, 4, 2, 2]
    original = old.RUN_ID, old.run_server, old.Budget, old.assess
    with new.run_03_bindings():
        assert old.RUN_ID == new.RUN_ID and old.Budget == new.Run03Budget
    assert (old.RUN_ID, old.run_server, old.Budget, old.assess) == original


@pytest.mark.parametrize("failed", [False, True])
def test_diagnostics_do_not_change_existing_acceptance_verdict(failed):
    spec = old.CASES[0]
    observation = SimpleNamespace(plans=[], downstream_calls=[], model_calls=[
        {"taskId": "action_selection", "taskVersion": "action-selection-v4", "status": "succeeded"},
        {"taskId": "knowledge_rewrite", "taskVersion": "4", "status": "failed" if failed else "succeeded",
         "failureKind": "invalid_output" if failed else None}])
    result = {"status": "downstream_failure" if failed else "no_result", "capabilityId": "knowledge.query",
              "result": {"reason": "clarification_required", "points": []}}
    expected = v2.assess(spec, result, observation, [])
    actual = new.assess(spec, result, observation, [])
    rows = actual.pop("modelFailures")
    assert actual == expected and actual["passed"] is not failed
    assert len(rows) == int(failed)


@pytest.mark.asyncio
async def test_new_batch_budget_resets_diagnostics_and_never_resumes(tmp_path):
    with new.run_03_bindings():
        budget = new.Run03Budget(tmp_path, "a" * 64, lambda row: None)
        try:
            for spec in old.CASES:
                budget.begin(spec)
                assert budget.model_failures == [] and budget.per_case["e2e"] == 1
                budget.model_failures.append({"synthetic": "not serialized"})
                for task in ("action_selection", "knowledge_rewrite", "knowledge_summary"):
                    await budget.model_request(request(task, spec["question"]))
            assert budget.totals["model"] == 30 and budget.totals["e2e"] == 10
            assert json.loads((tmp_path / "consumed.json").read_text())["runId"] == new.RUN_ID
            with pytest.raises(ValueError):
                budget.begin(old.CASES[0])
        finally:
            budget.journal.close()


@pytest.fixture
def manifest_root(tmp_path, monkeypatch):
    value = {"schemaVersion": 1, "runId": old.RUN_ID, "frozenHead": "a" * 40, "authorizationReference": "old",
             "limits": old.LIMITS, "cases": old.CASES, "gold": old.GOLD, "environment": old.ENV,
             "indexBinding": {}, "assets": {}, "executables": {}, "taskVersions": {}, "evaluation": "unchanged"}
    monkeypatch.setattr(v2, "_prepare", lambda root: value)
    monkeypatch.setattr(old, "git", lambda *args: "a" * 40 if args[0] == "rev-parse" else "")
    new.prepare(tmp_path)
    return tmp_path


def test_manifest_new_freeze_and_unchanged_gold(manifest_root):
    path = manifest_root / "manifest.json"
    manifest, _ = new.validate_manifest(manifest_root, old.digest(path.read_bytes()))
    assert manifest["schemaVersion"] == 3 and manifest["diagnosticVersion"] == diag.VERSION
    assert manifest["cases"] == list(old.CASES) and manifest["gold"] == old.GOLD
    assert len(manifest["priorRuns"]) == 2
    with pytest.raises(FileExistsError):
        new.prepare(manifest_root)


@pytest.mark.parametrize("field,value", [("schemaVersion", True), ("priorRuns", []), ("cumulativeLimits", {}),
    ("diagnosticVersion", "other"), ("authorizationReference", "old"), ("runRoot", "elsewhere"),
    ("taskVersions", {}), ("promptHashes", {})])
def test_manifest_tamper_rejected(manifest_root, field, value):
    path = manifest_root / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest[field] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="run_03_binding_invalid"):
        new.validate_manifest(manifest_root)


@pytest.mark.parametrize("artifact", ["journal.jsonl", "consumed.json", "evidence.jsonl", "result.json"])
def test_execution_assets_reject_resume(manifest_root, artifact):
    (manifest_root / artifact).touch()
    with pytest.raises(ValueError, match="retry_resume_forbidden"):
        new.validate_manifest(manifest_root)
