"""Synthetic-only paired experiment safeguards; never launches real services."""
import asyncio
from dataclasses import asdict, replace
from datetime import date
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from agent_runtime.knowledge.evidence.contracts import KnowledgeEgressDisposition
from agent_runtime.knowledge.retrieval.bge_rerank import BgeRerankAdapter
from agent_runtime.knowledge.retrieval.http import BoundedHttpResponse, RetrievalTransportError
from tests.evidence_helpers import synthetic_catalog
from tests.retrieval_helpers import candidate
from tests.system_e2e import knowledge_stage_b_context_rerank_probe as experiment


def test_body_first_metadata_never_changes_original_candidate_or_invents_validity():
    item = replace(candidate(content="合成条文"), document_number="测试文号", written_date=date(2001, 2, 3))
    before = item.content, item.content_sha256
    text = experiment.scoring_text(item)
    assert text == "合成条文\n文档标题：标题\n文号：测试文号\n成文日期（非生效日期）：2001-02-03"
    assert before == (item.content, item.content_sha256)
    assert experiment.scoring_text(replace(item, title="", document_number=None, written_date=None)) == item.content
    large = replace(item, content="x" * 4096, title="y" * 256, document_number="z" * 256)
    assert experiment.scoring_text(large).startswith(large.content) and len(experiment.scoring_text(large)) <= 4700


@pytest.mark.parametrize("values", [{"content": ""}, {"content": "x" * 4097}, {"title": "x" * 257},
                                  {"document_number": "x" * 257}, {"written_date": "2001-01-01"}])
def test_bad_representation_input_is_refused(values):
    with pytest.raises(RetrievalTransportError):
        # Test the experiment boundary itself; the typed constructor already
        # rejects several of these before an HTTP response becomes a candidate.
        experiment.scoring_text(SimpleNamespace(**{**asdict(candidate()), **values}))


class EchoTransport:
    def __init__(self, fault=None):
        self.calls, self.fault = [], fault

    async def send(self, *, request, timeout_s):
        self.calls.append(request)
        assert timeout_s <= 5 and request.relative_path == "/rerank"
        assert not any(name.lower() == "authorization" for name, _ in request.headers)
        if self.fault in {"timeout", "cancel"}:
            raise TimeoutError() if self.fault == "timeout" else asyncio.CancelledError()
        payload = json.loads(request.body)
        results = [{"index": i, "text": text, "score": 0.25} for i, text in enumerate(payload["documents"])]
        value = {"model": BgeRerankAdapter.MODEL, "results": results}
        if self.fault == "echo": results[0]["text"] = "different"
        if self.fault == "bool_index": results[0]["index"] = True
        if self.fault == "bool_score": results[0]["score"] = True
        if self.fault == "nan": results[0]["score"] = float("nan")
        if self.fault == "duplicate_index": results[1]["index"] = 0
        if self.fault == "missing": value["results"] = results[:-1]
        if self.fault == "extra": value["extra"] = 1
        if self.fault == "model": value["model"] = "wrong"
        raw = json.dumps(value).encode()
        if self.fault == "duplicate_key": raw = b'{"model":1,"model":2,"results":[]}'
        if self.fault == "too_large": raw = b"x" * (2 * 1024 * 1024 + 1)
        return BoundedHttpResponse(status_code=503 if self.fault == "status" else 200,
            content_type="text/plain" if self.fault == "mime" else "application/json",
            content_encoding="gzip" if self.fault == "encoding" else None, body=raw)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["echo", "bool_index", "bool_score", "nan", "duplicate_index", "missing",
    "extra", "model", "duplicate_key", "too_large", "status", "mime", "encoding", "timeout", "cancel"])
async def test_context_echo_shape_and_technical_failure_fail_closed(fault):
    transport = EchoTransport(fault)
    with pytest.raises((RetrievalTransportError, TimeoutError, asyncio.CancelledError)):
        await experiment.ContextScorer(transport).rerank(query="合成问题", candidates=(candidate(), candidate(chunk="c2")), timeout_s=5)
    assert len(transport.calls) == 1


@pytest.mark.asyncio
async def test_pair_has_same_query_order_two_calls_raw_first_and_finite_observation():
    transport, rows = EchoTransport(), []
    original = (candidate(content="合成原文1"), candidate(chunk="c2", content="合成原文2"))
    scores = await experiment.PairedObservedRerank(BgeRerankAdapter(transport), rows).rerank(
        query="合成问题", candidates=original, timeout_s=5)
    assert len(scores) == 2 and len(transport.calls) == 2
    raw, contextual = [json.loads(r.body) for r in transport.calls]
    assert raw["query"] == contextual["query"] == "合成问题"
    assert raw["documents"] == [item.content for item in original]
    assert contextual["documents"] == [experiment.scoring_text(item) for item in original]
    assert [r["stage"] for r in rows] == ["rerank_raw", "rerank"]
    assert all(s["sha256"] == original[i].content_sha256 for row in rows for i, s in enumerate(row["candidates"]))
    assert "合成" not in json.dumps(rows, ensure_ascii=False)


@pytest.mark.asyncio
async def test_raw_failure_never_starts_context_arm():
    transport, rows = EchoTransport("status"), []
    with pytest.raises(RetrievalTransportError):
        await experiment.PairedObservedRerank(BgeRerankAdapter(transport), rows).rerank(
            query="q", candidates=(candidate(),), timeout_s=5)
    assert len(transport.calls) == 1 and rows == []


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", [None, "forbidden", "context"])
async def test_same_current_stage_selector_and_policy_use_original_evidence(monkeypatch, fault):
    probe = experiment.probe
    monkeypatch.setattr(probe, "SPECIFICATIONS", probe.SPECIFICATIONS[:1])
    monkeypatch.setattr(probe, "ObservedRerank", experiment.PairedObservedRerank)
    monkeypatch.setattr(probe, "LIMITS", experiment.LIMITS)
    monkeypatch.setattr(probe, "PER_CASE", experiment.PER_CASE)
    catalog = synthetic_catalog(disposition=KnowledgeEgressDisposition.ALLOW_MINIMAL)
    monkeypatch.setattr(probe, "CATALOG_SHA", catalog.snapshot.source_sha256)
    monkeypatch.setattr(probe, "KnowledgeEgressPolicyCatalog", SimpleNamespace(load_current_resource=lambda: catalog))
    original = "合成授权依据"
    digest = hashlib.sha256(original.encode()).hexdigest()
    monkeypatch.setattr(probe, "GOLD", {label: {"chunk": "synthetic", "sha256": digest, "clause": original}
                                      for label in ("lodging", "living")})
    calls, clients, events = [], [], []
    def response(status, payload):
        return httpx.Response(status, stream=httpx.ByteStream(json.dumps(payload).encode()),
                              headers={"Content-Type": "application/json"})
    def handle(request):
        body = json.loads(request.content)
        calls.append((request.url.path, request.headers.get("Authorization")))
        if request.url.path == "/embed": return response(200, {"dim": 1024, "vectors": [[0.1] * 1024]})
        if request.url.path == "/rerank":
            contextual = "文档标题" in body["documents"][0]
            return response(503 if fault == "context" and contextual else 200, {"model": BgeRerankAdapter.MODEL,
                "results": [{"index": i, "text": text, "score": 0.5} for i, text in enumerate(body["documents"])]})
        assert request.url.path == "/es/knowledge/search"
        return response(403 if fault == "forbidden" else 200, {"schemaVersion": 1,
            "logicalDomainId": "tax.policy", "retrievalProfileId": "tax-policy-v1", "path": body["path"],
            "profileVersion": "tax-knowledge-search-v1", "indexSnapshotId": "a" * 64,
            "readPolicyVersion": "tax-public-authenticated-v1", "truncated": False, "candidates": [
                {"documentId": "d1", "chunkId": "synthetic", "logicalDomainId": "tax.policy", "title": "合成标题",
                 "content": original, "sourceUrl": None, "documentNumber": None, "writtenDate": None,
                 "materialType": "tax_policy", "sourceRank": 1, "contentSha256": digest, "policyRef": "policy-doc-v1"}]})
    def factory(origin):
        client = httpx.AsyncClient(base_url=origin, transport=httpx.MockTransport(handle), trust_env=False)
        clients.append(client)
        return client
    budget = probe.Budget()
    if fault:
        with pytest.raises(ValueError, match="retrieval_failed"):
            await probe.diagnose({"policySnapshotId": "a" * 64}, "test-private-token", events.append, budget, client_factory=factory)
        assert budget.total["rerank"] == (0 if fault == "forbidden" else 2)
    else:
        result = await probe.diagnose({"policySnapshotId": "a" * 64}, "test-private-token", events.append, budget, client_factory=factory)
        assert result == {"casesMeasured": 1, "casesWithRequiredSources": 1}
        assert budget.total == {"search": 2, "embedding": 1, "rerank": 4}
        assert all(check["allowedOriginalClause"] for check in events[-1]["requiredSources"].values())
        assert events[-1]["evidence"] == [{"chunkId": "synthetic", "sha256": digest}]
    assert all(c.is_closed for c in clients)
    assert not any(token for path, token in calls if path != "/es/knowledge/search")
    assert all(text not in json.dumps(events, ensure_ascii=False) for text in (original, "合成标题", "test-private-token"))


def test_entry_restores_scoped_patch_even_on_failure_and_marks_experiment(monkeypatch, tmp_path):
    probe = experiment.probe
    assert hashlib.sha256(Path(probe.__file__).read_bytes()).hexdigest() == experiment.BASE_SHA
    old = probe.ObservedRerank, probe.LIMITS, probe.PER_CASE, probe.emit_line
    def fake_main():
        assert probe.LIMITS == {"search": 22, "embedding": 11, "rerank": 36} and probe.PER_CASE["rerank"] == 8
        with (tmp_path / "finite.jsonl").open("xb") as stream:
            probe.emit_line(stream, {"event": "prepared"})
        raise ValueError("synthetic")
    monkeypatch.setattr(probe, "main", fake_main)
    with pytest.raises(ValueError, match="synthetic"): experiment.main()
    assert (probe.ObservedRerank, probe.LIMITS, probe.PER_CASE, probe.emit_line) == old
    record = json.loads((tmp_path / "finite.jsonl").read_text())
    assert record["rankedArm"] == "context" and record["pairedRawScoring"]
    assert record["experimentSourceSha256"] == hashlib.sha256(Path(experiment.__file__).read_bytes()).hexdigest()


def test_immutable_paired_measurement_is_eight_local_plans_not_live_uat():
    path = experiment.probe.REPO / "knowledge-corpus-tools/evidence/policy-vector-publication-20260907-b2/quality-v3-context-paired-20260908-01.jsonl"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "beae7ddda48b4afd8382c975f1cb107c0e24a6d489b497808c6a82a4d8b35275"
    rows = [json.loads(line) for line in raw.splitlines()]
    assert rows[0]["head"] == "401988e531a231e10cbfc50ce50e00b8cbe8d8b4"
    assert rows[0]["experimentSourceSha256"] == hashlib.sha256(Path(experiment.__file__).read_bytes()).hexdigest()
    cases = [r for r in rows if r["event"] == "case"]
    assert [c["caseId"] for c in cases] == [s[0] for s in experiment.probe.SPECIFICATIONS]
    assert all(c["status"] == "measured" and c["policyAllowed"] and
               all(s["allowedOriginalClause"] for s in c["requiredSources"].values()) for c in cases)
    assert cases[3]["requiredSources"]["rent"]["evidenceRank"] == 2
    assert cases[4]["requiredSources"]["historical_rate"]["evidenceRank"] == 6
    for case in cases:
        arms = {arm: [r for r in rows if r.get("caseId") == case["caseId"] and r.get("stage") == arm]
                for arm in ("rerank_raw", "rerank")}
        assert len(arms["rerank_raw"]) == len(arms["rerank"]) == case["counts"]["rerank"] // 2
        for left, right in zip(arms["rerank_raw"], arms["rerank"], strict=True):
            assert left["ordinal"] == right["ordinal"]
            # Scores are emitted in the server's rank order, not request order.
            # The paired request-order contract is checked separately above.
            left_ids = [(v["chunkId"], v["sha256"]) for v in left["candidates"]]
            right_ids = [(v["chunkId"], v["sha256"]) for v in right["candidates"]]
            assert len(left_ids) == len(set(left_ids)) == len(right_ids) == len(set(right_ids))
            assert sorted(left_ids) == sorted(right_ids)
    terminal = rows[-1]
    assert terminal["status"] == "measured" and terminal["casesWithRequiredSources"] == 8
    assert terminal["counts"] == {"search": 22, "embedding": 11, "rerank": 36}
    assert all(terminal[key] == 0 for key in ("modelCalls", "businessCalls", "indexWrites", "retry", "resume"))
    assert all(terminal[key] is True for key in ("ownedProcessesStopped", "rawLogsDeleted", "secretScanPassed"))
    assert "not_functional_or_effectiveness_uat" in terminal["limitations"]
    def check(value):
        if isinstance(value, dict):
            assert not set(value) & {"query", "question", "content", "title", "text", "documentNumber", "writtenDate", "token", "authorization"}
            for child in value.values(): check(child)
        elif isinstance(value, list):
            for child in value: check(child)
    check(rows)
