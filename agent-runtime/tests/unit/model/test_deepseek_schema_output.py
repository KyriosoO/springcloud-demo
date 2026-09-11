from dataclasses import replace
import asyncio
import json

import httpx
import pytest

from agent_runtime.model.contracts import InvalidModelOutput, ModelInputDenied, StructuredFinishKind
from agent_runtime.model.deepseek.transport import DeepSeekChatTransport
from agent_runtime.knowledge.rewrite_v10 import KnowledgeRewriteTaskV10, OUTPUT_NAME
from tests.contract.knowledge.test_rewrite_task_v10 import request
from tests.contract.knowledge.test_rewrite_task_v7 import wire_plan
from tests.unit.model.test_deepseek_transport import _settings, _client, FixedStream


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_model", [False, True])
async def test_schema_only_uses_one_fixed_beta_request_and_no_tool_execution(bad_model):
    calls = []

    async def handle(outbound):
        calls.append(outbound)
        assert str(outbound.url) == "https://api.deepseek.com/beta/chat/completions"
        body = json.loads(outbound.content)
        assert body["model"] == "deepseek-flash" and body["thinking"] == {"type": "disabled"}
        assert body["tools"][0]["function"]["strict"] is True
        assert body["tool_choice"] == {"type": "function", "function": {"name": OUTPUT_NAME}}
        raw = {"object": "chat.completion", "model": "deepseek-v4-pro" if bad_model else "deepseek-flash",
               "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {"content": None,
                            "tool_calls": [{"type": "function", "function": {
                                "name": OUTPUT_NAME, "arguments": json.dumps(wire_plan()),
                            }}]}}]}
        return httpx.Response(200, headers={"Content-Type": "application/json"}, stream=FixedStream(json.dumps(raw).encode()))

    async with _client(httpx.MockTransport(handle)) as client:
        transport = DeepSeekChatTransport(settings=_settings(), client=client)
        if bad_model:
            with pytest.raises(InvalidModelOutput, match="provider_response_mismatch"):
                await transport.complete(request(), call_deadline=asyncio.get_running_loop().time() + 2)
        else:
            result = await transport.complete(request(), call_deadline=asyncio.get_running_loop().time() + 2)
            assert result.finish_kind is StructuredFinishKind.TOOL_CALLS
            assert KnowledgeRewriteTaskV10.definition().parse_response(result).outcome == "search"
    assert len(calls) == 1 and client.is_closed


@pytest.mark.asyncio
async def test_unsupported_schema_fails_before_http():
    calls = []

    async def handle(outbound):
        calls.append(outbound)
        raise AssertionError("No HTTP allowed")

    current = request()
    schema = {"type": "object", "properties": {"x": {"type": "string", "minLength": 1}},
              "required": ["x"], "additionalProperties": False}
    current = replace(current, tools=(replace(current.tools[0], arguments_schema=schema),))
    async with _client(httpx.MockTransport(handle)) as client:
        with pytest.raises(ModelInputDenied, match="strict_schema_unsupported"):
            await DeepSeekChatTransport(settings=_settings(), client=client).complete(
                current, call_deadline=asyncio.get_running_loop().time() + 2)
    assert calls == []
