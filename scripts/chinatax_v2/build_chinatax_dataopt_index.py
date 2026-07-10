#!/usr/bin/env python
"""Build a data-optimized chinatax policy index from the current ES index.

The script does not switch the production read alias unless --switch-alias is set.
It is intended for data-layer experiments: analyzer upgrade, metadata enrichment,
chunk reshaping, embedding-text enrichment, and curated current-answer chunks.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import sys
import time
from collections import defaultdict
from typing import Any

import requests


DEFAULT_SOURCE = "agent-doc-tax-policy-v2-read"
DEFAULT_TARGET = "agent-doc-tax-policy-v3-20260710-dataopt-bge-m3"
DEFAULT_READ_ALIAS = "agent-doc-tax-policy-v3-dataopt-read"
DEFAULT_WRITE_ALIAS = "agent-doc-tax-policy-v3-dataopt-write"
DEFAULT_PROFILE = "tax_policy_v2_default"
DEFAULT_PROFILE_VERSION = "chinatax-policy-v2-dataopt-20260710-bge-m3"

DOMAIN = "tax_policy"
MATERIAL_TYPE = "tax_policy"
CHUNK_STRATEGY = "tax-policy-section-dataopt-v1"
CHUNK_VERSION = "chunk-dataopt-v1.0.0"
SOURCE_DATASET = "salpt/chinatax-policy-corpus"
SUMMARY_DATASET = "curated/tax-policy-current-summaries"
RATE_PATTERN = re.compile(r"(?:百分之[一二三四五六七八九十零〇百]+|\d+(?:\.\d+)?\s*%)")
SENTENCE_SPLIT = re.compile(r"(?<=[。；;！？])")
CITATION_TEXT_LIMIT = 500
GENERATION_TEXT_LIMIT = 1600
EMBEDDING_TEXT_LIMIT = 2200


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--es-url", default="http://127.0.0.1:9200")
    parser.add_argument("--embedding-url", default="http://127.0.0.1:8908")
    parser.add_argument("--source-index", default=DEFAULT_SOURCE)
    parser.add_argument("--target-index", default=DEFAULT_TARGET)
    parser.add_argument("--read-alias", default=DEFAULT_READ_ALIAS)
    parser.add_argument("--write-alias", default=DEFAULT_WRITE_ALIAS)
    parser.add_argument("--tenant-id", default="tenant-local")
    parser.add_argument("--retrieval-profile", default=DEFAULT_PROFILE)
    parser.add_argument("--profile-version", default=DEFAULT_PROFILE_VERSION)
    parser.add_argument("--dimension", type=int, default=1024)
    parser.add_argument("--scroll-size", type=int, default=500)
    parser.add_argument("--embed-batch-size", type=int, default=16)
    parser.add_argument("--bulk-batch-size", type=int, default=128)
    parser.add_argument("--max-chunk-size", type=int, default=1100)
    parser.add_argument("--min-standalone-chunk-size", type=int, default=80)
    parser.add_argument("--reshape-chunks", action="store_true")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--limit-documents", type=int, default=0)
    parser.add_argument("--recreate", action="store_true")
    parser.add_argument("--switch-alias", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validate_args(args)
    session = requests.Session()
    docs_by_id = load_source_documents(session, args)
    source_document_count = len(docs_by_id)
    if args.limit_documents > 0:
        docs_by_id = dict(list(docs_by_id.items())[: args.limit_documents])
    optimized_docs = []
    for document_id, chunks in docs_by_id.items():
        optimized_docs.extend(transform_document(document_id, chunks, args))
    optimized_docs.extend(curated_summary_documents(args))
    print(
        json.dumps(
            {
                "event": "plan",
                "sourceIndex": args.source_index,
                "targetIndex": args.target_index,
                "sourceDocuments": source_document_count,
                "plannedDocuments": len(docs_by_id),
                "plannedChunks": len(optimized_docs),
                "switchAlias": args.switch_alias,
                "reshapeChunks": args.reshape_chunks,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    if args.dry_run:
        return 0
    verify_embedding_provider(session, args)
    create_target_index(session, args)
    indexed = 0
    batch: list[dict[str, Any]] = []
    started = time.monotonic()
    for doc in optimized_docs:
        batch.append(doc)
        if len(batch) >= args.embed_batch_size:
            indexed += embed_and_bulk(session, args, batch)
            batch = []
            log_progress(indexed, len(optimized_docs), started)
    if batch:
        indexed += embed_and_bulk(session, args, batch)
        log_progress(indexed, len(optimized_docs), started)
    finalize_index(session, args)
    count = es_get(session, args.es_url, f"/{args.target_index}/_count", args.timeout)["count"]
    print(
        json.dumps(
            {
                "event": "complete",
                "targetIndex": args.target_index,
                "indexedChunks": indexed,
                "esCount": count,
                "readAlias": args.read_alias if args.switch_alias else None,
                "profileVersion": args.profile_version,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0


def validate_args(args: argparse.Namespace) -> None:
    if args.dimension <= 0:
        raise SystemExit("--dimension must be positive")
    if args.max_chunk_size < 400:
        raise SystemExit("--max-chunk-size is too small")
    if args.embed_batch_size <= 0 or args.bulk_batch_size <= 0:
        raise SystemExit("batch sizes must be positive")


def mapping_definition(dimension: int) -> dict[str, Any]:
    text_field = {
        "type": "text",
        "analyzer": "policy_text_analyzer",
        "search_analyzer": "policy_search_analyzer",
    }
    return {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "refresh_interval": "-1",
            "analysis": {
                "filter": {
                    "tax_synonym": {
                        "type": "synonym_graph",
                        "synonyms": [
                            "增值税税率, VAT税率, 增值税适用税率",
                            "企业所得税税率, 企业所得税基本税率, 企业所得税法定税率",
                            "征收率, 简易计税征收率",
                            "小规模纳税人, 小规模",
                            "一般纳税人, 增值税一般纳税人",
                            "现行, 当前, 目前",
                        ],
                    }
                },
                "analyzer": {
                    "policy_text_analyzer": {
                        "type": "custom",
                        "tokenizer": "ik_max_word",
                        "filter": ["lowercase"],
                    },
                    "policy_phrase_analyzer": {
                        "type": "custom",
                        "tokenizer": "ik_smart",
                        "filter": ["lowercase"],
                    },
                    "policy_search_analyzer": {
                        "type": "custom",
                        "tokenizer": "ik_smart",
                        "filter": ["lowercase", "tax_synonym"],
                    },
                },
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
                "title": {**text_field, "fields": {"keyword": {"type": "keyword"}}},
                "content": text_field,
                "snippet": text_field,
                "citationText": text_field,
                "generationText": text_field,
                "embeddingText": text_field,
                "section": {**text_field, "fields": {"keyword": {"type": "keyword"}}},
                "documentNo": {"type": "keyword"},
                "issuer": {"type": "keyword"},
                "taxType": {"type": "keyword"},
                "effectiveDate": {"type": "date"},
                "writtenDate": {"type": "date"},
                "validityStatus": {"type": "keyword"},
                "policyTopic": {"type": "keyword"},
                "applicableSubject": {"type": "keyword"},
                "authorityRank": {"type": "integer"},
                "currencyRank": {"type": "integer"},
                "retrievalBoostTags": {"type": "keyword"},
                "curated": {"type": "boolean"},
                "summaryType": {"type": "keyword"},
                "curationReviewStatus": {"type": "keyword"},
                "curationReviewedAt": {"type": "date"},
                "sourceDocumentIds": {"type": "keyword"},
                "sourceChunkIds": {"type": "keyword"},
                "sourceTitles": {"type": "keyword"},
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
                "chunkCount": {"type": "integer"},
            }
        },
    }


def load_source_documents(session: requests.Session, args: argparse.Namespace) -> dict[str, list[dict[str, Any]]]:
    docs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    body = {
        "size": args.scroll_size,
        "sort": [{"documentId": "asc"}, {"chunkIndex": "asc"}, {"chunkId": "asc"}],
        "_source": {"excludes": ["embedding"]},
        "query": {
            "bool": {
                "filter": [
                    {"term": {"tenantId": args.tenant_id}},
                    {"term": {"corpusId": DOMAIN}},
                    {"term": {"materialType": MATERIAL_TYPE}},
                    {"term": {"retrievalProfile": args.retrieval_profile}},
                    {"term": {"status": "ACTIVE"}},
                    {"term": {"visibility": "PUBLIC"}},
                ]
            }
        },
    }
    search_after = None
    while True:
        if search_after is not None:
            body["search_after"] = search_after
        response = session.post(
            f"{args.es_url.rstrip('/')}/{args.source_index}/_search",
            json=body,
            timeout=args.timeout,
        )
        response.raise_for_status()
        hits = response.json().get("hits", {}).get("hits", [])
        if not hits:
            break
        for hit in hits:
            source = hit.get("_source") or {}
            document_id = source.get("documentId")
            if document_id:
                docs[document_id].append(source)
        search_after = hits[-1].get("sort")
    return dict(docs)


def transform_document(document_id: str, chunks: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    ordered = sorted(chunks, key=lambda item: int(item.get("chunkIndex") or 0))
    base = ordered[0]
    texts = [single_line(item.get("content", "")) for item in ordered if single_line(item.get("content", ""))]
    chunk_specs = chunk_specs_for(document_id, ordered, texts, args)
    if not chunk_specs:
        chunk_specs = [{
            "base": base,
            "text": single_line(base.get("title", "")),
            "chunkId": f"{document_id}#c0000",
            "chunkIndex": 0,
            "charStart": 0,
            "charEnd": len(single_line(base.get("title", ""))),
        }]
    enriched = metadata_enrichment(base, " ".join(texts))
    result = []
    for index, spec in enumerate(chunk_specs):
        text = spec["text"]
        source_chunk = spec["base"]
        doc = copy_base_document(source_chunk, args)
        doc.update(enriched)
        doc["documentId"] = document_id
        doc["documentVersion"] = base.get("documentVersion") or sha256_text(document_id)
        doc["chunkId"] = spec["chunkId"]
        doc["chunkIndex"] = spec["chunkIndex"]
        doc["charStart"] = spec["charStart"]
        doc["charEnd"] = spec["charEnd"]
        doc["content"] = text
        doc["snippet"] = enriched_snippet(doc, text)
        doc["citationText"] = citation_text(doc, text)
        doc["generationText"] = generation_text(doc, text)
        doc["section"] = section_for(text, source_chunk)
        doc["chunkCount"] = len(chunk_specs)
        doc["parentSectionId"] = "sec-" + sha256_text(f"{document_id}|{doc['section']}")[:16]
        doc["contentHash"] = sha256_text(f"{doc['chunkId']}|{text}")
        doc["embeddingText"] = embedding_input(doc)
        doc["_embeddingInput"] = doc["embeddingText"]
        result.append(doc)
    return result


def chunk_specs_for(
    document_id: str,
    ordered: list[dict[str, Any]],
    texts: list[str],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    if args.reshape_chunks:
        return reshaped_chunk_specs(document_id, ordered[0], texts, args)
    specs = []
    for fallback_index, item in enumerate(ordered):
        text = single_line(item.get("content", ""))
        if not text:
            continue
        chunk_id = item.get("chunkId") or f"{document_id}#c{fallback_index:04d}"
        specs.append({
            "base": item,
            "text": text,
            "chunkId": chunk_id,
            "chunkIndex": int_value(item.get("chunkIndex"), fallback_index),
            "charStart": int_value(item.get("charStart"), 0),
            "charEnd": int_value(item.get("charEnd"), len(text)),
        })
    return specs


def reshaped_chunk_specs(
    document_id: str,
    base: dict[str, Any],
    texts: list[str],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    reshaped = reshape_chunks(texts, args)
    return [
        {
            "base": base,
            "text": text,
            "chunkId": f"{document_id}#d{index:04d}",
            "chunkIndex": index,
            "charStart": 0,
            "charEnd": len(text),
        }
        for index, text in enumerate(reshaped)
        if text
    ]


def reshape_chunks(texts: list[str], args: argparse.Namespace) -> list[str]:
    result: list[str] = []
    pending = ""
    for text in texts:
        if not text:
            continue
        if len(text) < args.min_standalone_chunk_size:
            pending = join_text(pending, text)
            continue
        if pending:
            text = join_text(pending, text)
            pending = ""
        for piece in split_long_text(text, args.max_chunk_size):
            if piece:
                result.append(piece)
    if pending:
        if result:
            result[-1] = join_text(result[-1], pending)
        else:
            result.append(pending)
    return result


def split_long_text(text: str, max_size: int) -> list[str]:
    if len(text) <= max_size:
        return [text]
    parts = [part for part in SENTENCE_SPLIT.split(text) if part]
    result: list[str] = []
    current = ""
    for part in parts:
        if len(current) + len(part) <= max_size:
            current += part
            continue
        if current:
            result.append(current.strip())
        if len(part) > max_size:
            result.extend(part[i : i + max_size].strip() for i in range(0, len(part), max_size))
            current = ""
        else:
            current = part
    if current:
        result.append(current.strip())
    return result


def metadata_enrichment(base: dict[str, Any], full_text: str) -> dict[str, Any]:
    title = str(base.get("title") or "")
    tax_types = string_list(base.get("taxType"))
    labels = string_list(base.get("labels"))
    combined = f"{title} {full_text}"
    policy_topic = infer_policy_topic(combined)
    subject = infer_subject(combined)
    validity = str(base.get("validityStatus") or "UNKNOWN")
    effect_level = str(base.get("effectLevel") or "")
    return {
        "taxType": tax_types,
        "labels": labels,
        "policyTopic": policy_topic,
        "applicableSubject": subject,
        "authorityRank": authority_rank(effect_level),
        "currencyRank": currency_rank(validity, str(base.get("effectiveDate") or base.get("writtenDate") or "")),
        "retrievalBoostTags": boost_tags(tax_types, labels, policy_topic, subject, validity, effect_level),
        "validityStatus": validity,
        "effectLevel": effect_level,
    }


def copy_base_document(base: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    fields = [
        "documentNo",
        "issuer",
        "effectiveDate",
        "writtenDate",
        "aclRef",
        "aclVersion",
        "visibility",
        "departmentIds",
        "roleIds",
        "userIds",
        "attributeKeys",
        "sourceUri",
        "sourceUrl",
        "channel",
        "sourceRowNumber",
    ]
    doc = {field: base.get(field) for field in fields if field in base}
    doc.update(
        {
            "tenantId": args.tenant_id,
            "corpusId": DOMAIN,
            "domain": DOMAIN,
            "materialType": MATERIAL_TYPE,
            "retrievalProfile": args.retrieval_profile,
            "profileVersion": args.profile_version,
            "title": base.get("title", ""),
            "aclRef": base.get("aclRef") or f"public:{DOMAIN}",
            "aclVersion": base.get("aclVersion") or "public-v1",
            "visibility": base.get("visibility") or "PUBLIC",
            "departmentIds": base.get("departmentIds") or [],
            "roleIds": base.get("roleIds") or [],
            "userIds": base.get("userIds") or [],
            "attributeKeys": unique((base.get("attributeKeys") or []) + ["tax-policy-dataopt"]),
            "status": "ACTIVE",
            "chunkStrategy": CHUNK_STRATEGY,
            "chunkVersion": CHUNK_VERSION,
            "indexVersion": args.profile_version,
            "sourceDataset": base.get("sourceDataset") or SOURCE_DATASET,
            "sourceCrawledAt": base.get("sourceCrawledAt") or "2026-02-27",
            "indexedAt": now_iso(),
            "curated": False,
        }
    )
    return doc


def curated_summary_documents(args: argparse.Namespace) -> list[dict[str, Any]]:
    summaries = [
        {
            "documentId": "tax-curated-vat-rates-current",
            "title": "现行增值税税率当前口径汇总",
            "taxType": ["税收政策-增值税"],
            "policyTopic": "tax_rate",
            "applicableSubject": ["一般纳税人", "进口货物", "应税交易"],
            "sourceDocumentIds": [
                "tax-ed86dea9630deb65973c6bb2",
                "tax-31d17b20b37475140af18a93",
            ],
            "sourceChunkIds": [
                "tax-ed86dea9630deb65973c6bb2#c0007",
                "tax-31d17b20b37475140af18a93#c0000",
            ],
            "sourceTitles": [
                "中华人民共和国增值税法",
                "财政部 税务总局 海关总署关于深化增值税改革有关政策的公告",
            ],
            "content": (
                "现行增值税税率当前口径汇总：一般计税场景下，销售货物、加工修理修配服务、"
                "有形动产租赁服务和进口货物通常适用 13%；交通运输、邮政、基础电信、建筑、"
                "不动产租赁服务、销售不动产、转让土地使用权以及农产品、食用植物油、食用盐等"
                "通常适用 9%；销售服务、无形资产等通常适用 6%；出口货物和跨境应税行为可适用"
                "零税率。汇总依据包括《中华人民共和国增值税法》第十条及 2019 年深化增值税改革"
                "有关政策公告。"
            ),
        },
        {
            "documentId": "tax-curated-vat-small-scale-current",
            "title": "小规模纳税人增值税征收率当前口径汇总",
            "taxType": ["税收政策-增值税"],
            "policyTopic": "collection_rate",
            "applicableSubject": ["小规模纳税人"],
            "sourceDocumentIds": [
                "tax-986604ed425418fdaff65f6e",
                "tax-fbd2a31b07bc3ce308d0dd47",
            ],
            "sourceChunkIds": [
                "tax-986604ed425418fdaff65f6e#c0001",
                "tax-fbd2a31b07bc3ce308d0dd47#c0000",
            ],
            "sourceTitles": [
                "中华人民共和国增值税暂行条例",
                "财政部 税务总局关于增值税小规模纳税人减免增值税政策的公告",
            ],
            "content": (
                "小规模纳税人增值税征收率当前口径汇总：法定征收率为 3%，国务院另有规定的除外；"
                "自 2023 年 8 月 1 日至 2027 年 12 月 31 日，适用 3% 征收率的应税销售收入"
                "减按 1% 征收率征收增值税。"
            ),
        },
        {
            "documentId": "tax-curated-eit-rates-current",
            "title": "企业所得税税率当前口径汇总",
            "taxType": ["税收政策-企业所得税"],
            "policyTopic": "tax_rate",
            "applicableSubject": ["居民企业", "非居民企业", "小型微利企业", "高新技术企业"],
            "sourceDocumentIds": [
                "tax-0d5b04990b508ca61326d670",
                "tax-f186c1cf633380d4a6b6cd49",
                "tax-f4ede0cfeb676756c93a4866",
            ],
            "sourceChunkIds": [
                "tax-0d5b04990b508ca61326d670#c0008",
                "tax-f186c1cf633380d4a6b6cd49#c0000",
                "tax-f4ede0cfeb676756c93a4866#c0000",
            ],
            "sourceTitles": [
                "中华人民共和国企业所得税法",
                "财政部 国家税务总局关于小型微利企业所得税优惠政策的通知",
                "财政部 税务总局关于扩大小型微利企业所得税优惠政策范围的通知",
            ],
            "content": (
                "企业所得税税率当前口径汇总：企业所得税法规定基本税率为 25%；非居民企业在中国境内"
                "未设机构、场所，或者虽设机构、场所但取得所得与其机构、场所没有实际联系的，适用"
                "20% 税率；符合条件的小型微利企业、高新技术企业等可按现行优惠政策适用优惠税率。"
            ),
        },
    ]
    docs: list[dict[str, Any]] = []
    for index, summary in enumerate(summaries):
        document_id = summary["documentId"]
        doc = {
            "tenantId": args.tenant_id,
            "corpusId": DOMAIN,
            "domain": DOMAIN,
            "materialType": MATERIAL_TYPE,
            "retrievalProfile": args.retrieval_profile,
            "profileVersion": args.profile_version,
            "documentId": document_id,
            "documentVersion": sha256_text(summary["content"]),
            "chunkId": f"{document_id}#c0000",
            "chunkIndex": 0,
            "charStart": 0,
            "charEnd": len(summary["content"]),
            "title": summary["title"],
            "content": summary["content"],
            "snippet": "当前口径汇总 " + summary["content"][:260],
            "citationText": complete_boundary_text(summary["content"], CITATION_TEXT_LIMIT),
            "generationText": complete_boundary_text(summary["content"], GENERATION_TEXT_LIMIT),
            "section": "当前口径汇总",
            "documentNo": "",
            "issuer": "system-curated",
            "taxType": summary["taxType"],
            "effectiveDate": "2026-07-10",
            "writtenDate": "2026-07-10",
            "validityStatus": "ACTIVE",
            "policyTopic": summary["policyTopic"],
            "applicableSubject": summary["applicableSubject"],
            "authorityRank": 95,
            "currencyRank": 100,
            "retrievalBoostTags": unique(summary["taxType"] + summary["applicableSubject"] + ["当前", "现行", summary["policyTopic"]]),
            "curated": True,
            "summaryType": "current_answer_summary",
            "curationReviewStatus": "NEEDS_HUMAN_REVIEW",
            "curationReviewedAt": None,
            "sourceDocumentIds": summary["sourceDocumentIds"],
            "sourceChunkIds": summary["sourceChunkIds"],
            "sourceTitles": summary["sourceTitles"],
            "aclRef": f"public:{DOMAIN}",
            "aclVersion": "public-v1",
            "visibility": "PUBLIC",
            "departmentIds": [],
            "roleIds": [],
            "userIds": [],
            "attributeKeys": ["tax-policy-dataopt", "curated-summary"],
            "status": "ACTIVE",
            "chunkStrategy": CHUNK_STRATEGY,
            "chunkVersion": CHUNK_VERSION,
            "parentSectionId": "sec-curated-current",
            "indexVersion": args.profile_version,
            "contentHash": sha256_text(f"{document_id}|{summary['content']}"),
            "sourceDataset": SUMMARY_DATASET,
            "sourceCrawledAt": "2026-07-10",
            "sourceRowNumber": index,
            "sourceUri": "",
            "sourceUrl": "",
            "channel": "curated",
            "effectLevel": "当前口径汇总",
            "labels": unique(summary["taxType"] + ["当前口径", "高频问答"]),
            "indexedAt": now_iso(),
            "chunkCount": 1,
        }
        doc["embeddingText"] = embedding_input(doc)
        doc["_embeddingInput"] = doc["embeddingText"]
        docs.append(doc)
    return docs


def enriched_snippet(doc: dict[str, Any], text: str) -> str:
    tags = [
        f"税种:{'、'.join(string_list(doc.get('taxType')))}",
        f"效力:{doc.get('validityStatus')}",
        f"层级:{doc.get('effectLevel')}",
        f"主题:{doc.get('policyTopic')}",
        f"对象:{'、'.join(string_list(doc.get('applicableSubject')))}",
    ]
    return f"[{' | '.join(tag for tag in tags if not tag.endswith(':'))}] {single_line(text)[:260]}"


def complete_boundary_text(text: Any, limit: int) -> str:
    value = single_line(text)
    if len(value) <= limit:
        return value
    clipped = value[:limit]
    boundary = last_sentence_boundary(clipped)
    if boundary >= max(40, limit // 2):
        return clipped[:boundary].strip()
    return clipped.strip()


def last_sentence_boundary(text: str) -> int:
    boundary = max(text.rfind(marker) for marker in ("。", "；", ";", "！", "？"))
    return boundary + 1 if boundary >= 0 else -1


def citation_text(doc: dict[str, Any], text: str) -> str:
    return complete_boundary_text(text, CITATION_TEXT_LIMIT)


def generation_text(doc: dict[str, Any], text: str) -> str:
    return complete_boundary_text(text, GENERATION_TEXT_LIMIT)


def embedding_input(doc: dict[str, Any]) -> str:
    body = doc.get("generationText") or doc.get("content") or ""
    parts = [
        f"标题：{doc.get('title', '')}",
        f"文号：{doc.get('documentNo', '')}",
        f"发文机关：{doc.get('issuer', '')}",
        f"资料域：税务政策",
        f"效力状态：{doc.get('validityStatus', '')}",
        f"政策层级：{doc.get('effectLevel', '')}",
        f"税种：{'、'.join(string_list(doc.get('taxType')))}",
        f"主题：{doc.get('policyTopic', '')}",
        f"适用对象：{'、'.join(string_list(doc.get('applicableSubject')))}",
        f"检索标签：{'、'.join(string_list(doc.get('retrievalBoostTags')))}",
        f"来源文档：{'、'.join(string_list(doc.get('sourceTitles')))}",
        f"章节：{doc.get('section', '')}",
        f"正文：{body}",
    ]
    return complete_boundary_text(
        "\n".join(part for part in parts if not part.endswith("：")),
        EMBEDDING_TEXT_LIMIT,
    )


def infer_policy_topic(text: str) -> str:
    if "征收率" in text or "简易计税" in text:
        return "collection_rate"
    if "税率" in text or RATE_PATTERN.search(text):
        return "tax_rate"
    if "发票" in text:
        return "invoice"
    if "申报" in text or "预缴" in text:
        return "declaration"
    if "免征" in text or "减按" in text or "优惠" in text:
        return "tax_incentive"
    return "general"


def infer_subject(text: str) -> list[str]:
    values = []
    if "一般纳税人" in text:
        values.append("一般纳税人")
    if "小规模纳税人" in text or "小规模" in text:
        values.append("小规模纳税人")
    if "居民企业" in text:
        values.append("居民企业")
    if "非居民企业" in text:
        values.append("非居民企业")
    if "小型微利企业" in text:
        values.append("小型微利企业")
    if "高新技术企业" in text:
        values.append("高新技术企业")
    return values or ["通用"]


def authority_rank(effect_level: str) -> int:
    return {
        "法律": 100,
        "行政法规": 90,
        "国务院文件": 85,
        "税务部门规章": 80,
        "财税文件": 70,
        "税务规范性文件": 65,
        "工作通知": 45,
        "其他文件": 35,
        "当前口径汇总": 95,
    }.get(effect_level, 30)


def currency_rank(validity: str, date_value: str) -> int:
    base = {
        "ACTIVE": 100,
        "PENDING": 20,
        "UNKNOWN": 60,
        "AMENDED": 35,
        "EXPIRED": 5,
    }.get(validity, 40)
    year = parse_year(date_value)
    if year and validity == "UNKNOWN":
        base += max(0, min(20, year - 2010))
    return min(base, 100)


def boost_tags(
    tax_types: list[str],
    labels: list[str],
    policy_topic: str,
    subject: list[str],
    validity: str,
    effect_level: str,
) -> list[str]:
    values = tax_types + labels + subject + [policy_topic, validity, effect_level]
    if validity == "ACTIVE":
        values.extend(["当前", "现行"])
    return unique([value for value in values if value])


def section_for(text: str, base: dict[str, Any]) -> str:
    section = single_line(base.get("section", ""))
    if section and section != "正文":
        return section[:80]
    first = text[:80]
    if "税率" in first:
        return "税率"
    if "征收率" in first:
        return "征收率"
    return section or "正文"


def verify_embedding_provider(session: requests.Session, args: argparse.Namespace) -> None:
    vectors, dim = embed_texts(session, args, ["增值税税率"])
    if dim != args.dimension or len(vectors[0]) != args.dimension:
        raise SystemExit(f"embedding dimension mismatch: provider={dim}, expected={args.dimension}")


def create_target_index(session: requests.Session, args: argparse.Namespace) -> None:
    if index_exists(session, args.es_url, args.target_index, args.timeout):
        if not args.recreate:
            raise SystemExit(f"target index exists: {args.target_index}; add --recreate to rebuild")
        es_delete(session, args.es_url, f"/{args.target_index}", args.timeout)
    es_put(session, args.es_url, f"/{args.target_index}", mapping_definition(args.dimension), args.timeout)
    print(json.dumps({"event": "index_created", "index": args.target_index}, ensure_ascii=False), flush=True)


def embed_and_bulk(session: requests.Session, args: argparse.Namespace, docs: list[dict[str, Any]]) -> int:
    vectors, dim = embed_texts(session, args, [doc["_embeddingInput"] for doc in docs])
    if dim != args.dimension:
        raise RuntimeError(f"embedding dimension mismatch: provider={dim}, expected={args.dimension}")
    for doc, vector in zip(docs, vectors, strict=True):
        if len(vector) != args.dimension:
            raise RuntimeError("embedding vector length mismatch")
        doc["embedding"] = vector
        doc.pop("_embeddingInput", None)
    for start in range(0, len(docs), args.bulk_batch_size):
        bulk_index(session, args, docs[start : start + args.bulk_batch_size])
    return len(docs)


def embed_texts(session: requests.Session, args: argparse.Namespace, texts: list[str]) -> tuple[list[list[float]], int]:
    response = session.post(
        f"{args.embedding_url.rstrip('/')}/embed",
        json={"texts": texts},
        timeout=args.timeout,
    )
    response.raise_for_status()
    payload = response.json()
    vectors = payload.get("vectors")
    dim = payload.get("dim")
    if not isinstance(dim, int) or not isinstance(vectors, list) or len(vectors) != len(texts):
        raise RuntimeError("embedding provider returned invalid payload")
    normalized = []
    for vector in vectors:
        values = [float(value) for value in vector]
        if any(not math.isfinite(value) for value in values):
            raise RuntimeError("embedding provider returned non-finite value")
        normalized.append(values)
    return normalized, dim


def bulk_index(session: requests.Session, args: argparse.Namespace, docs: list[dict[str, Any]]) -> None:
    lines = []
    for doc in docs:
        lines.append(json.dumps({"index": {"_index": args.target_index, "_id": doc["chunkId"]}}, ensure_ascii=False))
        lines.append(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
    response = session.post(
        f"{args.es_url.rstrip('/')}/_bulk",
        data=("\n".join(lines) + "\n").encode("utf-8"),
        headers={"Content-Type": "application/x-ndjson"},
        timeout=args.timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        first_error = next((item for item in payload.get("items", []) if item.get("index", {}).get("error")), None)
        raise RuntimeError(f"bulk index failed: {json.dumps(first_error, ensure_ascii=False)[:1200]}")


def finalize_index(session: requests.Session, args: argparse.Namespace) -> None:
    es_put(session, args.es_url, f"/{args.target_index}/_settings", {"index": {"refresh_interval": "1s"}}, args.timeout)
    es_post(session, args.es_url, f"/{args.target_index}/_refresh", None, args.timeout)
    if not args.switch_alias:
        return
    actions = [
        {"remove": {"index": "*", "alias": args.read_alias, "must_exist": False}},
        {"remove": {"index": "*", "alias": args.write_alias, "must_exist": False}},
        {"add": {"index": args.target_index, "alias": args.read_alias}},
        {"add": {"index": args.target_index, "alias": args.write_alias, "is_write_index": True}},
    ]
    es_post(session, args.es_url, "/_aliases", {"actions": actions}, args.timeout)


def log_progress(indexed: int, total: int, started: float) -> None:
    if indexed == total or indexed % 512 == 0:
        print(
            json.dumps(
                {"event": "progress", "indexed": indexed, "total": total, "elapsedSec": round(time.monotonic() - started, 1)},
                ensure_ascii=False,
            ),
            flush=True,
        )


def index_exists(session: requests.Session, es_url: str, index: str, timeout: int) -> bool:
    response = session.head(f"{es_url.rstrip('/')}/{index}", timeout=timeout)
    if response.status_code == 404:
        return False
    response.raise_for_status()
    return True


def es_get(session: requests.Session, es_url: str, path: str, timeout: int) -> dict[str, Any]:
    response = session.get(es_url.rstrip("/") + path, timeout=timeout)
    response.raise_for_status()
    return response.json()


def es_put(session: requests.Session, es_url: str, path: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    response = session.put(es_url.rstrip("/") + path, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def es_post(session: requests.Session, es_url: str, path: str, payload: dict[str, Any] | None, timeout: int) -> dict[str, Any]:
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


def string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return unique(str(item).strip() for item in value if str(item).strip())
    text = str(value).strip()
    if not text:
        return []
    return unique(part.strip() for part in re.split(r"[，,、;；/|]+", text) if part.strip())


def unique(values: Any) -> list[str]:
    result = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def join_text(left: str, right: str) -> str:
    if not left:
        return right
    if not right:
        return left
    return f"{left}\n{right}"


def single_line(value: Any) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_year(value: str) -> int | None:
    match = re.match(r"^(\d{4})", value or "")
    if not match:
        return None
    return int(match.group(1))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    sys.exit(main())
