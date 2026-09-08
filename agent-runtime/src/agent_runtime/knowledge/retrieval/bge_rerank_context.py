"""DR-KRET-034: local scoring context, separate from original Evidence."""
from __future__ import annotations

from datetime import date
import json
import math
from typing import Never

from agent_runtime.knowledge.retrieval.bge_rerank import BgeRerankAdapter, _unique
from agent_runtime.knowledge.retrieval.contracts import AuthorizedKnowledgeCandidate, RerankScore
from agent_runtime.knowledge.retrieval.http import BoundedHttpRequest, KnowledgeHttpTransport, RetrievalTransportError


def authorized_scoring_text(candidate: AuthorizedKnowledgeCandidate) -> str:
    if (type(candidate.content) is not str or not 1 <= len(candidate.content) <= 4096
            or type(candidate.title) is not str or len(candidate.title) > 256
            or candidate.document_number is not None and (
                type(candidate.document_number) is not str or len(candidate.document_number) > 256)
            or candidate.written_date is not None and type(candidate.written_date) is not date):
        raise RetrievalTransportError("invalid_input")
    parts = [candidate.content]
    for label, value in (("文档标题", candidate.title), ("文号", candidate.document_number),
                         ("成文日期（非生效日期）", candidate.written_date.isoformat() if candidate.written_date else None)):
        if value:
            parts.append(f"{label}：{value}")
    result = "\n".join(parts)
    if len(result) > 4700:
        raise RetrievalTransportError("invalid_input")
    return result


def _reject_constant(value: str) -> Never:
    raise ValueError("knowledge.invalid_json_number")


class ContextualBgeRerankAdapter:
    """One local call; derived text never replaces candidate.content or hash.

    Legacy BgeRerankAdapter is frozen by historical runs. Keep its decoder
    untouched instead of changing its meaning for existing explicit callers.
    """
    __slots__ = ("_transport",)
    INPUT_VERSION = "authorized-body-first-metadata-v1"

    def __init__(self, transport: KnowledgeHttpTransport) -> None:
        self._transport = transport

    async def rerank(
        self, *, query: str, candidates: tuple[AuthorizedKnowledgeCandidate, ...], timeout_s: float,
    ) -> tuple[RerankScore, ...]:
        if not 1 <= len(candidates) <= 40:
            raise RetrievalTransportError("invalid_input")
        documents = [authorized_scoring_text(item) for item in candidates]
        body = json.dumps({"query": query, "documents": documents, "top_n": len(documents), "normalize": True},
                          ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(body) > 2 * 1024 * 1024:
            raise RetrievalTransportError("request_too_large")
        response = await self._transport.send(request=BoundedHttpRequest(method="POST", relative_path="/rerank",
            headers=(("Accept-Encoding", "identity"), ("Content-Type", "application/json")), body=body,
            max_response_bytes=2 * 1024 * 1024), timeout_s=min(timeout_s, 5.0))
        if (response.status_code != 200 or response.content_type != "application/json"
                or response.content_encoding not in (None, "identity") or len(response.body) > 2 * 1024 * 1024):
            raise RetrievalTransportError("invalid_response")
        try:
            value = json.loads(response.body.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_reject_constant)
        except (UnicodeError, ValueError) as exc:
            raise RetrievalTransportError("invalid_response") from exc
        if (type(value) is not dict or set(value) != {"model", "results"}
                or value["model"] != BgeRerankAdapter.MODEL or type(value["results"]) is not list
                or len(value["results"]) != len(candidates)):
            raise RetrievalTransportError("invalid_response")
        scores: list[RerankScore] = []
        seen: set[int] = set()
        for raw in value["results"]:
            if type(raw) is not dict or set(raw) != {"index", "text", "score"}:
                raise RetrievalTransportError("invalid_response")
            index, score = raw["index"], raw["score"]
            if (type(index) is not int or index in seen or not 0 <= index < len(candidates)
                    or raw["text"] != documents[index] or type(score) not in (int, float)):
                raise RetrievalTransportError("invalid_response")
            try:
                finite_score = float(score)
            except OverflowError as exc:
                raise RetrievalTransportError("invalid_response") from exc
            if not math.isfinite(finite_score):
                raise RetrievalTransportError("invalid_response")
            seen.add(index)
            scores.append(RerankScore(candidate_index=index, score=finite_score))
        return tuple(scores)
