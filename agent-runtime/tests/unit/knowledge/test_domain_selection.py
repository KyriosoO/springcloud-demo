from __future__ import annotations

from agent_runtime.knowledge.catalog import build_tax_domain_catalog
from agent_runtime.knowledge.domain_selection import DeterministicDomainSelector


def test_domain_selection_is_deterministic_and_bounded() -> None:
    domains = build_tax_domain_catalog().domains
    selector = DeterministicDomainSelector()

    assert selector.select(original_question="现行增值税优惠政策", enabled_domains=domains).selected_domain_ids == ("tax.policy",)
    assert selector.select(original_question="增值税条例第五条", enabled_domains=domains).selected_domain_ids == ("tax.law",)
    assert selector.select(original_question="税务政策是否违反法律", enabled_domains=domains).selected_domain_ids == ("tax.policy", "tax.law")
    assert selector.select(original_question="天气如何", enabled_domains=domains).selected_domain_ids == ()


def test_v2_domain_selection_fixes_candidate_04_supported_mismatches() -> None:
    domains = build_tax_domain_catalog().domains
    selector = DeterministicDomainSelector()

    policy_questions = (
        "增值税有哪些税率？",
        "目前增值税一般纳税人适用的税率有哪些？",
        "小规模纳税人增值税征收率是多少？",
        "企业所得税税率是多少？",
        "增值税专用发票丢失怎么处理？",
    )
    for question in policy_questions:
        selection = selector.select(original_question=question, enabled_domains=domains)
        assert selection.selected_domain_ids == ("tax.policy",)
        assert selection.catalog_version == "tax-domain-catalog-v2"

    explicit_law = selector.select(
        original_question="《中华人民共和国企业所得税法》第二十八条规定了哪些优惠情形？",
        enabled_domains=domains,
    )
    assert explicit_law.selected_domain_ids == ("tax.law",)
    assert selector.select(
        original_question="增值税暂行条例实施细则如何规定？",
        enabled_domains=domains,
    ).selected_domain_ids == ("tax.law",)
    assert selector.select(
        original_question="税收征管法有哪些规定？",
        enabled_domains=domains,
    ).selected_domain_ids == ("tax.law",)

    mixed = selector.select(
        original_question="增值税法与一般纳税人现行税率政策在2026年如何衔接？",
        enabled_domains=domains,
    )
    assert mixed.selected_domain_ids == ("tax.policy", "tax.law")


def test_v2_selector_does_not_guess_whether_a_tax_document_exists() -> None:
    domains = build_tax_domain_catalog().domains
    selector = DeterministicDomainSelector()

    fictional_document = selector.select(
        original_question="税测发〔2099〕999号规定的火星资源税减免范围是什么？",
        enabled_domains=domains,
    )
    fictional_law = selector.select(
        original_question="《星际贸易税法》第八十八条规定了哪些免税项目？",
        enabled_domains=domains,
    )

    assert fictional_document.selected_domain_ids == ("tax.policy",)
    assert fictional_law.selected_domain_ids == ("tax.law",)
