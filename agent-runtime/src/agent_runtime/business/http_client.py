from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

import httpx

from agent_runtime.capability_api.contracts import CancellationSignal, OpaqueUserToken
from agent_runtime.business.contracts import (
    BoundedBusinessHttpResponse,
    BusinessHttpRequest,
    BusinessTransportFailure,
    BusinessTransportFailureKind,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class FakeDomainHttpRequest:
    request: BusinessHttpRequest
    authorization: str
    accept_encoding: str = "identity"
    content_type: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class FakeDomainHttpResponse:
    status_code: int
    content_type: str | None
    body: bytes


class FakeDomainTransport(Protocol):
    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse: ...
    async def aclose(self) -> None: ...


class HttpxBusinessDomainTransport:
    """Bounded HTTP transport for one code-bound Business service."""

    __slots__ = ("_allowed_paths", "_client", "_max_response_bytes")

    def __init__(
        self,
        *,
        base_endpoint: str,
        allowed_paths: frozenset[str],
        max_response_bytes: int,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not allowed_paths or any(not path.startswith("/") for path in allowed_paths):
            raise ValueError("business.invalid_transport_paths")
        if type(max_response_bytes) is not int or max_response_bytes <= 0:
            raise ValueError("business.invalid_transport_response_limit")
        if client is not None and str(client.base_url).rstrip("/") != base_endpoint.rstrip("/"):
            raise ValueError("business.invalid_transport_endpoint")
        self._allowed_paths = frozenset(allowed_paths)
        self._max_response_bytes = max_response_bytes
        self._client = client or httpx.AsyncClient(
            base_url=base_endpoint,
            follow_redirects=False,
            trust_env=False,
            timeout=None,
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
        )

    async def send(self, outbound: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        request = outbound.request
        if request.method != "POST" or request.relative_path not in self._allowed_paths:
            raise BusinessTransportFailure(BusinessTransportFailureKind.PROTOCOL)
        headers = {
            "Accept-Encoding": "identity",
            "Authorization": outbound.authorization,
        }
        if outbound.content_type is not None:
            headers["Content-Type"] = outbound.content_type
        content = request.json_body.content if request.json_body is not None else None
        async with self._client.stream(
            request.method,
            request.relative_path,
            params=request.query,
            headers=headers,
            content=content,
            follow_redirects=False,
        ) as response:
            body = bytearray()
            if response.is_stream_consumed:
                body.extend(response.content)
                if len(body) > self._max_response_bytes:
                    raise BusinessTransportFailure(BusinessTransportFailureKind.RESPONSE_TOO_LARGE)
            else:
                async for chunk in response.aiter_raw():
                    body.extend(chunk)
                    if len(body) > self._max_response_bytes:
                        raise BusinessTransportFailure(
                            BusinessTransportFailureKind.RESPONSE_TOO_LARGE
                        )
            return FakeDomainHttpResponse(
                status_code=response.status_code,
                content_type=response.headers.get("Content-Type"),
                body=bytes(body),
            )

    async def aclose(self) -> None:
        await self._client.aclose()


class UserJwtBusinessHttpClient:
    __slots__ = ("_closed", "_max_response_bytes", "_transport")

    def __init__(self, *, transport: FakeDomainTransport, max_response_bytes: int) -> None:
        self._transport = transport
        self._max_response_bytes = max_response_bytes
        self._closed = False

    async def execute(
        self,
        *,
        request: BusinessHttpRequest,
        user_token: OpaqueUserToken,
        call_deadline: float,
        cancellation: CancellationSignal,
    ) -> BoundedBusinessHttpResponse:
        if self._closed:
            raise BusinessTransportFailure(BusinessTransportFailureKind.PROTOCOL)
        loop = asyncio.get_running_loop()
        if cancellation.is_cancelled() or call_deadline - loop.time() <= 0.1:
            raise BusinessTransportFailure(BusinessTransportFailureKind.TIMEOUT)
        outbound = FakeDomainHttpRequest(
            request=request,
            authorization=f"Bearer {user_token.reveal_for_outbound()}",
            content_type="application/json" if request.json_body is not None else None,
        )
        try:
            async with asyncio.timeout_at(call_deadline):
                response = await self._transport.send(outbound)
        except asyncio.CancelledError:
            raise
        except TimeoutError as exc:
            raise BusinessTransportFailure(BusinessTransportFailureKind.TIMEOUT) from exc
        except BusinessTransportFailure:
            raise
        except Exception as exc:
            raise BusinessTransportFailure(BusinessTransportFailureKind.TLS_OR_CONNECT) from exc
        if cancellation.is_cancelled():
            raise BusinessTransportFailure(BusinessTransportFailureKind.TIMEOUT)
        if len(response.body) > self._max_response_bytes:
            raise BusinessTransportFailure(BusinessTransportFailureKind.RESPONSE_TOO_LARGE)
        body: bytes | None = None
        if 200 <= response.status_code < 300 and response.status_code != 204:
            body = bytes(response.body)
        return BoundedBusinessHttpResponse(
            status_code=response.status_code,
            content_type=response.content_type,
            body=body,
        )

    async def aclose(self) -> None:
        if not self._closed:
            self._closed = True
            await self._transport.aclose()
