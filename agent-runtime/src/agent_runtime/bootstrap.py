from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import partial
from typing import Any, Awaitable, Callable, Mapping, Protocol, Sequence, cast

from langgraph.graph import END, START, StateGraph

from agent_runtime.capability_api.action_resolution import LocalActionResolver
from agent_runtime.capability_api.contracts import (
    CapabilityDescriptor,
    CapabilityRegistrationCandidate,
    CapabilityRegistrationProvider,
)
from agent_runtime.core.execution import CapabilityExecutionCore
from agent_runtime.core.registry import CapabilityRegistryBuilder
from agent_runtime.adapters.employee.protected_input import EmployeeProtectedValueExtractor
from agent_runtime.adapters.employee.provider import EmployeeSearchDomainProvider
from agent_runtime.adapters.transaction.protected_input import TransactionProtectedValueExtractor
from agent_runtime.adapters.transaction.provider import TransactionListDomainProvider
from agent_runtime.business.contracts import BusinessServiceKey
from agent_runtime.business.egress import BusinessEgressProjector
from agent_runtime.business.handler import BoundBusinessActionHandler
from agent_runtime.business.http_client import FakeDomainTransport, UserJwtBusinessHttpClient
from agent_runtime.business.protected_input import CompositeBusinessProtectedValueExtractor
from agent_runtime.business.provider import BusinessSupportFactory
from agent_runtime.business.query_plan import (
    DefaultBusinessQueryPlanValidator,
    ExactBusinessQueryPlanDecoder,
    RequestProtectedValueBinder,
)
from agent_runtime.business.settings import (
    BusinessConfigurationSource,
    BusinessGlobalSettings,
    BusinessQueryConfigurationLoader,
    BusinessServiceBinding,
    GlobalBusinessEgressPolicy,
)
from agent_runtime.business.user_projection import BusinessUserResultProjector
from agent_runtime.graph.nodes import (
    ActionSelectionNode,
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
from agent_runtime.graph.business_query_planning import (
    BusinessAwareActionSelectionNode,
    BusinessQueryPlanningNode,
    BusinessQueryPlanRuntimeBindings,
    validate_business_query_plan_composition,
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
from agent_runtime.model.deepseek.business_query_plan import DeepSeekBusinessQueryPlanGenerator
from agent_runtime.model.deepseek.business_query_plan_v7 import build_business_query_plan_task_definition
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
        business_query_plan: BusinessQueryPlanRuntimeBindings | None = None,
    ) -> AgentRuntimeInvoker:
        candidates = tuple(
            candidate
            for provider in providers
            for candidate in provider.registrations()
        )
        registry = CapabilityRegistryBuilder(settings).build(candidates)
        descriptors = registry.descriptors()
        business_action_ids = (
            validate_business_query_plan_composition(
                registry=registry,
                bindings=business_query_plan,
            )
            if business_query_plan is not None
            else ()
        )
        fallback_descriptors = tuple(
            descriptor
            for descriptor in descriptors
            if descriptor.capability_id not in business_action_ids
        )
        resolvers = _validate_local_action_resolvers(
            descriptors=fallback_descriptors,
            resolvers=local_action_resolvers,
        )
        fallback_selector = HybridActionSelectionNode(
            descriptors=fallback_descriptors,
            resolvers=resolvers,
            capability_selector=capability_selector,
        )
        action_selector: ActionSelectionNode = fallback_selector
        if business_query_plan is not None:
            action_selector = BusinessAwareActionSelectionNode(
                all_descriptors=descriptors,
                fallback_descriptors=fallback_descriptors,
                fallback_selector=fallback_selector,
                planning_node=BusinessQueryPlanningNode(
                    generator=business_query_plan.generator,
                    decoder=ExactBusinessQueryPlanDecoder(),
                    validator=DefaultBusinessQueryPlanValidator(
                        business_query_plan.definitions
                    ),
                    binder=RequestProtectedValueBinder(),
                    registry=registry,
                    planner_catalog=business_query_plan.planner_catalog,
                ),
                bindings=business_query_plan,
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


class _BusinessRegistrationProvider:
    __slots__ = ("_registrations",)

    def __init__(self, registrations: Sequence[CapabilityRegistrationCandidate[Any]]) -> None:
        self._registrations = tuple(registrations)

    def registrations(self) -> tuple[CapabilityRegistrationCandidate[Any], ...]:
        return self._registrations


class _AsyncCloseable(Protocol):
    async def aclose(self) -> None: ...


class _BusinessRuntimeLifecycle:
    __slots__ = ("_model", "_resources")

    def __init__(
        self,
        *,
        clients: tuple[UserJwtBusinessHttpClient, ...],
        additional_resources: Sequence[_AsyncCloseable],
        model: LocalModelComponents,
    ) -> None:
        resources: tuple[_AsyncCloseable, ...] = (*clients, *additional_resources)
        if len({id(resource) for resource in resources}) != len(resources):
            raise ValueError("runtime.duplicate_owned_resource")
        self._resources = resources
        self._model = model

    async def aclose(self) -> None:
        failure: BaseException | None = None
        for resource in self._resources:
            try:
                await resource.aclose()
            except BaseException as exc:
                if failure is None:
                    failure = exc
        try:
            await self._model.aclose()
        except BaseException as exc:
            if failure is None:
                failure = exc
        if failure is not None:
            raise failure


class BusinessQueryRuntimeCompositionRoot:
    """Owns the sole three-action Business QueryPlan production object graph."""

    @staticmethod
    def build(
        *,
        model: LocalModelComponents,
        employee_transport: FakeDomainTransport,
        transaction_transport: FakeDomainTransport,
        employee_endpoint: str,
        transaction_endpoint: str,
        global_settings: BusinessGlobalSettings | None = None,
        additional_providers: Sequence[CapabilityRegistrationProvider] = (),
        additional_resources: Sequence[_AsyncCloseable] = (),
        local_action_resolvers: Sequence[LocalActionResolver] = (),
    ) -> ModelContextBindingRuntimeInvoker:
        core_settings = CoreRuntimeSettings()
        configured = dict(BusinessQueryConfigurationLoader.load_v3_resource().actions)
        employee_provider = EmployeeSearchDomainProvider(
            search_settings=configured["employee.search"],
            semantic_settings=configured["employee.semantic_search"],
            service_binding=BusinessServiceBinding(
                service_key=BusinessServiceKey("employee-service"),
                base_endpoint=employee_endpoint,
            ),
        )
        transaction_provider = TransactionListDomainProvider(
            settings=configured["transaction.search"],
            service_binding=BusinessServiceBinding(
                service_key=BusinessServiceKey("mq-procedure-service"),
                base_endpoint=transaction_endpoint,
            ),
        )
        definitions = (*employee_provider.definitions(), *transaction_provider.definitions())
        fragments = (
            employee_provider.configuration_fragment(),
            transaction_provider.configuration_fragment(),
        )
        support = BusinessSupportFactory().build(
            definitions=definitions,
            config=BusinessConfigurationSource(
                global_settings=global_settings or BusinessGlobalSettings(),
                actions=tuple(item for fragment in fragments for item in fragment.actions),
                service_bindings=tuple(
                    item for fragment in fragments for item in fragment.service_bindings
                ),
            ),
            core_max_domain_result_bytes=core_settings.max_domain_result_bytes,
        )
        if support.planner_catalog is None:
            raise ValueError("business.plan_composition_invalid")
        clients = {
            "employee-service": UserJwtBusinessHttpClient(
                transport=employee_transport,
                max_response_bytes=support.global_settings.http_max_response_bytes,
            ),
            "mq-procedure-service": UserJwtBusinessHttpClient(
                transport=transaction_transport,
                max_response_bytes=support.global_settings.http_max_response_bytes,
            ),
        }
        registrations = tuple(
            CapabilityRegistrationCandidate[Any](
                descriptor=item.definition.descriptor,
                enabled=item.settings.enabled,
                argument_validator=item.definition.argument_validator,
                handler=BoundBusinessActionHandler(
                    definition=item.definition,
                    settings=item.settings,
                    client=clients[str(item.definition.service_key)],
                    user_projector=BusinessUserResultProjector(),
                    egress_projector=BusinessEgressProjector(),
                    egress_policy=GlobalBusinessEgressPolicy.from_settings(
                        support.global_settings
                    ),
                    config_snapshot_id=support.snapshot_id,
                    max_user_result_bytes=support.global_settings.max_user_result_bytes,
                ),
            )
            for item in support.actions
        )
        runtime = RuntimeCompositionRoot.build(
            settings=core_settings,
            providers=(
                _BusinessRegistrationProvider(registrations),
                *additional_providers,
            ),
            capability_selector=model.action_selector,
            answer_generator=model.answer_generator,
            local_action_resolvers=local_action_resolvers,
            business_query_plan=BusinessQueryPlanRuntimeBindings(
                definitions=definitions,
                snapshot=support.configuration_snapshot,
                planner_catalog=support.planner_catalog,
                generator=model.business_query_plan_generator,
                context_accessor=model.context_accessor,
                protected_value_extractor=CompositeBusinessProtectedValueExtractor(
                    (EmployeeProtectedValueExtractor(), TransactionProtectedValueExtractor())
                ),
                guard=QuestionEgressGuard(),
            ),
        )
        lifecycle = _BusinessRuntimeLifecycle(
            clients=tuple(clients.values()),
            additional_resources=additional_resources,
            model=model,
        )
        return ModelContextBindingRuntimeInvoker(runtime, close=lifecycle.aclose)


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeTaskDefinitions:
    rewrite: ModelTaskDefinition[Any, Any]
    summary: ModelTaskDefinition[Any, Any]

    def as_tuple(self) -> tuple[ModelTaskDefinition[Any, Any], ...]:
        return (self.rewrite, self.summary)


class KnowledgeCompositionRoot:
    @staticmethod
    def task_definitions(*, enabled: bool, rewrite_max_candidates: int = 3) -> KnowledgeTaskDefinitions | None:
        if not enabled:
            return None
        from agent_runtime.knowledge.evidence.summary_task_v5 import KnowledgeSummaryTaskV5
        from agent_runtime.knowledge.rewrite_v5 import KnowledgeRewriteTaskV5

        return KnowledgeTaskDefinitions(
            rewrite=KnowledgeRewriteTaskV5.definition(),
            summary=KnowledgeSummaryTaskV5.definition(),
        )

    @staticmethod
    def build_provider(
        *,
        settings: object,
        model: LocalModelComponents,
        tasks: KnowledgeTaskDefinitions | None,
        retrieval: object | None,
        policy_catalog: object | None = None,
    ) -> CapabilityRegistrationProvider:
        from typing import cast

        from agent_runtime.knowledge.catalog import build_tax_domain_catalog
        from agent_runtime.knowledge.evidence.catalog import KnowledgeEgressPolicyCatalog
        from agent_runtime.knowledge.evidence.stage import DefaultKnowledgeEvidenceStage
        from agent_runtime.knowledge.evidence.contracts import KnowledgeEvidenceLimits, KnowledgeSummaryInput, KnowledgeSummaryOutput
        from agent_runtime.knowledge.planning import KnowledgeRetrievalPlanBuilder
        from agent_runtime.knowledge.provider import KnowledgeCapabilityProvider
        from agent_runtime.knowledge.semantic_planner import KnowledgeSemanticPlanner
        from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput, KnowledgeSemanticPlanOutput
        from agent_runtime.knowledge.settings import KnowledgeSettings
        from agent_runtime.knowledge.contracts import KnowledgeRetrievalStage

        typed_settings = cast(KnowledgeSettings, settings)
        if not typed_settings.enabled:
            if tasks is not None or retrieval is not None:
                raise ValueError("knowledge.disabled_dependencies_forbidden")
            return KnowledgeCapabilityProvider(enabled=False, handler=None)
        if tasks is None or retrieval is None:
            raise ValueError("knowledge.dependencies_required")
        typed_policy_catalog = (
            KnowledgeEgressPolicyCatalog.load_current_resource()
            if policy_catalog is None
            else policy_catalog
        )
        if not isinstance(typed_policy_catalog, KnowledgeEgressPolicyCatalog):
            raise ValueError("knowledge.policy_catalog_invalid")
        if tasks.rewrite.task_version != "5" or tasks.summary.task_version != "5":
            raise ValueError("knowledge.production_task_version_invalid")
        summary_definition = cast(ModelTaskDefinition[KnowledgeSummaryInput, KnowledgeSummaryOutput], tasks.summary)
        rewriter = KnowledgeSemanticPlanner(
            gateway=model.gateway,
            context=model.context_accessor,
            definition=cast(ModelTaskDefinition[KnowledgeSemanticPlanInput, KnowledgeSemanticPlanOutput], tasks.rewrite),
            enabled_domain_ids=typed_settings.enabled_domain_ids,
            max_query_chars=typed_settings.max_retrieval_query_chars,
        )
        evidence = DefaultKnowledgeEvidenceStage(
            catalog=typed_policy_catalog,
            guard=QuestionEgressGuard(max_question_chars=4096),
            context=model.context_accessor,
            gateway=model.gateway,
            definition=summary_definition,
            limits=KnowledgeEvidenceLimits.quality_v1(),
        )
        from agent_runtime.knowledge.capability import KnowledgeQueryCapability

        handler = KnowledgeQueryCapability(
            settings=typed_settings,
            enabled_domains=build_tax_domain_catalog().enabled(typed_settings.enabled_domain_ids),
            rewriter=rewriter,
            selector=None,
            planner=KnowledgeRetrievalPlanBuilder(),
            retrieval=cast(KnowledgeRetrievalStage[Any], retrieval),
            evidence=evidence,
            require_semantic_plan=True,
        )
        return KnowledgeCapabilityProvider(enabled=True, handler=handler)
