from __future__ import annotations

import asyncio

import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.graph.state import AgentSemanticOutcome
from agent_runtime.model.context import (
    ModelCallContextAccessor,
    ModelContextBindingRuntimeInvoker,
)
from agent_runtime.model.contracts import MissingModelCallContext
from tests.helpers import scope


def _outcome() -> AgentSemanticOutcome:
    return AgentSemanticOutcome(
        status=CapabilityStatus.SUCCESS,
        capability_id=None,
        answer_text="test",
        user_result=None,
        failure=None,
    )


@pytest.mark.asyncio
async def test_concurrent_requests_do_not_share_context_and_exit_resets_it() -> None:
    accessor = ModelCallContextAccessor()
    both_entered = asyncio.Event()
    entered = 0
    lock = asyncio.Lock()
    observed: dict[str, tuple[str, str, float]] = {}

    class Delegate:
        async def ainvoke(self, *, question: str, scope: object) -> AgentSemanticOutcome:
            nonlocal entered
            del scope
            async with lock:
                entered += 1
                if entered == 2:
                    both_entered.set()
            await both_entered.wait()
            current = accessor.require_current()
            observed[question] = (
                current.request_id,
                current.correlation_id,
                current.deadline_monotonic,
            )
            return _outcome()

    binder = ModelContextBindingRuntimeInvoker(Delegate())
    first_scope = scope("税务政策一")
    second_scope = scope("税务政策二")
    object.__setattr__(first_scope.context, "request_id", "req-one")
    object.__setattr__(first_scope.context, "correlation_id", "corr-one")
    object.__setattr__(second_scope.context, "request_id", "req-two")
    object.__setattr__(second_scope.context, "correlation_id", "corr-two")

    await asyncio.gather(
        binder.ainvoke(question="税务政策一", scope=first_scope),
        binder.ainvoke(question="税务政策二", scope=second_scope),
    )

    assert observed["税务政策一"][:2] == ("req-one", "corr-one")
    assert observed["税务政策二"][:2] == ("req-two", "corr-two")
    with pytest.raises(MissingModelCallContext):
        accessor.require_current()


@pytest.mark.asyncio
async def test_cancellation_resets_context_and_propagates() -> None:
    accessor = ModelCallContextAccessor()
    started = asyncio.Event()

    class Delegate:
        async def ainvoke(self, *, question: str, scope: object) -> AgentSemanticOutcome:
            del question, scope
            assert accessor.require_current().request_id == "req-1"
            started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    binder = ModelContextBindingRuntimeInvoker(Delegate())
    task = asyncio.create_task(binder.ainvoke(question="税务政策", scope=scope("税务政策")))
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    with pytest.raises(MissingModelCallContext):
        accessor.require_current()

