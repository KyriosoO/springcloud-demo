#!/usr/bin/env python3
"""Scan target Agent Java sources for unexpected legacy Auth field consumers."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


TOKENS = ("LegacyAuthFieldView", "legacyFieldView", "legacyView")
LEGACY_WIRE_FIELDS = ("filterableFields", "displayableFields", "allowedOperators", "allowedFunctions")
ALLOWED_MIGRATION_BOUNDARY = {
    "agent-service/src/main/java/com/dylan/baseline/agent/security/authorization/LegacyAuthFieldView.java",
    "agent-service/src/main/java/com/dylan/baseline/agent/security/authorization/ResolvedAuthPermission.java",
    "agent-service/src/main/java/com/dylan/baseline/agent/security/authorization/internal/AuthPermissionAuthorityAdapter.java",
    "agent-service/src/main/java/com/dylan/baseline/agent/security/authorization/internal/AuthPermissionWireResponse.java",
    "agent-service/src/main/java/com/dylan/baseline/agent/security/migration/AuthFieldMigrationComparator.java",
    "agent-service/src/main/java/com/dylan/baseline/agent/security/migration/AuthFieldMigrationResolution.java",
    "agent-service/src/main/java/com/dylan/baseline/agent/security/policy/AgentFieldPolicySnapshot.java",
    "agent-service/src/main/java/com/dylan/baseline/agent/security/policy/AuthorizationIntersectionService.java",
    "agent-service/src/main/java/com/dylan/baseline/agent/security/policy/admin/AuthFieldPolicyPayloadValidator.java",
}
INTERSECTION_SERVICE = (
    "agent-service/src/main/java/com/dylan/baseline/agent/security/policy/AuthorizationIntersectionService.java"
)


def scan(root: Path) -> dict[str, Any]:
    resolved_root = root.resolve()
    source_root = resolved_root / "agent-service/src/main/java"
    matched: list[str] = []
    hashes: dict[str, str] = {}
    if source_root.is_dir():
        for source in sorted(source_root.rglob("*.java")):
            text = source.read_text(encoding="utf-8")
            relative = source.relative_to(resolved_root).as_posix()
            carries_legacy_wire_fields = all(field in text for field in LEGACY_WIRE_FIELDS)
            if any(token in text for token in TOKENS) or carries_legacy_wire_fields:
                matched.append(relative)
                hashes[relative] = hashlib.sha256(source.read_bytes()).hexdigest()

    unexpected = sorted(set(matched) - ALLOWED_MIGRATION_BOUNDARY)
    service_path = resolved_root / INTERSECTION_SERVICE
    service_text = service_path.read_text(encoding="utf-8") if service_path.is_file() else ""
    invariants = {
        "dualReadIsOnlyLegacyDecisionMode": (
            "migrationMode == AuthFieldMigrationMode.DUAL_READ_ENFORCE_INTERSECTION" in service_text
            and "agentFields.intersect(legacyView)" in service_text
        ),
        "agentAuthorityMarksLegacyDecisionUseFalse": (
            "migrationMode == AuthFieldMigrationMode.AGENT_FIELD_AUTHORITY && legacyView != null"
            in service_text
            and "agentFields, Optional.of(migrationComparator.compare(legacyView, agentFields)), false"
            in service_text
        ),
        "removedModeCanReturnWithoutLegacyObservation": (
            "new AuthFieldMigrationResolution(agentFields, Optional.empty(), false)" in service_text
        ),
    }
    passed = not unexpected and all(invariants.values())
    return {
        "schemaVersion": "auth-field-legacy-consumer-scan-v0.1",
        "state": "PASS" if passed else "FAIL",
        "scope": "agent-service/src/main/java target sources only",
        "knownMigrationBoundaryFiles": matched,
        "unexpectedLegacyConsumers": unexpected,
        "repositoryUnexpectedConsumersZero": not unexpected,
        "runtimeDecisionInvariants": invariants,
        "externalConsumersProvenZero": False,
        "sourceHashes": hashes,
        "limitations": [
            "The scan does not inspect external repositories or deployed consumers.",
            "Runtime zero-read evidence still requires a 12A-frozen AGENT_FIELD_AUTHORITY observation window.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    result = scan(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["state"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
