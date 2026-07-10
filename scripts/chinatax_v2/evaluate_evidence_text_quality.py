#!/usr/bin/env python
"""Compare current snippet text with proposed citation/generation evidence text.

This script reads existing ES documents and simulates the derived text fields
added by build_chinatax_dataopt_index.py. It does not write to ES.
"""

from __future__ import annotations

import argparse
import json
import re
from statistics import mean
from typing import Any

import requests


DEFAULT_INDEX = "agent-doc-tax-policy-v2-read"
DOMAIN = "tax_policy"
MATERIAL_TYPE = "tax_policy"
DEFAULT_PROFILE = "tax_policy_v2_default"
CITATION_TEXT_LIMIT = 500
GENERATION_TEXT_LIMIT = 1600
SENTENCE_ENDINGS = ("。", "；", ";", "！", "？")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--es-url", default="http://127.0.0.1:9200")
    parser.add_argument("--index", default=DEFAULT_INDEX)
    parser.add_argument("--tenant-id", default="tenant-local")
    parser.add_argument("--retrieval-profile", default=DEFAULT_PROFILE)
    parser.add_argument("--size", type=int, default=200)
    parser.add_argument("--timeout", type=int, default=30)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    docs = load_documents(args)
    metrics = evaluate(docs)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


def load_documents(args: argparse.Namespace) -> list[dict[str, Any]]:
    body = {
        "size": args.size,
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
    response = requests.post(
        f"{args.es_url.rstrip('/')}/{args.index}/_search",
        json=body,
        timeout=args.timeout,
    )
    response.raise_for_status()
    hits = response.json().get("hits", {}).get("hits", [])
    return [hit.get("_source") or {} for hit in hits]


def evaluate(docs: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for doc in docs:
        content = single_line(doc.get("content"))
        snippet = single_line(doc.get("snippet"))
        citation = complete_boundary_text(content, CITATION_TEXT_LIMIT)
        generation = complete_boundary_text(content, GENERATION_TEXT_LIMIT)
        rows.append(
            {
                "snippetLength": len(snippet),
                "citationLength": len(citation),
                "generationLength": len(generation),
                "snippetComplete": complete_sentence(snippet),
                "citationComplete": complete_sentence(citation),
                "generationComplete": complete_sentence(generation),
                "snippetHasMetadataPrefix": snippet.startswith("["),
                "citationEmpty": not citation,
            }
        )
    count = len(rows)
    if count == 0:
        return {"documents": 0}
    return {
        "documents": count,
        "currentSnippet": {
            "avgChars": round(avg(row["snippetLength"] for row in rows), 2),
            "completeSentenceRatio": ratio(row["snippetComplete"] for row in rows),
            "metadataPrefixRatio": ratio(row["snippetHasMetadataPrefix"] for row in rows),
        },
        "proposedCitationText": {
            "avgChars": round(avg(row["citationLength"] for row in rows), 2),
            "completeSentenceRatio": ratio(row["citationComplete"] for row in rows),
            "emptyRatio": ratio(row["citationEmpty"] for row in rows),
        },
        "proposedGenerationText": {
            "avgChars": round(avg(row["generationLength"] for row in rows), 2),
            "completeSentenceRatio": ratio(row["generationComplete"] for row in rows),
        },
    }


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
    boundary = max(text.rfind(marker) for marker in SENTENCE_ENDINGS)
    return boundary + 1 if boundary >= 0 else -1


def complete_sentence(text: str) -> bool:
    value = single_line(text)
    return bool(value) and value.endswith(SENTENCE_ENDINGS)


def single_line(value: Any) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def avg(values: Any) -> float:
    items = list(values)
    return mean(items) if items else 0.0


def ratio(values: Any) -> float:
    items = list(values)
    return round(sum(1 for value in items if value) / len(items), 4) if items else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
