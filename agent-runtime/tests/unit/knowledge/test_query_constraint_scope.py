from __future__ import annotations

import pytest

from agent_runtime.knowledge.contracts import (
    KnowledgeEvidenceRequirement, KnowledgeRequirementKind, PlannedDomainQuery,
)
from agent_runtime.knowledge.document_reference_semantics import DocumentReferenceSemanticGuard
from agent_runtime.knowledge.errors import KnowledgeInputError
from agent_runtime.knowledge.query_constraint_scope import validate_scoped_queries

POLICY = "tax.policy"
LAW = "tax.law"
QUESTION = "请分别查找财税〔2011〕100号的软件产品定义，以及增值税法第十条的销售服务税率规定。"
POLICY_QUERY = "财税〔2011〕100号 软件产品定义"
LAW_QUERY = "增值税法第十条 销售服务税率规定"


def check(question: str, queries: tuple[str, ...], focuses: tuple[tuple[str, ...], ...]) -> None:
    domains = (POLICY, LAW)[:len(queries)]
    requirements = []
    for domain, group in zip(domains, focuses, strict=True):
        for text in group:
            requirements.append(KnowledgeEvidenceRequirement(
                requirement_id=f"r{len(requirements) + 1}", domain_id=domain,
                kind=KnowledgeRequirementKind.RULE, focus=text,
            ))
    validate_scoped_queries(
        original_question=question,
        queries=tuple(PlannedDomainQuery(domain_id=domain, query=text)
                      for domain, text in zip(domains, queries, strict=True)),
        requirements=tuple(requirements), semantic_guard=DocumentReferenceSemanticGuard(), max_chars=1024,
    )


def test_independent_document_and_article_are_not_copied_between_domains() -> None:
    check(QUESTION, (POLICY_QUERY, LAW_QUERY), ((POLICY_QUERY,), (LAW_QUERY,)))
    original = DocumentReferenceSemanticGuard().extract(QUESTION)
    for query in (POLICY_QUERY, LAW_QUERY):
        assert not DocumentReferenceSemanticGuard().validate_candidate(
            candidate=query, constraints=original, max_chars=1024,
        ).accepted


@pytest.mark.parametrize("queries", [
    (LAW_QUERY, POLICY_QUERY),
    (POLICY_QUERY.replace("2011", "2012"), LAW_QUERY),
    (POLICY_QUERY.replace("100", "101"), LAW_QUERY),
    (POLICY_QUERY, LAW_QUERY.replace("第十条", "第十一条")),
    (POLICY_QUERY, "销售服务税率规定"),
    (QUESTION, QUESTION),
    (POLICY_QUERY + " 100", LAW_QUERY),
])
def test_wrong_missing_extra_or_moved_constraints_are_rejected(queries: tuple[str, str]) -> None:
    with pytest.raises(KnowledgeInputError, match="query_scope_mismatch"):
        check(QUESTION, queries, ((POLICY_QUERY,), (LAW_QUERY,)))


@pytest.mark.parametrize("condition", [
    "2020-01-01", "不得免税", "一般纳税人", "小规模纳税人", "一般计税", "简易计税", "13％税率",
])
@pytest.mark.parametrize("declared", [False, True])
def test_shared_declared_or_unassigned_conditions_apply_to_each_domain(condition: str, declared: bool) -> None:
    question = f"{condition}，政策定义及法律规则"
    queries = (f"{condition} 政策定义", f"{condition} 法律规则")
    focuses = tuple((text if declared else base,) for text, base in zip(queries, ("政策定义", "法律规则")))
    check(question, queries, focuses)
    with pytest.raises(KnowledgeInputError, match="query_scope_mismatch"):
        check(question, (queries[0], "法律规则"), focuses)


def test_local_date_and_tax_category_do_not_leak_to_other_domain() -> None:
    question = "2020-01-01一般纳税人政策定义，以及法律基本规则"
    check(question, ("2020-01-01 一般纳税人 政策定义", "法律基本规则"),
          (("2020-01-01 一般纳税人 政策定义",), ("法律基本规则",)))


def test_multiple_roles_do_not_multiply_same_condition() -> None:
    check("2020年政策及法律规则", ("2020年政策", "法律规则"),
          (("2020年政策定义", "2020年政策规则"), ("法律规则",)))


def test_repeated_original_value_is_counted_across_domains() -> None:
    check("2020年政策及2020年法律", ("2020年政策", "2020年法律"),
          (("2020年政策",), ("2020年法律",)))
    with pytest.raises(KnowledgeInputError, match="query_scope_mismatch"):
        check("2020年政策及2020年法律", ("2020年政策", "法律"),
              (("2020年政策",), ("法律",)))


def test_single_domain_retains_all_counts_and_order() -> None:
    question = "2020年和2021年政策对比"
    check(question, (question,), (("2020年政策",),))
    for query in ("2020年政策", "2021年和2020年政策对比", "2020年和2021年和2021年政策"):
        with pytest.raises(KnowledgeInputError, match="query_scope_mismatch"):
            check(question, (query,), (("2020年政策",),))


def test_tax_category_order_and_word_position_remain_flexible() -> None:
    check("一般纳税人和小规模纳税人2020年政策对比", ("2020年小规模纳税人和一般纳税人政策对比",),
          (("政策对比",),))


@pytest.mark.parametrize("focus", ["2022年政策", "一般纳税人政策", "13％税率政策", "不得免税政策"])
def test_untrusted_focus_cannot_introduce_constraints(focus: str) -> None:
    with pytest.raises(KnowledgeInputError):
        check("政策和法律规则", ("政策", "法律规则"), ((focus,), ("法律规则",)))


@pytest.mark.parametrize("query", ["13%税率政策", "13‰税率政策", "13％征收率政策", "13％税率政策 13％"])
def test_ratio_unit_and_topic_cannot_be_changed(query: str) -> None:
    with pytest.raises(KnowledgeInputError):
        check("13％税率政策，以及法律规则", (query, "法律规则"), (("13％税率政策",), ("法律规则",)))


def test_no_ratio_topics_can_belong_to_distinct_domains() -> None:
    check("政策征收率和法律税率", ("政策征收率", "法律税率"), (("政策征收率",), ("法律税率",)))
    with pytest.raises(KnowledgeInputError):
        check("政策征收率和法律税率", ("政策征收率", "法律"), (("政策征收率",), ("法律",)))


def test_focus_cannot_introduce_rate_topic_even_without_number() -> None:
    with pytest.raises(KnowledgeInputError, match="query_scope_mismatch"):
        check("政策规则", ("政策规则",), (("政策税率",),))


def test_safety_is_checked_before_scope_is_trusted() -> None:
    with pytest.raises(KnowledgeInputError, match="requirement_focus_denied"):
        check("政策规则", ("政策规则",), (("身份证号码110101199001011234政策",),))


@pytest.mark.parametrize("query", ["政策\x00规则", "政策" * 600, "身份证号码110101199001011234政策"])
def test_invalid_query_is_rejected(query: str) -> None:
    with pytest.raises(KnowledgeInputError):
        check("政策规则", (query,), (("政策规则",),))


def test_structural_success_is_not_proof_of_semantic_ownership() -> None:
    # 有意错误声明：全局日期只归到政策域。机械校验能通过，语义UAT必须判错。
    check("2020年期间，政策和法律均适用什么规则", ("2020年政策规则", "法律规则"),
          (("2020年政策规则",), ("法律规则",)))


def test_calls_do_not_share_constraint_state() -> None:
    check(QUESTION, (POLICY_QUERY, LAW_QUERY), ((POLICY_QUERY,), (LAW_QUERY,)))
    check("政策规则", ("政策规则",), (("政策规则",),))
    with pytest.raises(KnowledgeInputError):
        check("政策规则", (POLICY_QUERY,), (("政策规则",),))
