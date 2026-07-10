#!/usr/bin/env python
"""Dry-run-first alias cutover helper for the data-optimized tax-policy index."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests


DEFAULT_READINESS = Path(".tmp/chinatax-v2/dataopt-cutover-readiness.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--es-url", default="http://127.0.0.1:9200")
    parser.add_argument("--readiness-report", type=Path, default=DEFAULT_READINESS)
    parser.add_argument("--read-alias", default="agent-doc-tax-policy-v2-read")
    parser.add_argument("--write-alias", default="agent-doc-tax-policy-v2-write")
    parser.add_argument("--execute", action="store_true", help="Actually send the ES _aliases request.")
    parser.add_argument("--rollback", action="store_true", help="Switch back to rollbackTargetIndex from readiness report.")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--output", type=Path, default=Path(".tmp/chinatax-v2/dataopt-alias-switch-plan.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session = requests.Session()
    started = time.time()
    readiness = read_json(args.readiness_report)
    target_index = target_index_for(args, readiness)
    current_aliases = alias_indices_for(session, args, [args.read_alias, args.write_alias])
    current_index = first_index(current_aliases, args.read_alias)
    actions = alias_actions(args.read_alias, args.write_alias, target_index, current_aliases)
    plan = {
        "mode": "rollback" if args.rollback else "cutover",
        "execute": args.execute,
        "readinessReport": str(args.readiness_report),
        "readyForManualCutover": readiness.get("readyForManualCutover"),
        "readAlias": args.read_alias,
        "writeAlias": args.write_alias,
        "currentIndexBefore": current_index,
        "targetIndex": target_index,
        "rollbackTargetIndex": readiness.get("rollbackTargetIndex"),
        "actions": actions,
        "elapsedSec": round(time.time() - started, 2),
    }
    if not args.rollback and not readiness.get("readyForManualCutover"):
        plan["status"] = "BLOCKED_READINESS_FAILED"
        emit(plan, args.output)
        return 2
    if not target_index:
        plan["status"] = "BLOCKED_TARGET_INDEX_MISSING"
        emit(plan, args.output)
        return 2
    if not index_exists(session, args, target_index):
        plan["status"] = "BLOCKED_TARGET_INDEX_NOT_FOUND"
        emit(plan, args.output)
        return 2
    if args.execute:
        response = session.post(
            f"{args.es_url.rstrip('/')}/_aliases",
            json={"actions": actions},
            timeout=args.timeout,
        )
        response.raise_for_status()
        plan["status"] = "EXECUTED"
        plan["esResponse"] = response.json()
        plan["currentIndexAfter"] = first_index(alias_indices_for(session, args, [args.read_alias]), args.read_alias)
    else:
        plan["status"] = "DRY_RUN"
    emit(plan, args.output)
    return 0


def target_index_for(args: argparse.Namespace, readiness: dict[str, Any]) -> str | None:
    if args.rollback:
        return readiness.get("rollbackTargetIndex")
    return readiness.get("candidateIndex")


def alias_actions(
    read_alias: str,
    write_alias: str,
    target_index: str,
    current_aliases: dict[str, list[str]],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for alias in [read_alias, write_alias]:
        for index in current_aliases.get(alias, []):
            actions.append({"remove": {"index": index, "alias": alias}})
    actions.append({"add": {"index": target_index, "alias": read_alias}})
    actions.append({"add": {"index": target_index, "alias": write_alias, "is_write_index": True}})
    return actions


def alias_indices_for(
    session: requests.Session,
    args: argparse.Namespace,
    aliases: list[str],
) -> dict[str, list[str]]:
    response = session.get(
        f"{args.es_url.rstrip('/')}/_cat/aliases/{','.join(aliases)}?format=json",
        timeout=args.timeout,
    )
    if response.status_code == 404:
        return {}
    response.raise_for_status()
    result: dict[str, list[str]] = {}
    for row in response.json():
        alias = row.get("alias")
        index = row.get("index")
        if alias and index:
            result.setdefault(alias, []).append(index)
    return result


def first_index(aliases: dict[str, list[str]], alias: str) -> str | None:
    values = aliases.get(alias) or []
    return values[0] if values else None


def index_exists(session: requests.Session, args: argparse.Namespace, index: str) -> bool:
    response = session.head(f"{args.es_url.rstrip('/')}/{index}", timeout=args.timeout)
    if response.status_code == 404:
        return False
    response.raise_for_status()
    return True


def emit(plan: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(plan, ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    sys.exit(main())
