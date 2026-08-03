from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from time import monotonic
from typing import Any

import httpx
import pytest

from agent_runtime.model.contracts import (
    InvalidModelOutput,
    ModelInputDenied,
    ModelProviderFailureKind,
    ModelTaskId,
    ModelTransportError,
    StructuredModelRequest,
    StructuredOutputMode,
    StructuredToolMode,
)
from agent_runtime.model.deepseek.transport import DeepSeekChatTransport, build_deepseek_http_client
from agent_runtime.model.settings import ModelApiKey, ModelProvider, ModelSettings


SECRET = "sentinel-live-secret"


def _request() -> StructuredModelRequest:
    return StructuredModelRequest(
        task_id=ModelTaskId.ANSWER_GENERATION,
        task_version="answer-v1",
        system_instruction="Return one JSON object.",
        user_payload_json='{"question":"synthetic tax question"}',
        tools=(),
        tool_mode=StructuredToolMode.NONE,
        output_mode=StructuredOutputMode.JSON_OBJECT,
        max_output_tokens=64,
    )


def _response_bytes() -> bytes:
    return json.dumps(
        {
            "object": "chat.completion",
            "model": "deepseek-v4-pro",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"content": '{"answer":"synthetic"}'},
                }
            ],
            "usage": {"total_tokens": 9},
        },
        separators=(",", ":"),
    ).encode()


def _settings(**overrides: object) -> ModelSettings:
    values: dict[str, object] = {
        "provider": ModelProvider.DEEPSEEK,
        "api_key": ModelApiKey(SECRET),
    }
    values.update(overrides)
    return ModelSettings(**values)  # type: ignore[arg-type]


def _client(handler: httpx.AsyncBaseTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=ModelSettings.BASE_URL,
        transport=handler,
        trust_env=False,
        follow_redirects=False,
    )


class FixedStream(httpx.AsyncByteStream):
    def __init__(self, content: bytes) -> None:
        self._content = content

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield self._content


@pytest.mark.asyncio
async def test_posts_one_canonical_request_and_strictly_decodes_response(caplog: pytest.LogCaptureFixture) -> None:
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        body = await request.aread()
        parsed = json.loads(body)
        assert request.url == "https://api.deepseek.com/chat/completions"
        assert request.headers["authorization"] == f"Bearer {SECRET}"
        assert request.headers["accept-encoding"] == "identity"
        assert parsed["model"] == "deepseek-v4-pro"
        assert parsed["thinking"] == {"type": "disabled"}
        assert parsed["stream"] is False
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json", "Content-Encoding": "identity"},
            stream=FixedStream(_response_bytes()),
        )

    with caplog.at_level(logging.DEBUG):
        async with _client(httpx.MockTransport(handler)) as client:
            transport = DeepSeekChatTransport(settings=_settings(), client=client)
            response = await transport.complete(
                _request(),
                call_deadline=asyncio.get_running_loop().time() + 2,
            )

    assert response.content == '{"answer":"synthetic"}'
    assert response.usage_total_tokens == 9
    assert len(captured) == 1
    assert SECRET not in caplog.text


class ExplodingStream(httpx.AsyncByteStream):
    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield b"non-200 body must not be read"
        raise AssertionError("non-200 body must not be read")


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [201, 204, 301, 400, 401, 402, 429, 500, 504])
async def test_every_non_200_status_is_one_call_and_reads_zero_body(status: int) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        del request
        calls += 1
        return httpx.Response(status, stream=ExplodingStream())

    async with _client(httpx.MockTransport(handler)) as client:
        transport = DeepSeekChatTransport(settings=_settings(), client=client)
        with pytest.raises(ModelTransportError) as raised:
            await transport.complete(
                _request(),
                call_deadline=asyncio.get_running_loop().time() + 2,
            )

    expected = (
        ModelProviderFailureKind.PROVIDER_TIMEOUT
        if status == 504
        else ModelProviderFailureKind.PROVIDER_FAILURE
    )
    assert raised.value.kind is expected
    assert calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers",
    [
        {"Content-Type": "text/plain"},
        {"Content-Type": "application/json", "Content-Encoding": "gzip"},
    ],
)
async def test_rejects_non_json_or_compressed_success(headers: dict[str, str]) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, headers=headers, stream=FixedStream(_response_bytes()))

    async with _client(httpx.MockTransport(handler)) as client:
        transport = DeepSeekChatTransport(settings=_settings(), client=client)
        with pytest.raises(InvalidModelOutput):
            await transport.complete(
                _request(),
                call_deadline=asyncio.get_running_loop().time() + 2,
            )


@pytest.mark.asyncio
async def test_rejects_response_before_buffer_exceeds_limit() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            stream=FixedStream(b"x" * 16385),
        )

    async with _client(httpx.MockTransport(handler)) as client:
        transport = DeepSeekChatTransport(
            settings=_settings(max_response_bytes=16384),
            client=client,
        )
        with pytest.raises(InvalidModelOutput, match="model.provider_response_too_large"):
            await transport.complete(
                _request(),
                call_deadline=asyncio.get_running_loop().time() + 2,
            )


@pytest.mark.asyncio
async def test_expired_deadline_is_zero_call() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        del request
        calls += 1
        return httpx.Response(200, headers={"Content-Type": "application/json"}, stream=FixedStream(_response_bytes()))

    async with _client(httpx.MockTransport(handler)) as client:
        transport = DeepSeekChatTransport(settings=_settings(), client=client)
        with pytest.raises(ModelTransportError) as raised:
            await transport.complete(
                _request(),
                call_deadline=asyncio.get_running_loop().time() - 1,
            )

    assert raised.value.kind is ModelProviderFailureKind.PROVIDER_TIMEOUT
    assert calls == 0


@pytest.mark.asyncio
async def test_cancellation_propagates_and_closes_stream() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    class WaitingStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            started.set()
            await release.wait()
            yield _response_bytes()

    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, headers={"Content-Type": "application/json"}, stream=WaitingStream())

    async with _client(httpx.MockTransport(handler)) as client:
        transport = DeepSeekChatTransport(settings=_settings(), client=client)
        task = asyncio.create_task(
            transport.complete(
                _request(),
                call_deadline=asyncio.get_running_loop().time() + 10,
            )
        )
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert task.cancelled()


@pytest.mark.asyncio
async def test_closed_client_fails_without_request_and_secret_never_reaches_logs(caplog: pytest.LogCaptureFixture) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        raise AssertionError("closed client must not send")

    client = _client(httpx.MockTransport(handler))
    transport = DeepSeekChatTransport(settings=_settings(), client=client)
    await client.aclose()
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(ModelTransportError) as raised:
            await transport.complete(
                _request(),
                call_deadline=asyncio.get_running_loop().time() + 2,
            )

    assert raised.value.kind is ModelProviderFailureKind.PROVIDER_FAILURE
    assert SECRET not in caplog.text
    assert SECRET not in repr(transport)


def test_rejects_invalid_deadline_or_request_over_limit_without_http() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        del request
        calls += 1
        return httpx.Response(500)

    client = _client(httpx.MockTransport(handler))
    transport = DeepSeekChatTransport(
        settings=_settings(max_request_bytes=65536),
        client=client,
    )
    with pytest.raises(ModelInputDenied):
        asyncio.run(transport.complete(_request(), call_deadline=float("nan")))
    oversized = StructuredModelRequest(
        task_id=ModelTaskId.ANSWER_GENERATION,
        task_version="answer-v1",
        system_instruction="Return one JSON object.",
        user_payload_json="x" * 70000,
        tools=(),
        tool_mode=StructuredToolMode.NONE,
        output_mode=StructuredOutputMode.JSON_OBJECT,
        max_output_tokens=64,
    )
    with pytest.raises(ModelInputDenied, match="model.provider_request_too_large"):
        asyncio.run(
            transport.complete(
                oversized,
                call_deadline=monotonic() + 2,
            )
        )
    asyncio.run(client.aclose())
    assert calls == 0


def test_http_client_builder_freezes_outbound_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    sentinel_transport = object()
    sentinel_client = object()

    def fake_transport(**kwargs: Any) -> object:
        captured["transport"] = kwargs
        return sentinel_transport

    def fake_client(**kwargs: Any) -> object:
        captured["client"] = kwargs
        return sentinel_client

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", fake_transport)
    monkeypatch.setattr(httpx, "AsyncClient", fake_client)

    assert build_deepseek_http_client(_settings()) is sentinel_client
    assert captured["transport"]["retries"] == 0
    assert captured["transport"]["verify"] is True
    assert captured["client"]["base_url"] == "https://api.deepseek.com"
    assert captured["client"]["trust_env"] is False
    assert captured["client"]["follow_redirects"] is False
    assert captured["client"]["http2"] is False
    assert captured["client"]["timeout"] is None
    assert captured["client"]["headers"] == {
        "Accept": "application/json",
        "Accept-Encoding": "identity",
    }
