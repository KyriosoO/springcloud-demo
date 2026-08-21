from __future__ import annotations

import asyncio

import pytest

from agent_runtime.capability_api.contracts import CancellationSource, CapabilityStatus
from agent_runtime.core.execution import CapabilityExecutionCore
from agent_runtime.core.registry import CapabilityRegistryBuilder
from agent_runtime.settings import CoreRuntimeSettings
from tests.helpers import (
    ManualCancellationSignal,
    QueryValidator,
    ResultHandler,
    candidate,
    registration,
    scope,
    success_result,
)


@pytest.mark.asyncio
async def test_concurrent_submissions_call_handler_only_once() -> None:
    release = asyncio.Event()
    handler = ResultHandler(success_result(), release=release)
    registry = CapabilityRegistryBuilder(CoreRuntimeSettings()).build(
        (registration(validator=QueryValidator(), handler=handler),)
    )
    core = CapabilityExecutionCore(registry, CoreRuntimeSettings())
    execution_scope = scope()

    first = asyncio.create_task(core.execute(candidate=candidate(), scope=execution_scope))
    await handler.started.wait()
    second = asyncio.create_task(core.execute(candidate=candidate(), scope=execution_scope))
    await asyncio.sleep(0)
    release.set()
    first_result, second_result = await asyncio.gather(first, second)

    assert handler.calls == 1
    assert {first_result.status, second_result.status} == {
        CapabilityStatus.SUCCESS,
        CapabilityStatus.INVALID_ARGUMENT,
    }
    assert execution_scope.latch.state.value == "finished"


@pytest.mark.asyncio
async def test_runtime_shutdown_finishes_latch_and_propagates_cancel() -> None:
    cancellation = ManualCancellationSignal()
    release = asyncio.Event()
    handler = ResultHandler(success_result(), release=release)
    registry = CapabilityRegistryBuilder(CoreRuntimeSettings()).build(
        (registration(validator=QueryValidator(), handler=handler),)
    )
    core = CapabilityExecutionCore(registry, CoreRuntimeSettings())
    execution_scope = scope(cancellation=cancellation)
    task = asyncio.create_task(core.execute(candidate=candidate(), scope=execution_scope))
    await handler.started.wait()

    cancellation.cancel(CancellationSource.RUNTIME_SHUTDOWN)
    with pytest.raises(asyncio.CancelledError):
        await task

    assert execution_scope.latch.state.value == "finished"
    assert execution_scope.latch.completion == "runtime_cancelled"
    release.set()


@pytest.mark.asyncio
async def test_handler_failure_consumes_action_and_rejects_second_submission() -> None:
    from tests.helpers import failure_result

    handler = ResultHandler(failure_result())
    registry = CapabilityRegistryBuilder(CoreRuntimeSettings()).build(
        (registration(validator=QueryValidator(), handler=handler),)
    )
    core = CapabilityExecutionCore(registry, CoreRuntimeSettings())
    execution_scope = scope()

    first = await core.execute(candidate=candidate(), scope=execution_scope)
    second = await core.execute(candidate=candidate(), scope=execution_scope)

    assert first.status is CapabilityStatus.DOWNSTREAM_FAILURE
    assert second.status is CapabilityStatus.INVALID_ARGUMENT
    assert second.failure is not None
    assert second.failure.code == "core.second_action_not_allowed"
    assert handler.calls == 1
