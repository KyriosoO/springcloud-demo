"""Synthetic send-boundary integration; never real performance/quality evidence."""
import asyncio
from dataclasses import replace
import json

import pytest

from agent_runtime.capability_api.contracts import OpaqueUserToken
from agent_runtime.knowledge.contracts import KnowledgeRetrievalContext, RetrievalStageKind
from agent_runtime.knowledge.retrieval.bge_embedding import BgeM3EmbeddingAdapter
from agent_runtime.knowledge.retrieval.bge_rerank import BgeRerankAdapter
from agent_runtime.knowledge.retrieval.bge_rerank_context import ContextualBgeRerankAdapter
from agent_runtime.knowledge.retrieval.es_adapter import EsKnowledgeSearchAdapter
from agent_runtime.knowledge.retrieval.http import BoundedHttpRequest, BoundedHttpResponse
from agent_runtime.knowledge.retrieval.minimal_stage import MinimalKnowledgeRetrievalStage
from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.evaluation.knowledge import rebuild_document_number_transport as t
from tests.helpers import ManualCancellationSignal
from tests.retrieval_helpers import FakeTransport, candidate


@pytest.fixture
def draft():
    return p.draft_from_bytes(fixture_raw=(p.ROOT / p.FIXTURE).read_bytes(), head="f" * 40,
        old_helper=b"synthetic-old", current_helper=b"synthetic-current", changed_paths=(p.HELPER,))


def response(value=None, *, status=200):
    return BoundedHttpResponse(status_code=status, content_type="application/json", content_encoding=None,
                               body=p.canonical(value if value is not None else {}))


def request(value, *, path="/es/knowledge/search", token=True):
    headers = (("Accept-Encoding", "identity"), ("Content-Type", "application/json"))
    if token:
        headers += (("Authorization", "Bearer synthetic-memory-only"),)
    return BoundedHttpRequest(method="POST", relative_path=path, headers=headers,
                              body=p.canonical(value), max_response_bytes=2 * 1024 * 1024)


def typed(case, *, route="keyword", domain="tax.policy"):
    return {"schemaVersion": 1, "logicalDomainId": domain,
        "retrievalProfileId": {"tax.policy": "tax-policy-v1", "tax.law": "tax-law-v1"}[domain],
        "path": route, "queryText": case.plan.original_question if route == "keyword" else None,
        "queryVector": [0.0] * 1024 if route == "vector" else None, "limit": 20}


def physical(case, *, route="keyword", domain="tax.policy", signal=False):
    category = {"terms": {"channel": list(t.POLICY_CATEGORIES if domain == "tax.policy" else t.LAW_CATEGORIES)}}
    value = {"_source": {"includes": list(t.SOURCE_FIELDS)}, "track_total_hits": False, "size": 21}
    if route == "vector":
        value["knn"] = {"field": "embedding", "query_vector": [0.0] * 1024, "k": 21,
                        "num_candidates": 100, "filter": category}
    else:
        multi = {"multi_match": {"query": case.plan.original_question, "fields": ["title", "content", "section"]}}
        if signal:
            value["query"] = {"bool": {"filter": [category], "should": [multi, {"constant_score": {
                "boost": 100, "filter": {"bool": {"should": [{"regexp": {"documentNo": {
                    "value": "[ 　]*".join("合成机关公告2026年第1号"), "flags": "NONE", "case_insensitive": False,
                    "max_determinized_states": 256}}}], "minimum_should_match": 1}}}}], "minimum_should_match": 1}}
        else:
            value["query"] = {"bool": {"filter": [category], "must": [multi]}}
    return value


def synthetic_keyword_hashes(case, *, signal=False):
    # This is fake projection only; a future real launcher must use actual Java.
    return tuple((domain, t._request_hashes("POST", p.canonical(physical(case, domain=domain,
        signal=signal and domain == "tax.policy")))[1]) for domain in case.plan.selected_domain_ids)


def test_budget_includes_separate_fresh_capture_and_frozen_pre_post():
    value = t.BudgetPlan(15521).preview()
    assert value["limits"] == {"snapshotPreparation": 64, "preparationMetadata": 3,
        "snapshotPrePost": 128, "metadata": 18, "physicalSearch": 44, "typedSearch": 44,
        "queryEmbedding": 10, "rerank": 22, "prewarmRerank": 1, "javaHealth": 40, "bgeHealth": 4}
    assert value["esHttpUpperBound"] == 257 and value["allHttpUpperBound"] == 378
    assert value["realExecutionAllowed"] is False and value["inventoryCountStatus"] == "declared_not_observed"
    assert not any(value["forbidden"].values())
    assert t.BudgetPlan(15521, preparation_scans=0).preview()["esHttpUpperBound"] == 190


@pytest.mark.parametrize("count", [0, True, 22001, 1.0])
def test_budget_does_not_treat_unknown_or_unbounded_inventory_as_observed(count):
    with pytest.raises(p.ProtocolError):
        t.BudgetPlan(count)


def test_attempts_are_reserved_before_failure_and_no_resume_or_raw_data():
    ledger = t.AttemptLedger((("typedSearch", 2),))
    ticket = ledger.begin("typedSearch", "UAT-KM-001/old/tax.policy/keyword", b"private-body")
    assert ledger.counts["typedSearch"] == 1 and ledger.view()["pending"] == 1
    ledger.finish(ticket, "transport_failed")
    with pytest.raises(p.ProtocolError, match="batch_stopped"):
        ledger.begin("typedSearch", "UAT-KM-001/old/tax.policy/keyword", b"private-body")
    with pytest.raises(p.ProtocolError, match="batch_stopped"):
        ledger.begin("typedSearch", "UAT-KM-002/old/tax.policy/keyword", b"other")
    with pytest.raises(p.ProtocolError, match="already_finished"):
        ledger.finish(ticket, "completed", 200)
    assert "private-body" not in p.canonical(ledger.view()).decode()
    ledger = t.AttemptLedger((("typedSearch", 1),))
    ledger.begin("typedSearch", "UAT-KM-002/old/tax.policy/keyword", b"other")
    with pytest.raises(p.ProtocolError, match="budget_exceeded"):
        ledger.begin("typedSearch", "UAT-KM-003/old/tax.policy/keyword", b"other")


@pytest.mark.parametrize("mutation", ["domain", "unknown", "question", "limit", "vector", "headers", "path"])
async def test_send_guard_rejects_unplanned_data_without_delegate_call(draft, mutation):
    case = draft.cases[0]
    payload = typed(case)
    req = request(payload)
    if mutation == "domain":
        payload = typed(case, domain="tax.law")
    elif mutation == "unknown":
        payload["extra"] = "bad"
    elif mutation == "question":
        payload["queryText"] = "changed"
    elif mutation == "limit":
        payload["limit"] = True
    elif mutation == "vector":
        payload = typed(case, route="vector")
        payload["queryVector"][0] = True
    req = request(payload)
    if mutation == "headers":
        req = replace(req, headers=req.headers + (("Cookie", "private"),))
    elif mutation == "path":
        req = replace(req, relative_path="/employees/es/search")
    delegate = FakeTransport(response())
    ledger = t.AttemptLedger((("typedSearch", 44),))
    port = t.CountedKnowledgeTransport(delegate=delegate, ledger=ledger, case=case,
        arm="old", kind="typedSearch", vector=(0.0,) * 1024)
    with pytest.raises(p.ProtocolError):
        await port.send(request=req, timeout_s=5)
    assert not delegate.requests and ledger.counts["typedSearch"] == 0


@pytest.mark.parametrize("failure", ["timeout", "disconnect", "cancelled"])
async def test_send_attempt_failure_is_counted_and_finite(draft, failure):
    class Failed:
        async def send(self, **kwargs):
            assert ledger.counts["queryEmbedding"] == 1
            if failure == "cancelled":
                raise asyncio.CancelledError
            raise TimeoutError("private-provider-body") if failure == "timeout" else OSError("private-provider-body")
    ledger = t.AttemptLedger((("queryEmbedding", 10),))
    case = draft.cases[0]
    port = t.CountedKnowledgeTransport(delegate=Failed(), ledger=ledger, case=case, arm="shared", kind="queryEmbedding")
    with pytest.raises(asyncio.CancelledError if failure == "cancelled" else p.ProtocolError) as caught:
        await BgeM3EmbeddingAdapter(port).embed(text=case.plan.original_question, timeout_s=3)
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert ledger.view()["pending"] == 0
    assert ledger.events[0].outcome == ("cancelled" if failure == "cancelled" else "transport_failed")
    assert "private-provider-body" not in p.canonical(ledger.view()).decode()
    assert ledger.view()["stopped"] is True
    with pytest.raises(p.ProtocolError, match="batch_stopped"):
        ledger.begin("queryEmbedding", "another-case", b"other")


@pytest.mark.parametrize("mutation", ["route", "projection", "filter", "query", "size", "vector", "regex", "law_signal"])
def test_physical_gate_rejects_scope_drift_before_es_send(draft, mutation):
    case = draft.cases[5] if mutation == "law_signal" else draft.cases[0]
    value = physical(case, domain="tax.law" if mutation == "law_signal" else "tax.policy",
                     signal=mutation in ("regex", "law_signal"))
    path = "/synthetic-read/_search"
    if mutation == "route":
        path = "/_aliases"
    elif mutation == "projection":
        value["_source"]["includes"].append("privateField")
    elif mutation == "filter":
        value["query"]["bool"]["filter"] = []
    elif mutation == "query":
        value["query"]["bool"]["must"][0]["multi_match"]["query"] = "changed"
    elif mutation == "size":
        value["size"] = 100
    elif mutation == "vector":
        value = physical(case, route="vector")
        value["knn"]["query_vector"][0] = 1.0
    elif mutation == "regex":
        value["query"]["bool"]["should"][1]["constant_score"]["filter"]["bool"]["should"][0]["regexp"]["documentNo"]["value"] = ".*"
    ledger = t.AttemptLedger((("physicalSearch", 44),))
    gate = t.PhysicalSearchGate(case=case, arm="current", read_alias="synthetic-read", vector=(0.0,) * 1024, ledger=ledger,
        keyword_sha256=synthetic_keyword_hashes(case))
    with pytest.raises(p.ProtocolError):
        gate.forward(method="POST", path=path, body=p.canonical(value), send=lambda _: pytest.fail("unexpected ES send"))
    assert ledger.counts["physicalSearch"] == 0


def test_physical_send_disconnect_records_attempt_and_prevents_retry(draft):
    ledger = t.AttemptLedger((("physicalSearch", 44),))
    gate = t.PhysicalSearchGate(case=draft.cases[0], arm="old", read_alias="synthetic-read", vector=(0.0,) * 1024, ledger=ledger,
        keyword_sha256=synthetic_keyword_hashes(draft.cases[0]))
    def failed(body):
        assert ledger.counts["physicalSearch"] == 1
        raise OSError("private-original-response")
    with pytest.raises(p.ProtocolError, match="physical_transport_failed") as caught:
        gate.forward(method="POST", path="/synthetic-read/_search", body=p.canonical(physical(draft.cases[0])), send=failed)
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    with pytest.raises(p.ProtocolError, match="batch_stopped"):
        gate.forward(method="POST", path="/synthetic-read/_search", body=p.canonical(physical(draft.cases[0])), send=lambda _: response())
    assert not gate.witnesses and ledger.view()["pending"] == 0


def test_pending_requests_can_finish_but_failure_prevents_new_sends():
    ledger = t.AttemptLedger((("typedSearch", 3),))
    first = ledger.begin("typedSearch", "first", b"one")
    second = ledger.begin("typedSearch", "second", b"two")
    ledger.finish(first, "transport_failed")
    ledger.finish(second, "completed", 200)
    assert ledger.view()["pending"] == 0 and ledger.view()["stopped"] is True
    with pytest.raises(p.ProtocolError, match="batch_stopped"):
        ledger.begin("typedSearch", "third", b"three")


def test_success_does_not_permit_duplicate_send():
    ledger = t.AttemptLedger((("typedSearch", 3),))
    ticket = ledger.begin("typedSearch", "first", b"one")
    ledger.finish(ticket, "completed", 200)
    with pytest.raises(p.ProtocolError, match="retry_forbidden"):
        ledger.begin("typedSearch", "first", b"one")


@pytest.mark.parametrize("fault", ["status", "status_bool", "media", "encoding", "empty", "oversize", "type"])
async def test_adapter_invalid_response_is_counted_and_stops_batch(draft, fault):
    value = response()
    value = {"status": replace(value, status_code=503), "status_bool": replace(value, status_code=True),
        "media": replace(value, content_type="text/html"), "encoding": replace(value, content_encoding="gzip"),
        "empty": replace(value, body=b""), "oversize": replace(value, body=b"x" * (2 * 1024 * 1024 + 1)),
        "type": object()}[fault]
    delegate = FakeTransport(value)
    ledger = t.AttemptLedger((("queryEmbedding", 10),))
    port = t.CountedKnowledgeTransport(delegate=delegate, ledger=ledger, case=draft.cases[0], arm="shared", kind="queryEmbedding")
    with pytest.raises(p.ProtocolError, match="adapter_response_invalid") as caught:
        await port.send(request=request({"texts": [draft.cases[0].plan.original_question]}, path="/embed", token=False), timeout_s=3)
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert ledger.counts["queryEmbedding"] == 1 and ledger.view()["pending"] == 0
    assert ledger.view()["stopped"] is True


@pytest.mark.parametrize("fault", ["status", "status_bool", "media", "encoding", "empty", "oversize", "type"])
def test_physical_invalid_response_has_receipt_and_stops_batch(draft, fault):
    value = response()
    value = {"status": replace(value, status_code=503), "status_bool": replace(value, status_code=True),
        "media": replace(value, content_type="text/html"), "encoding": replace(value, content_encoding="gzip"),
        "empty": replace(value, body=b""), "oversize": replace(value, body=b"x" * (2 * 1024 * 1024 + 1)),
        "type": object()}[fault]
    ledger = t.AttemptLedger((("physicalSearch", 44),))
    gate = t.PhysicalSearchGate(case=draft.cases[0], arm="old", read_alias="synthetic-read", vector=(0.0,) * 1024, ledger=ledger,
        keyword_sha256=synthetic_keyword_hashes(draft.cases[0]))
    with pytest.raises(p.ProtocolError, match="physical_response_invalid") as caught:
        gate.forward(method="POST", path="/synthetic-read/_search", body=p.canonical(physical(draft.cases[0])), send=lambda _: value)
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert ledger.counts["physicalSearch"] == 1 and ledger.view()["pending"] == 0
    assert ledger.view()["stopped"] is True
    assert len(gate.witnesses) == (0 if fault in ("status_bool", "type") else 1)


async def test_request_header_newlines_are_rejected_before_send(draft):
    delegate = FakeTransport(response())
    ledger = t.AttemptLedger((("typedSearch", 44),))
    port = t.CountedKnowledgeTransport(delegate=delegate, ledger=ledger, case=draft.cases[0],
        arm="old", kind="typedSearch", vector=(0.0,) * 1024)
    req = request(typed(draft.cases[0]))
    req = replace(req, headers=tuple((k, "Bearer safe\r\nPrivate: hidden" if k == "Authorization" else v) for k, v in req.headers))
    with pytest.raises(p.ProtocolError, match="headers_invalid"):
        await port.send(request=req, timeout_s=5)
    assert not delegate.requests and not ledger.events


@pytest.mark.parametrize("change", ["added_signal", "removed_signal", "wrong_issuer"])
def test_physical_keyword_requires_independently_frozen_projection(draft, change):
    case = draft.cases[0]
    expected_signal = change != "added_signal"
    value = physical(case, signal=change != "removed_signal")
    if change == "wrong_issuer":
        regex = value["query"]["bool"]["should"][1]["constant_score"]["filter"]["bool"]["should"][0]["regexp"]["documentNo"]
        regex["value"] = "[ 　]*".join("其他机关公告2026年第2号")
    ledger = t.AttemptLedger((("physicalSearch", 44),))
    gate = t.PhysicalSearchGate(case=case, arm="current", read_alias="synthetic-read", vector=(0.0,) * 1024,
        ledger=ledger, keyword_sha256=synthetic_keyword_hashes(case, signal=expected_signal))
    with pytest.raises(p.ProtocolError, match="projection_drift"):
        gate.forward(method="POST", path="/synthetic-read/_search", body=p.canonical(value), send=lambda _: pytest.fail("unexpected ES send"))
    assert ledger.counts["physicalSearch"] == 0 and not gate.witnesses


async def test_actual_adapters_and_stage_at_send_boundary_all_ten_cases(draft):
    ledger = t.AttemptLedger((("typedSearch", 44), ("physicalSearch", 44), ("queryEmbedding", 10), ("rerank", 22)))
    class Cached:
        async def embed(self, *, text, timeout_s):
            assert text == case.plan.original_question
            return vector
    class Scripted:
        async def send(self, *, request, timeout_s):
            payload = json.loads(request.body)
            if request.relative_path == "/embed":
                return response({"dim": 1024, "vectors": [[0.0] * 1024]})
            if request.relative_path == "/rerank":
                return response({"model": BgeRerankAdapter.MODEL, "results": [
                    {"index": i, "text": text, "score": 0.5} for i, text in enumerate(payload["documents"])]})
            domain, route = payload["logicalDomainId"], payload["path"]
            physical_body = p.canonical(physical(case, route=route, domain=domain))
            def backend(body):
                assert body is physical_body  # Bytes are forwarded, never regenerated.
                return response({"hits": {"hits": []}})
            gate.forward(method="POST", path="/synthetic-read/_search", body=physical_body, send=backend)
            item = candidate(chunk=f"{case.case_id}-{domain}-c1", domain=domain)
            row = {"documentId": item.document_id, "chunkId": item.chunk_id, "logicalDomainId": domain,
                "title": item.title, "content": item.content, "sourceUrl": None, "documentNumber": None,
                "writtenDate": None, "materialType": item.material_type, "sourceRank": 1,
                "contentSha256": item.content_sha256, "policyRef": item.policy_ref}
            return response({"schemaVersion": 1, "logicalDomainId": domain, "retrievalProfileId": payload["retrievalProfileId"],
                "path": route, "profileVersion": "tax-knowledge-search-v1", "indexSnapshotId": "a" * 64,
                "readPolicyVersion": "tax-public-authenticated-v1", "truncated": False, "candidates": [row]})
    class Rerank:
        async def rerank(self, *, query, candidates, timeout_s):
            port = t.CountedKnowledgeTransport(delegate=Scripted(), ledger=ledger, case=case, arm=arm,
                kind="rerank", domain=candidates[0].domain_id)
            return await ContextualBgeRerankAdapter(port).rerank(query=query, candidates=candidates, timeout_s=timeout_s)
    for number, case in enumerate(draft.cases):
        embed = t.CountedKnowledgeTransport(delegate=Scripted(), ledger=ledger, case=case, arm="shared", kind="queryEmbedding")
        vector = await BgeM3EmbeddingAdapter(embed).embed(text=case.plan.original_question, timeout_s=3)
        arm_results = []
        for arm in (p.ARMS if number % 2 == 0 else tuple(reversed(p.ARMS))):
            gate = t.PhysicalSearchGate(case=case, arm=arm, read_alias="synthetic-read", vector=vector, ledger=ledger,
                keyword_sha256=synthetic_keyword_hashes(case))
            port = t.CountedKnowledgeTransport(delegate=Scripted(), ledger=ledger, case=case, arm=arm, kind="typedSearch", vector=vector)
            context = KnowledgeRetrievalContext(request_id=case.case_id, correlation_id=case.case_id,
                subject="synthetic", user_token=OpaqueUserToken.from_raw("synthetic-memory-only"),
                deadline_monotonic=asyncio.get_running_loop().time() + 30, cancellation=ManualCancellationSignal())
            result = await MinimalKnowledgeRetrievalStage(search=EsKnowledgeSearchAdapter(port), embedding=Cached(),
                rerank=Rerank(), settings=case.plan.settings).execute(plan=case.plan, context=context, timeout_s=20)
            assert result.kind is RetrievalStageKind.SUCCESS and len(gate.witnesses) == len(case.plan.items)
            arm_results.append(result)
        assert arm_results[0] == arm_results[1]
    assert ledger.counts == {"typedSearch": 44, "physicalSearch": 44, "queryEmbedding": 10, "rerank": 22}
    assert ledger.view()["pending"] == 0 and all(e.http_status == 200 for e in ledger.events)
    rendered = p.canonical(ledger.view()).decode()
    assert "synthetic-memory-only" not in rendered and "税务政策正文" not in rendered
    assert draft.cases[0].plan.original_question not in rendered
