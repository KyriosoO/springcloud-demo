"""B preparation fake tests; MockTransport never opens ES or BGE sockets."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from knowledge_corpus_tools.b_assessment_prepare_v1 import (
    BPrepareError, bind_b_request_v1, prepare_b_intent_v1,
)
from knowledge_corpus_tools.b_candidate_freeze_v1 import GitState, _intent
from knowledge_corpus_tools.retrieval_representation_v2 import build_retrieval_representation_v2
from knowledge_corpus_tools.vector_candidate import canonical_bytes, mapping_fingerprint
from knowledge_corpus_tools.vector_representation import build_vector_representation


FIXTURE = (Path(__file__).resolve().parents[2] / "agent-runtime" / "tests" /
           "uat" / "knowledge_rebuild_measure.v1.json").read_bytes()
MANIFEST = (Path(__file__).resolve().parents[1] / "evidence" /
            "asset-manifest.candidate-08.jsonl").read_bytes()
HEAD = "a" * 40
COUNTS = (342, 149, 187, 60)
ASSETS = (
    "asset-0b9c99e7dfb27c8e600743d7",
    "asset-5cac035a23b63ebf01ea1a3e",
    "asset-9ddc228c43d9e2758c5c0db2",
    "asset-45bb466b54ad7d636c7a0abb",
)
PARENT = "tax-50abf52b7a181b8974c97fd4"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class FakeScopedEs:
    def __init__(self) -> None:
        model = json.loads((Path(__file__).resolve().parents[1] / "evidence" /
                            "policy-vector-candidate-20260907-b2" / "binding.json").read_bytes())["modelSnapshot"]
        self.old_model = model
        self.current_model = copy.deepcopy(model)
        self.current_model["container"]["started"] = "2026-09-29T00:00:00Z"
        self.mapping = {"_meta": {"mapping_version": "baseline-map-v1"},
                        "properties": {"content": {"type": "text"}}}
        self.alias: dict[str, Any] = {"source-index": {"aliases": {"read-alias": {}}}}
        self.definition = {"source-index": {
            "settings": {"index": {"uuid": "source-uuid", "blocks": {"write": "true"}}},
            "mappings": self.mapping, "aliases": {"read-alias": {}},
        }}
        self.assets = ASSETS
        self.manifest = MANIFEST
        versions = {item["asset_id"]: item["asset_version"]
                    for item in map(json.loads, self.manifest.splitlines())}
        self.records: list[tuple[str, dict[str, Any]]] = []
        ordinal = 0
        for asset_id, count in zip(self.assets, COUNTS, strict=True):
            for _ in range(count):
                content = f"税务资料第{ordinal}项原文。"
                old = build_vector_representation(content=content, title="资料标题")
                fields = {
                    "documentId": PARENT + "@" + asset_id,
                    "chunkId": f"chunk-{ordinal:04d}",
                    "parentDocumentId": PARENT, "assetId": asset_id,
                    "assetVersion": versions[asset_id], "channel": "税务规范性文件",
                    "content": content, "title": "资料标题", "section": "",
                    "vectorRepresentationVersion": old.version,
                    "vectorModelSnapshotSha256": sha(canonical_bytes(self.old_model)),
                    "vectorBodySha256": old.content_sha256,
                    "vectorInputSha256": old.input_sha256,
                }
                self.records.append((f"es-{ordinal:04d}", fields))
                ordinal += 1
        self.calls: list[tuple[str, str]] = []
        self.alias_drift_on_last = False
        self.truncate_page = False

    def handle(self, request: httpx.Request) -> httpx.Response:
        method, path = request.method, request.url.path
        self.calls.append((method, path))
        if method == "GET" and path == "/source-index":
            return httpx.Response(200, json=self.definition)
        if method == "GET" and path == "/_alias/read-alias":
            if self.alias_drift_on_last and len(self.calls) >= 7:
                return httpx.Response(200, json={"source-index": {"aliases": {"read-alias": {
                    "is_write_index": True}}}})
            return httpx.Response(200, json=self.alias)
        if method == "POST" and path == "/source-index/_search":
            body = json.loads(request.content)
            assert body["query"] == {"terms": {"assetId": list(self.assets)}}
            assert body["size"] <= 250
            after = body.get("search_after", [""])[0]
            selected = [(identifier, fields) for identifier, fields in self.records
                        if fields["chunkId"] > after][:body["size"]]
            if self.truncate_page and selected:
                selected.pop()
            return httpx.Response(200, json={
                "timed_out": False,
                "_shards": {"failed": 0, "total": 1, "successful": 1},
                "hits": {"total": {"value": 738, "relation": "eq"},
                         "hits": [{"_index": "source-index", "_id": identifier,
                                   "_source": fields, "sort": [fields["chunkId"]]}
                                  for identifier, fields in selected]},
            })
        raise AssertionError(f"unexpected fake request: {method} {path}")

    def inputs(self) -> tuple[bytes, bytes, bytes, bytes, dict[str, bytes]]:
        fixture = json.loads(FIXTURE)
        fixture["sourceCorpus"].update({
            "readAlias": "read-alias", "index": "source-index",
            "indexUuid": "source-uuid", "recordCount": 738,
            "mappingSha256": mapping_fingerprint(self.mapping),
            "fullFingerprint": "f" * 64,
        })
        selection = canonical_bytes({
            "schemaVersion": 1, "manifestSha256": sha(self.manifest),
            "assetIds": list(self.assets), "expectedChunkCounts": list(COUNTS),
        })
        source_build_binding = canonical_bytes({
            "modelSnapshot": self.old_model,
            "spec": {"candidate_index": "source-index", "total_count": 738,
                     "model_snapshot_sha256": sha(canonical_bytes(self.old_model))},
        })
        source_build_result = canonical_bytes({
            "status": "built_read_only_unpublished", "bindingSha256": sha(source_build_binding),
            "candidate": "source-index", "aliasWrites": 0, "paid": 0, "retry": 0,
            "resume": 0, "result": {
                "candidate_index": "source-index", "candidate_uuid": "source-uuid",
                "candidate_fingerprint": "f" * 64, "total_count": 738,
                "model_snapshot_sha256": sha(canonical_bytes(self.old_model)),
                "representation_version": "policy-title-section-body-v1",
            },
        })
        preparation = canonical_bytes({
            "schemaVersion": 1, "runId": "knowledge-b-fake-v1", "frozenHead": HEAD,
            "candidate": {
                "source_index": "source-index", "source_uuid": "source-uuid",
                "source_mapping_sha256": mapping_fingerprint(self.mapping),
                "source_fingerprint": "f" * 64, "source_count": 738,
                "read_alias": "read-alias", "online_index": "source-index",
                "online_uuid": "source-uuid",
                "online_mapping_sha256": mapping_fingerprint(self.mapping),
                "alias_snapshot_sha256": sha(canonical_bytes(self.alias)),
                "candidate_index": "candidate-index",
                "target_mapping_version": "candidate-map-v1",
                "target_mapping_sha256": "c" * 64,
                "baseline_model_snapshot": self.old_model,
                "model_snapshot": self.current_model,
                "tokenizer_sha256": "d" * 64,
                "baseline_representation_version": "policy-title-section-body-v1",
            },
            "profileParameters": {
                domain: {"profileId": profile_id,
                         "profileVersion": "tax-knowledge-search-v1",
                         "readPolicyVersion": "tax-public-authenticated-v1",
                         "baselineMappingVersion": "baseline-map-v1",
                         "candidateMappingVersion": "candidate-map-v1",
                         "configSha256": "e" * 64}
                for domain, profile_id in (("tax.policy", "tax-policy-v1"),
                                           ("tax.law", "tax-law-v1"))},
            "comparisonMetadataEsHttp": 30,
        })
        evidence = {
            "knowledge-corpus-tools/evidence/policy-vector-candidate-20260907-b2/binding.json": source_build_binding,
            "knowledge-corpus-tools/evidence/policy-vector-candidate-20260907-b2/result.json": source_build_result,
        }
        return canonical_bytes(fixture), selection, preparation, self.manifest, evidence

    def mapping_raw(self) -> bytes:
        return canonical_bytes({
            "schemaVersion": 1, "indexName": "source-index",
            "indexUuid": "source-uuid", "sourceFingerprint": "f" * 64,
            "recordCount": 738,
            "records": [{"id": identifier, "documentId": fields["documentId"],
                         "chunkId": fields["chunkId"],
                         "contentSha256": sha(fields["content"].encode())}
                        for identifier, fields in self.records],
        })


def run(fake: FakeScopedEs) -> tuple[bytes, bytes]:
    fixture, selection, preparation, manifest, evidence = fake.inputs()
    with httpx.Client(base_url="http://127.0.0.1:9200", timeout=30,
                      trust_env=False, follow_redirects=False,
                      transport=httpx.MockTransport(fake.handle)) as client:
        prepared = prepare_b_intent_v1(
            client=client, fixture_raw=fixture, selection_raw=selection,
            asset_manifest_raw=manifest, preparation_raw=preparation,
            git_state=GitState("codex_0915", HEAD, True),
            fixture_blob_reader=lambda _head: fixture,
            source_build_blob_reader=lambda _head, path: evidence[path],
        )
    assert prepared.scoped_es_http == prepared.scoped_es_http_max == 7
    assert len(prepared.representation_bindings) == 738
    _intent(prepared.intent_raw, fixture)
    return prepared.intent_raw, prepared.preliminary_raw


def test_scoped_preparation_is_canonical_bounded_and_content_free() -> None:
    fake = FakeScopedEs()
    intent, preliminary = run(fake)
    assert fake.calls == [
        ("GET", "/source-index"), ("GET", "/_alias/read-alias"),
        *( ("POST", "/source-index/_search") for _ in range(3)),
        ("GET", "/source-index"), ("GET", "/_alias/read-alias"),
    ]
    assert b"\xe7\xa8\x8e\xe5\x8a\xa1\xe8\xb5\x84\xe6\x96\x99" not in intent
    assert json.loads(intent)["representationBindings"][0]["identifier"] == "es-0000"
    request = bind_b_request_v1(preliminary_raw=preliminary,
                                source_id_mapping_raw=fake.mapping_raw())
    assert json.loads(request)["idMappingSha256"] == sha(fake.mapping_raw())
    assert canonical_bytes(json.loads(request)) == request


@pytest.mark.parametrize("budget", [0, 20, 31, 512, True, "30"])
def test_comparison_metadata_budget_must_be_exact_before_first_es_http(budget: object) -> None:
    fake = FakeScopedEs()
    fixture, selection, preparation, manifest, evidence = fake.inputs()
    changed = json.loads(preparation)
    changed["comparisonMetadataEsHttp"] = budget
    preparation = canonical_bytes(changed)
    with httpx.Client(base_url="http://127.0.0.1:9200", timeout=30,
                      trust_env=False, follow_redirects=False,
                      transport=httpx.MockTransport(fake.handle)) as client:
        with pytest.raises(BPrepareError, match="input_invalid") as raised:
            prepare_b_intent_v1(
                client=client, fixture_raw=fixture, selection_raw=selection,
                asset_manifest_raw=manifest, preparation_raw=preparation,
                git_state=GitState("codex_0915", HEAD, True),
                fixture_blob_reader=lambda _head: fixture,
                source_build_blob_reader=lambda _head, path: evidence[path],
            )
    assert fake.calls == []
    assert raised.value.__context__ is None


@pytest.mark.parametrize("fault", ["trace", "asset_version", "channel", "short_page", "alias_drift"])
def test_scoped_preparation_refuses_drift_without_retry_or_artifacts(fault: str) -> None:
    fake = FakeScopedEs()
    if fault == "trace":
        fake.records[0][1]["vectorInputSha256"] = "0" * 64
    elif fault == "asset_version":
        fake.records[0][1]["assetVersion"] = "0" * 64
    elif fault == "channel":
        fake.records[0][1]["channel"] = "other"
    elif fault == "short_page":
        fake.truncate_page = True
    else:
        fake.alias_drift_on_last = True
    fixture, selection, preparation, manifest, evidence = fake.inputs()
    with httpx.Client(base_url="http://127.0.0.1:9200", timeout=30,
                      trust_env=False, follow_redirects=False,
                      transport=httpx.MockTransport(fake.handle)) as client:
        with pytest.raises(BPrepareError):
            prepare_b_intent_v1(
                client=client, fixture_raw=fixture, selection_raw=selection,
                asset_manifest_raw=manifest, preparation_raw=preparation,
                git_state=GitState("codex_0915", HEAD, True),
                fixture_blob_reader=lambda _head: fixture,
                source_build_blob_reader=lambda _head, path: evidence[path],
            )
    assert len(fake.calls) <= 7
    assert all(method in ("GET", "POST") and not path.endswith("/_bulk")
               for method, path in fake.calls)


@pytest.mark.parametrize("fault", [
    "asset_selection", "manifest_bytes", "mapping_version", "current_model_drift",
    "current_started_missing", "old_model_trace", "old_body_trace",
])
def test_preparation_rejects_unregistered_assets_and_provenance_drift(fault: str) -> None:
    fake = FakeScopedEs()
    if fault == "mapping_version":
        meta = fake.mapping["_meta"]
        assert type(meta) is dict
        meta["mapping_version"] = "other-map-v1"
    elif fault == "current_model_drift":
        model = fake.current_model["model"]
        assert type(model) is dict
        model["revision"] = "other-revision"
    elif fault == "current_started_missing":
        container = fake.current_model["container"]
        assert type(container) is dict
        del container["started"]
    elif fault == "old_model_trace":
        fake.records[0][1]["vectorModelSnapshotSha256"] = "0" * 64
    elif fault == "old_body_trace":
        fake.records[0][1]["vectorBodySha256"] = "0" * 64
    fixture, selection, preparation, manifest, evidence = fake.inputs()
    if fault == "asset_selection":
        changed = json.loads(selection)
        changed["assetIds"][0] = "asset-000000000000000000000000"
        selection = canonical_bytes(changed)
    elif fault == "manifest_bytes":
        manifest += b"\n"
        changed = json.loads(selection)
        changed["manifestSha256"] = sha(manifest)
        selection = canonical_bytes(changed)
    with httpx.Client(base_url="http://127.0.0.1:9200", timeout=30,
                      trust_env=False, follow_redirects=False,
                      transport=httpx.MockTransport(fake.handle)) as client:
        with pytest.raises(BPrepareError):
            prepare_b_intent_v1(
                client=client, fixture_raw=fixture, selection_raw=selection,
                asset_manifest_raw=manifest, preparation_raw=preparation,
                git_state=GitState("codex_0915", HEAD, True),
                fixture_blob_reader=lambda _head: fixture,
                source_build_blob_reader=lambda _head, path: evidence[path],
            )
    assert len(fake.calls) <= 7


def test_request_binding_rejects_incomplete_or_changed_full_map() -> None:
    fake = FakeScopedEs()
    _, preliminary = run(fake)
    changed = json.loads(fake.mapping_raw())
    changed["records"][0]["contentSha256"] = "0" * 64
    # A changed body hash is not rejected here: the full scanner and builder
    # bind that content against source fingerprint. Missing IDs are rejected.
    changed["records"].pop()
    with pytest.raises(BPrepareError, match="binding_invalid"):
        bind_b_request_v1(preliminary_raw=preliminary,
                          source_id_mapping_raw=canonical_bytes(changed))


@pytest.mark.parametrize("fault", [
    "fixture_blob", "historical_index", "historical_uuid", "historical_fingerprint",
    "historical_count", "historical_model", "historical_representation",
    "alias_path", "source_path",
])
def test_preparation_refuses_unbound_inputs_before_first_http(fault: str) -> None:
    fake = FakeScopedEs()
    fixture, selection, preparation, manifest, evidence = fake.inputs()
    committed_fixture = fixture
    if fault == "fixture_blob":
        changed = json.loads(fixture)
        changed["cases"][0]["question"] += "伪造"
        fixture = canonical_bytes(changed)
    elif fault.startswith("historical_"):
        path = "knowledge-corpus-tools/evidence/policy-vector-candidate-20260907-b2/result.json"
        changed = json.loads(evidence[path])
        field, value = {
            "historical_index": ("candidate_index", "other-index"),
            "historical_uuid": ("candidate_uuid", "other-uuid"),
            "historical_fingerprint": ("candidate_fingerprint", "0" * 64),
            "historical_count": ("total_count", 737),
            "historical_model": ("model_snapshot_sha256", "0" * 64),
            "historical_representation": ("representation_version", "other-v1"),
        }[fault]
        changed["result"][field] = value
        evidence[path] = canonical_bytes(changed)
    elif fault == "alias_path":
        changed = json.loads(preparation)
        changed["candidate"]["read_alias"] = "read-alias/../../_delete"
        preparation = canonical_bytes(changed)
        changed_fixture = json.loads(fixture)
        changed_fixture["sourceCorpus"]["readAlias"] = "read-alias/../../_delete"
        fixture = canonical_bytes(changed_fixture)
        committed_fixture = fixture
    else:
        bad_index = "source-index/../../_delete"
        changed = json.loads(preparation)
        changed["candidate"]["source_index"] = bad_index
        preparation = canonical_bytes(changed)
        changed_fixture = json.loads(fixture)
        changed_fixture["sourceCorpus"]["index"] = bad_index
        fixture = canonical_bytes(changed_fixture)
        committed_fixture = fixture
        binding_path = "knowledge-corpus-tools/evidence/policy-vector-candidate-20260907-b2/binding.json"
        result_path = "knowledge-corpus-tools/evidence/policy-vector-candidate-20260907-b2/result.json"
        binding = json.loads(evidence[binding_path])
        binding["spec"]["candidate_index"] = bad_index
        evidence[binding_path] = canonical_bytes(binding)
        result = json.loads(evidence[result_path])
        result["bindingSha256"] = sha(evidence[binding_path])
        result["candidate"] = bad_index
        result["result"]["candidate_index"] = bad_index
        evidence[result_path] = canonical_bytes(result)
    with httpx.Client(base_url="http://127.0.0.1:9200", timeout=30,
                      trust_env=False, follow_redirects=False,
                      transport=httpx.MockTransport(fake.handle)) as client:
        with pytest.raises(BPrepareError) as raised:
            prepare_b_intent_v1(
                client=client, fixture_raw=fixture, selection_raw=selection,
                asset_manifest_raw=manifest, preparation_raw=preparation,
                git_state=GitState("codex_0915", HEAD, True),
                fixture_blob_reader=lambda _head: committed_fixture,
                source_build_blob_reader=lambda _head, path: evidence[path],
            )
    assert fake.calls == []
    assert raised.value.__context__ is None
    assert raised.value.__cause__ is None


@pytest.mark.parametrize("fault", ["source_index", "source_uuid", "source_fingerprint"])
def test_self_consistent_forged_source_still_requires_frozen_build_evidence(fault: str) -> None:
    fake = FakeScopedEs()
    fixture, selection, preparation, manifest, evidence = fake.inputs()
    changed = json.loads(preparation)
    changed_fixture = json.loads(fixture)
    candidate_field, fixture_field, value = {
        "source_index": ("source_index", "index", "other-source-index"),
        "source_uuid": ("source_uuid", "indexUuid", "other-source-uuid"),
        "source_fingerprint": ("source_fingerprint", "fullFingerprint", "0" * 64),
    }[fault]
    changed["candidate"][candidate_field] = value
    changed_fixture["sourceCorpus"][fixture_field] = value
    fixture = canonical_bytes(changed_fixture)
    preparation = canonical_bytes(changed)
    with httpx.Client(base_url="http://127.0.0.1:9200", timeout=30,
                      trust_env=False, follow_redirects=False,
                      transport=httpx.MockTransport(fake.handle)) as client:
        with pytest.raises(BPrepareError, match="binding_invalid") as raised:
            prepare_b_intent_v1(
                client=client, fixture_raw=fixture, selection_raw=selection,
                asset_manifest_raw=manifest, preparation_raw=preparation,
                git_state=GitState("codex_0915", HEAD, True),
                fixture_blob_reader=lambda _head: fixture,
                source_build_blob_reader=lambda _head, path: evidence[path],
            )
    assert fake.calls == []
    assert raised.value.__context__ is None


@pytest.mark.parametrize("fault", [
    "malformed_json", "transport_error", "git_reader_error", "fixture_reader_error",
])
def test_preparation_error_chain_never_retains_response_text(fault: str) -> None:
    fake = FakeScopedEs()
    fixture, selection, preparation, manifest, evidence = fake.inputs()
    marker = "税务正文不可保存"

    def handle(request: httpx.Request) -> httpx.Response:
        fake.calls.append((request.method, request.url.path))
        if fault == "transport_error":
            raise RuntimeError(marker)
        return httpx.Response(200, content=(b'{"secret":"' + marker.encode() + b'",'))

    def read_historical(_head: str, path: str) -> bytes:
        if fault == "git_reader_error":
            raise RuntimeError(marker)
        return evidence[path]

    def read_fixture(_head: str) -> bytes:
        if fault == "fixture_reader_error":
            raise RuntimeError(marker)
        return fixture

    with httpx.Client(base_url="http://127.0.0.1:9200", timeout=30,
                      trust_env=False, follow_redirects=False,
                      transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(BPrepareError) as raised:
            prepare_b_intent_v1(
                client=client, fixture_raw=fixture, selection_raw=selection,
                asset_manifest_raw=manifest, preparation_raw=preparation,
                git_state=GitState("codex_0915", HEAD, True),
                fixture_blob_reader=read_fixture,
                source_build_blob_reader=read_historical,
            )
    assert fake.calls == ([] if fault.endswith("reader_error") else [("GET", "/source-index")])
    assert marker not in str(raised.value)
    assert raised.value.__context__ is None
    assert raised.value.__cause__ is None
