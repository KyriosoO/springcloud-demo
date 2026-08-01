from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from agent_runtime.knowledge.contracts import (
    KnowledgeRetrievalContext,
    KnowledgeRetrievalPlan,
    RetrievalPath,
    RetrievalPlanItem,
    RetrievalStageKind,
)
from agent_runtime.knowledge.retrieval.contracts import (
    KnowledgePathRequest,
    PathResultKind,
    PathRetrievalResult,
    RerankScore,
)
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from tests.helpers import ManualCancellationSignal, scope
from tests.retrieval_helpers import candidate


class FakeEmbedding:
    calls = 0

    async def embed(self, *, text: str, timeout_s: float) -> tuple[float, ...]:
        del text, timeout_s
        self.calls += 1
        return (0.0,) * 1024


class FakeSearch:
    def __init__(self) -> None:
        self.calls: list[KnowledgePathRequest] = []

    async def search(self, *, request: KnowledgePathRequest, context: KnowledgeRetrievalContext, timeout_s: float) -> PathRetrievalResult:
        del context, timeout_s
        self.calls.append(request)
        item = candidate(rank=1)
        return PathRetrievalResult(
            kind=PathResultKind.CANDIDATES,
            logical_domain_id=request.logical_domain_id,
            retrieval_profile_id=request.retrieval_profile_id,
            path=request.path,
            profile_version="tax-knowledge-search-v1",
            index_snapshot_id="a" * 64,
            read_policy_version="tax-public-authenticated-v1",
            candidates=(item,),
        )


class FakeRerank:
    calls = 0

    async def rerank(self, *, query: str, candidates: tuple[object, ...], timeout_s: float) -> tuple[RerankScore, ...]:
        del query, timeout_s
        self.calls += 1
        return tuple(RerankScore(candidate_index=index, score=float(len(candidates) - index)) for index in range(len(candidates)))


@pytest.mark.asyncio
async def test_stage_embeds_once_searches_paths_concurrently_and_reranks_once() -> None:
    request_scope = scope()
    context = KnowledgeRetrievalContext(
        request_id="r", correlation_id="c", subject="u", user_token=request_scope.context.user_token,
        deadline_monotonic=asyncio.get_running_loop().time() + 5, cancellation=ManualCancellationSignal(),
    )
    plan = KnowledgeRetrievalPlan(
        items=(
            RetrievalPlanItem(logical_domain_id="tax.policy", path=RetrievalPath.KEYWORD, query_text="税务政策", candidate_limit=20, ordinal=1),
            RetrievalPlanItem(logical_domain_id="tax.policy", path=RetrievalPath.VECTOR, query_text="税务政策", candidate_limit=20, ordinal=2),
        ),
        selected_domain_ids=("tax.policy",), config_version="knowledge-flow-config-v1",
    )
    embedding, search, rerank = FakeEmbedding(), FakeSearch(), FakeRerank()

    result = await DefaultKnowledgeRetrievalStage(search=search, embedding=embedding, rerank=rerank).execute(
        plan=plan, context=context, timeout_s=4
    )

    assert result.kind is RetrievalStageKind.SUCCESS
    assert embedding.calls == 1
    assert len(search.calls) == 2
    assert rerank.calls == 1
    assert result.coverage is not None and result.coverage.complete

