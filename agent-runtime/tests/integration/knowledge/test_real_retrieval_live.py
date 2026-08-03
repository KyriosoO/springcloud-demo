from __future__ import annotations

import asyncio
import hashlib
import os
from collections.abc import Mapping
from typing import cast

import httpx
import pytest

from agent_runtime.capability_api.contracts import OpaqueUserToken
from agent_runtime.knowledge.contracts import (
    KnowledgeRetrievalContext,
    KnowledgeRetrievalPlan,
    RetrievalPath,
    RetrievalPlanItem,
    RetrievalStageKind,
)
from agent_runtime.knowledge.retrieval.bge_embedding import BgeM3EmbeddingAdapter
from agent_runtime.knowledge.retrieval.bge_rerank import BgeRerankAdapter
from agent_runtime.knowledge.retrieval.contracts import (
    AuthorizedKnowledgeCandidate,
    KnowledgePathRequest,
    PathResultKind,
    RerankScore,
)
from agent_runtime.knowledge.retrieval.es_adapter import EsKnowledgeSearchAdapter
from agent_runtime.knowledge.retrieval.http import HttpxKnowledgeTransport, build_knowledge_http_client
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from tests.helpers import ManualCancellationSignal


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_KNOWLEDGE_RETRIEVAL_LIVE") != "1",
    reason="requires explicit local Knowledge retrieval live opt-in",
)

_QUESTION = "增值税相关税收法规政策"


def _required(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"knowledge.live_env_missing:{name}")
    return value


def _plan() -> KnowledgeRetrievalPlan:
    return KnowledgeRetrievalPlan(
        items=tuple(
            RetrievalPlanItem(
                logical_domain_id=domain,
                path=path,
                query_text=_QUESTION,
                candidate_limit=5,
                ordinal=ordinal,
            )
            for ordinal, (domain, path) in enumerate(
                (
                    ("tax.policy", RetrievalPath.KEYWORD),
                    ("tax.policy", RetrievalPath.VECTOR),
                    ("tax.law", RetrievalPath.KEYWORD),
                    ("tax.law", RetrievalPath.VECTOR),
                ),
                1,
            )
        ),
        selected_domain_ids=("tax.policy", "tax.law"),
        config_version="knowledge-flow-config-v1",
    )


def _context(token: str) -> KnowledgeRetrievalContext:
    return KnowledgeRetrievalContext(
        request_id="knowledge-live-request",
        correlation_id="knowledge-live-correlation",
        subject="knowledge-live-user",
        user_token=OpaqueUserToken.from_raw(token),
        deadline_monotonic=asyncio.get_running_loop().time() + 20.0,
        cancellation=ManualCancellationSignal(),
    )


class CountingRerank:
    def __init__(self, delegate: BgeRerankAdapter) -> None:
        self._delegate = delegate
        self.calls = 0

    async def rerank(
        self,
        *,
        query: str,
        candidates: tuple[AuthorizedKnowledgeCandidate, ...],
        timeout_s: float,
    ) -> tuple[RerankScore, ...]:
        self.calls += 1
        return await self._delegate.rerank(query=query, candidates=candidates, timeout_s=timeout_s)


def _stage(
    search: EsKnowledgeSearchAdapter,
    embedding: BgeM3EmbeddingAdapter,
    rerank: CountingRerank,
) -> DefaultKnowledgeRetrievalStage:
    return DefaultKnowledgeRetrievalStage(
        search=search,
        embedding=embedding,
        rerank=rerank,
        final_candidates=10,
    )


@pytest.mark.asyncio
async def test_admin_and_viewer_complete_real_four_path_retrieval() -> None:
    es_base = _required("AGENT_KNOWLEDGE_ES_BASE_URL")
    embedding_base = _required("AGENT_KNOWLEDGE_EMBEDDING_BASE_URL")
    rerank_base = _required("AGENT_KNOWLEDGE_RERANK_BASE_URL")
    expected_snapshots = {
        _required("AGENT_KNOWLEDGE_POLICY_SNAPSHOT_ID"),
        _required("AGENT_KNOWLEDGE_LAW_SNAPSHOT_ID"),
    }
    async with (
        build_knowledge_http_client(es_base) as es_client,
        build_knowledge_http_client(embedding_base) as embedding_client,
        build_knowledge_http_client(rerank_base) as rerank_client,
    ):
        search = EsKnowledgeSearchAdapter(HttpxKnowledgeTransport(es_client))
        embedding = BgeM3EmbeddingAdapter(HttpxKnowledgeTransport(embedding_client))
        vector = await embedding.embed(text=_QUESTION, timeout_s=3.0)
        for domain, profile in (("tax.policy", "tax-policy-v1"), ("tax.law", "tax-law-v1")):
            for path in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR):
                path_result = await search.search(
                    request=KnowledgePathRequest(
                        logical_domain_id=domain,
                        retrieval_profile_id=profile,
                        path=path,
                        query_text=_QUESTION if path is RetrievalPath.KEYWORD else None,
                        query_vector=vector if path is RetrievalPath.VECTOR else None,
                        candidate_limit=5,
                    ),
                    context=_context(_required("AGENT_KNOWLEDGE_ADMIN_JWT")),
                    timeout_s=5.0,
                )
                summary: tuple[object, ...] = (
                    domain,
                    path.value,
                    path_result.kind.value,
                    path_result.failure.value if path_result.failure else None,
                )
                if path_result.kind is not PathResultKind.CANDIDATES:
                    raw = await es_client.post(
                        "/es/knowledge/search",
                        headers={"Authorization": f"Bearer {_required('AGENT_KNOWLEDGE_ADMIN_JWT')}"},
                        json={
                            "schemaVersion": 1,
                            "logicalDomainId": domain,
                            "retrievalProfileId": profile,
                            "path": path.value,
                            "queryText": _QUESTION if path is RetrievalPath.KEYWORD else None,
                            "queryVector": list(vector) if path is RetrievalPath.VECTOR else None,
                            "limit": 5,
                        },
                    )
                    summary += (_safe_response_shape(raw),)
                assert path_result.kind is PathResultKind.CANDIDATES, summary
        for token_name in ("AGENT_KNOWLEDGE_ADMIN_JWT", "AGENT_KNOWLEDGE_VIEWER_JWT"):
            rerank = CountingRerank(BgeRerankAdapter(HttpxKnowledgeTransport(rerank_client)))
            result = await _stage(search, embedding, rerank).execute(
                plan=_plan(),
                context=_context(_required(token_name)),
                timeout_s=15.0,
            )

            assert result.kind is RetrievalStageKind.SUCCESS
            assert result.batch is not None and result.coverage is not None
            failure_summary = tuple(
                (item.logical_domain_id, item.path.value, item.failure_kind.value)
                for item in result.coverage.failed_paths
            )
            assert result.coverage.complete and not result.coverage.failed_paths, failure_summary
            assert {item.logical_domain_id for item in result.coverage.candidate_count_by_domain} == {
                "tax.policy",
                "tax.law",
            }
            assert all(item.count > 0 for item in result.coverage.candidate_count_by_domain)
            assert set(result.batch.index_snapshot_ids) == expected_snapshots
            assert result.batch.profile_version == "tax-knowledge-search-v1"
            assert rerank.calls == 1


@pytest.mark.asyncio
async def test_denied_tokens_read_no_es_content_and_never_reach_rerank() -> None:
    es_base = _required("AGENT_KNOWLEDGE_ES_BASE_URL")
    embedding_base = _required("AGENT_KNOWLEDGE_EMBEDDING_BASE_URL")
    rerank_base = _required("AGENT_KNOWLEDGE_RERANK_BASE_URL")
    stats_base = _required("AGENT_KNOWLEDGE_ES_STATS_BASE_URL")
    index = _required("AGENT_KNOWLEDGE_EXPECTED_INDEX_NAME")
    async with (
        build_knowledge_http_client(es_base) as es_client,
        build_knowledge_http_client(embedding_base) as embedding_client,
        build_knowledge_http_client(rerank_base) as rerank_client,
        httpx.AsyncClient(base_url=stats_base, trust_env=False, follow_redirects=False, timeout=5.0) as stats_client,
    ):
        before = await _query_total(stats_client, index)
        search = EsKnowledgeSearchAdapter(HttpxKnowledgeTransport(es_client))
        embedding = BgeM3EmbeddingAdapter(HttpxKnowledgeTransport(embedding_client))
        rerank = CountingRerank(BgeRerankAdapter(HttpxKnowledgeTransport(rerank_client)))
        result = await _stage(search, embedding, rerank).execute(
            plan=_plan(),
            context=_context(_required("AGENT_KNOWLEDGE_UNKNOWN_ROLE_JWT")),
            timeout_s=15.0,
        )

        assert result.kind is RetrievalStageKind.FORBIDDEN
        assert result.batch is None
        assert rerank.calls == 0
        assert await _query_total(stats_client, index) == before

        body = {
            "schemaVersion": 1,
            "logicalDomainId": "tax.policy",
            "retrievalProfileId": "tax-policy-v1",
            "path": "keyword",
            "queryText": "synthetic authorization probe",
            "queryVector": None,
            "limit": 5,
        }
        cases: tuple[tuple[str | None, int], ...] = (
            (None, 401),
            ("not-a-jwt", 401),
            (_required("AGENT_KNOWLEDGE_SERVICE_JWT"), 401),
        )
        for token, expected_status in cases:
            headers = {} if token is None else {"Authorization": f"Bearer {token}"}
            response = await es_client.post("/es/knowledge/search", headers=headers, json=body)
            assert response.status_code == expected_status
            assert len(response.content) <= 4096
        assert await _query_total(stats_client, index) == before


async def _query_total(client: httpx.AsyncClient, index: str) -> int:
    response = await client.get(f"/{index}/_stats/search", params={"filter_path": "indices.*.total.search.query_total"})
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise AssertionError("knowledge.live_stats_invalid")
    indices = payload.get("indices")
    if not isinstance(indices, Mapping):
        raise AssertionError("knowledge.live_stats_invalid")
    data = indices.get(index)
    if not isinstance(data, Mapping):
        raise AssertionError("knowledge.live_stats_invalid")
    total = data.get("total")
    if not isinstance(total, Mapping):
        raise AssertionError("knowledge.live_stats_invalid")
    search = total.get("search")
    if not isinstance(search, Mapping) or type(search.get("query_total")) is not int:
        raise AssertionError("knowledge.live_stats_invalid")
    return cast(int, search["query_total"])


def _safe_response_shape(response: httpx.Response) -> tuple[object, ...]:
    try:
        payload = response.json()
    except ValueError:
        return (response.status_code, response.headers.get("Content-Type"), "non-json", len(response.content))
    if not isinstance(payload, dict):
        return (response.status_code, "non-object")
    candidates = payload.get("candidates")
    candidate_shapes: list[tuple[object, ...]] = []
    if isinstance(candidates, list):
        for item in candidates:
            if not isinstance(item, dict):
                candidate_shapes.append(("non-object",))
                continue
            content = item.get("content")
            candidate_shapes.append(
                (
                    tuple(sorted(item)),
                    {key: type(item.get(key)).__name__ for key in sorted(item)},
                    len(item.get("title", "")) if isinstance(item.get("title"), str) else None,
                    len(content) if isinstance(content, str) else None,
                    hashlib.sha256(content.encode("utf-8")).hexdigest() == item.get("contentSha256")
                    if isinstance(content, str)
                    else False,
                )
            )
    return (
        response.status_code,
        response.headers.get("Content-Type"),
        tuple(sorted(payload)),
        payload.get("logicalDomainId"),
        payload.get("retrievalProfileId"),
        payload.get("path"),
        payload.get("profileVersion"),
        len(payload.get("indexSnapshotId", "")) if isinstance(payload.get("indexSnapshotId"), str) else None,
        payload.get("readPolicyVersion"),
        type(payload.get("truncated")).__name__,
        len(candidates) if isinstance(candidates, list) else None,
        tuple(candidate_shapes),
    )
