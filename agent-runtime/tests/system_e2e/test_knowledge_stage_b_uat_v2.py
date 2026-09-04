from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from tests.system_e2e import knowledge_stage_b_uat as old
from tests.system_e2e import knowledge_stage_b_uat_v2 as new


def request(task, question, *, instruction=None):
    prompts = {"action_selection": new.ACTION_SELECTION_SYSTEM_INSTRUCTION,
               "knowledge_rewrite": new.INSTRUCTION, "knowledge_summary": new.SUMMARY_PROMPT_V4}
    payload = {"question": question}
    if task == "action_selection":
        payload["capabilities"] = []
    elif task == "knowledge_rewrite":
        payload["domains"] = []
    else:
        payload.update(schema_version=1, coverage={}, evidence=[{"content": "synthetic public source"}])
    return httpx.Request("POST", old.ModelSettings.BASE_URL + "/chat/completions", json={
        "messages": [{"role": "system", "content": instruction if instruction is not None else prompts[task]},
                     {"role": "user", "content": json.dumps(payload)}]})


@pytest.fixture
def budget(tmp_path):
    with new.run_02_bindings():
        value = new.Run02Budget(tmp_path, "a" * 64, lambda _: None)
        yield value
        value.journal.close()


def test_scoped_bindings_restore_frozen_runner():
    before = (old.RUN_ID, old.prepare, old.validate_manifest, old.Budget, old.assess)
    with new.run_02_bindings():
        assert old.RUN_ID == new.RUN_ID != before[0]
        assert old.Budget is new.Run02Budget
    assert (old.RUN_ID, old.prepare, old.validate_manifest, old.Budget, old.assess) == before


def test_prior_failed_run_is_verified_and_cumulative_budget_remains_bounded():
    prior = new.prior_binding()
    assert prior["calls"]["e2e"] + old.LIMITS["e2e"] == 11 <= 20
    assert prior["calls"]["model"] + old.LIMITS["model"] == 33 <= 60
    assert prior["calls"]["search"] + old.LIMITS["search"] == 44 <= 80


@pytest.mark.asyncio
async def test_current_prompts_journal_and_correct_per_case_e2e(budget):
    budget.begin(old.CASES[0])
    for task in ("action_selection", "knowledge_rewrite"):
        await budget.model_request(request(task, old.CASES[0]["question"]))
    assert budget.per_case["e2e"] == budget.totals["e2e"] == 1
    assert budget.per_case["model"] == 2
    consumed = json.loads((budget.root / "consumed.json").read_text())
    assert consumed["runId"] == new.RUN_ID
    assert old.CASES[0]["question"] not in (budget.root / "journal.jsonl").read_text()
    with pytest.raises(ValueError, match="case_order_invalid"):
        budget.begin(old.CASES[0])


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_instruction", ["synthetic wrong instruction", ""])
async def test_prompt_drift_stops_before_any_model_send(budget, bad_instruction):
    budget.begin(old.CASES[0])
    with pytest.raises(ValueError, match="model_request_rejected"):
        await budget.model_request(request("action_selection", old.CASES[0]["question"], instruction=bad_instruction))
    assert budget.stopped and budget.totals["model"] == 0
    assert not (budget.root / "consumed.json").exists()
    with pytest.raises(ValueError, match="batch_stopped"):
        budget.begin(old.CASES[1])


@pytest.mark.asyncio
async def test_full_fake_budget_is_30_not_remaining_prior_authorization(budget):
    for spec in old.CASES:
        budget.begin(spec)
        for task in ("action_selection", "knowledge_rewrite", "knowledge_summary"):
            await budget.model_request(request(task, spec["question"]))
    assert budget.totals["e2e"] == 10 and budget.totals["model"] == 30
    with pytest.raises(ValueError, match="case_order_invalid"):
        budget.begin(old.CASES[-1])
    assert len((budget.root / "journal.jsonl").read_text().splitlines()) == 30
    assert "synthetic public source" not in (budget.root / "journal.jsonl").read_text()


@pytest.mark.asyncio
async def test_business_and_fifth_search_remain_forbidden(budget):
    budget.begin(old.CASES[0])
    req = httpx.Request("POST", "http://127.0.0.1:19201/es/knowledge/search")
    for _ in range(4):
        await budget.downstream_request(req)
    with pytest.raises(ValueError, match="budget_exceeded"):
        await budget.downstream_request(req)
    assert budget.totals["search"] == 4
    with pytest.raises(ValueError):
        await budget.business_request()
    assert budget.totals["business"] == 0


def test_assessment_requires_current_task_binding_and_unchanged_gold():
    spec = old.CASES[0]
    response = {"status": "no_result", "capabilityId": "knowledge.query",
                "result": {"reason": "clarification_required", "points": []}}
    observation = SimpleNamespace(plans=[], downstream_calls=[], model_calls=[
        {"taskId": "action_selection", "taskVersion": "action-selection-v4", "status": "succeeded"},
        {"taskId": "knowledge_rewrite", "taskVersion": "4", "status": "succeeded"}])
    assert new.assess(spec, response, observation, [])["passed"]
    observation.downstream_calls = [{"target": "es-query-service"}]
    assert not new.assess(spec, response, observation, [])["passed"]
    observation.downstream_calls = []
    observation.model_calls[-1]["taskVersion"] = "3"
    assert not new.assess(spec, response, observation, [])["passed"]


@pytest.fixture
def manifest_root(tmp_path, monkeypatch):
    manifest = {"schemaVersion": 1, "runId": old.RUN_ID, "frozenHead": "a" * 40,
                "authorizationReference": "old", "limits": old.LIMITS, "cases": old.CASES,
                "gold": old.GOLD, "environment": old.ENV, "indexBinding": {},
                "assets": {}, "executables": {}, "taskVersions": {}, "evaluation": "unchanged"}
    monkeypatch.setattr(new, "_prepare", lambda _: manifest)
    monkeypatch.setattr(old, "git", lambda *args: "a" * 40 if args[0] == "rev-parse" else "")
    new.prepare(tmp_path)
    return tmp_path


def test_manifest_freezes_v4_prompts_history_and_exact_new_authorization(manifest_root):
    path = manifest_root / "manifest.json"
    value, sha = new.validate_manifest(manifest_root, old.digest(path.read_bytes()))
    assert sha and value["schemaVersion"] == 2
    assert value["runId"] == new.RUN_ID and value["authorizationReference"] == new.REFERENCE
    assert value["taskVersions"] == new.TASK_VERSIONS
    assert value["promptHashes"] == new.prompt_hashes()
    with pytest.raises(FileExistsError):
        new.prepare(manifest_root)


@pytest.mark.parametrize("field,value", [("taskVersions", {"rewrite": "3"}), ("promptHashes", {}),
    ("authorizationReference", "old"), ("cumulativeLimits", {}), ("priorRun", {}),
    ("runRoot", "elsewhere"), ("schemaVersion", True)])
def test_binding_tampering_fails_before_execution(manifest_root, field, value):
    path = manifest_root / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest[field] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="run_02_binding_invalid"):
        new.validate_manifest(manifest_root)


@pytest.mark.parametrize("artifact", ["consumed.json", "journal.jsonl", "result.json", "evidence.jsonl"])
def test_existing_execution_artifact_forbids_resume(manifest_root, artifact):
    (manifest_root / artifact).touch()
    with pytest.raises(ValueError, match="retry_resume_forbidden"):
        new.validate_manifest(manifest_root)
