from dataclasses import replace

import pytest

from agent_runtime.knowledge.contracts import (
    KNOWLEDGE_QUALITY_VERSION_V3, DomainSelection, KnowledgeEvidenceRequirement,
    KnowledgeQuestionKind, KnowledgeRequirementKind, PlannedDomainQuery,
    RewriteMode, RewriteResult,
)
from agent_runtime.knowledge.errors import KnowledgeInputError
from agent_runtime.knowledge.planning import KnowledgeRetrievalPlanBuilder
from agent_runtime.knowledge.settings import KnowledgeSettings
from agent_runtime.observation import observation_scope


def rewrite(question="税务政策与税收法律分别有哪些规定"):
    return RewriteResult(
        original_question=question, selected_query="税务政策规定", candidates=(),
        mode=RewriteMode.MODEL, question_policy_version="question-egress-v1",
        question_egress_denied=False, plan_version=KNOWLEDGE_QUALITY_VERSION_V3,
        question_kind=KnowledgeQuestionKind.LOOKUP,
        domain_queries=(PlannedDomainQuery(domain_id="tax.policy", query="税务政策规定"),
                        PlannedDomainQuery(domain_id="tax.law", query="税收法律规定")),
        evidence_requirements=tuple(KnowledgeEvidenceRequirement(
            requirement_id=f"r{i}", domain_id=d, kind=KnowledgeRequirementKind.RULE, focus=q,
        ) for i, (d, q) in enumerate((("tax.policy", "税务政策规定"), ("tax.law", "税收法律规定")), 1)),
    )


def build(value=None, *, preserve=True, maximum=1024):
    value = rewrite() if value is None else value
    return KnowledgeRetrievalPlanBuilder(preserve_original_keyword=preserve).build(
        rewrite=value,
        domains=DomainSelection(selected_domain_ids=("tax.policy", "tax.law"), catalog_version="test", reason_codes=()),
        settings=KnowledgeSettings.from_env({"AGENT_KNOWLEDGE_ENABLED": "true",
            "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,tax.law",
            "AGENT_KNOWLEDGE_MAX_RETRIEVAL_QUERY_CHARS": str(maximum)}),
    )


def test_original_keyword_and_distinct_domain_vectors_preserve_plan_and_projection():
    value = rewrite()
    with observation_scope() as collector:
        plan = build(value)
    assert plan.original_keyword_query == value.original_question
    assert [x.query_text for x in plan.items] == [value.original_question, "税务政策规定",
                                                value.original_question, "税收法律规定"]
    assert plan.evidence_requirements is value.evidence_requirements
    assert [x.ordinal for x in plan.items] == [1, 2, 3, 4]
    assert all(x.candidate_limit == 20 for x in plan.items)
    assert "original_keyword_query" not in collector.snapshot().plans[0]["plan"]
    assert "evidence_requirements" not in collector.snapshot().plans[0]["plan"]


def test_original_normalization_is_only_existing_nfc_and_whitespace():
    value = rewrite("\t税务  政策\n问题e\u0301  ")
    plan = build(value)
    assert plan.original_keyword_query == "税务 政策 问题é"
    assert plan.items[1].query_text == value.domain_queries[0].query


@pytest.mark.parametrize("maximum", [128, 1024])
@pytest.mark.parametrize("extra", [0, 1])
def test_original_length_boundary_is_preselected_without_truncation(maximum, extra):
    value = rewrite("税务政策" + "政" * (maximum + extra - 4))
    plan = build(value, maximum=maximum)
    assert plan.original_keyword_query == (value.original_question if extra == 0 else None)
    for i, query in enumerate(value.domain_queries):
        assert plan.items[2*i+1].query_text == query.query
        assert plan.items[2*i].query_text == (value.original_question if extra == 0 else query.query)


@pytest.mark.parametrize("question", ["", "税务" + "政" * 4095, "税务政策\x00", "税务联系人13800138000"],
                         ids=["empty", "oversized", "control", "sensitive"])
def test_unsafe_or_invalid_original_never_emits_a_plan(question):
    with observation_scope() as collector, pytest.raises(KnowledgeInputError):
        build(rewrite(question))
    assert collector.snapshot().plans == ()


@pytest.mark.parametrize("changes", [
    {"question_egress_denied": True}, {"mode": RewriteMode.ORIGINAL_FALLBACK},
    {"plan_version": None, "question_kind": None, "evidence_requirements": ()},
    {"domain_queries": ()},
])
def test_new_strategy_cannot_be_attached_to_denied_or_non_model_plans(changes):
    with pytest.raises(KnowledgeInputError):
        build(replace(rewrite(), **changes))


def test_explicit_legacy_mode_and_default_builder_keep_two_identical_queries():
    plan = build(preserve=False)
    default = KnowledgeRetrievalPlanBuilder().build(
        rewrite=rewrite(), domains=DomainSelection(selected_domain_ids=("tax.policy", "tax.law"),
            catalog_version="test", reason_codes=()),
        settings=KnowledgeSettings.from_env({"AGENT_KNOWLEDGE_ENABLED": "true",
            "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,tax.law"}),
    )
    assert plan == default and plan.original_keyword_query is None
    assert plan.items[0].query_text == plan.items[1].query_text
    assert plan.items[2].query_text == plan.items[3].query_text


@pytest.mark.parametrize("value", ["true", 1, None])
def test_strategy_switch_is_code_bound_strict_bool(value):
    with pytest.raises(ValueError):
        KnowledgeRetrievalPlanBuilder(preserve_original_keyword=value)
