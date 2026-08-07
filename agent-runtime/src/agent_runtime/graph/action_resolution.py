from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Mapping, Protocol

from agent_runtime.capability_api.action_resolution import (
    LocalActionInvalidReason,
    LocalActionResolution,
    LocalActionResolutionKind,
    LocalActionResolver,
)
from agent_runtime.capability_api.contracts import ActionCandidate, CapabilityDescriptor
from agent_runtime.graph.state import (
    ActionSelectionDecision,
    ActionSelectionDecisionKind,
    ActionSelectionInput,
    ActionSelectionInvalidCode,
    ModelNodeFailure,
    ModelNodeFailureKind,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class CapabilitySelectionInput:
    question: str
    descriptors: tuple[CapabilityDescriptor, ...]


class CapabilitySelectionDecisionKind(StrEnum):
    CANDIDATE = "candidate"
    UNSUPPORTED = "unsupported"
    FAILURE = "failure"


@dataclass(frozen=True, slots=True, kw_only=True)
class CapabilitySelectionDecision:
    kind: CapabilitySelectionDecisionKind
    capability_id: str | None = None
    failure: ModelNodeFailure | None = None

    def __post_init__(self) -> None:
        valid = (
            (
                self.kind is CapabilitySelectionDecisionKind.CANDIDATE
                and isinstance(self.capability_id, str)
                and bool(self.capability_id)
                and self.failure is None
            )
            or (
                self.kind is CapabilitySelectionDecisionKind.UNSUPPORTED
                and self.capability_id is None
                and self.failure is None
            )
            or (
                self.kind is CapabilitySelectionDecisionKind.FAILURE
                and self.capability_id is None
                and isinstance(self.failure, ModelNodeFailure)
            )
        )
        if not valid:
            raise ValueError("core.invalid_model_node_decision")


class CapabilitySelectionNode(Protocol):
    async def __call__(self, input: CapabilitySelectionInput) -> CapabilitySelectionDecision: ...


class InvalidActionResolution(RuntimeError):
    __slots__ = ("code",)

    code: Literal["core.invalid_action_resolution"]

    def __init__(self) -> None:
        super().__init__()
        self.code = "core.invalid_action_resolution"


class HybridActionSelectionNode:
    __slots__ = ("_capability_selector", "_descriptor_by_id", "_descriptors", "_resolver_bindings")

    def __init__(
        self,
        *,
        descriptors: tuple[CapabilityDescriptor, ...],
        resolvers: tuple[LocalActionResolver, ...],
        capability_selector: CapabilitySelectionNode,
    ) -> None:
        self._descriptors = tuple(descriptors)
        self._descriptor_by_id = {descriptor.capability_id: descriptor for descriptor in self._descriptors}
        resolver_bindings: list[tuple[str, LocalActionResolver]] = []
        resolver_ids: set[str] = set()
        for resolver in resolvers:
            try:
                capability_id = resolver.capability_id
            except Exception:
                raise ValueError("runtime.invalid_local_action_resolver") from None
            if (
                not isinstance(capability_id, str)
                or capability_id not in self._descriptor_by_id
                or capability_id in resolver_ids
            ):
                raise ValueError("runtime.invalid_local_action_resolver")
            resolver_ids.add(capability_id)
            resolver_bindings.append((capability_id, resolver))
        self._resolver_bindings = tuple(sorted(resolver_bindings, key=lambda item: item[0]))
        self._capability_selector = capability_selector

    async def __call__(self, input: ActionSelectionInput) -> ActionSelectionDecision:
        if input.descriptors != self._descriptors:
            raise InvalidActionResolution() from None

        candidates: list[tuple[str, LocalActionResolution]] = []
        invalid_reasons: list[LocalActionInvalidReason] = []
        for capability_id, resolver in self._resolver_bindings:
            resolution: object | None = None
            try:
                if resolver.capability_id != capability_id:
                    resolution = None
                else:
                    resolution = resolver.resolve(input.question)
                    if resolver.capability_id != capability_id:
                        resolution = None
            except Exception:
                resolution = None
            if not isinstance(resolution, LocalActionResolution):
                raise InvalidActionResolution() from None

            if resolution.kind is LocalActionResolutionKind.CANDIDATE:
                candidates.append((capability_id, resolution))
            elif resolution.kind is LocalActionResolutionKind.INVALID:
                if not isinstance(resolution.reason, LocalActionInvalidReason):
                    raise InvalidActionResolution() from None
                invalid_reasons.append(resolution.reason)
            elif resolution.kind is not LocalActionResolutionKind.NO_MATCH:
                raise InvalidActionResolution() from None

        if LocalActionInvalidReason.AMBIGUOUS_INTENT in invalid_reasons or len(candidates) >= 2:
            return _invalid_decision(ActionSelectionInvalidCode.LOCAL_ACTION_AMBIGUOUS)
        if invalid_reasons:
            return _invalid_decision(ActionSelectionInvalidCode.LOCAL_ACTION_INVALID)
        if len(candidates) == 1:
            capability_id, resolution = candidates[0]
            if capability_id not in self._descriptor_by_id or resolution.arguments is None:
                raise InvalidActionResolution() from None
            try:
                candidate = ActionCandidate(capability_id=capability_id, arguments=resolution.arguments)
            except Exception:
                candidate = None
            if candidate is None:
                raise InvalidActionResolution() from None
            return ActionSelectionDecision(
                kind=ActionSelectionDecisionKind.CANDIDATE,
                candidate=candidate,
            )

        try:
            selected_object: object = await self._capability_selector(
                CapabilitySelectionInput(question=input.question, descriptors=self._descriptors)
            )
        except Exception:
            return _model_invalid_output()
        if not isinstance(selected_object, CapabilitySelectionDecision):
            return _model_invalid_output()
        selected = selected_object
        if selected.kind is CapabilitySelectionDecisionKind.UNSUPPORTED:
            return ActionSelectionDecision(kind=ActionSelectionDecisionKind.UNSUPPORTED)
        if selected.kind is CapabilitySelectionDecisionKind.FAILURE and selected.failure is not None:
            return ActionSelectionDecision(
                kind=ActionSelectionDecisionKind.FAILURE,
                failure=selected.failure,
            )
        if selected.kind is not CapabilitySelectionDecisionKind.CANDIDATE or selected.capability_id is None:
            return _model_invalid_output()

        descriptor = self._descriptor_by_id.get(selected.capability_id)
        if descriptor is None:
            return _model_invalid_output()
        if not is_exact_empty_execution_schema(descriptor.argument_schema):
            return _invalid_decision(ActionSelectionInvalidCode.LOCAL_ARGUMENTS_REQUIRED)
        return ActionSelectionDecision(
            kind=ActionSelectionDecisionKind.CANDIDATE,
            candidate=ActionCandidate(capability_id=descriptor.capability_id, arguments={}),
        )


def is_exact_empty_execution_schema(schema: Mapping[str, object]) -> bool:
    return (
        set(schema) == {"type", "properties", "required", "additionalProperties"}
        and schema.get("type") == "object"
        and isinstance(schema.get("properties"), Mapping)
        and not schema["properties"]
        and schema.get("required") == ()
        and schema.get("additionalProperties") is False
    )


def _invalid_decision(code: ActionSelectionInvalidCode) -> ActionSelectionDecision:
    return ActionSelectionDecision(
        kind=ActionSelectionDecisionKind.INVALID_ARGUMENT,
        invalid_code=code,
    )


def _model_invalid_output() -> ActionSelectionDecision:
    return ActionSelectionDecision(
        kind=ActionSelectionDecisionKind.FAILURE,
        failure=ModelNodeFailure(kind=ModelNodeFailureKind.INVALID_OUTPUT),
    )
