from __future__ import annotations

import asyncio
import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_INVOKE_PATH = "/internal/v1/agent-runs:invoke"


class RequestBodyTooLarge(Exception):
    pass


class RuntimeCapacityExceeded(Exception):
    pass


async def _send_protocol_error(send: Send, status: int) -> None:
    body = json.dumps(
        {"contractVersion": 1, "code": "runtime.protocol_error"},
        separators=(",", ":"),
    ).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class MaxBodyBytesMiddleware:
    __slots__ = ("_app", "_max_body_bytes")

    def __init__(self, app: ASGIApp, *, max_body_bytes: int) -> None:
        self._app = app
        self._max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") != _INVOKE_PATH:
            await self._app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", ())}
        content_type = headers.get(b"content-type", b"").split(b";", 1)[0].strip().lower()
        if content_type != b"application/json":
            await _send_protocol_error(send, 415)
            return
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                length = int(content_length)
            except ValueError:
                await _send_protocol_error(send, 400)
                return
            if length < 0:
                await _send_protocol_error(send, 400)
                return
            if length > self._max_body_bytes:
                await _send_protocol_error(send, 413)
                return

        received = 0
        body_exceeded = False
        replacement_sent = False

        async def limited_receive() -> Message:
            nonlocal body_exceeded, received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._max_body_bytes:
                    body_exceeded = True
                    raise RequestBodyTooLarge
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal replacement_sent
            if body_exceeded:
                if not replacement_sent and message["type"] == "http.response.start":
                    replacement_sent = True
                    await _send_protocol_error(send, 413)
                return
            await send(message)

        try:
            await self._app(scope, limited_receive, guarded_send)
        except RequestBodyTooLarge:
            if not replacement_sent:
                await _send_protocol_error(send, 413)


class RuntimeRequestLease:
    __slots__ = ("_limiter", "_released")

    def __init__(self, limiter: RuntimeRequestLimiter) -> None:
        self._limiter = limiter
        self._released = False

    async def release(self) -> None:
        if not self._released:
            self._released = True
            await self._limiter.release()

    async def __aenter__(self) -> RuntimeRequestLease:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.release()


class RuntimeRequestLimiter:
    __slots__ = ("_in_flight", "_lock", "_maximum")

    def __init__(self, maximum: int) -> None:
        if not 1 <= maximum <= 32:
            raise ValueError("runtime.limiter_invalid")
        self._maximum = maximum
        self._in_flight = 0
        self._lock = asyncio.Lock()

    @property
    def in_flight(self) -> int:
        return self._in_flight

    async def try_acquire(self) -> RuntimeRequestLease:
        async with self._lock:
            if self._in_flight >= self._maximum:
                raise RuntimeCapacityExceeded
            self._in_flight += 1
        return RuntimeRequestLease(self)

    async def release(self) -> None:
        async with self._lock:
            if self._in_flight <= 0:
                raise RuntimeError("runtime.limiter_release_invariant")
            self._in_flight -= 1
