from dataclasses import asdict, replace
import json

import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.main import build_runtime
from agent_runtime.model.contracts import ModelTaskId, StructuredFinishKind, StructuredModelResponse, StructuredToolCall
from agent_runtime.observation import observation_scope
from tests.helpers import scope
from tests.integration.knowledge.test_requirement_runtime_composition import Model, Clients, plan, QUESTION
from tests.integration.knowledge.test_production_runtime_wiring import _enabled_environment


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["none", "two", "wrong_name", "mixed", "scope", "unknown_domain", "root_fields"])
async def test_invalid_output_envelope_or_semantics_has_zero_retrieval_and_no_raw_observation(fault, caplog):
    marker = "SYNTHETIC_RAW_MODEL_MARKER"

    class Broken(Model):
        async def complete(self, request, *, call_deadline):
            result = await super().complete(request, call_deadline=call_deadline)
            if request.task_id is not ModelTaskId.KNOWLEDGE_REWRITE: return result
            call = result.tool_calls[0]
            if fault == "none":
                return StructuredModelResponse(finish_kind=StructuredFinishKind.STOP,
                    content=call.arguments_json, tool_calls=(), usage_total_tokens=0)
            if fault == "two": return replace(result, tool_calls=result.tool_calls * 2)
            if fault == "wrong_name": return replace(result, tool_calls=(replace(call, name="execute_query"),))
            if fault == "mixed": return replace(result, content=marker)
            value = json.loads(call.arguments_json)
            if fault == "scope": value["queries"][0]["query"] += " 17%税率"
            elif fault == "unknown_domain": value["queries"][0]["domain_id"] = "employee"
            else: value["extra"] = marker
            return replace(result, tool_calls=(StructuredToolCall(name=call.name, arguments_json=json.dumps(value)),))

    model, clients = Broken(plan()), Clients()
    runtime = build_runtime(_enabled_environment(), model_transport=model, knowledge_http_client_factory=clients)
    try:
        with observation_scope() as collector:
            result = await runtime.ainvoke(question=QUESTION, scope=scope(QUESTION))
            view = json.dumps(asdict(collector.snapshot()))
    finally:
        await runtime.aclose()
    assert result.status is CapabilityStatus.DOWNSTREAM_FAILURE
    assert len(model.requests) == 2 and clients.paths == []
    assert marker not in caplog.text + view and "execute_query" not in view
    assert all(client.is_closed for client in clients.clients)
