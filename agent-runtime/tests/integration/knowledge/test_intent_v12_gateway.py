"""Component-only non-live tests; this does not switch or certify a new root."""
import asyncio
from dataclasses import asdict
import json

import httpx
import pytest

from agent_runtime.knowledge.intent_contracts import KnowledgeQueryIntentInput
from agent_runtime.knowledge.intent_task_v12 import KnowledgeQueryIntentTaskV12, OUTPUT_NAME
from agent_runtime.model.contracts import ModelCallContext, ModelInputDenied, ModelProviderFailureKind
from agent_runtime.model.deepseek.transport import DeepSeekChatTransport
from agent_runtime.model.gateway import BoundedStructuredModelGateway
from agent_runtime.model.settings import ModelApiKey, ModelProvider, ModelSettings
from agent_runtime.observation import observation_scope


def context(*, remaining=10):
    return ModelCallContext(request_id="intent-nonlive", correlation_id="intent-contract",
                            deadline_monotonic=asyncio.get_running_loop().time() + remaining)


def body(*, mode="lookup", outcome="search", missing=()):
    intent = {"outcome": outcome, "query_mode": mode,
              "domains": {"tax.policy": "selected" if outcome == "search" else "not_selected"},
              "missing_conditions": list(missing)}
    return {"object": "chat.completion", "model": ModelSettings.MODEL_NAME,
            "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                "role": "assistant", "content": None, "tool_calls": [{"id": "nonlive-call", "type": "function",
                    "function": {"name": OUTPUT_NAME, "arguments": json.dumps(intent)}}],
            }}]}


def settings():
    return ModelSettings(provider=ModelProvider.DEEPSEEK, api_key=ModelApiKey("synthetic-nonlive-only"))


def gateway(task, client):
    return BoundedStructuredModelGateway(transport=DeepSeekChatTransport(settings=settings(), client=client),
                                        definitions=(task,), max_concurrency=1)


@pytest.mark.parametrize("mode,outcome,missing", [
    ("lookup", "search", ()), ("explanation", "search", ()), ("applicability", "search", ()),
    ("applicability", "clarification_required", ("period",)), ("none", "unsupported", ()),
])
async def test_provider_wire_to_new_intent_uses_exactly_one_model_request(mode, outcome, missing):
    paths = []
    question = "税务法规 2025年 不含13%的规定"

    def handler(request):
        paths.append(request.url.path)
        payload = json.loads(request.content)
        assert payload["max_tokens"] == 512 and payload["stream"] is False
        assert payload["tools"][0]["function"]["strict"] is True
        assert json.loads(payload["messages"][1]["content"])["question"] == question
        return httpx.Response(200, json=body(mode=mode, outcome=outcome, missing=missing))

    task = KnowledgeQueryIntentTaskV12.definition(enabled_domain_ids=("tax.policy",))
    async with httpx.AsyncClient(base_url=ModelSettings.BASE_URL, transport=httpx.MockTransport(handler), trust_env=False) as client:
        with observation_scope() as observations:
            result = await gateway(task, client).generate(definition=task,
                input=KnowledgeQueryIntentInput(minimized_question=question), context=context())
        assert result.failure_kind is None
        assert result.output.outcome == outcome and result.output.query_mode == mode
        assert result.output.missing_conditions == missing
        assert paths == ["/beta/chat/completions"]
        snapshot = observations.snapshot()
        assert len(snapshot.model_calls) == 1 and snapshot.downstream_calls == () and snapshot.plans == ()
        assert snapshot.model_calls[0]["status"] == "succeeded"
        serialized = json.dumps(asdict(snapshot))
        assert "synthetic-nonlive-only" not in serialized and "nonlive-call" not in serialized
    assert client.is_closed


@pytest.mark.parametrize("fault,expected", [
    ("http", ModelProviderFailureKind.PROVIDER_FAILURE),
    ("timeout", ModelProviderFailureKind.PROVIDER_TIMEOUT),
    ("json", ModelProviderFailureKind.INVALID_OUTPUT),
    ("extra", ModelProviderFailureKind.INVALID_OUTPUT),
    ("duplicate", ModelProviderFailureKind.INVALID_OUTPUT),
    ("second_call", ModelProviderFailureKind.INVALID_OUTPUT),
    ("mixed_text", ModelProviderFailureKind.INVALID_OUTPUT),
    ("truncated", ModelProviderFailureKind.INVALID_OUTPUT),
])
async def test_failures_preserve_category_without_retry_or_retrieval(fault, expected):
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if fault == "http":
            return httpx.Response(503)
        if fault == "timeout":
            raise httpx.ReadTimeout("synthetic non-live timeout", request=request)
        value = body()
        choice = value["choices"][0]
        message = choice["message"]
        function = message["tool_calls"][0]["function"]
        if fault == "json":
            function["arguments"] = "{"
        elif fault == "extra":
            value_intent = json.loads(function["arguments"])
            value_intent["queries"] = []
            function["arguments"] = json.dumps(value_intent)
        elif fault == "duplicate":
            function["arguments"] = function["arguments"].replace('"outcome":', '"outcome":"unsupported","outcome":')
        elif fault == "second_call":
            message["tool_calls"] *= 2
        elif fault == "mixed_text":
            message["content"] = "raw-model-marker"
        elif fault == "truncated":
            choice["finish_reason"] = "length"
        return httpx.Response(200, json=value)

    task = KnowledgeQueryIntentTaskV12.definition(enabled_domain_ids=("tax.policy",))
    async with httpx.AsyncClient(base_url=ModelSettings.BASE_URL, transport=httpx.MockTransport(handler), trust_env=False) as client:
        with observation_scope() as observations:
            result = await gateway(task, client).generate(definition=task,
                input=KnowledgeQueryIntentInput(minimized_question="税务政策"), context=context())
        assert result.output is None and result.failure_kind is expected
        assert paths == ["/beta/chat/completions"]
        snapshot = observations.snapshot()
        assert snapshot.downstream_calls == () and snapshot.plans == ()
        assert snapshot.model_calls[0]["failureKind"] == expected.value
        assert "raw-model-marker" not in json.dumps(asdict(snapshot))
    assert client.is_closed


@pytest.mark.parametrize("question", ["税务 demo@example.test", "税务 电话13800138000", "税" * 1025])
async def test_rejected_input_never_reaches_transport_or_observation(question):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        pytest.fail("Input rejection must precede outbound")

    task = KnowledgeQueryIntentTaskV12.definition(enabled_domain_ids=("tax.policy",))
    async with httpx.AsyncClient(base_url=ModelSettings.BASE_URL, transport=httpx.MockTransport(handler), trust_env=False) as client:
        bounded = gateway(task, client)
        with observation_scope() as observations, pytest.raises(ModelInputDenied):
            await bounded.generate(definition=task, input=KnowledgeQueryIntentInput(minimized_question=question), context=context())
        assert calls == [] and observations.snapshot().model_calls == ()
        assert observations.snapshot().downstream_calls == ()


async def test_deadline_timeout_and_cancellation_release_gateway_slot_without_retry():
    calls = []
    entered = asyncio.Event()
    cancelled = asyncio.Event()
    should_wait = True

    async def handler(request):
        calls.append(request.url.path)
        if should_wait:
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        return httpx.Response(200, json=body())

    task = KnowledgeQueryIntentTaskV12.definition(enabled_domain_ids=("tax.policy",))
    value = KnowledgeQueryIntentInput(minimized_question="税务政策")
    async with httpx.AsyncClient(base_url=ModelSettings.BASE_URL, transport=httpx.MockTransport(handler), trust_env=False) as client:
        bounded = gateway(task, client)
        expired = await bounded.generate(definition=task, input=value, context=context(remaining=0))
        assert expired.failure_kind is ModelProviderFailureKind.PROVIDER_TIMEOUT and calls == []
        # Leave scheduling headroom beyond the gateway's 250ms reserve.
        timed_out = await bounded.generate(definition=task, input=value, context=context(remaining=0.75))
        assert timed_out.failure_kind is ModelProviderFailureKind.PROVIDER_TIMEOUT and cancelled.is_set()
        entered.clear()
        cancelled.clear()
        with observation_scope() as observations:
            pending = asyncio.create_task(bounded.generate(definition=task, input=value, context=context()))
            await asyncio.wait_for(entered.wait(), timeout=1)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
        assert cancelled.is_set() and observations.snapshot().model_calls[0]["failureKind"] == "cancelled"
        should_wait = False
        recovered = await bounded.generate(definition=task, input=value, context=context())
        assert recovered.output.outcome == "search"
        # Three independent invocations: timed out, cancelled, then a fresh call.
        assert calls == ["/beta/chat/completions"] * 3
    assert client.is_closed
