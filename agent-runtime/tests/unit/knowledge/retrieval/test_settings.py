from __future__ import annotations

import pytest

from agent_runtime.knowledge.retrieval.settings import (
    KnowledgeRetrievalConfigurationError,
    KnowledgeRetrievalSettings,
)
from agent_runtime.knowledge.settings import KnowledgeSettings


def test_retrieval_settings_freeze_expected_local_model_contract() -> None:
    env = {
        "AGENT_KNOWLEDGE_ENABLED": "true",
        "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy",
        "AGENT_KNOWLEDGE_ES_BASE_URL": "http://127.0.0.1:19999",
        "AGENT_KNOWLEDGE_FINAL_CANDIDATES": "3",
    }

    flow = KnowledgeSettings.from_env(env)
    retrieval = KnowledgeRetrievalSettings.from_env(env, enabled=flow.enabled)

    assert retrieval.es_base_url == "http://127.0.0.1:19999"
    assert retrieval.embedding_base_url == "http://127.0.0.1:8908"
    assert retrieval.rerank_base_url == "http://127.0.0.1:8909"
    assert retrieval.final_candidates == 3


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"AGENT_KNOWLEDGE_ES_BASE_URL": "http://user@127.0.0.1:9200"},
        {"AGENT_KNOWLEDGE_ES_BASE_URL": "http://127.0.0.1:9200/path"},
        {"AGENT_KNOWLEDGE_ES_BASE_URL": "http://127.0.0.1:9200", "AGENT_KNOWLEDGE_EMBEDDING_DIM": "01024"},
        {"AGENT_KNOWLEDGE_ES_BASE_URL": "http://127.0.0.1:9200", "AGENT_KNOWLEDGE_RERANK_MODEL": "other"},
        {"AGENT_KNOWLEDGE_ES_BASE_URL": "http://127.0.0.1:9200", "AGENT_KNOWLEDGE_ES_UNKNOWN": "x"},
    ],
)
def test_enabled_retrieval_rejects_missing_or_expansive_configuration(env: dict[str, str]) -> None:
    with pytest.raises(KnowledgeRetrievalConfigurationError):
        KnowledgeRetrievalSettings.from_env(env, enabled=True)
