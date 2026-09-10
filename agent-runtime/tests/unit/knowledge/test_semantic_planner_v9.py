from __future__ import annotations

import asyncio
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from agent_runtime.knowledge.contracts import KNOWLEDGE_QUALITY_VERSION_V3, RewriteStageKind
from agent_runtime.knowledge.document_reference_semantics import DocumentReferenceSemanticGuard
from agent_runtime.knowledge.rewrite_v8 import KnowledgeRewriteTaskV8
from agent_runtime.knowledge.rewrite_v9 import KnowledgeRewriteTaskV9
from agent_runtime.knowledge.semantic_planner import KnowledgeSemanticPlanner
from agent_runtime.model.contracts import ModelProviderFailureKind
from tests.contract.knowledge.test_rewrite_task_v2 import _response
from tests.unit.knowledge.test_query_constraint_scope import LAW, LAW_QUERY, POLICY, POLICY_QUERY, QUESTION


def wire():
    return {
        "outcome": "search", "question_kind": "lookup", "missing_conditions": [],
        "queries": [{"domain_id": POLICY, "query": POLICY_QUERY}, {"domain_id": LAW, "query": LAW_QUERY}],
        "requirements": [
            {"requirement_id": "r1", "domain_id": POLICY, "kind": "rule", "focus": POLICY_QUERY},
            {"requirement_id": "r2", "domain_id": LAW, "kind": "rule", "focus": LAW_QUERY},
        ],
    }


class Gateway:
    def __init__(self, value=None, *, error=None, failure=None, forged=None):
        self.value = wire() if value is None else value
        self.error, self.failure, self.forged = error, failure, forged
        self.calls = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        output = self.forged or kwargs["definition"].parse_response(_response(json.dumps(self.value)))
        return SimpleNamespace(output=output if self.failure is None else None, failure_kind=self.failure)


def planner(gateway, *, version="9"):
    definition = KnowledgeRewriteTaskV9.definition() if version == "9" else KnowledgeRewriteTaskV8.definition()
    return KnowledgeSemanticPlanner(
        gateway=gateway, context=SimpleNamespace(require_current=lambda: object()),
        enabled_domain_ids=(POLICY, LAW), definition=definition, quality_version=KNOWLEDGE_QUALITY_VERSION_V3,
        semantic_guard=DocumentReferenceSemanticGuard(),
    )


@pytest.mark.asyncio
async def test_scoped_plan_accepted_only_by_new_version_and_original_is_unchanged():
    for version in ("8", "9"):
        gateway = Gateway()
        result = await planner(gateway, version=version).rewrite(original_question=QUESTION, timeout_s=1)
        assert len(gateway.calls) == 1
        assert gateway.calls[0]["input"].minimized_question == QUESTION
        if version == "8":
            assert result.kind is RewriteStageKind.FAILURE and result.rewrite is None
        else:
            assert result.kind is RewriteStageKind.SUCCESS
            assert result.rewrite.original_question == QUESTION
            assert result.rewrite.selected_query == POLICY_QUERY
            assert tuple((item.domain_id, item.query) for item in result.rewrite.domain_queries) == (
                (POLICY, POLICY_QUERY), (LAW, LAW_QUERY),
            )
            assert tuple(item.focus for item in result.rewrite.evidence_requirements) == (POLICY_QUERY, LAW_QUERY)


@pytest.mark.asyncio
async def test_old_full_constraint_contract_is_preserved_for_v8():
    value = wire()
    for item in value["queries"]:
        item["query"] = QUESTION
    before = await planner(Gateway(value), version="8").rewrite(original_question=QUESTION, timeout_s=1)
    after = await planner(Gateway(value)).rewrite(original_question=QUESTION, timeout_s=1)
    assert before.kind is RewriteStageKind.SUCCESS
    assert after.kind is RewriteStageKind.FAILURE and after.reason_code == "query_scope_mismatch"


@pytest.mark.asyncio
async def test_query_order_follows_catalog_without_changing_requirement_ownership():
    value = wire()
    value["queries"].reverse()
    result = await planner(Gateway(value)).rewrite(original_question=QUESTION, timeout_s=1)
    assert result.kind is RewriteStageKind.SUCCESS
    assert tuple(item.query for item in result.rewrite.domain_queries) == (POLICY_QUERY, LAW_QUERY)


@pytest.mark.parametrize("field, replacement", [
    ("query", POLICY_QUERY.replace("2011", "2012")),
    ("query", LAW_QUERY),
    ("query", POLICY_QUERY + " 100"),
    ("focus", POLICY_QUERY.replace("100", "101")),
    ("focus", "身份证号码110101199001011234政策"),
])
@pytest.mark.asyncio
async def test_invalid_scope_fails_with_finite_reason_and_no_rewrite(field, replacement):
    value = wire()
    value["queries" if field == "query" else "requirements"][0][field] = replacement
    gateway = Gateway(value)
    result = await planner(gateway).rewrite(original_question=QUESTION, timeout_s=1)
    assert result.kind is RewriteStageKind.FAILURE and result.rewrite is None
    assert result.reason_code == "query_scope_mismatch"
    assert len(gateway.calls) == 1


@pytest.mark.asyncio
async def test_all_focus_validation_precedes_query_topic_check(monkeypatch):
    from agent_runtime.knowledge import query_constraint_scope
    observed = []
    original = query_constraint_scope.validate_requirement_focuses

    def observe(**kwargs):
        observed.append(kwargs["requirements"])
        return original(**kwargs)

    monkeypatch.setattr(query_constraint_scope, "validate_requirement_focuses", observe)
    value = wire()
    value["queries"][1]["query"] = LAW_QUERY.replace("税率", "")
    result = await planner(Gateway(value)).rewrite(original_question=QUESTION, timeout_s=1)
    assert len(observed) == 1 and len(observed[0]) == 2
    assert result.kind is RewriteStageKind.FAILURE and result.reason_code == "query_scope_mismatch"


@pytest.mark.parametrize("outcome, missing, expected", [
    ("clarification_required", ["taxpayer_type"], RewriteStageKind.CLARIFICATION_REQUIRED),
    ("unsupported", [], RewriteStageKind.SUCCESS),
])
@pytest.mark.asyncio
async def test_nonsearch_outcomes_keep_the_existing_empty_plan_contract(outcome, missing, expected):
    value = dict(outcome=outcome, question_kind="none", queries=[], requirements=[], missing_conditions=missing)
    result = await planner(Gateway(value)).rewrite(original_question=QUESTION, timeout_s=1)
    assert result.kind is expected
    if result.rewrite is not None:
        assert result.rewrite.domain_queries == () and result.rewrite.evidence_requirements == ()


@pytest.mark.parametrize("forgery", ["missing_requirements", "disabled_domain", "clarification_with_queries"])
@pytest.mark.asyncio
async def test_internal_provider_output_cannot_bypass_shape_validation(forgery):
    output = KnowledgeRewriteTaskV9.definition().parse_response(_response(json.dumps(wire())))
    if forgery == "missing_requirements":
        output = replace(output, evidence_requirements=())
    elif forgery == "disabled_domain":
        output = replace(output, queries=(replace(output.queries[0], domain_id="disabled"), output.queries[1]))
    else:
        output = replace(output, outcome="clarification_required", missing_conditions=("taxpayer_type",))
    gateway = Gateway(forged=output)
    result = await planner(gateway).rewrite(original_question=QUESTION, timeout_s=1)
    assert result.kind is RewriteStageKind.FAILURE and result.rewrite is None
    assert len(gateway.calls) == 1


@pytest.mark.parametrize("error, failure, expected", [
    (RuntimeError("synthetic"), None, RewriteStageKind.FAILURE),
    (TimeoutError(), None, RewriteStageKind.TIMEOUT),
    (None, ModelProviderFailureKind.PROVIDER_TIMEOUT, RewriteStageKind.TIMEOUT),
])
@pytest.mark.asyncio
async def test_model_failures_do_not_return_an_executable_plan(error, failure, expected):
    gateway = Gateway(error=error, failure=failure)
    result = await planner(gateway).rewrite(original_question=QUESTION, timeout_s=1)
    assert result.kind is expected and result.rewrite is None
    assert len(gateway.calls) == 1


@pytest.mark.asyncio
async def test_sensitive_original_is_denied_before_model_call():
    gateway = Gateway()
    result = await planner(gateway).rewrite(original_question="身份证号码110101199001011234的税务政策", timeout_s=1)
    assert result.kind is RewriteStageKind.QUESTION_DENIED and result.rewrite is None
    assert gateway.calls == []


@pytest.mark.asyncio
async def test_cancellation_propagates_without_second_call():
    gateway = Gateway(error=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await planner(gateway).rewrite(original_question=QUESTION, timeout_s=1)
    assert len(gateway.calls) == 1
