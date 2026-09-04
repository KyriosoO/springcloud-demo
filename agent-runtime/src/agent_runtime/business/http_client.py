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
from agent_runtime.observation import (
    business_http_request_view,
    downstream_call_finished,
    downstream_call_started,
    safe_business_relative_path,
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
        target, operation = _business_target(request.relative_path)
        try:
            request_view = business_http_request_view(
                request.relative_path,
                None if request.json_body is None else request.json_body.content,
                request.query,
            )
        except (UnicodeError, ValueError):
            request_view = {"projectionStatus": "unavailable"}
        observation_id = downstream_call_started(
            target=target,
            operation=operation,
            method=request.method,
            relative_path=safe_business_relative_path(request.relative_path),
            request=request_view,
        )
        started = loop.time()
        try:
            async with asyncio.timeout_at(call_deadline):
                response = await self._transport.send(outbound)
        except asyncio.CancelledError:
            downstream_call_finished(
                observation_id,
                status="cancelled",
                http_status=None,
                duration_ms=int((loop.time() - started) * 1000),
            )
            raise
        except TimeoutError as exc:
            downstream_call_finished(
                observation_id,
                status="timeout",
                http_status=None,
                duration_ms=int((loop.time() - started) * 1000),
            )
            raise BusinessTransportFailure(BusinessTransportFailureKind.TIMEOUT) from exc
        except BusinessTransportFailure as exc:
            downstream_call_finished(
                observation_id,
                status=_business_failure_status(exc.kind),
                http_status=None,
                duration_ms=int((loop.time() - started) * 1000),
            )
            raise
        except Exception as exc:
            downstream_call_finished(
                observation_id,
                status="transport_failure",
                http_status=None,
                duration_ms=int((loop.time() - started) * 1000),
            )
            raise BusinessTransportFailure(BusinessTransportFailureKind.TLS_OR_CONNECT) from exc
        if cancellation.is_cancelled():
            downstream_call_finished(
                observation_id,
                status="cancelled",
                http_status=None,
                duration_ms=int((loop.time() - started) * 1000),
            )
            raise BusinessTransportFailure(BusinessTransportFailureKind.TIMEOUT)
        if len(response.body) > self._max_response_bytes:
            downstream_call_finished(
                observation_id,
                status="response_too_large",
                http_status=None,
                duration_ms=int((loop.time() - started) * 1000),
            )
            raise BusinessTransportFailure(BusinessTransportFailureKind.RESPONSE_TOO_LARGE)
        downstream_call_finished(
            observation_id,
            status="completed",
            http_status=response.status_code,
            duration_ms=int((loop.time() - started) * 1000),
        )
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


def _business_target(relative_path: str) -> tuple[str, str]:
    if relative_path == "/employees/es/search":
        return "employee-service", "employee.search"
    if relative_path == "/employees/es/vector-search":
        return "employee-service", "employee.semantic_search"
    if relative_path == "/txn/search":
        return "mq-procedure-service", "transaction.search"
    return "business-service", "unsupported"


def _business_failure_status(kind: BusinessTransportFailureKind) -> str:
    if kind is BusinessTransportFailureKind.PROTOCOL:
        return "protocol_failure"
    return kind.value
