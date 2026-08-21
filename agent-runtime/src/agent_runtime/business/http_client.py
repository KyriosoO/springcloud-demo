from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

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
