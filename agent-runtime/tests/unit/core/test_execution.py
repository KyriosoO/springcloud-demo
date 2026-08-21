from __future__ import annotations

import asyncio
from typing import Any

import pytest

from agent_runtime.capability_api.contracts import (
    ActionCandidate,
    CancellationSource,
    CapabilityRegistrationCandidate,
    CapabilityResult,
    CapabilityStatus,
    EgressDisposition,
    ModelEgressResult,
)
from agent_runtime.core.execution import CapabilityExecutionCore
from agent_runtime.core.registry import CapabilityRegistryBuilder
from agent_runtime.settings import CoreRuntimeSettings
from tests.helpers import (
    ManualCancellationSignal,
    MutableQueryValidator,
    QueryValidator,
    ResultHandler,
    candidate,
    failure_result,
    registration,
    scope,
    success_result,
)


def _core(validator: QueryValidator, handler: ResultHandler) -> CapabilityExecutionCore:
    registry = CapabilityRegistryBuilder(CoreRuntimeSettings()).build(
        (registration(validator=validator, handler=handler),)
    )
    return CapabilityExecutionCore(registry, CoreRuntimeSettings())


@pytest.mark.asyncio
async def test_invalid_arguments_do_not_claim_or_call_handler() -> None:
    validator = QueryValidator()
    handler = ResultHandler(success_result())
    execution_scope = scope()

    result = await _core(validator, handler).execute(
        candidate=ActionCandidate(capability_id="test.query", arguments={}),
        scope=execution_scope,
    )

    assert result.status is CapabilityStatus.INVALID_ARGUMENT
    assert handler.calls == 0
    assert execution_scope.latch.state.value == "open"

    subsequent_valid_execution = await _core(validator, handler).execute(
        candidate=candidate(),
        scope=execution_scope,
    )

    assert subsequent_valid_execution.status is CapabilityStatus.SUCCESS
    assert execution_scope.latch.state.value == "finished"
    assert handler.calls == 1


@pytest.mark.asyncio
async def test_published_cancellation_wins_over_simultaneous_handler_exception() -> None:
    cancellation = ManualCancellationSignal()
    release = asyncio.Event()
    handler = ResultHandler(
        success_result(),
        release=release,
        exception=RuntimeError("sensitive-late-error"),
    )
    execution_scope = scope(cancellation=cancellation)
    task = asyncio.create_task(
        _core(QueryValidator(), handler).execute(candidate=candidate(), scope=execution_scope)
    )
    await handler.started.wait()

    cancellation.cancel(CancellationSource.UPSTREAM_CANCEL)
    release.set()
    result = await task

    assert result.status is CapabilityStatus.TIMEOUT
    assert result.failure is not None and result.failure.code == "core.request_cancelled"
    assert execution_scope.latch.state.value == "finished"


@pytest.mark.asyncio
async def test_standard_handler_failure_is_preserved() -> None:
    expected = failure_result()
    handler = ResultHandler(expected)

    result = await _core(QueryValidator(), handler).execute(candidate=candidate(), scope=scope())

    assert result == expected
    assert handler.calls == 1


@pytest.mark.asyncio
async def test_handler_exception_becomes_safe_internal_failure(caplog: pytest.LogCaptureFixture) -> None:
    secret = "secret-response-body"
    handler = ResultHandler(success_result(), exception=RuntimeError(secret))

    result = await _core(QueryValidator(), handler).execute(candidate=candidate(), scope=scope())

    assert result.status is CapabilityStatus.INTERNAL_FAILURE
    assert result.failure is not None and result.failure.code == "core.handler_exception"
    assert secret not in caplog.text


@pytest.mark.asyncio
async def test_invalid_handler_result_is_discarded() -> None:
    invalid = CapabilityResult(
        status=CapabilityStatus.SUCCESS,
        domain_result={"private": "value"},
        egress=ModelEgressResult(disposition=EgressDisposition.ALLOWED, policy_version="v1"),
        failure=None,
    )
    handler = ResultHandler(invalid)

    result = await _core(QueryValidator(), handler).execute(candidate=candidate(), scope=scope())

    assert result.status is CapabilityStatus.INTERNAL_FAILURE
    assert result.domain_result is None
    assert result.egress.safe_payload is None


@pytest.mark.asyncio
async def test_pre_cancelled_request_does_not_call_validator_or_handler() -> None:
    cancellation = ManualCancellationSignal()
    cancellation.cancel(CancellationSource.UPSTREAM_CANCEL)
    validator = QueryValidator()
    handler = ResultHandler(success_result())

    result = await _core(validator, handler).execute(
        candidate=candidate(),
        scope=scope(cancellation=cancellation),
    )

    assert result.status is CapabilityStatus.TIMEOUT
    assert validator.calls == 0
    assert handler.calls == 0


@pytest.mark.asyncio
async def test_handler_timeout_discards_late_result() -> None:
    release = asyncio.Event()
    handler = ResultHandler(success_result(), release=release)
    loop = asyncio.get_running_loop()
    execution_scope = scope(deadline_monotonic=loop.time() + 0.02)

    result = await _core(QueryValidator(), handler).execute(candidate=candidate(), scope=execution_scope)

    assert result.status is CapabilityStatus.TIMEOUT
    assert result.failure is not None and result.failure.code == "core.handler_timeout"
    assert execution_scope.latch.state.value == "finished"
    release.set()


@pytest.mark.asyncio
async def test_published_cancellation_wins_over_simultaneous_handler_result() -> None:
    cancellation = ManualCancellationSignal()
    release = asyncio.Event()
    handler = ResultHandler(success_result(), release=release)
    execution_scope = scope(cancellation=cancellation)
    task = asyncio.create_task(
        _core(QueryValidator(), handler).execute(candidate=candidate(), scope=execution_scope)
    )
    await handler.started.wait()

    cancellation.cancel(CancellationSource.UPSTREAM_CANCEL)
    release.set()
    result = await task

    assert result.status is CapabilityStatus.TIMEOUT
    assert result.failure is not None and result.failure.code == "core.request_cancelled"
    assert execution_scope.latch.state.value == "finished"


@pytest.mark.asyncio
async def test_mutable_typed_input_is_rejected_before_handler() -> None:
    handler = ResultHandler(success_result())
    candidate_binding = registration(validator=QueryValidator(), handler=handler)
    unsafe_binding: CapabilityRegistrationCandidate[Any] = CapabilityRegistrationCandidate(
        descriptor=candidate_binding.descriptor,
        enabled=True,
        argument_validator=MutableQueryValidator(),
        handler=handler,
    )
    registry = CapabilityRegistryBuilder(CoreRuntimeSettings()).build((unsafe_binding,))

    result = await CapabilityExecutionCore(registry, CoreRuntimeSettings()).execute(
        candidate=candidate(),
        scope=scope(),
    )

    assert result.status is CapabilityStatus.INTERNAL_FAILURE
    assert handler.calls == 0
