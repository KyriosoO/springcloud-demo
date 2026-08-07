from __future__ import annotations

from typing import cast

import pytest

from agent_runtime.capability_api.action_resolution import (
    LocalActionInvalidReason,
    LocalActionResolution,
    LocalActionResolutionKind,
)
from agent_runtime.capability_api.contracts import CapabilityDescriptor, CapabilityStatus
from agent_runtime.graph.action_resolution import (
    CapabilitySelectionDecision,
    CapabilitySelectionDecisionKind,
    CapabilitySelectionInput,
    HybridActionSelectionNode,
    InvalidActionResolution,
)
from agent_runtime.graph.nodes import select_action_node
from agent_runtime.graph.state import (
    ActionSelectionDecision,
    ActionSelectionDecisionKind,
    ActionSelectionInput,
    ActionSelectionInvalidCode,
    ModelNodeFailure,
    ModelNodeFailureKind,
)
from tests.helpers import descriptor


class ResolverStub:
    def __init__(
        self,
        capability_id: str,
        resolution: LocalActionResolution,
        *,
        calls: list[str] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._capability_id = capability_id
        self.resolution = resolution
        self.calls = calls if calls is not None else []
        self.error = error

    @property
    def capability_id(self) -> str:
        return self._capability_id

    def resolve(self, question: str) -> LocalActionResolution:
        del question
        self.calls.append(self._capability_id)
        if self.error is not None:
            raise self.error
        return self.resolution


class SelectorStub:
    def __init__(self, decision: object) -> None:
        self.decision = decision
        self.calls = 0
        self.inputs: list[CapabilitySelectionInput] = []

    async def __call__(self, input: CapabilitySelectionInput) -> CapabilitySelectionDecision:
        self.calls += 1
        self.inputs.append(input)
        return cast(CapabilitySelectionDecision, self.decision)


def _no_match() -> LocalActionResolution:
    return LocalActionResolution(kind=LocalActionResolutionKind.NO_MATCH)


def _candidate(value: str) -> LocalActionResolution:
    return LocalActionResolution(
        kind=LocalActionResolutionKind.CANDIDATE,
        arguments={"value": value},
    )


def _invalid(reason: LocalActionInvalidReason) -> LocalActionResolution:
    return LocalActionResolution(kind=LocalActionResolutionKind.INVALID, reason=reason)


def _empty_descriptor(capability_id: str = "knowledge.query") -> CapabilityDescriptor:
    base = descriptor(capability_id)
    return CapabilityDescriptor(
        capability_id=base.capability_id,
        api_version=base.api_version,
        kind=base.kind,
        display_name=base.display_name,
        description=base.description,
        aliases=base.aliases,
        argument_schema={
            "type": "object",
            "properties": {},
            "required": (),
            "additionalProperties": False,
        },
    )


def _hybrid(
    descriptors: tuple[CapabilityDescriptor, ...],
    resolvers: tuple[ResolverStub, ...],
    selector: SelectorStub,
) -> HybridActionSelectionNode:
    return HybridActionSelectionNode(
        descriptors=descriptors,
        resolvers=resolvers,
        capability_selector=selector,
    )


@pytest.mark.asyncio
async def test_resolvers_run_in_canonical_order_and_single_candidate_skips_model() -> None:
    descriptors = (descriptor("alpha.query"), descriptor("beta.query"))
    calls: list[str] = []
    selector = SelectorStub(CapabilitySelectionDecision(kind=CapabilitySelectionDecisionKind.UNSUPPORTED))
    node = _hybrid(
        descriptors,
        (
            ResolverStub("beta.query", _candidate("beta"), calls=calls),
            ResolverStub("alpha.query", _no_match(), calls=calls),
        ),
        selector,
    )

    decision = await node(ActionSelectionInput(question="bounded question", descriptors=descriptors))

    assert calls == ["alpha.query", "beta.query"]
    assert decision.kind is ActionSelectionDecisionKind.CANDIDATE
    assert decision.candidate is not None
    assert decision.candidate.capability_id == "beta.query"
    assert decision.candidate.arguments == {"value": "beta"}
    assert selector.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("resolutions", "expected"),
    [
        ((_invalid(LocalActionInvalidReason.MALFORMED_VALUE),), ActionSelectionInvalidCode.LOCAL_ACTION_INVALID),
        (
            (
                _invalid(LocalActionInvalidReason.MALFORMED_VALUE),
                _invalid(LocalActionInvalidReason.AMBIGUOUS_INTENT),
            ),
            ActionSelectionInvalidCode.LOCAL_ACTION_AMBIGUOUS,
        ),
        (
            (_candidate("alpha"), _candidate("beta"), _invalid(LocalActionInvalidReason.MISSING_REQUIRED)),
            ActionSelectionInvalidCode.LOCAL_ACTION_AMBIGUOUS,
        ),
    ],
)
async def test_local_invalid_precedence_is_fixed(
    resolutions: tuple[LocalActionResolution, ...],
    expected: ActionSelectionInvalidCode,
) -> None:
    descriptors = tuple(descriptor(f"cap{index}.query") for index in range(len(resolutions)))
    selector = SelectorStub(CapabilitySelectionDecision(kind=CapabilitySelectionDecisionKind.UNSUPPORTED))
    resolvers = tuple(
        ResolverStub(item.capability_id, resolution)
        for item, resolution in zip(descriptors, resolutions, strict=True)
    )

    decision = await _hybrid(descriptors, resolvers, selector)(
        ActionSelectionInput(question="bounded question", descriptors=descriptors)
    )

    assert decision.kind is ActionSelectionDecisionKind.INVALID_ARGUMENT
    assert decision.invalid_code is expected
    assert selector.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason",
    [
        LocalActionInvalidReason.MISSING_REQUIRED,
        LocalActionInvalidReason.DUPLICATE_ARGUMENT,
        LocalActionInvalidReason.CONFLICTING_ARGUMENT,
        LocalActionInvalidReason.UNSUPPORTED_CLAUSE,
        LocalActionInvalidReason.MALFORMED_VALUE,
    ],
)
async def test_each_non_ambiguous_invalid_reason_maps_to_local_action_invalid(
    reason: LocalActionInvalidReason,
) -> None:
    descriptors = (descriptor("employee.detail"),)
    selector = SelectorStub(CapabilitySelectionDecision(kind=CapabilitySelectionDecisionKind.UNSUPPORTED))
    node = _hybrid(descriptors, (ResolverStub("employee.detail", _invalid(reason)),), selector)

    decision = await node(ActionSelectionInput(question="employee", descriptors=descriptors))

    assert decision.kind is ActionSelectionDecisionKind.INVALID_ARGUMENT
    assert decision.invalid_code is ActionSelectionInvalidCode.LOCAL_ACTION_INVALID
    assert selector.calls == 0


@pytest.mark.asyncio
async def test_zero_local_match_calls_id_only_selector_once_and_binds_empty_arguments() -> None:
    descriptors = (_empty_descriptor(),)
    selector = SelectorStub(
        CapabilitySelectionDecision(
            kind=CapabilitySelectionDecisionKind.CANDIDATE,
            capability_id="knowledge.query",
        )
    )
    node = _hybrid(descriptors, (), selector)

    decision = await node(ActionSelectionInput(question="tax policy", descriptors=descriptors))

    assert decision.kind is ActionSelectionDecisionKind.CANDIDATE
    assert decision.candidate is not None
    assert decision.candidate.capability_id == "knowledge.query"
    assert decision.candidate.arguments == {}
    assert selector.calls == 1
    assert selector.inputs[0] == CapabilitySelectionInput(question="tax policy", descriptors=descriptors)


@pytest.mark.asyncio
async def test_model_selected_non_empty_action_requires_local_arguments() -> None:
    descriptors = (descriptor("employee.detail"),)
    selector = SelectorStub(
        CapabilitySelectionDecision(
            kind=CapabilitySelectionDecisionKind.CANDIDATE,
            capability_id="employee.detail",
        )
    )
    node = _hybrid(descriptors, (ResolverStub("employee.detail", _no_match()),), selector)

    decision = await node(ActionSelectionInput(question="employee", descriptors=descriptors))

    assert decision.kind is ActionSelectionDecisionKind.INVALID_ARGUMENT
    assert decision.invalid_code is ActionSelectionInvalidCode.LOCAL_ARGUMENTS_REQUIRED
    assert selector.calls == 1


@pytest.mark.asyncio
async def test_protocol_violation_stops_remaining_resolvers_and_maps_without_detail() -> None:
    descriptors = (descriptor("alpha.query"), descriptor("beta.query"))
    calls: list[str] = []
    selector = SelectorStub(CapabilitySelectionDecision(kind=CapabilitySelectionDecisionKind.UNSUPPORTED))
    node = _hybrid(
        descriptors,
        (
            ResolverStub("alpha.query", _no_match(), calls=calls, error=RuntimeError("secret detail")),
            ResolverStub("beta.query", _candidate("beta"), calls=calls),
        ),
        selector,
    )

    with pytest.raises(InvalidActionResolution) as captured:
        await node(ActionSelectionInput(question="secret question", descriptors=descriptors))

    assert captured.value.code == "core.invalid_action_resolution"
    assert captured.value.args == ()
    assert str(captured.value) == ""
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert calls == ["alpha.query"]
    assert selector.calls == 0

    update = await select_action_node(
        {"question": "secret question"},
        descriptors=descriptors,
        selector=node,
    )
    outcome = update["final_outcome"]
    assert outcome.status is CapabilityStatus.INTERNAL_FAILURE
    assert outcome.failure is not None
    assert outcome.failure.code == "core.invalid_action_resolution"


@pytest.mark.asyncio
async def test_malformed_candidate_arguments_are_a_context_free_protocol_violation() -> None:
    malformed = object.__new__(LocalActionResolution)
    object.__setattr__(malformed, "kind", LocalActionResolutionKind.CANDIDATE)
    object.__setattr__(malformed, "arguments", {"unsafe": object()})
    object.__setattr__(malformed, "reason", None)
    descriptors = (descriptor("employee.detail"),)
    selector = SelectorStub(CapabilitySelectionDecision(kind=CapabilitySelectionDecisionKind.UNSUPPORTED))
    node = _hybrid(descriptors, (ResolverStub("employee.detail", malformed),), selector)

    with pytest.raises(InvalidActionResolution) as captured:
        await node(ActionSelectionInput(question="employee", descriptors=descriptors))

    assert captured.value.args == ()
    assert captured.value.__context__ is None
    assert selector.calls == 0


@pytest.mark.parametrize(
    "values",
    [
        {
            "kind": ActionSelectionDecisionKind.CANDIDATE,
            "candidate": object(),
        },
        {
            "kind": ActionSelectionDecisionKind.FAILURE,
            "failure": object(),
        },
    ],
)
def test_action_selection_decision_rejects_runtime_type_smuggling(values: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="core.invalid_model_node_decision"):
        ActionSelectionDecision(**values)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_unknown_or_malformed_model_decision_is_invalid_output() -> None:
    descriptors = (_empty_descriptor(),)
    for model_decision in (
        CapabilitySelectionDecision(
            kind=CapabilitySelectionDecisionKind.CANDIDATE,
            capability_id="knowledge.alias",
        ),
        object(),
    ):
        selector = SelectorStub(model_decision)
        decision = await _hybrid(descriptors, (), selector)(
            ActionSelectionInput(question="tax policy", descriptors=descriptors)
        )

        assert decision.kind is ActionSelectionDecisionKind.FAILURE
        assert decision.failure == ModelNodeFailure(kind=ModelNodeFailureKind.INVALID_OUTPUT)
