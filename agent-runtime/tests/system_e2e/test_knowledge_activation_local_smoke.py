"""Non-live safety tests; importing the diagnostic never starts local services."""
from dataclasses import replace
import json

import httpx
import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.knowledge.contracts import KnowledgeEvidenceRequirement, KnowledgeRequirementKind
from tests.evaluation.knowledge.retrieval_benchmark_dataset import load_dataset
from tests.integration.knowledge.test_requirement_runtime_composition import Clients, CONTENTS, FOCUSES, QUESTION
from tests.system_e2e import knowledge_activation_local_smoke as smoke


@pytest.mark.asyncio
@pytest.mark.parametrize("url,method,headers", [
    ("https://api.deepseek.com/chat/completions", "POST", {}),
    ("http://127.0.0.1:9200/_search", "POST", {}),
    ("http://127.0.0.1:9210/employees/es/search", "POST", {}),
    ("http://127.0.0.1:19201/es/knowledge/search", "GET", {}),
    ("http://127.0.0.1:8908/embed", "POST", {"Authorization": "secret"}),
    ("http://127.0.0.1:8909/rerank?extra=true", "POST", {}),
])
async def test_forbidden_outbound_latches_stop_without_consuming_or_leaking(url, method, headers):
    budget = smoke.LocalBudget()
    with pytest.raises(smoke.SmokeFailure, match="^outbound_not_allowed$"):
        await budget.request(httpx.Request(method, url, headers=headers))
    with pytest.raises(smoke.SmokeFailure):
        await budget.request(httpx.Request("POST", "http://127.0.0.1:8908/embed"))
    assert not budget.counts and budget.stopped


@pytest.mark.asyncio
async def test_budget_counts_attempts_and_never_automatically_resumes():
    budget = smoke.LocalBudget()
    request = httpx.Request("POST", "http://127.0.0.1:8908/embed")
    for _ in range(smoke.LIMITS["embedding"]):
        await budget.request(request)
    with pytest.raises(smoke.SmokeFailure, match="local_budget_exhausted"):
        await budget.request(request)
    assert budget.counts == {"embedding": 3} and budget.stopped


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,status,tasks", [(None, CapabilityStatus.NO_RESULT, 3),
    ("denied", CapabilityStatus.FORBIDDEN, 2), ("all_failed", CapabilityStatus.DOWNSTREAM_FAILURE, 2)])
async def test_current_root_fake_summary_no_answer_and_finite_observation(monkeypatch, fault, status, tasks):
    clients = Clients(fault=fault)
    monkeypatch.setattr(smoke, "build_knowledge_http_client", clients)
    case = replace(load_dataset().cases[0], question=QUESTION, requirements=(KnowledgeEvidenceRequirement(
        requirement_id="r1", domain_id="tax.policy", kind=KnowledgeRequirementKind.RULE, focus=FOCUSES[0]),))
    result, row = await smoke.run_case(case, "header.payload.signature", smoke.LocalBudget())
    assert result.status is status and len(row["fakeModelTasks"]) == tasks
    assert all(c.is_closed for c in clients.clients)
    visible = json.dumps(row, ensure_ascii=False)
    assert "header.payload.signature" not in visible and all(c not in visible for c in CONTENTS)
    if fault is None:
        assert row["reason"] == "insufficient_evidence"
        assert row["selection"] == [{"version": "optional-evidence-score-v1", "verified": 3, "selected": 1}]
        assert len(row["evidenceHashes"]) == 1
        assert row["retrievalPathsComplete"]
    else:
        assert row["selection"] == [] and row["evidenceHashes"] == []
        assert not row["retrievalPathsComplete"]


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["vector_http", "embed_timeout"])
async def test_partial_vector_failure_cannot_pass_complete_integration(monkeypatch, fault):
    clients = Clients(fault="partial" if fault == "vector_http" else None)

    def factory(url):
        client = clients(url)
        async def response_hook(response):
            if fault == "embed_timeout" and response.request.url.path == "/embed":
                raise httpx.ReadTimeout("synthetic")
        client.event_hooks["response"].append(response_hook)
        return client

    monkeypatch.setattr(smoke, "build_knowledge_http_client", factory)
    case = replace(load_dataset().cases[0], question=QUESTION, requirements=(KnowledgeEvidenceRequirement(
        requirement_id="r1", domain_id="tax.policy", kind=KnowledgeRequirementKind.RULE, focus=FOCUSES[0]),))
    result, row = await smoke.run_case(case, "header.payload.signature", smoke.LocalBudget())
    assert result.status is CapabilityStatus.NO_RESULT and row["reason"] == "insufficient_evidence"
    assert len(row["fakeModelTasks"]) == 3 and row["selection"]
    assert not row["retrievalPathsComplete"]
    if fault == "vector_http":
        assert any(entry["httpStatus"] == 500 for entry in row["http"])
    else:
        assert row["counts"]["search"] == 1
        assert any(entry["status"] != "completed" for entry in row["http"])


@pytest.mark.asyncio
async def test_sensitive_input_no_model_or_transport(monkeypatch):
    clients = Clients()
    monkeypatch.setattr(smoke, "build_knowledge_http_client", clients)
    result, row = await smoke.run_case(load_dataset().cases[0], "header.payload.signature", smoke.LocalBudget(),
                                      question="税务查询 test@example.com")
    assert result.status is CapabilityStatus.MODEL_EGRESS_DENIED
    assert not row["fakeModelTasks"] and not clients.paths and all(c.is_closed for c in clients.clients)
