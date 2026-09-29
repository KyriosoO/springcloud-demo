from __future__ import annotations

import copy
import hashlib
import json
import struct
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from knowledge_corpus_tools.chunking_v2 import ChunkingResultV2, chunk_document_v2, chunk_id, unit_id
from knowledge_corpus_tools.models import ParsedDocument
from knowledge_corpus_tools.normalization_v2 import (
    MetadataV2, RelationV2, SourceAssertionV2, TemporalV2, build_document_v2,
    parsed_source_v2, v2_json_bytes,
)
from knowledge_corpus_tools.rechunk_candidate_v1 import (
    AssetChangeV1, AssetPayloadV1, CandidateSpec, PreparedVectorsV1,
    RepresentationScopeV1, new_build_owner_alias,
    RechunkCandidateError, _Build, build_rechunk_candidate_v1,
)
from knowledge_corpus_tools.retrieval_representation_v2 import build_retrieval_representation_v2
from knowledge_corpus_tools.vector_candidate import canonical_bytes, mapping_fingerprint
from knowledge_corpus_tools.vector_representation import build_vector_representation

SOURCE = "agent-doc-tax-policy-v5-20260907-vector-b1"
ONLINE_OLD = "agent-doc-tax-policy-v4-20260901-vector-a1"
TARGET = "agent-doc-tax-policy-v6-20260929-structure-a1"
REP_TARGET = "agent-doc-tax-policy-v6-20260929-represent-b1"
ALIAS = "agent-doc-tax-policy-v5-read"
OWNER_ALIAS = "agent-knowledge-build-owner-" + "a" * 32
TOKENIZER = "b" * 64
OLD_VECTOR = [0.125] * 1024
NEW_VECTOR = tuple([0.25] * 1024)
SECRET = "不可写入错误的原文"
STRUCTURE_FIELDS = {
    "documentVersionId": {"type": "keyword"},
    "structureUnitId": {"type": "keyword"},
    "sourceTextSha256": {"type": "keyword"},
    "sourceStart": {"type": "long"},
    "sourceEnd": {"type": "long"},
}

BASELINE_SNAPSHOT = {
    "container": {"id": "container-1", "image": "sha256:abc", "running": True,
                  "started": "2026-09-07T00:00:00Z", "path": "python",
                  "args": ["-m", "uvicorn", "embedding_server:app"],
                  "ports": {"8908/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8908"}]}},
    "model": {"revision": "a" * 40, "max_length": 1024,
              "files": {"tokenizer.json": {"sha256": TOKENIZER}},
              "service": {"sha256": "c" * 64},
              "implementation": {"sha256": "d" * 64},
              "packages": {"transformers": "4.0"},
              "cache_provenance": "single_snapshot_predates_start"},
}
CURRENT_SNAPSHOT = copy.deepcopy(BASELINE_SNAPSHOT)
CURRENT_SNAPSHOT["container"]["started"] = "2026-09-28T00:00:00Z"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


OLD_MODEL = sha(canonical_bytes(BASELINE_SNAPSHOT))
CURRENT_MODEL = sha(canonical_bytes(CURRENT_SNAPSHOT))


def fingerprint(documents: dict[str, dict[str, Any]]) -> str:
    digests = []
    for identifier, document in sorted(documents.items(), key=lambda item: item[1]["chunkId"]):
        fields = {key: value for key, value in document.items() if key != "embedding"}
        digest = sha(canonical_bytes([identifier, fields])
                     + struct.pack("<1024f", *document["embedding"]))
        digests.append(digest + "\n")
    return sha("".join(digests).encode())


def old_document(chunk_id: str, *, channel: str = "财税文件") -> dict[str, Any]:
    content = "第一条 旧资料内容。"
    representation = build_vector_representation(
        content=content, title="测试标题", section="第一条")
    return {
        "documentId": "parent-1@asset-1", "documentVersion": "old-version",
        "chunkId": chunk_id,
        "title": "测试标题", "content": content, "section": "第一条",
        "snippet": content, "contentHash": sha(content.encode()),
        "chunkIndex": 0, "chunkCount": 1, "charStart": 0, "charEnd": len(content),
        "chunkStrategy": "knowledge-structure-chunker-v1",
        "chunkVersion": "knowledge-structure-chunker-v1",
        "indexVersion": SOURCE, "indexedAt": "2026-09-07T00:00:00+00:00",
        "parserVersion": "old-parser", "sectionPath": ["第一条"],
        "clauseId": "第一条", "tableId": None,
        "assetId": "asset-1", "assetVersion": "replace-me",
        "assetSha256": "replace-me", "assetKind": "attachment",
        "parentDocumentId": "parent-1", "relationType": "attachment_chunk",
        "aclRef": "public", "aclVersion": "v1", "visibility": "public",
        "channel": channel, "tenantId": "public", "corpusId": "public",
        "domain": "tax.policy", "materialType": "policy",
        "sourceUrl": "https://www.chinatax.gov.cn/example.html",
        "sourceFinalUrl": "https://www.chinatax.gov.cn/example.html",
        "documentNo": "", "writtenDate": None,
        "vectorRepresentationVersion": representation.version,
        "vectorInputSha256": representation.input_sha256,
        "vectorBodySha256": representation.content_sha256,
        "vectorModelSnapshotSha256": OLD_MODEL,
        "embedding": list(OLD_VECTOR),
    }


class FakeES:
    def __init__(self, asset_sha: str, target: str = TARGET) -> None:
        self.target_name = target
        changed = old_document("old-1")
        changed["assetVersion"] = asset_sha
        changed["assetSha256"] = asset_sha
        self.source = {
            "old-1": changed,
            "law-1": {**old_document("law-1", channel="法律"), "assetKind": "baseline",
                      "assetId": "law-asset", "assetVersion": "c" * 64,
                      "assetSha256": "c" * 64, "parentDocumentId": "law-doc",
                      "documentId": "law-doc", "domain": "tax.law"},
            "unclassified-1": {**old_document("unclassified-1", channel="其他文件"),
                               "assetKind": "baseline", "assetId": "other-asset",
                               "assetVersion": "d" * 64, "assetSha256": "d" * 64,
                               "parentDocumentId": "other-doc", "documentId": "other-doc"},
        }
        properties = {key: {"type": "keyword"} for key in changed if key != "embedding"}
        properties["embedding"] = {"type": "dense_vector", "dims": 1024}
        self.mapping = {"_meta": {"mapping_version": "old-mapping"}, "properties": properties}
        self.source_def = {
            "settings": {"index": {"uuid": "source-uuid", "blocks": {"write": "true"},
                                   "number_of_replicas": "0", "number_of_shards": "1"}},
            "aliases": {ALIAS: {}}, "mappings": self.mapping,
        }
        self.alias_snapshot = {SOURCE: {"aliases": {ALIAS: {}}}}
        self.online_name = SOURCE
        self.online_def = self.source_def
        self.owner_alias = OWNER_ALIAS
        self.candidate: dict[str, dict[str, Any]] | None = None
        self.candidate_def: dict[str, Any] | None = None
        self.calls: list[tuple[str, str]] = []
        self.fault: str | None = None
        self.seq_no = 5

    def spec(self, workspace: Path, *, mode: str, change: AssetChangeV1 | None = None,
             representation_binding: str | None = None,
             representation_scope: tuple[RepresentationScopeV1, ...] | None = None) -> CandidateSpec:
        additions = STRUCTURE_FIELDS if mode == "rechunk" else {}
        mapping = copy.deepcopy(self.mapping)
        mapping["_meta"]["mapping_version"] = "candidate-mapping-v1"
        mapping["properties"].update(additions)
        writes = 2 if mode == "rechunk" else 1
        bulk = 2 if mode == "rechunk" else 1
        http_upper = 42 + 3 + 1 + 3 * bulk
        scope = representation_scope
        if scope is None and mode == "representation":
            record = self.source["old-1"]
            scope = (RepresentationScopeV1(
                "old-1", record["documentId"], record["parentDocumentId"],
                record["assetId"], record["assetVersion"]),)
        return CandidateSpec(
            mode=mode, source_index=SOURCE, source_uuid="source-uuid",
            source_mapping_sha256=mapping_fingerprint(self.mapping),
            source_fingerprint=fingerprint(self.source), source_count=len(self.source),
            workspace=workspace, read_alias=ALIAS, owner_alias=self.owner_alias,
            online_index=self.online_name,
            online_uuid=self.online_def["settings"]["index"]["uuid"],
            online_mapping_sha256=mapping_fingerprint(self.online_def["mappings"]),
            alias_snapshot_sha256=sha(canonical_bytes(self.alias_snapshot)),
            candidate_index=self.target_name,
            target_mapping_version="candidate-mapping-v1",
            target_mapping_sha256=mapping_fingerprint(mapping),
            baseline_model_snapshot_sha256=OLD_MODEL, model_snapshot_sha256=CURRENT_MODEL,
            baseline_model_snapshot=canonical_bytes(BASELINE_SNAPSHOT),
            model_snapshot=canonical_bytes(CURRENT_SNAPSHOT),
            tokenizer_sha256=TOKENIZER,
            baseline_representation_version="policy-title-section-body-v1",
            representation_version=("policy-title-section-body-v1" if mode == "rechunk"
                                    else "body-only-v2"),
            indexed_at="2026-09-29T00:00:00+00:00",
            max_http_requests=http_upper, max_embedding_requests=1,
            max_write_ops=writes,
            changes=(change,) if change else (),
            update_ids=("old-1",) if mode == "representation" else (),
            representation_scope=scope or (),
            representation_binding_sha256=representation_binding,
        )

    def client(self) -> httpx.Client:
        return httpx.Client(base_url="http://127.0.0.1:9200", timeout=30,
                            trust_env=False, transport=httpx.MockTransport(self.handle))

    def handle(self, request: httpx.Request) -> httpx.Response:
        method, path = request.method, request.url.path
        self.calls.append((method, path))
        if method == "GET" and path == f"/{SOURCE}":
            return httpx.Response(200, json={SOURCE: self.source_def})
        if method == "GET" and path == f"/{self.online_name}":
            return httpx.Response(200, json={self.online_name: self.online_def})
        if method == "GET" and path == f"/_alias/{ALIAS}":
            return httpx.Response(200, json=self.alias_snapshot)
        if method == "GET" and path == f"/_alias/{self.owner_alias}":
            if self.fault == "owner_existing" and self.candidate_def is None:
                return httpx.Response(200, json={SOURCE: {"aliases": {
                    self.owner_alias: {"is_hidden": True, "is_write_index": False}}}})
            aliases = (self.candidate_def or {}).get("aliases", {})
            if self.owner_alias not in aliases:
                return httpx.Response(404)
            result = {self.target_name: {"aliases": {
                self.owner_alias: aliases[self.owner_alias]}}}
            if self.fault == "owner_multi_target":
                result[SOURCE] = {"aliases": {
                    self.owner_alias: aliases[self.owner_alias]}}
            return httpx.Response(200, json=result)
        if method == "HEAD" and path == f"/{self.target_name}":
            return httpx.Response(404 if self.candidate is None else 200)
        if method == "GET" and path.startswith("/_cluster/health/"):
            return httpx.Response(200, json={"status": "green", "timed_out": False})
        if method == "GET" and path == f"/{self.target_name}":
            assert self.candidate_def is not None
            return httpx.Response(200, json={self.target_name: self.candidate_def})
        if method == "POST" and path == f"/{SOURCE}/_clone/{self.target_name}":
            body = json.loads(request.content)
            assert body["aliases"] == {self.owner_alias: {
                "is_hidden": True, "is_write_index": False}}
            self.candidate = copy.deepcopy(self.source)
            self.candidate_def = copy.deepcopy(self.source_def)
            self.candidate_def["aliases"] = copy.deepcopy(body["aliases"])
            self.candidate_def["settings"]["index"]["uuid"] = "candidate-uuid"
            if self.fault == "ack_wrong_uuid":
                self.candidate_def["settings"]["index"]["uuid"] = "source-uuid"
            self.candidate_def["settings"]["index"]["resize"] = {
                "source": {"name": SOURCE, "uuid": "source-uuid"}}
            if self.fault == "unknown_clone_owner":
                self.candidate_def["settings"]["index"].pop("resize")
                self.candidate_def["aliases"] = {}
                raise httpx.ReadTimeout(SECRET)
            if self.fault == "ambiguous_clone":
                self.candidate_def["settings"]["index"].pop("resize")
                raise httpx.ReadTimeout(SECRET)
            if self.fault == "owner_missing_after_clone":
                self.candidate_def["aliases"] = {}
            if self.fault == "owner_flags_drift":
                self.candidate_def["aliases"][self.owner_alias]["is_hidden"] = False
            if self.fault == "owner_extra_alias":
                self.candidate_def["aliases"]["unrelated-alias"] = {}
            if self.fault == "clone_ack_missing":
                return httpx.Response(200, json={"acknowledged": True,
                                                 "shards_acknowledged": True})
            self.candidate_def["settings"]["index"].pop("resize")
            return httpx.Response(200, json={"acknowledged": True,
                                             "shards_acknowledged": True,
                                             "index": self.target_name})
        if method == "POST" and path.endswith("/_search"):
            selected = self.candidate if path == f"/{self.target_name}/_search" else self.source
            assert selected is not None
            if (self.fault == "owner_uuid_replaced_mid"
                    and path == f"/{self.target_name}/_search"):
                assert self.candidate_def is not None
                self.candidate_def["settings"]["index"]["uuid"] = "replacement-uuid"
            body = json.loads(request.content)
            after = body.get("search_after", [""])[0]
            entries = [{"_index": self.target_name if selected is self.candidate else SOURCE,
                        "_id": identifier, "_source": item,
                        "sort": [item["chunkId"]], "_seq_no": self.seq_no,
                        "_primary_term": 1}
                       for identifier, item in sorted(selected.items(), key=lambda pair: pair[1]["chunkId"])
                       if item["chunkId"] > after][:body["size"]]
            return httpx.Response(200, json={"timed_out": False,
                                             "_shards": {"failed": 0, "total": 1, "successful": 1},
                                             "hits": {"total": {"value": len(selected), "relation": "eq"},
                                                      "hits": entries}})
        if method == "PUT" and path == f"/{self.target_name}/_settings":
            assert self.candidate_def is not None
            value = json.loads(request.content)["index.blocks.write"]
            if value is True and self.fault == "partial_bulk_seal_failure":
                return httpx.Response(503, text=SECRET)
            self.candidate_def["settings"]["index"]["blocks"]["write"] = value
            if value is False and self.fault == "owner_drift_after_unblock":
                self.candidate_def["aliases"] = {}
            return httpx.Response(200, json={"acknowledged": True})
        if method == "POST" and path == "/_aliases":
            assert self.candidate_def is not None
            body = json.loads(request.content)
            assert body == {"actions": [{"remove": {
                "index": self.target_name, "alias": self.owner_alias}}]}
            if self.fault == "owner_remove_rejected":
                return httpx.Response(200, json={"acknowledged": True, "errors": True})
            if self.fault == "owner_remove_noop":
                return httpx.Response(200, json={"acknowledged": True, "errors": False})
            del self.candidate_def["aliases"][self.owner_alias]
            return httpx.Response(200, json={"acknowledged": True, "errors": False})
        if method == "PUT" and path == f"/{self.target_name}/_mapping":
            assert self.candidate_def is not None
            body = json.loads(request.content)
            self.candidate_def["mappings"]["_meta"] = body["_meta"]
            self.candidate_def["mappings"]["properties"].update(body["properties"])
            return httpx.Response(200, json={"acknowledged": True})
        if method == "POST" and path == f"/{self.target_name}/_bulk":
            assert self.candidate is not None
            if self.fault == "cancel_bulk":
                raise KeyboardInterrupt()
            if self.fault in {"partial_bulk", "partial_bulk_seal_failure"}:
                return httpx.Response(200, json={"errors": True, "items": [
                    {"delete": {"status": 409, "error": {"reason": SECRET}}}]})
            lines = [json.loads(line) for line in request.content.splitlines()]
            items = []
            offset = 0
            while offset < len(lines):
                header = lines[offset]
                action = next(iter(header))
                info = header[action]
                identifier = info["_id"]
                if action != "create":
                    assert info["if_seq_no"] == self.seq_no and info["if_primary_term"] == 1
                if action == "delete":
                    del self.candidate[identifier]
                    status, result = 200, "deleted"
                    offset += 1
                elif action == "create":
                    assert identifier not in self.candidate
                    self.candidate[identifier] = lines[offset + 1]
                    status, result = 201, "created"
                    offset += 2
                else:
                    self.candidate[identifier].update(lines[offset + 1]["doc"])
                    status, result = 200, "updated"
                    offset += 2
                items.append({action: {"status": status, "result": result,
                                       "_index": self.target_name, "_id": identifier}})
            return httpx.Response(200, json={"errors": False, "items": items})
        if method == "POST" and path == f"/{self.target_name}/_refresh":
            return httpx.Response(200, json={"_shards": {"failed": 0}})
        raise AssertionError((method, path))


def inputs(
    tmp_path: Path, *, blocks: list[dict[str, Any]] | None = None,
) -> tuple[FakeES, AssetChangeV1, AssetPayloadV1]:
    asset = tmp_path / "raw" / "asset-1.bin"
    asset.parent.mkdir()
    asset.write_bytes(b"fixture immutable asset")
    asset_hash = sha(asset.read_bytes())
    parsed = ParsedDocument.model_validate_json(json.dumps({
        "schema_version": 1, "asset_id": "asset-1", "asset_sha256": asset_hash,
        "parser_name": "fixture-parser", "parser_version": "fixture-parser-v2",
        "ocr_status": "not_applied", "quality_status": "accepted",
        "blocks": blocks or [{"ordinal": 1, "kind": "clause", "text": "第一条 新资料内容。",
                              "clause_id": "第一条"}],
    }, ensure_ascii=False))
    source = parsed_source_v2(parsed, order_proof_ref="fixture:order",
                              structure_proof_ref="fixture:structure")
    assertion = SourceAssertionV2.model_validate_json(json.dumps({
        "kind": "official", "sourceSnapshot": "fixture-v1",
        "finalUrl": "https://www.chinatax.gov.cn/example.html",
        "officialPublisher": "国家税务总局", "officialProofRef": "fixture:official",
        "rawHashScope": "asset_bytes", "rawSha256": asset_hash,
        "assetId": "asset-1", "assetVersion": asset_hash,
    }, ensure_ascii=False))
    document = build_document_v2(
        document_id="parent-1@asset-1", source=assertion, metadata=MetadataV2(),
        temporal=TemporalV2.model_validate({"snapshotAt": datetime(2026, 9, 29, tzinfo=UTC)}),
        relations=RelationV2.model_validate({
            "parentDocumentId": "parent-1", "relationType": "attachment",
            "parentSourceRef": "fixture:parent",
        }), parsed_source=source, parsed_source_ref="parsed/source.json",
    )
    chunking = chunk_document_v2(document, parsed, source)
    assert chunking.publishable and chunking.chunks
    sidecar_ref = "manifests/corpus-document-v2/sidecar.json"
    chunks_ref = "manifests/chunks-v2/chunks.json"
    for ref, data in ((sidecar_ref, v2_json_bytes(document)),
                      ("parsed/source.json", v2_json_bytes(source)),
                      (chunks_ref, canonical_bytes(chunking.model_dump(mode="json", by_alias=True)))):
        target = tmp_path / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    change = AssetChangeV1(
        document_id="parent-1@asset-1", parent_document_id="parent-1",
        document_version_id=document.document_version_id,
        asset_id="asset-1", asset_version=asset_hash, old_ids=("old-1",),
        asset_ref="raw/asset-1.bin", sidecar_ref=sidecar_ref,
        sidecar_sha256=document.normalized_sha256,
        parsed_source_ref="parsed/source.json",
        parsed_source_sha256=sha(v2_json_bytes(source)),
        chunks_ref=chunks_ref,
        chunks_sha256=sha(canonical_bytes(chunking.model_dump(mode="json", by_alias=True))),
    )
    return FakeES(asset_hash), change, AssetPayloadV1(document, source, chunking)


def with_frozen_chunking(
    tmp_path: Path, change: AssetChangeV1, payload: AssetPayloadV1,
    chunking: ChunkingResultV2,
) -> tuple[AssetChangeV1, AssetPayloadV1]:
    raw = canonical_bytes(chunking.model_dump(mode="json", by_alias=True))
    (tmp_path / change.chunks_ref).write_bytes(raw)
    return replace(change, chunks_sha256=sha(raw)), replace(payload, chunking=chunking)


def prepared(representations: tuple[Any, ...]) -> PreparedVectorsV1:
    return PreparedVectorsV1(
        vectors=tuple(NEW_VECTOR for _ in representations),
        input_sha256=tuple(item.input_sha256 for item in representations),
        body_sha256=tuple(item.content_sha256 if hasattr(item, "content_sha256")
                          else item.body_sha256 for item in representations),
        representation_versions=tuple(item.version for item in representations),
        token_counts=tuple(20 for _ in representations), max_input_tokens=1024,
        model_snapshot_sha256=CURRENT_MODEL, tokenizer_sha256=TOKENIZER,
        embedding_requests=1,
    )


def test_rechunk_clone_delete_create_preserves_full_competition_pool(tmp_path: Path) -> None:
    es, change, payload = inputs(tmp_path)
    original = copy.deepcopy(es.source)
    received = []
    def prepare(values: tuple[Any, ...]) -> PreparedVectorsV1:
        received.extend(values)
        assert es.candidate is None
        return prepared(values)
    spec = es.spec(tmp_path, mode="rechunk", change=change)
    with es.client() as client:
        result = build_rechunk_candidate_v1(spec, client=client,
                                            prepare_vectors=prepare, payloads=(payload,))
    assert result.deleted_count == result.created_count == 1
    assert result.candidate_count == 3 and result.http_requests == spec.max_http_requests - 3
    assert result.embedding_requests == spec.max_embedding_requests == 1
    assert result.source_counts["law"] == result.candidate_counts["law"] == 1
    assert result.source_counts["classification_missing"] == result.candidate_counts["classification_missing"] == 3
    assert es.source == original
    assert es.candidate is not None and es.candidate_def is not None
    assert "old-1" not in es.candidate
    new = es.candidate[payload.chunking.chunks[0].chunk_id]
    assert new["content"] == payload.chunking.chunks[0].content
    assert new["sourceStart"] == 0 and new["sourceEnd"] == len(new["content"])
    assert new["charStart"] == 0 and new["charEnd"] == len(new["content"])
    assert new["vectorBodySha256"] == sha(new["content"].encode())
    assert new["vectorModelSnapshotSha256"] == CURRENT_MODEL
    assert original["old-1"]["vectorModelSnapshotSha256"] == OLD_MODEL
    assert result.baseline_container_started != result.current_container_started
    assert es.candidate["law-1"] == original["law-1"]
    assert es.candidate["unclassified-1"] == original["unclassified-1"]
    assert es.candidate_def["settings"]["index"]["blocks"]["write"] is True
    assert es.candidate_def["aliases"] == {}
    assert sum(path == "/_aliases" for _, path in es.calls) == 1
    assert es.calls[-1] == ("GET", f"/_alias/{OWNER_ALIAS}")
    assert len(received) == 1 and received[0].version == "policy-title-section-body-v1"


def test_owner_alias_is_random_shaped_and_preexisting_name_rejected(tmp_path: Path) -> None:
    first = new_build_owner_alias()
    second = new_build_owner_alias()
    assert first.startswith("agent-knowledge-build-owner-")
    assert len(first) == len(second) == len("agent-knowledge-build-owner-") + 32
    assert first != second
    es, change, payload = inputs(tmp_path)
    with pytest.raises(RechunkCandidateError, match="spec_invalid"):
        replace(es.spec(tmp_path, mode="rechunk", change=change),
                owner_alias="agent-knowledge-build-owner-" + "G" * 32)
    es.fault = "owner_existing"
    spec = es.spec(tmp_path, mode="rechunk", change=change)
    with es.client() as client, pytest.raises(RechunkCandidateError) as error:
        build_rechunk_candidate_v1(spec, client=client, prepare_vectors=prepared,
                                   payloads=(payload,))
    assert error.value.reason == "owner_alias_exists"
    assert es.candidate is None
    assert not any(method == "PUT" or path.endswith("/_clone") for method, path in es.calls)


def test_representation_candidate_updates_only_frozen_vector(tmp_path: Path) -> None:
    es, _, _ = inputs(tmp_path)
    es.target_name = REP_TARGET
    original = copy.deepcopy(es.source)
    body = es.source["old-1"]["content"]
    representation = build_retrieval_representation_v2(body=body, kind="body-only-v2")
    binding = sha(canonical_bytes([["old-1", representation.version,
                                   representation.input_sha256, representation.body_sha256]]))
    spec = es.spec(tmp_path, mode="representation", representation_binding=binding)
    received = []
    def prepare(values: tuple[Any, ...]) -> PreparedVectorsV1:
        received.extend(values)
        assert es.candidate is None
        return prepared(values)
    with es.client() as client:
        result = build_rechunk_candidate_v1(
            spec, client=client, prepare_vectors=prepare)
    assert result.updated_count == 1 and result.deleted_count == result.created_count == 0
    assert result.http_requests == spec.max_http_requests - 3
    assert received == [representation]
    assert es.candidate is not None
    assert es.candidate["old-1"]["content"] == original["old-1"]["content"]
    assert es.candidate["old-1"]["vectorRepresentationVersion"] == "body-only-v2"
    assert es.candidate["law-1"] == original["law-1"]
    assert es.candidate["unclassified-1"] == original["unclassified-1"]


@pytest.mark.parametrize("invalid", ["binding", "external_body", "external_hash"])
def test_b_rejects_unbound_or_untrusted_representation_before_clone(
    tmp_path: Path, invalid: str,
) -> None:
    es, _, _ = inputs(tmp_path)
    es.target_name = REP_TARGET
    body = es.source["old-1"]["content"]
    representation = build_retrieval_representation_v2(body=body, kind="body-only-v2")
    binding = sha(canonical_bytes([["old-1", representation.version,
                                    representation.input_sha256, representation.body_sha256]]))
    spec = es.spec(tmp_path, mode="representation", representation_binding=binding)
    supplied = ()
    if invalid == "binding":
        spec = replace(spec, representation_binding_sha256="f" * 64)
    elif invalid == "external_body":
        supplied = (build_retrieval_representation_v2(
            body="外部传入的非源正文", kind="body-only-v2"),)
    else:
        supplied = (replace(representation, body_sha256="f" * 64),)
    with es.client() as client, pytest.raises(RechunkCandidateError) as error:
        build_rechunk_candidate_v1(
            spec, client=client, prepare_vectors=lambda _: pytest.fail("must not prepare"),
            representations=supplied,
        )
    assert error.value.reason == "input_invalid"
    assert es.candidate is None
    assert not any(path.endswith("/_clone") for _, path in es.calls)


def test_b_rejects_frozen_update_order_drift_before_clone(tmp_path: Path) -> None:
    es, _, _ = inputs(tmp_path)
    es.target_name = REP_TARGET
    second = copy.deepcopy(es.source["old-1"])
    second["chunkId"] = "old-2"
    second["content"] = "第二条 旧资料内容。"
    second["contentHash"] = sha(second["content"].encode())
    old_representation = build_vector_representation(
        content=second["content"], title=second["title"], section=second["section"])
    second["vectorInputSha256"] = old_representation.input_sha256
    second["vectorBodySha256"] = old_representation.content_sha256
    es.source["old-2"] = second
    order = ("old-1", "old-2")
    scopes = tuple(RepresentationScopeV1(
        identifier, es.source[identifier]["documentId"],
        es.source[identifier]["parentDocumentId"],
        es.source[identifier]["assetId"], es.source[identifier]["assetVersion"],
    ) for identifier in order)
    representations = tuple(build_retrieval_representation_v2(
        body=es.source[identifier]["content"], kind="body-only-v2",
    ) for identifier in order)
    binding = sha(canonical_bytes([
        [identifier, representation.version, representation.input_sha256,
         representation.body_sha256]
        for identifier, representation in zip(order, representations, strict=True)
    ]))
    base = es.spec(tmp_path, mode="representation", representation_binding=binding)
    spec = replace(base, source_count=len(es.source), source_fingerprint=fingerprint(es.source),
                   max_write_ops=2, update_ids=order[::-1], representation_scope=scopes[::-1])
    with es.client() as client, pytest.raises(RechunkCandidateError) as error:
        build_rechunk_candidate_v1(
            spec, client=client, prepare_vectors=lambda _: pytest.fail("must not prepare"))
    assert error.value.reason == "input_invalid"
    assert es.candidate is None
    assert not any(path.endswith("/_clone") for _, path in es.calls)


def test_b_rejects_body_change_even_when_source_snapshot_is_rebound(tmp_path: Path) -> None:
    es, _, _ = inputs(tmp_path)
    es.target_name = REP_TARGET
    original = build_retrieval_representation_v2(
        body=es.source["old-1"]["content"], kind="body-only-v2")
    binding = sha(canonical_bytes([["old-1", original.version,
                                    original.input_sha256, original.body_sha256]]))
    record = es.source["old-1"]
    record["content"] = "第一条 已改变的来源正文。"
    record["contentHash"] = sha(record["content"].encode())
    baseline = build_vector_representation(
        content=record["content"], title=record["title"], section=record["section"])
    record["vectorInputSha256"] = baseline.input_sha256
    record["vectorBodySha256"] = baseline.content_sha256
    spec = replace(es.spec(tmp_path, mode="representation", representation_binding=binding),
                   source_fingerprint=fingerprint(es.source))
    with es.client() as client, pytest.raises(RechunkCandidateError) as error:
        build_rechunk_candidate_v1(
            spec, client=client, prepare_vectors=lambda _: pytest.fail("must not prepare"))
    assert error.value.reason == "input_invalid"
    assert es.candidate is None
    assert not any(path.endswith("/_clone") for _, path in es.calls)


def test_b_clones_offline_a_source_without_switching_online_alias(tmp_path: Path) -> None:
    es, _, _ = inputs(tmp_path)
    es.target_name = REP_TARGET
    es.online_name = ONLINE_OLD
    es.online_def = copy.deepcopy(es.source_def)
    es.online_def["settings"]["index"]["uuid"] = "online-old-uuid"
    es.source_def["aliases"] = {}
    es.alias_snapshot = {ONLINE_OLD: {"aliases": {ALIAS: {}}}}
    representation = build_retrieval_representation_v2(
        body=es.source["old-1"]["content"], kind="body-only-v2")
    binding = sha(canonical_bytes([["old-1", representation.version,
                                    representation.input_sha256, representation.body_sha256]]))
    spec = es.spec(tmp_path, mode="representation", representation_binding=binding)
    with es.client() as client:
        result = build_rechunk_candidate_v1(
            spec, client=client, prepare_vectors=prepared,
            representations=(representation,))
    assert result.updated_count == 1
    assert result.http_requests == spec.max_http_requests - 3
    assert es.alias_snapshot == {ONLINE_OLD: {"aliases": {ALIAS: {}}}}
    assert ("POST", f"/{SOURCE}/_clone/{REP_TARGET}") in es.calls
    assert ("GET", f"/{ONLINE_OLD}") in es.calls
    assert es.candidate_def is not None and es.candidate_def["aliases"] == {}
    assert sum(path == "/_aliases" for _, path in es.calls) == 1


def test_b_rejects_online_target_drift_before_clone(tmp_path: Path) -> None:
    es, _, _ = inputs(tmp_path)
    es.target_name = REP_TARGET
    es.online_name = ONLINE_OLD
    es.online_def = copy.deepcopy(es.source_def)
    es.online_def["settings"]["index"]["uuid"] = "online-old-uuid"
    es.source_def["aliases"] = {}
    es.alias_snapshot = {ONLINE_OLD: {"aliases": {ALIAS: {}}}}
    representation = build_retrieval_representation_v2(
        body=es.source["old-1"]["content"], kind="body-only-v2")
    binding = sha(canonical_bytes([["old-1", representation.version,
                                    representation.input_sha256, representation.body_sha256]]))
    spec = es.spec(tmp_path, mode="representation", representation_binding=binding)
    es.online_def["settings"]["index"]["uuid"] = "drifted-online-uuid"
    with es.client() as client, pytest.raises(RechunkCandidateError) as error:
        build_rechunk_candidate_v1(spec, client=client, prepare_vectors=prepared,
                                   representations=(representation,))
    assert error.value.reason == "alias_changed"
    assert es.candidate is None


def test_b_scope_rejects_thirty_one_parents_and_record_identity_drift(tmp_path: Path) -> None:
    es, _, _ = inputs(tmp_path)
    es.target_name = REP_TARGET
    representation = build_retrieval_representation_v2(
        body=es.source["old-1"]["content"], kind="body-only-v2")
    binding = sha(canonical_bytes([["old-1", representation.version,
                                    representation.input_sha256, representation.body_sha256]]))
    base = es.spec(tmp_path, mode="representation", representation_binding=binding)
    scopes = tuple(RepresentationScopeV1(f"id-{index}", f"doc-{index}",
                                         f"parent-{index}", f"asset-{index}", "a" * 64)
                   for index in range(31))
    with pytest.raises(RechunkCandidateError, match="spec_invalid"):
        replace(base, update_ids=tuple(scope.identifier for scope in scopes),
                representation_scope=scopes)
    wrong_scope = replace(base.representation_scope[0], parent_document_id="wrong-parent")
    spec = replace(base, representation_scope=(wrong_scope,))
    with es.client() as client, pytest.raises(RechunkCandidateError) as error:
        build_rechunk_candidate_v1(spec, client=client, prepare_vectors=prepared,
                                   representations=(representation,))
    assert error.value.reason == "input_invalid"
    assert es.candidate is None


def test_asset_or_span_change_stops_before_clone(tmp_path: Path) -> None:
    es, change, payload = inputs(tmp_path)
    (tmp_path / change.asset_ref).write_bytes(b"changed")
    spec = es.spec(tmp_path, mode="rechunk", change=change)
    with es.client() as client, pytest.raises(RechunkCandidateError, match="input_invalid"):
        build_rechunk_candidate_v1(spec, client=client, prepare_vectors=prepared,
                                   payloads=(payload,))
    assert es.candidate is None
    assert all(method in ("GET", "HEAD") or path.endswith("/_search")
               for method, path in es.calls)


def test_missing_frozen_asset_has_finite_preclone_failure(tmp_path: Path) -> None:
    es, change, payload = inputs(tmp_path)
    (tmp_path / change.asset_ref).unlink()
    spec = es.spec(tmp_path, mode="rechunk", change=change)
    with es.client() as client, pytest.raises(RechunkCandidateError) as error:
        build_rechunk_candidate_v1(spec, client=client, prepare_vectors=prepared,
                                   payloads=(payload,))
    assert error.value.reason == "input_invalid"
    assert error.value.seal_status == "not_needed"
    assert es.candidate is None


def test_missing_record_provenance_stops_without_candidate_write(tmp_path: Path) -> None:
    es, change, payload = inputs(tmp_path)
    del es.source["old-1"]["vectorInputSha256"]
    spec = es.spec(tmp_path, mode="rechunk", change=change)
    with es.client() as client, pytest.raises(RechunkCandidateError, match="provenance_invalid"):
        build_rechunk_candidate_v1(spec, client=client, prepare_vectors=prepared,
                                   payloads=(payload,))
    assert es.candidate is None


def test_ambiguous_clone_seals_only_when_owner_alias_proves_target(tmp_path: Path) -> None:
    es, change, payload = inputs(tmp_path)
    es.fault = "ambiguous_clone"
    spec = es.spec(tmp_path, mode="rechunk", change=change)
    with es.client() as client, pytest.raises(RechunkCandidateError) as error:
        build_rechunk_candidate_v1(spec, client=client, prepare_vectors=prepared,
                                   payloads=(payload,))
    assert error.value.reason == "http_invalid"
    assert error.value.seal_status == "sealed"
    assert es.candidate_def is not None
    assert es.candidate_def["settings"]["index"]["blocks"]["write"] is True
    assert ("PUT", f"/{TARGET}/_settings") in es.calls
    assert not any(path.endswith("/_bulk") or path == "/_aliases" for _, path in es.calls)
    assert SECRET not in str(error.value)


@pytest.mark.parametrize("fault", [
    "owner_missing_after_clone", "owner_multi_target", "owner_flags_drift",
    "owner_extra_alias", "owner_uuid_replaced_mid",
])
def test_owner_drift_stops_before_candidate_write_and_does_not_seal_unknown(
    tmp_path: Path, fault: str,
) -> None:
    es, change, payload = inputs(tmp_path)
    es.fault = fault
    spec = es.spec(tmp_path, mode="rechunk", change=change)
    with es.client() as client, pytest.raises(RechunkCandidateError) as error:
        build_rechunk_candidate_v1(spec, client=client, prepare_vectors=prepared,
                                   payloads=(payload,))
    assert error.value.seal_status == "ownership_unknown"
    assert not any(method == "PUT" or path.endswith("/_bulk") or path == "/_aliases"
                   for method, path in es.calls)


def test_owner_drift_after_first_write_stops_further_writes(tmp_path: Path) -> None:
    es, change, payload = inputs(tmp_path)
    es.fault = "owner_drift_after_unblock"
    spec = es.spec(tmp_path, mode="rechunk", change=change)
    with es.client() as client, pytest.raises(RechunkCandidateError) as error:
        build_rechunk_candidate_v1(spec, client=client, prepare_vectors=prepared,
                                   payloads=(payload,))
    assert error.value.seal_status == "ownership_unknown"
    assert sum(method == "PUT" for method, _ in es.calls) == 1
    assert not any(path.endswith("/_bulk") or path == "/_aliases" for _, path in es.calls)


def test_unconfirmed_clone_with_owner_marker_can_be_sealed(tmp_path: Path) -> None:
    es, change, payload = inputs(tmp_path)
    es.fault = "clone_ack_missing"
    spec = es.spec(tmp_path, mode="rechunk", change=change)
    with es.client() as client, pytest.raises(RechunkCandidateError) as error:
        build_rechunk_candidate_v1(spec, client=client, prepare_vectors=prepared,
                                   payloads=(payload,))
    assert error.value.reason == "clone_unacknowledged"
    assert error.value.seal_status == "sealed"
    assert es.candidate_def is not None
    assert es.candidate_def["settings"]["index"]["blocks"]["write"] is True
    assert not any(path.endswith("/_bulk") or path == "/_aliases" for _, path in es.calls)


def test_acknowledged_clone_still_requires_new_candidate_uuid(tmp_path: Path) -> None:
    es, change, payload = inputs(tmp_path)
    es.fault = "ack_wrong_uuid"
    spec = es.spec(tmp_path, mode="rechunk", change=change)
    with es.client() as client, pytest.raises(RechunkCandidateError) as error:
        build_rechunk_candidate_v1(spec, client=client, prepare_vectors=prepared,
                                   payloads=(payload,))
    assert error.value.reason == "candidate_ownership_unknown"
    assert error.value.seal_status == "ownership_unknown"
    assert not any(method == "PUT" or path.endswith("/_bulk") for method, path in es.calls)


def test_partial_bulk_failure_seals_without_source_mutation(tmp_path: Path) -> None:
    es, change, payload = inputs(tmp_path)
    original = copy.deepcopy(es.source)
    es.fault = "partial_bulk"
    spec = es.spec(tmp_path, mode="rechunk", change=change)
    with es.client() as client, pytest.raises(RechunkCandidateError, match="bulk_failed") as error:
        build_rechunk_candidate_v1(spec, client=client, prepare_vectors=prepared,
                                   payloads=(payload,))
    assert error.value.seal_status == "sealed"
    assert es.source == original
    assert es.candidate_def is not None
    assert es.candidate_def["settings"]["index"]["blocks"]["write"] is True


@pytest.mark.parametrize("fault", ["owner_remove_rejected", "owner_remove_noop"])
def test_owner_alias_removal_failure_never_returns_built(
    tmp_path: Path, fault: str,
) -> None:
    es, change, payload = inputs(tmp_path)
    es.fault = fault
    spec = es.spec(tmp_path, mode="rechunk", change=change)
    with es.client() as client, pytest.raises(RechunkCandidateError) as error:
        build_rechunk_candidate_v1(spec, client=client, prepare_vectors=prepared,
                                   payloads=(payload,))
    assert error.value.seal_status == "sealed"
    assert es.candidate_def is not None
    assert es.candidate_def["aliases"] == {OWNER_ALIAS: {
        "is_hidden": True, "is_write_index": False}}
    assert es.candidate_def["settings"]["index"]["blocks"]["write"] is True
    assert sum(path == "/_aliases" for _, path in es.calls) == 1


def test_exact_budget_rejects_understated_writes_before_prepare(tmp_path: Path) -> None:
    es, change, payload = inputs(tmp_path)
    spec = replace(es.spec(tmp_path, mode="rechunk", change=change), max_write_ops=1)
    with es.client() as client, pytest.raises(RechunkCandidateError, match="budget_exceeded"):
        build_rechunk_candidate_v1(spec, client=client,
                                   prepare_vectors=lambda _: pytest.fail("must not prepare"),
                                   payloads=(payload,))
    assert es.candidate is None


def test_owner_checks_are_included_in_exact_http_budget(tmp_path: Path) -> None:
    es, change, payload = inputs(tmp_path)
    base = es.spec(tmp_path, mode="rechunk", change=change)
    spec = replace(base, max_http_requests=base.max_http_requests - 1)
    with es.client() as client, pytest.raises(RechunkCandidateError) as error:
        build_rechunk_candidate_v1(
            spec, client=client,
            prepare_vectors=lambda _: pytest.fail("must not prepare"), payloads=(payload,))
    assert error.value.reason == "budget_exceeded"
    assert es.candidate is None


@pytest.mark.parametrize("changed", [
    {"tokenizer_sha256": "0" * 64},
    {"model_snapshot_sha256": "0" * 64},
    {"token_counts": (1025,)},
    {"embedding_requests": 2},
])
def test_preparation_receipt_mismatch_has_zero_index_writes(
    tmp_path: Path, changed: dict[str, Any],
) -> None:
    es, change, payload = inputs(tmp_path)
    spec = es.spec(tmp_path, mode="rechunk", change=change)
    with es.client() as client, pytest.raises(RechunkCandidateError, match="preparation_invalid"):
        build_rechunk_candidate_v1(
            spec, client=client,
            prepare_vectors=lambda values: replace(prepared(values), **changed),
            payloads=(payload,),
        )
    assert es.candidate is None


def test_model_identity_allows_only_started_difference(tmp_path: Path) -> None:
    es, change, _ = inputs(tmp_path)
    spec = es.spec(tmp_path, mode="rechunk", change=change)
    assert spec.baseline_model_snapshot_sha256 != spec.model_snapshot_sha256
    changed = copy.deepcopy(CURRENT_SNAPSHOT)
    changed["model"]["files"]["tokenizer.json"]["sha256"] = "e" * 64
    raw = canonical_bytes(changed)
    with pytest.raises(RechunkCandidateError, match="spec_invalid"):
        replace(spec, model_snapshot=raw, model_snapshot_sha256=sha(raw))
    changed = copy.deepcopy(CURRENT_SNAPSHOT)
    changed["container"]["image"] = "sha256:other"
    raw = canonical_bytes(changed)
    with pytest.raises(RechunkCandidateError, match="spec_invalid"):
        replace(spec, model_snapshot=raw, model_snapshot_sha256=sha(raw))


def test_inherited_acl_conflict_rejects_without_prepare(tmp_path: Path) -> None:
    es, change, payload = inputs(tmp_path)
    second = copy.deepcopy(es.source["old-1"])
    second["chunkId"] = "old-2"
    second["aclRef"] = "different-policy"
    second["content"] = "第二条 旧资料内容。"
    second["contentHash"] = sha(second["content"].encode())
    old = build_vector_representation(content=second["content"],
                                      title=second["title"], section=second["section"])
    second["vectorInputSha256"] = old.input_sha256
    second["vectorBodySha256"] = old.content_sha256
    es.source["old-2"] = second
    spec = replace(es.spec(tmp_path, mode="rechunk", change=change),
                   changes=(replace(change, old_ids=("old-1", "old-2")),),
                   max_write_ops=3)
    with es.client() as client, pytest.raises(RechunkCandidateError, match="inheritance_conflict"):
        build_rechunk_candidate_v1(spec, client=client,
                                   prepare_vectors=lambda _: pytest.fail("must not prepare"),
                                   payloads=(payload,))
    assert es.candidate is None


def test_missing_inherited_acl_rejects_before_clone(tmp_path: Path) -> None:
    es, change, payload = inputs(tmp_path)
    del es.source["old-1"]["tenantId"]
    spec = es.spec(tmp_path, mode="rechunk", change=change)
    with es.client() as client, pytest.raises(RechunkCandidateError, match="inheritance_conflict"):
        build_rechunk_candidate_v1(spec, client=client, prepare_vectors=prepared,
                                   payloads=(payload,))
    assert es.candidate is None


def test_rechunk_typed_projection_rejects_non_nfc_title(tmp_path: Path) -> None:
    es, change, payload = inputs(tmp_path)
    record = es.source["old-1"]
    record["title"] = "e\u0301"
    old = build_vector_representation(content=record["content"],
                                      title=record["title"], section=record["section"])
    record["vectorInputSha256"] = old.input_sha256
    spec = es.spec(tmp_path, mode="rechunk", change=change)
    with es.client() as client, pytest.raises(RechunkCandidateError, match="typed_projection_invalid"):
        build_rechunk_candidate_v1(spec, client=client, prepare_vectors=prepared,
                                   payloads=(payload,))
    assert es.candidate is None


def test_b_rejects_unproven_metadata_representation(tmp_path: Path) -> None:
    es, _, _ = inputs(tmp_path)
    es.target_name = REP_TARGET
    body = es.source["old-1"]["content"]
    representation = build_retrieval_representation_v2(body=body, kind="body-only-v2")
    binding = sha(canonical_bytes([["old-1", representation.version,
                                   representation.input_sha256, representation.body_sha256]]))
    spec = es.spec(tmp_path, mode="representation", representation_binding=binding)
    with pytest.raises(RechunkCandidateError, match="spec_invalid"):
        replace(spec, representation_version="trusted-title-section-body-v2")
    with pytest.raises(RechunkCandidateError, match="spec_invalid"):
        replace(spec, representation_version="trusted-classification-body-v2")


@pytest.mark.parametrize("field,value", [
    ("content", "伪造正文"),
    ("chunk_id", "old-1"),
])
def test_rechunk_rejects_span_or_id_conflict_before_clone(
    tmp_path: Path, field: str, value: str,
) -> None:
    es, change, payload = inputs(tmp_path)
    chunk = payload.chunking.chunks[0].model_copy(update={field: value})
    tampered = payload.chunking.model_copy(update={"chunks": (chunk,)})
    raw = canonical_bytes(tampered.model_dump(mode="json", by_alias=True))
    (tmp_path / change.chunks_ref).write_bytes(raw)
    changed = replace(change, chunks_sha256=sha(raw))
    spec = es.spec(tmp_path, mode="rechunk", change=changed)
    with es.client() as client, pytest.raises(RechunkCandidateError, match="source_span_invalid"):
        build_rechunk_candidate_v1(
            spec, client=client, prepare_vectors=lambda _: pytest.fail("must not prepare"),
            payloads=(AssetPayloadV1(payload.document, payload.source, tampered),),
        )
    assert es.candidate is None


def test_claimed_publishable_but_incomplete_chunk_coverage_rejected(tmp_path: Path) -> None:
    es, change, payload = inputs(tmp_path)
    old = payload.chunking.chunks[0]
    content = old.content[:-1]
    body = sha(content.encode())
    shortened = old.model_copy(update={
        "end": old.end - 1, "content": content, "body_sha256": body,
        "chunk_id": chunk_id(document_version_id=old.document_version_id,
                             unit_id=old.unit_id, start=old.start,
                             end=old.end - 1, body_sha256=body),
    })
    tampered = payload.chunking.model_copy(update={"chunks": (shortened,)})
    raw = canonical_bytes(tampered.model_dump(mode="json", by_alias=True))
    (tmp_path / change.chunks_ref).write_bytes(raw)
    changed = replace(change, chunks_sha256=sha(raw))
    spec = es.spec(tmp_path, mode="rechunk", change=changed)
    with es.client() as client, pytest.raises(RechunkCandidateError, match="source_span_invalid"):
        build_rechunk_candidate_v1(
            spec, client=client, prepare_vectors=prepared,
            payloads=(AssetPayloadV1(payload.document, payload.source, tampered),),
        )
    assert es.candidate is None


def test_claimed_publishable_cannot_omit_an_entire_parsed_block(tmp_path: Path) -> None:
    blocks = [
        {"ordinal": 1, "kind": "clause", "text": "第一条 新资料内容。", "clause_id": "第一条"},
        {"ordinal": 2, "kind": "clause", "text": "第二条 后续资料内容。", "clause_id": "第二条"},
    ]
    es, change, payload = inputs(tmp_path, blocks=blocks)
    original = payload.chunking
    assert len(payload.source.blocks) == len(original.units) == len(original.chunks) == 2
    tampered = original.model_copy(update={
        "units": original.units[:1], "chunks": original.chunks[:1],
        "unit_coverage": original.unit_coverage[:1], "publishable": True,
    })
    changed, forged_payload = with_frozen_chunking(tmp_path, change, payload, tampered)
    spec = es.spec(tmp_path, mode="rechunk", change=changed)
    with es.client() as client, pytest.raises(RechunkCandidateError) as error:
        build_rechunk_candidate_v1(
            spec, client=client, prepare_vectors=lambda _: pytest.fail("must not prepare"),
            payloads=(forged_payload,))
    assert error.value.reason == "source_span_invalid"
    assert es.candidate is None


def test_partial_cross_block_chunk_cannot_cover_second_block_boundary(tmp_path: Path) -> None:
    blocks = [
        {"ordinal": 1, "kind": "clause", "text": "第一条 新资料内容。", "clause_id": "第一条"},
        {"ordinal": 2, "kind": "clause", "text": "第二条 后续资料内容。", "clause_id": "第二条"},
    ]
    es, change, payload = inputs(tmp_path, blocks=blocks)
    source = payload.source
    end = source.blocks[1].start + 1
    original_unit = payload.chunking.units[0]
    new_unit_id = unit_id(
        document_version_id=original_unit.document_version_id,
        source_text_sha256=original_unit.source_text_sha256,
        parser_version=original_unit.parser_version,
        unit_type=original_unit.unit_type, start=original_unit.start, end=end)
    extended = source.text[original_unit.start:end]
    unit = original_unit.model_copy(update={
        "unit_id": new_unit_id, "end": end, "body_sha256": sha(extended.encode()),
    })
    original_chunk = payload.chunking.chunks[0]
    chunk = original_chunk.model_copy(update={
        "unit_id": new_unit_id, "end": end, "content": extended,
        "body_sha256": sha(extended.encode()),
        "chunk_id": chunk_id(
            document_version_id=original_chunk.document_version_id,
            unit_id=new_unit_id, start=original_chunk.start, end=end,
            body_sha256=sha(extended.encode())),
    })
    coverage = payload.chunking.unit_coverage[0].model_copy(update={"unit_id": new_unit_id})
    tampered = payload.chunking.model_copy(update={
        "units": (unit,), "chunks": (chunk,), "unit_coverage": (coverage,),
        "publishable": True,
    })
    changed, forged_payload = with_frozen_chunking(tmp_path, change, payload, tampered)
    spec = es.spec(tmp_path, mode="rechunk", change=changed)
    with es.client() as client, pytest.raises(RechunkCandidateError) as error:
        build_rechunk_candidate_v1(
            spec, client=client, prepare_vectors=lambda _: pytest.fail("must not prepare"),
            payloads=(forged_payload,))
    assert error.value.reason == "source_span_invalid"
    assert es.candidate is None


def test_duplicate_chunk_spans_cannot_count_as_block_coverage(tmp_path: Path) -> None:
    es, change, payload = inputs(tmp_path)
    original_unit = payload.chunking.units[0]
    duplicate_unit_id = unit_id(
        document_version_id=original_unit.document_version_id,
        source_text_sha256=original_unit.source_text_sha256,
        parser_version=original_unit.parser_version,
        unit_type="section", start=original_unit.start, end=original_unit.end)
    duplicate_unit = original_unit.model_copy(update={
        "unit_id": duplicate_unit_id, "unit_type": "section", "ordinal": 2,
        "parent_unit_id": None, "clause_id": None,
    })
    original_chunk = payload.chunking.chunks[0]
    duplicate_chunk = original_chunk.model_copy(update={
        "unit_id": duplicate_unit_id, "ordinal": 2, "clause_id": None,
        "chunk_id": chunk_id(
            document_version_id=original_chunk.document_version_id,
            unit_id=duplicate_unit_id, start=original_chunk.start, end=original_chunk.end,
            body_sha256=original_chunk.body_sha256),
    })
    duplicate_coverage = payload.chunking.unit_coverage[0].model_copy(
        update={"unit_id": duplicate_unit_id})
    tampered = payload.chunking.model_copy(update={
        "units": (original_unit, duplicate_unit),
        "chunks": (original_chunk, duplicate_chunk),
        "unit_coverage": (payload.chunking.unit_coverage[0], duplicate_coverage),
        "publishable": True,
    })
    changed, forged_payload = with_frozen_chunking(tmp_path, change, payload, tampered)
    spec = es.spec(tmp_path, mode="rechunk", change=changed)
    with es.client() as client, pytest.raises(RechunkCandidateError) as error:
        build_rechunk_candidate_v1(
            spec, client=client, prepare_vectors=lambda _: pytest.fail("must not prepare"),
            payloads=(forged_payload,))
    assert error.value.reason == "source_span_invalid"
    assert es.candidate is None


def test_new_chunk_id_colliding_with_existing_es_id_is_rejected(tmp_path: Path) -> None:
    es, change, payload = inputs(tmp_path)
    new_id = payload.chunking.chunks[0].chunk_id
    es.source[new_id] = es.source.pop("unclassified-1")
    assert es.source[new_id]["chunkId"] != new_id
    spec = es.spec(tmp_path, mode="rechunk", change=change)
    with es.client() as client, pytest.raises(RechunkCandidateError, match="source_span_invalid"):
        build_rechunk_candidate_v1(spec, client=client, prepare_vectors=prepared,
                                   payloads=(payload,))
    assert es.candidate is None


def test_cancellation_after_clone_seals_candidate(tmp_path: Path) -> None:
    es, change, payload = inputs(tmp_path)
    es.fault = "cancel_bulk"
    spec = es.spec(tmp_path, mode="rechunk", change=change)
    with es.client() as client, pytest.raises(KeyboardInterrupt):
        build_rechunk_candidate_v1(spec, client=client, prepare_vectors=prepared,
                                   payloads=(payload,))
    assert es.candidate_def is not None
    assert es.candidate_def["settings"]["index"]["blocks"]["write"] is True
    assert es.alias_snapshot == {SOURCE: {"aliases": {ALIAS: {}}}}


def test_seal_failure_reports_finite_reason_without_deletion(tmp_path: Path) -> None:
    es, change, payload = inputs(tmp_path)
    es.fault = "partial_bulk_seal_failure"
    spec = es.spec(tmp_path, mode="rechunk", change=change)
    with es.client() as client, pytest.raises(RechunkCandidateError) as error:
        build_rechunk_candidate_v1(spec, client=client, prepare_vectors=prepared,
                                   payloads=(payload,))
    assert error.value.reason == "bulk_failed"
    assert error.value.seal_status == "candidate_seal_failed"
    assert es.candidate is not None
    assert SECRET not in str(error.value)


def test_failure_seal_uses_reserved_http_budget(tmp_path: Path) -> None:
    es, change, _ = inputs(tmp_path)
    spec = es.spec(tmp_path, mode="rechunk", change=change)
    es.candidate = copy.deepcopy(es.source)
    es.candidate_def = copy.deepcopy(es.source_def)
    es.candidate_def["settings"]["index"]["uuid"] = "candidate-uuid"
    es.candidate_def["settings"]["index"]["resize"] = {
        "source": {"name": SOURCE, "uuid": "source-uuid"}}
    es.candidate_def["aliases"] = {OWNER_ALIAS: {
        "is_hidden": True, "is_write_index": False}}
    es.candidate_def["settings"]["index"]["blocks"]["write"] = "false"
    with es.client() as client:
        build = _Build(spec, client)
        build.clone_attempted = True
        build.clone_acknowledged = True
        build.calls = spec.max_http_requests - 3
        assert build.seal_on_failure() == "sealed"
        assert build.calls == spec.max_http_requests
    assert es.candidate_def["settings"]["index"]["blocks"]["write"] is True


def test_unknown_clone_result_without_source_proof_does_not_seal(tmp_path: Path) -> None:
    es, change, payload = inputs(tmp_path)
    es.fault = "unknown_clone_owner"
    spec = es.spec(tmp_path, mode="rechunk", change=change)
    with es.client() as client, pytest.raises(RechunkCandidateError) as error:
        build_rechunk_candidate_v1(spec, client=client, prepare_vectors=prepared,
                                   payloads=(payload,))
    assert error.value.reason == "candidate_ownership_unknown"
    assert error.value.seal_status == "ownership_unknown"
    assert es.candidate_def is not None
    assert not any(method == "PUT" and path.endswith("/_settings") for method, path in es.calls)
