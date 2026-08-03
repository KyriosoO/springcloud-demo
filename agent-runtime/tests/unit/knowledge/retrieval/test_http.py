from __future__ import annotations

import asyncio

import httpx
import pytest

from agent_runtime.knowledge.retrieval.http import (
    BoundedHttpRequest,
    HttpxKnowledgeTransport,
    RetrievalTransportError,
)


class FixedStream(httpx.AsyncByteStream):
    def __init__(self, content: bytes) -> None:
        self._content = content

    async def __aiter__(self):  # type: ignore[no-untyped-def]
        yield self._content


def _request(*, path: str = "/embed", maximum: int = 1024) -> BoundedHttpRequest:
    headers = [("Accept-Encoding", "identity"), ("Content-Type", "application/json")]
    if path == "/es/knowledge/search":
        headers.append(("Authorization", "Bearer opaque-test-token"))
    return BoundedHttpRequest(
        method="POST",
        relative_path=path,
        headers=tuple(headers),
        body=b'{}',
        max_response_bytes=maximum,
    )


def _client(handler: httpx.AsyncBaseTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url="http://127.0.0.1:19999",
        transport=handler,
        follow_redirects=False,
        trust_env=False,
        timeout=None,
    )


@pytest.mark.asyncio
async def test_httpx_transport_preserves_request_and_bounds_response() -> None:
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json; charset=utf-8", "Content-Encoding": "identity"},
            stream=FixedStream(b'{"ok":true}'),
        )

    async with _client(httpx.MockTransport(handler)) as client:
        response = await HttpxKnowledgeTransport(client).send(request=_request(), timeout_s=1.0)

    assert len(captured) == 1
    assert captured[0].url.path == "/embed"
    assert captured[0].headers["Accept-Encoding"] == "identity"
    assert response.content_type == "application/json"
    assert response.content_encoding == "identity"
    assert response.body == b'{"ok":true}'


@pytest.mark.asyncio
async def test_httpx_transport_rejects_declared_or_streamed_oversize_body() -> None:
    async def declared(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Content-Length": "2048"}, content=b"x")

    async with _client(httpx.MockTransport(declared)) as client:
        with pytest.raises(RetrievalTransportError, match="response_too_large"):
            await HttpxKnowledgeTransport(client).send(request=_request(maximum=1024), timeout_s=1.0)

    async def streamed(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=FixedStream(b"x" * 1025))

    async with _client(httpx.MockTransport(streamed)) as client:
        with pytest.raises(RetrievalTransportError, match="response_too_large"):
            await HttpxKnowledgeTransport(client).send(request=_request(maximum=1024), timeout_s=1.0)


@pytest.mark.asyncio
async def test_httpx_transport_never_follows_redirects() -> None:
    paths: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(307, headers={"Location": "/redirected"}, stream=FixedStream(b"redirect"))

    async with _client(httpx.MockTransport(handler)) as client:
        response = await HttpxKnowledgeTransport(client).send(request=_request(), timeout_s=1.0)

    assert response.status_code == 307
    assert paths == ["/embed"]


@pytest.mark.asyncio
async def test_httpx_transport_maps_timeout_and_propagates_cancellation() -> None:
    async def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("bounded timeout")

    async with _client(httpx.MockTransport(timeout)) as client:
        with pytest.raises(TimeoutError, match="knowledge.provider_timeout"):
            await HttpxKnowledgeTransport(client).send(request=_request(), timeout_s=1.0)

    started = asyncio.Event()

    async def wait_forever(_: httpx.Request) -> httpx.Response:
        started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async with _client(httpx.MockTransport(wait_forever)) as client:
        task = asyncio.create_task(HttpxKnowledgeTransport(client).send(request=_request(), timeout_s=1.0))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_httpx_transport_rejects_non_finite_path_and_header_contract() -> None:
    async def unreachable(_: httpx.Request) -> httpx.Response:
        raise AssertionError("transport must not be called")

    async with _client(httpx.MockTransport(unreachable)) as client:
        transport = HttpxKnowledgeTransport(client)
        with pytest.raises(RetrievalTransportError, match="invalid_request"):
            await transport.send(request=_request(path="/other"), timeout_s=1.0)
        with pytest.raises(RetrievalTransportError, match="invalid_request"):
            await transport.send(request=_request(path="/es/knowledge/search"), timeout_s=6.0)
