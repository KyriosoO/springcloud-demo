#!/usr/bin/env python
"""Run gold-query retrieval checks against a tax-policy ES index or alias."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import requests


DEFAULT_GOLD_PATH = Path("scripts/chinatax_v2/tax_policy_gold_queries.v1.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--es-query-url", default="http://127.0.0.1:9201")
    parser.add_argument("--embedding-url", default="http://127.0.0.1:8908")
    parser.add_argument("--index", default="agent-doc-tax-policy-v2-read")
    parser.add_argument("--gold-path", type=Path, default=DEFAULT_GOLD_PATH)
    parser.add_argument("--tenant-id", default="tenant-local")
    parser.add_argument("--profile-version", default=None)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session = requests.Session()
    gold = read_json(args.gold_path)
    profile_version = args.profile_version or gold.get("profileVersion")
    cases = gold.get("cases") or []
    started = time.time()
    results = []
    expected_cases = 0
    hit_cases = 0
    reciprocal_ranks: list[float] = []
    for case in cases:
        query = require_text(case.get("query"), "case.query")
        expected = [value for value in case.get("expectedDocumentIds") or [] if value]
        top_k = int(case.get("topK") or args.top_k)
        vector = embed(session, args, query)
        response = hybrid_search(session, args, gold, profile_version, query, vector, top_k)
        hits = response.get("hits") or []
        hit_ids = unique([hit.get("documentId") for hit in hits])
        rank = first_rank(hit_ids, expected)
        passed = rank is not None
        if expected:
            expected_cases += 1
            if passed:
                hit_cases += 1
                reciprocal_ranks.append(1.0 / rank)
            else:
                reciprocal_ranks.append(0.0)
        results.append(
            {
                "caseId": case.get("caseId"),
                "query": query,
                "caseType": case.get("caseType"),
                "expectedDocumentIds": expected,
                "hitDocumentIds": hit_ids[:top_k],
                "firstExpectedRank": rank,
                "passed": passed if expected else None,
                "topTitles": [
                    {
                        "documentId": hit.get("documentId"),
                        "chunkId": hit.get("chunkId"),
                        "title": hit.get("title"),
                        "score": hit.get("score"),
                        "rrfScore": hit.get("rrfScore"),
                    }
                    for hit in hits[: min(top_k, 5)]
                ],
            }
        )
    hit_rate = 0.0 if expected_cases == 0 else hit_cases / expected_cases
    mrr = 0.0 if not reciprocal_ranks else sum(reciprocal_ranks) / len(reciprocal_ranks)
    report = {
        "index": args.index,
        "goldSetVersion": gold.get("goldSetVersion"),
        "profileVersion": profile_version,
        "caseCount": len(cases),
        "expectedCaseCount": expected_cases,
        "expectedHitCount": hit_cases,
        "topKHitRate": round(hit_rate, 4),
        "mrr": round(mrr, 4),
        "elapsedSec": round(time.time() - started, 2),
        "results": results,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0 if hit_cases == expected_cases else 2


def hybrid_search(
    session: requests.Session,
    args: argparse.Namespace,
    gold: dict[str, Any],
    profile_version: str,
    query: str,
    vector: list[float],
    top_k: int,
) -> dict[str, Any]:
    body = {
        "queryText": query,
        "domain": gold.get("domain", "tax_policy"),
        "materialType": gold.get("materialType", "tax_policy"),
        "retrievalProfile": gold.get("retrievalProfile", "tax_policy_v2_default"),
        "profileVersion": profile_version,
        "indexAlias": args.index,
        "filters": acl_filters(args.tenant_id),
        "embeddingField": "embedding",
        "topK": top_k,
        "rrfK": 60,
        "maxChunksPerDocument": 2,
        "sourceExcludes": ["embedding"],
        "channelWeights": {
            "BM25": 1.0,
            "EXACT": 1.8,
            "PHRASE": 1.4,
            "DENSE_VECTOR": 1.0,
        },
        "channels": [
            {"channel": "BM25", "queryDsl": bm25_dsl(query), "k": 40, "numCandidates": 200},
            {"channel": "EXACT", "queryDsl": exact_dsl(query), "k": 20, "numCandidates": 100},
            {"channel": "PHRASE", "queryDsl": phrase_dsl(query), "k": 30, "numCandidates": 100},
            {
                "channel": "DENSE_VECTOR",
                "queryVector": vector,
                "embeddingField": "embedding",
                "k": 40,
                "numCandidates": 200,
            },
        ],
    }
    response = session.post(
        f"{args.es_query_url.rstrip('/')}/es/indexes/{args.index}/hybrid-search",
        json=body,
        timeout=args.timeout,
    )
    response.raise_for_status()
    return response.json()


def acl_filters(tenant_id: str) -> dict[str, Any]:
    return {
        "bool": {
            "filter": [
                {"term": {"tenantId": tenant_id}},
                {"term": {"corpusId": "tax_policy"}},
                {"term": {"materialType": "tax_policy"}},
                {"term": {"retrievalProfile": "tax_policy_v2_default"}},
                {"term": {"status": "ACTIVE"}},
                {"term": {"visibility": "PUBLIC"}},
            ]
        }
    }


def bm25_dsl(query: str) -> dict[str, Any]:
    return {
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["title^2", "content", "snippet", "section"],
                "type": "best_fields",
            }
        }
    }


def phrase_dsl(query: str) -> dict[str, Any]:
    return {
        "query": {
            "multi_match": {
                "query": query,
                "type": "phrase",
                "slop": 2,
                "fields": ["title^2", "content", "snippet", "section"],
            }
        }
    }


def exact_dsl(query: str) -> dict[str, Any]:
    return {
        "query": {
            "bool": {
                "should": [
                    {"term": {"title.keyword": query}},
                    {"term": {"documentNo": query}},
                    {"term": {"issuer": query}},
                    {"term": {"section.keyword": query}},
                    {"term": {"taxType": query}},
                ],
                "minimum_should_match": 1,
            }
        }
    }


def embed(session: requests.Session, args: argparse.Namespace, text: str) -> list[float]:
    response = session.post(
        f"{args.embedding_url.rstrip('/')}/embed",
        json={"texts": [text]},
        timeout=args.timeout,
    )
    response.raise_for_status()
    payload = response.json()
    vectors = payload.get("vectors")
    if not isinstance(vectors, list) or not vectors:
        raise RuntimeError("embedding provider returned no vector")
    vector = [float(value) for value in vectors[0]]
    if not vector or any(not math.isfinite(value) for value in vector):
        raise RuntimeError("embedding provider returned invalid vector")
    return vector


def first_rank(hit_ids: list[str], expected: list[str]) -> int | None:
    if not expected:
        return None
    expected_set = set(expected)
    for index, document_id in enumerate(hit_ids, start=1):
        if document_id in expected_set:
            return index
    return None


def unique(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        if isinstance(value, str) and value and value not in result:
            result.append(value)
    return result


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def require_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be blank")
    return value.strip()


if __name__ == "__main__":
    sys.exit(main())
