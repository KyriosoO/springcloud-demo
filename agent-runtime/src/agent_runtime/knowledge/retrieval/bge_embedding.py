from __future__ import annotations

import json
import math

from agent_runtime.knowledge.retrieval.http import BoundedHttpRequest, LocalFakeHttpTransport, RetrievalTransportError


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("knowledge.duplicate_json_key")
        result[key] = value
    return result


class BgeM3EmbeddingAdapter:
    __slots__ = ("_transport",)

    def __init__(self, transport: LocalFakeHttpTransport) -> None:
        self._transport = transport

    async def embed(self, *, text: str, timeout_s: float) -> tuple[float, ...]:
        if not isinstance(text, str) or not 1 <= len(text) <= 1024:
            raise RetrievalTransportError("invalid_input")
        body = json.dumps({"texts": [text]}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(body) > 8192:
            raise RetrievalTransportError("request_too_large")
        response = await self._transport.send(
            request=BoundedHttpRequest(
                method="POST",
                relative_path="/embed",
                headers=(("Accept-Encoding", "identity"), ("Content-Type", "application/json")),
                body=body,
                max_response_bytes=65536,
            ),
            timeout_s=min(timeout_s, 3.0),
        )
        if response.status_code != 200 or response.content_type != "application/json" or response.content_encoding not in (None, "identity") or len(response.body) > 65536:
            raise RetrievalTransportError("invalid_response")
        try:
            value = json.loads(response.body.decode("utf-8"), object_pairs_hook=_unique)
        except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise RetrievalTransportError("invalid_response") from exc
        if type(value) is not dict or set(value) != {"dim", "vectors"} or value.get("dim") != 1024:
            raise RetrievalTransportError("invalid_response")
        vectors = value.get("vectors")
        if type(vectors) is not list or len(vectors) != 1 or type(vectors[0]) is not list or len(vectors[0]) != 1024:
            raise RetrievalTransportError("invalid_response")
        if any(type(item) not in (int, float) or isinstance(item, bool) or not math.isfinite(item) for item in vectors[0]):
            raise RetrievalTransportError("invalid_response")
        return tuple(float(item) for item in vectors[0])

