"""Current typed adapters + new strategy, in-memory transport only (not Spring UAT)."""
import hashlib
import json

import pytest

from agent_runtime.knowledge.contracts import RetrievalStageKind
from agent_runtime.knowledge.retrieval.bge_embedding import BgeM3EmbeddingAdapter
from agent_runtime.knowledge.retrieval.bge_rerank_context import ContextualBgeRerankAdapter
from agent_runtime.knowledge.retrieval.es_adapter import EsKnowledgeSearchAdapter
from agent_runtime.knowledge.retrieval.http import BoundedHttpResponse
from agent_runtime.knowledge.retrieval.minimal_stage import MinimalKnowledgeRetrievalStage
from tests.unit.knowledge.test_minimal_retrieval_plan import make_plan
from tests.unit.knowledge.retrieval.test_minimal_stage import context


class Transport:
    def __init__(self, es_status=200):
        self.requests = []
        self.es_status = es_status

    async def send(self, *, request, timeout_s):
        self.requests.append(request)
        assert 0 < timeout_s <= 5
        raw = json.loads(request.body)
        status = 200
        if request.relative_path == "/embed":
            response = {"dim": 1024, "vectors": [[0.0] * 1024]}
        elif request.relative_path == "/rerank":
            assert raw["normalize"] is True and raw["top_n"] == len(raw["documents"])
            assert all(text.startswith("合成税法正文\n文档标题：") for text in raw["documents"])
            response = {"model": "BAAI/bge-reranker-v2-m3", "results": [
                {"index": i, "text": text, "score": 0.4} for i, text in enumerate(raw["documents"])]}
        else:
            assert request.relative_path == "/es/knowledge/search"
            assert set(raw) == {"schemaVersion", "logicalDomainId", "retrievalProfileId", "path", "queryText", "queryVector", "limit"}
            status = self.es_status
            response = {"schemaVersion": 1, "logicalDomainId": raw["logicalDomainId"],
                "retrievalProfileId": raw["retrievalProfileId"], "path": raw["path"],
                "profileVersion": "tax-knowledge-search-v1", "indexSnapshotId": "a" * 64,
                "readPolicyVersion": "tax-public-authenticated-v1", "truncated": False,
                "candidates": [{"documentId": "d1", "chunkId": "c1", "logicalDomainId": raw["logicalDomainId"],
                    "title": "合成标题", "content": "合成税法正文", "sourceUrl": None, "documentNumber": None,
                    "writtenDate": None, "materialType": "tax_policy", "sourceRank": 1,
                    "contentSha256": hashlib.sha256("合成税法正文".encode()).hexdigest(), "policyRef": "policy-doc-v1"}]}
        return BoundedHttpResponse(status_code=status, content_type="application/json", content_encoding=None,
            body=json.dumps(response, ensure_ascii=False).encode())


@pytest.mark.parametrize("status,expected", [(200, RetrievalStageKind.SUCCESS), (403, RetrievalStageKind.FORBIDDEN),
    (401, RetrievalStageKind.DOWNSTREAM_FAILURE), (503, RetrievalStageKind.DOWNSTREAM_FAILURE),
    (500, RetrievalStageKind.DOWNSTREAM_FAILURE)])
async def test_current_typed_protocol_and_jwt_only_to_read_authority(status, expected):
    plan, ctx, transport = make_plan(), context(), Transport(status)
    stage = MinimalKnowledgeRetrievalStage(search=EsKnowledgeSearchAdapter(transport),
        embedding=BgeM3EmbeddingAdapter(transport), rerank=ContextualBgeRerankAdapter(transport), settings=plan.settings)
    result = await stage.execute(plan=plan, context=ctx, timeout_s=20)
    assert result.kind is expected
    paths = [request.relative_path for request in transport.requests]
    assert paths.count("/embed") == 1 and paths.count("/es/knowledge/search") == 4
    assert paths.count("/rerank") == (2 if status == 200 else 0)
    for request in transport.requests:
        headers = dict(request.headers)
        if request.relative_path == "/es/knowledge/search":
            assert headers["Authorization"] == "Bearer " + ctx.user_token.reveal_for_outbound()
        else:
            assert "Authorization" not in headers
        raw = json.loads(request.body)
        if request.relative_path == "/rerank":
            assert raw["query"] == plan.original_question
    if status == 200:
        assert result.batch.candidates[0].candidate.content == "合成税法正文"
        assert "文档标题" not in result.batch.candidates[0].candidate.content
