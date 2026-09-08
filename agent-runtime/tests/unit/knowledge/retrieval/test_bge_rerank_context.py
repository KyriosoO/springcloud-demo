"""DR-KRET-034: current single-call scoring; original Evidence is untouched."""
import asyncio
from dataclasses import asdict, replace
from datetime import date
import json
from types import SimpleNamespace

import pytest

from agent_runtime.knowledge.retrieval.bge_rerank import BgeRerankAdapter
from agent_runtime.knowledge.retrieval.bge_rerank_context import ContextualBgeRerankAdapter, authorized_scoring_text
from agent_runtime.knowledge.retrieval.http import RetrievalTransportError
from agent_runtime.knowledge.retrieval.provider import LocalKnowledgeRetrievalFactory
from agent_runtime.knowledge.retrieval.settings import KnowledgeRetrievalSettings
from tests.retrieval_helpers import candidate
from tests.system_e2e.knowledge_stage_b_context_rerank_probe import ContextScorer, scoring_text
from tests.system_e2e.test_knowledge_stage_b_context_rerank_probe import EchoTransport


@pytest.mark.asyncio
@pytest.mark.parametrize("metadata", [False, True])
async def test_measured_representation_and_protocol_match_with_one_request(metadata):
    item = candidate(content="合成原文")
    item = replace(item, title="测试标题" if metadata else "", document_number="测试字1号" if metadata else None,
                   written_date=date(2001, 2, 3) if metadata else None)
    expected = ("合成原文\n文档标题：测试标题\n文号：测试字1号\n成文日期（非生效日期）：2001-02-03" if metadata else "合成原文")
    assert authorized_scoring_text(item) == scoring_text(item) == expected
    live, measured = EchoTransport(), EchoTransport()
    before = item.content, item.content_sha256
    actual = await ContextualBgeRerankAdapter(live).rerank(query="合成问题", candidates=(item,), timeout_s=5)
    reference = await ContextScorer(measured).rerank(query="合成问题", candidates=(item,), timeout_s=5)
    assert actual == reference and live.calls == measured.calls and len(live.calls) == 1
    assert json.loads(live.calls[0].body)["documents"] == [expected]
    assert before == (item.content, item.content_sha256)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["echo", "bool_index", "bool_score", "nan", "duplicate_index", "missing",
    "extra", "model", "duplicate_key", "too_large", "status", "mime", "encoding", "timeout", "cancel"])
async def test_bad_response_does_not_retry_or_fallback(fault):
    transport = EchoTransport(fault)
    with pytest.raises((RetrievalTransportError, TimeoutError, asyncio.CancelledError)):
        await ContextualBgeRerankAdapter(transport).rerank(
            query="合成问题", candidates=(candidate(), candidate(chunk="c2")), timeout_s=5)
    assert len(transport.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, 41, 80])
async def test_domain_pool_limit_before_http(count):
    transport = EchoTransport()
    with pytest.raises(RetrievalTransportError, match="invalid_input"):
        await ContextualBgeRerankAdapter(transport).rerank(query="q", candidates=(candidate(),) * count, timeout_s=5)
    assert transport.calls == []


def test_factory_default_history_and_explicit_current_version_are_distinct():
    settings = KnowledgeRetrievalSettings.from_env({"AGENT_KNOWLEDGE_ES_BASE_URL": "http://127.0.0.1:19201"}, enabled=True)
    transport = EchoTransport()
    kwargs = dict(settings=settings, search_transport=transport, embedding_transport=transport, rerank_transport=transport)
    assert type(LocalKnowledgeRetrievalFactory.build(**kwargs).rerank) is BgeRerankAdapter
    assert type(LocalKnowledgeRetrievalFactory.build(**kwargs,
        rerank_input_version=ContextualBgeRerankAdapter.INPUT_VERSION).rerank) is ContextualBgeRerankAdapter
    for invalid in ("", "unknown", None, True):
        with pytest.raises(ValueError, match="rerank_input_version_invalid"):
            LocalKnowledgeRetrievalFactory.build(**kwargs, rerank_input_version=invalid)
    assert transport.calls == []


@pytest.mark.parametrize("values", [{"content": ""}, {"content": "x" * 4097}, {"title": "x" * 257},
                                  {"document_number": "x" * 257}, {"written_date": "2001-01-01"}])
def test_current_representation_rejects_invalid_metadata(values):
    with pytest.raises(RetrievalTransportError, match="invalid_input"):
        authorized_scoring_text(SimpleNamespace(**{**asdict(candidate()), **values}))


@pytest.mark.asyncio
@pytest.mark.parametrize("score", [10 ** 400, -(10 ** 400), float("inf")])
async def test_non_representable_score_is_a_protocol_failure(score):
    class BadScore(EchoTransport):
        async def send(self, **kwargs):
            response = await super().send(**kwargs)
            value = json.loads(response.body)
            value["results"][0]["score"] = score
            return replace(response, body=json.dumps(value).encode())
    transport = BadScore()
    with pytest.raises(RetrievalTransportError, match="invalid_response"):
        await ContextualBgeRerankAdapter(transport).rerank(query="q", candidates=(candidate(),), timeout_s=5)
    assert len(transport.calls) == 1


@pytest.mark.asyncio
async def test_score_order_may_differ_from_request_order_without_rebinding_candidates():
    class ReversedScores(EchoTransport):
        async def send(self, **kwargs):
            response = await super().send(**kwargs)
            value = json.loads(response.body)
            value["results"].reverse()
            return replace(response, body=json.dumps(value).encode())
    transport = ReversedScores()
    items = (candidate(content="合成第一条"), candidate(chunk="c2", content="合成第二条"))
    scores = await ContextualBgeRerankAdapter(transport).rerank(query="q", candidates=items, timeout_s=5)
    assert [s.candidate_index for s in scores] == [1, 0]
    assert json.loads(transport.calls[0].body)["documents"] == [authorized_scoring_text(v) for v in items]
    assert len(transport.calls) == 1


@pytest.mark.asyncio
async def test_maximum_domain_pool_is_one_bounded_call():
    transport = EchoTransport()
    item = replace(candidate(content="x" * 4096), title="y" * 256, document_number="z" * 256)
    scores = await ContextualBgeRerankAdapter(transport).rerank(query="q", candidates=(item,) * 40, timeout_s=5)
    assert len(scores) == 40 and len(transport.calls) == 1
    assert len(transport.calls[0].body) < 2 * 1024 * 1024 and len(authorized_scoring_text(item)) <= 4700
