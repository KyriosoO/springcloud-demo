#!/usr/bin/env python3
"""Scan an explicitly declared repository/deployment inventory for legacy Auth-field consumers."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "auth-field-external-consumer-scope-v0.1"
OUTPUT_SCHEMA = "auth-field-external-consumer-scan-v0.1"
DIGEST = re.compile(r"^[0-9a-f]{64}$")
TOKENS = ("filterableFields", "displayableFields", "allowedOperators", "allowedFunctions")


def scan(scope: dict[str, Any], root: Path) -> tuple[dict[str, Any], bool]:
    if scope.get("schemaVersion") != SCHEMA:
        raise ValueError("unsupported scope schema")
    complete = scope.get("externalScopeDeclaredComplete") is True
    declarer = scope.get("declaredByRefDigest")
    if not isinstance(declarer, str) or DIGEST.fullmatch(declarer) is None:
        raise ValueError("declaredByRefDigest must be a lowercase SHA-256")
    systems = scope.get("systems")
    if not isinstance(systems, list) or not systems:
        raise ValueError("systems must be a non-empty explicit inventory")
    results = []
    all_hashes: dict[str, str] = {}
    consumers: list[dict[str, str]] = []
    for system in systems:
        if not isinstance(system, dict) or set(system) != {"systemId", "kind", "rootRef", "revision", "includeGlobs"}:
            raise ValueError("each system must use the closed inventory schema")
        system_id = _text(system, "systemId")
        system_root = _resolve(root, _text(system, "rootRef"))
        globs = system.get("includeGlobs")
        if not isinstance(globs, list) or not globs or any(not isinstance(item, str) or not item for item in globs):
            raise ValueError("includeGlobs must be a non-empty string list")
        files: set[Path] = set()
        for pattern in globs:
            files.update(path for path in system_root.glob(pattern) if path.is_file())
        if not files:
            raise ValueError(f"system {system_id} scan matched no files")
        hits = []
        for path in sorted(files):
            relative = path.relative_to(root.resolve()).as_posix()
            content = path.read_text(encoding="utf-8", errors="ignore")
            all_hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            for token in TOKENS:
                if token in content:
                    hit = {"systemId": system_id, "sourceRef": relative, "token": token}
                    hits.append(hit)
                    consumers.append(hit)
        results.append({
            "systemId": system_id,
            "kind": _text(system, "kind"),
            "revision": _text(system, "revision"),
            "matchedFileCount": len(files),
            "legacyConsumers": hits,
        })
    passed = complete and not consumers
    return ({
        "schemaVersion": OUTPUT_SCHEMA,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scopeDeclarationRef": scope.get("declarationRef"),
        "declaredByRefDigest": declarer,
        "externalScopeDeclaredComplete": complete,
        "scannedSystems": results,
        "legacyConsumers": consumers,
        "externalConsumersZero": passed,
        "sourceHashes": dict(sorted(all_hashes.items())),
    }, passed)


def _resolve(root: Path, relative: str) -> Path:
    resolved_root = root.resolve()
    candidate = (resolved_root / relative).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("system root escapes repository root") from exc
    if not candidate.is_dir():
        raise ValueError("system root is not a directory")
    return candidate


def _text(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise ValueError(f"{key} must be non-blank")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result, passed = scan(json.loads(args.scope.read_text(encoding="utf-8")), args.root)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"OPEN-04-001 EXTERNAL CONSUMER SCAN BLOCKED: {exc}", file=sys.stderr)
        return 2
    if not passed:
        print("OPEN-04-001 EXTERNAL CONSUMER SCAN BLOCKED: scope incomplete or consumers found", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
