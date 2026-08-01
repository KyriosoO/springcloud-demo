from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace

import pytest

from agent_runtime.model.contracts import (
    ModelCallContext,
    ModelProviderFailureKind,
    ModelTaskDefinition,
    ModelTaskId,
    StructuredFinishKind,
    StructuredModelRequest,
    StructuredModelResponse,
    StructuredOutputMode,
    StructuredToolMode,
)
from agent_runtime.model.gateway import BoundedStructuredModelGateway
from tests.model_helpers import FakeStructuredModelTransport


@dataclass(frozen=True, slots=True)
class SampleInput:
    value: str


def _definition(*, timeout_ms: int = 1000) -> ModelTaskDefinition[SampleInput, str]:
    def build_request(input: SampleInput) -> StructuredModelRequest:
        return StructuredModelRequest(
            task_id=ModelTaskId.KNOWLEDGE_REWRITE,
            task_version="test-task-v1",
            system_instruction="Return JSON.",
            user_payload_json='{"value":"' + input.value + '"}',
            tools=(),
            tool_mode=StructuredToolMode.NONE,
            output_mode=StructuredOutputMode.JSON_OBJECT,
            max_output_tokens=32,
        )

    def parse_response(response: StructuredModelResponse) -> str:
        if response.content is None:
            raise ValueError("missing")
        return response.content

    return ModelTaskDefinition(
        task_id=ModelTaskId.KNOWLEDGE_REWRITE,
        task_version="test-task-v1",
        input_type=SampleInput,
        max_input_bytes=1024,
        timeout_ms=timeout_ms,
        max_output_tokens=32,
        build_request=build_request,
        parse_response=parse_response,
    )


def _response() -> StructuredModelResponse:
    return StructuredModelResponse(
        finish_kind=StructuredFinishKind.STOP,
        content='{"value":"ok"}',
        tool_calls=(),
        usage_total_tokens=None,
    )


def _context(deadline: float) -> ModelCallContext:
    return ModelCallContext(request_id="req-1", correlation_id="corr-1", deadline_monotonic=deadline)


@pytest.mark.asyncio
async def test_exhausted_request_deadline_is_zero_call() -> None:
    loop = asyncio.get_running_loop()
    definition = _definition()
    transport = FakeStructuredModelTransport(_response())
    gateway = BoundedStructuredModelGateway(
        transport=transport,
        definitions=(definition,),
        max_concurrency=1,
    )

    result = await gateway.generate(
        definition=definition,
        input=SampleInput("x"),
        context=_context(loop.time() + 0.100),
    )

    assert result.failure_kind is ModelProviderFailureKind.PROVIDER_TIMEOUT
    assert transport.calls == 0


@pytest.mark.asyncio
async def test_single_absolute_deadline_covers_transport_and_releases_permit() -> None:
    loop = asyncio.get_running_loop()
    wait = asyncio.Event()
    definition = _definition(timeout_ms=30)
    transport = FakeStructuredModelTransport(_response(), wait=wait)
    gateway = BoundedStructuredModelGateway(
        transport=transport,
        definitions=(definition,),
        max_concurrency=1,
    )

    result = await gateway.generate(
        definition=definition,
        input=SampleInput("x"),
        context=_context(loop.time() + 10),
    )

    assert result.failure_kind is ModelProviderFailureKind.PROVIDER_TIMEOUT
    assert transport.calls == 1
    assert transport.active == 0


@pytest.mark.asyncio
async def test_global_concurrency_limit_bounds_active_transport_calls() -> None:
    loop = asyncio.get_running_loop()
    wait = asyncio.Event()
    definition = _definition()
    transport = FakeStructuredModelTransport(_response(), wait=wait)
    gateway = BoundedStructuredModelGateway(
        transport=transport,
        definitions=(definition,),
        max_concurrency=1,
    )
    first = asyncio.create_task(
        gateway.generate(
            definition=definition,
            input=SampleInput("one"),
            context=_context(loop.time() + 10),
        )
    )
    await transport.started.wait()
    second = asyncio.create_task(
        gateway.generate(
            definition=definition,
            input=SampleInput("two"),
            context=_context(loop.time() + 10),
        )
    )
    await asyncio.sleep(0)
    third = await gateway.generate(
        definition=definition,
        input=SampleInput("three"),
        context=_context(loop.time() + 10),
    )

    assert transport.calls == 1
    assert transport.max_active == 1
    assert third.failure_kind is ModelProviderFailureKind.PROVIDER_TIMEOUT
    wait.set()
    results = await asyncio.gather(first, second)

    assert all(result.output == '{"value":"ok"}' for result in results)
    assert transport.calls == 2
    assert transport.max_active == 1


@pytest.mark.asyncio
async def test_cancellation_propagates_and_does_not_accept_late_result() -> None:
    loop = asyncio.get_running_loop()
    wait = asyncio.Event()
    definition = _definition()
    transport = FakeStructuredModelTransport(_response(), wait=wait)
    gateway = BoundedStructuredModelGateway(
        transport=transport,
        definitions=(definition,),
        max_concurrency=1,
    )
    task = asyncio.create_task(
        gateway.generate(
            definition=definition,
            input=SampleInput("x"),
            context=_context(loop.time() + 10),
        )
    )
    await transport.started.wait()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert transport.active == 0
    assert task.cancelled()


@pytest.mark.asyncio
async def test_transport_failure_is_not_retried() -> None:
    loop = asyncio.get_running_loop()
    definition = _definition()
    transport = FakeStructuredModelTransport(failure=RuntimeError("provider secret body"))
    gateway = BoundedStructuredModelGateway(
        transport=transport,
        definitions=(definition,),
        max_concurrency=1,
    )

    result = await gateway.generate(
        definition=definition,
        input=SampleInput("x"),
        context=_context(loop.time() + 10),
    )

    assert result.failure_kind is ModelProviderFailureKind.PROVIDER_FAILURE
    assert transport.calls == 1
