"""Exercise current retrieval/Evidence on bounded fake HTTP, not a fake scorer."""
from dataclasses import replace
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest

from tests.evaluation.knowledge.retrieval_benchmark_dataset import load_dataset
from tests.evidence_helpers import synthetic_catalog
from tests.system_e2e import knowledge_retrieval_benchmark_v1 as runner

base = runner.base


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", [None, "empty", "forbidden", "snapshot", "rerank", "partial"])
async def test_current_production_stages_counts_fail_closed_and_no_body(monkeypatch, fault):
    data = load_dataset()
    content = "合成检索基准正文，仅用于本地契约测试"
    digest = hashlib.sha256(content.encode()).hexdigest()
    source = replace(data.sources[0], chunk_id="synthetic", sha256=digest, anchors=(content,))
    case = replace(data.cases[0], sources=(source.id,), requirements=data.cases[0].requirements[:1])
    # A second case proves zero hits continue; technical failures stop the batch.
    dataset = replace(data, sources=(source,), cases=(case, replace(case, id="KRB-002")))
    catalog = synthetic_catalog()
    monkeypatch.setattr(base, "CATALOG_SHA", catalog.snapshot.source_sha256)
    monkeypatch.setattr(base, "KnowledgeEgressPolicyCatalog", SimpleNamespace(load_current_resource=lambda: catalog))
    seen, clients, events = [], [], []

    def reply(status, value):
        return httpx.Response(status, stream=httpx.ByteStream(json.dumps(value).encode()),
                              headers={"Content-Type": "application/json"})

    def handle(request):
        value = json.loads(request.content)
        seen.append(request.url.path)
        if request.url.path == "/embed":
            assert "authorization" not in request.headers
            return reply(200, {"dim": 1024, "vectors": [[0.1] * 1024]})
        if request.url.path == "/rerank":
            assert "authorization" not in request.headers
            assert all(text.startswith(content) and "文档标题：合成标题" in text for text in value["documents"])
            return reply(503 if fault == "rerank" else 200, {"model": "BAAI/bge-reranker-v2-m3",
                "results": [{"index": i, "text": text, "score": 0.5} for i, text in enumerate(value["documents"])]})
        assert request.url.path == "/es/knowledge/search"
        assert request.headers["authorization"] == "Bearer synthetic-token"
        result = {"schemaVersion": 1, "logicalDomainId": "tax.policy", "retrievalProfileId": "tax-policy-v1",
            "path": value["path"], "profileVersion": "tax-knowledge-search-v1",
            "indexSnapshotId": ("b" if fault == "snapshot" else "a") * 64,
            "readPolicyVersion": "tax-public-authenticated-v1", "truncated": False,
            "candidates": [] if fault == "empty" else [{"documentId": "d1", "chunkId": "synthetic",
                "logicalDomainId": "tax.policy", "title": "合成标题", "content": content, "sourceUrl": None,
                "documentNumber": None, "writtenDate": None, "materialType": "tax_policy", "sourceRank": 1,
                "contentSha256": digest, "policyRef": "policy-doc-v1"}]}
        status = 403 if fault == "forbidden" else 503 if fault == "partial" and value["path"] == "keyword" else 200
        return reply(status, result if status == 200 else {})

    def factory(origin):
        client = httpx.AsyncClient(base_url=origin, transport=httpx.MockTransport(handle), trust_env=False)
        clients.append(client)
        return client

    with patch.multiple(base, **dataset.probe_inputs()):
        budget = base.Budget()
        if fault in ("forbidden", "snapshot", "rerank", "partial"):
            with pytest.raises(ValueError, match="probe_retrieval_failed"):
                await runner.diagnose(dataset, {"policySnapshotId": "a" * 64}, "synthetic-token", events.append,
                                      budget, client_factory=factory)
        else:
            outcome = await runner.diagnose(dataset, {"policySnapshotId": "a" * 64}, "synthetic-token", events.append,
                                          budget, client_factory=factory)
            assert outcome["casesMeasured"] == 2
            assert outcome["casesWithRequiredSources"] == (0 if fault == "empty" else 2)
    assert all(c.is_closed for c in clients)
    cases = [e for e in events if e["event"] == "case"]
    assert len(cases) == (2 if fault in (None, "empty") else 1)
    for case_row in cases:
        if case_row["status"] == "measured":
            assert case_row["metrics"]["necessary_recall_at_k"] == (0.0 if fault == "empty" else 1.0)
            assert case_row["metrics"]["precision_at_k"] == (0.0 if fault == "empty" else None)
            assert case_row["kind"] == ("no_result" if fault == "empty" else "success")
    assert budget.total["search"] == seen.count("/es/knowledge/search")
    assert budget.total["embedding"] == seen.count("/embed")
    assert budget.total["rerank"] == seen.count("/rerank")
    if fault == "empty":
        assert budget.total == {"search": 4, "embedding": 2, "rerank": 0}
    serialized = json.dumps(events, ensure_ascii=False)
    assert content not in serialized and "synthetic-token" not in serialized and case.question not in serialized


def test_source_hash_and_anchor_drift_rejected_without_publishing():
    data = load_dataset()
    content = "合成正文"
    source = replace(data.sources[0], sha256=hashlib.sha256(content.encode()).hexdigest(), anchors=("正文",))
    dataset = replace(data, sources=(source,))
    value = {"hits": {"hits": [{"_source": {"chunkId": source.chunk_id, "content": content, "channel": "财税文件"}}]}}
    runner.verify_sources(dataset, value)
    with pytest.raises(ValueError, match="benchmark_source_changed"):
        runner.verify_sources(replace(dataset, sources=(replace(source, anchors=("不存在",)),)), value)
    value["hits"]["hits"][0]["_source"]["content"] += "变化"
    with pytest.raises(ValueError, match="benchmark_source_changed"):
        runner.verify_sources(dataset, value)


def test_main_wrapper_restores_all_patches_after_failure(monkeypatch):
    original = base.SPECIFICATIONS, base.diagnose, base.check_index, base.emit_line, base.LIMITS

    def fail():
        assert len(base.SPECIFICATIONS) == 24
        assert base.LIMITS == {"search": 54, "embedding": 27, "rerank": 29}
        assert base.diagnose is not original[1]
        raise RuntimeError("synthetic")

    monkeypatch.setattr(base, "main", fail)
    with pytest.raises(RuntimeError, match="synthetic"):
        runner.main()
    assert original == (base.SPECIFICATIONS, base.diagnose, base.check_index, base.emit_line, base.LIMITS)


@pytest.mark.parametrize("fault", ["duplicate", "wrong_domain", "non_nfc", "missing"])
def test_source_audit_rejects_non_equivalent_inputs(fault):
    data = load_dataset()
    text = "合成é正文"
    source = replace(data.sources[0], sha256=hashlib.sha256(text.encode()).hexdigest(), anchors=("正文",))
    dataset = replace(data, sources=(source,))
    row = {"_source": {"chunkId": source.chunk_id, "content": text, "channel": "财税文件"}}
    hits = [row]
    if fault == "duplicate":
        hits.append(row)
    elif fault == "wrong_domain":
        row["_source"]["channel"] = "法律"
    elif fault == "non_nfc":
        row["_source"]["content"] = text.replace("é", "e\u0301")
    else:
        hits.clear()
    with pytest.raises(ValueError, match="benchmark_source_changed"):
        runner.verify_sources(dataset, {"hits": {"hits": hits}})
