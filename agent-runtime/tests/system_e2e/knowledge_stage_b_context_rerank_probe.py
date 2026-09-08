"""P3 §20.55: paired local scoring experiment, never a production/UAT entry.

Reuse the frozen probe in a scoped test patch; neither its bytes nor production
objects are changed. Derived scoring text is distinct from authorized Evidence.
"""
from __future__ import annotations

from datetime import date
import hashlib
import json
import math
from pathlib import Path
from unittest.mock import patch

from agent_runtime.knowledge.retrieval.bge_rerank import BgeRerankAdapter, _unique
from agent_runtime.knowledge.retrieval.contracts import AuthorizedKnowledgeCandidate, RerankScore
from agent_runtime.knowledge.retrieval.http import BoundedHttpRequest, KnowledgeHttpTransport, RetrievalTransportError
from tests.system_e2e import knowledge_stage_b_quality_v3_probe as probe

BASE_SHA = "618bae17d518623edd526baf861d2249920bb475f553aa8593006bb5d45c6542"
LIMITS = {"search": 22, "embedding": 11, "rerank": 36}
PER_CASE = {"search": 4, "embedding": 2, "rerank": 8}
REPRESENTATION = "authorized-body-first-metadata-v1"


def scoring_text(candidate: AuthorizedKnowledgeCandidate) -> str:
    """Existing typed metadata only; written date never becomes validity."""
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


class ContextScorer:
    """Test-only HTTP peer: validate echo against derived text, not Evidence."""
    def __init__(self, transport: KnowledgeHttpTransport):
        self.transport = transport

    async def rerank(self, *, query, candidates, timeout_s):
        if not 1 <= len(candidates) <= 40:
            raise RetrievalTransportError("invalid_input")
        documents = [scoring_text(item) for item in candidates]
        body = json.dumps({"query": query, "documents": documents, "top_n": len(documents), "normalize": True},
                          ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(body) > 2 * 1024 * 1024:
            raise RetrievalTransportError("request_too_large")
        response = await self.transport.send(request=BoundedHttpRequest(method="POST", relative_path="/rerank",
            headers=(("Accept-Encoding", "identity"), ("Content-Type", "application/json")), body=body,
            max_response_bytes=2 * 1024 * 1024), timeout_s=min(timeout_s, 5.0))
        if (response.status_code != 200 or response.content_type != "application/json"
                or response.content_encoding not in (None, "identity") or len(response.body) > 2 * 1024 * 1024):
            raise RetrievalTransportError("invalid_response")
        try:
            value = json.loads(response.body.decode("utf-8"), object_pairs_hook=_unique,
                               parse_constant=probe._reject_constant)
        except (UnicodeError, ValueError) as exc:
            raise RetrievalTransportError("invalid_response") from exc
        if (type(value) is not dict or set(value) != {"model", "results"}
                or value["model"] != BgeRerankAdapter.MODEL or type(value["results"]) is not list
                or len(value["results"]) != len(candidates)):
            raise RetrievalTransportError("invalid_response")
        scores, seen = [], set()
        for raw in value["results"]:
            if type(raw) is not dict or set(raw) != {"index", "text", "score"}:
                raise RetrievalTransportError("invalid_response")
            index, score = raw["index"], raw["score"]
            if (type(index) is not int or index in seen or not 0 <= index < len(candidates)
                    or raw["text"] != documents[index] or type(score) not in (int, float) or not math.isfinite(score)):
                raise RetrievalTransportError("invalid_response")
            seen.add(index)
            scores.append(RerankScore(candidate_index=index, score=float(score)))
        return tuple(scores)


class PairedObservedRerank(probe.ObservedRerank):
    async def rerank(self, **kwargs):
        # Access is confined to this frozen test seam. Production keeps raw BGE.
        baseline = await self.delegate.rerank(**kwargs)
        ordinal = 1 + sum(row["stage"] == "rerank" for row in self.rows)
        self.rows.append({"stage": "rerank_raw", "ordinal": ordinal, "candidates": [
            {**probe.identity(kwargs["candidates"][s.candidate_index]), "score": s.score} for s in baseline]})
        contextual = await ContextScorer(self.delegate._transport).rerank(**kwargs)
        self.rows.append({"stage": "rerank", "ordinal": ordinal, "candidates": [
            {**probe.identity(kwargs["candidates"][s.candidate_index]), "score": s.score} for s in contextual]})
        return contextual


def main():
    if hashlib.sha256(Path(probe.__file__).read_bytes()).hexdigest() != BASE_SHA:
        raise ValueError("context_probe_base_changed")
    original_emit = probe.emit_line
    def emit(stream, value):
        value = {**value, "experiment": REPRESENTATION, "rankedArm": "context"}
        if value["event"] == "prepared":
            value["experimentSourceSha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            value["pairedRawScoring"] = True
        original_emit(stream, value)
    # Patches exist only inside this standalone, single-run diagnostic process.
    with patch.object(probe, "ObservedRerank", PairedObservedRerank), patch.object(probe, "LIMITS", LIMITS), \
            patch.object(probe, "PER_CASE", PER_CASE), patch.object(probe, "emit_line", emit):
        return probe.main()


if __name__ == "__main__":
    raise SystemExit(main())
