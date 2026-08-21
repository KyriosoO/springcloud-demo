from __future__ import annotations

import asyncio

import pytest

from agent_runtime.business.contracts import (
    BusinessHttpRequest,
    BusinessTransportFailure,
    BusinessTransportFailureKind,
)
from agent_runtime.business.http_client import FakeDomainHttpRequest, FakeDomainHttpResponse, UserJwtBusinessHttpClient
from tests.helpers import ManualCancellationSignal, scope


class FakeTransport:
    def __init__(self) -> None:
        self.requests: list[FakeDomainHttpRequest] = []
        self.closed = 0

    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        self.requests.append(request)
        return FakeDomainHttpResponse(status_code=403, content_type="text/plain", body=b"sensitive body")

    async def aclose(self) -> None:
        self.closed += 1


@pytest.mark.asyncio
async def test_client_forwards_only_original_user_jwt_once_and_drops_error_body() -> None:
    transport = FakeTransport()
    client = UserJwtBusinessHttpClient(transport=transport, max_response_bytes=1024)
    result = await client.execute(
        request=BusinessHttpRequest(method="GET", relative_path="/fake", query=(), json_body=None),
        user_token=scope().context.user_token,
        call_deadline=asyncio.get_running_loop().time() + 2,
        cancellation=ManualCancellationSignal(),
    )

    assert len(transport.requests) == 1
    assert transport.requests[0].authorization == "Bearer header.payload.signature"
    assert result.status_code == 403 and result.body is None
    await client.aclose()
    await client.aclose()
    assert transport.closed == 1


@pytest.mark.asyncio
async def test_client_rejects_oversized_error_body_before_dropping_it() -> None:
    client = UserJwtBusinessHttpClient(transport=FakeTransport(), max_response_bytes=8)

    with pytest.raises(BusinessTransportFailure) as failure:
        await client.execute(
            request=BusinessHttpRequest(method="GET", relative_path="/fake", query=(), json_body=None),
            user_token=scope().context.user_token,
            call_deadline=asyncio.get_running_loop().time() + 2,
            cancellation=ManualCancellationSignal(),
        )

    assert failure.value.kind is BusinessTransportFailureKind.RESPONSE_TOO_LARGE
