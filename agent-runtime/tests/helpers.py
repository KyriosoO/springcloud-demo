from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from agent_runtime.capability_api.contracts import (
    ActionCandidate,
    CancellationSource,
    CapabilityDescriptor,
    CapabilityExecutionContext,
    CapabilityKind,
    CapabilityRegistrationCandidate,
    CapabilityResult,
    CapabilityStatus,
    EgressDisposition,
    FailureDetail,
    FailureSource,
    InvalidCapabilityArguments,
    JsonObject,
    ModelEgressResult,
    OpaqueUserToken,
    SubjectType,
)
from agent_runtime.capability_api.action_resolution import LocalActionResolution
from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.graph.action_resolution import (
    CapabilitySelectionDecision,
    CapabilitySelectionInput,
)
from agent_runtime.graph.state import (
    AnswerGenerationDecision,
    AnswerGenerationInput,
)


class ManualCancellationSignal:
    def __init__(self) -> None:
        self._event = asyncio.Event()
        self._source: CancellationSource | None = None

    def cancel(self, source: CancellationSource) -> None:
        if self._source is None:
            self._source = source
            self._event.set()

    def is_cancelled(self) -> bool:
        return self._source is not None

    async def wait_cancelled(self) -> CancellationSource:
        await self._event.wait()
        assert self._source is not None
        return self._source


@dataclass(frozen=True, slots=True)
class QueryInput:
    value: str


class QueryValidator:
    def __init__(self) -> None:
        self.calls = 0

    def validate(self, arguments: JsonObject) -> QueryInput:
        self.calls += 1
        value = arguments.get("value")
        if not isinstance(value, str) or not value:
            raise InvalidCapabilityArguments("test.invalid_value")
        return QueryInput(value=value)


class MutableQueryValidator:
    def validate(self, arguments: JsonObject) -> list[str]:
        value = arguments.get("value")
        return [str(value)]


class ResultHandler:
    def __init__(
        self,
        result: CapabilityResult,
        *,
        release: asyncio.Event | None = None,
        exception: Exception | None = None,
    ) -> None:
        self.result = result
        self.release = release
        self.exception = exception
        self.calls = 0
        self.contexts: list[CapabilityExecutionContext] = []
        self.started = asyncio.Event()

    async def handle(self, input: QueryInput, context: CapabilityExecutionContext) -> CapabilityResult:
        del input
        self.calls += 1
        self.contexts.append(context)
        self.started.set()
        if self.release is not None:
            await self.release.wait()
        if self.exception is not None:
            raise self.exception
        return self.result


class Provider:
    def __init__(self, *candidates: CapabilityRegistrationCandidate[Any]) -> None:
        self._candidates = candidates

    def registrations(self) -> tuple[CapabilityRegistrationCandidate[Any], ...]:
        return self._candidates


class FixedSelector:
    def __init__(self, decision: CapabilitySelectionDecision) -> None:
        self.decision = decision
        self.calls = 0
        self.inputs: list[CapabilitySelectionInput] = []

    async def __call__(self, input: CapabilitySelectionInput) -> CapabilitySelectionDecision:
        self.calls += 1
        self.inputs.append(input)
        return self.decision


class FixedLocalActionResolver:
    def __init__(self, capability_id: str, resolution: LocalActionResolution) -> None:
        self._capability_id = capability_id
        self.resolution = resolution
        self.calls = 0
        self.questions: list[str] = []

    @property
    def capability_id(self) -> str:
        return self._capability_id

    def resolve(self, question: str) -> LocalActionResolution:
        self.calls += 1
        self.questions.append(question)
        return self.resolution


class FixedAnswerGenerator:
    def __init__(self, decision: AnswerGenerationDecision) -> None:
        self.decision = decision
        self.calls = 0
        self.inputs: list[AnswerGenerationInput] = []

    async def __call__(self, input: AnswerGenerationInput) -> AnswerGenerationDecision:
        self.calls += 1
        self.inputs.append(input)
        return self.decision


def descriptor(capability_id: str = "test.query", *, aliases: tuple[str, ...] = ()) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id=capability_id,
        api_version=1,
        kind=CapabilityKind.QUERY,
        display_name="Test query",
        description="Query a bounded local test source.",
        aliases=aliases,
        argument_schema={
            "type": "object",
            "properties": {
                "value": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 64,
                }
            },
            "required": ("value",),
            "additionalProperties": False,
        },
    )


def success_result(
    *,
    disposition: EgressDisposition = EgressDisposition.NOT_APPLICABLE,
) -> CapabilityResult:
    if disposition is EgressDisposition.ALLOWED:
        egress = ModelEgressResult(
            disposition=disposition,
            policy_version="test-v1",
            safe_payload={"fact": "safe"},
        )
    elif disposition is EgressDisposition.DENIED:
        egress = ModelEgressResult(
            disposition=disposition,
            policy_version="test-v1",
            reason_code="policy.denied",
        )
    else:
        egress = ModelEgressResult(disposition=disposition)
    return CapabilityResult(
        status=CapabilityStatus.SUCCESS,
        domain_result={"value": "result"},
        egress=egress,
        failure=None,
    )


def failure_result(
    status: CapabilityStatus = CapabilityStatus.DOWNSTREAM_FAILURE,
    *,
    code: str = "downstream.test_failure",
    source: FailureSource = FailureSource.DOWNSTREAM,
) -> CapabilityResult:
    return CapabilityResult(
        status=status,
        domain_result=None,
        egress=ModelEgressResult(disposition=EgressDisposition.NOT_APPLICABLE),
        failure=FailureDetail(code=code, source=source),
    )


def candidate(capability_id: str = "test.query", value: str = "x") -> ActionCandidate:
    return ActionCandidate(capability_id=capability_id, arguments={"value": value})


def registration(
    *,
    capability_id: str = "test.query",
    enabled: bool = True,
    validator: QueryValidator | None = None,
    handler: ResultHandler | None = None,
    aliases: tuple[str, ...] = (),
) -> CapabilityRegistrationCandidate[QueryInput]:
    return CapabilityRegistrationCandidate(
        descriptor=descriptor(capability_id, aliases=aliases),
        enabled=enabled,
        argument_validator=validator if enabled else None,
        handler=handler if enabled else None,
    )


def scope(
    question: str = "test question",
    *,
    cancellation: ManualCancellationSignal | None = None,
    deadline_monotonic: float | None = None,
) -> RequestExecutionScope:
    signal = cancellation or ManualCancellationSignal()
    if deadline_monotonic is None:
        try:
            deadline_monotonic = asyncio.get_running_loop().time() + 10.0
        except RuntimeError:
            deadline_monotonic = 1_000_000_000.0
    return RequestExecutionScope(
        context=CapabilityExecutionContext(
            request_id="req-1",
            correlation_id="corr-1",
            original_question=question,
            subject_id="user-1",
            subject_type=SubjectType.USER,
            user_token=OpaqueUserToken.from_raw("header.payload.signature"),
            deadline_monotonic=deadline_monotonic,
            cancellation=signal,
        )
    )
