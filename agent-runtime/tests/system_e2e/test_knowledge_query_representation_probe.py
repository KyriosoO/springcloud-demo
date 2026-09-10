"""The experiment changes inputs, not the production Stage's allowed plan shape."""
from dataclasses import replace
import hashlib
import json

import httpx
import pytest

from tests.system_e2e import knowledge_query_representation_probe as probe


class BodyStream(httpx.AsyncByteStream):
    def __init__(self, value):
        self.raw = json.dumps(value, ensure_ascii=False).encode()

    async def __aiter__(self):
        yield self.raw


def response(status, value):
    return httpx.Response(status, headers={"Content-Type":"application/json"}, stream=BodyStream(value))


def test_queries_use_only_question_and_requirements_not_gold_or_sources():
    data = probe.load_dataset()
    original = probe.prepare_cases(data)
    changed = probe.prepare_cases(replace(data, sources=()))
    assert original == changed
    assert [c.id for c, _, _ in original] == [c.id for c in data.cases]
    assert [c.split for c, _, _ in original].count("holdout") == 8
    for case, queries, plan in original:
        assert queries == tuple((d, " ".join(r.focus for r in case.requirements if r.domain_id == d)) for d in case.domains)
        assert all(plan.items[i].query_text == plan.items[i+1].query_text for i in range(0, len(plan.items), 2))
        assert all(i.candidate_limit == 20 for i in plan.items)
    assert probe.LIMITS == {"search": 81, "embedding": 27, "rerank": 58}


def test_unsafe_input_rejected_before_network():
    data = probe.load_dataset()
    bad = replace(data.cases[0], question="联系邮箱 person@example.com")
    with pytest.raises(ValueError, match="unsafe_query"):
        probe.prepare_cases(replace(data, cases=(bad, *data.cases[1:])))


@pytest.mark.asyncio
@pytest.mark.parametrize("url,method,headers", [
    ("https://api.deepseek.com/chat/completions", "POST", {}),
    ("http://127.0.0.1:19201/es/knowledge/search", "GET", {}),
    ("http://127.0.0.1:19201/es/search", "POST", {}),
    ("http://127.0.0.1:8908/embed", "POST", {"Authorization":"Bearer sentinel"}),
])
async def test_forbidden_wire_is_rejected_before_count(url, method, headers):
    budget = probe.Budget()
    with pytest.raises(ValueError, match="outbound_rejected"):
        await budget.request(httpx.Request(method, url, headers=headers))
    assert budget.counts == dict.fromkeys(probe.LIMITS, 0)
    assert budget.stopped


@pytest.mark.asyncio
async def test_limit_is_sticky_and_counts_attempts():
    budget = probe.Budget()
    request = httpx.Request("POST", "http://127.0.0.1:19201/es/knowledge/search")
    for _ in range(81):
        await budget.request(request)
    for _ in range(2):
        with pytest.raises(ValueError, match="outbound_rejected"):
            await budget.request(request)
    assert budget.counts == {"search":81,"embedding":0,"rerank":0}


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", [None, "empty", "forbidden", "server", "snapshot"])
async def test_real_adapters_and_ranking_in_fake_network_preserve_arms_and_fail_closed(monkeypatch, fault):
    data = probe.load_dataset()
    prepared = probe.prepare_cases(data)[:2]
    binding = json.loads(probe.BINDING.read_text(encoding="utf-8-sig"))
    requests, clients, rows = [], [], []

    def handler(request):
        value = json.loads(request.content)
        requests.append((request.url.port, value))
        if request.url.port == 8908:
            return response(200, {"dim":1024,"vectors":[[0.1]*1024]})
        if request.url.port == 8909:
            return response(200, {"model":"BAAI/bge-reranker-v2-m3", "results":[
                {"index":i,"text":text,"score":0.8} for i,text in enumerate(value["documents"])]})
        if fault in ("forbidden", "server"):
            return response(403 if fault == "forbidden" else 500, {})
        domain, path = value["logicalDomainId"], value["path"]
        identifier = domain + "-" + hashlib.sha256(request.content).hexdigest()[:10]
        body = "合成正文sentinel，不是真实知识内容。"
        row = dict(documentId=identifier,chunkId=identifier,logicalDomainId=domain,title="合成标题",
            content=body,sourceUrl=None,documentNumber=None,writtenDate=None,materialType="tax_policy",
            sourceRank=1,contentSha256=hashlib.sha256(body.encode()).hexdigest(),policyRef="synthetic-policy")
        return response(200, dict(schemaVersion=1,logicalDomainId=domain,
            retrievalProfileId=value["retrievalProfileId"],path=path,profileVersion="tax-knowledge-search-v1",
            indexSnapshotId="a"*64 if fault == "snapshot" else binding["lawSnapshotId" if domain=="tax.law" else "policySnapshotId"],
            readPolicyVersion="tax-public-authenticated-v1",truncated=False,candidates=[] if fault=="empty" else [row]))

    def client_factory(url):
        client = httpx.AsyncClient(base_url=url, transport=httpx.MockTransport(handler))
        clients.append(client)
        return client

    monkeypatch.setattr(probe.base, "build_knowledge_http_client", client_factory)
    budget = probe.Budget()
    if fault in ("forbidden", "server", "snapshot"):
        with pytest.raises(ValueError, match="path_failed|path_binding"):
            await probe.diagnose(prepared,data,binding,"in-memory-token",rows.append,budget)
        assert budget.counts == {"search":1,"embedding":1,"rerank":0}
        assert not any(r.get("event") == "case" for r in rows)
    else:
        await probe.diagnose(prepared,data,binding,"in-memory-token",rows.append,budget)
        assert budget.counts == {"search":9,"embedding":3,"rerank":0 if fault=="empty" else 8}
        cases = [r for r in rows if r["event"] == "case"]
        assert len(cases) == 2
        for case, (fixture, queries, _) in zip(cases, prepared, strict=True):
            assert set(case["arms"]) == set(probe.ARMS)
            assert len(case["paths"]) == 3*len(fixture.domains)
            assert all(arm["metrics"]["precision_at_k"] == (0.0 if fault == "empty" else None)
                       for arm in case["arms"].values())
            assert all(arm["metrics"]["necessary_recall_at_k"] == 0 for arm in case["arms"].values())
        search_wire = [r for port,r in requests if port==19201]
        cursor=0
        for fixture,queries,_ in prepared:
            for domain,focused in queries:
                first,second,third=search_wire[cursor:cursor+3]
                assert first["queryText"] == fixture.question and second["queryText"] == focused
                assert first["path"] == second["path"] == "keyword" and third["path"] == "vector"
                assert third["queryText"] is None and len(third["queryVector"]) == 1024
                assert all(r["logicalDomainId"] == domain and r["limit"] == 20 for r in (first,second,third))
                cursor+=3
    assert all(client.is_closed for client in clients)
    serialized=json.dumps(rows,ensure_ascii=False)
    assert "in-memory-token" not in serialized and "合成正文sentinel" not in serialized
    assert all(c.question not in serialized for c,_,_ in prepared)


def test_experiment_does_not_patch_or_relax_production_stage():
    source = probe.Path(probe.__file__).read_text(encoding="utf-8")
    assert "DefaultKnowledgeRetrievalStage" not in source
    assert "LLM_API_KEY\", None" in source
    assert "OUTPUT.open(\"x\"" in source
