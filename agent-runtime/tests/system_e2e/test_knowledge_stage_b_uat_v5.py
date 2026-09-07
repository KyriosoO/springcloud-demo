"""Fake-only run-05 binding, budget, version and immutable-verdict checks."""
import json
from types import SimpleNamespace

import pytest

from agent_runtime.knowledge.rewrite_v6 import KnowledgeRewriteTaskV6
from tests.system_e2e import knowledge_stage_b_failure_diagnostics as diag
from tests.system_e2e import knowledge_stage_b_uat as old
from tests.system_e2e import knowledge_stage_b_uat_v2 as v2
from tests.system_e2e import knowledge_stage_b_uat_v4 as v4
from tests.system_e2e import knowledge_stage_b_uat_v5 as new
from tests.system_e2e import test_knowledge_stage_b_uat_v4 as previous_tests
from tests.system_e2e.test_knowledge_stage_b_uat_v2 import request as old_request


def request(task, question):
    prompts = {"action_selection": new.ACTION_SELECTION_SYSTEM_INSTRUCTION,
               "knowledge_rewrite": new.INSTRUCTION, "knowledge_summary": new.SUMMARY_PROMPT_V5}
    return old_request(task, question, instruction=prompts[task])


def test_prior_budget_and_exclusive_scope_restore():
    before = old.RUN_ID, old.Budget, old.assess, diag.TASKS, diag.KnowledgeRewriteTaskV4
    with pytest.raises(RuntimeError), new.run_05_bindings():
        assert old.RUN_ID == new.RUN_ID
        assert diag.KnowledgeRewriteTaskV4 is KnowledgeRewriteTaskV6
        rows = new.prior_bindings()
        assert len(rows) == 4
        assert [sum(row["calls"][key] for row in rows) for key in
                ("e2e", "model", "search", "embedding", "rerank")] == [8, 20, 14, 7, 7]
        assert all(sum(row["calls"][key] for row in rows) + old.LIMITS[key] <= limit
                   for key, limit in v2.TOTAL_LIMITS.items())
        raise RuntimeError("synthetic")
    assert (old.RUN_ID, old.Budget, old.assess, diag.TASKS, diag.KnowledgeRewriteTaskV4) == before


@pytest.mark.parametrize("value", [True, -1, 60])
def test_cumulative_excess_or_invalid_counts_fail(monkeypatch, value):
    rows = v4.prior_bindings()
    rows[0]["calls"]["model"] = value
    monkeypatch.setattr(v4, "prior_bindings", lambda: rows)
    with pytest.raises(ValueError, match="cumulative_budget_invalid"):
        new.prior_bindings()


def test_history_drift_fails(monkeypatch):
    monkeypatch.setattr(new, "RUN04_HASHES", {**new.RUN04_HASHES, "result.json": "0" * 64})
    with pytest.raises(ValueError, match="prior_run_changed"):
        new.prior_bindings()


@pytest.fixture
def budget(tmp_path):
    with new.run_05_bindings():
        value = old.Budget(tmp_path, "a" * 64, lambda row: None)
        yield value
        value.journal.close()


@pytest.mark.asyncio
async def test_full_fake_budget_and_forbidden_requests(budget, monkeypatch):
    monkeypatch.setattr(previous_tests, "request", request)
    monkeypatch.setattr(previous_tests, "new", new)
    await previous_tests.test_full_fake_budget_journal_and_stop(budget)


@pytest.mark.asyncio
async def test_wrong_prompt_repeated_task_rejected_before_outbound(budget, monkeypatch):
    monkeypatch.setattr(previous_tests, "request", request)
    await previous_tests.test_old_prompt_and_repeated_task_stop_before_outbound(budget)


@pytest.mark.asyncio
async def test_other_endpoint_and_excess_search_zero(budget):
    await previous_tests.test_business_and_excess_search_forbidden(budget)


@pytest.fixture
def manifest_root(tmp_path, monkeypatch):
    value = {"schemaVersion": 1, "runId": old.RUN_ID, "frozenHead": "a" * 40, "authorizationReference": "old",
             "limits": old.LIMITS, "cases": old.CASES, "gold": old.GOLD, "environment": old.ENV,
             "indexBinding": {}, "assets": {}, "executables": {}, "taskVersions": {}, "evaluation": "unchanged"}
    monkeypatch.setattr(v2, "_prepare", lambda root: value)
    monkeypatch.setattr(old, "git", lambda *args: "a" * 40 if args[0] == "rev-parse" else "")
    new.prepare(tmp_path)
    return tmp_path


def test_manifest_freezes_tasks_quality_and_original_gold(manifest_root):
    manifest, sha = new.validate_manifest(manifest_root, old.digest((manifest_root / "manifest.json").read_bytes()))
    assert manifest["schemaVersion"] == 5 and len(sha) == 64
    assert manifest["taskVersions"] == new.TASK_VERSIONS
    assert manifest["qualityVersion"] == new.KNOWLEDGE_QUALITY_VERSION_V2
    assert manifest["cases"] == list(old.CASES) and manifest["gold"] == old.GOLD
    assert len(manifest["priorRuns"]) == 4
    with pytest.raises(FileExistsError):
        new.prepare(manifest_root)


@pytest.mark.parametrize("field,value", [("schemaVersion", True), ("priorRuns", []), ("cumulativeLimits", {}),
    ("diagnosticVersion", "other"), ("authorizationReference", "old"), ("runRoot", "elsewhere"),
    ("taskVersions", v4.TASK_VERSIONS), ("promptHashes", {}), ("qualityVersion", "knowledge-retrieval-quality-v1")])
def test_manifest_tamper_rejected(manifest_root, field, value):
    path = manifest_root / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest[field] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="run_05_binding_invalid"):
        new.validate_manifest(manifest_root)


@pytest.mark.parametrize("name", ["journal.jsonl", "consumed.json", "evidence.jsonl", "result.json"])
def test_consumed_or_partial_assets_never_resume(manifest_root, name):
    (manifest_root / name).touch()
    with pytest.raises(ValueError, match="retry_resume_forbidden"):
        new.validate_manifest(manifest_root)


@pytest.mark.parametrize("spec", old.CASES, ids=lambda spec: spec["caseId"])
def test_original_source_clause_verdict_and_quality_version(spec):
    sources = [{"sha256": old.GOLD[g]["sha256"], "content": old.GOLD[g]["clause"]} for g in spec["requiredGold"]]
    points = [{"quote": source["content"], "citation": {"domainIds": spec["domains"]}} for source in sources]
    response = {"status": "no_result" if spec["reason"] else "success", "capabilityId": "knowledge.query",
                "result": {"reason": spec["reason"], "points": points}}
    plans = [] if spec["reason"] else [{"type": "knowledge_retrieval_plan", "plan": {
        "selected_domain_ids": spec["domains"], "quality_version": new.KNOWLEDGE_QUALITY_VERSION_V2}}]
    tasks = [("action_selection", "action-selection-v4"), ("knowledge_rewrite", "6")]
    if not spec["reason"]:
        tasks.append(("knowledge_summary", "5"))
    observation = SimpleNamespace(plans=plans, downstream_calls=[], model_calls=[
        dict(taskId=task, taskVersion=version, status="succeeded") for task, version in tasks])
    with new.run_05_bindings():
        assert new.assess(spec, response, observation, sources)["passed"]
        if plans:
            plans[0]["plan"]["quality_version"] = "knowledge-retrieval-quality-v1"
            assert not new.assess(spec, response, observation, sources)["passed"]
            plans[0]["plan"]["quality_version"] = new.KNOWLEDGE_QUALITY_VERSION_V2
        response["result"]["points"] = []
        if spec["reason"]:
            observation.downstream_calls.append({"synthetic": True})
        assert not new.assess(spec, response, observation, sources)["passed"]
