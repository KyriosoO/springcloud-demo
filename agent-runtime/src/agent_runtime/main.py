from __future__ import annotations

import os
from collections.abc import Callable
from typing import Mapping

import httpx

import uvicorn

from agent_runtime.api.app import create_app
from agent_runtime.api.settings import RuntimeHttpSettings
from agent_runtime.bootstrap import (
    BusinessQueryRuntimeCompositionRoot,
    KnowledgeCompositionRoot,
    LocalModelCompositionRoot,
    RuntimeCompositionRoot,
)
from agent_runtime.capability_api.contracts import CapabilityRegistrationProvider
from agent_runtime.adapters.http_transport import HttpxBusinessDomainTransport
from agent_runtime.business.settings import BusinessGlobalSettings
from agent_runtime.graph.action_resolution import (
    CapabilitySelectionDecision,
    CapabilitySelectionDecisionKind,
    CapabilitySelectionInput,
)
from agent_runtime.graph.state import (
    AnswerGenerationDecision,
    AnswerGenerationDecisionKind,
    AnswerGenerationInput,
    ModelNodeFailure,
    ModelNodeFailureKind,
)
from agent_runtime.runtime import AgentRuntimeInvoker
from agent_runtime.settings import CoreRuntimeSettings
from agent_runtime.model.context import ModelContextBindingRuntimeInvoker
from agent_runtime.model.settings import ModelProvider, ModelSettings
from agent_runtime.model.contracts import StructuredModelTransport
from agent_runtime.knowledge.evidence.catalog import KnowledgeEgressPolicyCatalog
from agent_runtime.knowledge.retrieval.http import (
    HttpxKnowledgeTransport,
    build_knowledge_http_client,
)
from agent_runtime.knowledge.retrieval.provider import LocalKnowledgeRetrievalFactory
from agent_runtime.knowledge.retrieval.settings import KnowledgeRetrievalSettings
from agent_runtime.knowledge.settings import KnowledgeSettings


KnowledgeHttpClientFactory = Callable[[str], httpx.AsyncClient]


class _DisabledSelector:
    async def __call__(self, input: CapabilitySelectionInput) -> CapabilitySelectionDecision:
        del input
        return CapabilitySelectionDecision(kind=CapabilitySelectionDecisionKind.UNSUPPORTED)


class _DisabledAnswerGenerator:
    async def __call__(self, input: AnswerGenerationInput) -> AnswerGenerationDecision:
        del input
        return AnswerGenerationDecision(
            kind=AnswerGenerationDecisionKind.FAILURE,
            failure=ModelNodeFailure(kind=ModelNodeFailureKind.INPUT_DENIED),
        )


def build_stub_runtime() -> AgentRuntimeInvoker:
    return RuntimeCompositionRoot.build(
        settings=CoreRuntimeSettings(),
        providers=(),
        capability_selector=_DisabledSelector(),
        answer_generator=_DisabledAnswerGenerator(),
    )


def build_runtime(
    environ: Mapping[str, str] | None = None,
    *,
    model_transport: StructuredModelTransport | None = None,
    knowledge_http_client_factory: KnowledgeHttpClientFactory = build_knowledge_http_client,
) -> AgentRuntimeInvoker | ModelContextBindingRuntimeInvoker:
    active = os.environ if environ is None else environ
    model_settings = ModelSettings.from_env(active)
    knowledge_settings = KnowledgeSettings.from_env(active)
    if model_settings.provider is ModelProvider.STUB and model_transport is None:
        if knowledge_settings.enabled:
            raise ValueError("knowledge.stub_transport_required")
        return build_stub_runtime()
    global_settings = BusinessGlobalSettings.from_env(active)
    employee_endpoint = active.get("AGENT_EMPLOYEE_BASE_URL", "http://127.0.0.1:9210")
    transaction_endpoint = active.get("AGENT_TRANSACTION_BASE_URL", "http://127.0.0.1:8182")
    knowledge_tasks = KnowledgeCompositionRoot.task_definitions(
        enabled=knowledge_settings.enabled,
        rewrite_max_candidates=knowledge_settings.rewrite_max_candidates,
    )
    policy_catalog = (
        KnowledgeEgressPolicyCatalog.load_current_resource()
        if knowledge_settings.enabled
        else None
    )
    retrieval_settings = (
        KnowledgeRetrievalSettings.from_env(active, enabled=True)
        if knowledge_settings.enabled
        else None
    )
    if retrieval_settings is not None and retrieval_settings.final_candidates < 2 * len(knowledge_settings.enabled_domain_ids):
        raise ValueError("knowledge.final_candidates_cannot_cover_domain_anchors")
    model = LocalModelCompositionRoot.build(
        settings=model_settings,
        transport=model_transport,
        grounding_policies={},
        additional_definitions=(
            knowledge_tasks.as_tuple() if knowledge_tasks is not None else ()
        ),
    )
    employee_transport = HttpxBusinessDomainTransport(
        base_endpoint=employee_endpoint,
        allowed_paths=frozenset({"/employees/es/search", "/employees/es/vector-search"}),
        max_response_bytes=global_settings.http_max_response_bytes,
    )
    transaction_transport = HttpxBusinessDomainTransport(
        base_endpoint=transaction_endpoint,
        allowed_paths=frozenset({"/txn/search"}),
        max_response_bytes=global_settings.http_max_response_bytes,
    )
    knowledge_providers: tuple[CapabilityRegistrationProvider, ...] = ()
    knowledge_clients: tuple[httpx.AsyncClient, ...] = ()
    if knowledge_settings.enabled:
        if retrieval_settings is None or retrieval_settings.es_base_url is None:
            raise ValueError("knowledge.retrieval_es_base_url_required")
        knowledge_clients = (
            knowledge_http_client_factory(retrieval_settings.es_base_url),
            knowledge_http_client_factory(retrieval_settings.embedding_base_url),
            knowledge_http_client_factory(retrieval_settings.rerank_base_url),
        )
        retrieval = LocalKnowledgeRetrievalFactory.build(
            settings=retrieval_settings,
            search_transport=HttpxKnowledgeTransport(knowledge_clients[0]),
            embedding_transport=HttpxKnowledgeTransport(knowledge_clients[1]),
            rerank_transport=HttpxKnowledgeTransport(knowledge_clients[2]),
        )
        knowledge_providers = (
            KnowledgeCompositionRoot.build_provider(
                settings=knowledge_settings,
                model=model,
                tasks=knowledge_tasks,
                retrieval=retrieval.stage,
                policy_catalog=policy_catalog,
            ),
        )
    return BusinessQueryRuntimeCompositionRoot.build(
        model=model,
        employee_transport=employee_transport,
        transaction_transport=transaction_transport,
        employee_endpoint=employee_endpoint,
        transaction_endpoint=transaction_endpoint,
        global_settings=global_settings,
        additional_providers=knowledge_providers,
        additional_resources=knowledge_clients,
    )


def main() -> None:
    settings = RuntimeHttpSettings.from_env()
    app = create_app(settings, build_runtime)
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        workers=1,
        http="h11",
        h11_max_incomplete_event_size=settings.max_incomplete_event_bytes,
        access_log=False,
    )


if __name__ == "__main__":
    main()
