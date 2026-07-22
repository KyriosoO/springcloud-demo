#!/usr/bin/env python3
"""Read-only verifier for the evidence required to close OPEN-04-001."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA = "open-04-001-exit-evidence-v0.1"
DIGEST = re.compile(r"^[0-9a-f]{64}$")


def _read_path(data: dict[str, Any], dotted: str) -> Any:
    current: Any = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def verify(evidence: dict[str, Any], root: Path) -> list[str]:
    failures: list[str] = []

    expected_values = {
        "schemaVersion": SCHEMA,
        "state": "OPEN_04_001_EXIT_APPROVED",
        "authority.topic": "12A",
        "authority.documentStatus": "Approved",
        "observation.representativeTraffic": True,
        "observation.thresholdsPassed": True,
        "policy.mode": "AGENT_FIELD_AUTHORITY",
        "policy.rollbackExercisePassed": True,
        "consumerScan.repositoryUnexpectedConsumersZero": True,
        "consumerScan.externalConsumersZero": True,
        "validation.authContractPassed": True,
        "validation.allKnownProfilesRecomputable": True,
        "validation.negativeTestsPassed": True,
        "validation.independentReviewPassed": True,
    }
    for path, expected in expected_values.items():
        actual = _read_path(evidence, path)
        if actual != expected:
            failures.append(f"{path}: expected {expected!r}, got {actual!r}")

    required_text = [
        "authority.documentRef",
        "authority.exitApprovalRef",
        "observation.trafficProfileRef",
        "observation.thresholdsRef",
        "consumerScan.scopeRef",
        "consumerScan.externalScopeRef",
        "validation.independentReviewRef",
        "policy.policyVersion",
    ]
    for path in required_text:
        value = _read_path(evidence, path)
        if not isinstance(value, str) or not value.strip():
            failures.append(f"{path}: non-blank reference required")

    required_digests = [
        "authority.operatorRefDigest",
        "authority.independentReviewerRefDigest",
        "authority.exitApprovalEvidenceDigest",
        "policy.policyDigest",
        "validation.independentReviewEvidenceDigest",
    ]
    for path in required_digests:
        value = _read_path(evidence, path)
        if not isinstance(value, str) or DIGEST.fullmatch(value) is None:
            failures.append(f"{path}: lowercase SHA-256 required")
    operator_digest = _read_path(evidence, "authority.operatorRefDigest")
    reviewer_digest = _read_path(evidence, "authority.independentReviewerRefDigest")
    if isinstance(operator_digest, str) and operator_digest == reviewer_digest:
        failures.append("authority: reviewer must be independent from operator")

    start = _parse_time(_read_path(evidence, "observation.windowStart"), "observation.windowStart", failures)
    end = _parse_time(_read_path(evidence, "observation.windowEnd"), "observation.windowEnd", failures)
    if start is not None and end is not None and end <= start:
        failures.append("observation: windowEnd must be after windowStart")
    request_count = _read_path(evidence, "observation.requestCount")
    if not isinstance(request_count, int) or isinstance(request_count, bool) or request_count <= 0:
        failures.append("observation.requestCount: positive integer required")
    epoch = _read_path(evidence, "policy.policyEpoch")
    if not isinstance(epoch, int) or isinstance(epoch, bool) or epoch <= 0:
        failures.append("policy.policyEpoch: positive integer required")
    legacy_reads = _read_path(evidence, "observation.legacyDecisionReadCount")
    if not isinstance(legacy_reads, int) or isinstance(legacy_reads, bool) or legacy_reads != 0:
        failures.append("observation.legacyDecisionReadCount: integer zero required")
    for name in ("AGENT_WIDER_THAN_AUTH", "UNMAPPABLE", "AUTH_WIDER_THAN_AGENT"):
        value = _read_path(evidence, f"observation.diff.{name}")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            failures.append(f"observation.diff.{name}: non-negative integer required")
        elif name in ("AGENT_WIDER_THAN_AUTH", "UNMAPPABLE") and value != 0:
            failures.append(f"observation.diff.{name}: must be zero")
    narrowing = _read_path(evidence, "observation.diff.AUTH_WIDER_THAN_AGENT")
    narrowing_approval = _read_path(evidence, "observation.narrowingApprovalRef")
    if isinstance(narrowing, int) and not isinstance(narrowing, bool) and narrowing > 0:
        if not isinstance(narrowing_approval, str) or not narrowing_approval.strip():
            failures.append("observation.narrowingApprovalRef: required when narrowing is observed")

    source_hashes = evidence.get("sourceHashes")
    if not isinstance(source_hashes, dict) or not source_hashes:
        failures.append("sourceHashes: at least one bound source is required")
    else:
        failures.extend(_verify_source_hashes(source_hashes, root, "sourceHashes"))
        authority_ref = _read_path(evidence, "authority.documentRef")
        if isinstance(authority_ref, str):
            authority_path = authority_ref.split("#", 1)[0]
            if authority_path not in source_hashes:
                failures.append("sourceHashes: authority.documentRef must be hash-bound")
        consumer_ref = _read_path(evidence, "consumerScan.scopeRef")
        if isinstance(consumer_ref, str):
            consumer_path = consumer_ref.split("#", 1)[0]
            if consumer_path not in source_hashes:
                failures.append("sourceHashes: consumerScan.scopeRef must be hash-bound")
            else:
                failures.extend(_verify_consumer_scan(root, consumer_path))
        external_consumer_ref = _read_path(evidence, "consumerScan.externalScopeRef")
        if isinstance(external_consumer_ref, str):
            external_consumer_path = external_consumer_ref.split("#", 1)[0]
            if external_consumer_path not in source_hashes:
                failures.append("sourceHashes: consumerScan.externalScopeRef must be hash-bound")
            else:
                failures.extend(_verify_external_consumer_scan(root, external_consumer_path))

    return failures


def _verify_source_hashes(source_hashes: dict[str, Any], root: Path, label: str) -> list[str]:
    failures: list[str] = []
    resolved_root = root.resolve()
    for relative, expected_digest in sorted(source_hashes.items()):
        if not isinstance(relative, str) or not isinstance(expected_digest, str) or DIGEST.fullmatch(expected_digest) is None:
            failures.append(f"{label}.{relative}: invalid entry")
            continue
        candidate = (resolved_root / relative).resolve()
        try:
            candidate.relative_to(resolved_root)
        except ValueError:
            failures.append(f"{label}.{relative}: path escapes repository root")
            continue
        if not candidate.is_file():
            failures.append(f"{label}.{relative}: source file not found")
            continue
        actual_digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if actual_digest != expected_digest:
            failures.append(f"{label}.{relative}: digest mismatch")
    return failures


def _verify_consumer_scan(root: Path, relative: str) -> list[str]:
    failures: list[str] = []
    resolved_root = root.resolve()
    candidate = (resolved_root / relative).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError:
        return ["consumerScan.scopeRef: path escapes repository root"]
    try:
        scan = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"consumerScan.scopeRef: cannot read bound scan evidence: {exc}"]
    if not isinstance(scan, dict):
        return ["consumerScan.scopeRef: scan evidence root must be an object"]
    if scan.get("schemaVersion") != "auth-field-legacy-consumer-scan-v0.1":
        failures.append("consumerScan.scopeRef: unsupported scan evidence schema")
    if scan.get("repositoryUnexpectedConsumersZero") is not True:
        failures.append("consumerScan.scopeRef: repository unexpected consumers are not zero")
    if scan.get("unexpectedLegacyConsumers") != []:
        failures.append("consumerScan.scopeRef: unexpected legacy consumers must be empty")
    invariants = scan.get("runtimeDecisionInvariants")
    if not isinstance(invariants, dict) or not invariants or any(value is not True for value in invariants.values()):
        failures.append("consumerScan.scopeRef: runtime decision invariants are incomplete")
    nested_hashes = scan.get("sourceHashes")
    if not isinstance(nested_hashes, dict) or not nested_hashes:
        failures.append("consumerScan.scopeRef: nested sourceHashes are required")
    else:
        failures.extend(_verify_source_hashes(nested_hashes, root, "consumerScan.sourceHashes"))
    return failures


def _verify_external_consumer_scan(root: Path, relative: str) -> list[str]:
    resolved_root = root.resolve()
    candidate = (resolved_root / relative).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError:
        return ["consumerScan.externalScopeRef: path escapes repository root"]
    try:
        scan = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"consumerScan.externalScopeRef: cannot read bound scan evidence: {exc}"]
    if not isinstance(scan, dict):
        return ["consumerScan.externalScopeRef: scan evidence root must be an object"]
    failures: list[str] = []
    if scan.get("schemaVersion") != "auth-field-external-consumer-scan-v0.1":
        failures.append("consumerScan.externalScopeRef: unsupported scan evidence schema")
    if scan.get("externalConsumersZero") is not True:
        failures.append("consumerScan.externalScopeRef: external consumers are not zero")
    systems = scan.get("scannedSystems")
    if not isinstance(systems, list) or not systems or any(
        not isinstance(system, str) or not system.strip() for system in systems
    ):
        failures.append("consumerScan.externalScopeRef: non-empty scannedSystems are required")
    return failures


def _parse_time(value: Any, path: str, failures: list[str]) -> datetime | None:
    if not isinstance(value, str):
        failures.append(f"{path}: ISO-8601 timestamp required")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        failures.append(f"{path}: invalid ISO-8601 timestamp")
        return None
    if parsed.tzinfo is None:
        failures.append(f"{path}: timezone offset required")
        return None
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"OPEN-04-001 EXIT BLOCKED: cannot read evidence: {exc}", file=sys.stderr)
        return 2
    if not isinstance(evidence, dict):
        print("OPEN-04-001 EXIT BLOCKED: evidence root must be an object", file=sys.stderr)
        return 2
    failures = verify(evidence, args.root)
    if failures:
        print("OPEN-04-001 EXIT BLOCKED")
        for failure in failures:
            print(f"- {failure}")
        return 2
    print("OPEN-04-001 EXIT VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
