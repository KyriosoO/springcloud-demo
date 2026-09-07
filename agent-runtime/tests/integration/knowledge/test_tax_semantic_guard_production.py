"""Current production root, synthetic model and domain transports; no live claim."""
import asyncio
import json

import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.knowledge.tax_question_semantics import TaxQuestionSemanticGuard
from agent_runtime.main import build_runtime
from agent_runtime.model.contracts import ModelTaskId
from agent_runtime.observation import observation_scope
from tests.helpers import scope
from tests.integration.knowledge.test_production_runtime_wiring import _enabled_environment
from tests.integration.knowledge.test_rewrite_v6_query_focus import RecordingClients
from tests.integration.knowledge.test_stage_b_production import PlanModel


ORIGINAL = "一般纳税人采用一般计税方法，2026年提供住宿服务适用何种增值税税率？"
REORDERED = "2026年一般纳税人采用一般计税方法提供住宿服务的增值税税率"


async def invoke(question, queries):
    model = PlanModel({"outcome": "search", "queries": [
        {"domain_id": domain, "query": query} for domain, query in queries], "missing_conditions": []})
    clients = RecordingClients()
    runtime = build_runtime({**_enabled_environment(), "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,tax.law"},
                            model_transport=model, knowledge_http_client_factory=clients)
    try:
        with observation_scope() as collector:
            result = await runtime.ainvoke(question=question, scope=scope(question))
            observation = collector.snapshot()
    finally:
        await runtime.aclose()
    assert all(client.is_closed for client in clients.clients)
    return result, model, clients, observation


@pytest.mark.asyncio
@pytest.mark.parametrize("service", ["住宿", "软件", "咨询"])
@pytest.mark.parametrize("domains", [("tax.policy",), ("tax.policy", "tax.law")])
async def test_category_order_is_not_a_quantity_change_and_query_is_not_locally_rewritten(service, domains):
    question, query = ORIGINAL.replace("住宿", service), REORDERED.replace("住宿", service)
    result, model, clients, observation = await invoke(question, tuple((d, query) for d in domains))
    assert result.status is CapabilityStatus.SUCCESS, result.failure
    assert [(r.task_id, r.task_version) for r in model.requests] == [
        (ModelTaskId.ACTION_SELECTION, "action-selection-v4"), (ModelTaskId.KNOWLEDGE_REWRITE, "6"),
        (ModelTaskId.KNOWLEDGE_SUMMARY, "5")]
    assert json.loads(model.requests[1].user_payload_json)["question"] == question
    assert json.loads(model.requests[2].user_payload_json)["question"] == question
    assert len(observation.plans) == 1
    assert observation.plans[0]["plan"]["selected_domain_ids"] == list(domains)
    assert {row["query_text"] for row in observation.plans[0]["plan"]["items"]} == {query}
    # The existing retrieval stage embeds each unique query once per request.
    assert len(clients.payloads) == 1 + len(domains) * 3
    assert sum(p == "/es/knowledge/search" for p, _ in clients.payloads) == len(domains) * 2
    assert [v["texts"] for p, v in clients.payloads if p == "/embed"] == [[query]]
    assert [v["query"] for p, v in clients.payloads if p == "/rerank"] == [query] * len(domains)
    assert all(v["queryText"] == query for p, v in clients.payloads
               if p == "/es/knowledge/search" and v["path"] == "keyword")


@pytest.mark.asyncio
@pytest.mark.parametrize("query", [
    REORDERED.replace("一般纳税人", ""),
    REORDERED.replace("一般纳税人", "小规模纳税人"),
    REORDERED.replace("一般计税", ""),
    REORDERED.replace("一般计税", "简易计税"),
    REORDERED + "小规模纳税人",
    REORDERED + "简易计税",
    REORDERED.replace("2026", "2027"),
    REORDERED.replace("2026年", ""),
    REORDERED + "6%",
])
async def test_category_or_real_quantity_changes_reject_whole_multi_domain_plan(query):
    result, model, clients, observation = await invoke(ORIGINAL, (("tax.policy", REORDERED), ("tax.law", query)))
    assert result.status is CapabilityStatus.DOWNSTREAM_FAILURE
    assert result.failure.code == "knowledge.rewrite_failure"
    assert [r.task_id for r in model.requests] == [ModelTaskId.ACTION_SELECTION, ModelTaskId.KNOWLEDGE_REWRITE]
    assert clients.payloads == [] and observation.plans == () and observation.downstream_calls == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("question,query", [
    ("一般计税2026年6％税率", "2026年一般计税6‰税率"),
    ("一般计税2026年百分之六税率", "2026年一般计税千分之六税率"),
    ("一般计税2026年6%税率", "一般计税6%税率2026年"),
    ("一般纳税人2026年不得适用", "2026年一般纳税人适用"),
])
async def test_unicode_ratio_and_negative_constraints_still_fail_closed(question, query):
    result, model, clients, observation = await invoke(question, (("tax.policy", query),))
    assert result.status is CapabilityStatus.DOWNSTREAM_FAILURE
    assert result.failure.code == "knowledge.rewrite_failure"
    assert len(model.requests) == 2 and clients.payloads == [] and observation.plans == ()


@pytest.mark.asyncio
async def test_guard_does_not_leak_original_constraints_between_concurrent_requests():
    model = PlanModel({"outcome": "search", "queries": [
        {"domain_id": "tax.policy", "query": REORDERED}], "missing_conditions": []})
    clients = RecordingClients()
    runtime = build_runtime(_enabled_environment(), model_transport=model, knowledge_http_client_factory=clients)

    async def one(question):
        with observation_scope() as collector:
            result = await runtime.ainvoke(question=question, scope=scope(question))
            return result, collector.snapshot()

    try:
        good, bad = await asyncio.gather(one(ORIGINAL), one(ORIGINAL.replace("2026", "2027")))
    finally:
        await runtime.aclose()
    assert good[0].status is CapabilityStatus.SUCCESS
    assert bad[0].status is CapabilityStatus.DOWNSTREAM_FAILURE
    assert bad[0].failure.code == "knowledge.rewrite_failure"
    assert len(good[1].plans) == 1 and bad[1].plans == ()
    assert len(good[1].downstream_calls) == 4 and bad[1].downstream_calls == ()
    assert len(model.requests) == 5 and len(clients.payloads) == 4
    assert all(client.is_closed for client in clients.clients)


@pytest.mark.asyncio
async def test_disabled_root_never_instantiates_current_tax_guard(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("disabled Knowledge must not create a tax guard")

    monkeypatch.setattr(TaxQuestionSemanticGuard, "__init__", forbidden)
    model = PlanModel({"outcome": "unsupported", "queries": [], "missing_conditions": []})
    runtime = build_runtime({**_enabled_environment(), "AGENT_KNOWLEDGE_ENABLED": "false"},
                            model_transport=model, knowledge_http_client_factory=forbidden)
    await runtime.aclose()
    assert model.requests == []
