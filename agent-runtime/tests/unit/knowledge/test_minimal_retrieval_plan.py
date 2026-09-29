from dataclasses import asdict, replace

import pytest

from agent_runtime.knowledge.contracts import RetrievalPath
from agent_runtime.knowledge.intent_contracts import (
    KnowledgeIntentOutcome, KnowledgeQueryIntent, KnowledgeQueryIntentInput, KnowledgeQueryMode,
)
from agent_runtime.knowledge.minimal_plan import MinimalKnowledgePlanBuilder, MinimalRetrievalSettings
from agent_runtime.model.contracts import ModelInputDenied


def make_plan(domains=("tax.policy", "tax.law"), *, settings=None, question="税务政策与法律依据"):
    return MinimalKnowledgePlanBuilder().build(question=KnowledgeQueryIntentInput(minimized_question=question),
        intent=KnowledgeQueryIntent(query_mode=KnowledgeQueryMode.LOOKUP, selected_domain_ids=domains,
            missing_conditions=(), outcome=KnowledgeIntentOutcome.SEARCH),
        settings=settings or MinimalRetrievalSettings())


@pytest.mark.parametrize("domains", [("tax.policy",), ("tax.law",), ("tax.policy", "tax.law")])
@pytest.mark.parametrize("question", ["酒店行业的住宿费用适用哪种税率", "2019年税率是否不适用", "法规" * 512])
def test_plan_freezes_original_question_catalog_profiles_and_budgets(domains, question):
    plan = make_plan(domains, question=question)
    assert plan.schema_version == 3 and plan.settings.config_version == "knowledge-minimal-v1"
    assert len(plan.items) == len(domains) * 2 <= 4
    assert [(item.logical_domain_id, item.path) for item in plan.items] == [
        (domain, path) for domain in domains for path in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR)]
    assert all(item.query_text == question and item.candidate_limit == 20 for item in plan.items)
    assert [item.ordinal for item in plan.items] == list(range(1, len(plan.items) + 1))
    assert plan.profile_bindings == tuple((d, d.replace(".", "-") + "-v1") for d in domains)
    assert not {"requirements", "focus", "evidence_requirements", "quality_version"} & asdict(plan).keys()
    assert question not in repr(plan)


@pytest.mark.parametrize("raw", [
    {"enabled_domain_ids": []}, {"enabled_domain_ids": ["employee"]},
    {"enabled_domain_ids": ["tax.law", "tax.policy"]}, {"enabled_domain_ids": ["tax.policy"] * 2},
    {"enabled_domain_ids": "tax.policy"}, {"enabled_domain_ids": [1]},
    {"min_partial_candidates": 2}, {"min_partial_candidates": 21}, {"min_partial_candidates": True},
    {"per_path_candidate_limit": 4}, {"per_path_candidate_limit": 21},
    {"per_path_candidate_limit": True}, {"final_candidate_limit": 2},
    {"final_candidate_limit": 21}, {"final_candidate_limit": True},
    {"per_path_candidate_limit": 5, "min_partial_candidates": 6},
    {"min_partial_candidates": "3"}, {"retrieval_timeout_s": 21}, {"retrieval_timeout_s": 0},
    {"retrieval_timeout_s": float("nan")}, {"retrieval_timeout_s": True},
    {"retrieval_timeout_s": "5"}, {"config_version": "knowledge-retrieval-quality-v3"},
    {"per_path_candidate_limit": 50}, {"retry": 1}, {"profile": "new-index"},
])
def test_config_cannot_expand_code_limits_or_inject_strategy(raw):
    with pytest.raises(ValueError):
        MinimalRetrievalSettings.from_mapping(raw)


def test_config_snapshot_copies_input_and_disabled_domain_is_not_allowed():
    raw = {"enabled_domain_ids": ["tax.policy"], "min_partial_candidates": 5, "retrieval_timeout_s": 2}
    settings = MinimalRetrievalSettings.from_mapping(raw)
    raw["enabled_domain_ids"].append("tax.law")
    assert settings.enabled_domain_ids == ("tax.policy",)
    with pytest.raises(ValueError):
        make_plan(settings=settings)
    with pytest.raises(ValueError):
        make_plan(("tax.policy",)).validate(settings)


def test_narrowed_per_path_budget_is_frozen_into_both_paths():
    settings = MinimalRetrievalSettings.from_mapping({"per_path_candidate_limit": 5,
        "final_candidate_limit": 3, "min_partial_candidates": 3})
    plan = make_plan(("tax.policy",), settings=settings)
    assert tuple(item.candidate_limit for item in plan.items) == (5, 5)
    assert plan.settings.final_candidate_limit == 3
    with pytest.raises(ValueError):
        replace(plan, items=(replace(plan.items[0], candidate_limit=20), plan.items[1]))


@pytest.mark.parametrize("change", [
    {"schema_version": 1}, {"schema_version": True}, {"catalog_version": "invented"},
    {"query_mode": KnowledgeQueryMode.NONE}, {"query_mode": "lookup"},
    {"selected_domain_ids": ("employee",)}, {"selected_domain_ids": ()},
    {"profile_bindings": (("tax.policy", "physical-index"),)},
])
def test_plan_rejects_version_domain_mode_and_binding_drift(change):
    with pytest.raises(ValueError):
        replace(make_plan(), **change)


@pytest.mark.parametrize("field,value", [("query_text", "被改写的问题"), ("candidate_limit", 21),
    ("ordinal", True), ("path", "keyword")])
def test_plan_rejects_modified_or_duplicate_paths(field, value):
    plan = make_plan()
    with pytest.raises(ValueError):
        replace(plan, items=(replace(plan.items[0], **{field: value}),) + plan.items[1:])
    with pytest.raises(ValueError):
        replace(plan, items=(plan.items[0],) * 4)


def test_terminal_intent_never_builds_plan():
    intent = KnowledgeQueryIntent(query_mode=KnowledgeQueryMode.NONE, selected_domain_ids=(),
        missing_conditions=(), outcome=KnowledgeIntentOutcome.UNSUPPORTED)
    with pytest.raises(ValueError):
        MinimalKnowledgePlanBuilder().build(question=KnowledgeQueryIntentInput(minimized_question="税法"),
            intent=intent, settings=MinimalRetrievalSettings())


def test_existing_guard_boundary_is_not_relaxed_for_retrieval():
    with pytest.raises(ModelInputDenied):
        make_plan(question="酒店行业的住宿费用适用规则")
