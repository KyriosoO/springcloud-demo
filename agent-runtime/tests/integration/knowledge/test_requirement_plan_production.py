"""Requirement components and current version pairing; not live effectiveness."""
from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
import json
from types import SimpleNamespace

import pytest

from agent_runtime.bootstrap import KnowledgeCompositionRoot
from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.knowledge.capability import KnowledgeQueryCapability
from agent_runtime.knowledge.catalog import build_tax_domain_catalog
from agent_runtime.knowledge.context import to_retrieval_context
from agent_runtime.knowledge.contracts import (
    KNOWLEDGE_QUALITY_VERSION_V2, KNOWLEDGE_QUALITY_VERSION_V3, KNOWLEDGE_QUALITY_VERSIONS,
    DomainSelection, KnowledgeQueryArguments, KnowledgeQuestionKind, RetrievalStageKind,
    RewriteStageKind, RewriteStageResult,
)
from agent_runtime.knowledge.evidence.builder import EvidenceIntegrityError, EvidenceIntegrityVerifier
from agent_runtime.knowledge.errors import KnowledgeInputError
from agent_runtime.knowledge.planning import KnowledgeRetrievalPlanBuilder
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanOutput
from agent_runtime.knowledge.rewrite_v6 import KnowledgeRewriteTaskV6
from agent_runtime.knowledge.rewrite_v7 import KnowledgeRequirementPlanOutput, KnowledgeRewriteTaskV7
from agent_runtime.knowledge.semantic_planner import KnowledgeSemanticPlanner
from agent_runtime.knowledge.settings import KnowledgeSettings
from agent_runtime.knowledge.tax_question_semantics import TaxQuestionSemanticGuard
from agent_runtime.model.contracts import ModelCallContext, ModelTaskId
from agent_runtime.model.gateway import BoundedStructuredModelGateway
from agent_runtime.observation import knowledge_http_request_view, model_call_started, observation_scope
from tests.contract.knowledge.test_rewrite_task_v2 import _response
from tests.contract.knowledge.test_rewrite_task_v7 import wire_plan
from tests.evidence_helpers import evidence_input
from tests.helpers import scope
from tests.unit.knowledge.retrieval.test_stage import FakeEmbedding, FakeRerank, FakeSearch


class PlanTransport:
    def __init__(self, value):
        self.value, self.calls = value, []

    async def complete(self, request, **kwargs):
        self.calls.append(request)
        if isinstance(self.value, BaseException):
            raise self.value
        return _response(json.dumps(self.value))


def planner(*, gateway, definition=None, quality=KNOWLEDGE_QUALITY_VERSION_V3, domains=("tax.policy", "tax.law")):
    return KnowledgeSemanticPlanner(
        gateway=gateway, context=SimpleNamespace(require_current=lambda: ModelCallContext(
            request_id="r1", correlation_id="c1", deadline_monotonic=asyncio.get_running_loop().time() + 10,
        )), enabled_domain_ids=domains, definition=definition or KnowledgeRewriteTaskV7.definition(),
        quality_version=quality, semantic_guard=TaxQuestionSemanticGuard(),
    )


async def invoke(value, question=None, domains=("tax.policy", "tax.law")):
    definition = KnowledgeRewriteTaskV7.definition()
    transport = PlanTransport(value)
    gateway = BoundedStructuredModelGateway(transport=transport, definitions=(definition,), max_concurrency=1)
    result = await planner(gateway=gateway, definition=definition, domains=domains).rewrite(
        original_question=question or wire_plan()["queries"][0]["query"], timeout_s=8,
    )
    return result, transport


def build_plan(rewrite):
    return KnowledgeRetrievalPlanBuilder().build(
        rewrite=rewrite,
        domains=DomainSelection(selected_domain_ids=tuple(item.domain_id for item in rewrite.domain_queries), catalog_version="test", reason_codes=()),
        settings=KnowledgeSettings.from_env({"AGENT_KNOWLEDGE_ENABLED": "true", "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,tax.law"}),
    )


@pytest.mark.asyncio
async def test_typed_requirement_tuple_survives_gateway_planner_and_plan_without_observation_leak(caplog):
    value = wire_plan(applicability=True, second_domain=True)
    # Provider ordering cannot change stable catalog/path order or requirement IDs.
    value["queries"].reverse()
    with observation_scope() as collector:
        result, transport = await invoke(value)
        assert result.kind is RewriteStageKind.SUCCESS
        rewritten = result.rewrite
        plan = build_plan(rewritten)
        assert plan.evidence_requirements is rewritten.evidence_requirements
        assert plan.question_kind is KnowledgeQuestionKind.APPLICABILITY
        assert [(item.logical_domain_id, item.path.value) for item in plan.items] == [
            ("tax.policy", "keyword"), ("tax.policy", "vector"), ("tax.law", "keyword"), ("tax.law", "vector"),
        ]
        for requirement in plan.evidence_requirements:
            view = knowledge_http_request_view("/rerank", json.dumps({"query": requirement.focus, "documents": ["synthetic body"], "top_n": 1}).encode())
            assert view["query"] == "<hidden>"
            assert requirement.focus not in repr(view)
        # Exercise the current whitelist with the new input shape, without Summary I/O.
        model_call_started(replace(transport.calls[0], task_id=ModelTaskId.KNOWLEDGE_SUMMARY, task_version="6",
                                  user_payload_json=json.dumps({"question": "税务政策", "requirements": [asdict(item) for item in plan.evidence_requirements], "evidence": []})))
        snapshot = collector.snapshot()
    assert len(transport.calls) == 1 and transport.calls[0].max_output_tokens == 1536
    assert set(snapshot.plans[0]["plan"]) == {"items", "selected_domain_ids", "config_version", "quality_version"}
    for requirement in plan.evidence_requirements:
        assert requirement.focus not in repr(snapshot) + caplog.text
    assert "requirements" not in snapshot.model_calls[-1]["request"]["input"]


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,expected", [
    ("missing_role", RewriteStageKind.FAILURE), ("extra_domain", RewriteStageKind.FAILURE),
    ("sensitive_focus", RewriteStageKind.FAILURE), ("introduced_focus", RewriteStageKind.FAILURE),
    ("unsafe_focus", RewriteStageKind.FAILURE), ("lost_query_date", RewriteStageKind.FAILURE),
    ("old_shape", RewriteStageKind.FAILURE), ("model_failure", RewriteStageKind.FAILURE),
    ("timeout", RewriteStageKind.TIMEOUT), ("unsupported", RewriteStageKind.SUCCESS),
    ("clarification", RewriteStageKind.CLARIFICATION_REQUIRED),
])
async def test_rejected_plans_produce_no_executable_subset(fault, expected):
    value = wire_plan(applicability=True)
    if fault == "missing_role":
        value["requirements"].pop()
    elif fault == "extra_domain":
        value["queries"][0]["domain_id"] = value["requirements"][0]["domain_id"] = "employee"
    elif fault == "sensitive_focus":
        value["requirements"][0]["focus"] = "税务政策联系13800138000"
    elif fault == "introduced_focus":
        value["requirements"][0]["focus"] = "2027年税务规定"
    elif fault == "unsafe_focus":
        value["requirements"][0]["focus"] = "普通运输依据"
    elif fault == "lost_query_date":
        value["queries"][0]["query"] = value["queries"][0]["query"].replace("2026", "")
    elif fault == "old_shape":
        del value["requirements"]
    elif fault in {"model_failure", "timeout"}:
        value = RuntimeError("synthetic") if fault == "model_failure" else TimeoutError()
    elif fault in {"unsupported", "clarification"}:
        value = {"outcome": "unsupported" if fault == "unsupported" else "clarification_required", "question_kind": "none",
                 "queries": [], "requirements": [], "missing_conditions": [] if fault == "unsupported" else ["subject"]}
    with observation_scope() as collector:
        result, transport = await invoke(value)
        observed = collector.snapshot()
    assert result.kind is expected
    assert len(transport.calls) == 1 and observed.downstream_calls == () and observed.plans == ()
    if fault == "unsupported":
        assert result.rewrite.domain_queries == () and result.rewrite.question_kind is None and result.rewrite.evidence_requirements == ()
    else:
        assert result.rewrite is None


@pytest.mark.asyncio
async def test_sensitive_original_denied_before_any_model_call():
    result, transport = await invoke(wire_plan(), question="员工13800138000的税务记录")
    assert result.kind is RewriteStageKind.QUESTION_DENIED and transport.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["old_output", "kind", "requirements", "missing", "outcome", "list"])
@pytest.mark.parametrize("terminal", ["unsupported", "clarification_required"])
async def test_provider_bypassing_decoder_cannot_hide_invalid_terminal(fault, terminal):
    output = KnowledgeRequirementPlanOutput(outcome=terminal, queries=(), missing_conditions=() if terminal == "unsupported" else ("subject",),
                                           question_kind=None, evidence_requirements=())
    if fault == "old_output":
        output = KnowledgeSemanticPlanOutput(outcome=terminal, queries=(), missing_conditions=output.missing_conditions)
    elif fault == "kind":
        output = replace(output, question_kind=KnowledgeQuestionKind.LOOKUP)
    elif fault == "requirements":
        parsed = KnowledgeRewriteTaskV7.definition().parse_response(_response(json.dumps(wire_plan())))
        output = replace(output, evidence_requirements=parsed.evidence_requirements)
    elif fault == "missing":
        output = replace(output, missing_conditions=("unknown",))
    elif fault == "outcome":
        output = replace(output, outcome="invented")
    elif fault == "list":
        output = replace(output, queries=[])

    class Gateway:
        async def generate(self, **kwargs):
            return SimpleNamespace(output=output)

    result = await planner(gateway=Gateway()).rewrite(original_question="运输服务税务分类", timeout_s=8)
    assert result.kind is RewriteStageKind.FAILURE and result.rewrite is None


@pytest.mark.parametrize("definition,version", [(KnowledgeRewriteTaskV7.definition(), KNOWLEDGE_QUALITY_VERSION_V2),
    (KnowledgeRewriteTaskV6.definition(), KNOWLEDGE_QUALITY_VERSION_V3),
    (replace(KnowledgeRewriteTaskV7.definition(), task_id=ModelTaskId.KNOWLEDGE_SUMMARY), KNOWLEDGE_QUALITY_VERSION_V3),
    (replace(KnowledgeRewriteTaskV7.definition(), input_type=object), KNOWLEDGE_QUALITY_VERSION_V3)])
def test_version_pair_cannot_be_mixed(definition, version):
    with pytest.raises(ValueError, match="version_mismatch"):
        planner(gateway=object(), definition=definition, quality=version)


@pytest.mark.asyncio
async def test_disabled_domain_cannot_be_selected_by_v7():
    result, transport = await invoke(wire_plan(applicability=True, second_domain=True), domains=("tax.policy",))
    assert result.kind is RewriteStageKind.FAILURE and len(transport.calls) == 1


@pytest.mark.asyncio
async def test_cancellation_propagates_without_retry():
    result = None
    transport = PlanTransport(asyncio.CancelledError())
    definition = KnowledgeRewriteTaskV7.definition()
    gateway = BoundedStructuredModelGateway(transport=transport, definitions=(definition,), max_concurrency=1)
    with pytest.raises(asyncio.CancelledError):
        result = await planner(gateway=gateway, definition=definition).rewrite(original_question="运输服务税务分类", timeout_s=8)
    assert result is None and len(transport.calls) == 1


@pytest.mark.asyncio
async def test_old_version_with_requirements_rejected_before_retrieval_io_and_v3_evidence_requires_labels():
    result, _ = await invoke(wire_plan(applicability=True))
    plan = build_plan(result.rewrite)
    for version in (KNOWLEDGE_QUALITY_VERSION_V2, None):
        embedding, search, rerank = FakeEmbedding(), FakeSearch(), FakeRerank()
        stage = DefaultKnowledgeRetrievalStage(embedding=embedding, search=search, rerank=rerank)
        rejected = await stage.execute(plan=replace(plan, quality_version=version), context=to_retrieval_context(scope().context), timeout_s=5)
        assert rejected.kind is RetrievalStageKind.DOWNSTREAM_FAILURE
        assert embedding.calls == rerank.calls == 0 and search.calls == []
        with pytest.raises(EvidenceIntegrityError):
            EvidenceIntegrityVerifier().verify(input=replace(evidence_input(), quality_version=version,
                                                            question_kind=plan.question_kind, evidence_requirements=plan.evidence_requirements))
    from tests.requirement_evidence_helpers import select
    missing_labels = replace(evidence_input(), quality_version=KNOWLEDGE_QUALITY_VERSION_V3,
                             question_kind=plan.question_kind, evidence_requirements=plan.evidence_requirements)
    assert not select(missing_labels).sufficient
    with pytest.raises(KnowledgeInputError, match="version_mismatch"):
        build_plan(replace(result.rewrite, plan_version=KNOWLEDGE_QUALITY_VERSION_V2))


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["missing", "empty_with_kind", "empty_with_requirements", "empty_with_list", "empty_wrong_question"])
async def test_current_capability_rejects_invalid_v3_requirements_before_downstream(fault):
    result, _ = await invoke(wire_plan())
    rewritten = replace(result.rewrite, evidence_requirements=())
    if fault == "empty_with_kind":
        rewritten = replace(rewritten, domain_queries=())
    elif fault == "empty_with_requirements":
        rewritten = replace(result.rewrite, domain_queries=(), question_kind=None)
    elif fault == "empty_with_list":
        rewritten = replace(rewritten, domain_queries=(), question_kind=None, evidence_requirements=[])
    elif fault == "empty_wrong_question":
        rewritten = replace(rewritten, domain_queries=(), question_kind=None, original_question="不同税务问题")

    class Rewrite:
        async def rewrite(self, **kwargs):
            return RewriteStageResult(kind=RewriteStageKind.SUCCESS, rewrite=rewritten)

    class NoCalls:
        calls = 0

        async def execute(self, **kwargs):
            self.calls += 1
            raise AssertionError

        async def build_result(self, **kwargs):
            self.calls += 1
            raise AssertionError

    settings = KnowledgeSettings.from_env({"AGENT_KNOWLEDGE_ENABLED": "true", "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy"})
    no_calls = NoCalls()
    capability = KnowledgeQueryCapability(settings=settings, enabled_domains=build_tax_domain_catalog().enabled(settings.enabled_domain_ids),
        rewriter=Rewrite(), selector=None, planner=KnowledgeRetrievalPlanBuilder(), retrieval=no_calls, evidence=no_calls,
        require_semantic_plan=True)
    outcome = await capability.handle(KnowledgeQueryArguments(), scope(result.rewrite.original_question).context)
    assert outcome.status is CapabilityStatus.DOWNSTREAM_FAILURE and no_calls.calls == 0


def test_current_root_pairs_requirement_consumers_and_runtime_version():
    tasks = KnowledgeCompositionRoot.task_definitions(enabled=True)
    assert tasks.rewrite.task_version == "10" and tasks.summary.task_version == "7"
    assert KNOWLEDGE_QUALITY_VERSION_V3 in KNOWLEDGE_QUALITY_VERSIONS
    assert KnowledgeCompositionRoot.task_definitions(enabled=False) is None


@pytest.mark.asyncio
async def test_v7_gateway_plan_reaches_requirement_ranker_without_changing_search_queries():
    from tests.unit.knowledge.retrieval.test_quality_ranking_v3 import FocusRerank, Search

    rewritten, transport = await invoke(wire_plan(applicability=True, second_domain=True))
    plan = build_plan(rewritten.rewrite)
    search, rerank, embedding = Search(count=2), FocusRerank(), FakeEmbedding()
    outcome = await DefaultKnowledgeRetrievalStage(search=search, embedding=embedding, rerank=rerank).execute(
        plan=plan, context=to_retrieval_context(scope().context), timeout_s=4)
    assert outcome.kind is RetrievalStageKind.SUCCESS
    assert len(transport.calls) == 1 and len(search.calls) == 4 and embedding.calls == 1
    assert [call[0] for call in rerank.calls] == [requirement.focus for requirement in plan.evidence_requirements]
    assert all(request.query_text == plan.items[0].query_text for request in search.calls if request.query_text is not None)
    assert sorted(label for item in outcome.batch.candidates for label in item.requirement_ids) == ["r1", "r2", "r3"]
