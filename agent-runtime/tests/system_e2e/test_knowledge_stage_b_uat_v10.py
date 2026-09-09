"""Current batch reuses the unchanged contract tests with new bounded bindings."""
import json
import sys

import pytest

from agent_runtime.model import gateway
from agent_runtime.model.contracts import InvalidModelOutput
from tests.system_e2e import knowledge_stage_b_uat_v10 as new
from tests.system_e2e.test_knowledge_stage_b_uat_v9 import (
    budget, manifest_root, preflight,
    test_whole_original_ten_exact_maximum_budget,
    test_clarification_zero_downstream_before_outbound,
    test_per_case_and_total_limits, test_total_budget_blocks_before_attempt,
    test_model_contract_rejects_mutation, test_summary_bound_to_actual_original_evidence,
    test_original_source_and_gold_not_weakened,
    test_current_root_capture_provider_wire_and_context_observer,
    test_manifest_exact_complete_asset_set, test_partial_or_terminal_never_resumes,
)


@pytest.fixture(autouse=True)
def scoped(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with new.bindings():
        yield


def test_exact_history_and_additional_diagnostic_not_hidden():
    rows = new.prior_bindings()
    assert len(rows) == 9
    assert {k: sum(r["calls"][k] for r in rows) for k in new.TOTAL_LIMITS} == dict(
        e2e=18, model=43, search=27, embedding=14, rerank=14, business=0, retry=0, resume=0)
    assert sum(row["startupCalls"].get("rerank", 0) for row in rows) == 1
    assert new.TOTAL_LIMITS["model"] == 71
    result = json.loads((new.DIAGNOSTIC / "result.json").read_bytes())
    assert result["counts"]["model"] == 1 and result["failureKind"] is None


def test_new_manifest_and_authorization(manifest_root):
    manifest, sha = new.previous.validate_manifest(manifest_root)
    assert manifest["schemaVersion"] == 10 and len(manifest["priorRuns"]) == 9
    assert manifest["runId"] == new.RUN_ID and manifest["authorizationReference"] == new.REFERENCE
    assert manifest["diagnostic"]["hashes"] == new.DIAGNOSTIC_HASHES
    assert manifest["cases"] == list(new.previous.CASES) and manifest["gold"] == new.previous.GOLD
    assert manifest["taskVersions"] == dict(selection="action-selection-v4", rewrite="8", summary="6")
    assert manifest["failureObservationVersion"] == "finite-throw-site-v1"
    preflight(manifest_root, sha)
    auth = new.previous.authorization(manifest, sha)
    new.previous.legacy.write_exclusive(manifest_root / "authorization.json", auth)
    assert new.previous.validate_authorized(manifest_root, sha)[1] == sha
    assert auth["runId"] == new.RUN_ID and auth["cumulativeLimits"] == new.TOTAL_LIMITS


@pytest.mark.parametrize("field,value", [("diagnostic", {}), ("failureObservationVersion", "old")])
def test_observation_and_diagnostic_cannot_drift(manifest_root, field, value):
    path = manifest_root / "manifest.json"
    data = json.loads(path.read_bytes()); data[field] = value
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError): new.previous.validate_manifest(manifest_root)


@pytest.mark.asyncio
async def test_finite_failure_observer_preserves_callback_and_restores(budget, monkeypatch):
    original_calls, rows = [], []
    def original(sequence, kind): original_calls.append((sequence, kind, sys.exception()))
    monkeypatch.setattr(gateway, "model_call_failed", original)
    async def fake_server(token, emit, active):
        budget.begin(new.previous.CASES[0]); budget.begin(new.previous.CASES[1])
        budget.seen_tasks.update(("action_selection", "knowledge_rewrite"))
        for _ in range(5):
            try:
                raise InvalidModelOutput("knowledge.invalid_requirement_plan") from ValueError("synthetic-private-marker")
            except InvalidModelOutput:
                gateway.model_call_failed(2, "invalid_output")
        raise KeyboardInterrupt()
    monkeypatch.setattr(new, "_run_server", fake_server)
    with pytest.raises(KeyboardInterrupt):
        await new.run_server("synthetic-token", rows.append, budget)
    assert gateway.model_call_failed is original and len(original_calls) == 5
    assert len(rows) == 3 and budget.probes == rows
    assert all(r == dict(stage="model_failure_diagnostic", caseId="UAT-KB-015a", taskId="knowledge_rewrite",
                        phase="rewrite_decoder", code="knowledge.invalid_requirement_plan", cause="shape_or_enum",
                        throwSite="unknown") for r in rows)
    assert "synthetic-private-marker" not in json.dumps(rows)
    assert budget.totals["model"] == 0


def test_scope_restores_all_patches():
    before = (new.previous.RUN_ID, new.previous.legacy.Budget, gateway.model_call_failed)
    with pytest.raises(KeyboardInterrupt), new.bindings():
        raise KeyboardInterrupt()
    assert before == (new.previous.RUN_ID, new.previous.legacy.Budget, gateway.model_call_failed)
