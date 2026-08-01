from __future__ import annotations

import json
import math

from agent_runtime.knowledge.retrieval.contracts import AuthorizedKnowledgeCandidate, RerankScore
from agent_runtime.knowledge.retrieval.http import BoundedHttpRequest, LocalFakeHttpTransport, RetrievalTransportError


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("knowledge.duplicate_json_key")
        result[key] = value
    return result


class BgeRerankAdapter:
    __slots__ = ("_transport",)
    MODEL = "BAAI/bge-reranker-v2-m3"

    def __init__(self, transport: LocalFakeHttpTransport) -> None:
        self._transport = transport

    async def rerank(
        self,
        *,
        query: str,
        candidates: tuple[AuthorizedKnowledgeCandidate, ...],
        timeout_s: float,
    ) -> tuple[RerankScore, ...]:
        if not 1 <= len(candidates) <= 80:
            raise RetrievalTransportError("invalid_input")
        documents = [item.content for item in candidates]
        body = json.dumps(
            {"query": query, "documents": documents, "top_n": len(documents), "normalize": True},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(body) > 2 * 1024 * 1024:
            raise RetrievalTransportError("request_too_large")
        response = await self._transport.send(
            request=BoundedHttpRequest(
                method="POST", relative_path="/rerank",
                headers=(("Accept-Encoding", "identity"), ("Content-Type", "application/json")),
                body=body, max_response_bytes=2 * 1024 * 1024,
            ),
            timeout_s=min(timeout_s, 5.0),
        )
        if response.status_code != 200 or response.content_type != "application/json" or response.content_encoding not in (None, "identity") or len(response.body) > 2 * 1024 * 1024:
            raise RetrievalTransportError("invalid_response")
        try:
            value = json.loads(response.body.decode("utf-8"), object_pairs_hook=_unique)
        except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise RetrievalTransportError("invalid_response") from exc
        if type(value) is not dict or set(value) != {"model", "results"} or value.get("model") != self.MODEL:
            raise RetrievalTransportError("invalid_response")
        results = value.get("results")
        if type(results) is not list or len(results) != len(candidates):
            raise RetrievalTransportError("invalid_response")
        scores: list[RerankScore] = []
        seen: set[int] = set()
        for raw in results:
            if type(raw) is not dict or set(raw) != {"index", "text", "score"}:
                raise RetrievalTransportError("invalid_response")
            index, text, score = raw["index"], raw["text"], raw["score"]
            if type(index) is not int or index in seen or not 0 <= index < len(candidates):
                raise RetrievalTransportError("invalid_response")
            if text != documents[index] or type(score) not in (int, float) or isinstance(score, bool) or not math.isfinite(score):
                raise RetrievalTransportError("invalid_response")
            seen.add(index)
            scores.append(RerankScore(candidate_index=index, score=float(score)))
        if seen != set(range(len(candidates))):
            raise RetrievalTransportError("invalid_response")
        return tuple(scores)

