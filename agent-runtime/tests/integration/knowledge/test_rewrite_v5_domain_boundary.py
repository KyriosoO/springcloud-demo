"""Current-root regression of V5 domain rules, retained by V6; not historical UAT."""
from __future__ import annotations

import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.main import build_runtime
from agent_runtime.model.contracts import ModelTaskId
from agent_runtime.knowledge.rewrite_v6 import INSTRUCTION
from agent_runtime.observation import observation_scope
from tests.helpers import scope
from tests.integration.knowledge.test_production_runtime_wiring import _KnowledgeClientFactory, _enabled_environment
from tests.integration.knowledge.test_stage_b_production import PlanModel


@pytest.mark.parametrize("question,planned_domains,enabled,accepted", [
    ("增值税政策中生活服务的分类定义是什么", ("tax.policy",), ("tax.policy", "tax.law"), True),
    ("软件产品增值税政策规定的申请条件是什么", ("tax.policy",), ("tax.policy", "tax.law"), True),
    ("增值税法规定的法定纳税义务是什么", ("tax.law",), ("tax.policy", "tax.law"), True),
    ("税收征收管理法的申报条文是什么", ("tax.law",), ("tax.policy", "tax.law"), True),
    ("增值税服务政策分类与税法规则分别是什么", ("tax.policy", "tax.law"), ("tax.policy", "tax.law"), True),
    ("增值税政策与法律的依据分别是什么", ("tax.law", "tax.policy"), ("tax.policy", "tax.law"), True),
    ("增值税法规定的法定纳税义务是什么", ("tax.law",), ("tax.policy",), False),
    ("增值税政策定义是什么", ("other",), ("tax.policy", "tax.law"), False),
    ("增值税政策定义是什么", ("tax.policy", "tax.policy"), ("tax.policy", "tax.law"), False),
])
@pytest.mark.asyncio
@pytest.mark.parametrize("distinct_queries", [False, True])
async def test_current_root_uses_exact_model_domain_plan_without_local_routing(
    question, planned_domains, enabled, accepted, distinct_queries,
):
    output = {"outcome": "search", "queries": [
        {"domain_id": domain, "query": question + (
            (" 实施资料" if domain == "tax.policy" else " 法律资料") if distinct_queries else "")}
        for domain in planned_domains], "missing_conditions": []}
    model, clients = PlanModel(output), _KnowledgeClientFactory()
    runtime = build_runtime(
        {**_enabled_environment(), "AGENT_KNOWLEDGE_ENABLED_DOMAINS": ",".join(enabled)},
        model_transport=model, knowledge_http_client_factory=clients,
    )
    try:
        with observation_scope() as collector:
            outcome = await runtime.ainvoke(question=question, scope=scope(question))
            observation = collector.snapshot()
    finally:
        await runtime.aclose()
    rewrite = [request for request in model.requests if request.task_id is ModelTaskId.KNOWLEDGE_REWRITE]
    assert len(rewrite) == 1 and rewrite[0].task_version == "6"
    assert rewrite[0].system_instruction == INSTRUCTION
    assert {r.task_id for r in model.requests} <= {
        ModelTaskId.ACTION_SELECTION, ModelTaskId.KNOWLEDGE_REWRITE, ModelTaskId.KNOWLEDGE_SUMMARY}
    if accepted:
        assert outcome.status is CapabilityStatus.SUCCESS, outcome.failure
        assert len(model.requests) == 3 and len(observation.plans) == 1
        assert tuple(observation.plans[0]["plan"]["selected_domain_ids"]) == tuple(
            domain for domain in enabled if domain in planned_domains)
        assert clients.paths.count("/es/knowledge/search") == 2 * len(planned_domains)
        # Identical query texts share one request-local embedding, not a cross-request cache.
        assert clients.paths.count("/embed") == len({item["query"] for item in output["queries"]})
        assert clients.paths.count("/rerank") == len(planned_domains)
    else:
        assert outcome.status is CapabilityStatus.DOWNSTREAM_FAILURE
        assert len(model.requests) == 2 and not clients.paths and not observation.plans
    assert all(client.is_closed for client in clients.clients)
