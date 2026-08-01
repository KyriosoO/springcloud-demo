from __future__ import annotations

from functools import partial
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from langgraph.graph import END, START, StateGraph

from agent_runtime.capability_api.contracts import CapabilityRegistrationProvider
from agent_runtime.core.execution import CapabilityExecutionCore
from agent_runtime.core.registry import CapabilityRegistryBuilder
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
from agent_runtime.graph.state import AgentInputState, AgentOutputState, AgentRequestState, GraphRunContext
from agent_runtime.runtime import AgentRuntimeInvoker
from agent_runtime.settings import CoreRuntimeSettings
from agent_runtime.model.context import (
    ModelCallContextAccessor,
    ModelContextBindingRuntimeInvoker,
)
from agent_runtime.model.contracts import (
    AnswerGroundingPolicy,
    ModelTaskDefinition,
    StructuredModelGateway,
    StructuredModelTransport,
)
from agent_runtime.model.deepseek.action_selector import (
    DeepSeekActionSelector,
    build_action_selection_task_definition,
)
from agent_runtime.model.deepseek.answer_generator import (
    DeepSeekAnswerGenerator,
    build_answer_generation_task_definition,
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
        action_selector: ActionSelectionNode,
        answer_generator: AnswerGenerationNode,
    ) -> AgentRuntimeInvoker:
        candidates = tuple(
            candidate
            for provider in providers
            for candidate in provider.registrations()
        )
        registry = CapabilityRegistryBuilder(settings).build(candidates)
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
                descriptors=registry.descriptors(),
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


@dataclass(frozen=True, slots=True, kw_only=True)
class LocalModelComponents:
    action_selector: ActionSelectionNode
    answer_generator: AnswerGenerationNode
    context_accessor: ModelCallContextAccessor
    gateway: StructuredModelGateway

    def bind_runtime(self, runtime: AgentRuntimeInvoker) -> ModelContextBindingRuntimeInvoker:
        return ModelContextBindingRuntimeInvoker(runtime)


class LocalModelCompositionRoot:
    """Builds only the provider-neutral local/stub model slice."""

    @staticmethod
    def build(
        *,
        settings: ModelSettings,
        transport: StructuredModelTransport,
        grounding_policies: Mapping[str, AnswerGroundingPolicy],
        max_question_chars: int = 4096,
        max_argument_bytes: int = 16384,
        additional_definitions: Sequence[ModelTaskDefinition[Any, Any]] = (),
    ) -> LocalModelComponents:
        if settings.provider is not ModelProvider.STUB:
            raise ValueError("model.local_composition_requires_stub")
        action_definition = build_action_selection_task_definition(
            timeout_ms=settings.action_timeout_ms,
        )
        answer_definition = build_answer_generation_task_definition(
            timeout_ms=settings.answer_timeout_ms,
        )
        gateway = BoundedStructuredModelGateway(
            transport=transport,
            definitions=(action_definition, answer_definition, *additional_definitions),
            max_concurrency=settings.max_concurrency,
        )
        guard = QuestionEgressGuard(max_question_chars=max_question_chars)
        accessor = ModelCallContextAccessor()
        grounding = GroundingPolicyRegistry(grounding_policies)
        return LocalModelComponents(
            action_selector=DeepSeekActionSelector(
                guard=guard,
                gateway=gateway,
                context=accessor,
                definition=action_definition,
                max_argument_bytes=max_argument_bytes,
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
        from agent_runtime.knowledge.evidence.summary_task import KnowledgeSummaryTaskV1
        from agent_runtime.knowledge.rewrite import KnowledgeRewriteTaskV1

        return KnowledgeTaskDefinitions(
            rewrite=KnowledgeRewriteTaskV1.definition(),
            summary=KnowledgeSummaryTaskV1.definition(),
        )

    @staticmethod
    def build_provider(
        *,
        settings: object,
        model: LocalModelComponents,
        tasks: KnowledgeTaskDefinitions | None,
        retrieval: object | None,
        policy_catalog: object | None,
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
            if tasks is not None or retrieval is not None or policy_catalog is not None:
                raise ValueError("knowledge.disabled_dependencies_forbidden")
            return KnowledgeCapabilityProvider(enabled=False, handler=None)
        if tasks is None or retrieval is None or not isinstance(policy_catalog, KnowledgeEgressPolicyCatalog):
            raise ValueError("knowledge.dependencies_required")
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
