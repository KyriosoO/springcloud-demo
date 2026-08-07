from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.graph.state import AgentSemanticOutcome
from agent_runtime.model.context import ModelContextBindingRuntimeInvoker
from agent_runtime.model.contracts import (
    GroundingDecision,
    GroundingInput,
    StructuredModelRequest,
    StructuredModelResponse,
)
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
