from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_runtime.bootstrap import RuntimeCompositionRoot
from agent_runtime.capability_api.action_resolution import LocalActionResolution, LocalActionResolutionKind
from agent_runtime.capability_api.contracts import (
    CapabilityExecutionContext,
    CapabilityRegistrationCandidate,
    CapabilityResult,
    JsonObject,
)
from agent_runtime.graph.action_resolution import (
    CapabilitySelectionDecision,
    CapabilitySelectionDecisionKind,
)
from agent_runtime.graph.state import AnswerGenerationDecision, AnswerGenerationDecisionKind
from agent_runtime.settings import CoreRuntimeSettings
from tests.helpers import (
    FixedAnswerGenerator,
    FixedLocalActionResolver,
    FixedSelector,
    Provider,
    QueryValidator,
    ResultHandler,
    descriptor,
    registration,
    success_result,
)


def _selector(capability_id: str = "test.query") -> FixedSelector:
    return FixedSelector(
        CapabilitySelectionDecision(
            kind=CapabilitySelectionDecisionKind.CANDIDATE,
            capability_id=capability_id,
        )
    )


def _answer() -> FixedAnswerGenerator:
    return FixedAnswerGenerator(
        AnswerGenerationDecision(
            kind=AnswerGenerationDecisionKind.ANSWER,
            answer_text="unused",
        )
    )


def _resolver(capability_id: str = "test.query") -> FixedLocalActionResolver:
    return FixedLocalActionResolver(
        capability_id,
        LocalActionResolution(
            kind=LocalActionResolutionKind.CANDIDATE,
            arguments={"value": "x"},
        ),
    )


def test_non_empty_execution_schema_requires_exactly_one_enabled_resolver() -> None:
    with pytest.raises(ValueError, match="runtime.local_action_resolver_missing"):
        RuntimeCompositionRoot.build(
            settings=CoreRuntimeSettings(),
            providers=(Provider(registration(validator=QueryValidator(), handler=ResultHandler(success_result()))),),
            capability_selector=_selector(),
            answer_generator=_answer(),
        )

    RuntimeCompositionRoot.build(
        settings=CoreRuntimeSettings(),
        providers=(Provider(registration(validator=QueryValidator(), handler=ResultHandler(success_result()))),),
        capability_selector=_selector(),
        answer_generator=_answer(),
        local_action_resolvers=(_resolver(),),
    )


@pytest.mark.parametrize(
    ("providers", "resolvers", "code"),
    [
        (
            (Provider(registration(validator=QueryValidator(), handler=ResultHandler(success_result()))),),
            (_resolver(), _resolver()),
            "runtime.duplicate_local_action_resolver",
        ),
        (
            (Provider(registration(validator=QueryValidator(), handler=ResultHandler(success_result()))),),
            (_resolver("unknown.query"),),
            "runtime.local_action_resolver_not_enabled",
        ),
        (
            (Provider(registration(enabled=False)),),
            (_resolver(),),
            "runtime.local_action_resolver_not_enabled",
        ),
    ],
)
def test_duplicate_unknown_or_disabled_resolver_prevents_readiness(
    providers: tuple[Provider, ...],
    resolvers: tuple[FixedLocalActionResolver, ...],
    code: str,
) -> None:
    with pytest.raises(ValueError, match=code):
        RuntimeCompositionRoot.build(
            settings=CoreRuntimeSettings(),
            providers=providers,
            capability_selector=_selector(),
            answer_generator=_answer(),
            local_action_resolvers=resolvers,
        )


@dataclass(frozen=True, slots=True)
class EmptyInput:
    pass


class EmptyValidator:
    def validate(self, arguments: JsonObject) -> EmptyInput:
        if arguments:
            raise ValueError("test.arguments_not_empty")
        return EmptyInput()


class EmptyHandler:
    async def handle(self, input: EmptyInput, context: CapabilityExecutionContext) -> CapabilityResult:
        del input, context
        return success_result()


def test_exact_empty_execution_schema_can_start_without_resolver() -> None:
    empty = descriptor("knowledge.query")
    empty = type(empty)(
        capability_id=empty.capability_id,
        api_version=empty.api_version,
        kind=empty.kind,
        display_name=empty.display_name,
        description=empty.description,
        aliases=empty.aliases,
        argument_schema={
            "type": "object",
            "properties": {},
            "required": (),
            "additionalProperties": False,
        },
    )
    candidate = CapabilityRegistrationCandidate[EmptyInput](
        descriptor=empty,
        enabled=True,
        argument_validator=EmptyValidator(),
        handler=EmptyHandler(),
    )

    RuntimeCompositionRoot.build(
        settings=CoreRuntimeSettings(),
        providers=(Provider(candidate),),
        capability_selector=_selector("knowledge.query"),
        answer_generator=_answer(),
    )


def test_resolver_list_is_explicit_not_configuration_or_dynamic_discovery() -> None:
    import inspect

    signature = inspect.signature(RuntimeCompositionRoot.build)

    assert "local_action_resolvers" in signature.parameters
    assert signature.parameters["local_action_resolvers"].default == ()
