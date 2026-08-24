from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import partial
from typing import Any, Awaitable, Callable, Mapping, Sequence, cast

from langgraph.graph import END, START, StateGraph

from agent_runtime.capability_api.action_resolution import LocalActionResolver
from agent_runtime.capability_api.contracts import CapabilityDescriptor, CapabilityRegistrationProvider
from agent_runtime.core.execution import CapabilityExecutionCore
from agent_runtime.core.registry import CapabilityRegistryBuilder
from agent_runtime.graph.nodes import (
    AnswerGenerationNode,
    execute_capability_node,
    finalize_without_model,
    generate_answer_node,
    route_after_capability,
    route_after_selection,
    select_action_node,
)
from agent_runtime.graph.action_resolution import (
    CapabilitySelectionNode,
    HybridActionSelectionNode,
    is_exact_empty_execution_schema,
)
from agent_runtime.graph.state import AgentInputState, AgentOutputState, AgentRequestState, GraphRunContext
from agent_runtime.runtime import AgentRuntimeInvoker
from agent_runtime.settings import CoreRuntimeSettings
from agent_runtime.model.context import (
    ModelCallContextAccessor,
    ModelContextBindingRuntimeInvoker,
)
from agent_runtime.model.contracts import (
    AnswerGroundingPolicy,
    BusinessQueryPlanGenerator,
    ModelTaskDefinition,
    StructuredModelGateway,
    StructuredModelTransport,
)
from agent_runtime.model.deepseek.business_query_plan import (
    DeepSeekBusinessQueryPlanGenerator,
    build_business_query_plan_task_definition,
)
from agent_runtime.model.deepseek.action_selector import (
    DeepSeekCapabilitySelector,
    build_action_selection_task_definition,
)
from agent_runtime.model.deepseek.answer_generator import (
    DeepSeekAnswerGenerator,
)
from agent_runtime.model.deepseek.answer_generator_v2 import (
    build_answer_generation_v2_task_definition,
)
from agent_runtime.model.deepseek.transport import (
    DeepSeekChatTransport,
    build_deepseek_http_client,
)
from agent_runtime.model.gateway import BoundedStructuredModelGateway
from agent_runtime.model.grounding import GroundingPolicyRegistry
from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.model.settings import ModelProvider, ModelSettings


class RuntimeCompositionRoot:
    @staticmethod
    def build(
        *,
        settings: CoreRuntimeSettings,
        providers: Sequence[CapabilityRegistrationProvider],
        capability_selector: CapabilitySelectionNode,
        answer_generator: AnswerGenerationNode,
        local_action_resolvers: Sequence[LocalActionResolver] = (),
    ) -> AgentRuntimeInvoker:
        candidates = tuple(
            candidate
            for provider in providers
            for candidate in provider.registrations()
        )
        registry = CapabilityRegistryBuilder(settings).build(candidates)
        descriptors = registry.descriptors()
        resolvers = _validate_local_action_resolvers(
            descriptors=descriptors,
            resolvers=local_action_resolvers,
        )
        action_selector = HybridActionSelectionNode(
            descriptors=descriptors,
            resolvers=resolvers,
            capability_selector=capability_selector,
        )
        core = CapabilityExecutionCore(registry, settings)

        graph = StateGraph(
            AgentRequestState,
            input_schema=AgentInputState,
            output_schema=AgentOutputState,
            context_schema=GraphRunContext,
        )
        graph.add_node(
            "select_action",
            partial(
                select_action_node,
                descriptors=descriptors,
                selector=action_selector,
            ),
        )
        graph.add_node("execute_capability", partial(execute_capability_node, core=core))
        graph.add_node(
            "generate_answer",
            partial(generate_answer_node, answer_generator=answer_generator),
        )
        graph.add_node("finalize_without_model", finalize_without_model)
        graph.add_edge(START, "select_action")
        graph.add_conditional_edges(
            "select_action",
            route_after_selection,
            {"execute": "execute_capability", "end": END},
        )
        graph.add_conditional_edges(
            "execute_capability",
            route_after_capability,
            {"answer": "generate_answer", "fixed": "finalize_without_model"},
        )
        graph.add_edge("generate_answer", END)
        graph.add_edge("finalize_without_model", END)
        compiled = graph.compile()
        return AgentRuntimeInvoker(compiled, settings)


def _validate_local_action_resolvers(
    *,
    descriptors: tuple[CapabilityDescriptor, ...],
    resolvers: Sequence[LocalActionResolver],
) -> tuple[LocalActionResolver, ...]:
    descriptor_by_id = {descriptor.capability_id: descriptor for descriptor in descriptors}
    resolver_by_id: dict[str, LocalActionResolver] = {}
    resolver_objects: set[int] = set()
    for resolver in resolvers:
        try:
            capability_id = resolver.capability_id
            resolve = resolver.resolve
        except Exception:
            raise ValueError("runtime.invalid_local_action_resolver") from None
        if not isinstance(capability_id, str) or not capability_id or not callable(resolve):
            raise ValueError("runtime.invalid_local_action_resolver")
        if capability_id not in descriptor_by_id:
            raise ValueError("runtime.local_action_resolver_not_enabled")
        if capability_id in resolver_by_id or id(resolver) in resolver_objects:
            raise ValueError("runtime.duplicate_local_action_resolver")
        resolver_by_id[capability_id] = resolver
        resolver_objects.add(id(resolver))

    for descriptor in descriptors:
        if (
            not is_exact_empty_execution_schema(descriptor.argument_schema)
            and descriptor.capability_id not in resolver_by_id
        ):
            raise ValueError("runtime.local_action_resolver_missing")
    return tuple(resolver_by_id[capability_id] for capability_id in sorted(resolver_by_id))


@dataclass(frozen=True, slots=True, kw_only=True)
class LocalModelComponents:
    action_selector: CapabilitySelectionNode
    business_query_plan_generator: BusinessQueryPlanGenerator
    answer_generator: AnswerGenerationNode
    context_accessor: ModelCallContextAccessor
    gateway: StructuredModelGateway
    _lifecycle: _ModelResourceLifecycle

    def bind_runtime(self, runtime: AgentRuntimeInvoker) -> ModelContextBindingRuntimeInvoker:
        return ModelContextBindingRuntimeInvoker(runtime, close=self.aclose)

    async def aclose(self) -> None:
        await self._lifecycle.aclose()


class _ModelResourceLifecycle:
    __slots__ = ("_close", "_closed", "_lock")

    def __init__(self, close: Callable[[], Awaitable[None]] | None) -> None:
        self._close = close
        self._closed = False
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._close is not None:
                await self._close()


class LocalModelCompositionRoot:
    """Builds the provider-neutral model slice and owns provider resources."""

    @staticmethod
    def build(
        *,
        settings: ModelSettings,
        transport: StructuredModelTransport | None = None,
        grounding_policies: Mapping[str, AnswerGroundingPolicy],
        max_question_chars: int = 4096,
        max_argument_bytes: int = 16384,
        additional_definitions: Sequence[ModelTaskDefinition[Any, Any]] = (),
    ) -> LocalModelComponents:
        if (
            not isinstance(max_argument_bytes, int)
            or isinstance(max_argument_bytes, bool)
            or max_argument_bytes <= 0
        ):
            raise ValueError("model.invalid_action_output_limit")
        action_definition = build_action_selection_task_definition(
            timeout_ms=settings.action_timeout_ms,
        )
        business_query_plan_definition = build_business_query_plan_task_definition(
            timeout_ms=settings.action_timeout_ms,
            max_output_bytes=max_argument_bytes,
        )
        answer_definition = build_answer_generation_v2_task_definition(
            timeout_ms=settings.answer_timeout_ms,
        )
        definitions: tuple[ModelTaskDefinition[Any, Any], ...] = (
            cast(ModelTaskDefinition[Any, Any], action_definition),
            cast(ModelTaskDefinition[Any, Any], business_query_plan_definition),
            cast(ModelTaskDefinition[Any, Any], answer_definition),
            *additional_definitions,
        )
        definition_keys = tuple((definition.task_id, definition.task_version) for definition in definitions)
        if len(set(definition_keys)) != len(definition_keys):
            raise ValueError("model.duplicate_task_definition")
        guard = QuestionEgressGuard(max_question_chars=max_question_chars)
        accessor = ModelCallContextAccessor()
        grounding = GroundingPolicyRegistry(grounding_policies)

        close: Callable[[], Awaitable[None]] | None = None
        if settings.provider is ModelProvider.STUB:
            if transport is None:
                raise ValueError("model.stub_transport_required")
            active_transport = transport
        else:
            if transport is not None:
                raise ValueError("model.deepseek_transport_managed")
            client = build_deepseek_http_client(settings)
            active_transport = DeepSeekChatTransport(settings=settings, client=client)
            close = client.aclose
        gateway = BoundedStructuredModelGateway(
            transport=active_transport,
            definitions=definitions,
            max_concurrency=settings.max_concurrency,
        )
        return LocalModelComponents(
            action_selector=DeepSeekCapabilitySelector(
                guard=guard,
                gateway=gateway,
                context=accessor,
                definition=action_definition,
                max_argument_bytes=max_argument_bytes,
            ),
            business_query_plan_generator=DeepSeekBusinessQueryPlanGenerator(
                gateway=gateway,
                definition=business_query_plan_definition,
            ),
            answer_generator=DeepSeekAnswerGenerator(
                guard=guard,
                gateway=gateway,
                context=accessor,
                grounding=grounding,
                definition=answer_definition,
            ),
            context_accessor=accessor,
            gateway=gateway,
            _lifecycle=_ModelResourceLifecycle(close),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeTaskDefinitions:
    rewrite: ModelTaskDefinition[Any, Any]
    summary: ModelTaskDefinition[Any, Any]

    def as_tuple(self) -> tuple[ModelTaskDefinition[Any, Any], ...]:
        return (self.rewrite, self.summary)


class KnowledgeCompositionRoot:
    @staticmethod
    def task_definitions(*, enabled: bool) -> KnowledgeTaskDefinitions | None:
        if not enabled:
            return None
        from agent_runtime.knowledge.evidence.summary_task_v2 import KnowledgeSummaryTaskV2
        from agent_runtime.knowledge.rewrite import KnowledgeRewriteTaskV1

        return KnowledgeTaskDefinitions(
            rewrite=KnowledgeRewriteTaskV1.definition(),
            summary=KnowledgeSummaryTaskV2.definition(),
        )

    @staticmethod
    def build_provider(
        *,
        settings: object,
        model: LocalModelComponents,
        tasks: KnowledgeTaskDefinitions | None,
        retrieval: object | None,
    ) -> CapabilityRegistrationProvider:
        from typing import cast

        from agent_runtime.knowledge.catalog import build_tax_domain_catalog
        from agent_runtime.knowledge.domain_selection import DeterministicDomainSelector
        from agent_runtime.knowledge.evidence.catalog import KnowledgeEgressPolicyCatalog
        from agent_runtime.knowledge.evidence.stage import DefaultKnowledgeEvidenceStage
        from agent_runtime.knowledge.evidence.contracts import KnowledgeSummaryInput, KnowledgeSummaryOutput
        from agent_runtime.knowledge.planning import KnowledgeRetrievalPlanBuilder
        from agent_runtime.knowledge.provider import KnowledgeCapabilityProvider
        from agent_runtime.knowledge.question_semantics import QuestionSemanticGuard
        from agent_runtime.knowledge.rewrite import KnowledgeQuestionRewriter, KnowledgeRewriteInput, KnowledgeRewriteOutput
        from agent_runtime.knowledge.settings import KnowledgeSettings
        from agent_runtime.knowledge.contracts import KnowledgeRetrievalStage

        typed_settings = cast(KnowledgeSettings, settings)
        if not typed_settings.enabled:
            if tasks is not None or retrieval is not None:
                raise ValueError("knowledge.disabled_dependencies_forbidden")
            return KnowledgeCapabilityProvider(enabled=False, handler=None)
        if tasks is None or retrieval is None:
            raise ValueError("knowledge.dependencies_required")
        policy_catalog = KnowledgeEgressPolicyCatalog.load_v1_resource()
        rewrite_definition = cast(ModelTaskDefinition[KnowledgeRewriteInput, KnowledgeRewriteOutput], tasks.rewrite)
        summary_definition = cast(ModelTaskDefinition[KnowledgeSummaryInput, KnowledgeSummaryOutput], tasks.summary)
        rewriter = KnowledgeQuestionRewriter(
            guard=QuestionEgressGuard(max_question_chars=4096),
            semantic_guard=QuestionSemanticGuard(),
            gateway=model.gateway,
            context=model.context_accessor,
            definition=rewrite_definition,
            max_candidates=typed_settings.rewrite_max_candidates,
            max_retrieval_query_chars=typed_settings.max_retrieval_query_chars,
            allow_original_fallback=typed_settings.allow_original_fallback,
        )
        evidence = DefaultKnowledgeEvidenceStage(
            catalog=policy_catalog,
            guard=QuestionEgressGuard(max_question_chars=4096),
            context=model.context_accessor,
            gateway=model.gateway,
            definition=summary_definition,
        )
        from agent_runtime.knowledge.capability import KnowledgeQueryCapability

        handler = KnowledgeQueryCapability(
            settings=typed_settings,
            enabled_domains=build_tax_domain_catalog().enabled(typed_settings.enabled_domain_ids),
            rewriter=rewriter,
            selector=DeterministicDomainSelector(),
            planner=KnowledgeRetrievalPlanBuilder(),
            retrieval=cast(KnowledgeRetrievalStage[Any], retrieval),
            evidence=evidence,
        )
        return KnowledgeCapabilityProvider(enabled=True, handler=handler)
