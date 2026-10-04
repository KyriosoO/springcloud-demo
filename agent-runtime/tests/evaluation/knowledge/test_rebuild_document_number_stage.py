"""Full selected case/arm order with fake physical sends, not quality evidence."""
import asyncio
from dataclasses import asdict
import json
import socket
import subprocess
import traceback

import pytest

from agent_runtime.capability_api.contracts import CancellationSource, OpaqueUserToken
from agent_runtime.knowledge.retrieval.bge_rerank import BgeRerankAdapter
from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.evaluation.knowledge import rebuild_document_number_stage as s
from tests.evaluation.knowledge.rebuild_document_number_journal import AttemptJournal, JournalBinding
from tests.evaluation.knowledge.rebuild_document_number_transport import PhysicalSearchGate
from tests.evaluation.knowledge.test_rebuild_document_number_owned import pair
from tests.evaluation.knowledge.test_rebuild_document_number_transport import physical, response
from tests.helpers import ManualCancellationSignal
from tests.retrieval_helpers import candidate


@pytest.fixture(autouse=True)
def no_real_resources(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("real operation attempted")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)


@pytest.fixture
def journal(tmp_path):
    binding = JournalBinding("synthetic-document-number-002", "f" * 40, "1" * 64, "2" * 64,
                             "3" * 64, "4" * 64, "synthetic_non_live")
    with AttemptJournal(directory=tmp_path / binding.run_id, binding=binding,
        limits=(("typedSearch", 44), ("physicalSearch", 44), ("queryEmbedding", 10), ("rerank", 22))) as value:
        yield value


class PhysicalPort:
    def __init__(self, arm, ledger, order, *, no_witness=False):
        self.arm, self.ledger, self.order, self.no_witness = arm, ledger, order, no_witness
    def bind(self, *, case, vector, keyword_sha256):
        self.case = case
        self.gate = PhysicalSearchGate(case=case, arm=self.arm, read_alias="synthetic-read",
            vector=vector, ledger=self.ledger, keyword_sha256=keyword_sha256)
        self.order.append((case.case_id, self.arm))
    def finish(self):
        return () if self.no_witness else tuple(self.gate.witnesses)


class Scripted:
    def __init__(self, port=None, *, failure=None, empty=False):
        self.port, self.failure, self.empty, self.sent = port, failure, empty, []
    async def send(self, *, request, timeout_s):
        self.sent.append(request)
        payload = json.loads(request.body)
        if request.relative_path == "/embed":
            if self.failure == "embedding_cancel":
                raise asyncio.CancelledError
            return response({"dim": 1023 if self.failure == "embedding" else 1024, "vectors": [[0.0] * 1024]})
        if request.relative_path == "/rerank":
            if self.failure == "rerank":
                raise RuntimeError("synthetic-private-provider")
            return response({"model": BgeRerankAdapter.MODEL, "results": [
                {"index": i, "text": text, "score": 0.5} for i, text in enumerate(payload["documents"])]})
        assert self.port is not None
        if self.failure == "typed_malformed":
            return response({"schemaVersion": 1})
        if self.failure == "typed":
            return response({}, status=403)
        domain, route, case = payload["logicalDomainId"], payload["path"], self.port.case
        body = p.canonical(physical(case, route=route, domain=domain,
            signal=self.port.arm == "current" and case.case_id == "UAT-KM-003" and domain == "tax.policy"))
        self.port.gate.forward(method="POST", path="/synthetic-read/_search", body=body,
                               send=lambda unchanged: response({"hits": {"hits": []}}))
        chunk = "changed" if self.failure == "vector_drift" and route == "vector" else "same"
        item = candidate(chunk=f"{case.case_id}-{domain}-{chunk}", domain=domain)
        row = {"documentId": item.document_id, "chunkId": item.chunk_id, "logicalDomainId": domain,
            "title": item.title, "content": item.content, "sourceUrl": None, "documentNumber": None,
            "writtenDate": None, "materialType": item.material_type, "sourceRank": 1,
            "contentSha256": item.content_sha256, "policyRef": item.policy_ref}
        return response({"schemaVersion": 1, "logicalDomainId": domain,
            "retrievalProfileId": payload["retrievalProfileId"], "path": route,
            "profileVersion": "tax-knowledge-search-v1", "indexSnapshotId": "a" * 64,
            "readPolicyVersion": "tax-public-authenticated-v1", "truncated": False,
            "candidates": [] if self.empty else [row]})


def session(pair, journal, *, failure=None, empty=False):
    order = []
    physical_ports = tuple(PhysicalPort(arm, journal.ledger, order, no_witness=failure == "witness") for arm in p.ARMS)
    typed = tuple(Scripted(port, failure=failure if port.arm == "current" else None, empty=empty) for port in physical_ports)
    embedding, rerank = Scripted(failure=failure), Scripted(failure=failure)
    value = s.StageComparisonSession(pair=pair, ledger=journal.ledger, typed=typed,
                                     embedding=embedding, rerank=rerank, physical=physical_ports)
    return value, order, typed, embedding, rerank


async def test_all_ten_cases_use_real_adapters_stage_counting_and_physical_receipts(pair, journal):
    value, order, typed, embedding, rerank = session(pair, journal)
    result = await value.evaluate(token=OpaqueUserToken.from_raw("synthetic-memory-only"), cancellation=ManualCancellationSignal())
    assert len(result.cases) == 10 and len(result.physical_witnesses) == 44
    assert journal.ledger.counts == {"typedSearch": 44, "physicalSearch": 44, "queryEmbedding": 10, "rerank": 22}
    assert len(embedding.sent) == 10 and len(rerank.sent) == 22
    assert order == [(case.case_id, arm) for number, case in enumerate(pair.draft.cases)
                     for arm in (p.ARMS if number % 2 == 0 else tuple(reversed(p.ARMS)))]
    assert all(row.baseline.final20 == row.candidate.final20 for row in result.cases)
    assert all(row.baseline.latency_seconds > 0 and row.candidate.latency_seconds > 0 for row in result.cases)
    assert result.quality_assessment == "Not assessed" and not result.release_allowed
    rendered = p.canonical(asdict(result)).decode()
    log = journal._path.read_text(encoding="utf-8")
    assert "synthetic-memory-only" not in rendered + log and "税务政策正文" not in rendered + log
    assert pair.draft.cases[0].plan.original_question not in rendered + log
    assert journal.ledger.view()["pending"] == 0
    with pytest.raises(p.ProtocolError, match="already_attempted"):
        await value.evaluate(token=OpaqueUserToken.from_raw("unused"), cancellation=ManualCancellationSignal())


async def test_empty_result_uses_no_rerank_and_makes_no_quality_claim(pair, journal):
    value, order, typed, embedding, rerank = session(pair, journal, empty=True)
    result = await value.evaluate(token=OpaqueUserToken.from_raw("synthetic-memory-only"), cancellation=ManualCancellationSignal())
    assert journal.ledger.counts["rerank"] == 0 and not rerank.sent
    assert len(result.cases) == 10 and all(not row.baseline.final20 for row in result.cases)
    assert result.quality_assessment == "Not assessed"


@pytest.mark.parametrize("failure", ["embedding", "typed", "rerank", "witness", "vector_drift"])
async def test_technical_or_single_variable_failure_stops_without_retry_or_resume(pair, journal, failure):
    value, order, typed, embedding, rerank = session(pair, journal, failure=failure)
    before = asyncio.all_tasks()
    with pytest.raises(p.ProtocolError, match="stage_comparison_failed") as caught:
        await value.evaluate(token=OpaqueUserToken.from_raw("synthetic-memory-only"), cancellation=ManualCancellationSignal())
    assert journal.ledger.counts["queryEmbedding"] == 1 and journal.ledger.view()["stopped"]
    assert len(order) <= 2 and asyncio.all_tasks() == before
    assert "synthetic-private-provider" not in "".join(traceback.format_exception(caught.value))
    assert journal.ledger.view()["pending"] == 0
    with pytest.raises(p.ProtocolError, match="already_attempted"):
        await value.evaluate(token=OpaqueUserToken.from_raw("unused"), cancellation=ManualCancellationSignal())


@pytest.mark.parametrize("where", ["before", "embedding"])
async def test_cancellation_charges_only_actual_attempt_and_leaves_no_stage_children(pair, journal, where):
    signal = ManualCancellationSignal()
    if where == "before":
        signal.cancel(CancellationSource.CLIENT_DISCONNECT)
    value, order, typed, embedding, rerank = session(pair, journal, failure="embedding_cancel" if where == "embedding" else None)
    before = asyncio.all_tasks()
    with pytest.raises(asyncio.CancelledError):
        await value.evaluate(token=OpaqueUserToken.from_raw("synthetic-memory-only"), cancellation=signal)
    assert asyncio.all_tasks() == before and journal.ledger.view()["pending"] == 0
    assert journal.ledger.counts["queryEmbedding"] == (0 if where == "before" else 1)
    assert not order and not any(journal.ledger.counts[key] for key in ("typedSearch", "physicalSearch", "rerank"))


async def test_cancel_signal_during_shared_embedding_cancels_send_before_any_arm(pair, journal):
    signal = ManualCancellationSignal()
    value, order, typed, embedding, rerank = session(pair, journal)
    entered = asyncio.Event()
    async def wait_forever(**kwargs):
        entered.set()
        await asyncio.Future()
    embedding.send = wait_forever
    before = asyncio.all_tasks()
    task = asyncio.create_task(value.evaluate(token=OpaqueUserToken.from_raw("synthetic-memory-only"), cancellation=signal))
    await entered.wait()
    signal.cancel(CancellationSource.UPSTREAM_CANCEL)
    with pytest.raises(asyncio.CancelledError):
        await task
    assert asyncio.all_tasks() == before and not order
    assert journal.ledger.counts["queryEmbedding"] == 1 and journal.ledger.view()["pending"] == 0


async def test_http200_malformed_dto_stops_peer_not_yet_sent(pair, journal):
    value, order, typed, embedding, rerank = session(pair, journal)
    typed[0].failure = "typed_malformed"
    with pytest.raises(p.ProtocolError, match="stage_comparison_failed"):
        await value.evaluate(token=OpaqueUserToken.from_raw("synthetic-memory-only"), cancellation=ManualCancellationSignal())
    assert [json.loads(request.body)["path"] for request in typed[0].sent] == ["keyword"]
    assert not typed[1].sent and not rerank.sent
    assert journal.ledger.counts == {"typedSearch": 1, "physicalSearch": 0, "queryEmbedding": 1, "rerank": 0}
    assert journal.ledger.view()["stopped"] and journal.ledger.view()["pending"] == 0


@pytest.mark.parametrize("swallow_cancel", [False, True])
async def test_shared_embedding_absolute_timeout_and_late_result_cannot_advance(monkeypatch, pair, journal, swallow_cancel):
    # Shorten only the test deadline while retaining the actual production
    # timeout scope, cancellation and late-result checks.
    production_bounded = s._bounded
    async def short_bounded(call, deadline):
        return await production_bounded(call, min(deadline, asyncio.get_running_loop().time() + 0.01))
    monkeypatch.setattr(s, "_bounded", short_bounded)
    value, order, typed, embedding, rerank = session(pair, journal)
    async def slow_send(**kwargs):
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            if not swallow_cancel:
                raise
            return response({"dim": 1024, "vectors": [[0.0] * 1024]})
    embedding.send = slow_send
    before = asyncio.all_tasks()
    with pytest.raises(p.ProtocolError, match="stage_comparison_failed"):
        await value.evaluate(token=OpaqueUserToken.from_raw("synthetic-memory-only"), cancellation=ManualCancellationSignal())
    assert asyncio.all_tasks() == before and not order
    assert journal.ledger.counts == {"typedSearch": 0, "physicalSearch": 0, "queryEmbedding": 1, "rerank": 0}
    assert journal.ledger.view()["stopped"] and journal.ledger.view()["pending"] == 0
