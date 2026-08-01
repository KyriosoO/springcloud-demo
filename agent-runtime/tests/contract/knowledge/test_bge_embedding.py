from __future__ import annotations

import json

import pytest

from agent_runtime.knowledge.retrieval.bge_embedding import BgeM3EmbeddingAdapter
from agent_runtime.knowledge.retrieval.http import BoundedHttpResponse, RetrievalTransportError
from tests.retrieval_helpers import FakeTransport


@pytest.mark.asyncio
async def test_embedding_wire_is_exact_and_dimension_is_1024() -> None:
    transport = FakeTransport(BoundedHttpResponse(status_code=200, content_type="application/json", content_encoding=None, body=json.dumps({"dim": 1024, "vectors": [[0.0] * 1024]}, separators=(",", ":")).encode()))
    vector = await BgeM3EmbeddingAdapter(transport).embed(text="增值税政策", timeout_s=4)

    assert len(vector) == 1024
    assert json.loads(transport.requests[0].body) == {"texts": ["增值税政策"]}
    assert transport.requests[0].relative_path == "/embed"


@pytest.mark.asyncio
async def test_embedding_rejects_non_finite_or_wrong_dimension() -> None:
    transport = FakeTransport(BoundedHttpResponse(status_code=200, content_type="application/json", content_encoding=None, body=b'{"dim":1024,"vectors":[[1.0]]}'))
    with pytest.raises(RetrievalTransportError, match="invalid_response"):
        await BgeM3EmbeddingAdapter(transport).embed(text="税", timeout_s=1)

