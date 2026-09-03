from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from .errors import ContractError, StateConflict
from .jsonio import canonical_bytes, load_jsonl, sha256_bytes, sha256_file, write_model
from .models import AssetManifest, BuildManifest, CorpusChunk, ParsedDocument


TRACE_PROPERTIES: dict[str, Any] = {
    "assetId": {"type": "keyword"},
    "assetVersion": {"type": "keyword"},
    "assetSha256": {"type": "keyword"},
    "assetKind": {"type": "keyword"},
    "parentDocumentId": {"type": "keyword"},
    "parentAssetId": {"type": "keyword"},
    "relationType": {"type": "keyword"},
    "sectionPath": {"type": "keyword"},
    "clauseId": {"type": "keyword"},
    "tableId": {"type": "keyword"},
    "parserVersion": {"type": "keyword"},
    "ocrApplied": {"type": "boolean"},
    "ocrConfidenceStatus": {"type": "keyword"},
    "sourceFinalUrl": {"type": "keyword", "index": False},
    "sourceFetchedAt": {"type": "date"},
}


class EmbeddingClient:
    def __init__(self, endpoint: str, *, client: httpx.Client | None = None) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._owned = client is None
        self._client = client or httpx.Client(timeout=60.0)

    def close(self) -> None:
        if self._owned:
            self._client.close()

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        if not 1 <= len(texts) <= 32:
            raise ContractError("embedding batch must contain 1..32 texts")
        response = self._client.post(f"{self._endpoint}/embed", json={"texts": list(texts)})
        response.raise_for_status()
        value = response.json()
        if not isinstance(value, dict) or set(value) != {"dim", "vectors"} or value.get("dim") != 1024:
            raise ContractError("invalid embedding response shape")
        vectors = value.get("vectors")
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise ContractError("invalid embedding response shape")
        output: list[tuple[float, ...]] = []
        for vector in vectors:
            if not isinstance(vector, list) or len(vector) != 1024:
                raise ContractError("embedding must contain exactly 1024 dimensions")
            converted = tuple(float(item) for item in vector)
            if any(not math.isfinite(item) for item in converted):
                raise ContractError("embedding contains non-finite value")
            output.append(converted)
        return tuple(output)


class ElasticsearchCandidateAdmin:
    def __init__(self, endpoint: str, *, client: httpx.Client | None = None) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._owned = client is None
        self._client = client or httpx.Client(timeout=120.0)

    def close(self) -> None:
        if self._owned:
            self._client.close()

    def index_uuid(self, index: str) -> str:
        response = self._client.get(f"{self._endpoint}/{index}")
        response.raise_for_status()
        body = response.json()
        return str(body[index]["settings"]["index"]["uuid"])

    def alias_targets(self, alias: str) -> tuple[str, ...]:
        response = self._client.get(f"{self._endpoint}/_alias/{alias}")
        response.raise_for_status()
        return tuple(sorted(response.json().keys()))

    def create_and_clone(
        self,
        *,
        source_index: str,
        source_uuid: str,
        candidate_index: str,
    ) -> None:
        if self.index_uuid(source_index) != source_uuid:
            raise StateConflict("source index UUID changed")
        existing = self._client.head(f"{self._endpoint}/{candidate_index}")
        if existing.status_code != 404:
            raise StateConflict("candidate index already exists")
        definition_response = self._client.get(f"{self._endpoint}/{source_index}")
        definition_response.raise_for_status()
        definition = definition_response.json()[source_index]
        mapping = definition["mappings"]
        properties = mapping.setdefault("properties", {})
        if any(name in properties for name in TRACE_PROPERTIES):
            raise StateConflict("source mapping unexpectedly contains Stage A trace fields")
        properties.update(TRACE_PROPERTIES)
        mapping.setdefault("_meta", {})["mapping_version"] = "agent-knowledge-tax-v2-corpus-a1"
        source_settings = definition["settings"]["index"]
        settings = {
            key: source_settings[key]
            for key in ("number_of_shards", "number_of_replicas", "refresh_interval", "analysis")
            if key in source_settings
        }
        create = self._client.put(
            f"{self._endpoint}/{candidate_index}",
            json={"settings": settings, "mappings": mapping},
        )
        create.raise_for_status()
        reindex = self._client.post(
            f"{self._endpoint}/_reindex?wait_for_completion=true&refresh=true",
            json={"source": {"index": source_index}, "dest": {"index": candidate_index, "op_type": "create"}, "conflicts": "abort"},
        )
        reindex.raise_for_status()
        result = reindex.json()
        if result.get("failures") or int(result.get("created", -1)) != int(result.get("total", -2)):
            raise StateConflict("baseline reindex was incomplete")

    def source_document(self, *, index: str, document_id: str) -> dict[str, Any]:
        response = self._client.post(
            f"{self._endpoint}/{index}/_search",
            json={"query": {"term": {"documentId": document_id}}, "size": 1},
        )
        response.raise_for_status()
        hits = response.json().get("hits", {}).get("hits", [])
        if len(hits) != 1 or not isinstance(hits[0].get("_source"), dict):
            raise StateConflict("parent source document is not uniquely available")
        return dict(hits[0]["_source"])

    def add_chunks(self, *, candidate_index: str, documents: Iterable[dict[str, Any]]) -> int:
        lines: list[str] = []
        count = 0
        for document in documents:
            identifier = str(document["chunkId"])
            lines.append(json.dumps({"create": {"_index": candidate_index, "_id": identifier}}, separators=(",", ":")))
            lines.append(json.dumps(document, ensure_ascii=False, separators=(",", ":")))
            count += 1
        if not lines:
            return 0
        response = self._client.post(
            f"{self._endpoint}/_bulk?refresh=true",
            content=("\n".join(lines) + "\n").encode("utf-8"),
            headers={"Content-Type": "application/x-ndjson"},
        )
        response.raise_for_status()
        result = response.json()
        if result.get("errors"):
            raise StateConflict("bulk create contained failures")
        return count

    def block_writes(self, *, candidate_index: str) -> None:
        response = self._client.put(
            f"{self._endpoint}/{candidate_index}/_settings",
            json={"index.blocks.write": True},
        )
        response.raise_for_status()

    def count(self, *, index: str) -> int:
        response = self._client.get(f"{self._endpoint}/{index}/_count")
        response.raise_for_status()
        return int(response.json()["count"])

    def mapping_sha256(self, *, index: str) -> str:
        response = self._client.get(f"{self._endpoint}/{index}/_mapping")
        response.raise_for_status()
        mapping = response.json()[index]["mappings"]
        return sha256_bytes(canonical_bytes(mapping))


def normalized_fingerprint(documents: Sequence[dict[str, Any]]) -> str:
    canonical = json.dumps(sorted(documents, key=lambda item: str(item.get("chunkId"))), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def tool_source_fingerprint() -> str:
    root = Path(__file__).resolve().parent
    records = [
        {"path": path.name, "sha256": sha256_file(path)}
        for path in sorted(root.glob("*.py"), key=lambda item: item.name)
    ]
    return sha256_bytes(canonical_bytes(records))


def to_index_document(
    *,
    chunk: CorpusChunk,
    vector: Sequence[float],
    parent_source: dict[str, Any],
    attachment_title: str,
    source_url: str,
    source_final_url: str,
    source_fetched_at: str,
    parser_version: str,
    chunk_count: int,
) -> dict[str, Any]:
    if len(vector) != 1024 or any(not math.isfinite(float(item)) for item in vector):
        raise ContractError("index vector must contain 1024 finite values")
    required = {"aclRef", "aclVersion", "visibility", "channel", "tenantId", "corpusId", "domain", "materialType"}
    if not required.issubset(parent_source):
        raise ContractError("parent source is missing required authorization metadata")
    document = {
        key: value
        for key, value in parent_source.items()
        if key not in {"content", "snippet", "section", "embedding", "chunkId", "chunkIndex", "charStart", "charEnd", "contentHash", "chunkCount"}
    }
    attachment_document_id = f"{chunk.document_id}@{chunk.asset_id}"
    document.update(
        {
            "documentId": attachment_document_id,
            "documentVersion": chunk.asset_version,
            "title": attachment_title,
            "sourceUri": source_final_url,
            "sourceUrl": source_url,
            "section": " / ".join(chunk.section_path) or "附件",
            "content": chunk.content,
            "snippet": chunk.content[:512],
            "embedding": list(vector),
            "chunkId": chunk.chunk_id,
            "chunkIndex": chunk.ordinal - 1,
            "charStart": 0,
            "charEnd": len(chunk.content),
            "contentHash": chunk.content_sha256,
            "chunkCount": chunk_count,
            "chunkStrategy": "knowledge-structure-chunker-v1",
            "chunkVersion": "knowledge-structure-chunker-v1",
            "indexVersion": "agent-doc-tax-policy-v4-20260902-corpus-a1",
            "assetId": chunk.asset_id,
            "assetVersion": chunk.asset_version,
            "assetSha256": chunk.asset_version,
            "assetKind": "attachment",
            "parentDocumentId": chunk.document_id,
            "parentAssetId": None,
            "relationType": "attachment_chunk",
            "sectionPath": list(chunk.section_path),
            "clauseId": chunk.clause_id,
            "tableId": chunk.table_id,
            "parserVersion": parser_version,
            "ocrApplied": chunk.ocr_applied,
            "ocrConfidenceStatus": chunk.ocr_confidence_status.value,
            "sourceFinalUrl": source_final_url,
            "sourceFetchedAt": source_fetched_at,
        }
    )
    return document


def build_candidate_index(
    *,
    workspace: Path,
    run_id: str,
    es_endpoint: str,
    embedding_endpoint: str,
    source_index: str,
    source_uuid: str,
    source_document_count: int,
    candidate_index: str,
) -> BuildManifest:
    run_dir = workspace.resolve() / "runs" / run_id
    manifest_path = run_dir / "asset-manifest.v1.jsonl"
    manifests = {item.asset_id: item for item in load_jsonl(manifest_path, AssetManifest)}
    parsed = {item.asset_id: item for item in load_jsonl(run_dir / "parsed-documents.v1.jsonl", ParsedDocument)}
    chunks = load_jsonl(run_dir / "chunks.v1.jsonl", CorpusChunk)
    per_asset_count: dict[str, int] = {}
    for chunk in chunks:
        per_asset_count[chunk.asset_id] = per_asset_count.get(chunk.asset_id, 0) + 1
    admin = ElasticsearchCandidateAdmin(es_endpoint)
    embedding = EmbeddingClient(embedding_endpoint)
    indexed_documents: list[dict[str, Any]] = []
    try:
        source_chunk_count = admin.count(index=source_index)
        admin.create_and_clone(
            source_index=source_index,
            source_uuid=source_uuid,
            candidate_index=candidate_index,
        )
        parent_cache: dict[str, dict[str, Any]] = {}
        for offset in range(0, len(chunks), 32):
            batch = chunks[offset : offset + 32]
            vectors = embedding.embed(tuple(chunk.content for chunk in batch))
            for chunk, vector in zip(batch, vectors, strict=True):
                manifest = manifests[chunk.asset_id]
                parsed_document = parsed[chunk.asset_id]
                if manifest.parent_document_id not in parent_cache:
                    parent_cache[manifest.parent_document_id] = admin.source_document(
                        index=source_index,
                        document_id=manifest.parent_document_id,
                    )
                parent = parent_cache[manifest.parent_document_id]
                indexed_documents.append(
                    to_index_document(
                        chunk=chunk,
                        vector=vector,
                        parent_source=parent,
                        attachment_title=Path(manifest.filename).stem,
                        source_url=manifest.source_url,
                        source_final_url=manifest.source_final_url,
                        source_fetched_at=manifest.fetched_at_utc.isoformat(),
                        parser_version=f"{parsed_document.parser_name}:{parsed_document.parser_version}",
                        chunk_count=per_asset_count[chunk.asset_id],
                    )
                )
        for offset in range(0, len(indexed_documents), 250):
            admin.add_chunks(candidate_index=candidate_index, documents=indexed_documents[offset : offset + 250])
        expected_total = source_chunk_count + len(indexed_documents)
        actual_total = admin.count(index=candidate_index)
        if actual_total != expected_total:
            raise StateConflict("candidate document count is incomplete")
        admin.block_writes(candidate_index=candidate_index)
        candidate_uuid = admin.index_uuid(candidate_index)
        build = BuildManifest(
            schema_version=1,
            candidate_index=candidate_index,
            candidate_index_uuid=candidate_uuid,
            source_index=source_index,
            source_index_uuid=source_uuid,
            mapping_version="agent-knowledge-tax-v2-corpus-a1",
            parser_versions={
                item.parser_name: item.parser_version for item in parsed.values()
            },
            chunker_version="knowledge-structure-chunker-v1",
            embedding_model="BGE-M3",
            embedding_dimensions=1024,
            source_document_count=source_document_count,
            source_chunk_count=source_chunk_count,
            asset_count=len(manifests),
            new_chunk_count=len(indexed_documents),
            total_chunk_count=actual_total,
            normalized_fingerprint=normalized_fingerprint(indexed_documents),
            source_manifest_sha256=sha256_file(manifest_path),
            mapping_sha256=admin.mapping_sha256(index=candidate_index),
            tool_source_sha256=tool_source_fingerprint(),
            build_completed_at_utc=datetime.now(UTC),
        )
        write_model(run_dir / "build-manifest.v1.json", build)
        return build
    finally:
        embedding.close()
        admin.close()
