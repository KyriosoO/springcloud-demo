"""Counted all-record checks with synthetic records, never actual ES reads."""
import asyncio
from dataclasses import replace
from hashlib import sha256
import json
from threading import Event
import traceback

import httpx
import pytest

from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.evaluation.knowledge import rebuild_document_number_inventory as i
from tests.evaluation.knowledge.rebuild_document_number_journal import AttemptJournal, JournalBinding
from tests.evaluation.knowledge.rebuild_document_number_owned import ReadBinding
from tests.evaluation.knowledge.rebuild_document_number_transport import AttemptLedger

BODY = "合成完整原文，不可保存完整正文或向量。"
BINDING = ReadBinding("synthetic-read", "synthetic-index", "synthetic-uuid", "synthetic-mapping")


@pytest.fixture(autouse=True)
def no_real_http(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("real ES operation attempted")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)


@pytest.fixture
def draft():
    source = p.draft_from_bytes(fixture_raw=(p.ROOT / p.FIXTURE).read_bytes(), head="f" * 40,
        old_helper=b"synthetic-old", current_helper=b"synthetic-current", changed_paths=(p.HELPER,))
    ref = p.CandidateRef("document-0", "chunk-00000", sha256(BODY.encode()).hexdigest())
    # Synthetic source coverage ONLY; neither the on-disk fixture nor gold is changed.
    return replace(source, cases=tuple(replace(case, necessary_sources=(ref,)) for case in source.cases))


class Es:
    def __init__(self, count=3):
        self.mapping = {"_meta": {"mapping_version": BINDING.mapping_version},
            "properties": {"embedding": {"type": "dense_vector", "dims": 1024}}}
        self.settings = {"index": {"uuid": BINDING.index_uuid, "blocks": {"write": True}}}
        self.flags = {}
        self.records = [{"_index": BINDING.index_name, "_id": f"id-{n:05d}",
            "_source": {"documentId": f"document-{n}", "chunkId": f"chunk-{n:05d}",
                "content": BODY, "embedding": [0.125] * 1024,
                **({"channel": "法律"} if n == 1 else {"channel": "财税文件"} if n == 0 else {})},
            "sort": [f"chunk-{n:05d}"], "_seq_no": n, "_primary_term": 1} for n in range(count)]
        self.calls = []
        self.fail_at = None
        self.effect = None

    def client(self):
        return httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False, timeout=30,
            transport=httpx.MockTransport(self.handle))

    def handle(self, request):
        self.calls.append((request.method, request.url.path))
        if self.effect:
            self.effect(request)
        if self.fail_at == len(self.calls):
            return httpx.Response(500, stream=httpx.ByteStream(p.canonical({"error": BODY})), headers={
                "Content-Type": "application/json", "X-Elastic-Product": "Elasticsearch"})
        name = BINDING.index_name
        alias = {BINDING.read_alias: self.flags}
        if request.method == "GET":
            payload = {name: ({"aliases": alias} if "/_alias/" in request.url.path
                else {"settings": self.settings} if request.url.path.endswith("/_settings")
                else {"mappings": self.mapping} if request.url.path.endswith("/_mapping")
                else {"settings": self.settings, "mappings": self.mapping, "aliases": alias})}
        else:
            assert request.url.path == f"/{name}/_search"
            body = json.loads(request.content)
            assert body["query"] == {"match_all": {}}
            assert body["_source"] == {"exclude_vectors": False}
            assert body["sort"] == [{"chunkId": "asc"}]
            assert body["seq_no_primary_term"] is True
            after = body.get("search_after", [""])[0]
            rows = [row for row in self.records if row["sort"][0] > after][:body["size"]]
            payload = {"timed_out": False, "_shards": {"total": 1, "successful": 1, "failed": 0},
                "hits": {"total": {"value": len(self.records), "relation": "eq"}, "hits": rows}}
        return httpx.Response(200, stream=httpx.ByteStream(p.canonical(payload)), headers={
            "Content-Type": "application/json", "X-Elastic-Product": "Elasticsearch"})


def session(draft, es, client, ledger, expected=None):
    return i.InventorySession(draft=draft, binding=BINDING,
        mapping_sha256=sha256(p.canonical(es.mapping)).hexdigest(), record_count=len(es.records),
        ledger=ledger, client=client, expected=expected)


def test_capture_and_pre_post_same_all_records_with_durable_attempts(draft, tmp_path):
    es = Es(501)  # Three full-record pages; law and unclassified competitors remain.
    binding = JournalBinding("synthetic-document-number-005", "f" * 40, "1" * 64,
                             "2" * 64, "3" * 64, "4" * 64, "synthetic_non_live")
    with es.client() as client, AttemptJournal(directory=tmp_path / binding.run_id,
        binding=binding, limits=i.exact_http_limits(501, include_preparation=True)) as journal:
        frozen = session(draft, es, client, journal.ledger).capture("preparation")
        runtime = session(draft, es, client, journal.ledger, frozen)
        assert runtime.capture("pre") == frozen
        assert runtime.capture("post") == frozen
        assert journal.ledger.counts["snapshotPreparation"] == 4
        assert journal.ledger.counts["snapshotPrePost"] == 8
        assert journal.ledger.counts["preparationMetadata"] == 3
        assert journal.ledger.counts["metadata"] == 6
        assert journal.ledger.view()["pending"] == 0
        assert len(es.calls) == 21
        rows = json.loads(frozen.inventory)["records"]
        assert len(rows) == 501 and rows[1]["documentId"] == "document-1"
        for value in (repr(frozen), json.dumps(frozen.preview()), (tmp_path / binding.run_id / "attempts.jsonl").read_text()):
            assert BODY not in value and "embedding" not in value and "0.125" not in value
        assert not client.is_closed
        with pytest.raises(p.ProtocolError, match="inventory_phase_invalid"):
            runtime.capture("post")
        assert len(es.calls) == 21


@pytest.mark.parametrize("count,per_scan", [(1,2), (250,2), (251,3), (15521,64), (22000,89)])
def test_exact_call_graph_not_a_grant(count, per_scan):
    execution = dict(i.exact_http_limits(count, include_preparation=False))
    assert execution["snapshotPrePost"] == 2 * per_scan
    assert execution["snapshotPreparation"] == execution["preparationMetadata"] == execution["bgeHealth"] == 0
    assert execution["metadata"] == 18 and execution["javaHealth"] == 2
    assert execution["typedSearch"] == execution["physicalSearch"] == 44
    assert execution["queryEmbedding"] == 10 and execution["rerank"] == 22 and execution["prewarmRerank"] == 1
    if count == 15521:
        assert sum(execution.values()) == 269
        assert sum(dict(i.exact_http_limits(count, include_preparation=True)).values()) == 336


@pytest.mark.parametrize("value", [True, 0, -1, 22001, 1.0])
def test_invalid_inventory_count(value):
    with pytest.raises(p.ProtocolError):
        i.exact_http_limits(value, include_preparation=False)


@pytest.mark.parametrize("flags", [{"filter": {}}, {"search_routing": "x"}, {"routing": "x"},
    {"is_write_index": True}, {"is_hidden": 1}, {"unknown": False}])
def test_alias_scope_not_silently_filtered(draft, flags):
    es = Es()
    es.flags = flags
    ledger = AttemptLedger(i.exact_http_limits(3, include_preparation=True))
    with es.client() as client:
        with pytest.raises(p.ProtocolError, match="inventory_capture_failed"):
            session(draft, es, client, ledger).capture("preparation")
    assert len(es.calls) == 3 and ledger.view()["stopped"]
    assert ledger.counts["snapshotPreparation"] == 0


@pytest.mark.parametrize("drift", ["body", "vector", "metadata", "unclassified", "alias", "write_block", "uuid", "mapping"])
def test_full_pool_postflight_drift_fails_closed(draft, drift):
    es = Es()
    ledger = AttemptLedger(i.exact_http_limits(3, include_preparation=True))
    with es.client() as client:
        frozen = session(draft, es, client, ledger).capture("preparation")
        checks = session(draft, es, client, ledger, frozen)
        checks.capture("pre")
        if drift == "body": es.records[2]["_source"]["content"] += "新增"
        if drift == "vector": es.records[1]["_source"]["embedding"][5] = 0.5
        if drift == "metadata": es.records[1]["_source"]["channel"] = "政策解读"
        if drift == "unclassified": es.records[2]["_source"]["new"] = True
        if drift == "alias": es.flags = {"is_hidden": True}
        if drift == "write_block": es.settings["index"]["blocks"]["write"] = False
        if drift == "uuid": es.settings["index"]["uuid"] = "other-uuid"
        if drift == "mapping": es.mapping["_meta"]["mapping_version"] = "new"
        with pytest.raises(p.ProtocolError, match="inventory_capture_failed"):
            checks.capture("post")
        assert ledger.view()["stopped"] and ledger.view()["pending"] == 0
        count = len(es.calls)
        with pytest.raises(p.ProtocolError, match="inventory_phase_invalid"):
            checks.capture("post")
        assert len(es.calls) == count


@pytest.mark.parametrize("at", [1, 3, 4, 5])
def test_http_failure_consumes_attempt_no_retry(draft, at):
    es = Es()
    es.fail_at = at
    ledger = AttemptLedger(i.exact_http_limits(3, include_preparation=True))
    with es.client() as client:
        with pytest.raises(p.ProtocolError) as caught:
            session(draft, es, client, ledger).capture("preparation")
    assert sum(ledger.counts.values()) == len(es.calls) == at
    assert ledger.view()["stopped"] and ledger.view()["pending"] == 0
    assert ledger.events[-1].http_status == 500
    assert BODY not in "".join(traceback.format_exception(caught.value))


def test_checkpoint_failure_before_actual_scan_send(draft):
    es = Es()
    def checkpoint(event, ticket, attempt):
        if event == "started" and attempt.kind == "snapshotPreparation":
            raise OSError(BODY)
    ledger = AttemptLedger(i.exact_http_limits(3, include_preparation=True), checkpoint=checkpoint)
    with es.client() as client:
        with pytest.raises(p.ProtocolError): session(draft, es, client, ledger).capture("preparation")
    assert len(es.calls) == 3 and ledger.counts["snapshotPreparation"] == 1
    assert ledger.view()["stopped"] and ledger.view()["pending"] == 1


def test_source_missing_cannot_use_historical_fingerprint(draft):
    es = Es()
    es.records[0]["_source"]["content"] = "合成另一个来源"
    ledger = AttemptLedger(i.exact_http_limits(3, include_preparation=True))
    with es.client() as client:
        with pytest.raises(p.ProtocolError): session(draft, es, client, ledger).capture("preparation")
    assert len(es.calls) == 5 and ledger.view()["stopped"]


def test_client_cookie_drift_between_scan_pages_stops_next_send(draft):
    es = Es(251)
    ledger = AttemptLedger(i.exact_http_limits(251, include_preparation=True))
    with es.client() as client:
        def effect(request):
            if request.method == "POST": client.cookies.set("unsafe", BODY)
        es.effect = effect
        with pytest.raises(p.ProtocolError): session(draft, es, client, ledger).capture("preparation")
    assert len(es.calls) == 5 and ledger.counts["snapshotPreparation"] == 2
    assert ledger.view()["stopped"]


def test_cancelled_sync_worker_is_stopped_and_joined(draft):
    async def run():
        es = Es(251)
        ledger = AttemptLedger(i.exact_http_limits(251, include_preparation=True))
        entered, release = Event(), Event()
        def effect(request):
            if request.method == "POST":
                entered.set()
                assert release.wait(5)
        es.effect = effect
        with es.client() as client:
            task = asyncio.create_task(session(draft, es, client, ledger).capture_async("preparation"))
            assert await asyncio.to_thread(entered.wait, 5)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
            task.cancel()
            release.set()
            with pytest.raises(asyncio.CancelledError): await task
            count = len(es.calls)
            await asyncio.sleep(0)
            assert len(es.calls) == count == 5
            assert ledger.view()["pending"] == 0 and ledger.view()["stopped"]
            assert not client.is_closed
    asyncio.run(run())


def test_pending_cancel_before_thread_creation_sends_nothing(draft):
    async def run():
        es = Es()
        ledger = AttemptLedger(i.exact_http_limits(3, include_preparation=True))
        with es.client() as client:
            async def cancelled_work():
                asyncio.current_task().cancel()
                await session(draft, es, client, ledger).capture_async("preparation")
            with pytest.raises(asyncio.CancelledError): await asyncio.create_task(cancelled_work())
        assert not es.calls and not ledger.events and ledger.view()["stopped"]
    asyncio.run(run())


def test_cancel_stop_checkpoint_failure_still_drains_worker(draft):
    async def run():
        es = Es(251)
        def checkpoint(event, ticket, attempt):
            if event == "stopped": raise OSError(BODY)
        ledger = AttemptLedger(i.exact_http_limits(251, include_preparation=True), checkpoint=checkpoint)
        entered, release = Event(), Event()
        def effect(request):
            if request.method == "POST":
                entered.set()
                assert release.wait(5)
        es.effect = effect
        unobserved = []
        loop = asyncio.get_running_loop()
        previous = loop.get_exception_handler()
        loop.set_exception_handler(lambda _, context: unobserved.append(context))
        try:
            with es.client() as client:
                task = asyncio.create_task(session(draft, es, client, ledger).capture_async("preparation"))
                assert await asyncio.to_thread(entered.wait, 5)
                task.cancel()
                await asyncio.sleep(0)
                assert ledger.view()["stopped"] and ledger.view()["pending"] == 1
                assert not task.done() and not client.is_closed
                task.cancel()
                release.set()
                with pytest.raises(p.ProtocolError, match="inventory_cancel_stop_failed") as caught:
                    await task
                assert BODY not in "".join(traceback.format_exception(caught.value))
                assert ledger.view()["pending"] == 0 and len(es.calls) == 5
                await asyncio.sleep(0)
                assert not unobserved and not client.is_closed
        finally:
            release.set()
            loop.set_exception_handler(previous)
    asyncio.run(run())


def test_post_cannot_overtake_inflight_pre(draft):
    async def run():
        es = Es()
        ledger = AttemptLedger(i.exact_http_limits(3, include_preparation=True))
        entered, release = Event(), Event()
        with es.client() as client:
            frozen = session(draft, es, client, ledger).capture("preparation")
            checks = session(draft, es, client, ledger, frozen)
            def effect(request):
                entered.set()
                assert release.wait(5)
            es.effect = effect
            pre = asyncio.create_task(checks.capture_async("pre"))
            assert await asyncio.to_thread(entered.wait, 5)
            try:
                with pytest.raises(p.ProtocolError, match="inventory_phase_invalid"):
                    await checks.capture_async("post")
                assert ledger.view()["stopped"] and not pre.done()
                assert len(es.calls) == 6  # Only preparation and pre's first GET.
            finally:
                release.set()
            with pytest.raises(p.ProtocolError): await pre
            assert len(es.calls) == 6 and ledger.view()["pending"] == 0
            with pytest.raises(p.ProtocolError, match="inventory_phase_invalid"):
                checks.capture("post")
            assert len(es.calls) == 6
    asyncio.run(run())


def test_fresh_finite_inventory_can_exceed_typed_dto_two_mib_limit(draft):
    es = Es(4000)
    for row in es.records[1:]:
        row["_id"] += "x" * 240
        row["_source"]["documentId"] += "x" * 240
    ledger = AttemptLedger(i.exact_http_limits(4000, include_preparation=True))
    with es.client() as client:
        result = session(draft, es, client, ledger).capture("preparation")
    assert 2 * 1024 * 1024 < len(result.inventory) <= 16 * 1024 * 1024
    assert result.record_count == 4000 and len(es.calls) == 20
    assert ledger.counts["snapshotPreparation"] == 17 and not ledger.view()["stopped"]


def test_last_page_reentry_cannot_return_late_post_success(draft):
    async def run():
        es = Es()
        ledger = AttemptLedger(i.exact_http_limits(3, include_preparation=True))
        entered, release = Event(), Event()
        with es.client() as client:
            frozen = session(draft, es, client, ledger).capture("preparation")
            checks = session(draft, es, client, ledger, frozen)
            checks.capture("pre")
            def effect(request):
                if request.method == "POST":
                    entered.set()
                    assert release.wait(5)
            es.effect = effect
            post = asyncio.create_task(checks.capture_async("post"))
            assert await asyncio.to_thread(entered.wait, 5)
            try:
                with pytest.raises(p.ProtocolError, match="inventory_phase_invalid"):
                    checks.capture("post")
                assert ledger.view()["stopped"] and not post.done()
            finally:
                release.set()
            with pytest.raises(p.ProtocolError, match="inventory_capture_failed"):
                await post
            assert len(es.calls) == 15 and ledger.view()["pending"] == 0
    asyncio.run(run())
