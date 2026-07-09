#!/usr/bin/env python
"""构建 chinatax-policy-corpus 的文档检索 v2 ES + dense_vector 索引。"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    import pyarrow.parquet as pq
    import requests
except ImportError as exc:
    raise SystemExit(
        "缺少运行依赖，请先在临时环境安装 pyarrow 和 requests；"
        "示例：python -m pip install pyarrow requests"
    ) from exc


DATASET_URL = (
    "https://huggingface.co/datasets/salpt/chinatax-policy-corpus/"
    "resolve/main/data/train-00000-of-00001.parquet"
)
DEFAULT_DATASET_PATH = Path(".tmp/chinatax-v2/train.parquet")
DEFAULT_MANIFEST_PATH = Path(".tmp/chinatax-v2/build_manifest.json")

DEFAULT_INDEX = "agent-doc-tax-policy-v2-20260227-bge-m3"
DEFAULT_READ_ALIAS = "agent-doc-tax-policy-v2-read"
DEFAULT_WRITE_ALIAS = "agent-doc-tax-policy-v2-write"
DEFAULT_PROFILE = "tax_policy_v2_default"
DEFAULT_PROFILE_VERSION = "chinatax-policy-v2-20260227-bge-m3"

DOMAIN = "tax_policy"
MATERIAL_TYPE = "tax_policy"
CHUNK_STRATEGY = "tax-policy-section-v2"
CHUNK_VERSION = "chunk-v2.0.0"
SOURCE_DATASET = "salpt/chinatax-policy-corpus"
SOURCE_CRAWLED_AT = "2026-02-27"
HF_SOURCE_BASE_URL = "https://fgk.chinatax.gov.cn"


SECTION_PATTERN = re.compile(
    r"^(?:"
    r"第[一二三四五六七八九十百千万零〇0-9]+[章节].{0,60}"
    r"|附表[一二三四五六七八九十百千万零〇0-9]*.{0,60}"
    r"|附件[一二三四五六七八九十百千万零〇0-9]*.{0,60}"
    r")$"
)
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SPLIT_PATTERN = re.compile(r"[，,、;；/|]+")


@dataclass(frozen=True)
class Section:
    title: str
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class Chunk:
    section: str
    text: str
    char_start: int
    char_end: int
    parent_section_id: str


def mapping_definition(dimension: int) -> dict[str, Any]:
    return {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "refresh_interval": "-1",
            "analysis": {
                "analyzer": {
                    "policy_text_analyzer": {"type": "standard"},
                    "policy_phrase_analyzer": {"type": "standard"},
                }
            },
        },
        "mappings": {
            "properties": {
                "tenantId": {"type": "keyword"},
                "corpusId": {"type": "keyword"},
                "domain": {"type": "keyword"},
                "materialType": {"type": "keyword"},
                "retrievalProfile": {"type": "keyword"},
                "profileVersion": {"type": "keyword"},
                "documentId": {"type": "keyword"},
                "documentVersion": {"type": "keyword"},
                "chunkId": {"type": "keyword"},
                "chunkIndex": {"type": "integer"},
                "charStart": {"type": "integer"},
                "charEnd": {"type": "integer"},
                "title": {
                    "type": "text",
                    "analyzer": "policy_text_analyzer",
                    "fields": {"keyword": {"type": "keyword"}},
                },
                "content": {
                    "type": "text",
                    "analyzer": "policy_text_analyzer",
                    "search_analyzer": "policy_phrase_analyzer",
                },
                "snippet": {"type": "text", "analyzer": "policy_text_analyzer"},
                "section": {
                    "type": "text",
                    "analyzer": "policy_text_analyzer",
                    "fields": {"keyword": {"type": "keyword"}},
                },
                "documentNo": {"type": "keyword"},
                "issuer": {"type": "keyword"},
                "taxType": {"type": "keyword"},
                "effectiveDate": {"type": "date"},
                "writtenDate": {"type": "date"},
                "validityStatus": {"type": "keyword"},
                "aclRef": {"type": "keyword"},
                "aclVersion": {"type": "keyword"},
                "visibility": {"type": "keyword"},
                "departmentIds": {"type": "keyword"},
                "roleIds": {"type": "keyword"},
                "userIds": {"type": "keyword"},
                "attributeKeys": {"type": "keyword"},
                "status": {"type": "keyword"},
                "chunkStrategy": {"type": "keyword"},
                "chunkVersion": {"type": "keyword"},
                "parentSectionId": {"type": "keyword"},
                "indexVersion": {"type": "keyword"},
                "contentHash": {"type": "keyword"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": dimension,
                    "index": True,
                    "similarity": "cosine",
                },
                "sourceDataset": {"type": "keyword"},
                "sourceCrawledAt": {"type": "date"},
                "sourceRowNumber": {"type": "integer"},
                "sourceUri": {"type": "keyword"},
                "sourceUrl": {"type": "keyword"},
                "channel": {"type": "keyword"},
                "effectLevel": {"type": "keyword"},
                "labels": {"type": "keyword"},
                "indexedAt": {"type": "date"},
            }
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--es-url", default="http://127.0.0.1:9200")
    parser.add_argument("--embedding-url", default="http://127.0.0.1:8908")
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--dataset-url", default=DATASET_URL)
    parser.add_argument("--index", default=DEFAULT_INDEX)
    parser.add_argument("--read-alias", default=DEFAULT_READ_ALIAS)
    parser.add_argument("--write-alias", default=DEFAULT_WRITE_ALIAS)
    parser.add_argument("--tenant-id", default="tenant-local")
    parser.add_argument("--retrieval-profile", default=DEFAULT_PROFILE)
    parser.add_argument("--profile-version", default=DEFAULT_PROFILE_VERSION)
    parser.add_argument("--dimension", type=int, default=1024)
    parser.add_argument("--chunk-size", type=int, default=1600)
    parser.add_argument("--chunk-overlap", type=int, default=120)
    parser.add_argument("--embed-batch-size", type=int, default=16)
    parser.add_argument("--bulk-batch-size", type=int, default=128)
    parser.add_argument("--request-timeout", type=int, default=120)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--recreate", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validate_args(args)
    session = requests.Session()
    ensure_dataset(args.dataset_path, args.dataset_url, session, args.request_timeout)
    rows = pq.read_table(args.dataset_path).to_pylist()
    if args.limit > 0:
        rows = rows[: args.limit]
    rows = [normalize_row(row, index) for index, row in enumerate(rows)]

    planned_chunks = sum(len(chunks_for_row(row, args)) for row in rows)
    print(
        json.dumps(
            {
                "event": "plan",
                "rows": len(rows),
                "plannedChunks": planned_chunks,
                "index": args.index,
                "readAlias": args.read_alias,
                "dimension": args.dimension,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    if args.dry_run:
        return 0

    verify_embedding_provider(session, args)
    recreate_index_if_needed(session, args)

    indexed = 0
    failed = 0
    chunk_batch: list[dict[str, Any]] = []
    started = time.monotonic()
    for row in rows:
        chunks = chunks_for_row(row, args)
        for chunk_index, chunk in enumerate(chunks):
            chunk_batch.append(build_document(row, chunk, chunk_index, len(chunks), args))
            if len(chunk_batch) >= args.embed_batch_size:
                indexed += embed_and_bulk(session, chunk_batch, args)
                failed += failed_documents(chunk_batch)
                chunk_batch = []
                log_progress(indexed, planned_chunks, failed, started)
    if chunk_batch:
        indexed += embed_and_bulk(session, chunk_batch, args)
        failed += failed_documents(chunk_batch)
        log_progress(indexed, planned_chunks, failed, started)

    finalize_index(session, args)
    count = es_get(session, args.es_url, f"/{args.index}/_count", timeout=args.request_timeout)["count"]
    manifest = {
        "dataset": SOURCE_DATASET,
        "datasetUrl": args.dataset_url,
        "sourceCrawledAt": SOURCE_CRAWLED_AT,
        "index": args.index,
        "readAlias": args.read_alias,
        "writeAlias": args.write_alias,
        "tenantId": args.tenant_id,
        "domain": DOMAIN,
        "materialType": MATERIAL_TYPE,
        "retrievalProfile": args.retrieval_profile,
        "profileVersion": args.profile_version,
        "dimension": args.dimension,
        "rows": len(rows),
        "plannedChunks": planned_chunks,
        "indexedChunks": indexed,
        "failedChunks": failed,
        "esCount": count,
        "builtAt": now_iso(),
    }
    write_json(args.manifest_path, manifest)
    print(json.dumps({"event": "complete", **manifest}, ensure_ascii=False), flush=True)
    return 0


def validate_args(args: argparse.Namespace) -> None:
    if args.dimension <= 0:
        raise SystemExit("--dimension 必须为正数")
    if args.chunk_size <= 200:
        raise SystemExit("--chunk-size 过小")
    if args.chunk_overlap < 0 or args.chunk_overlap >= args.chunk_size:
        raise SystemExit("--chunk-overlap 必须小于 chunk-size")
    if args.embed_batch_size <= 0 or args.bulk_batch_size <= 0:
        raise SystemExit("batch size 必须为正数")


def ensure_dataset(path: Path, url: str, session: requests.Session, timeout: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return
    print(json.dumps({"event": "download", "url": url, "path": str(path)}, ensure_ascii=False), flush=True)
    with session.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with tmp_path.open("wb") as output:
            for block in response.iter_content(chunk_size=1024 * 1024):
                if block:
                    output.write(block)
        tmp_path.replace(path)


def normalize_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    normalized = {key: safe_text(value) for key, value in row.items()}
    normalized["sourceRowNumber"] = index
    normalized["content"] = normalize_content(normalized.get("content", ""))
    normalized["title"] = single_line(normalized.get("title", ""))
    normalized["document_number"] = single_line(normalized.get("document_number", ""))
    normalized["issuing_department"] = single_line(normalized.get("issuing_department", ""))
    return normalized


def normalize_content(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace("\u3000", " ").replace("\u2002", " ").replace("\xa0", " ")
    lines: list[str] = []
    previous_blank = False
    for raw_line in value.split("\n"):
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if not line:
            if not previous_blank and lines:
                lines.append("")
            previous_blank = True
            continue
        lines.append(line)
        previous_blank = False
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines).strip()


def chunks_for_row(row: dict[str, Any], args: argparse.Namespace) -> list[Chunk]:
    content = row.get("content", "")
    if not content:
        content = row.get("title", "")
    sections = sectionize(content)
    chunks: list[Chunk] = []
    for section in sections:
        for chunk in split_section(section, args.chunk_size, args.chunk_overlap):
            if chunk.text.strip() and not is_low_value_chunk(chunk.text):
                chunks.append(chunk)
    if not chunks:
        text = row.get("title", "")
        chunks.append(Chunk("标题", text, 0, len(text), section_id("标题", 0)))
    return chunks


def is_low_value_chunk(text: str) -> bool:
    value = single_line(text)
    if not value:
        return True
    if value.startswith("目 录") or value.startswith("目录"):
        return True
    return False


def sectionize(content: str) -> list[Section]:
    lines = content.split("\n")
    offsets: list[tuple[str, int, int]] = []
    cursor = 0
    for line in lines:
        start = cursor
        end = start + len(line)
        offsets.append((line, start, end))
        cursor = end + 1

    sections: list[Section] = []
    current_title = "正文"
    current_start = 0
    current_lines: list[str] = []
    for line, start, end in offsets:
        is_heading = looks_like_heading(line)
        if is_heading and current_lines:
            text = "\n".join(current_lines).strip()
            sections.append(Section(current_title, text, current_start, start))
            current_title = line[:80]
            current_start = start
            current_lines = [line]
        else:
            if is_heading and not current_lines:
                current_title = line[:80]
                current_start = start
            current_lines.append(line)
    if current_lines:
        sections.append(Section(current_title, "\n".join(current_lines).strip(), current_start, len(content)))
    return sections


def looks_like_heading(line: str) -> bool:
    value = line.strip()
    if len(value) < 2 or len(value) > 80:
        return False
    if value.startswith(("目", "税 目", "计税单位", "税 额", "备注")):
        return False
    return bool(SECTION_PATTERN.match(value))


def split_section(section: Section, chunk_size: int, overlap: int) -> list[Chunk]:
    text = section.text.strip()
    if len(text) <= chunk_size:
        return [Chunk(section.title, text, section.start, section.end, section_id(section.title, section.start))]
    chunks: list[Chunk] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        if end < len(text):
            end = best_break(text, start, end)
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(
                Chunk(
                    section.title,
                    chunk_text,
                    section.start + start,
                    section.start + end,
                    section_id(section.title, section.start),
                )
            )
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def best_break(text: str, start: int, proposed_end: int) -> int:
    lower = start + int((proposed_end - start) * 0.65)
    window = text[lower:proposed_end]
    candidates = [window.rfind(token) for token in ("\n", "。", "；", ";", "！", "？")]
    best = max(candidates)
    if best >= 0:
        return lower + best + 1
    return proposed_end


def build_document(
    row: dict[str, Any],
    chunk: Chunk,
    chunk_index: int,
    chunk_count: int,
    args: argparse.Namespace,
) -> dict[str, Any]:
    title = row.get("title", "")
    document_id = stable_id(row)
    document_version = sha256_json(
        {
            "title": title,
            "documentNo": row.get("document_number", ""),
            "writtenDate": row.get("written_date", ""),
            "url": row.get("url", ""),
            "contentHash": sha256_text(row.get("content", "")),
        }
    )
    chunk_id = f"{document_id}#c{chunk_index:04d}"
    source_url = row.get("url", "")
    source_uri = source_url if source_url.startswith("http") else HF_SOURCE_BASE_URL + source_url
    written_date = valid_date_or_none(row.get("written_date", ""))
    doc = {
        "tenantId": args.tenant_id,
        "corpusId": DOMAIN,
        "domain": DOMAIN,
        "materialType": MATERIAL_TYPE,
        "retrievalProfile": args.retrieval_profile,
        "profileVersion": args.profile_version,
        "documentId": document_id,
        "documentVersion": document_version,
        "chunkId": chunk_id,
        "chunkIndex": chunk_index,
        "charStart": chunk.char_start,
        "charEnd": chunk.char_end,
        "title": title,
        "content": chunk.text,
        "snippet": snippet(chunk.text),
        "section": chunk.section,
        "documentNo": row.get("document_number", ""),
        "issuer": row.get("issuing_department", ""),
        "taxType": split_values(row.get("tax_type", "")),
        "effectiveDate": written_date,
        "writtenDate": written_date,
        "validityStatus": validity_status(row.get("aging", "")),
        "aclRef": f"public:{DOMAIN}",
        "aclVersion": "public-v1",
        "visibility": "PUBLIC",
        "departmentIds": [],
        "roleIds": [],
        "userIds": [],
        "attributeKeys": ["tax-policy-local"],
        "status": "ACTIVE",
        "chunkStrategy": CHUNK_STRATEGY,
        "chunkVersion": CHUNK_VERSION,
        "parentSectionId": chunk.parent_section_id,
        "indexVersion": args.profile_version,
        "contentHash": sha256_text(f"{document_id}|{chunk_index}|{chunk.text}"),
        "sourceDataset": SOURCE_DATASET,
        "sourceCrawledAt": SOURCE_CRAWLED_AT,
        "sourceRowNumber": row.get("sourceRowNumber", 0),
        "sourceUri": source_uri,
        "sourceUrl": source_url,
        "channel": row.get("channel", ""),
        "effectLevel": row.get("effect_level", ""),
        "labels": split_values(row.get("labels", "")),
        "indexedAt": now_iso(),
        "chunkCount": chunk_count,
    }
    doc["_embeddingInput"] = embedding_input(doc)
    return doc


def stable_id(row: dict[str, Any]) -> str:
    raw = "|".join(
        [
            row.get("url", ""),
            row.get("title", ""),
            row.get("document_number", ""),
            row.get("written_date", ""),
        ]
    )
    return "tax-" + sha256_text(raw)[:24]


def section_id(title: str, start: int) -> str:
    return "sec-" + sha256_text(f"{title}|{start}")[:16]


def embedding_input(doc: dict[str, Any]) -> str:
    tax_type = "、".join(doc.get("taxType") or [])
    labels = "、".join(doc.get("labels") or [])
    parts = [
        f"标题：{doc['title']}",
        f"文号：{doc['documentNo']}",
        f"发文机关：{doc['issuer']}",
        f"资料域：税务政策",
        f"效力状态：{doc['validityStatus']}",
        f"税种：{tax_type}",
        f"标签：{labels}",
        f"章节：{doc['section']}",
        f"正文：{doc['content']}",
    ]
    value = "\n".join(part for part in parts if not part.endswith("："))
    return value[:1800]


def verify_embedding_provider(session: requests.Session, args: argparse.Namespace) -> None:
    vectors, dim = embed_texts(session, args, ["增值税税率"])
    if dim != args.dimension or len(vectors[0]) != args.dimension:
        raise SystemExit(f"embedding 维度不匹配：provider={dim}, expected={args.dimension}")


def recreate_index_if_needed(session: requests.Session, args: argparse.Namespace) -> None:
    if index_exists(session, args.es_url, args.index, args.request_timeout):
        if not args.recreate:
            raise SystemExit(f"索引已存在：{args.index}；如需重建请添加 --recreate")
        es_delete(session, args.es_url, f"/{args.index}", timeout=args.request_timeout)
    es_put(session, args.es_url, f"/{args.index}", mapping_definition(args.dimension), timeout=args.request_timeout)
    print(json.dumps({"event": "index_created", "index": args.index}, ensure_ascii=False), flush=True)


def embed_and_bulk(session: requests.Session, docs: list[dict[str, Any]], args: argparse.Namespace) -> int:
    vectors, dim = embed_texts(session, args, [doc["_embeddingInput"] for doc in docs])
    if dim != args.dimension:
        raise RuntimeError(f"embedding 维度不匹配：provider={dim}, expected={args.dimension}")
    for doc, vector in zip(docs, vectors, strict=True):
        if len(vector) != args.dimension:
            raise RuntimeError("embedding 向量长度不匹配")
        doc["embedding"] = vector
        doc.pop("_embeddingInput", None)
    bulk_index(session, args, docs)
    return len(docs)


def embed_texts(
    session: requests.Session,
    args: argparse.Namespace,
    texts: list[str],
) -> tuple[list[list[float]], int]:
    endpoint = args.embedding_url.rstrip("/") + "/embed"
    response = session.post(endpoint, json={"texts": texts}, timeout=args.request_timeout)
    response.raise_for_status()
    payload = response.json()
    vectors = payload.get("vectors")
    dim = payload.get("dim")
    if not isinstance(dim, int) or not isinstance(vectors, list) or len(vectors) != len(texts):
        raise RuntimeError("embedding provider 返回格式不符合 /embed 契约")
    normalized: list[list[float]] = []
    for vector in vectors:
        if not isinstance(vector, list):
            raise RuntimeError("embedding provider 返回非数组向量")
        values = [float(value) for value in vector]
        if any(not math.isfinite(value) for value in values):
            raise RuntimeError("embedding provider 返回非有限数向量")
        normalized.append(values)
    return normalized, dim


def bulk_index(session: requests.Session, args: argparse.Namespace, docs: list[dict[str, Any]]) -> None:
    lines: list[str] = []
    for doc in docs:
        doc_id = doc["chunkId"]
        lines.append(json.dumps({"index": {"_index": args.index, "_id": doc_id}}, ensure_ascii=False))
        lines.append(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
    body = "\n".join(lines) + "\n"
    response = session.post(
        args.es_url.rstrip("/") + "/_bulk",
        data=body.encode("utf-8"),
        headers={"Content-Type": "application/x-ndjson"},
        timeout=args.request_timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        first_error = next((item for item in payload.get("items", []) if item.get("index", {}).get("error")), None)
        raise RuntimeError(f"ES bulk 写入失败：{json.dumps(first_error, ensure_ascii=False)[:1000]}")


def finalize_index(session: requests.Session, args: argparse.Namespace) -> None:
    es_put(
        session,
        args.es_url,
        f"/{args.index}/_settings",
        {"index": {"refresh_interval": "1s"}},
        timeout=args.request_timeout,
    )
    es_post(session, args.es_url, f"/{args.index}/_refresh", None, timeout=args.request_timeout)
    actions: list[dict[str, Any]] = [
        {"remove": {"index": "*", "alias": args.read_alias, "must_exist": False}},
        {"remove": {"index": "*", "alias": args.write_alias, "must_exist": False}},
        {"add": {"index": args.index, "alias": args.read_alias}},
        {"add": {"index": args.index, "alias": args.write_alias, "is_write_index": True}},
    ]
    es_post(session, args.es_url, "/_aliases", {"actions": actions}, timeout=args.request_timeout)


def log_progress(indexed: int, total: int, failed: int, started: float) -> None:
    if indexed == total or indexed % 512 == 0:
        elapsed = round(time.monotonic() - started, 1)
        print(
            json.dumps(
                {"event": "progress", "indexed": indexed, "total": total, "failed": failed, "elapsedSec": elapsed},
                ensure_ascii=False,
            ),
            flush=True,
        )


def failed_documents(docs: list[dict[str, Any]]) -> int:
    return sum(1 for doc in docs if not doc.get("embedding"))


def index_exists(session: requests.Session, es_url: str, index: str, timeout: int) -> bool:
    response = session.head(es_url.rstrip("/") + f"/{index}", timeout=timeout)
    if response.status_code == 404:
        return False
    response.raise_for_status()
    return True


def es_get(session: requests.Session, es_url: str, path: str, timeout: int) -> dict[str, Any]:
    response = session.get(es_url.rstrip() + path, timeout=timeout)
    response.raise_for_status()
    return response.json()


def es_put(session: requests.Session, es_url: str, path: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    response = session.put(es_url.rstrip("/") + path, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def es_post(
    session: requests.Session,
    es_url: str,
    path: str,
    payload: dict[str, Any] | None,
    timeout: int,
) -> dict[str, Any]:
    if payload is None:
        response = session.post(es_url.rstrip("/") + path, timeout=timeout)
    else:
        response = session.post(es_url.rstrip("/") + path, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def es_delete(session: requests.Session, es_url: str, path: str, timeout: int) -> dict[str, Any]:
    response = session.delete(es_url.rstrip("/") + path, timeout=timeout)
    if response.status_code == 404:
        return {}
    response.raise_for_status()
    return response.json()


def split_values(value: str) -> list[str]:
    values = [item.strip() for item in SPLIT_PATTERN.split(value or "") if item.strip()]
    deduped: list[str] = []
    for item in values:
        if item not in deduped:
            deduped.append(item)
    return deduped


def validity_status(value: str) -> str:
    normalized = (value or "").strip()
    return {
        "全文有效": "ACTIVE",
        "尚未生效": "PENDING",
        "全文废止": "EXPIRED",
        "全文失效": "EXPIRED",
        "已修改": "AMENDED",
    }.get(normalized, "UNKNOWN")


def valid_date_or_none(value: str) -> str | None:
    value = (value or "").strip()
    if not DATE_PATTERN.match(value):
        return None
    try:
        dt.date.fromisoformat(value)
        return value
    except ValueError:
        return None


def snippet(value: str, limit: int = 220) -> str:
    value = single_line(value)
    return value[:limit]


def single_line(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_json(value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(payload)


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
