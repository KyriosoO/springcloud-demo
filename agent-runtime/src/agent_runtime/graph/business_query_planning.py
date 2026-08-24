from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from agent_runtime.capability_api.contracts import (
    ActionCandidate,
    CapabilityDescriptor,
    CapabilityStatus,
    CancellationSignal,
    InvalidCapabilityArguments,
)
from agent_runtime.business.contracts import BusinessActionDefinition
from agent_runtime.business.planner_catalog import (
    BusinessPlannerCatalog,
    build_business_planner_catalog,
)
from agent_runtime.business.protected_input import ProtectedValueExtractor
from agent_runtime.business.query_plan import (
    BusinessQueryPlanDecoder,
    BusinessQueryPlanValidator,
    InvalidBusinessQueryPlan,
    InvalidProtectedValue,
    ProtectedValueBinder,
    ProtectedValueSlots,
    UnsupportedBusinessQueryPlan,
    ValidatedBusinessQueryPlan,
)
from agent_runtime.business.settings import BusinessConfigurationSnapshot
from agent_runtime.core.registry import FrozenCapabilityRegistry, InvalidValidatedCall
from agent_runtime.graph.state import ActionSelectionDecision, ActionSelectionInput
from agent_runtime.model.context import ModelCallContextAccessor
from agent_runtime.model.contracts import (
    BusinessQueryPlanGenerator,
    BusinessQueryPlanTaskInput,
    InvalidModelOutput,
    MissingModelCallContext,
    ModelCallContext,
    ModelInputDenied,
    ModelProviderFailureKind,
    ModelTransportError,
    QuestionEgressDisposition,
)
from agent_runtime.model.input_guard import QuestionEgressGuard


_TERMINAL_STATUSES = frozenset(
    {
        CapabilityStatus.UNSUPPORTED,
        CapabilityStatus.INVALID_ARGUMENT,
        CapabilityStatus.FORBIDDEN,
        CapabilityStatus.TIMEOUT,
        CapabilityStatus.DOWNSTREAM_FAILURE,
        CapabilityStatus.INTERNAL_FAILURE,
    }
)


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessPlanningInput:
    request_id: str
    minimized_question: str
    protected_slots: ProtectedValueSlots
    config_snapshot: BusinessConfigurationSnapshot
    model_context: ModelCallContext
    cancellation: CancellationSignal


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessPlanningDecision:
    candidate: ActionCandidate | None
    status: CapabilityStatus | None
    failure_code: str | None
    config_snapshot_id: str

    def __post_init__(self) -> None:
        candidate_result = (
            isinstance(self.candidate, ActionCandidate)
            and self.status is None
            and self.failure_code is None
        )
        terminal_result = (
            self.candidate is None
            and self.status in _TERMINAL_STATUSES
            and isinstance(self.failure_code, str)
            and bool(self.failure_code)
        )
        if not candidate_result and not terminal_result:
            raise ValueError("business.invalid_planning_decision")
        if not isinstance(self.config_snapshot_id, str) or not self.config_snapshot_id:
            raise ValueError("business.invalid_planning_decision")


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessQueryPlanRuntimeBindings:
    definitions: tuple[BusinessActionDefinition[Any, Any, Any, Any], ...]
    snapshot: BusinessConfigurationSnapshot
    planner_catalog: BusinessPlannerCatalog
    generator: BusinessQueryPlanGenerator
    context_accessor: ModelCallContextAccessor
    protected_value_extractor: ProtectedValueExtractor
    guard: QuestionEgressGuard

    def __post_init__(self) -> None:
        object.__setattr__(self, "definitions", tuple(self.definitions))


class FallbackActionSelectionNode(Protocol):
    async def __call__(self, input: ActionSelectionInput) -> ActionSelectionDecision: ...


class BusinessQueryPlanningNode:
    __slots__ = (
        "_binder",
        "_catalog",
        "_decoder",
        "_generator",
        "_registry",
        "_validator",
    )

    def __init__(
        self,
        *,
        generator: BusinessQueryPlanGenerator,
        decoder: BusinessQueryPlanDecoder,
        validator: BusinessQueryPlanValidator,
        binder: ProtectedValueBinder,
        registry: FrozenCapabilityRegistry,
        planner_catalog: BusinessPlannerCatalog,
    ) -> None:
        self._generator = generator
        self._decoder = decoder
        self._validator = validator
        self._binder = binder
        self._registry = registry
        self._catalog = planner_catalog

    async def __call__(self, input: BusinessPlanningInput) -> BusinessPlanningDecision:
        snapshot_id = input.config_snapshot.snapshot_id
        if (
            input.request_id != input.model_context.request_id
            or input.request_id != input.protected_slots.request_id
            or snapshot_id != self._catalog.snapshot_id
        ):
            return _terminal(
                CapabilityStatus.INTERNAL_FAILURE,
                "business.plan_snapshot_mismatch",
                snapshot_id,
            )
        if _planning_timed_out(input):
            return _terminal(
                CapabilityStatus.TIMEOUT,
                "business.plan_model_timeout",
                snapshot_id,
            )
        try:
            payload = await self._generator.generate(
                BusinessQueryPlanTaskInput(
                    minimized_question=input.minimized_question,
                    catalog=self._catalog.payload,
                    catalog_snapshot_id=self._catalog.snapshot_id,
                ),
                context=input.model_context,
            )
            if _planning_timed_out(input):
                return _terminal(
                    CapabilityStatus.TIMEOUT,
                    "business.plan_model_timeout",
                    snapshot_id,
                )
            decoded = self._decoder.decode(payload)
            validated = self._validator.validate(
                decoded,
                snapshot=input.config_snapshot,
            )
            if isinstance(validated, UnsupportedBusinessQueryPlan):
                if validated.config_snapshot_id != snapshot_id:
                    return _terminal(
                        CapabilityStatus.INTERNAL_FAILURE,
                        "business.plan_snapshot_mismatch",
                        snapshot_id,
                    )
                return _terminal(
                    CapabilityStatus.UNSUPPORTED,
                    "business.plan_unsupported",
                    snapshot_id,
                )
            if validated.config_snapshot_id != snapshot_id:
                return _terminal(
                    CapabilityStatus.INTERNAL_FAILURE,
                    "business.plan_snapshot_mismatch",
                    snapshot_id,
                )
            if _planning_timed_out(input):
                return _terminal(
                    CapabilityStatus.TIMEOUT,
                    "business.plan_model_timeout",
                    snapshot_id,
                )
            candidate = self._binder.bind(
                validated,
                slots=input.protected_slots,
                request_id=input.request_id,
            )
            registered = self._registry.resolve(candidate.capability_id)
            if registered is None:
                return _terminal(
                    CapabilityStatus.INTERNAL_FAILURE,
                    "business.plan_registry_mismatch",
                    snapshot_id,
                )
            registered.validate(candidate.arguments)
            return BusinessPlanningDecision(
                candidate=candidate,
                status=None,
                failure_code=None,
                config_snapshot_id=snapshot_id,
            )
        except ModelTransportError as exc:
            if exc.kind is ModelProviderFailureKind.PROVIDER_TIMEOUT:
                return _terminal(CapabilityStatus.TIMEOUT, "business.plan_model_timeout", snapshot_id)
            if exc.kind is ModelProviderFailureKind.INPUT_DENIED:
                return _terminal(CapabilityStatus.FORBIDDEN, "business.plan_model_denied", snapshot_id)
            if exc.kind is ModelProviderFailureKind.INVALID_OUTPUT:
                return _terminal(CapabilityStatus.INVALID_ARGUMENT, "business.plan_invalid", snapshot_id)
            return _terminal(CapabilityStatus.DOWNSTREAM_FAILURE, "business.plan_model_failure", snapshot_id)
        except ModelInputDenied:
            return _terminal(CapabilityStatus.FORBIDDEN, "business.plan_model_denied", snapshot_id)
        except InvalidProtectedValue:
            return _terminal(
                CapabilityStatus.INVALID_ARGUMENT,
                "business.protected_value_invalid",
                snapshot_id,
            )
        except (InvalidModelOutput, InvalidBusinessQueryPlan, InvalidCapabilityArguments):
            return _terminal(CapabilityStatus.INVALID_ARGUMENT, "business.plan_invalid", snapshot_id)
        except InvalidValidatedCall:
            return _terminal(CapabilityStatus.INTERNAL_FAILURE, "business.plan_registry_mismatch", snapshot_id)
        except (TypeError, ValueError):
            return _terminal(CapabilityStatus.INTERNAL_FAILURE, "business.plan_internal_failure", snapshot_id)


class BusinessAwareActionSelectionNode:
    __slots__ = (
        "_all_descriptors",
        "_bindings",
        "_fallback_descriptors",
        "_fallback_selector",
        "_planning_node",
    )

    def __init__(
        self,
        *,
        all_descriptors: tuple[CapabilityDescriptor, ...],
        fallback_descriptors: tuple[CapabilityDescriptor, ...],
        fallback_selector: FallbackActionSelectionNode,
        planning_node: BusinessQueryPlanningNode,
        bindings: BusinessQueryPlanRuntimeBindings,
    ) -> None:
        self._all_descriptors = all_descriptors
        self._fallback_descriptors = fallback_descriptors
        self._fallback_selector = fallback_selector
        self._planning_node = planning_node
        self._bindings = bindings

    async def __call__(
        self,
        input: ActionSelectionInput,
    ) -> ActionSelectionDecision | BusinessPlanningDecision:
        if input.descriptors != self._all_descriptors:
            return _terminal(
                CapabilityStatus.INTERNAL_FAILURE,
                "business.plan_registry_mismatch",
                self._bindings.snapshot.snapshot_id,
            )
        if not self._bindings.guard.is_business_question(input.question):
            return await self._fallback_selector(
                ActionSelectionInput(
                    question=input.question,
                    descriptors=self._fallback_descriptors,
                    cancellation=input.cancellation,
                )
            )
        if input.cancellation is None:
            return _terminal(
                CapabilityStatus.INTERNAL_FAILURE,
                "business.plan_context_missing",
                self._bindings.snapshot.snapshot_id,
            )
        if input.cancellation.is_cancelled():
            return _terminal(
                CapabilityStatus.TIMEOUT,
                "business.plan_model_timeout",
                self._bindings.snapshot.snapshot_id,
            )
        try:
            context = self._bindings.context_accessor.require_current()
            slots = self._bindings.protected_value_extractor.extract(
                input.question,
                request_id=context.request_id,
            )
        except MissingModelCallContext:
            return _terminal(
                CapabilityStatus.INTERNAL_FAILURE,
                "business.plan_context_missing",
                self._bindings.snapshot.snapshot_id,
            )
        except (InvalidProtectedValue, ValueError):
            return _terminal(
                CapabilityStatus.INVALID_ARGUMENT,
                "business.protected_value_invalid",
                self._bindings.snapshot.snapshot_id,
            )
        egress = self._bindings.guard.evaluate_business(
            input.question,
            protected_values=slots.values,
        )
        if egress.disposition is QuestionEgressDisposition.DENIED or egress.minimized_question is None:
            return _terminal(
                CapabilityStatus.FORBIDDEN,
                "business.plan_input_denied",
                self._bindings.snapshot.snapshot_id,
            )
        return await self._planning_node(
            BusinessPlanningInput(
                request_id=context.request_id,
                minimized_question=egress.minimized_question,
                protected_slots=slots,
                config_snapshot=self._bindings.snapshot,
                model_context=context,
                cancellation=input.cancellation,
            )
        )


def validate_business_query_plan_composition(
    *,
    registry: FrozenCapabilityRegistry,
    bindings: BusinessQueryPlanRuntimeBindings,
) -> tuple[str, ...]:
    definitions = bindings.definitions
    by_id = {item.descriptor.capability_id: item for item in definitions}
    if not definitions or len(by_id) != len(definitions):
        raise ValueError("business.plan_composition_invalid")
    if any(item.local_action_resolver is not None or not item.query_fields for item in definitions):
        raise ValueError("business.plan_composition_invalid")
    settings = dict(bindings.snapshot.actions)
    if len(settings) != len(bindings.snapshot.actions):
        raise ValueError("business.plan_composition_invalid")
    enabled_ids = tuple(sorted(capability_id for capability_id, value in settings.items() if value.enabled))
    if not enabled_ids or set(settings) != set(by_id):
        raise ValueError("business.plan_composition_invalid")
    if bindings.planner_catalog.snapshot_id != bindings.snapshot.snapshot_id:
        raise ValueError("business.plan_composition_invalid")
    try:
        expected_catalog = build_business_planner_catalog(definitions, bindings.snapshot)
    except ValueError:
        raise ValueError("business.plan_composition_invalid") from None
    if bindings.planner_catalog != expected_catalog:
        raise ValueError("business.plan_composition_invalid")
    actions = bindings.planner_catalog.payload.get("actions")
    if not isinstance(actions, tuple):
        raise ValueError("business.plan_composition_invalid")
    catalog_pairs: list[tuple[str, str]] = []
    for action in actions:
        if not isinstance(action, Mapping):
            raise ValueError("business.plan_composition_invalid")
        action_id = action.get("action")
        domain_id = action.get("domain")
        if not isinstance(action_id, str) or not isinstance(domain_id, str):
            raise ValueError("business.plan_composition_invalid")
        catalog_pairs.append((domain_id, action_id))
    expected_pairs = tuple(
        sorted(
            (str(by_id[action_id].domain_id), action_id)
            for action_id in enabled_ids
        )
    )
    descriptor_by_id = {
        descriptor.capability_id: descriptor
        for descriptor in registry.descriptors()
    }
    if (
        tuple(sorted(catalog_pairs)) != expected_pairs
        or len(catalog_pairs) != len(enabled_ids)
        or any(not registry.contains(item) for item in enabled_ids)
        or any(
            descriptor_by_id.get(item) != by_id[item].descriptor
            for item in enabled_ids
        )
    ):
        raise ValueError("business.plan_composition_invalid")
    return enabled_ids


def _terminal(
    status: CapabilityStatus,
    code: str,
    snapshot_id: str,
) -> BusinessPlanningDecision:
    return BusinessPlanningDecision(
        candidate=None,
        status=status,
        failure_code=code,
        config_snapshot_id=snapshot_id,
    )


def _planning_timed_out(input: BusinessPlanningInput) -> bool:
    return (
        input.cancellation.is_cancelled()
        or asyncio.get_running_loop().time() >= input.model_context.deadline_monotonic
    )
