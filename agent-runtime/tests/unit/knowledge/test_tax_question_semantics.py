from dataclasses import asdict
from types import SimpleNamespace

import pytest

from agent_runtime.knowledge.contracts import PlannedDomainQuery, RewriteStageKind
from agent_runtime.knowledge.errors import KnowledgeInputError
from agent_runtime.knowledge.question_semantics import QuestionSemanticGuard
from agent_runtime.knowledge.rewrite_v6 import KnowledgeRewriteTaskV6
from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanOutput
from agent_runtime.knowledge.semantic_planner import KnowledgeSemanticPlanner
from agent_runtime.knowledge.tax_question_semantics import TAX_CATEGORY_CONDITIONS, TaxQuestionSemanticGuard


def accepts(original, candidate):
    guard = TaxQuestionSemanticGuard()
    return guard.validate_candidate(candidate=candidate, constraints=guard.extract(original), max_chars=1024).accepted


@pytest.mark.parametrize("category", TAX_CATEGORY_CONDITIONS)
def test_only_complete_code_bound_categories_are_non_numeric(category):
    assert TaxQuestionSemanticGuard().extract(f"2026年{category}住宿服务").numbers == ("2026",)
    assert accepts(f"{category}2026年住宿服务", f"2026年{category}住宿服务")
    # A fragment is not a category: keep its Chinese quantity unchanged.
    assert TaxQuestionSemanticGuard().extract("一、一般规则、第一条").numbers == ("一", "一", "一")


def test_category_mask_never_concatenates_or_changes_other_constraint_groups():
    text = "2026一般纳税人6% 一般计税〔2026〕10号 第六条 不适用 2026年1月1日"
    old = asdict(QuestionSemanticGuard().extract(text))
    new = asdict(TaxQuestionSemanticGuard().extract(text))
    assert new.pop("numbers") == ("2026", "6%", "2026", "10", "六", "2026", "1", "1")
    old.pop("numbers")
    assert new == old
    assert new["document_numbers"] == ("一般计税〔2026〕10号",)
    assert new["dates"] == ("2026年1月1日",)
    assert new["article_refs"] == ("第六条",) and new["negations"] == ("不",)


@pytest.mark.parametrize("original,candidate", [
    ("一般纳税人2026年6%税率", "一般纳税人2027年6%税率"),
    ("一般计税6%税率", "一般计税9%税率"),
    ("一般计税6%税率", "一般计税6税率"),
    ("一般计税2026年6%税率", "一般计税6%税率2026年"),
    ("一般计税六元和九元", "一般计税九元和六元"),
    ("一般计税6元与6元", "一般计税6元"),
    ("一般计税2026年1月1日", "一般计税2026年1月2日"),
    ("一般计税〔2026〕10号", "一般纳税人〔2026〕10号"),
    ("一般计税第六条", "一般计税第七条"),
    ("一般计税不适用", "一般计税适用"),
    ("一般计税免税", "一般计税征税"),
])
def test_true_constraints_are_not_relaxed(original, candidate):
    assert not accepts(original, candidate)


@pytest.mark.parametrize("text", ["", None, 2026, "一般计税\x00", "一般计税\u200b", "一般计税 " * 33])
def test_original_input_validation_is_preserved_before_masking(text):
    with pytest.raises(KnowledgeInputError):
        TaxQuestionSemanticGuard().extract(text)


def test_candidate_length_and_frozen_constraints():
    guard = TaxQuestionSemanticGuard()
    original = guard.extract("一般纳税人2026年")
    assert not guard.validate_candidate(candidate="一般纳税人2026年" + "甲" * 1024,
                                        constraints=original, max_chars=1024).accepted
    assert original.numbers == ("2026",)
    from dataclasses import FrozenInstanceError
    with pytest.raises(FrozenInstanceError):
        original.numbers = ()


@pytest.mark.asyncio
@pytest.mark.parametrize("current,expected", [(False, RewriteStageKind.FAILURE), (True, RewriteStageKind.SUCCESS)])
async def test_historical_default_and_explicit_current_guard_have_separate_semantics(current, expected):
    class Gateway:
        calls = 0

        async def generate(self, **kwargs):
            self.calls += 1
            return SimpleNamespace(output=KnowledgeSemanticPlanOutput(outcome="search", missing_conditions=(),
                queries=(PlannedDomainQuery(domain_id="tax.policy", query="2026年一般纳税人一般计税住宿服务税率"),)))

    gateway = Gateway()
    planner = KnowledgeSemanticPlanner(
        gateway=gateway, context=SimpleNamespace(require_current=lambda: object()),
        enabled_domain_ids=("tax.policy",), definition=KnowledgeRewriteTaskV6.definition(),
        **({"semantic_guard": TaxQuestionSemanticGuard()} if current else {}),
    )
    result = await planner.rewrite(original_question="一般纳税人一般计税2026年住宿服务税率", timeout_s=1)
    assert result.kind is expected and gateway.calls == 1
    assert type(planner._semantic) is (TaxQuestionSemanticGuard if current else QuestionSemanticGuard)
