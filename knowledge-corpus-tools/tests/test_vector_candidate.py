from __future__ import annotations

import copy
import hashlib
import json
import struct
from dataclasses import FrozenInstanceError, replace
from typing import Any

import httpx
import pytest

from knowledge_corpus_tools.vector_candidate import (
    ACL_FIELDS, MAPPING_VERSION, POLICY_CATEGORIES, TRACE_FIELDS, CandidateError,
    VectorCandidateSpec, build_policy_vector_candidate, mapping_fingerprint,
)

SOURCE = "agent-doc-tax-policy-v4-20260903-corpus-a5"
TARGET = "agent-doc-tax-policy-v5-20260907-vector-b1"
MODEL_SHA = "a" * 64
SECRET = "不可进入日志的测试原文"
OLD = [0.125] * 1024
NEW = tuple([0.25] * 1024)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode()


def independent_fingerprint(documents: dict[str, dict[str, Any]]) -> str:
    digests = []
    for identifier, document in sorted(documents.items(), key=lambda item: item[1]["chunkId"]):
        rest = {k: v for k, v in document.items() if k != "embedding"}
        digest = hashlib.sha256(canonical([identifier, rest])
                                + struct.pack("<1024f", *document["embedding"])).hexdigest()
        digests.append(digest + "\n")
    return hashlib.sha256("".join(digests).encode()).hexdigest()


def attachment(chunk: str = "a") -> dict[str, Any]:
    return {
        **{key: "public" for key in ACL_FIELDS}, "channel": "财税文件",
        "chunkId": chunk, "content": SECRET, "title": "测试标题", "section": "第一条",
        "contentHash": hashlib.sha256(SECRET.encode()).hexdigest(), "embedding": list(OLD),
        "assetKind": "attachment", "assetId": "asset-1", "parentDocumentId": "parent-1",
        "relationType": "attachment_chunk", "indexVersion": "unchanged-old",
        "sourceUrl": "https://www.chinatax.gov.cn/test", "documentId": "parent-1@asset-1",
    }


class FakeES:
    def __init__(self) -> None:
        self.source = {
            "a": attachment(),
            "b": {**attachment("b"), "assetKind": "baseline"},
            "c": {**attachment("c"), "channel": "法律"},
        }
        self.mapping: dict[str, Any] = {
            "_meta": {"mapping_version": "old", "keep": "unchanged"},
            "properties": {"embedding": {"type": "dense_vector", "dims": 1024,
                                          "index_options": {"type": "bbq_hnsw"}},
                           "chunkId": {"type": "keyword"}},
        }
        self.source_definition: dict[str, Any] = {
            "settings": {"index": {"uuid": "source-uuid", "blocks": {"write": "true"},
                                   "number_of_replicas": "0", "number_of_shards": "1"}},
            "aliases": {"policy-read": {}}, "mappings": self.mapping,
        }
        self.target: dict[str, dict[str, Any]] | None = None
        self.target_definition: dict[str, Any] | None = None
        self.calls: list[tuple[str, str, bytes]] = []
        self.mode = "normal"
        self.bulk_count = 0
        self.target_scans = 0
        self.seq = 5

    def spec(self) -> VectorCandidateSpec:
        return VectorCandidateSpec(SOURCE, "source-uuid", mapping_fingerprint(self.mapping),
                                   independent_fingerprint(self.source), len(self.source),
                                   len(self.source) - 1, len(self.source) - 2, TARGET, MODEL_SHA)

    def client(self, **kwargs: Any) -> httpx.Client:
        return httpx.Client(base_url="http://127.0.0.1:9200", timeout=30, trust_env=False,
                            transport=httpx.MockTransport(self.handle), **kwargs)

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method
        self.calls.append((method, path, request.content))
        if path == f"/{SOURCE}" and method == "GET":
            return httpx.Response(200, json={SOURCE: self.source_definition})
        if path == f"/{TARGET}" and method == "HEAD":
            return httpx.Response(404 if self.target is None else 200)
        if path == f"/{TARGET}" and method == "GET":
            if self.mode == "ownership_unknown":
                return httpx.Response(503)
            if self.target_definition is None:
                return httpx.Response(404)
            return httpx.Response(200, json={TARGET: self.target_definition})
        if path.startswith("/_cluster/health/"):
            failed = self.mode == "not_ready" and path.endswith(TARGET)
            return httpx.Response(200, json={"status": "yellow" if failed else "green",
                                            "timed_out": failed})
        if path == f"/{SOURCE}/_clone/{TARGET}":
            assert json.loads(request.content) == {"settings": {
                "index.number_of_replicas": "0", "index.blocks.write": True}}
            self.target = copy.deepcopy(self.source)
            self.target_definition = copy.deepcopy(self.source_definition)
            self.target_definition["aliases"] = {}
            self.target_definition["settings"]["index"].update({
                "uuid": "candidate-uuid", "resize": {"source": {"name": SOURCE, "uuid": "source-uuid"}}})
            if self.mode in ("clone_ambiguous", "ownership_unknown"):
                raise httpx.ReadTimeout(SECRET)
            if self.mode == "clone_tamper":
                self.target["c"]["embedding"][0] = 1
            if self.mode == "clone_alias":
                self.target_definition["aliases"] = {"do-not-touch": {}}
            if self.mode == "clone_wrong_parent":
                self.target_definition["settings"]["index"]["resize"]["source"]["uuid"] = "other"
            if self.mode not in {"clone_wrong_parent", "clone_alias"}:
                self.target_definition["settings"]["index"].pop("resize")
            return httpx.Response(200, json={"acknowledged": True, "shards_acknowledged": False,
                                            "index": TARGET})
        if path.endswith("/_search"):
            candidate = path == f"/{TARGET}/_search"
            docs = self.target if candidate else self.source
            assert docs is not None
            body = json.loads(request.content)
            assert body["_source"] == {"exclude_vectors": False}
            assert body["query"] == {"match_all": {}}
            if candidate:
                self.target_scans += 1
            after = body.get("search_after", [""])[0]
            entries = [
                {"_index": TARGET if candidate else SOURCE, "_id": key, "_source": value,
                 "sort": [value["chunkId"]], "_seq_no": self.seq, "_primary_term": 1}
                for key, value in sorted(docs.items(), key=lambda item: item[1]["chunkId"])
                if value["chunkId"] > after
            ][:body["size"]]
            if self.mode == "scan_empty":
                entries = []
            if self.mode == "duplicate_id" and entries:
                entries[-1]["_id"] = entries[0]["_id"]
            if self.mode == "duplicate_chunk" and entries:
                entries[-1]["_source"] = entries[0]["_source"]
                entries[-1]["sort"] = entries[0]["sort"]
            return httpx.Response(200, json={
                "timed_out": self.mode == "scan_timeout",
                "_shards": {"failed": 1 if self.mode == "scan_shard_failure" else 0,
                            "total": 1, "successful": 1},
                "hits": {"total": {"value": len(docs), "relation": "eq"}, "hits": entries},
            })
        assert self.target_definition is not None
        if path == f"/{TARGET}/_settings":
            body = json.loads(request.content)
            if self.mode == "seal_failure" and body["index.blocks.write"] is True:
                return httpx.Response(500, text=SECRET)
            self.target_definition["settings"]["index"]["blocks"]["write"] = body["index.blocks.write"]
            return httpx.Response(200, json={"acknowledged": True})
        if path == f"/{TARGET}/_mapping":
            body = json.loads(request.content)
            assert set(body) == {"_meta", "properties"}
            assert set(body["properties"]) == set(TRACE_FIELDS)
            self.target_definition["mappings"]["_meta"] = body["_meta"]
            self.target_definition["mappings"]["properties"].update(body["properties"])
            return httpx.Response(200, json={"acknowledged": True})
        if path == f"/{TARGET}/_bulk":
            self.bulk_count += 1
            lines = [json.loads(line) for line in request.content.splitlines()]
            assert 1 <= len(lines) // 2 <= 32
            assert self.target is not None
            items = []
            for head, data in zip(lines[::2], lines[1::2], strict=True):
                op = head["update"]
                assert set(op) == {"_id", "if_seq_no", "if_primary_term"}
                assert op["if_seq_no"] == self.seq and op["if_primary_term"] == 1
                assert set(data) == {"doc"}
                assert set(data["doc"]) == {"embedding", *TRACE_FIELDS}
                if self.mode == "bulk_conflict":
                    return httpx.Response(200, json={"errors": True, "items": [
                        {"update": {"status": 409, "error": {"reason": SECRET}}}]})
                self.target[op["_id"]].update(data["doc"])
                items.append({"update": {"status": 200, "result": "updated",
                                         "_index": TARGET, "_id": op["_id"]}})
            return httpx.Response(200, json={"errors": False, "items": items})
        if path == f"/{TARGET}/_refresh":
            assert self.target is not None
            if self.mode == "final_law_tamper":
                self.target["c"]["embedding"][0] = 0.75
            if self.mode == "final_body_tamper":
                self.target["a"]["content"] = "tampered"
            if self.mode == "final_source_alias_tamper":
                self.source_definition["aliases"] = {"changed": {}}
            return httpx.Response(200, json={"_shards": {"failed": 0}})
        raise AssertionError((method, path))


def execute(es: FakeES, spec: VectorCandidateSpec | None = None, prepare: Any = None) -> Any:
    with es.client() as client:
        return build_policy_vector_candidate(spec or es.spec(), client=client,
                                            prepare_vectors=prepare or (lambda reps: tuple(NEW for _ in reps)))


def assert_no_writes(es: FakeES) -> None:
    assert all(method in ("GET", "HEAD") or path.endswith("/_search")
               for method, path, _ in es.calls)


def test_clone_preserves_all_source_values_only_attachment_vector_changes() -> None:
    es = FakeES()
    original = copy.deepcopy(es.source)
    definition = copy.deepcopy(es.source_definition)
    inputs = []
    def prepare(reps: Any) -> Any:
        inputs.extend(reps)
        assert_no_writes(es)
        return (NEW,)
    result = execute(es, prepare=prepare)
    assert result.updated_count == 1 and result.total_count == 3 and result.policy_count == 2
    assert result.http_requests == len(es.calls)
    assert result.candidate_uuid == "candidate-uuid"
    assert "resize" not in es.target_definition["settings"]["index"]
    assert len(inputs) == 1 and inputs[0].text == "测试标题\n第一条\n" + SECRET
    assert es.source == original and es.source_definition == definition
    assert es.target is not None and es.target_definition is not None
    assert es.target["b"] == original["b"] and es.target["c"] == original["c"]
    assert {k: v for k, v in es.target["a"].items() if k not in TRACE_FIELDS and k != "embedding"} == {
        k: v for k, v in original["a"].items() if k != "embedding"}
    assert es.target["a"]["embedding"] == list(NEW)
    assert es.target["a"]["vectorModelSnapshotSha256"] == MODEL_SHA
    assert es.target_definition["aliases"] == {}
    assert es.target_definition["settings"]["index"]["blocks"]["write"] is True
    assert es.target_definition["mappings"]["_meta"]["mapping_version"] == MAPPING_VERSION
    assert es.target_definition["mappings"]["properties"]["embedding"] == es.mapping["properties"]["embedding"]
    assert all("/_aliases" not in path and method != "DELETE" for method, path, _ in es.calls)
    with pytest.raises(FrozenInstanceError):
        result.updated_count = 2
    with pytest.raises(CandidateError, match="candidate_exists"):
        execute(es)


@pytest.mark.parametrize("mode", ["scan_empty", "duplicate_id", "duplicate_chunk", "scan_timeout", "scan_shard_failure"])
def test_bad_source_scan_has_zero_prepare_and_writes(mode: str) -> None:
    es = FakeES()
    es.mode = mode
    def prepare(_: Any) -> Any:
        pytest.fail("must not prepare")
    with pytest.raises(CandidateError):
        execute(es, prepare=prepare)
    assert_no_writes(es)


@pytest.mark.parametrize("field,value", [
    ("source_uuid", "different"), ("mapping_sha256", "0" * 64),
    ("source_fingerprint", "0" * 64), ("total_count", 4), ("policy_count", 3),
    ("attachment_count", 2),
])
def test_binding_changes_stop_before_prepare(field: str, value: Any) -> None:
    es = FakeES()
    spec = replace(es.spec(), **{field: value})
    with pytest.raises(CandidateError):
        execute(es, spec, lambda _: pytest.fail("must not prepare"))
    assert_no_writes(es)


@pytest.mark.parametrize("field,value", [
    ("source_index", "../bad"), ("candidate_index", SOURCE), ("candidate_index", "other-index"),
    ("candidate_index", TARGET + "/_delete_by_query"), ("model_snapshot_sha256", "secret"),
    ("total_count", True), ("total_count", 20001), ("attachment_count", 0),
    ("attachment_count", 1001), ("source_uuid", "../uuid"),
])
def test_spec_rejects_invalid_paths_counts_hashes(field: str, value: Any) -> None:
    with pytest.raises(CandidateError, match="spec_invalid"):
        replace(FakeES().spec(), **{field: value})


@pytest.mark.parametrize("vector", [[], [0.0] * 1024, [True] * 1024, ["1"] * 1024,
                                   [float("nan")] * 1024, [float("inf")] * 1024,
                                   [1e40] * 1024, [1e-50] * 1024])
def test_prepared_vectors_strict_zero_writes(vector: Any) -> None:
    es = FakeES()
    with pytest.raises(CandidateError, match="vector_invalid"):
        execute(es, prepare=lambda _: (vector,))
    assert_no_writes(es)


@pytest.mark.parametrize("shape", [[], (), (NEW, NEW), {"vectors": [NEW]}])
def test_prepared_shape_strict_zero_writes(shape: Any) -> None:
    es = FakeES()
    with pytest.raises(CandidateError, match="prepared_shape_invalid"):
        execute(es, prepare=lambda _: shape)
    assert_no_writes(es)


@pytest.mark.parametrize("field,value", [("relationType", "other"), ("assetId", ""),
                                       ("parentDocumentId", ""), ("aclRef", ""),
                                       ("contentHash", "0" * 64)])
def test_invalid_attachment_is_not_silently_skipped(field: str, value: Any) -> None:
    es = FakeES()
    es.source["a"][field] = value
    with pytest.raises(CandidateError):
        execute(es)
    assert_no_writes(es)


@pytest.mark.parametrize("mode,reason,sealed", [
    ("not_ready", "index_not_ready", "sealed"),
    ("clone_ambiguous", "http_or_json_invalid", "sealed"),
    ("ownership_unknown", "http_or_json_invalid", "candidate_seal_failed"),
    ("clone_wrong_parent", "candidate_identity_invalid", "candidate_seal_failed"),
    ("clone_alias", "candidate_alias_forbidden", "candidate_seal_failed"),
    ("clone_tamper", "clone_content_changed", "sealed"),
    ("bulk_conflict", "bulk_failed", "sealed"),
    ("seal_failure", "http_status_invalid", "candidate_seal_failed"),
    ("final_law_tamper", "candidate_content_changed", "sealed"),
    ("final_body_tamper", "candidate_content_changed", "sealed"),
    ("final_source_alias_tamper", "source_binding_changed", "sealed"),
])
def test_failures_seal_only_owned_candidate_without_retry(mode: str, reason: str, sealed: str) -> None:
    es = FakeES()
    es.mode = mode
    with pytest.raises(CandidateError) as captured:
        execute(es)
    error = captured.value
    assert error.reason == reason and error.seal_status == sealed
    assert SECRET not in str(error) and error.__context__ is None and error.__cause__ is None
    assert sum("/_clone/" in path for _, path, _ in es.calls) == 1
    assert es.bulk_count <= 1
    assert all(method != "DELETE" and "_aliases" not in path for method, path, _ in es.calls)
    if sealed == "sealed":
        assert es.target_definition["settings"]["index"]["blocks"]["write"] is True


def test_prepare_exception_does_not_retain_private_input() -> None:
    es = FakeES()
    def prepare(_: Any) -> Any:
        raise RuntimeError(SECRET)
    with pytest.raises(CandidateError) as captured:
        execute(es, prepare=prepare)
    assert captured.value.reason == "operation_invalid"
    assert captured.value.__context__ is None and SECRET not in str(captured.value)
    assert_no_writes(es)


def test_pagination_and_bulk_batches() -> None:
    es = FakeES()
    for index in range(260):
        key = f"d-{index:04}"
        es.source[key] = attachment(key)
    result = execute(es)
    assert result.updated_count == 261 and result.total_count == 263
    assert es.bulk_count == 9
    assert sum(path.endswith("/_search") for _, path, _ in es.calls) == 6


def test_catalog_matches_current_java_category_binding() -> None:
    from pathlib import Path
    text = (Path(__file__).resolve().parents[2] / "es-query-service/src/main/resources/application-knowledge-live.yml").read_text(encoding="utf-8")
    policy = text.split("category-values:", 1)[1].split("keyword-fields:", 1)[0]
    assert "category-field: channel" in text
    actual = {line.strip()[2:] for line in policy.splitlines() if line.strip().startswith("- ")}
    assert actual == POLICY_CATEGORIES


@pytest.mark.parametrize("kwargs", [{"base_url": "https://127.0.0.1:9200"},
                                    {"base_url": "http://example.com"},
                                    {"base_url": "http://127.0.0.1:9200/path"},
                                    {"base_url": "http://user:pass@127.0.0.1:9200"},
                                    {"follow_redirects": True}, {"trust_env": True},
                                    {"timeout": None}, {"timeout": 31}])
def test_invalid_client_never_calls_transport(kwargs: dict[str, Any]) -> None:
    options = {"base_url": "http://127.0.0.1:9200", "timeout": 30, "trust_env": False, **kwargs}
    with httpx.Client(**options, transport=httpx.MockTransport(lambda _: pytest.fail("zero calls"))) as client:
        with pytest.raises(CandidateError, match="client_invalid"):
            build_policy_vector_candidate(FakeES().spec(), client=client, prepare_vectors=lambda _: ())


@pytest.mark.parametrize("response", [
    httpx.Response(302, headers={"Location": "http://example.com"}),
    httpx.Response(200, content=b'{"secret":"first","secret":"second"}'),
    httpx.Response(200, content=b'{"bad":NaN}'), httpx.Response(200, content=b'[]'),
    httpx.Response(200, content=b'not json'),
])
def test_transport_invalid_responses_are_finite_no_retry(response: httpx.Response) -> None:
    calls = []
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        return response
    with httpx.Client(base_url="http://127.0.0.1:9200", timeout=30, trust_env=False,
                      transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(CandidateError) as captured:
            build_policy_vector_candidate(FakeES().spec(), client=client, prepare_vectors=lambda _: ())
    assert len(calls) == 1
    assert captured.value.__context__ is None
    assert "first" not in str(captured.value)


def test_response_limit_rejects_before_prepare(monkeypatch: pytest.MonkeyPatch) -> None:
    import knowledge_corpus_tools.vector_candidate as module
    monkeypatch.setattr(module, "MAX_RESPONSE_BYTES", 32)
    es = FakeES()
    with pytest.raises(CandidateError, match="response_limit_exceeded"):
        execute(es)
    assert_no_writes(es)


def test_elapsed_response_timeout_is_finite(monkeypatch: pytest.MonkeyPatch) -> None:
    import knowledge_corpus_tools.vector_candidate as module
    from types import SimpleNamespace
    ticks = iter((0, 31))
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: next(ticks)))
    es = FakeES()
    with pytest.raises(CandidateError, match="response_timeout"):
        execute(es)
    assert_no_writes(es)


def test_total_http_budget_reserves_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    import knowledge_corpus_tools.vector_candidate as module
    es = FakeES()
    monkeypatch.setattr(module, "MAX_REQUESTS", 3)
    with pytest.raises(CandidateError, match="http_budget_exhausted"):
        execute(es)
    assert len(es.calls) == 2
    assert_no_writes(es)


def test_source_is_rechecked_after_model_preparation() -> None:
    es = FakeES()
    def prepare(_: Any) -> Any:
        es.source_definition["aliases"] = {"changed": {}}
        return (NEW,)
    with pytest.raises(CandidateError, match="source_binding_changed"):
        execute(es, prepare=prepare)
    assert_no_writes(es)


@pytest.mark.parametrize("field", TRACE_FIELDS)
def test_reserved_fields_fail_before_model(field: str) -> None:
    es = FakeES()
    es.source["b"][field] = "previous-representation"
    with pytest.raises(CandidateError, match="trace_fields_present"):
        execute(es, prepare=lambda _: pytest.fail("zero model"))
    assert_no_writes(es)


def test_cancel_seals_then_propagates() -> None:
    es = FakeES()
    original = es.handle
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/_bulk"):
            raise KeyboardInterrupt()
        return original(request)
    with httpx.Client(base_url="http://127.0.0.1:9200", timeout=30, trust_env=False,
                      transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(KeyboardInterrupt) as captured:
            build_policy_vector_candidate(es.spec(), client=client, prepare_vectors=lambda _: (NEW,))
    assert captured.value.__notes__ == ["candidate_cleanup:sealed"]
    assert es.target_definition["settings"]["index"]["blocks"]["write"] is True


@pytest.mark.parametrize("mutation,reason", [
    ("bulk_id", "bulk_failed"), ("final_mapping", "candidate_mapping_changed"),
    ("final_unsealed", "candidate_not_sealed"), ("clone_replicas", "clone_settings_changed"),
    ("final_vector", "candidate_content_changed"),
])
def test_postconditions_detect_wrong_receipts_or_tampering(mutation: str, reason: str) -> None:
    es = FakeES()
    original = es.handle
    def handler(request: httpx.Request) -> httpx.Response:
        response = original(request)
        if mutation == "bulk_id" and request.url.path.endswith("/_bulk"):
            data = response.json()
            data["items"][0]["update"]["_id"] = "wrong"
            return httpx.Response(200, json=data)
        if mutation == "clone_replicas" and "/_clone/" in request.url.path:
            es.target_definition["settings"]["index"]["number_of_replicas"] = "1"
        if request.url.path.endswith("/_refresh"):
            if mutation == "final_mapping":
                es.target_definition["mappings"]["properties"]["embedding"]["dims"] = 512
            if mutation == "final_vector":
                es.target["a"]["embedding"][0] = 0.5
        if (mutation == "final_unsealed" and request.method == "PUT"
                and request.url.path.endswith("/_settings")):
            es.target_definition["settings"]["index"]["blocks"]["write"] = False
        return response
    with httpx.Client(base_url="http://127.0.0.1:9200", timeout=30, trust_env=False,
                      transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(CandidateError, match=reason):
            build_policy_vector_candidate(es.spec(), client=client, prepare_vectors=lambda _: (NEW,))


def test_non_target_vector_float32_preserved_not_original_double() -> None:
    es = FakeES()
    es.source["c"]["embedding"] = [0.1234567890123] * 1024
    assert execute(es).total_count == 3
    assert es.target["c"]["embedding"] == es.source["c"]["embedding"]


def test_non_native_text_is_not_unicode_normalized() -> None:
    es = FakeES()
    es.source["b"]["untouched"] = "e\u0301"
    execute(es)
    assert es.target["b"]["untouched"] == "e\u0301"


@pytest.mark.parametrize("field,value", [("data_stream", "do-not-clone"), ("write", False), ("write", 1)])
def test_source_must_be_write_blocked_and_not_data_stream(field: str, value: Any) -> None:
    es = FakeES()
    if field == "data_stream":
        es.source_definition[field] = value
    else:
        es.source_definition["settings"]["index"]["blocks"][field] = value
    with pytest.raises(CandidateError):
        execute(es)
    assert_no_writes(es)


def test_error_codes_are_finite_even_from_untrusted_callback() -> None:
    error = CandidateError(SECRET, phase=SECRET, seal_status=SECRET)
    assert str(error) == "validation:operation_invalid:candidate_seal_failed"
    es = FakeES()
    def prepare(_: Any) -> Any:
        raise CandidateError(SECRET, phase=SECRET)
    with pytest.raises(CandidateError) as captured:
        execute(es, prepare=prepare)
    assert str(captured.value) == "prepare:operation_invalid:not_needed"
    assert captured.value.__context__ is None
    assert_no_writes(es)


def test_mutated_callback_error_is_sanitized_at_public_boundary() -> None:
    es = FakeES()
    def prepare(_: Any) -> Any:
        error = CandidateError("vector_invalid", phase="prepare")
        error.reason = SECRET
        raise error
    with pytest.raises(CandidateError) as captured:
        execute(es, prepare=prepare)
    assert SECRET not in str(captured.value) and captured.value.reason == "operation_invalid"
    assert captured.value.__context__ is None


@pytest.mark.parametrize("field,value", [("index", None), ("index", SOURCE),
                                         ("acknowledged", False), ("acknowledged", 1),
                                         ("shards_acknowledged", None), ("shards_acknowledged", 1)])
def test_unbound_clone_receipt_without_transient_source_never_writes_again(field: str, value: Any) -> None:
    es = FakeES()
    original = es.handle
    def handle(request: httpx.Request) -> httpx.Response:
        response = original(request)
        if "/_clone/" in request.url.path:
            payload = response.json()
            payload[field] = value
            return httpx.Response(200, json=payload)
        return response
    es.handle = handle  # type: ignore[method-assign]
    with pytest.raises(CandidateError) as caught:
        execute(es)
    assert caught.value.reason == "write_not_acknowledged"
    assert caught.value.seal_status == "candidate_seal_failed"
    assert es.bulk_count == 0
    assert not any(method == "PUT" for method, _, _ in es.calls)


def test_ambiguous_clone_with_source_metadata_already_removed_never_claims_ownership() -> None:
    es = FakeES()
    original = es.handle
    def handle(request: httpx.Request) -> httpx.Response:
        response = original(request)
        if "/_clone/" in request.url.path:
            raise httpx.ReadTimeout(SECRET)
        return response
    es.handle = handle  # type: ignore[method-assign]
    with pytest.raises(CandidateError) as caught:
        execute(es)
    assert caught.value.reason == "http_or_json_invalid"
    assert caught.value.seal_status == "candidate_seal_failed"
    assert not any(method == "PUT" for method, _, _ in es.calls)
    assert es.bulk_count == 0


def test_uuid_is_bound_before_green_and_replacement_is_never_modified() -> None:
    es = FakeES()
    original = es.handle
    reads = 0
    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal reads
        response = original(request)
        if request.method == "GET" and request.url.path == f"/{TARGET}":
            reads += 1
        if request.url.path == f"/_cluster/health/{TARGET}":
            assert reads == 1
            es.target_definition["settings"]["index"]["uuid"] = "replacement"
        return response
    es.handle = handle  # type: ignore[method-assign]
    with pytest.raises(CandidateError) as caught:
        execute(es)
    assert caught.value.reason == "candidate_identity_invalid"
    assert caught.value.seal_status == "candidate_seal_failed"
    assert not any(method == "PUT" for method, _, _ in es.calls)


@pytest.mark.parametrize("parent,valid", [({"name": SOURCE}, True), ({"uuid": "source-uuid"}, True),
                                        ({"name": "other"}, False), ({"uuid": "other"}, False),
                                        ({"extra": "unknown"}, False), (None, False)])
def test_transient_source_fields_still_require_exact_identity(parent: Any, valid: bool) -> None:
    es = FakeES()
    original = es.handle
    def handle(request: httpx.Request) -> httpx.Response:
        response = original(request)
        if "/_clone/" in request.url.path:
            es.target_definition["settings"]["index"]["resize"] = {"source": parent}
        return response
    es.handle = handle  # type: ignore[method-assign]
    if valid:
        execute(es)
    else:
        with pytest.raises(CandidateError):
            execute(es)
        assert not any(method == "PUT" for method, _, _ in es.calls)
