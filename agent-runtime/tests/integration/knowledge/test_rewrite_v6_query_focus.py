"""Synthetic plans verify exact dispatch, not LLM semantic correctness or UAT."""
from __future__ import annotations

import json

import httpx
import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.main import build_runtime
from agent_runtime.model.contracts import ModelTaskId
from agent_runtime.knowledge.rewrite_v6 import INSTRUCTION
from agent_runtime.observation import observation_scope
from tests.helpers import scope
from tests.integration.knowledge.test_production_runtime_wiring import _KnowledgeClientFactory, _enabled_environment
from tests.integration.knowledge.test_stage_b_production import PlanModel


class RecordingClients(_KnowledgeClientFactory):
    def __init__(self):
        super().__init__()
        self.payloads = []

    def __call__(self, base_url):
        client = super().__call__(base_url)

        async def record(request: httpx.Request):
            self.payloads.append((request.url.path, json.loads(request.content)))

        client.event_hooks["request"].append(record)
        return client


@pytest.mark.parametrize("question,queries", [
    ("住宿服务的政策分类和增值税法的税率规定是什么？", (
        ("tax.policy", "住宿服务的政策分类"), ("tax.law", "住宿服务的增值税法税率规定"))),
    ("软件服务的政策定义及税收征收管理法的申报规定是什么？", (
        ("tax.policy", "软件服务的政策定义"), ("tax.law", "软件服务的税收征收管理法申报规定"))),
    ("增值税中的住宿服务分类是什么？", (("tax.policy", "增值税中的住宿服务分类"),)),
    ("增值税中的软件服务分类是什么？", (("tax.policy", "增值税中的软件服务分类"),)),
])
@pytest.mark.asyncio
async def test_current_root_dispatches_domain_queries_unchanged_and_summarizes_original(question, queries):
    model = PlanModel({"outcome": "search", "queries": [
        {"domain_id": domain, "query": query} for domain, query in queries], "missing_conditions": []})
    clients = RecordingClients()
    runtime = build_runtime(
        {**_enabled_environment(), "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,tax.law"},
        model_transport=model, knowledge_http_client_factory=clients,
    )
    try:
        with observation_scope() as collector:
            outcome = await runtime.ainvoke(question=question, scope=scope(question))
            observation = collector.snapshot()
    finally:
        await runtime.aclose()

    assert outcome.status is CapabilityStatus.SUCCESS, outcome.failure
    assert [r.task_id for r in model.requests] == [
        ModelTaskId.ACTION_SELECTION, ModelTaskId.KNOWLEDGE_REWRITE, ModelTaskId.KNOWLEDGE_SUMMARY]
    rewrite, summary = model.requests[1:]
    assert rewrite.task_version == "6" and rewrite.system_instruction == INSTRUCTION
    assert summary.task_version == "5"
    assert json.loads(rewrite.user_payload_json)["question"] == question
    assert json.loads(summary.user_payload_json)["question"] == question
    assert len(observation.plans) == 1
    planned = observation.plans[0]["plan"]
    assert tuple(planned["selected_domain_ids"]) == tuple(domain for domain, _ in queries)
    assert {(item["logical_domain_id"], item["query_text"]) for item in planned["items"]} == set(queries)

    searches = [value for path, value in clients.payloads if path == "/es/knowledge/search"]
    assert len(searches) == 2 * len(queries)
    for domain, query in queries:
        domain_requests = [value for value in searches if value["logicalDomainId"] == domain]
        assert {value["path"] for value in domain_requests} == {"keyword", "vector"}
        keyword = next(value for value in domain_requests if value["path"] == "keyword")
        vector = next(value for value in domain_requests if value["path"] == "vector")
        assert keyword["queryText"] == query and keyword["queryVector"] is None
        assert vector["queryText"] is None and len(vector["queryVector"]) == 1024
        assert all(value["limit"] == 20 for value in domain_requests)
    assert [value["texts"] for path, value in clients.payloads if path == "/embed"] == [[query] for _, query in queries]
    assert [value["query"] for path, value in clients.payloads if path == "/rerank"] == [query for _, query in queries]
    assert set(clients.paths) == {"/es/knowledge/search", "/embed", "/rerank"}
    assert len(clients.es_authorizations) == len(searches)
    assert all(client.is_closed for client in clients.clients)


@pytest.mark.parametrize("query", [
    "2016年住宿服务6％税率政策",  # Lost negation.
    "2017年不适用住宿服务6％税率政策",  # Changed date.
    "2016年不适用住宿服务6‰税率政策",  # Changed ratio unit.
    "2016年不适用住宿服务6％税率一般纳税人政策",  # Invented taxpayer condition.
])
@pytest.mark.asyncio
async def test_focusing_never_bypasses_existing_explicit_condition_guards(query):
    question = "2016年不适用住宿服务6％税率的政策和法律规则"
    model = PlanModel({"outcome": "search", "queries": [
        {"domain_id": "tax.policy", "query": query},
        {"domain_id": "tax.law", "query": question}], "missing_conditions": []})
    clients = RecordingClients()
    runtime = build_runtime(
        {**_enabled_environment(), "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,tax.law"},
        model_transport=model, knowledge_http_client_factory=clients,
    )
    try:
        outcome = await runtime.ainvoke(question=question, scope=scope(question))
    finally:
        await runtime.aclose()
    assert outcome.status is CapabilityStatus.DOWNSTREAM_FAILURE
    assert [r.task_id for r in model.requests] == [ModelTaskId.ACTION_SELECTION, ModelTaskId.KNOWLEDGE_REWRITE]
    assert not clients.paths and not clients.payloads
    assert all(client.is_closed for client in clients.clients)
