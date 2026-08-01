from __future__ import annotations

from typing import cast

import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.graph.state import AgentSemanticOutcome, GraphRunContext
from agent_runtime.runtime import AgentRuntimeInvoker, CompiledAgentGraph
from agent_runtime.settings import CoreRuntimeSettings
from tests.helpers import scope


class SpyGraph:
    def __init__(self) -> None:
        self.calls = 0
        self.inputs: list[dict[str, object]] = []
        self.contexts: list[GraphRunContext] = []

    async def ainvoke(
        self,
        input: dict[str, object],
        *,
        context: GraphRunContext,
    ) -> dict[str, object]:
        self.calls += 1
        self.inputs.append(input)
        self.contexts.append(context)
        return {
            "final_outcome": AgentSemanticOutcome(
                status=CapabilityStatus.NO_RESULT,
                capability_id=None,
                answer_text="none",
                user_result=None,
                failure=None,
            )
        }


class CrashingAfterClaimGraph:
    async def ainvoke(
        self,
        input: dict[str, object],
        *,
        context: GraphRunContext,
    ) -> dict[str, object]:
        del input
        await context.execution_scope.latch.claim("test.query")
        await context.execution_scope.latch.finish(CapabilityStatus.SUCCESS)
        raise RuntimeError("unsafe graph detail")


@pytest.mark.asyncio
async def test_same_question_value_reaches_graph_and_execution_context() -> None:
    graph = SpyGraph()
    execution_scope = scope(question="same question")
    invoker = AgentRuntimeInvoker(cast(CompiledAgentGraph, graph), CoreRuntimeSettings())

    outcome = await invoker.ainvoke(question="same question", scope=execution_scope)

    assert outcome.status is CapabilityStatus.NO_RESULT
    assert graph.inputs == [{"question": "same question"}]
    assert graph.contexts[0].execution_scope.context.original_question == "same question"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "context_question", "code"),
    [
        ("one", "two", "core.question_context_mismatch"),
        ("   ", "   ", "core.invalid_question"),
        ("x" * 4097, "x" * 4097, "core.invalid_question"),
    ],
)
async def test_invalid_or_mismatched_question_never_calls_graph(
    question: str,
    context_question: str,
    code: str,
) -> None:
    graph = SpyGraph()
    invoker = AgentRuntimeInvoker(cast(CompiledAgentGraph, graph), CoreRuntimeSettings())
    execution_scope = scope(question=context_question if context_question.strip() else "valid")
    if not context_question.strip():
        object.__setattr__(execution_scope.context, "original_question", context_question)

    outcome = await invoker.ainvoke(question=question, scope=execution_scope)

    assert outcome.status is CapabilityStatus.INVALID_ARGUMENT
    assert outcome.failure is not None and outcome.failure.code == code
    assert graph.calls == 0


@pytest.mark.asyncio
async def test_graph_failure_after_claim_preserves_canonical_capability_id() -> None:
    graph = CrashingAfterClaimGraph()
    invoker = AgentRuntimeInvoker(cast(CompiledAgentGraph, graph), CoreRuntimeSettings())

    outcome = await invoker.ainvoke(question="test question", scope=scope())

    assert outcome.status is CapabilityStatus.INTERNAL_FAILURE
    assert outcome.capability_id == "test.query"
    assert outcome.user_result is None
    assert outcome.failure is not None and outcome.failure.code == "core.invalid_graph_state"
