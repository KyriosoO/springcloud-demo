from __future__ import annotations

from dataclasses import dataclass

from agent_runtime.knowledge.retrieval.bge_embedding import BgeM3EmbeddingAdapter
from agent_runtime.knowledge.retrieval.bge_rerank import BgeRerankAdapter
from agent_runtime.knowledge.retrieval.bge_rerank_context import ContextualBgeRerankAdapter
from agent_runtime.knowledge.retrieval.contracts import RerankPort
from agent_runtime.knowledge.retrieval.es_adapter import EsKnowledgeSearchAdapter
from agent_runtime.knowledge.retrieval.http import KnowledgeHttpTransport
from agent_runtime.knowledge.retrieval.settings import KnowledgeRetrievalSettings
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from agent_runtime.knowledge.minimal_plan import MinimalRetrievalSettings
from agent_runtime.knowledge.retrieval.minimal_stage import MinimalKnowledgeRetrievalStage


@dataclass(frozen=True, slots=True, kw_only=True)
class LocalKnowledgeRetrievalComponents:
    stage: DefaultKnowledgeRetrievalStage
    search: EsKnowledgeSearchAdapter
    embedding: BgeM3EmbeddingAdapter
    rerank: RerankPort


@dataclass(frozen=True, slots=True, kw_only=True)
class LocalMinimalKnowledgeRetrievalComponents:
    stage: MinimalKnowledgeRetrievalStage
    search: EsKnowledgeSearchAdapter
    embedding: BgeM3EmbeddingAdapter
    rerank: RerankPort


class LocalKnowledgeRetrievalFactory:
    """Composes injected transports without owning their connection lifecycle."""

    @staticmethod
    def build(
        *,
        settings: KnowledgeRetrievalSettings,
        search_transport: KnowledgeHttpTransport,
        embedding_transport: KnowledgeHttpTransport,
        rerank_transport: KnowledgeHttpTransport,
        rerank_input_version: str = "raw-content-v1",
    ) -> LocalKnowledgeRetrievalComponents:
        if settings.es_base_url is None:
            raise ValueError("knowledge.retrieval_es_base_url_required")
        if type(rerank_input_version) is not str or rerank_input_version not in (
            "raw-content-v1", ContextualBgeRerankAdapter.INPUT_VERSION,
        ):
            raise ValueError("knowledge.rerank_input_version_invalid")
        search = EsKnowledgeSearchAdapter(
            search_transport,
            expected_profile_version=settings.profile_version,
        )
        embedding = BgeM3EmbeddingAdapter(embedding_transport)
        rerank: RerankPort = (ContextualBgeRerankAdapter(rerank_transport)
            if rerank_input_version == ContextualBgeRerankAdapter.INPUT_VERSION else BgeRerankAdapter(rerank_transport))
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

    @staticmethod
    def build_minimal(
        *, settings: KnowledgeRetrievalSettings, minimal_settings: MinimalRetrievalSettings,
        search_transport: KnowledgeHttpTransport, embedding_transport: KnowledgeHttpTransport,
        rerank_transport: KnowledgeHttpTransport,
    ) -> LocalMinimalKnowledgeRetrievalComponents:
        if settings.es_base_url is None or settings.profile_version != "tax-knowledge-search-v1":
            raise ValueError("knowledge.retrieval_settings_invalid")
        search = EsKnowledgeSearchAdapter(search_transport, expected_profile_version=settings.profile_version)
        embedding = BgeM3EmbeddingAdapter(embedding_transport)
        rerank = ContextualBgeRerankAdapter(rerank_transport)
        stage = MinimalKnowledgeRetrievalStage(search=search, embedding=embedding,
                                                rerank=rerank, settings=minimal_settings)
        return LocalMinimalKnowledgeRetrievalComponents(stage=stage, search=search,
                                                        embedding=embedding, rerank=rerank)
