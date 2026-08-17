from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import TypeVar

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.graph.state import AgentSemanticOutcome
from agent_runtime.model.context import ModelContextBindingRuntimeInvoker
from agent_runtime.model.contracts import (
    AnswerGroundingPolicy,
    GroundingDecision,
    GroundingInput,
    StructuredModelTransport,
    StructuredModelRequest,
    StructuredModelResponse,
)
from agent_runtime.model.context import ModelCallContextAccessor
from agent_runtime.model.deepseek.answer_generator import (
    DeepSeekAnswerGenerator,
    build_answer_generation_task_definition,
)
from agent_runtime.model.gateway import BoundedStructuredModelGateway
from agent_runtime.model.grounding import GroundingPolicyRegistry
from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.model.settings import ModelSettings
from tests.helpers import scope


class FakeStructuredModelTransport:
    def __init__(
        self,
        response: StructuredModelResponse | None = None,
        *,
        failure: Exception | None = None,
        wait: asyncio.Event | None = None,
    ) -> None:
        self.response = response
        self.failure = failure
        self.wait = wait
        self.calls = 0
        self.requests: list[StructuredModelRequest] = []
        self.deadlines: list[float] = []
        self.started = asyncio.Event()
        self.active = 0
        self.max_active = 0

    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        self.calls += 1
        self.requests.append(request)
        self.deadlines.append(call_deadline)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.started.set()
        try:
            if self.wait is not None:
                await self.wait.wait()
            if self.failure is not None:
                raise self.failure
            if self.response is None:
                raise RuntimeError("test.response_missing")
            return self.response
        finally:
            self.active -= 1


class AcceptGroundingPolicy:
    def __init__(self, *, accepted: bool = True, failure: Exception | None = None) -> None:
        self.accepted = accepted
        self.failure = failure
        self.calls = 0
        self.inputs: list[GroundingInput] = []

    def validate(self, input: GroundingInput) -> GroundingDecision:
        self.calls += 1
        self.inputs.append(input)
        if self.failure is not None:
            raise self.failure
        if self.accepted:
            return GroundingDecision(accepted=True)
        from agent_runtime.model.contracts import GroundingRejectionReason

        return GroundingDecision(
            accepted=False,
            reason=GroundingRejectionReason.DOMAIN_POLICY_REJECTED,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class HistoricalV1AnswerComponents:
    answer_generator: DeepSeekAnswerGenerator

    async def aclose(self) -> None:
        return None


def build_historical_v1_answer_components(
    *,
    transport: StructuredModelTransport,
    grounding_policies: Mapping[str, AnswerGroundingPolicy],
    settings: ModelSettings | None = None,
) -> HistoricalV1AnswerComponents:
    active_settings = settings or ModelSettings()
    definition = build_answer_generation_task_definition(
        timeout_ms=active_settings.answer_timeout_ms,
    )
    accessor = ModelCallContextAccessor()
    return HistoricalV1AnswerComponents(
        answer_generator=DeepSeekAnswerGenerator(
            guard=QuestionEgressGuard(),
            gateway=BoundedStructuredModelGateway(
                transport=transport,
                definitions=(definition,),
                max_concurrency=active_settings.max_concurrency,
            ),
            context=accessor,
            grounding=GroundingPolicyRegistry(grounding_policies),
            definition=definition,
        )
    )


T = TypeVar("T")


async def call_with_model_context(
    operation: Callable[[], Awaitable[T]],
    *,
    question: str = "现行增值税政策是什么",
    deadline_monotonic: float | None = None,
) -> T:
    result: list[T] = []

    class Delegate:
        async def ainvoke(
            self,
            *,
            question: str,
            scope: RequestExecutionScope,
        ) -> AgentSemanticOutcome:
            del question, scope
            result.append(await operation())
            return AgentSemanticOutcome(
                status=CapabilityStatus.SUCCESS,
                capability_id=None,
                answer_text="test",
                user_result=None,
                failure=None,
            )

    await ModelContextBindingRuntimeInvoker(Delegate()).ainvoke(
        question=question,
        scope=scope(question, deadline_monotonic=deadline_monotonic),
    )
    return result[0]
