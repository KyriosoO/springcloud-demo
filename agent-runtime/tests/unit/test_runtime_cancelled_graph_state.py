from __future__ import annotations

import asyncio
from typing import NoReturn, cast

import pytest
from langgraph.runtime import Runtime

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.core.execution import ActionAlreadyClaimed, ActionExecutionLatch, ActionLatchState
from agent_runtime.graph.nodes import select_action_node
from agent_runtime.graph.state import ActionSelectionInput, AgentSemanticOutcome, GraphRunContext
from agent_runtime.runtime import AgentRuntimeInvoker, CompiledAgentGraph
from agent_runtime.settings import CoreRuntimeSettings
from tests.helpers import descriptor, scope


class FinishedGraph:
    def __init__(self, result: str) -> None:
        self.result = result

    async def ainvoke(
        self, input: dict[str, object], *, context: GraphRunContext,
    ) -> dict[str, object]:
        del input
        await context.execution_scope.latch.claim("knowledge.query")
        await context.execution_scope.latch.finish("runtime_cancelled")
        if self.result == "exception":
            raise RuntimeError("graph failed after cancellation")
        if self.result == "late_outcome":
            return {"final_outcome": AgentSemanticOutcome(
                status=CapabilityStatus.SUCCESS,
                capability_id="knowledge.query",
                answer_text="late answer",
                user_result=None,
                failure=None,
            )}
        return {}


class EmptyGraph:
    async def ainvoke(
        self, input: dict[str, object], *, context: GraphRunContext,
    ) -> dict[str, object]:
        del input, context
        return {}


class CancellingSelector:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, input: ActionSelectionInput) -> NoReturn:
        del input
        self.calls += 1
        raise asyncio.CancelledError()


class SwallowingSelectionGraph:
    def __init__(self, selector: CancellingSelector) -> None:
        self.selector = selector

    async def ainvoke(
        self, input: dict[str, object], *, context: GraphRunContext,
    ) -> dict[str, object]:
        try:
            await select_action_node(
                {"question": cast(str, input["question"])},
                Runtime(context=context),
                descriptors=(descriptor(),),
                selector=self.selector,
            )
        except asyncio.CancelledError:
            return {}  # LangGraph 1.2.9 can consume a node-level cancellation.
        raise AssertionError("selection must cancel")


@pytest.mark.asyncio
@pytest.mark.parametrize("result", ["empty", "late_outcome", "exception"])
async def test_runtime_cancelled_latch_is_never_mapped_to_invalid_graph_state(result: str) -> None:
    graph = FinishedGraph(result)
    invoker = AgentRuntimeInvoker(cast(CompiledAgentGraph, graph), CoreRuntimeSettings())
    execution_scope = scope(question="test question")

    with pytest.raises(asyncio.CancelledError):
        await invoker.ainvoke(question="test question", scope=execution_scope)

    assert execution_scope.latch.completion == "runtime_cancelled"


@pytest.mark.asyncio
async def test_missing_graph_outcome_without_cancellation_still_fails_closed() -> None:
    graph = EmptyGraph()
    invoker = AgentRuntimeInvoker(cast(CompiledAgentGraph, graph), CoreRuntimeSettings())

    outcome = await invoker.ainvoke(question="test question", scope=scope(question="test question"))

    assert outcome.status is CapabilityStatus.INTERNAL_FAILURE
    assert outcome.failure is not None and outcome.failure.code == "core.invalid_graph_state"


@pytest.mark.asyncio
async def test_selection_cancellation_before_core_claim_survives_graph_suppression() -> None:
    selector = CancellingSelector()
    graph = SwallowingSelectionGraph(selector)
    invoker = AgentRuntimeInvoker(cast(CompiledAgentGraph, graph), CoreRuntimeSettings())
    execution_scope = scope(question="test question")

    with pytest.raises(asyncio.CancelledError):
        await invoker.ainvoke(question="test question", scope=execution_scope)

    assert selector.calls == 1
    assert execution_scope.latch.state is ActionLatchState.FINISHED
    assert execution_scope.latch.capability_id is None
    assert execution_scope.latch.completion == "runtime_cancelled"
    with pytest.raises(ActionAlreadyClaimed):
        await execution_scope.latch.claim("knowledge.query")


@pytest.mark.asyncio
async def test_unclaimed_cancel_marker_does_not_overwrite_a_claimed_action() -> None:
    latch = ActionExecutionLatch()
    await latch.claim("knowledge.query")

    await latch.cancel_unclaimed()

    before_state, before_completion = latch.state, latch.completion
    assert before_state is ActionLatchState.CLAIMED
    assert before_completion is None
    await latch.finish(CapabilityStatus.SUCCESS)
    await latch.cancel_unclaimed()
    assert latch.state is ActionLatchState.FINISHED
    assert latch.completion is CapabilityStatus.SUCCESS
