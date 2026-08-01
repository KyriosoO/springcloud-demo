from __future__ import annotations

import pytest

from agent_runtime.knowledge.retrieval.http import BoundedHttpResponse
from agent_runtime.knowledge.retrieval.provider import LocalKnowledgeRetrievalFactory
from agent_runtime.knowledge.retrieval.settings import KnowledgeRetrievalSettings
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from tests.retrieval_helpers import FakeTransport


def test_local_retrieval_factory_only_composes_injected_fake_transports() -> None:
    settings = KnowledgeRetrievalSettings.from_env(
        {"AGENT_KNOWLEDGE_ES_BASE_URL": "http://127.0.0.1:19999"},
        enabled=True,
    )
    transport = FakeTransport(BoundedHttpResponse(
        status_code=500,
        content_type=None,
        content_encoding=None,
        body=b"",
    ))

    components = LocalKnowledgeRetrievalFactory.build(
        settings=settings,
        search_transport=transport,
        embedding_transport=transport,
        rerank_transport=transport,
    )

    assert isinstance(components.stage, DefaultKnowledgeRetrievalStage)
    assert transport.requests == []


def test_local_retrieval_factory_rejects_disabled_unbound_es_configuration() -> None:
    settings = KnowledgeRetrievalSettings.from_env({}, enabled=False)
    transport = FakeTransport(BoundedHttpResponse(status_code=500, content_type=None, content_encoding=None, body=b""))
    with pytest.raises(ValueError, match="knowledge.retrieval_es_base_url_required"):
        LocalKnowledgeRetrievalFactory.build(
            settings=settings,
            search_transport=transport,
            embedding_transport=transport,
            rerank_transport=transport,
        )
