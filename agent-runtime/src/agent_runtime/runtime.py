from __future__ import annotations

import asyncio

from langgraph.graph.state import CompiledStateGraph

from agent_runtime.capability_api.contracts import CapabilityStatus, FailureDetail, FailureSource
from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.graph.state import (
    AgentInputState,
    AgentOutputState,
    AgentRequestState,
    AgentSemanticOutcome,
    GraphRunContext,
)
from agent_runtime.settings import CoreRuntimeSettings


CompiledAgentGraph = CompiledStateGraph[
    AgentRequestState,
    GraphRunContext,
    AgentInputState,
    AgentOutputState,
]


def _invalid_outcome(code: str) -> AgentSemanticOutcome:
    return AgentSemanticOutcome(
        status=CapabilityStatus.INVALID_ARGUMENT,
        capability_id=None,
        answer_text="查询参数无效。",
        user_result=None,
        failure=FailureDetail(code=code, source=FailureSource.CORE),
    )


class AgentRuntimeInvoker:
    __slots__ = ("_graph", "_settings")

    def __init__(self, graph: CompiledAgentGraph, settings: CoreRuntimeSettings) -> None:
        self._graph = graph
        self._settings = settings

    async def ainvoke(
        self,
        *,
        question: str,
        scope: RequestExecutionScope,
    ) -> AgentSemanticOutcome:
        if (
            not isinstance(question, str)
            or not question
            or not question.strip()
            or len(question) > self._settings.max_question_chars
        ):
            return _invalid_outcome("core.invalid_question")
        if question != scope.context.original_question:
            return _invalid_outcome("core.question_context_mismatch")
        try:
            output = await self._graph.ainvoke(
                {"question": question},
                context=GraphRunContext(execution_scope=scope),
            )
            outcome = output.get("final_outcome")
            if not isinstance(outcome, AgentSemanticOutcome):
                raise ValueError("core.invalid_graph_state")
            return outcome
        except asyncio.CancelledError:
            raise
        except Exception:
            return AgentSemanticOutcome(
                status=CapabilityStatus.INTERNAL_FAILURE,
                capability_id=scope.latch.capability_id,
                answer_text="查询处理失败。",
                user_result=None,
                failure=FailureDetail(code="core.invalid_graph_state", source=FailureSource.CORE),
            )
