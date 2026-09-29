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
    assert catalog.version == "tax-domain-catalog-v2"
    assert settings.enabled_domain_ids == ("tax.policy", "tax.law")


@pytest.mark.parametrize(
    "env",
    [
        {"AGENT_KNOWLEDGE_ENABLED": "TRUE"},
        {"AGENT_KNOWLEDGE_ENABLED": "true", "AGENT_KNOWLEDGE_ENABLED_DOMAINS": ""},
        {"AGENT_KNOWLEDGE_ENABLED": "true", "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,"},
        {"AGENT_KNOWLEDGE_UNKNOWN": "x"},
        {"AGENT_KNOWLEDGE_ENABLED": "true", "AGENT_KNOWLEDGE_PER_PATH_CANDIDATES": "5", "AGENT_KNOWLEDGE_MIN_PARTIAL_CANDIDATES": "6", "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy"},
    ],
)
def test_invalid_or_expanding_settings_fail_closed(env: dict[str, str]) -> None:
    with pytest.raises(KnowledgeConfigurationError):
        KnowledgeSettings.from_env(env)


def test_disabled_knowledge_does_not_parse_known_downstream_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_catalog() -> None:
        raise AssertionError("disabled Knowledge loaded domain catalog")

    monkeypatch.setattr(
        "agent_runtime.knowledge.settings.build_tax_domain_catalog",
        forbidden_catalog,
    )
    settings = KnowledgeSettings.from_env(
        {
            "AGENT_KNOWLEDGE_ENABLED": "false",
            "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,",
            "AGENT_KNOWLEDGE_PER_PATH_CANDIDATES": "bad",
        }
    )

    assert settings.enabled is False
    assert settings.enabled_domain_ids == ()
    assert settings.per_path_candidate_limit == 20
