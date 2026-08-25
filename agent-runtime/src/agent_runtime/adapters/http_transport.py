from __future__ import annotations

import httpx

from agent_runtime.business.contracts import (
    BusinessTransportFailure,
    BusinessTransportFailureKind,
)
from agent_runtime.business.http_client import FakeDomainHttpRequest, FakeDomainHttpResponse


class HttpxBusinessDomainTransport:
    """Bounded adapter-side HTTP transport for one code-bound Business service."""

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
