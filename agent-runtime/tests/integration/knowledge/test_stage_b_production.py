from __future__ import annotations

import json

import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.main import build_runtime
from agent_runtime.model.contracts import ModelTaskId, StructuredFinishKind, StructuredModelResponse
from tests.helpers import scope
from tests.integration.knowledge.test_production_runtime_wiring import (
    _KnowledgeClientFactory, _KnowledgeModelTransport, _enabled_environment,
)


class PlanModel(_KnowledgeModelTransport):
    def __init__(self, plan):
        super().__init__()
        self.plan = plan

    async def complete(self, request, *, call_deadline):
        if request.task_id is not ModelTaskId.KNOWLEDGE_REWRITE:
            return await super().complete(request, call_deadline=call_deadline)
        self.requests.append(request)
        if isinstance(self.plan, Exception):
            raise self.plan
        return StructuredModelResponse(
            finish_kind=StructuredFinishKind.STOP, content=json.dumps(self.plan), tool_calls=(), usage_total_tokens=0,
        )


def plan(query, domain="tax.policy"):
    return {"outcome": "search", "queries": [{"domain_id": domain, "query": query}], "missing_conditions": []}


@pytest.mark.parametrize("question, output, expected, reason", [
    ("酒店住宿服务增值税政策", plan("住宿服务生活服务增值税政策"), CapabilityStatus.SUCCESS, None),
    ("小规模纳税人住宿服务征收率", plan("住宿服务征收率"), CapabilityStatus.DOWNSTREAM_FAILURE, None),
    ("住宿服务税率", plan("一般纳税人住宿服务税率"), CapabilityStatus.DOWNSTREAM_FAILURE, None),
    ("2016年住宿服务税率", plan("2026年住宿服务税率"), CapabilityStatus.DOWNSTREAM_FAILURE, None),
    ("不适用免税的住宿服务政策", plan("适用免税的住宿服务政策"), CapabilityStatus.DOWNSTREAM_FAILURE, None),
    ("住宿服务税率", plan("住宿服务税率", "tax.law"), CapabilityStatus.DOWNSTREAM_FAILURE, None),
    ("住宿服务税率", {"candidates": ["住宿服务税率"]}, CapabilityStatus.DOWNSTREAM_FAILURE, None),
    ("住宿服务税率", {"outcome": "unsupported", "queries": [], "missing_conditions": []}, CapabilityStatus.NO_RESULT, "no_matching_domain"),
    ("酒店住宿费用适用什么税率", {"outcome": "clarification_required", "queries": [], "missing_conditions": ["taxpayer_type"]}, CapabilityStatus.NO_RESULT, "clarification_required"),
    ("住宿服务税率", RuntimeError("synthetic"), CapabilityStatus.DOWNSTREAM_FAILURE, None),
    ("住宿服务税率", TimeoutError(), CapabilityStatus.TIMEOUT, None),
    ("住宿服务6％税率", plan("住宿服务6‰税率"), CapabilityStatus.DOWNSTREAM_FAILURE, None),
    ("住宿服务6‰税率", plan("住宿服务6‱税率"), CapabilityStatus.DOWNSTREAM_FAILURE, None),
    ("住宿服务6％税率", plan("住宿服务6税率"), CapabilityStatus.DOWNSTREAM_FAILURE, None),
])
@pytest.mark.asyncio
async def test_current_root_semantic_plan_failures_never_query_or_fallback(question, output, expected, reason):
    model, clients = PlanModel(output), _KnowledgeClientFactory()
    runtime = build_runtime(_enabled_environment(), model_transport=model, knowledge_http_client_factory=clients)
    try:
        outcome = await runtime.ainvoke(question=question, scope=scope(question))
    finally:
        await runtime.aclose()
    assert outcome.status is expected, outcome.failure
    if expected is not CapabilityStatus.SUCCESS:
        assert clients.paths == []
        assert len(model.requests) == 2
    if reason:
        assert outcome.user_result["reason"] == reason
    if reason == "clarification_required":
        assert "查询条件不足" in outcome.answer_text
    assert all(item.is_closed for item in clients.clients)


def test_anchor_capacity_is_validated_before_http_clients_are_created():
    env = {**_enabled_environment(), "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,tax.law", "AGENT_KNOWLEDGE_FINAL_CANDIDATES": "3"}
    clients = _KnowledgeClientFactory()
    with pytest.raises(ValueError, match="cannot_cover_domain_anchors"):
        build_runtime(env, model_transport=PlanModel(None), knowledge_http_client_factory=clients)
    assert not clients.clients


@pytest.mark.parametrize("mode, expected", [
    ("partial", "continue"),
    ("missing_domain", CapabilityStatus.DOWNSTREAM_FAILURE),
    ("below_minimum", CapabilityStatus.DOWNSTREAM_FAILURE),
    ("missing_path", CapabilityStatus.DOWNSTREAM_FAILURE),
    ("duplicate_path", CapabilityStatus.DOWNSTREAM_FAILURE),
    ("empty", CapabilityStatus.NO_RESULT),
])
def test_quality_coverage_accounts_for_every_planned_path(mode, expected):
    from agent_runtime.knowledge.capability import KnowledgeQueryCapability
    from agent_runtime.knowledge.catalog import build_tax_domain_catalog
    from agent_runtime.knowledge.contracts import (
        KNOWLEDGE_QUALITY_VERSION, DomainCandidateCount, EvidenceStageKind, EvidenceStageResult,
        FailedPath, KnowledgeRetrievalPlan, PathFailureKind, PathRef, RetrievalCoverage,
        RetrievalPath, RetrievalPlanItem, RetrievalStageKind, RetrievalStageResult,
        RewriteStageKind, RewriteStageResult,
    )
    from agent_runtime.knowledge.fakes import FakeEvidenceStage, FakeRetrievalStage, FakeRewriteStage
    from agent_runtime.knowledge.planning import KnowledgeRetrievalPlanBuilder
    from agent_runtime.knowledge.settings import KnowledgeSettings

    domains = ("tax.policy", "tax.law")
    settings = KnowledgeSettings.from_env({"AGENT_KNOWLEDGE_ENABLED": "true",
        "AGENT_KNOWLEDGE_ENABLED_DOMAINS": ",".join(domains)})
    capability = KnowledgeQueryCapability(settings=settings,
        enabled_domains=build_tax_domain_catalog().enabled(domains), selector=None, require_semantic_plan=True,
        rewriter=FakeRewriteStage(RewriteStageResult(kind=RewriteStageKind.FAILURE)),
        planner=KnowledgeRetrievalPlanBuilder(),
        retrieval=FakeRetrievalStage(RetrievalStageResult(kind=RetrievalStageKind.NO_RESULT)),
        evidence=FakeEvidenceStage(EvidenceStageResult(kind=EvidenceStageKind.NO_RESULT)))
    paths = tuple(PathRef(logical_domain_id=d, path=p) for d in domains
                  for p in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR))
    plan_value = KnowledgeRetrievalPlan(items=tuple(RetrievalPlanItem(
        logical_domain_id=p.logical_domain_id, path=p.path, query_text="增值税政策法律",
        candidate_limit=20, ordinal=i) for i, p in enumerate(paths, 1)),
        selected_domain_ids=domains, config_version="knowledge-flow-config-v1",
        quality_version=KNOWLEDGE_QUALITY_VERSION)
    success, no_result = (paths[0], paths[2], paths[3]), ()
    failed = (FailedPath(logical_domain_id="tax.policy", path=RetrievalPath.VECTOR,
                        failure_kind=PathFailureKind.DOWNSTREAM_FAILURE),)
    counts = (2, 2)
    if mode == "missing_domain":
        success, no_result, counts = (paths[0],), (paths[2], paths[3]), (4, 0)
    elif mode == "below_minimum":
        counts = (1, 1)
    elif mode == "missing_path":
        success = (paths[0], paths[2])
    elif mode == "duplicate_path":
        success += (paths[0],)
    elif mode == "empty":
        success, no_result, failed, counts = (), paths, (), (0, 0)
    coverage = RetrievalCoverage(successful_paths=success, no_result_paths=no_result,
        failed_paths=failed, complete=not failed,
        candidate_count_by_domain=tuple(DomainCandidateCount(logical_domain_id=d, count=n)
                                        for d, n in zip(domains, counts)))
    batch = object()
    result = capability.map_retrieval_result(plan=plan_value, result=RetrievalStageResult(
        kind=RetrievalStageKind.NO_RESULT if mode == "empty" else RetrievalStageKind.SUCCESS,
        batch=None if mode == "empty" else batch, coverage=coverage))
    if expected == "continue":
        assert result == (batch, coverage)
        assert not coverage.complete
    else:
        assert result.status is expected
