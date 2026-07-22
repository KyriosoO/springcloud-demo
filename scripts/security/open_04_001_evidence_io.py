#!/usr/bin/env python3
"""Strict JSON and create-once publication helpers for OPEN-04-001 evidence."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


AUTH_CONTRACTS = (
    "tenantRef required and exact",
    "permissionCodes required and mapped",
    "validUntil bounded and enforced",
    "service JWT scope and subject enforced",
    "legacy field compatibility isolated to migration boundary",
    "AGENT_FIELD_AUTHORITY does not use legacy fields for decisions",
)

ARTIFACT_FIELDS = {
    "open-04-001-control-verification-v0.1": {
        "schemaVersion", "verifiedAt", "signatureVerified", "repositoryRevision", "configurationDigest",
        "databaseRefDigest", "controlRecordRef", "approvalRef", "evidenceDigest", "operatorRefDigest",
        "approverRefDigest", "validUntil", "verifiedOperations",
    },
    "open-04-001-controlled-migration-result-v0.1": {
        "schemaVersion", "startedAt", "completedAt", "repositoryRevision", "configurationDigest",
        "databaseRefDigest", "controlRecordRef", "controlRecordId", "controlRecordDigest",
        "signatureVerified", "operatorRefDigest", "approverRefDigest", "verifiedOperations",
        "completedStepsAtStart", "steps", "finalState", "policyVersionCount", "activationAuditCount",
        "rollbackExercisePassed",
    },
    "open-04-001-controlled-observation-v0.1": {
        "schemaVersion", "windowStart", "windowEnd", "generatedAt", "sourceDigests", "profiles", "totals",
        "legacyDecisionReadCount", "negativeCases", "thresholdsPassed",
    },
    "auth-field-external-consumer-scan-v0.1": {
        "schemaVersion", "generatedAt", "scopeDeclarationRef", "scopeDeclarationDigest",
        "declaredByRefDigest", "externalScopeDeclaredComplete", "declaredSystems", "scannedSystems",
        "legacyConsumers", "externalConsumersZero", "sourceHashes",
    },
    "open-04-001-auth-contract-verification-v0.1": {
        "schemaVersion", "generatedAt", "repositoryRevision", "passed", "testsRun", "failures", "errors",
        "skipped", "validatedContracts", "reportHashes", "sourceHashes",
    },
    "open-04-001-independent-exit-review-v0.1": {
        "schemaVersion", "reviewId", "reviewerRefDigest", "operatorRefDigest", "verificationKey", "reviewedAt",
        "decision", "findings", "designRef", "controlRecordRef", "controlVerificationRef",
        "migrationResultRef", "observationRef", "repositoryConsumerScanRef", "externalConsumerScanRef",
        "authContractEvidenceRef", "reviewedArtifactHashes", "signature",
    },
    "open-04-001-independent-review-verification-v0.1": {
        "schemaVersion", "verifiedAt", "signatureVerified", "reviewRef", "reviewId", "reviewDigest",
        "reviewerRefDigest", "operatorRefDigest", "controlRecordDigest", "reviewedArtifactHashes",
    },
}


def require_closed_artifact(value: dict[str, Any], label: str) -> None:
    expected = ARTIFACT_FIELDS.get(value.get("schemaVersion"))
    if expected is None or set(value) != expected:
        raise ValueError(f"{label} fields do not match the closed schema")


def load_json(path: Path) -> dict[str, Any]:
    def closed_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=closed_object)
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def atomic_write_json_new(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    atomic_write_bytes_new(path, payload)


def atomic_write_bytes_new(path: Path, payload: bytes) -> None:
    parent = path.resolve().parent
    if not parent.is_dir():
        raise OSError("evidence output parent directory does not exist")
    if path.exists():
        raise FileExistsError(f"evidence output already exists: {path}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=".open-04-001-", suffix=".tmp", dir=parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def resolve_inside(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative or Path(relative).is_absolute():
        raise ValueError("evidence reference must be a canonical repository-relative path")
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("evidence reference escapes repository root") from exc
    if not resolved.is_file():
        raise ValueError(f"evidence source does not exist: {relative}")
    return resolved
