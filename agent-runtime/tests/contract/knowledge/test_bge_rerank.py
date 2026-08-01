from __future__ import annotations

import json

import pytest

from agent_runtime.knowledge.retrieval.bge_rerank import BgeRerankAdapter
from agent_runtime.knowledge.retrieval.http import BoundedHttpResponse, RetrievalTransportError
from tests.retrieval_helpers import FakeTransport, candidate


@pytest.mark.asyncio
async def test_rerank_request_and_echo_binding_are_exact() -> None:
    item = candidate()
    response = {"model": "BAAI/bge-reranker-v2-m3", "results": [{"index": 0, "text": item.content, "score": 0.9}]}
    transport = FakeTransport(BoundedHttpResponse(status_code=200, content_type="application/json", content_encoding="identity", body=json.dumps(response, ensure_ascii=False).encode()))

    scores = await BgeRerankAdapter(transport).rerank(query="税务", candidates=(item,), timeout_s=6)

    request = json.loads(transport.requests[0].body)
    assert request == {"query": "税务", "documents": [item.content], "top_n": 1, "normalize": True}
    assert "model" not in request
    assert scores[0].candidate_index == 0


@pytest.mark.asyncio
async def test_rerank_rejects_mismatched_echo_text() -> None:
    item = candidate()
    response = {"model": "BAAI/bge-reranker-v2-m3", "results": [{"index": 0, "text": "other", "score": 0.9}]}
    transport = FakeTransport(BoundedHttpResponse(status_code=200, content_type="application/json", content_encoding=None, body=json.dumps(response).encode()))
    with pytest.raises(RetrievalTransportError, match="invalid_response"):
        await BgeRerankAdapter(transport).rerank(query="税务", candidates=(item,), timeout_s=1)

