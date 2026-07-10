#!/usr/bin/env python
"""Build a read-only cutover readiness report for the data-optimized index."""

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
    parser.add_argument("--current-read-alias", default="agent-doc-tax-policy-v2-read")
    parser.add_argument("--candidate-read-alias", default="agent-doc-tax-policy-v3-dataopt-read")
    parser.add_argument("--gold-report", type=Path, default=Path(".tmp/chinatax-v2/dataopt-alias-gold-report.json"))
    parser.add_argument("--source-report", type=Path, default=Path(".tmp/chinatax-v2/curated-source-report.json"))
    parser.add_argument("--minimum-hit-rate", type=float, default=1.0)
    parser.add_argument("--minimum-mrr", type=float, default=0.85)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--output", type=Path, default=Path(".tmp/chinatax-v2/dataopt-cutover-readiness.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session = requests.Session()
    started = time.time()
    gold = read_json(args.gold_report)
    source = read_json(args.source_report)
    alias_state = alias_state_for(session, args)
    checks = [
        check(
            "candidate_gold_hit_rate",
            float(gold.get("topKHitRate") or 0) >= args.minimum_hit_rate,
            f"topKHitRate={gold.get('topKHitRate')} minimum={args.minimum_hit_rate}",
        ),
        check(
            "candidate_gold_mrr",
            float(gold.get("mrr") or 0) >= args.minimum_mrr,
            f"mrr={gold.get('mrr')} minimum={args.minimum_mrr}",
        ),
        check(
            "curated_sources_exist",
            bool(source.get("passed")),
            (
                f"missing={source.get('missingSourceReferenceCount')} "
                f"titleMismatch={source.get('titleMismatchCount')}"
            ),
        ),
        check(
            "current_alias_resolved",
            bool(alias_state.get("currentIndex")),
            f"currentIndex={alias_state.get('currentIndex')}",
        ),
        check(
            "candidate_alias_resolved",
            bool(alias_state.get("candidateIndex")),
            f"candidateIndex={alias_state.get('candidateIndex')}",
        ),
        check(
            "candidate_differs_from_current",
            alias_state.get("currentIndex") != alias_state.get("candidateIndex"),
            (
                f"currentIndex={alias_state.get('currentIndex')} "
                f"candidateIndex={alias_state.get('candidateIndex')}"
            ),
        ),
    ]
    ready = all(item["passed"] for item in checks)
    report = {
        "readyForManualCutover": ready,
        "currentReadAlias": args.current_read_alias,
        "candidateReadAlias": args.candidate_read_alias,
        "currentIndex": alias_state.get("currentIndex"),
        "candidateIndex": alias_state.get("candidateIndex"),
        "rollbackTargetIndex": alias_state.get("currentIndex"),
        "goldSetVersion": gold.get("goldSetVersion"),
        "candidateTopKHitRate": gold.get("topKHitRate"),
        "candidateMrr": gold.get("mrr"),
        "curatedDocumentCount": source.get("curatedDocumentCount"),
        "curatedSourceReferenceCount": source.get("sourceReferenceCount"),
        "checks": checks,
        "elapsedSec": round(time.time() - started, 2),
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0 if ready else 2


def alias_state_for(session: requests.Session, args: argparse.Namespace) -> dict[str, str | None]:
    aliases = ",".join([args.current_read_alias, args.candidate_read_alias])
    response = session.get(
        f"{args.es_url.rstrip('/')}/_cat/aliases/{aliases}?format=json",
        timeout=args.timeout,
    )
    response.raise_for_status()
    rows = response.json()
    current = first_index(rows, args.current_read_alias)
    candidate = first_index(rows, args.candidate_read_alias)
    return {"currentIndex": current, "candidateIndex": candidate}


def first_index(rows: list[dict[str, Any]], alias: str) -> str | None:
    for row in rows:
        if row.get("alias") == alias:
            return row.get("index")
    return None


def check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    sys.exit(main())
