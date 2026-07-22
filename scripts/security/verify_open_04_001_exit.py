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

try:
    from open_04_001_evidence_io import (
        AUTH_CONTRACTS, canonical_bytes, load_json, require_closed_artifact, resolve_inside,
    )
except ModuleNotFoundError:  # importlib-based unit tests run from repository root
    from scripts.security.open_04_001_evidence_io import (
        AUTH_CONTRACTS, canonical_bytes, load_json, require_closed_artifact, resolve_inside,
    )


SCHEMA = "open-04-001-exit-evidence-v0.2"
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
        "authority.topic": "04_CONTROLLED_MIGRATION",
        "authority.documentStatus": "In Review",
        "controlRecord.signatureVerified": True,
        "controlRecord.environmentClass": "NON_PRODUCTION_CONTROLLED",
        "controlRecord.enabledModelTargetIdsEmpty": True,
        "controlRecord.runtimeToolTrafficEnabled": False,
        "controlRecord.businessTrafficEnabled": False,
        "observation.controlledProfileCoverageComplete": True,
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
        "controlRecord.ref",
        "controlRecord.verificationRef",
        "observation.evidenceRef",
        "observation.trafficProfileRef",
        "observation.thresholdsRef",
        "consumerScan.scopeRef",
        "consumerScan.externalScopeRef",
        "validation.independentReviewRef",
        "validation.independentReviewVerificationRef",
        "validation.authContractEvidenceRef",
        "policy.policyVersion",
        "policy.migrationResultRef",
    ]
    for path in required_text:
        value = _read_path(evidence, path)
        if not isinstance(value, str) or not value.strip():
            failures.append(f"{path}: non-blank reference required")

    required_digests = [
        "authority.operatorRefDigest",
        "authority.independentReviewerRefDigest",
        "authority.exitApprovalEvidenceDigest",
        "controlRecord.recordDigest",
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
        for ref_path in (
            "controlRecord.ref", "controlRecord.verificationRef", "observation.evidenceRef",
            "policy.migrationResultRef", "validation.authContractEvidenceRef",
            "validation.independentReviewRef", "validation.independentReviewVerificationRef",
        ):
            value = _read_path(evidence, ref_path)
            if isinstance(value, str):
                relative = value.split("#", 1)[0]
                if relative not in source_hashes:
                    failures.append(f"sourceHashes: {ref_path} must be hash-bound")
        observation_ref = _read_path(evidence, "observation.evidenceRef")
        if isinstance(observation_ref, str) and observation_ref.split("#", 1)[0] in source_hashes:
            failures.extend(_verify_observation(root, observation_ref.split("#", 1)[0]))
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
        failures.extend(_verify_closed_artifact_chain(evidence, root))

    return failures


def _verify_closed_artifact_chain(evidence: dict[str, Any], root: Path) -> list[str]:
    failures: list[str] = []
    ref_paths = {
        "control": "controlRecord.ref",
        "verification": "controlRecord.verificationRef",
        "migration": "policy.migrationResultRef",
        "observation": "observation.evidenceRef",
        "repository_scan": "consumerScan.scopeRef",
        "external_scan": "consumerScan.externalScopeRef",
        "auth_contract": "validation.authContractEvidenceRef",
        "review": "validation.independentReviewRef",
        "review_verification": "validation.independentReviewVerificationRef",
    }
    values: dict[str, dict[str, Any]] = {}
    refs: dict[str, str] = {}
    try:
        for name, dotted in ref_paths.items():
            ref = _read_path(evidence, dotted)
            if not isinstance(ref, str):
                return failures
            refs[name] = ref.split("#", 1)[0]
            values[name] = load_json(resolve_inside(root, refs[name]))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"artifact chain: cannot read a closed artifact: {exc}"]

    control = values["control"]
    verification = values["verification"]
    migration = values["migration"]
    observation = values["observation"]
    external_scan = values["external_scan"]
    auth_contract = values["auth_contract"]
    review = values["review"]
    review_verification = values["review_verification"]
    for label, artifact in (
        ("control verification", verification), ("migration result", migration),
        ("observation", observation), ("external scan", values["external_scan"]),
        ("Auth contract", auth_contract), ("independent review", review),
        ("review verification", review_verification),
    ):
        try:
            require_closed_artifact(artifact, label)
        except ValueError as exc:
            failures.append(f"artifact chain: {exc}")
    control_digest = hashlib.sha256(canonical_bytes(control)).hexdigest()
    failures.extend(_verify_nested_hash_map(root, control.get("sourceHashes"), "control record sourceHashes"))
    checks = {
        "controlRecord.recordDigest": control_digest,
        "control verification schema": "open-04-001-control-verification-v0.1",
        "migration result schema": "open-04-001-controlled-migration-result-v0.1",
        "Auth contract schema": "open-04-001-auth-contract-verification-v0.1",
        "independent review schema": "open-04-001-independent-exit-review-v0.1",
        "independent review verification schema": "open-04-001-independent-review-verification-v0.1",
    }
    actuals = {
        "controlRecord.recordDigest": _read_path(evidence, "controlRecord.recordDigest"),
        "control verification schema": verification.get("schemaVersion"),
        "migration result schema": migration.get("schemaVersion"),
        "Auth contract schema": auth_contract.get("schemaVersion"),
        "independent review schema": review.get("schemaVersion"),
        "independent review verification schema": review_verification.get("schemaVersion"),
    }
    for label, expected in checks.items():
        if actuals[label] != expected:
            failures.append(f"artifact chain: {label} does not match")
    for artifact_name, artifact in (("verification", verification), ("migration", migration)):
        if artifact.get("signatureVerified") is not True:
            failures.append(f"artifact chain: {artifact_name} signatureVerified must be true")
        expected_digest = artifact.get("evidenceDigest") if artifact_name == "verification" \
            else artifact.get("controlRecordDigest")
        if expected_digest != control_digest:
            failures.append(f"artifact chain: {artifact_name} control digest mismatch")
        if artifact.get("controlRecordRef") != refs["control"]:
            failures.append(f"artifact chain: {artifact_name} controlRecordRef mismatch")
        for field in ("repositoryRevision", "configurationDigest", "databaseRefDigest",
                      "operatorRefDigest", "approverRefDigest"):
            if artifact.get(field) != control.get(field):
                failures.append(f"artifact chain: {artifact_name}.{field} mismatch")
    expected_operations = [
        {key: value for key, value in operation.items() if key != "fromPolicyDigest"}
        for operation in control.get("policyOperations", [])
    ]
    if verification.get("verifiedOperations") != expected_operations \
            or migration.get("verifiedOperations") != expected_operations:
        failures.append("artifact chain: verified operations do not match control record")
    final = migration.get("finalState")
    if not isinstance(final, dict) or final.get("policyVersion") != control.get("policyVersion") \
            or final.get("policyDigest") != control.get("policyDigest") \
            or final.get("policyEpoch") != 3 or final.get("stateVersion") != 3 \
            or migration.get("policyVersionCount") != 2 or migration.get("activationAuditCount") != 3 \
            or migration.get("rollbackExercisePassed") is not True:
        failures.append("artifact chain: migration result does not prove exact final rollback state")
    if _read_path(evidence, "policy.policyVersion") != control.get("policyVersion") \
            or _read_path(evidence, "policy.policyDigest") != control.get("policyDigest") \
            or _read_path(evidence, "policy.policyEpoch") != 3:
        failures.append("artifact chain: exit policy does not match signed migration result")

    try:
        window_start = _parse_chain_time(observation.get("windowStart"))
        window_end = _parse_chain_time(observation.get("windowEnd"))
        if not (_parse_chain_time(control.get("windowNotBefore")) <= window_start < window_end
                <= _parse_chain_time(control.get("windowNotAfter"))):
            failures.append("artifact chain: observation is outside the signed window")
    except (TypeError, ValueError):
        failures.append("artifact chain: observation/control timestamps are invalid")
    if _read_path(evidence, "observation.windowStart") != observation.get("windowStart") \
            or _read_path(evidence, "observation.windowEnd") != observation.get("windowEnd"):
        failures.append("artifact chain: exit observation window is not derived from observation artifact")
    profiles = observation.get("profiles")
    if isinstance(profiles, list):
        derived_count = sum(
            profile.get(phase, {}).get("resolutionCount", 0)
            for profile in profiles if isinstance(profile, dict) for phase in ("phaseB", "phaseC")
        )
        if _read_path(evidence, "observation.requestCount") != derived_count:
            failures.append("artifact chain: observation requestCount is not derived")
    totals = observation.get("totals")
    if isinstance(totals, dict):
        for name in ("AGENT_WIDER_THAN_AUTH", "UNMAPPABLE", "AUTH_WIDER_THAN_AGENT"):
            if _read_path(evidence, f"observation.diff.{name}") != totals.get(name):
                failures.append(f"artifact chain: observation.diff.{name} is not derived")

    if auth_contract.get("passed") is not True or auth_contract.get("testsRun", 0) <= 0 \
            or auth_contract.get("failures") != 0 or auth_contract.get("errors") != 0 \
            or auth_contract.get("skipped") != 0 \
            or auth_contract.get("repositoryRevision") != control.get("repositoryRevision") \
            or auth_contract.get("validatedContracts") != list(AUTH_CONTRACTS):
        failures.append("artifact chain: Auth contract evidence is not a complete pass for the signed revision")
    failures.extend(_verify_nested_hash_map(root, auth_contract.get("sourceHashes"), "Auth contract sourceHashes"))
    failures.extend(_verify_nested_hash_map(root, auth_contract.get("reportHashes"), "Auth contract reportHashes"))

    operator = control.get("operatorRefDigest")
    reviewer = control.get("approverRefDigest")
    if review.get("operatorRefDigest") != operator or review.get("reviewerRefDigest") != reviewer \
            or reviewer == operator or review.get("decision") != "APPROVE_OPEN_04_001_EXIT" \
            or review.get("findings") != [] or review.get("verificationKey") != control.get("verificationKey"):
        failures.append("artifact chain: independent review identity or decision is invalid")
    try:
        reviewed_at = _parse_chain_time(review.get("reviewedAt"))
        latest_artifact = max(
            _parse_chain_time(verification.get("verifiedAt")),
            _parse_chain_time(migration.get("completedAt")),
            _parse_chain_time(observation.get("windowEnd")),
            _parse_chain_time(external_scan.get("generatedAt")),
            _parse_chain_time(auth_contract.get("generatedAt")),
        )
        if reviewed_at <= latest_artifact or reviewed_at > _parse_chain_time(control.get("validUntil")):
            failures.append("artifact chain: independent review time is outside the signed window")
        if _parse_chain_time(review_verification.get("verifiedAt")) < reviewed_at:
            failures.append("artifact chain: review verification predates the signed review")
    except (TypeError, ValueError):
        failures.append("artifact chain: independent review timestamps are invalid")
    design_ref = _read_path(evidence, "authority.documentRef")
    design_path = design_ref.split("#", 1)[0] if isinstance(design_ref, str) else ""
    expected_roles = {
        "designRef": design_path,
        "controlRecordRef": refs["control"],
        "controlVerificationRef": refs["verification"],
        "migrationResultRef": refs["migration"],
        "observationRef": refs["observation"],
        "repositoryConsumerScanRef": refs["repository_scan"],
        "externalConsumerScanRef": refs["external_scan"],
        "authContractEvidenceRef": refs["auth_contract"],
    }
    expected_review_hashes = {}
    try:
        for role, ref in expected_roles.items():
            if review.get(role) != ref:
                failures.append(f"artifact chain: independent review {role} mismatch")
            expected_review_hashes[ref] = hashlib.sha256(resolve_inside(root, ref).read_bytes()).hexdigest()
    except ValueError as exc:
        failures.append(f"artifact chain: independent review reference invalid: {exc}")
    if review.get("reviewedArtifactHashes") != dict(sorted(expected_review_hashes.items())):
        failures.append("artifact chain: independent review hashes do not bind the exact artifacts")
    review_digest = hashlib.sha256(canonical_bytes(review)).hexdigest()
    if review_verification.get("signatureVerified") is not True \
            or review_verification.get("reviewRef") != refs["review"] \
            or review_verification.get("reviewId") != review.get("reviewId") \
            or review_verification.get("reviewDigest") != review_digest \
            or review_verification.get("controlRecordDigest") != control_digest \
            or review_verification.get("reviewerRefDigest") != reviewer \
            or review_verification.get("operatorRefDigest") != operator \
            or review_verification.get("reviewedArtifactHashes") != review.get("reviewedArtifactHashes"):
        failures.append("artifact chain: independent review verification does not match signed review")
    if _read_path(evidence, "authority.exitApprovalEvidenceDigest") != review_digest \
            or _read_path(evidence, "validation.independentReviewEvidenceDigest") != review_digest:
        failures.append("artifact chain: exit review digest is not derived from signed review")
    return failures


def _verify_nested_hash_map(root: Path, hashes: Any, label: str) -> list[str]:
    if not isinstance(hashes, dict) or not hashes:
        return [f"artifact chain: {label} is required"]
    failures = []
    for ref, expected in hashes.items():
        try:
            actual = hashlib.sha256(resolve_inside(root, ref).read_bytes()).hexdigest()
            if actual != expected:
                failures.append(f"artifact chain: {label}.{ref} digest mismatch")
        except ValueError as exc:
            failures.append(f"artifact chain: {label}.{ref} invalid: {exc}")
    return failures


def _parse_chain_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise TypeError("timestamp must be text")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamp must have timezone")
    return result


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
        scan = load_json(candidate)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
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
        scan = load_json(candidate)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"consumerScan.externalScopeRef: cannot read bound scan evidence: {exc}"]
    if not isinstance(scan, dict):
        return ["consumerScan.externalScopeRef: scan evidence root must be an object"]
    failures: list[str] = []
    if scan.get("schemaVersion") != "auth-field-external-consumer-scan-v0.1":
        failures.append("consumerScan.externalScopeRef: unsupported scan evidence schema")
    if scan.get("externalConsumersZero") is not True:
        failures.append("consumerScan.externalScopeRef: external consumers are not zero")
    if scan.get("externalScopeDeclaredComplete") is not True:
        failures.append("consumerScan.externalScopeRef: external scope declaration is incomplete")
    declaration = {
        "schemaVersion": "auth-field-external-consumer-scope-v0.1",
        "declarationRef": scan.get("scopeDeclarationRef"),
        "declaredByRefDigest": scan.get("declaredByRefDigest"),
        "externalScopeDeclaredComplete": scan.get("externalScopeDeclaredComplete"),
        "systems": scan.get("declaredSystems"),
    }
    declaration_digest = scan.get("scopeDeclarationDigest")
    if not isinstance(declaration_digest, str) or DIGEST.fullmatch(declaration_digest) is None:
        failures.append("consumerScan.externalScopeRef: scopeDeclarationDigest is required")
    else:
        actual_declaration_digest = hashlib.sha256(
            json.dumps(declaration, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if declaration_digest != actual_declaration_digest:
            failures.append("consumerScan.externalScopeRef: scope declaration digest mismatch")
    declared_systems = scan.get("declaredSystems")
    if not isinstance(declared_systems, list) or not declared_systems:
        failures.append("consumerScan.externalScopeRef: declaredSystems are required")
    systems = scan.get("scannedSystems")
    if not isinstance(systems, list) or not systems or any(not isinstance(system, dict) for system in systems):
        failures.append("consumerScan.externalScopeRef: non-empty scannedSystems are required")
    if isinstance(declared_systems, list) and isinstance(systems, list):
        declared_identity = [(item.get("systemId"), item.get("revision")) for item in declared_systems
                             if isinstance(item, dict)]
        scanned_identity = [(item.get("systemId"), item.get("revision")) for item in systems
                            if isinstance(item, dict)]
        if len(declared_identity) != len(declared_systems) or len(scanned_identity) != len(systems) \
                or len(set(declared_identity)) != len(declared_identity) \
                or sorted(declared_identity) != sorted(scanned_identity):
            failures.append("consumerScan.externalScopeRef: scanned systems do not match declared revisions")
    if scan.get("legacyConsumers") != []:
        failures.append("consumerScan.externalScopeRef: legacyConsumers must be empty")
    nested_hashes = scan.get("sourceHashes")
    if not isinstance(nested_hashes, dict) or not nested_hashes:
        failures.append("consumerScan.externalScopeRef: nested sourceHashes are required")
    else:
        failures.extend(_verify_source_hashes(nested_hashes, root, "externalConsumerScan.sourceHashes"))
    return failures


def _verify_observation(root: Path, relative: str) -> list[str]:
    candidate = (root.resolve() / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
        observation = load_json(candidate)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return [f"observation.evidenceRef: cannot read bound observation: {exc}"]
    failures: list[str] = []
    if observation.get("schemaVersion") != "open-04-001-controlled-observation-v0.1":
        failures.append("observation.evidenceRef: unsupported observation schema")
    if observation.get("thresholdsPassed") is not True:
        failures.append("observation.evidenceRef: thresholds did not pass")
    if observation.get("legacyDecisionReadCount") != 0:
        failures.append("observation.evidenceRef: phase C legacy reads must be zero")
    profiles = observation.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        failures.append("observation.evidenceRef: profiles are required")
    else:
        for profile in profiles:
            if not isinstance(profile, dict):
                failures.append("observation.evidenceRef: profile entry must be an object")
                continue
            for phase in ("phaseB", "phaseC"):
                value = profile.get(phase)
                if not isinstance(value, dict) or value.get("resolutionCount", 0) < 100:
                    failures.append(f"observation.evidenceRef: {phase} requires at least 100 resolutions")
    totals = observation.get("totals")
    if not isinstance(totals, dict) or totals.get("AGENT_WIDER_THAN_AUTH") != 0 or totals.get("UNMAPPABLE") != 0:
        failures.append("observation.evidenceRef: widening and unmappable totals must be zero")
    negatives = observation.get("negativeCases")
    if not isinstance(negatives, list) or len(negatives) != 5 or any(
        not isinstance(item, dict) or item.get("attemptCount") != item.get("rejectedCount") for item in negatives
    ):
        failures.append("observation.evidenceRef: all five negative cases must be rejected")
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
        evidence = load_json(args.evidence)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
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
