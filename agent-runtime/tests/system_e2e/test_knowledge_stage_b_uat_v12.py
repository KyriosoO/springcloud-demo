"""Non-live proof of the new prompt binding, budgets and original acceptance."""
import json
import httpx
import pytest

from agent_runtime.knowledge.evidence.summary_task_v7 import SUMMARY_PROMPT_V7
from tests.system_e2e import knowledge_stage_b_uat_v12 as new
from tests.system_e2e.test_knowledge_stage_b_uat_v9 import (
    budget, manifest_root, preflight,
    test_whole_original_ten_exact_maximum_budget,
    test_clarification_zero_downstream_before_outbound,
    test_per_case_and_total_limits, test_total_budget_blocks_before_attempt,
    test_model_contract_rejects_mutation, test_summary_bound_to_actual_original_evidence,
    test_original_source_and_gold_not_weakened,
    test_current_root_capture_provider_wire_and_context_observer,
    test_manifest_exact_complete_asset_set, test_partial_or_terminal_never_resumes,
    test_bad_preflight_cannot_authorize, test_authorization_exact_binding,
)


@pytest.fixture(autouse=True)
def scoped(monkeypatch):
    from tests.system_e2e import test_knowledge_stage_b_uat_v8 as checks
    original = checks.request
    def current_request(task, question, payload=None):
        request = original(task, question, payload)
        if task != "knowledge_summary":
            return request
        body = json.loads(request.content)
        body["messages"][0]["content"] = SUMMARY_PROMPT_V7
        return httpx.Request(request.method, str(request.url), json=body)
    # Only migrate the current fake request builder; old test files/runner stay frozen.
    monkeypatch.setattr(checks, "request", current_request)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setattr(new.previous, "java_binding", lambda: dict(version="25.0.2", sha256="a" * 64))
    with new.bindings():
        yield


def test_real_history_counts_and_separate_diagnostic():
    rows = new.prior_bindings()
    assert len(rows) == 10  # run-10 is separately bound as failed preflight.
    assert {k: sum(r["calls"][k] for r in rows) for k in new.TOTAL_LIMITS} == dict(
        e2e=20, model=48, search=29, embedding=15, rerank=15, business=0, retry=0, resume=0)
    assert sum(r["startupCalls"].get("rerank", 0) for r in rows) + 1 == 3
    assert new.TOTAL_LIMITS["model"] + 1 == 77


def test_current_manifest_freezes_seven_and_new_prompt(manifest_root):
    manifest, sha = new.v9.validate_manifest(manifest_root)
    assert manifest["schemaVersion"] == 12
    assert manifest["taskVersions"] == dict(selection="action-selection-v4", rewrite="8", summary="7")
    assert manifest["promptHashes"]["knowledge_summary"] == new.v9.legacy.digest(SUMMARY_PROMPT_V7.encode())
    assert manifest["priorRuns"][-1]["hashes"] == new.HASHES
    assert manifest["failedPreflight"]["model"] == 0
    preflight(manifest_root, sha)
    auth = new.v9.authorization(manifest, sha)
    assert auth["cumulativeLimits"] == new.TOTAL_LIMITS
    new.v9.legacy.write_exclusive(manifest_root / "authorization.json", auth)
    new.v9.validate_authorized(manifest_root, sha)


def test_prior_history_tampering_and_cap_fail_closed(monkeypatch):
    with monkeypatch.context() as local:
        local.setattr(new, "HASHES", {**new.HASHES, "result.json": "0" * 64})
        with pytest.raises(ValueError, match="prior_run_changed"): new.prior_bindings()
    with monkeypatch.context() as local:
        local.setattr(new, "TOTAL_LIMITS", {**new.TOTAL_LIMITS, "model": 75})
        with pytest.raises(ValueError, match="cumulative_budget_invalid"): new.prior_bindings()


def test_scoped_changes_restore_on_failure():
    before = (new.v9.TASKS, new.v8.prompt_hashes, new.previous.current_manifest, new.v10.prior_bindings)
    with pytest.raises(RuntimeError):
        with new.overrides():
            assert new.v9.TASKS["knowledge_summary"] == "7"
            raise RuntimeError("synthetic")
    assert before == (new.v9.TASKS, new.v8.prompt_hashes, new.previous.current_manifest, new.v10.prior_bindings)


@pytest.mark.asyncio
async def test_previous_summary_instruction_rejected_before_outbound(budget):
    from agent_runtime.knowledge.evidence.summary_task_v6 import SUMMARY_PROMPT_V6
    from tests.system_e2e import test_knowledge_stage_b_uat_v8 as checks
    budget.begin(new.v9.CASES[0]); budget.begin(new.v9.CASES[1])
    question = budget.current["question"]
    for task in tuple(new.TASKS)[:2]:
        await budget.model_request(checks.request(task, question))
    checks.summary_source(budget)
    payload = json.loads(new.v8.summary.requirement_summary_input_json(budget.summary_input))
    request = checks.request("knowledge_summary", question, payload)
    body = json.loads(request.content)
    body["messages"][0]["content"] = SUMMARY_PROMPT_V6
    with pytest.raises(ValueError, match="model_request_rejected"):
        await budget.model_request(httpx.Request(request.method, str(request.url), json=body))
    assert budget.totals["model"] == 2 and budget.stopped
