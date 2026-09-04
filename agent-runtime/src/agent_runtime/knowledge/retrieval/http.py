from __future__ import annotations

import asyncio
from dataclasses import dataclass
import time
from typing import Final
from typing import Literal, Protocol
from urllib.parse import urlsplit

import httpx

from agent_runtime.observation import (
    downstream_call_finished,
    downstream_call_started,
    knowledge_http_request_view,
)


_MAX_REQUEST_BYTES: Final = 2 * 1024 * 1024
_MAX_RESPONSE_BYTES: Final = 2 * 1024 * 1024
_ALLOWED_PATHS: Final = frozenset({"/embed", "/rerank", "/es/knowledge/search"})
_ALLOWED_HEADERS: Final = frozenset({"accept-encoding", "authorization", "content-type"})


@dataclass(frozen=True, slots=True, kw_only=True)
class BoundedHttpRequest:
    method: Literal["POST"]
    relative_path: str
    headers: tuple[tuple[str, str], ...]
    body: bytes
    max_response_bytes: int


@dataclass(frozen=True, slots=True, kw_only=True)
class BoundedHttpResponse:
    status_code: int
    content_type: str | None
    content_encoding: str | None
    body: bytes


class KnowledgeHttpTransport(Protocol):
    async def send(self, *, request: BoundedHttpRequest, timeout_s: float) -> BoundedHttpResponse: ...


# Kept as a compatibility alias for existing fake-only tests and callers.
LocalFakeHttpTransport = KnowledgeHttpTransport


class RetrievalTransportError(RuntimeError):
    __slots__ = ("kind",)

    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


def build_knowledge_http_client(base_url: str) -> httpx.AsyncClient:
    """Builds a connection-bounded client for one prevalidated provider origin."""
    _validate_origin(base_url)
    return httpx.AsyncClient(
        base_url=base_url,
        follow_redirects=False,
        trust_env=False,
        limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
        timeout=None,
    )


class HttpxKnowledgeTransport:
    """Executes only the finite Knowledge provider calls with bounded raw responses."""

    __slots__ = ("_client",)

    def __init__(self, client: httpx.AsyncClient) -> None:
        if not isinstance(client, httpx.AsyncClient):
            raise TypeError("knowledge.http_client_invalid")
        self._client = client

    async def send(
        self,
        *,
        request: BoundedHttpRequest,
        timeout_s: float,
    ) -> BoundedHttpResponse:
        _validate_request(request, timeout_s)
        target, operation = _knowledge_target(request.relative_path)
        try:
            request_view = knowledge_http_request_view(request.relative_path, request.body)
        except (UnicodeError, ValueError):
            request_view = {"projectionStatus": "unavailable"}
        observation_id = downstream_call_started(
            target=target,
            operation=operation,
            method=request.method,
            relative_path=request.relative_path,
            request=request_view,
        )
        started = time.monotonic()
        try:
            async with self._client.stream(
                request.method,
                request.relative_path,
                headers=list(request.headers),
                content=request.body,
                timeout=httpx.Timeout(timeout_s),
                follow_redirects=False,
            ) as response:
                declared_length = _content_length(response.headers.get("Content-Length"))
                if declared_length is not None and declared_length > request.max_response_bytes:
                    raise RetrievalTransportError("response_too_large")
                body = bytearray()
                async for chunk in response.aiter_raw():
                    body.extend(chunk)
                    if len(body) > request.max_response_bytes:
                        raise RetrievalTransportError("response_too_large")
                result = BoundedHttpResponse(
                    status_code=response.status_code,
                    content_type=_media_type(response.headers.get("Content-Type")),
                    content_encoding=_content_encoding(response.headers.get("Content-Encoding")),
                    body=bytes(body),
                )
                downstream_call_finished(
                    observation_id,
                    status="completed",
                    http_status=response.status_code,
                    duration_ms=int((time.monotonic() - started) * 1000),
                )
                return result
        except asyncio.CancelledError:
            downstream_call_finished(
                observation_id,
                status="cancelled",
                http_status=None,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            raise
        except httpx.TimeoutException as exc:
            downstream_call_finished(
                observation_id,
                status="timeout",
                http_status=None,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            raise TimeoutError("knowledge.provider_timeout") from exc
        except httpx.RequestError as exc:
            downstream_call_finished(
                observation_id,
                status="transport_failure",
                http_status=None,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            raise RetrievalTransportError("request_failed") from exc
        except RetrievalTransportError as exc:
            downstream_call_finished(
                observation_id,
                status="response_too_large" if exc.kind == "response_too_large" else "protocol_failure",
                http_status=None,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            raise


def _validate_origin(base_url: str) -> None:
    try:
        parsed = urlsplit(base_url)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise ValueError("knowledge.http_origin_invalid") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("knowledge.http_origin_invalid")
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    canonical = f"{parsed.scheme}://{host}" + (f":{port}" if port is not None else "")
    if base_url.rstrip("/") != canonical:
        raise ValueError("knowledge.http_origin_invalid")


def _validate_request(request: BoundedHttpRequest, timeout_s: float) -> None:
    if (
        request.method != "POST"
        or request.relative_path not in _ALLOWED_PATHS
        or type(request.body) is not bytes
        or len(request.body) == 0
        or len(request.body) > _MAX_REQUEST_BYTES
        or type(request.max_response_bytes) is not int
        or not 1 <= request.max_response_bytes <= _MAX_RESPONSE_BYTES
        or type(timeout_s) not in (int, float)
        or isinstance(timeout_s, bool)
        or not 0 < timeout_s <= 5.0
    ):
        raise RetrievalTransportError("invalid_request")
    names: set[str] = set()
    for name, value in request.headers:
        normalized = name.lower()
        if (
            normalized not in _ALLOWED_HEADERS
            or normalized in names
            or not value
            or "\r" in value
            or "\n" in value
        ):
            raise RetrievalTransportError("invalid_request")
        names.add(normalized)
    if names < {"accept-encoding", "content-type"}:
        raise RetrievalTransportError("invalid_request")
    header_map = {name.lower(): value for name, value in request.headers}
    if header_map["accept-encoding"].lower() != "identity" or header_map["content-type"].lower() != "application/json":
        raise RetrievalTransportError("invalid_request")
    if request.relative_path == "/es/knowledge/search" and "authorization" not in names:
        raise RetrievalTransportError("invalid_request")
    if request.relative_path != "/es/knowledge/search" and "authorization" in names:
        raise RetrievalTransportError("invalid_request")


def _content_length(raw: str | None) -> int | None:
    if raw is None:
        return None
    if not raw.isascii() or not raw.isdecimal() or raw != str(int(raw)):
        raise RetrievalTransportError("invalid_response")
    return int(raw)


def _media_type(raw: str | None) -> str | None:
    if raw is None:
        return None
    return raw.split(";", 1)[0].strip().lower()


def _content_encoding(raw: str | None) -> str | None:
    if raw is None:
        return None
    return raw.strip().lower()


def _knowledge_target(relative_path: str) -> tuple[str, str]:
    if relative_path == "/embed":
        return "bge-embedding-service", "knowledge.embedding"
    if relative_path == "/rerank":
        return "bge-rerank-service", "knowledge.rerank"
    if relative_path == "/es/knowledge/search":
        return "es-query-service", "knowledge.search"
    return "knowledge-provider", "unsupported"
