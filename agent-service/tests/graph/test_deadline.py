import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from agent_service.api.errors import AgentFailure
from agent_service.api.schemas import AgentExecuteRequest
from agent_service.graph.runtime import run_graph


class LateGraph:
    async def ainvoke(self, graph_input):
        await asyncio.sleep(0.05)
        return {"request_id": graph_input["request_id"], "secured_result": {"type": "RESULT"}}


@pytest.mark.asyncio
async def test_late_graph_result_is_discarded():
    with pytest.raises(AgentFailure) as error:
        await run_graph(
            LateGraph(),
            {
                "request_id": uuid4(),
                "request_input": AgentExecuteRequest(message="员工"),
                "deadline_at": datetime.now(UTC) + timedelta(milliseconds=1),
                "trusted_identity": object(),
                "auth_upper_bound": object(),
            },
        )
    assert error.value.error.code == "TIMEOUT"
