import asyncio
from typing import Any, cast

from agent_service.api.errors import AgentError, AgentErrorCode, AgentFailure
from agent_service.graph.deadline import Deadline
from agent_service.graph.state import AgentGraphInput, AgentGraphOutput


async def run_graph(graph: Any, graph_input: AgentGraphInput) -> AgentGraphOutput:
    deadline = Deadline(graph_input["deadline_at"])
    deadline.require_remaining()
    try:
        result = await asyncio.wait_for(
            graph.ainvoke(graph_input),
            timeout=deadline.remaining_seconds(),
        )
    except TimeoutError as exc:
        raise AgentFailure(
            AgentError(code=AgentErrorCode.TIMEOUT, message="Request deadline was exceeded.")
        ) from exc
    return cast(AgentGraphOutput, result)
