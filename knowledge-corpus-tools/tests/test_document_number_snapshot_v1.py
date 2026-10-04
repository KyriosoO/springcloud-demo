from __future__ import annotations

import copy
import hashlib
import json
import struct
from collections.abc import Callable, Generator, Iterator
from dataclasses import asdict, replace
from typing import Any

import httpx
import pytest

from knowledge_corpus_tools.b_id_mapping_v1 import MappingScanSpec, scan_id_mapping_v1
from knowledge_corpus_tools.document_number_snapshot_v1 import (
    FreshSnapshotError, FreshSnapshotSpec, scan_fresh_snapshot,
)
from knowledge_corpus_tools.vector_candidate import canonical_bytes, mapping_fingerprint

INDEX = "agent-doc-tax-policy-v5-20260907-vector-b2"
SECRET = "响应原文、token和向量不可写入异常"


class FakeSnapshot:
    def __init__(self, count: int = 3) -> None:
        self.mapping: dict[str, Any] = {
            "_meta": {"mapping_version": "test-mapping-v1"},
            "properties": {"embedding": {"type": "dense_vector", "dims": 1024}},
        }
        self.definition: dict[str, Any] = {
            INDEX: {"settings": {"index": {"uuid": "fresh-uuid", "blocks": {"write": True}}},
                    "mappings": self.mapping, "aliases": {}},
        }
        self.records: list[dict[str, Any]] = [{
            "_index": INDEX, "_id": f"id-{count - number:05d}",
            "_source": {"documentId": f"document-{number:05d}",
                        "chunkId": f"chunk-{number:05d}", "content": f"第{number}条。正文。",
                        "title": f"资料{number}", "documentNo": "非目标资料",
                        "embedding": [0.125] * 1024},
            "sort": [f"chunk-{number:05d}"], "_seq_no": number, "_primary_term": 1,
        } for number in range(count)]
        if count >= 3:
            self.records[0]["_source"]["channel"] = "法律"
            self.records[0]["_source"]["domain"] = "tax.law"
            self.records[1]["_source"]["channel"] = "财税文件"
            # The third record deliberately has no classification/domain.
        self.calls: list[tuple[str, str]] = []
        self.queries: list[dict[str, Any]] = []
        self.mutate: Callable[[dict[str, Any]], None] | None = None
        self.limit: int | None = None
        self.disconnect_at: int | None = None
        self.status = 200
        self.raw: bytes | None = None
        self.content_type = "application/json"
        self.content_encoding = "identity"

    def spec(self) -> FreshSnapshotSpec:
        count = len(self.records)
        return FreshSnapshotSpec(INDEX, "fresh-uuid", mapping_fingerprint(self.mapping),
                                 count, 1 + (count + 249) // 250)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, request.url.path))
        if self.disconnect_at == len(self.calls):
            raise httpx.ReadError(SECRET, request=request)
        if self.status != 200:
            return httpx.Response(self.status, text=SECRET, headers={"Location": "http://evil.test"})
        if self.raw is not None:
            return httpx.Response(200, content=self.raw, headers={"Content-Type": self.content_type,
                "Content-Encoding": self.content_encoding})
        if request.method == "GET":
            assert request.url.path == f"/{INDEX}"
            assert request.content == b""
            return httpx.Response(200, json=self.definition)
        assert (request.method, request.url.path) == ("POST", f"/{INDEX}/_search")
        query = json.loads(request.content)
        self.queries.append(query)
        assert query["query"] == {"match_all": {}}
        assert query["_source"] == {"exclude_vectors": False}
        assert query["seq_no_primary_term"] is True
        assert query["track_total_hits"] is True
        assert query["sort"] == [{"chunkId": "asc"}]
        after = query.get("search_after", [""])[0]
        size = min(query["size"], self.limit) if self.limit is not None else query["size"]
        entries = copy.deepcopy([record for record in self.records if record["sort"][0] > after][:size])
        response: dict[str, Any] = {
            "timed_out": False, "_shards": {"failed": 0, "total": 1, "successful": 1},
            "hits": {"total": {"value": len(self.records), "relation": "eq"}, "hits": entries},
        }
        if self.mutate:
            self.mutate(response)
        return httpx.Response(200, json=response)

    def client(self, **kwargs: Any) -> httpx.Client:
        options: dict[str, Any] = {
            "base_url": "http://127.0.0.1:9200", "trust_env": False, "timeout": 30.0,
            "transport": httpx.MockTransport(self.handle),
        }
        options.update(kwargs)
        return httpx.Client(**options)


def expected_fingerprint(records: list[dict[str, Any]]) -> str:
    digests = []
    for record in records:
        source = record["_source"]
        fields = {key: value for key, value in source.items() if key != "embedding"}
        digests.append(hashlib.sha256(canonical_bytes([record["_id"], fields])
                                     + struct.pack("<1024f", *source["embedding"])).hexdigest() + "\n")
    return hashlib.sha256("".join(digests).encode()).hexdigest()


def assert_failure(fake: FakeSnapshot, reason: str, calls: int, spec: FreshSnapshotSpec | None = None) -> None:
    with fake.client() as client, pytest.raises(FreshSnapshotError) as caught:
        scan_fresh_snapshot(spec or fake.spec(), client=client)
    assert caught.value.reason == reason
    assert caught.value.http_requests == calls == len(fake.calls)
    assert str(caught.value) == reason
    assert SECRET not in repr(caught.value)
    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None


def test_fresh_scan_full_pool_and_old_scanner_compatible() -> None:
    fake = FakeSnapshot()
    spec = fake.spec()
    assert "source_fingerprint" not in asdict(spec)
    with fake.client() as client:
        fresh = scan_fresh_snapshot(spec, client=client)
        assert not client.is_closed
        old = scan_id_mapping_v1(MappingScanSpec(
            spec.index_name, spec.index_uuid, spec.mapping_sha256, fresh.source_fingerprint,
            spec.record_count, spec.max_http_requests), client=client)
    assert fresh.source_fingerprint == expected_fingerprint(fake.records)
    assert fresh.raw == old.raw
    assert fresh.sha256 == old.sha256 == hashlib.sha256(fresh.raw).hexdigest()
    assert fresh.mapping_version == old.mapping_version == "test-mapping-v1"
    assert fresh.http_requests == old.http_requests == 2
    assert fresh.record_count == 3
    value = json.loads(fresh.raw)
    assert set(value) == {"schemaVersion", "indexName", "indexUuid", "sourceFingerprint", "recordCount", "records"}
    assert fresh.raw == canonical_bytes(value)
    assert value["sourceFingerprint"] == fresh.source_fingerprint
    assert value["recordCount"] == 3
    assert [item["id"] for item in value["records"]] == sorted(record["_id"] for record in fake.records)
    assert len(value["records"]) == len(fake.records)  # law and unclassified remain in the pool.
    for item in value["records"]:
        assert set(item) == {"id", "documentId", "chunkId", "contentSha256"}
        source = next(record["_source"] for record in fake.records if record["_id"] == item["id"])
        assert item["contentSha256"] == hashlib.sha256(source["content"].encode()).hexdigest()
    assert b'"embedding"' not in fresh.raw and "正文".encode() not in fresh.raw


@pytest.mark.parametrize("kind", ["metadata", "vector", "content"])
def test_fingerprint_is_computed_from_current_full_record(kind: str) -> None:
    fake = FakeSnapshot()
    spec = fake.spec()
    with fake.client() as client:
        initial = scan_fresh_snapshot(spec, client=client)
        source = fake.records[0]["_source"]
        if kind == "metadata":
            source["unknownMetadata"] = {"aclVersion": "new", "value": "保持全量"}
        elif kind == "vector":
            source["embedding"][0] = 0.25
        else:
            source["content"] += "新增原文。"
        fresh = scan_fresh_snapshot(spec, client=client)
    assert fresh.source_fingerprint != initial.source_fingerprint
    assert fresh.source_fingerprint == expected_fingerprint(fake.records)
    assert fresh.sha256 != initial.sha256


@pytest.mark.parametrize("count,sizes", [(1, [1]), (250, [250]), (251, [250, 1]),
                                        (500, [250, 250]), (501, [250, 250, 1])])
def test_exact_pagination_and_request_budget(count: int, sizes: list[int]) -> None:
    fake = FakeSnapshot(count)
    with fake.client() as client:
        result = scan_fresh_snapshot(fake.spec(), client=client)
    assert result.record_count == count
    assert result.http_requests == len(fake.calls) == 1 + len(sizes)
    assert [query["size"] for query in fake.queries] == sizes
    assert fake.queries[0].get("search_after") is None
    for number, query in enumerate(fake.queries[1:], start=1):
        assert query["search_after"] == [f"chunk-{number * 250 - 1:05d}"]
    assert fake.calls == [("GET", f"/{INDEX}")] + [("POST", f"/{INDEX}/_search")] * len(sizes)
    assert result.source_fingerprint == expected_fingerprint(fake.records)


@pytest.mark.parametrize("changes", [
    {"record_count": 0}, {"record_count": 22001}, {"record_count": True},
    {"max_http_requests": 1}, {"max_http_requests": 3}, {"max_http_requests": True},
    {"index_name": "alias/*"}, {"index_uuid": "bad/uuid"}, {"mapping_sha256": "A" * 64},
])
def test_invalid_binding_rejected_without_http(changes: dict[str, Any]) -> None:
    fake = FakeSnapshot()
    with pytest.raises(FreshSnapshotError) as caught:
        replace(fake.spec(), **changes)
    assert caught.value.reason == "scan_binding_invalid"
    assert caught.value.http_requests == 0 and not fake.calls


def test_maximum_record_count_spec_exact_budget() -> None:
    assert FreshSnapshotSpec(INDEX, "uuid", "a" * 64, 22000, 89).max_http_requests == 89


@pytest.mark.parametrize("fault", ["uuid", "mapping", "version", "writeblock", "numeric_writeblock",
                                   "contradictory_writeblock", "index", "extra_index", "data_stream"])
def test_definition_binding_failure_stops_before_search(fault: str) -> None:
    fake = FakeSnapshot()
    spec = fake.spec()
    detail = fake.definition[INDEX]
    if fault == "uuid":
        detail["settings"]["index"]["uuid"] = "replacement"
    elif fault == "mapping":
        fake.mapping["extra"] = "changed"
    elif fault == "version":
        fake.mapping["_meta"]["mapping_version"] = ""
        spec = replace(spec, mapping_sha256=mapping_fingerprint(fake.mapping))
    elif fault in {"writeblock", "numeric_writeblock"}:
        detail["settings"]["index"]["blocks"]["write"] = False if fault == "writeblock" else 1
    elif fault == "contradictory_writeblock":
        detail["settings"]["index"]["blocks.write"] = False
    elif fault == "index":
        fake.definition["different-index"] = fake.definition.pop(INDEX)
    elif fault == "extra_index":
        fake.definition["extra-index"] = detail
    else:
        detail["data_stream"] = "stream"
    assert_failure(fake, "scan_binding_invalid", 1, spec)


@pytest.mark.parametrize("fault", ["count", "bool_count", "relation", "timeout", "failed_shard",
                                   "bool_failed", "bool_successful", "missing_successful", "zero_shards",
                                   "empty", "oversize", "duplicate_id", "duplicate_chunk", "duplicate_pair",
                                   "order", "sort", "index", "seq", "term", "document", "nfc",
                                   "missing_vector", "vector_shape", "vector_bool", "vector_zero",
                                   "vector_overflow"])
def test_bad_search_records_fail_closed(fault: str) -> None:
    fake = FakeSnapshot(1 if fault == "bool_count" else 3)

    def mutate(response: dict[str, Any]) -> None:
        hits = response["hits"]
        entries = hits["hits"]
        source = entries[0]["_source"]
        if fault in {"count", "bool_count", "relation"}:
            key = "relation" if fault == "relation" else "value"
            hits["total"][key] = "gte" if fault == "relation" else True if fault == "bool_count" else 4
        elif fault == "timeout":
            response["timed_out"] = True
        elif fault in {"failed_shard", "bool_failed", "bool_successful", "missing_successful", "zero_shards"}:
            shards = response["_shards"]
            if fault == "missing_successful":
                shards.pop("successful")
            elif fault == "zero_shards":
                shards["total"] = 0
            else:
                shards["successful" if fault == "bool_successful" else "failed"] = (
                    1 if fault == "failed_shard" else True if fault == "bool_successful" else False)
        elif fault == "empty":
            hits["hits"] = []
        elif fault == "oversize":
            entries.append(copy.deepcopy(entries[-1]))
        elif fault == "duplicate_id":
            entries[1]["_id"] = entries[0]["_id"]
        elif fault in {"duplicate_chunk", "duplicate_pair"}:
            entries[1]["_source"]["chunkId"] = source["chunkId"]
            entries[1]["sort"] = [source["chunkId"]]
            if fault == "duplicate_pair":
                entries[1]["_source"]["documentId"] = source["documentId"]
        elif fault == "order":
            entries.reverse()
        elif fault in {"sort", "index", "seq", "term"}:
            key, value = {"sort": ("sort", ["wrong"]), "index": ("_index", "wrong-index"),
                          "seq": ("_seq_no", True), "term": ("_primary_term", 0)}[fault]
            entries[0][key] = value
        elif fault == "document":
            source["documentId"] = ""
        elif fault == "nfc":
            source["content"] = "Cafe\u0301"
        elif fault == "missing_vector":
            source.pop("embedding")
        elif fault == "vector_shape":
            source["embedding"] = [1.0] * 1023
        elif fault == "vector_bool":
            source["embedding"][0] = True
        elif fault == "vector_zero":
            source["embedding"] = [0.0] * 1024
        else:
            source["embedding"][0] = 1e39

    fake.mutate = mutate
    assert_failure(fake, "scan_records_invalid", 2)


def test_non_finite_vector_rejected_without_retained_exception() -> None:
    class NonFiniteSnapshot(FakeSnapshot):
        def handle(self, request: httpx.Request) -> httpx.Response:
            response = super().handle(request)
            if request.method == "POST":
                # A valid JSON exponent overflows binary64, rather than the NaN extension.
                return httpx.Response(200, content=response.content.replace(b"0.125", b"1e309", 1),
                    headers={"Content-Type": "application/json"})
            return response

    fake = NonFiniteSnapshot()
    assert_failure(fake, "scan_records_invalid", 2)


@pytest.mark.parametrize("attempt", [1, 2])
def test_disconnect_counts_attempt_and_never_retries(attempt: int) -> None:
    fake = FakeSnapshot()
    fake.disconnect_at = attempt
    assert_failure(fake, "scan_http_invalid", attempt)


@pytest.mark.parametrize("status", [302, 404, 500])
def test_status_rejected_without_redirect_or_response_leak(status: int) -> None:
    fake = FakeSnapshot()
    fake.status = status
    assert_failure(fake, "scan_http_invalid", 1)


@pytest.mark.parametrize("raw", [b'{"duplicate":1,"duplicate":2}', b'{"value":NaN}',
                                 b'[]', b'not json', b'"\xff"'])
def test_malformed_json_rejected(raw: bytes) -> None:
    fake = FakeSnapshot()
    fake.raw = raw
    assert_failure(fake, "scan_http_invalid", 1)


def test_short_pages_exhaust_exact_budget_without_extra_request() -> None:
    fake = FakeSnapshot(251)
    fake.limit = 125
    assert_failure(fake, "scan_budget_exhausted", 3)
    assert len(fake.queries) == 2


@pytest.mark.parametrize("fault", ["duplicate", "out_of_order", "count_drift"])
def test_later_page_is_not_trusted(fault: str) -> None:
    fake = FakeSnapshot(251)

    def mutate(response: dict[str, Any]) -> None:
        if len(fake.queries) != 2:
            return
        if fault == "count_drift":
            response["hits"]["total"]["value"] += 1
        else:
            entry = copy.deepcopy(fake.records[249])
            if fault == "out_of_order":
                entry["_id"] = "not-seen"
                entry["_source"]["chunkId"] = "chunk-00248x"
                entry["sort"] = ["chunk-00248x"]
            response["hits"]["hits"] = [entry]

    fake.mutate = mutate
    assert_failure(fake, "scan_records_invalid", 3)


@pytest.mark.parametrize("flat", [True, False])
def test_string_and_flat_writeblock_settings_supported(flat: bool) -> None:
    fake = FakeSnapshot()
    settings = fake.definition[INDEX]["settings"]["index"]
    if flat:
        settings.pop("blocks")
        settings["blocks.write"] = "true"
    else:
        settings["blocks"]["write"] = "true"
    with fake.client() as client:
        result = scan_fresh_snapshot(fake.spec(), client=client)
    assert result.record_count == 3 and result.http_requests == 2


def test_oversized_response_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    import knowledge_corpus_tools.document_number_snapshot_v1 as snapshot

    monkeypatch.setattr(snapshot, "_MAX_RESPONSE", 128)
    fake = FakeSnapshot()
    fake.raw = b" " * 129
    assert_failure(fake, "scan_http_invalid", 1)


def test_stream_disconnect_sanitized_after_response_headers() -> None:
    class BrokenStream(httpx.SyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            yield b'{"prefix":'
            raise httpx.ReadError(SECRET)

    fake = FakeSnapshot()

    def handle(request: httpx.Request) -> httpx.Response:
        fake.calls.append((request.method, request.url.path))
        return httpx.Response(200, stream=BrokenStream(), headers={"Content-Type": "application/json"})

    with fake.client(transport=httpx.MockTransport(handle)) as client, pytest.raises(FreshSnapshotError) as caught:
        scan_fresh_snapshot(fake.spec(), client=client)
    assert caught.value.reason == "scan_http_invalid" and caught.value.http_requests == 1
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert SECRET not in repr(caught.value)


def test_closed_client_rejected_without_request() -> None:
    fake = FakeSnapshot()
    client = fake.client()
    client.close()
    with pytest.raises(FreshSnapshotError) as caught:
        scan_fresh_snapshot(fake.spec(), client=client)
    assert caught.value.reason == "scan_client_invalid"
    assert caught.value.http_requests == 0 and not fake.calls


@pytest.mark.parametrize("options", [
    {"base_url": "http://outside.test"}, {"base_url": "http://127.0.0.1:9200/prefix"},
    {"trust_env": True}, {"follow_redirects": True}, {"timeout": None}, {"timeout": 31},
])
def test_caller_client_gate_has_zero_http(options: dict[str, Any]) -> None:
    fake = FakeSnapshot()
    with fake.client(**options) as client, pytest.raises(FreshSnapshotError) as caught:
        scan_fresh_snapshot(fake.spec(), client=client)
    assert caught.value.reason == "scan_client_invalid"
    assert caught.value.http_requests == 0 and fake.calls == []


def test_multi_send_auth_is_rejected_before_transport() -> None:
    class Twice(httpx.Auth):
        def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
            yield request
            yield request
    fake = FakeSnapshot()
    with fake.client(auth=Twice()) as client, pytest.raises(FreshSnapshotError) as caught:
        scan_fresh_snapshot(fake.spec(), client=client)
    assert caught.value.reason == "scan_client_invalid" and caught.value.http_requests == 0
    assert not fake.calls


@pytest.mark.parametrize("options", [
    {"cookies": {"secret": "private"}}, {"headers": {"Authorization": "Bearer private"}},
    {"headers": {"X-Unapproved": "private"}}, {"event_hooks": {"request": [lambda request: None]}},
    {"params": {"routing": "synthetic-subset"}},
    {"mounts": {"http://": httpx.MockTransport(lambda request: pytest.fail("unexpected mounted send"))}},
])
def test_hidden_client_state_is_rejected_before_send(options: dict[str, Any]) -> None:
    fake = FakeSnapshot()
    with fake.client(**options) as client, pytest.raises(FreshSnapshotError) as caught:
        scan_fresh_snapshot(fake.spec(), client=client)
    assert caught.value.reason == "scan_client_invalid" and caught.value.http_requests == 0
    assert not fake.calls


def test_unknown_transport_and_native_retries_are_rejected_without_network() -> None:
    class CustomTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            pytest.fail("unexpected custom send")
    for transport in (CustomTransport(), httpx.HTTPTransport(retries=1)):
        fake = FakeSnapshot()
        with fake.client(transport=transport) as client, pytest.raises(FreshSnapshotError) as caught:
            scan_fresh_snapshot(fake.spec(), client=client)
        assert caught.value.reason == "scan_client_invalid" and caught.value.http_requests == 0
        assert not fake.calls


def test_pinned_native_zero_retry_client_is_valid_without_sending() -> None:
    from knowledge_corpus_tools.document_number_snapshot_v1 import _single_send_client
    with httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False) as client:
        assert _single_send_client(client)  # Does not call scan or make a request.


@pytest.mark.parametrize("transport", [
    httpx.HTTPTransport(proxy="http://outside.test:3128"),
    httpx.HTTPTransport(uds="/unapproved/socket"),
])
def test_explicit_transport_proxy_or_uds_rejected_without_send(transport: httpx.HTTPTransport) -> None:
    fake = FakeSnapshot()
    with fake.client(transport=transport) as client, pytest.raises(FreshSnapshotError) as caught:
        scan_fresh_snapshot(fake.spec(), client=client)
    assert caught.value.reason == "scan_client_invalid" and caught.value.http_requests == 0
    assert not fake.calls


@pytest.mark.parametrize("media,encoding", [("text/html", "identity"), ("application/json", "gzip")])
def test_wrong_media_or_compressed_response_is_rejected(media: str, encoding: str) -> None:
    fake = FakeSnapshot()
    fake.raw = b"{}"
    fake.content_type, fake.content_encoding = media, encoding
    assert_failure(fake, "scan_http_invalid", 1)


def test_request_explicitly_disables_content_compression() -> None:
    fake = FakeSnapshot()
    original = fake.handle
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.headers["accept-encoding"] == "identity"
        return original(request)
    with fake.client(transport=httpx.MockTransport(handle)) as client:
        assert scan_fresh_snapshot(fake.spec(), client=client).http_requests == 2


@pytest.mark.parametrize("library", ["httpx", "httpcore"])
def test_unknown_library_layout_version_is_rejected_before_send(monkeypatch: pytest.MonkeyPatch, library: str) -> None:
    import knowledge_corpus_tools.document_number_snapshot_v1 as snapshot
    monkeypatch.setattr(getattr(snapshot, library), "__version__", "unknown-version")
    fake = FakeSnapshot()
    with fake.client() as client, pytest.raises(FreshSnapshotError) as caught:
        scan_fresh_snapshot(fake.spec(), client=client)
    assert caught.value.reason == "scan_client_invalid" and caught.value.http_requests == 0
    assert not fake.calls
