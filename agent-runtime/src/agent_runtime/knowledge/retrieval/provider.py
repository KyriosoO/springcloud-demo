from __future__ import annotations

from dataclasses import dataclass

from agent_runtime.knowledge.retrieval.bge_embedding import BgeM3EmbeddingAdapter
from agent_runtime.knowledge.retrieval.bge_rerank import BgeRerankAdapter
from agent_runtime.knowledge.retrieval.es_adapter import EsKnowledgeSearchAdapter
from agent_runtime.knowledge.retrieval.http import KnowledgeHttpTransport
from agent_runtime.knowledge.retrieval.settings import KnowledgeRetrievalSettings
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage


@dataclass(frozen=True, slots=True, kw_only=True)
class LocalKnowledgeRetrievalComponents:
    stage: DefaultKnowledgeRetrievalStage
    search: EsKnowledgeSearchAdapter
    embedding: BgeM3EmbeddingAdapter
    rerank: BgeRerankAdapter


class LocalKnowledgeRetrievalFactory:
    """Composes injected transports without owning their connection lifecycle."""

    @staticmethod
    def build(
        *,
        settings: KnowledgeRetrievalSettings,
        search_transport: KnowledgeHttpTransport,
        embedding_transport: KnowledgeHttpTransport,
        rerank_transport: KnowledgeHttpTransport,
    ) -> LocalKnowledgeRetrievalComponents:
        if settings.es_base_url is None:
            raise ValueError("knowledge.retrieval_es_base_url_required")
        search = EsKnowledgeSearchAdapter(
            search_transport,
            expected_profile_version=settings.profile_version,
        )
        embedding = BgeM3EmbeddingAdapter(embedding_transport)
        rerank = BgeRerankAdapter(rerank_transport)
        stage = DefaultKnowledgeRetrievalStage(
            search=search,
            embedding=embedding,
            rerank=rerank,
            final_candidates=settings.final_candidates,
        )
        return LocalKnowledgeRetrievalComponents(
            stage=stage,
            search=search,
            embedding=embedding,
            rerank=rerank,
        )
