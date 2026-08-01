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

