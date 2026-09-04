from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from agent_runtime.model.settings import ModelSettings
from tests.system_e2e.knowledge_stage_b_cases import CASES, GOLD, LIMITS, assess
from tests.system_e2e.knowledge_stage_b_services import stop_owned
from tests.system_e2e.knowledge_stage_b_uat import Budget, digest, validate_manifest


def request(payload):
    return httpx.Request("POST", ModelSettings.BASE_URL + "/chat/completions", json={
        "messages": [{"role": "system", "content": "synthetic"}, {"role": "user", "content": json.dumps(payload)}]})


@pytest.fixture
def budget(tmp_path):
    value = Budget(tmp_path, "a" * 64, lambda _: None)
    value.begin(CASES[0])
    yield value
    value.journal.close()


@pytest.mark.asyncio
async def test_paid_journal_consumption_precedes_send_and_cannot_retry(budget):
    payload = {"question": CASES[0]["question"], "capabilities": []}
    await budget.model_request(request(payload))
    assert (budget.root / "consumed.json").exists()
    journal = (budget.root / "journal.jsonl").read_text()
    assert json.loads(journal)["ordinal"] == 1
    assert "question" not in journal and CASES[0]["question"] not in journal
    with pytest.raises(ValueError, match="retry_or_input_mismatch"):
        await budget.model_request(request(payload))
    assert budget.totals["model"] == 1


@pytest.mark.asyncio
async def test_only_three_current_tasks_and_expected_order(budget):
    question = CASES[0]["question"]
    for payload in ({"question": question, "capabilities": []}, {"question": question, "domains": []},
                    {"schema_version": 1, "question": question, "coverage": {}, "evidence": [{"content": "synthetic public evidence"}]}):
        await budget.model_request(request(payload))
    assert budget.totals["model"] == 3
    assert budget.summary_evidence[0]["sha256"] == digest(b"synthetic public evidence")
    assert "synthetic public evidence" not in (budget.root / "journal.jsonl").read_text()
    with pytest.raises(ValueError):
        await budget.model_request(request({"question": question, "answer": []}))


@pytest.mark.asyncio
async def test_summary_cannot_skip_selection_and_rewrite(budget):
    with pytest.raises(ValueError, match="mismatch"):
        await budget.model_request(request({"schema_version": 1, "question": CASES[0]["question"], "coverage": {}, "evidence": []}))
    assert budget.totals["model"] == 0
    assert not (budget.root / "consumed.json").exists()


@pytest.mark.asyncio
async def test_business_and_unknown_endpoint_never_send(budget):
    with pytest.raises(ValueError, match="budget_exceeded"):
        await budget.business_request()
    assert budget.totals["business"] == 0
    with pytest.raises(ValueError):
        await budget.downstream_request(httpx.Request("POST", "http://127.0.0.1:19201/es/write"))
    assert budget.totals["search"] == 0


@pytest.mark.asyncio
async def test_local_endpoint_budgets_stop_before_fifth_search(budget):
    req = httpx.Request("POST", "http://127.0.0.1:19201/es/knowledge/search")
    for _ in range(4):
        await budget.downstream_request(req)
    with pytest.raises(ValueError, match="budget_exceeded"):
        await budget.downstream_request(req)
    assert budget.totals["search"] == 4
    with pytest.raises(ValueError, match="batch_stopped"):
        budget.begin(CASES[1])


def test_no_resume_even_before_first_paid_call(tmp_path, monkeypatch):
    from tests.system_e2e import knowledge_stage_b_uat as module
    monkeypatch.setattr(module, "git", lambda *a: "a" * 40 if a[0] == "rev-parse" else "")
    manifest = {"runId": module.RUN_ID, "frozenHead": "a" * 40, "limits": LIMITS,
                "cases": CASES, "gold": GOLD, "environment": module.ENV, "assets": {}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    assert validate_manifest(tmp_path)[0]["frozenHead"] == "a" * 40
    (tmp_path / "journal.jsonl").touch()
    with pytest.raises(ValueError, match="retry_resume_forbidden"):
        validate_manifest(tmp_path)


def test_source_presence_alone_is_not_a_p0_pass():
    spec = CASES[1]
    observation = SimpleNamespace(plans=[{"type": "knowledge_retrieval_plan", "plan": {"selected_domain_ids": ["tax.policy"]}}])
    sources = [{"sha256": GOLD[g]["sha256"], "content": GOLD[g]["clause"]} for g in spec["requiredGold"]]
    response = {"status": "success", "capabilityId": "knowledge.query", "result": {"points": []}}
    assert not assess(spec, response, observation, sources)["passed"]
    response["result"]["points"] = [{"quote": s["content"], "citation": {"domainIds": ["tax.policy"]}} for s in sources]
    assert assess(spec, response, observation, sources)["passed"]
    response["result"]["points"][0]["quote"] = "unrelated synthetic text"
    assert not assess(spec, response, observation, sources)["passed"]


def test_all_owned_processes_attempted_and_timeout_kills_only_owned():
    good, slow, inaccessible = Mock(), Mock(), Mock()
    good.poll.side_effect = [None, 0]
    slow.poll.side_effect = [None, 0]
    slow.wait.side_effect = [subprocess.TimeoutExpired("owned", 20), 0]
    inaccessible.poll.side_effect = [None, None]
    inaccessible.terminate.side_effect = OSError()
    assert not stop_owned([good, slow, inaccessible])
    good.terminate.assert_called_once()
    slow.kill.assert_called_once()
    inaccessible.kill.assert_not_called()


def test_tightened_budget_and_fixed_unique_cases():
    assert len(CASES) == 10 and len({c["caseId"] for c in CASES}) == 10
    assert LIMITS["model"] == 30 <= 60 and LIMITS["e2e"] <= 20
    assert LIMITS["business"] == LIMITS["retry"] == LIMITS["resume"] == 0


@pytest.mark.asyncio
async def test_budget_accepts_the_actual_current_summary_projection(budget):
    from dataclasses import replace
    from agent_runtime.model.deepseek.dto import project_deepseek_request
    from agent_runtime.knowledge.evidence.summary_task_v4 import KnowledgeSummaryTaskV4
    from tests.contract.knowledge.test_summary_task_v4 import _input
    question = CASES[0]["question"]
    await budget.model_request(request({"question": question, "capabilities": []}))
    await budget.model_request(request({"question": question, "domains": []}))
    structured = KnowledgeSummaryTaskV4.definition().build_request(replace(_input(), question=question))
    # Provider projection uses immutable mappings; canonical helper is the wire source.
    from agent_runtime.capability_api.contracts import canonical_json_bytes
    projected = canonical_json_bytes(project_deepseek_request(structured).payload)
    await budget.model_request(httpx.Request("POST", ModelSettings.BASE_URL + "/chat/completions", content=projected))
    assert budget.totals["model"] == 3 and len(budget.summary_evidence) == 2


def test_explicit_manifest_digest_is_required_to_match(tmp_path):
    (tmp_path / "manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="manifest_sha_mismatch"):
        validate_manifest(tmp_path, "f" * 64)
