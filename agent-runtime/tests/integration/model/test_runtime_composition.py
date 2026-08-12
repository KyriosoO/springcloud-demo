from __future__ import annotations

import json
from dataclasses import dataclass

import httpx
import pytest

import agent_runtime.bootstrap as bootstrap_module
from agent_runtime.bootstrap import LocalModelCompositionRoot, RuntimeCompositionRoot
from agent_runtime.capability_api.contracts import (
    CapabilityDescriptor,
    CapabilityExecutionContext,
    CapabilityKind,
    CapabilityRegistrationCandidate,
    CapabilityResult,
    CapabilityStatus,
    EgressDisposition,
    JsonObject,
    ModelEgressResult,
)
from agent_runtime.model.settings import ModelApiKey, ModelProvider, ModelSettings
from agent_runtime.settings import CoreRuntimeSettings
from tests.helpers import Provider, scope
from tests.model_helpers import AcceptGroundingPolicy


@dataclass(frozen=True, slots=True)
class EmptyInput:
    pass


class EmptyValidator:
    def validate(self, arguments: JsonObject) -> EmptyInput:
        if arguments:
            raise ValueError("test.arguments_not_empty")
        return EmptyInput()


class SuccessHandler:
    def __init__(self, *, allow_model_egress: bool = False) -> None:
        self.calls = 0
        self.allow_model_egress = allow_model_egress

    async def handle(
        self,
        input: EmptyInput,
        context: CapabilityExecutionContext,
    ) -> CapabilityResult:
        del input, context
        self.calls += 1
        if self.allow_model_egress:
            egress = ModelEgressResult(
                disposition=EgressDisposition.ALLOWED,
                policy_version="test-v1",
                safe_payload={
                    "schema_version": 1,
                    "facts": (
                        {
                            "fact_id": "fact-0001",
                            "value": "ACTIVE",
                            "source": {"record_ref": "record-0001", "field_id": "status"},
                        },
                    ),
                    "coverage": {"truncated": False},
                },
            )
        else:
            egress = ModelEgressResult(disposition=EgressDisposition.NOT_APPLICABLE)
        return CapabilityResult(
            status=CapabilityStatus.SUCCESS,
            domain_result={"value": "local-result"},
            egress=egress,
            failure=None,
        )


def _registration(handler: SuccessHandler) -> CapabilityRegistrationCandidate[EmptyInput]:
    return CapabilityRegistrationCandidate(
        descriptor=CapabilityDescriptor(
            capability_id="knowledge.query",
            api_version=1,
            kind=CapabilityKind.QUERY,
            display_name="Knowledge Query",
            description="Query registered public policy knowledge.",
            aliases=("knowledge", "tax policy"),
            argument_schema={
                "type": "object",
                "properties": {},
                "required": (),
                "additionalProperties": False,
            },
        ),
        enabled=True,
        argument_validator=EmptyValidator(),
        handler=handler,
    )


def _deepseek_settings() -> ModelSettings:
    return ModelSettings(
        provider=ModelProvider.DEEPSEEK,
        api_key=ModelApiKey("sentinel-fake-secret"),
    )


def _response(
    *,
    status: int = 200,
    content: str = '{"capability_id":"knowledge.query"}',
) -> httpx.Response:
    if status != 200:
        return httpx.Response(status)
    body = json.dumps(
        {
            "object": "chat.completion",
            "model": "deepseek-v4-pro",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"content": content},
                }
            ],
            "usage": {"total_tokens": 7},
        },
        separators=(",", ":"),
    ).encode("utf-8")
    return httpx.Response(
        200,
        headers={"Content-Type": "application/json", "Content-Encoding": "identity"},
        content=body,
    )


def test_invalid_limit_fails_before_deepseek_client_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builder_calls = 0

    def build_client(settings: ModelSettings) -> httpx.AsyncClient:
        nonlocal builder_calls
        del settings
        builder_calls += 1
        raise AssertionError("client allocation must not start")

    monkeypatch.setattr(bootstrap_module, "build_deepseek_http_client", build_client)

    with pytest.raises(ValueError, match="model.invalid_action_output_limit"):
        LocalModelCompositionRoot.build(
            settings=_deepseek_settings(),
            grounding_policies={},
            max_argument_bytes=0,
        )

    assert builder_calls == 0


@pytest.mark.asyncio
async def test_explicit_deepseek_composition_binds_context_and_owns_one_fake_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outbound_calls = 0
    builder_calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal outbound_calls
        outbound_calls += 1
        assert request.url == "https://api.deepseek.com/chat/completions"
        return _response()

    client = httpx.AsyncClient(
        base_url=ModelSettings.BASE_URL,
        transport=httpx.MockTransport(handler),
        trust_env=False,
        follow_redirects=False,
    )

    def build_client(settings: ModelSettings) -> httpx.AsyncClient:
        nonlocal builder_calls
        assert settings.provider is ModelProvider.DEEPSEEK
        builder_calls += 1
        return client

    monkeypatch.setattr(bootstrap_module, "build_deepseek_http_client", build_client)
    model = LocalModelCompositionRoot.build(
        settings=_deepseek_settings(),
        grounding_policies={},
    )
    capability_handler = SuccessHandler()
    runtime = RuntimeCompositionRoot.build(
        settings=CoreRuntimeSettings(),
        providers=(Provider(_registration(capability_handler)),),
        capability_selector=model.action_selector,
        answer_generator=model.answer_generator,
    )
    managed_runtime = model.bind_runtime(runtime)

    try:
        outcome = await managed_runtime.ainvoke(
            question="现行增值税政策是什么",
            scope=scope("现行增值税政策是什么"),
        )

        assert outcome.status is CapabilityStatus.SUCCESS
        assert outcome.capability_id == "knowledge.query"
        assert outcome.user_result == {"value": "local-result"}
        assert builder_calls == 1
        assert outbound_calls == 1
        assert capability_handler.calls == 1
    finally:
        await managed_runtime.aclose()
        await managed_runtime.aclose()

    assert client.is_closed
    with pytest.raises(RuntimeError, match="model.runtime_closed"):
        await managed_runtime.ainvoke(
            question="现行增值税政策是什么",
            scope=scope("现行增值税政策是什么"),
        )
    assert outbound_calls == 1


@pytest.mark.asyncio
async def test_explicit_deepseek_composition_wires_grounded_answer_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        (
            _response(),
            _response(
                content=json.dumps(
                    {
                        "answer": "状态为 ACTIVE [fact-0001]。",
                        "used_fact_ids": ["fact-0001"],
                        "unsupported_claims": [],
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            ),
        )
    )
    outbound_calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal outbound_calls
        del request
        outbound_calls += 1
        return next(responses)

    client = httpx.AsyncClient(
        base_url=ModelSettings.BASE_URL,
        transport=httpx.MockTransport(handler),
        trust_env=False,
        follow_redirects=False,
    )
    monkeypatch.setattr(
        bootstrap_module,
        "build_deepseek_http_client",
        lambda settings: client,
    )
    grounding = AcceptGroundingPolicy()
    model = LocalModelCompositionRoot.build(
        settings=_deepseek_settings(),
        grounding_policies={"knowledge.query": grounding},
    )
    capability_handler = SuccessHandler(allow_model_egress=True)
    managed_runtime = model.bind_runtime(
        RuntimeCompositionRoot.build(
            settings=CoreRuntimeSettings(),
            providers=(Provider(_registration(capability_handler)),),
            capability_selector=model.action_selector,
            answer_generator=model.answer_generator,
        )
    )

    try:
        outcome = await managed_runtime.ainvoke(
            question="现行增值税政策是什么",
            scope=scope("现行增值税政策是什么"),
        )
    finally:
        await managed_runtime.aclose()

    assert outcome.status is CapabilityStatus.SUCCESS
    assert outcome.capability_id == "knowledge.query"
    assert outcome.answer_text == "状态为 ACTIVE [fact-0001]。"
    assert outcome.user_result is None
    assert capability_handler.calls == 1
    assert grounding.calls == 1
    assert outbound_calls == 2
    assert client.is_closed


@pytest.mark.asyncio
async def test_deepseek_composition_maps_fake_provider_failure_and_still_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outbound_calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal outbound_calls
        del request
        outbound_calls += 1
        return _response(status=503)

    client = httpx.AsyncClient(
        base_url=ModelSettings.BASE_URL,
        transport=httpx.MockTransport(handler),
        trust_env=False,
        follow_redirects=False,
    )
    monkeypatch.setattr(
        bootstrap_module,
        "build_deepseek_http_client",
        lambda settings: client,
    )
    model = LocalModelCompositionRoot.build(
        settings=_deepseek_settings(),
        grounding_policies={},
    )
    capability_handler = SuccessHandler()
    managed_runtime = model.bind_runtime(
        RuntimeCompositionRoot.build(
            settings=CoreRuntimeSettings(),
            providers=(Provider(_registration(capability_handler)),),
            capability_selector=model.action_selector,
            answer_generator=model.answer_generator,
        )
    )

    try:
        outcome = await managed_runtime.ainvoke(
            question="现行增值税政策是什么",
            scope=scope("现行增值税政策是什么"),
        )
    finally:
        await managed_runtime.aclose()

    assert outcome.status is CapabilityStatus.DOWNSTREAM_FAILURE
    assert outcome.failure is not None
    assert outcome.failure.code == "model.provider_failure"
    assert capability_handler.calls == 0
    assert outbound_calls == 1
    assert client.is_closed
