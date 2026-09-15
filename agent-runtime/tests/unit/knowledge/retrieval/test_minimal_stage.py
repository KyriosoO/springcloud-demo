import asyncio
from dataclasses import asdict, replace

import pytest

from agent_runtime.capability_api.contracts import CancellationSource
from agent_runtime.knowledge.contracts import KnowledgeRetrievalContext, RetrievalPath, RetrievalStageCode, RetrievalStageKind
from agent_runtime.knowledge.retrieval.contracts import PathResultFailure, PathResultKind, PathRetrievalResult, RerankScore
from agent_runtime.knowledge.retrieval.http import RetrievalTransportError
from agent_runtime.knowledge.retrieval.minimal_stage import MinimalKnowledgeRetrievalStage
from tests.helpers import ManualCancellationSignal, scope
from tests.retrieval_helpers import candidate
from tests.unit.knowledge.test_minimal_retrieval_plan import make_plan


class Embedding:
    def __init__(self, output=(0.0,) * 1024):
        self.calls = []
        self.output = output

    async def embed(self, *, text, timeout_s):
        self.calls.append((text, timeout_s))
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


class Search:
    def __init__(self, transform=lambda request, result: result, count=3):
        self.calls = []
        self.transform = transform
        self.count = count

    async def search(self, *, request, context, timeout_s):
        self.calls.append((request, context, timeout_s))
        await asyncio.sleep(0)
        candidates = tuple(candidate(chunk=f"{request.logical_domain_id}-{request.path}-{i:02d}",
            domain=request.logical_domain_id, rank=i) for i in range(1, self.count + 1))
        result = PathRetrievalResult(kind=PathResultKind.CANDIDATES if candidates else PathResultKind.NO_RESULT,
            logical_domain_id=request.logical_domain_id, retrieval_profile_id=request.retrieval_profile_id,
            path=request.path, profile_version="tax-knowledge-search-v1", index_snapshot_id="a" * 64,
            read_policy_version="tax-public-authenticated-v1", candidates=candidates)
        return self.transform(request, result)


class Rerank:
    def __init__(self, transform=lambda scores: scores):
        self.calls = []
        self.transform = transform
        self.active = 0

    async def rerank(self, *, query, candidates, timeout_s):
        assert self.active == 0
        self.active += 1
        self.calls.append((query, candidates, timeout_s))
        await asyncio.sleep(0)
        self.active -= 1
        return self.transform(tuple(RerankScore(candidate_index=i,
            score=(0.1 if c.domain_id == "tax.policy" else 0.99)) for i, c in enumerate(candidates)))


def context(signal=None):
    return KnowledgeRetrievalContext(request_id="r", correlation_id="c", subject="u",
        user_token=scope().context.user_token, deadline_monotonic=asyncio.get_running_loop().time() + 30,
        cancellation=signal or ManualCancellationSignal())


async def run(*, search=None, embedding=None, rerank=None, plan=None, ctx=None, timeout=20):
    plan = plan or make_plan()
    return await MinimalKnowledgeRetrievalStage(search=search or Search(), embedding=embedding or Embedding(),
        rerank=rerank or Rerank(), settings=plan.settings).execute(plan=plan, context=ctx or context(), timeout_s=timeout)


async def test_two_domain_maximum_budget_original_q_serial_rerank_and_round_robin():
    embedding, search, rerank, ctx = Embedding(), Search(count=20), Rerank(), context()
    plan = make_plan()
    result = await run(search=search, embedding=embedding, rerank=rerank, plan=plan, ctx=ctx)
    assert result.kind is RetrievalStageKind.SUCCESS
    assert len(embedding.calls) == 1 and embedding.calls[0][0] == plan.original_question
    assert len(search.calls) == 4
    vectors = []
    for request, forwarded, timeout in search.calls:
        assert forwarded is ctx and 0 < timeout <= 5 and request.candidate_limit == 20
        if request.path is RetrievalPath.KEYWORD:
            assert request.query_text == plan.original_question and request.query_vector is None
        else:
            assert request.query_text is None
            vectors.append(request.query_vector)
    assert vectors[0] is vectors[1]
    assert len(rerank.calls) == 2 and sum(len(c[1]) for c in rerank.calls) == 80
    assert [c[1][0].domain_id for c in rerank.calls] == ["tax.policy", "tax.law"]
    assert all(c[0] == plan.original_question and 0 < c[2] <= 5 for c in rerank.calls)
    assert len(result.batch.candidates) == 20
    assert [c.domain_ids[0] for c in result.batch.candidates] == ["tax.policy", "tax.law"] * 10
    assert all(c.path_ranks and "coverage_anchor" not in asdict(c) for c in result.batch.candidates)
    assert result.coverage.complete and result.batch.index_snapshot_ids == ("a" * 64,)


async def test_cross_domain_duplicate_merges_all_provenance_without_rerank_anchors():
    def duplicate(request, result):
        return replace(result, candidates=(candidate(domain=request.logical_domain_id),))
    result = await run(search=Search(duplicate))
    assert result.kind is RetrievalStageKind.SUCCESS and len(result.batch.candidates) == 1
    item = result.batch.candidates[0]
    assert item.domain_ids == ("tax.policy", "tax.law") and len(item.path_ranks) == 4
    assert item.rerank_score == 0.1  # First domain wins position; scores never compared across pools.


@pytest.mark.parametrize("change", [
    {"profile_version": "wrong"}, {"index_snapshot_id": "invalid"}, {"read_policy_version": ""},
    {"truncated": 1}, {"logical_domain_id": "employee"}, {"retrieval_profile_id": "detail"},
    {"kind": "candidates"}, {"candidates": ()}, {"path": "keyword"},
])
async def test_invalid_provider_metadata_is_not_partial(change):
    rerank = Rerank()
    result = await run(search=Search(lambda req, res: replace(res, **change)), rerank=rerank)
    assert result.kind is RetrievalStageKind.DOWNSTREAM_FAILURE and not rerank.calls


@pytest.mark.parametrize("change", [
    {"content_sha256": "b" * 64}, {"index_snapshot_id": "b" * 64},
    {"read_policy_version": "other"}, {"domain_id": "tax.law"}, {"source_rank": True},
])
async def test_bad_candidate_fails_before_any_scoring(change):
    def corrupt(req, res):
        return replace(res, candidates=(replace(res.candidates[0], **change),) + res.candidates[1:]) if req.logical_domain_id == "tax.policy" else res
    rerank = Rerank()
    result = await run(search=Search(corrupt), rerank=rerank)
    assert result.kind is RetrievalStageKind.DOWNSTREAM_FAILURE and not rerank.calls


@pytest.mark.parametrize("field,value", [("content", "不同原文"), ("policy_ref", "other-policy"), ("title", "不同标题")])
async def test_cross_path_identity_conflict_checks_even_low_rank(field, value):
    def conflict(req, res):
        items = tuple(candidate(chunk=f"c{i}", rank=i, domain=req.logical_domain_id) for i in range(1, 21))
        if req.path is RetrievalPath.VECTOR:
            last = replace(items[-1], **{field: value})
            if field == "content":
                last = candidate(chunk="c20", rank=20, domain=req.logical_domain_id, content=value)
            items = items[:-1] + (last,)
        return replace(res, candidates=items)
    rerank = Rerank()
    result = await run(search=Search(conflict), rerank=rerank)
    assert result.kind is RetrievalStageKind.DOWNSTREAM_FAILURE and not rerank.calls


async def test_empty_response_snapshot_conflict_also_fails_closed():
    def conflict(req, res):
        return replace(res, index_snapshot_id="b" * 64) if req.path is RetrievalPath.VECTOR else res
    result = await run(search=Search(conflict, count=0))
    assert result.kind is RetrievalStageKind.DOWNSTREAM_FAILURE


@pytest.mark.parametrize("output", [(0.0,) * 1023, (True,) * 1024, (0,) * 1024,
    (float("nan"),) * 1024, (float("inf"),) * 1024, ("0",) * 1024, None])
async def test_invalid_embedding_stops_before_search(output):
    search, rerank = Search(), Rerank()
    result = await run(embedding=Embedding(output), search=search, rerank=rerank)
    assert result.kind is RetrievalStageKind.DOWNSTREAM_FAILURE and not search.calls and not rerank.calls


@pytest.mark.parametrize("transform", [
    lambda s: s[:-1], lambda s: s + s[:1], lambda s: (replace(s[0], candidate_index=True),) + s[1:],
    lambda s: (replace(s[0], candidate_index=99),) + s[1:],
    lambda s: (replace(s[0], candidate_index=1),) + s[1:],
    lambda s: (replace(s[0], score=True),) + s[1:],
    lambda s: (replace(s[0], score=float("nan")),) + s[1:],
    lambda s: (replace(s[0], score=10**1000),) + s[1:],
])
async def test_invalid_rerank_never_starts_second_domain(transform):
    rerank = Rerank(transform)
    result = await run(rerank=rerank)
    assert result.stage_code is RetrievalStageCode.RERANK_FAILURE and len(rerank.calls) == 1


async def test_all_success_empty_is_no_result_and_zero_rerank():
    rerank = Rerank()
    result = await run(search=Search(count=0), rerank=rerank)
    assert result.kind is RetrievalStageKind.NO_RESULT and result.coverage.complete
    assert not result.coverage.failed_paths and not rerank.calls


@pytest.mark.parametrize("kind", [PathResultKind.FAILURE, PathResultKind.TIMEOUT])
async def test_all_failed_is_not_no_result(kind):
    rerank = Rerank()
    result = await run(search=Search(lambda req, res: replace(res, kind=kind, candidates=())), rerank=rerank)
    assert result.kind is RetrievalStageKind.DOWNSTREAM_FAILURE and not rerank.calls


async def test_embedding_transport_failure_allows_bounded_keyword_partial():
    search, rerank = Search(), Rerank()
    result = await run(search=search, embedding=Embedding(RetrievalTransportError("timeout")), rerank=rerank)
    assert result.kind is RetrievalStageKind.SUCCESS and len(search.calls) == 2 and len(rerank.calls) == 2
    assert not result.coverage.complete and len(result.coverage.failed_paths) == 2


@pytest.mark.parametrize("count", [1, 2, 3])
async def test_partial_requires_minimum_and_successful_candidate_path_in_each_domain(count):
    def partial(req, res):
        return replace(res, kind=PathResultKind.FAILURE, candidates=()) if req.path is RetrievalPath.VECTOR else res
    rerank = Rerank()
    result = await run(search=Search(partial, count=count), rerank=rerank, plan=make_plan(("tax.policy",)))
    assert result.kind is (RetrievalStageKind.SUCCESS if count >= 3 else RetrievalStageKind.DOWNSTREAM_FAILURE)
    assert len(rerank.calls) == (1 if count >= 3 else 0)


async def test_partial_missing_entire_domain_never_uses_other_domain():
    def partial(req, res):
        return replace(res, kind=PathResultKind.FAILURE, candidates=()) if req.logical_domain_id == "tax.law" else res
    rerank = Rerank()
    result = await run(search=Search(partial), rerank=rerank)
    assert result.kind is RetrievalStageKind.DOWNSTREAM_FAILURE and not rerank.calls


@pytest.mark.parametrize("kind,failure,expected", [
    (PathResultKind.FORBIDDEN, None, RetrievalStageCode.DOMAIN_FORBIDDEN),
    (PathResultKind.FAILURE, PathResultFailure.READ_DECISION_UNVERIFIABLE, RetrievalStageCode.READ_DECISION_UNVERIFIABLE),
    (PathResultKind.FAILURE, PathResultFailure.READ_AUTHORITY_FAILURE, RetrievalStageCode.READ_AUTHORITY_FAILURE),
])
async def test_authorization_failure_cancels_and_joins_pending_paths(kind, failure, expected):
    class BlockingSearch(Search):
        def __init__(self):
            super().__init__()
            self.started = 0
            self.cancelled = 0

        async def search(self, *, request, context, timeout_s):
            self.started += 1
            if request.logical_domain_id == "tax.policy" and request.path is RetrievalPath.KEYWORD:
                while self.started < 4:
                    await asyncio.sleep(0)
                return PathRetrievalResult(kind=kind, logical_domain_id=request.logical_domain_id,
                    retrieval_profile_id=request.retrieval_profile_id, path=request.path, failure=failure)
            try:
                await asyncio.Event().wait()
            finally:
                self.cancelled += 1
    search, rerank = BlockingSearch(), Rerank()
    result = await asyncio.wait_for(run(search=search, rerank=rerank), 1)
    assert result.stage_code is expected and search.cancelled == 3 and not rerank.calls


@pytest.mark.parametrize("phase", ["embedding", "search", "rerank"])
@pytest.mark.parametrize("cancel_signal", [False, True])
async def test_cancel_propagates_and_all_owned_tasks_finish(phase, cancel_signal):
    started, joined = asyncio.Event(), asyncio.Event()
    async def block(**kwargs):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            joined.set()
    embedding, search, rerank = Embedding(), Search(), Rerank()
    target, method = {"embedding": (embedding, "embed"), "search": (search, "search"), "rerank": (rerank, "rerank")}[phase]
    setattr(target, method, block)
    signal = ManualCancellationSignal()
    task = asyncio.create_task(run(embedding=embedding, search=search, rerank=rerank, ctx=context(signal)))
    await asyncio.wait_for(started.wait(), 1)
    if cancel_signal:
        signal.cancel(CancellationSource.CLIENT_DISCONNECT)
    else:
        task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert joined.is_set()


async def test_expired_context_calls_nothing():
    embedding, search, rerank = Embedding(), Search(), Rerank()
    result = await run(ctx=replace(context(), deadline_monotonic=0), embedding=embedding, search=search, rerank=rerank)
    assert result.kind is RetrievalStageKind.TIMEOUT and not embedding.calls and not search.calls and not rerank.calls


async def test_late_rerank_after_timeout_cannot_start_next_domain():
    rerank = Rerank()
    async def late(**kwargs):
        rerank.calls.append(kwargs)
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            return tuple(RerankScore(candidate_index=i, score=1.0) for i in range(len(kwargs["candidates"])))
    rerank.rerank = late
    result = await run(rerank=rerank, timeout=0.03)
    assert result.kind is RetrievalStageKind.TIMEOUT and len(rerank.calls) == 1


async def test_concurrent_requests_never_share_query_vector_or_context():
    search, embedding, rerank = Search(), Embedding(), Rerank()
    # Separate rerank fakes avoid imposing a global mutex that production does not require.
    plans = [make_plan(question=q) for q in ("增值税规定", "所得税法律")]
    results = await asyncio.gather(*(run(search=search, embedding=embedding, rerank=Rerank(), plan=p) for p in plans))
    assert all(r.kind is RetrievalStageKind.SUCCESS for r in results)
    assert len(embedding.calls) == 2 and len(search.calls) == 8
    assert {call[0] for call in embedding.calls} == {p.original_question for p in plans}
    assert len({id(call[1]) for call in search.calls}) == 2


async def test_swallowed_cancel_never_advances_to_search():
    started = asyncio.Event()
    embedding, search = Embedding(), Search()
    async def swallow(**kwargs):
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            return (0.0,) * 1024
    embedding.embed = swallow
    task = asyncio.create_task(run(embedding=embedding, search=search))
    await asyncio.wait_for(started.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not search.calls


async def test_completed_forbidden_takes_priority_over_completed_malformed_result():
    def mixed(req, res):
        if req.path is RetrievalPath.KEYWORD:
            return replace(res, kind=PathResultKind.FORBIDDEN, candidates=())
        return replace(res, logical_domain_id="wrong")
    result = await run(search=Search(mixed))
    assert result.kind is RetrievalStageKind.FORBIDDEN


async def test_invalid_plan_is_zero_port_calls():
    plan = make_plan()
    object.__setattr__(plan, "schema_version", 1)
    embedding, search, rerank = Embedding(), Search(), Rerank()
    with pytest.raises(ValueError):
        await run(plan=plan, embedding=embedding, search=search, rerank=rerank)
    assert not embedding.calls and not search.calls and not rerank.calls


@pytest.mark.parametrize("timeout", [True, 0, -1, float("nan"), float("inf")])
async def test_invalid_timeout_has_zero_calls(timeout):
    embedding = Embedding()
    with pytest.raises(ValueError):
        await run(embedding=embedding, timeout=timeout)
    assert not embedding.calls


async def test_invalid_deadline_has_zero_calls():
    embedding = Embedding()
    with pytest.raises(ValueError):
        await run(embedding=embedding, ctx=replace(context(), deadline_monotonic=float("nan")))
    assert not embedding.calls


@pytest.mark.parametrize("length,expected", [(256, RetrievalStageKind.SUCCESS), (257, RetrievalStageKind.DOWNSTREAM_FAILURE)])
async def test_read_policy_id_uses_existing_adapter_length_contract(length, expected):
    def policy(req, res):
        value = "p" * length
        return replace(res, read_policy_version=value,
            candidates=tuple(replace(c, read_policy_version=value) for c in res.candidates))
    result = await run(search=Search(policy))
    assert result.kind is expected
