from __future__ import annotations

import asyncio
import math
from typing import NoReturn

import httpx

from agent_runtime.capability_api.contracts import canonical_json_bytes
from agent_runtime.model.contracts import (
    InvalidModelOutput,
    ModelInputDenied,
    ModelTransportError,
    StructuredModelRequest,
    StructuredModelResponse,
)
from agent_runtime.model.deepseek.dto import parse_deepseek_response, project_deepseek_request
from agent_runtime.model.deepseek.errors import (
    DeepSeekTransportFailure,
    DeepSeekTransportFailureCategory,
    DeepSeekTransportPhase,
    map_deepseek_failure,
)
from agent_runtime.model.settings import ModelProvider, ModelSettings


def build_deepseek_http_client(settings: ModelSettings) -> httpx.AsyncClient:
    if settings.provider is not ModelProvider.DEEPSEEK or settings.api_key is None:
        raise ValueError("model.deepseek_settings_required")
    limits = httpx.Limits(
        max_connections=settings.max_concurrency,
        max_keepalive_connections=settings.max_concurrency,
    )
    transport = httpx.AsyncHTTPTransport(
        retries=0,
        verify=True,
        limits=limits,
    )
    return httpx.AsyncClient(
        base_url=ModelSettings.BASE_URL,
        transport=transport,
        limits=limits,
        timeout=None,
        trust_env=False,
        follow_redirects=False,
        http2=False,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",
        },
    )


class DeepSeekChatTransport:
    __slots__ = ("_client", "_settings")

    def __init__(self, *, settings: ModelSettings, client: httpx.AsyncClient) -> None:
        if settings.provider is not ModelProvider.DEEPSEEK or settings.api_key is None:
            raise ValueError("model.deepseek_settings_required")
        if not isinstance(client, httpx.AsyncClient):
            raise ValueError("model.invalid_http_client")
        if str(client.base_url).rstrip("/") != ModelSettings.BASE_URL:
            raise ValueError("model.invalid_base_url")
        self._settings = settings
        self._client = client

    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        if (
            not isinstance(call_deadline, (int, float))
            or isinstance(call_deadline, bool)
            or not math.isfinite(call_deadline)
        ):
            raise ModelInputDenied("model.invalid_call_deadline")
        if self._client.is_closed:
            _raise_transport_failure(DeepSeekTransportFailureCategory.TRANSPORT)

        loop = asyncio.get_running_loop()
        remaining = call_deadline - loop.time()
        if remaining <= 0:
            _raise_transport_failure(
                DeepSeekTransportFailureCategory.TIMEOUT,
                phase=DeepSeekTransportPhase.PERMIT,
            )

        projected = project_deepseek_request(request)
        body = canonical_json_bytes(projected.payload)
        if len(body) > self._settings.max_request_bytes:
            raise ModelInputDenied("model.provider_request_too_large")
        timeout = httpx.Timeout(
            connect=min(2.0, remaining),
            pool=min(1.0, remaining),
            read=remaining,
            write=remaining,
        )
        assert self._settings.api_key is not None
        authorization = f"Bearer {self._settings.api_key.reveal_for_authorization_header()}"
        headers = {
            "Authorization": authorization,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "identity",
        }

        try:
            async with asyncio.timeout_at(call_deadline):
                async with self._client.stream(
                    "POST",
                    "/chat/completions",
                    content=body,
                    headers=headers,
                    timeout=timeout,
                ) as response:
                    if response.status_code != 200:
                        _raise_transport_failure(
                            DeepSeekTransportFailureCategory.HTTP,
                            status_code=response.status_code,
                        )
                    _validate_response_headers(response)
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(raw) + len(chunk) > self._settings.max_response_bytes:
                            raise InvalidModelOutput("model.provider_response_too_large")
                        raw.extend(chunk)
                    return parse_deepseek_response(
                        bytes(raw),
                        max_bytes=self._settings.max_response_bytes,
                    )
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            _raise_transport_failure(
                DeepSeekTransportFailureCategory.TIMEOUT,
                phase=DeepSeekTransportPhase.READ,
            )
        except httpx.TimeoutException:
            _raise_transport_failure(
                DeepSeekTransportFailureCategory.TIMEOUT,
                phase=DeepSeekTransportPhase.READ,
            )
        except httpx.RequestError:
            _raise_transport_failure(DeepSeekTransportFailureCategory.TRANSPORT)


def _validate_response_headers(response: httpx.Response) -> None:
    content_type = response.headers.get("Content-Type", "")
    if content_type.split(";", 1)[0].strip().casefold() != "application/json":
        raise InvalidModelOutput("model.provider_content_type_invalid")
    content_encoding = response.headers.get("Content-Encoding", "identity").strip().casefold()
    if content_encoding not in ("", "identity"):
        raise InvalidModelOutput("model.provider_content_encoding_invalid")


def _raise_transport_failure(
    category: DeepSeekTransportFailureCategory,
    *,
    status_code: int | None = None,
    phase: DeepSeekTransportPhase | None = None,
) -> NoReturn:
    failure = DeepSeekTransportFailure(
        category=category,
        status_code=status_code,
        phase=phase,
    )
    raise ModelTransportError(map_deepseek_failure(failure)) from None
