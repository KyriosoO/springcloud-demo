from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_runtime.bootstrap import RuntimeCompositionRoot
from agent_runtime.capability_api.action_resolution import LocalActionResolution, LocalActionResolutionKind
from agent_runtime.capability_api.contracts import CapabilityExecutionContext, CapabilityResult, CapabilityStatus
from agent_runtime.graph.action_resolution import (
    CapabilitySelectionDecision,
    CapabilitySelectionDecisionKind,
)
from agent_runtime.graph.state import (
    AnswerGenerationDecision,
    AnswerGenerationDecisionKind,
)
from agent_runtime.settings import CoreRuntimeSettings
from tests.helpers import (
    FixedAnswerGenerator,
    FixedLocalActionResolver,
    FixedSelector,
    Provider,
    QueryInput,
    QueryValidator,
    descriptor,
    registration,
    scope,
    success_result,
)
from agent_runtime.capability_api.contracts import CapabilityRegistrationCandidate


@dataclass(slots=True)
class CountingDecorator:
    delegate: object
    calls: int = 0

    async def handle(self, input: QueryInput, context: CapabilityExecutionContext) -> CapabilityResult:
        self.calls += 1
        method = getattr(self.delegate, "handle")
        result = await method(input, context)
        assert isinstance(result, CapabilityResult)
        return result


class SimulatedHandler:
    async def handle(self, input: QueryInput, context: CapabilityExecutionContext) -> CapabilityResult:
        del input, context
        return success_result()


@pytest.mark.asyncio
async def test_new_simulated_capability_only_changes_provider_and_root_fixture() -> None:
    decorator = CountingDecorator(SimulatedHandler())
    simulated = CapabilityRegistrationCandidate(
        descriptor=descriptor("simulated.query"),
        enabled=True,
        argument_validator=QueryValidator(),
        handler=decorator,
    )
    selector = FixedSelector(
        CapabilitySelectionDecision(
            kind=CapabilitySelectionDecisionKind.CANDIDATE,
            capability_id="simulated.query",
        )
    )
    invoker = RuntimeCompositionRoot.build(
        settings=CoreRuntimeSettings(),
        providers=(Provider(simulated),),
        capability_selector=selector,
        answer_generator=FixedAnswerGenerator(
            AnswerGenerationDecision(
                kind=AnswerGenerationDecisionKind.ANSWER,
                answer_text="unused",
            )
        ),
        local_action_resolvers=(
            FixedLocalActionResolver(
                "simulated.query",
                LocalActionResolution(
                    kind=LocalActionResolutionKind.CANDIDATE,
                    arguments={"value": "x"},
                ),
            ),
        ),
    )

    outcome = await invoker.ainvoke(question="test question", scope=scope())

    assert outcome.status is CapabilityStatus.SUCCESS
    assert outcome.capability_id == "simulated.query"
    assert decorator.calls == 1


def test_existing_registration_factory_remains_domain_neutral() -> None:
    value = registration(enabled=False)

    assert value.descriptor.capability_id == "test.query"
