from __future__ import annotations

import pytest

from agent_runtime.knowledge.catalog import build_tax_domain_catalog
from agent_runtime.knowledge.errors import KnowledgeConfigurationError
from agent_runtime.knowledge.settings import KnowledgeSettings


def test_catalog_and_settings_freeze_two_code_bound_domains() -> None:
    catalog = build_tax_domain_catalog()
    settings = KnowledgeSettings.from_env(
        {
            "AGENT_KNOWLEDGE_ENABLED": "true",
            "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.law,tax.policy",
        }
    )

    assert tuple(item.domain_id for item in catalog.domains) == ("tax.policy", "tax.law")
    assert settings.enabled_domain_ids == ("tax.policy", "tax.law")


@pytest.mark.parametrize(
    "env",
    [
        {"AGENT_KNOWLEDGE_ENABLED": "TRUE"},
        {"AGENT_KNOWLEDGE_ENABLED": "true", "AGENT_KNOWLEDGE_ENABLED_DOMAINS": ""},
        {"AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,"},
        {"AGENT_KNOWLEDGE_UNKNOWN": "x"},
        {"AGENT_KNOWLEDGE_PER_PATH_CANDIDATES": "5", "AGENT_KNOWLEDGE_MIN_PARTIAL_CANDIDATES": "6"},
    ],
)
def test_invalid_or_expanding_settings_fail_closed(env: dict[str, str]) -> None:
    with pytest.raises(KnowledgeConfigurationError):
        KnowledgeSettings.from_env(env)

