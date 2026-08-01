from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


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


class LocalFakeHttpTransport(Protocol):
    async def send(self, *, request: BoundedHttpRequest, timeout_s: float) -> BoundedHttpResponse: ...


class RetrievalTransportError(RuntimeError):
    __slots__ = ("kind",)

    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind

