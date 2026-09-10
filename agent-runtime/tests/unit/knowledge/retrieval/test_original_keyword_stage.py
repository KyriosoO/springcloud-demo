import asyncio
from dataclasses import replace

import pytest

from agent_runtime.knowledge.contracts import (
    KNOWLEDGE_QUALITY_VERSION_V2, RetrievalPath, RetrievalStageKind,
)
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from tests.unit.knowledge.retrieval.test_quality_ranking_v3 import FocusRerank, Search, requirement_plan
from tests.unit.knowledge.test_original_keyword_planning import build, rewrite


class Embedding:
    def __init__(self, failure=False):
        self.texts, self.failure = [], failure

    async def embed(self, *, text, timeout_s):
        self.texts.append(text)
        if self.failure:
            raise TimeoutError()
        return (float(len(self.texts)),) * 1024


async def run(plan, *, search=None, embedding=None):
    context, _ = requirement_plan()
    search, embedding, rerank = search or Search(), embedding or Embedding(), FocusRerank()
    result = await DefaultKnowledgeRetrievalStage(search=search, embedding=embedding, rerank=rerank).execute(
        plan=plan, context=context, timeout_s=4,
    )
    return result, search, embedding, rerank


@pytest.mark.asyncio
async def test_two_domains_use_original_keyword_and_distinct_vector_with_same_budgets():
    plan = build()
    result, search, embedding, rerank = await run(plan)
    assert result.kind is RetrievalStageKind.SUCCESS
    assert embedding.texts == ["税务政策规定", "税收法律规定"]
    assert len(search.calls) == 4 and len(rerank.calls) == 2
    assert [r.query_text for r in search.calls if r.path is RetrievalPath.KEYWORD] == [plan.original_keyword_query] * 2
    assert [r.query_vector[0] for r in search.calls if r.path is RetrievalPath.VECTOR] == [1, 2]
    assert [r[0] for r in rerank.calls] == [r.focus for r in plan.evidence_requirements]
    assert all(r.candidate_limit == 20 for r in search.calls)
    assert len(result.batch.candidates) <= 20


@pytest.mark.asyncio
async def test_decoder_legal_spaces_in_vector_are_not_rewritten_or_rejected():
    value = rewrite()
    value = replace(value, domain_queries=tuple(replace(x, query=" " + x.query + "  ") for x in value.domain_queries))
    result, _, embedding, _ = await run(build(value))
    assert result.kind is RetrievalStageKind.SUCCESS
    assert embedding.texts == [x.query for x in value.domain_queries]


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", [
    "missing_source", "wrong_source", "empty", "bool", "oversized", "sensitive", "control", "nfd", "spaces",
    "old_quality", "legacy", "wrong_keyword", "unsafe_vector", "oversized_vector", "nfd_vector",
    "extra_path", "reordered", "unknown_domain", "ordinal_bool", "ordinal_order", "limit_bool",
])
async def test_invalid_source_shape_or_path_is_zero_io(fault):
    plan = build()
    sources = {"missing_source": None, "wrong_source": "其他税务政策", "empty": "", "bool": True,
        "oversized": "税务" + "政" * 1023, "sensitive": "税务电话13800138000", "control": "税务\x00",
        "nfd": "税务e\u0301", "spaces": " 税务  政策 "}
    if fault in sources:
        plan = replace(plan, original_keyword_query=sources[fault])
    elif fault in {"old_quality", "legacy"}:
        plan = replace(plan, quality_version=KNOWLEDGE_QUALITY_VERSION_V2 if fault == "old_quality" else None,
                       question_kind=None, evidence_requirements=())
    elif fault == "extra_path":
        plan = replace(plan, items=plan.items + (plan.items[0],))
    elif fault == "reordered":
        plan = replace(plan, items=tuple(reversed(plan.items)))
    elif fault == "unknown_domain":
        plan = replace(plan, selected_domain_ids=("tax.policy", "unknown"),
                       evidence_requirements=tuple(replace(r, domain_id="unknown") if r.domain_id == "tax.law" else r
                                                   for r in plan.evidence_requirements),
                       items=tuple(replace(x, logical_domain_id="unknown") if x.logical_domain_id == "tax.law" else x
                                   for x in plan.items))
    else:
        changes = {"wrong_keyword": (0, {"query_text": "其他税务政策"}),
            "unsafe_vector": (1, {"query_text": "税务电话13800138000"}),
            "oversized_vector": (1, {"query_text": "税务" + "政" * 1023}),
            "nfd_vector": (1, {"query_text": "税务e\u0301"}),
            "ordinal_bool": (0, {"ordinal": True}), "ordinal_order": (0, {"ordinal": 3}),
            "limit_bool": (0, {"candidate_limit": True})}
        index, change = changes[fault]
        plan = replace(plan, items=tuple(replace(x, **change) if i == index else x for i, x in enumerate(plan.items)))
    result, search, embedding, rerank = await run(plan)
    assert result.kind is RetrievalStageKind.DOWNSTREAM_FAILURE
    assert search.calls == embedding.texts == rerank.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,expected", [("forbidden", RetrievalStageKind.FORBIDDEN),
    ("all_failure", RetrievalStageKind.DOWNSTREAM_FAILURE), ("vector_failure", RetrievalStageKind.SUCCESS)])
async def test_path_failure_never_replans_or_adds_a_call(fault, expected):
    plan = build()
    result, search, embedding, rerank = await run(plan, search=Search(fault=fault))
    assert result.kind is expected
    assert len(search.calls) == 4 and len(embedding.texts) == 2
    assert len(rerank.calls) == (2 if fault == "vector_failure" else 0)
    if fault == "vector_failure":
        assert not result.coverage.complete and len(result.coverage.failed_paths) == 2


@pytest.mark.asyncio
async def test_embedding_failure_keeps_only_preplanned_keyword_not_original_embedding():
    result, search, embedding, rerank = await run(build(), embedding=Embedding(failure=True))
    assert result.kind is RetrievalStageKind.SUCCESS
    assert len(search.calls) == len(embedding.texts) == len(rerank.calls) == 2
    assert all(x.path is RetrievalPath.KEYWORD for x in search.calls)
    assert all(x != rewrite().original_question for x in embedding.texts)
    assert not result.coverage.complete


@pytest.mark.asyncio
async def test_cancel_propagates_and_collects_all_started_paths():
    entered, stopped = asyncio.Event(), []

    class WaitingSearch:
        async def search(self, *, request, context, timeout_s):
            entered.set()
            try:
                await asyncio.Future()
            finally:
                stopped.append(request)

    task = asyncio.create_task(run(build(), search=WaitingSearch()))
    await asyncio.wait_for(entered.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(stopped) == 4
