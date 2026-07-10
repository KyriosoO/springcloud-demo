#!/usr/bin/env python
"""Validate curated tax-policy summary chunks against their source chunks."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--es-url", default="http://127.0.0.1:9200")
    parser.add_argument("--target-index", default="agent-doc-tax-policy-v3-dataopt-read")
    parser.add_argument("--source-index", default="agent-doc-tax-policy-v2-read")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session = requests.Session()
    started = time.time()
    curated_docs = load_curated_docs(session, args)
    results = [validate_doc(session, args, doc) for doc in curated_docs]
    missing_refs = sum(len(item["missingSourceChunkIds"]) for item in results)
    title_mismatches = sum(len(item["titleMismatches"]) for item in results)
    report = {
        "targetIndex": args.target_index,
        "sourceIndex": args.source_index,
        "curatedDocumentCount": len(curated_docs),
        "sourceReferenceCount": sum(len(item["sourceChunkIds"]) for item in results),
        "missingSourceReferenceCount": missing_refs,
        "titleMismatchCount": title_mismatches,
        "passed": len(curated_docs) > 0 and missing_refs == 0 and title_mismatches == 0,
        "elapsedSec": round(time.time() - started, 2),
        "results": results,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0 if report["passed"] else 2


def load_curated_docs(session: requests.Session, args: argparse.Namespace) -> list[dict[str, Any]]:
    body = {
        "size": 100,
        "query": {"term": {"curated": True}},
        "_source": {
            "includes": [
                "documentId",
                "title",
                "curationReviewStatus",
                "sourceDocumentIds",
                "sourceChunkIds",
                "sourceTitles",
            ]
        },
    }
    response = session.post(
        f"{args.es_url.rstrip('/')}/{args.target_index}/_search",
        json=body,
        timeout=args.timeout,
    )
    response.raise_for_status()
    hits = response.json().get("hits", {}).get("hits", [])
    return [hit.get("_source") or {} for hit in hits]


def validate_doc(session: requests.Session, args: argparse.Namespace, doc: dict[str, Any]) -> dict[str, Any]:
    source_chunk_ids = string_list(doc.get("sourceChunkIds"))
    expected_titles = string_list(doc.get("sourceTitles"))
    source_chunks = load_source_chunks(session, args, source_chunk_ids)
    missing = [chunk_id for chunk_id in source_chunk_ids if chunk_id not in source_chunks]
    title_mismatches = []
    for index, chunk_id in enumerate(source_chunk_ids):
        source = source_chunks.get(chunk_id)
        if source is None:
            continue
        expected_title = expected_titles[index] if index < len(expected_titles) else ""
        actual_title = str(source.get("title") or "")
        if expected_title and expected_title != actual_title:
            title_mismatches.append(
                {
                    "chunkId": chunk_id,
                    "expectedTitle": expected_title,
                    "actualTitle": actual_title,
                }
            )
    return {
        "documentId": doc.get("documentId"),
        "title": doc.get("title"),
        "curationReviewStatus": doc.get("curationReviewStatus"),
        "sourceChunkIds": source_chunk_ids,
        "missingSourceChunkIds": missing,
        "titleMismatches": title_mismatches,
        "sourceTitles": [
            source_chunks[chunk_id].get("title")
            for chunk_id in source_chunk_ids
            if chunk_id in source_chunks
        ],
    }


def load_source_chunks(
    session: requests.Session,
    args: argparse.Namespace,
    chunk_ids: list[str],
) -> dict[str, dict[str, Any]]:
    if not chunk_ids:
        return {}
    body = {
        "size": len(chunk_ids),
        "query": {"terms": {"chunkId": chunk_ids}},
        "_source": {"includes": ["documentId", "chunkId", "title", "content", "validityStatus"]},
    }
    response = session.post(
        f"{args.es_url.rstrip('/')}/{args.source_index}/_search",
        json=body,
        timeout=args.timeout,
    )
    response.raise_for_status()
    hits = response.json().get("hits", {}).get("hits", [])
    return {
        (hit.get("_source") or {}).get("chunkId"): hit.get("_source") or {}
        for hit in hits
        if (hit.get("_source") or {}).get("chunkId")
    }


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if value is None:
        return []
    text = str(value)
    return [text] if text else []


if __name__ == "__main__":
    sys.exit(main())
