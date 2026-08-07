from __future__ import annotations

import pytest

from agent_runtime.bootstrap import RuntimeCompositionRoot
from agent_runtime.capability_api.action_resolution import (
    LocalActionResolution,
    LocalActionResolutionKind,
)
from agent_runtime.capability_api.contracts import (
    CapabilityResult,
    CapabilityStatus,
    EgressDisposition,
    ModelEgressResult,
)
from agent_runtime.graph.action_resolution import (
    CapabilitySelectionDecision,
    CapabilitySelectionDecisionKind,
)
from agent_runtime.graph.state import (
    AnswerGenerationDecision,
    AnswerGenerationDecisionKind,
    ModelNodeFailure,
    ModelNodeFailureKind,
)
from agent_runtime.settings import CoreRuntimeSettings
from tests.helpers import (
    FixedAnswerGenerator,
    FixedLocalActionResolver,
    FixedSelector,
    Provider,
    QueryValidator,
    ResultHandler,
    registration,
    scope,
    success_result,
)


def _selector() -> FixedSelector:
    return FixedSelector(
        CapabilitySelectionDecision(
            kind=CapabilitySelectionDecisionKind.CANDIDATE,
            capability_id="test.query",
        )
    )


def _resolver(*, matched: bool = True) -> FixedLocalActionResolver:
    resolution = LocalActionResolution(
        kind=LocalActionResolutionKind.CANDIDATE if matched else LocalActionResolutionKind.NO_MATCH,
        arguments={"value": "x"} if matched else None,
    )
    return FixedLocalActionResolver("test.query", resolution)


def _answer() -> FixedAnswerGenerator:
    return FixedAnswerGenerator(
        AnswerGenerationDecision(
            kind=AnswerGenerationDecisionKind.ANSWER,
            answer_text="safe answer",
        )
    )


@pytest.mark.asyncio
async def test_empty_registry_short_circuits_selector_and_handler() -> None:
    selector = _selector()
    answer = _answer()
    invoker = RuntimeCompositionRoot.build(
        settings=CoreRuntimeSettings(),
        providers=(Provider(registration(enabled=False)),),
        capability_selector=selector,
        answer_generator=answer,
    )

    outcome = await invoker.ainvoke(question="test question", scope=scope())

    assert outcome.status is CapabilityStatus.UNSUPPORTED
    assert outcome.capability_id is None
    assert selector.calls == 0
    assert answer.calls == 0


@pytest.mark.asyncio
async def test_allowed_payload_is_the_only_answer_model_input() -> None:
    handler = ResultHandler(success_result(disposition=EgressDisposition.ALLOWED))
    selector = _selector()
    answer = _answer()
    execution_scope = scope()
    invoker = RuntimeCompositionRoot.build(
        settings=CoreRuntimeSettings(),
        providers=(Provider(registration(validator=QueryValidator(), handler=handler)),),
        capability_selector=selector,
        answer_generator=answer,
        local_action_resolvers=(_resolver(),),
    )

    outcome = await invoker.ainvoke(question="test question", scope=execution_scope)

    assert outcome.status is CapabilityStatus.SUCCESS
    assert outcome.capability_id == "test.query"
    assert outcome.answer_text == "safe answer"
    assert outcome.user_result is None
    assert answer.calls == 1
    assert answer.inputs[0].safe_payload == {"fact": "safe"}
    assert not hasattr(answer.inputs[0], "domain_result")
    assert not hasattr(answer.inputs[0], "execution_scope")
    assert handler.contexts == [execution_scope.context]


@pytest.mark.asyncio
async def test_denied_success_returns_authorized_local_result_without_model() -> None:
    handler = ResultHandler(success_result(disposition=EgressDisposition.DENIED))
    answer = _answer()
    invoker = RuntimeCompositionRoot.build(
        settings=CoreRuntimeSettings(),
        providers=(Provider(registration(validator=QueryValidator(), handler=handler)),),
        capability_selector=_selector(),
        answer_generator=answer,
        local_action_resolvers=(_resolver(),),
    )

    outcome = await invoker.ainvoke(question="test question", scope=scope())

    assert outcome.status is CapabilityStatus.SUCCESS
    assert outcome.user_result == {"value": "result"}
    assert answer.calls == 0


@pytest.mark.asyncio
async def test_no_result_keeps_status_and_optional_coverage_metadata() -> None:
    result = CapabilityResult(
        status=CapabilityStatus.NO_RESULT,
        domain_result={"coverage": "bounded"},
        egress=ModelEgressResult(disposition=EgressDisposition.NOT_APPLICABLE),
        failure=None,
    )
    answer = _answer()
    invoker = RuntimeCompositionRoot.build(
        settings=CoreRuntimeSettings(),
        providers=(Provider(registration(validator=QueryValidator(), handler=ResultHandler(result))),),
        capability_selector=_selector(),
        answer_generator=answer,
        local_action_resolvers=(_resolver(),),
    )

    outcome = await invoker.ainvoke(question="test question", scope=scope())

    assert outcome.status is CapabilityStatus.NO_RESULT
    assert outcome.user_result == {"coverage": "bounded"}
    assert answer.calls == 0


@pytest.mark.asyncio
async def test_selector_failure_has_no_capability_id() -> None:
    selector = FixedSelector(
        CapabilitySelectionDecision(
            kind=CapabilitySelectionDecisionKind.FAILURE,
            failure=ModelNodeFailure(kind=ModelNodeFailureKind.PROVIDER_TIMEOUT),
        )
    )
    handler = ResultHandler(success_result())
    invoker = RuntimeCompositionRoot.build(
        settings=CoreRuntimeSettings(),
        providers=(Provider(registration(validator=QueryValidator(), handler=handler)),),
        capability_selector=selector,
        answer_generator=_answer(),
        local_action_resolvers=(_resolver(matched=False),),
    )

    outcome = await invoker.ainvoke(question="test question", scope=scope())

    assert outcome.status is CapabilityStatus.TIMEOUT
    assert outcome.capability_id is None
    assert handler.calls == 0


@pytest.mark.asyncio
async def test_answer_failure_preserves_claimed_capability_id_and_drops_payload() -> None:
    answer = FixedAnswerGenerator(
        AnswerGenerationDecision(
            kind=AnswerGenerationDecisionKind.FAILURE,
            failure=ModelNodeFailure(kind=ModelNodeFailureKind.PROVIDER_FAILURE),
        )
    )
    invoker = RuntimeCompositionRoot.build(
        settings=CoreRuntimeSettings(),
        providers=(
            Provider(
                registration(
                    validator=QueryValidator(),
                    handler=ResultHandler(success_result(disposition=EgressDisposition.ALLOWED)),
                )
            ),
        ),
        capability_selector=_selector(),
        answer_generator=answer,
        local_action_resolvers=(_resolver(),),
    )

    outcome = await invoker.ainvoke(question="test question", scope=scope())

    assert outcome.status is CapabilityStatus.DOWNSTREAM_FAILURE
    assert outcome.capability_id == "test.query"
    assert outcome.user_result is None
    assert outcome.failure is not None and outcome.failure.code == "model.provider_failure"
