#!/usr/bin/env python3
"""Assemble OPEN-04-001 exit evidence only from cross-checked immutable artifacts."""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from open_04_001_evidence_io import (
        AUTH_CONTRACTS, atomic_write_json_new, canonical_bytes, load_json, require_closed_artifact,
        resolve_inside, sha256_file,
    )
    from verify_open_04_001_exit import SCHEMA, verify
except ModuleNotFoundError:  # importlib-based unit tests run from repository root
    from scripts.security.open_04_001_evidence_io import (
        AUTH_CONTRACTS, atomic_write_json_new, canonical_bytes, load_json, require_closed_artifact,
        resolve_inside, sha256_file,
    )
    from scripts.security.verify_open_04_001_exit import SCHEMA, verify


DIGEST_KEYS = ("configurationDigest", "databaseRefDigest")


def assemble(root: Path, refs: dict[str, str]) -> dict[str, Any]:
    artifacts = {name: load_json(resolve_inside(root, ref)) for name, ref in refs.items() if name != "design"}
    control = artifacts["control"]
    verification = artifacts["verification"]
    migration = artifacts["migration"]
    observation = artifacts["observation"]
    repository_scan = artifacts["repository_scan"]
    external_scan = artifacts["external_scan"]
    auth_contract = artifacts["auth_contract"]
    review = artifacts["review"]
    review_verification = artifacts["review_verification"]

    _equals("open-04-001-migration-control-v0.1", control.get("schemaVersion"), "control schema")
    _equals("open-04-001-control-verification-v0.1", verification.get("schemaVersion"), "verification schema")
    _equals("open-04-001-controlled-migration-result-v0.1", migration.get("schemaVersion"), "migration schema")
    _equals("open-04-001-controlled-observation-v0.1", observation.get("schemaVersion"), "observation schema")
    _equals("auth-field-legacy-consumer-scan-v0.1", repository_scan.get("schemaVersion"), "repository scan schema")
    _equals("auth-field-external-consumer-scan-v0.1", external_scan.get("schemaVersion"), "external scan schema")
    _equals("open-04-001-auth-contract-verification-v0.1", auth_contract.get("schemaVersion"), "Auth contract schema")
    _equals("open-04-001-independent-exit-review-v0.1", review.get("schemaVersion"), "review schema")
    _equals("open-04-001-independent-review-verification-v0.1",
            review_verification.get("schemaVersion"), "review verification schema")
    for label, artifact in (
        ("control verification", verification), ("migration result", migration),
        ("observation", observation), ("external scan", external_scan),
        ("Auth contract", auth_contract), ("independent review", review),
        ("review verification", review_verification),
    ):
        require_closed_artifact(artifact, label)
    _verify_nested_hashes(root, control.get("sourceHashes"), "control record sources")

    control_digest = hashlib.sha256(canonical_bytes(control)).hexdigest()
    _equals(control_digest, verification.get("evidenceDigest"), "control verification digest")
    _equals(control_digest, migration.get("controlRecordDigest"), "migration control digest")
    for field in ("repositoryRevision", *DIGEST_KEYS, "operatorRefDigest", "approverRefDigest"):
        _equals(control.get(field), verification.get(field), f"verification {field}")
        _equals(control.get(field), migration.get(field), f"migration {field}")
    _equals(refs["control"], verification.get("controlRecordRef"), "verification controlRecordRef")
    _equals(refs["control"], migration.get("controlRecordRef"), "migration controlRecordRef")
    if verification.get("signatureVerified") is not True or migration.get("signatureVerified") is not True:
        raise ValueError("control signature must be verified by both runtime artifacts")
    _verify_operations(control, verification.get("verifiedOperations"))
    _verify_operations(control, migration.get("verifiedOperations"))
    _verify_migration(control, migration)
    _verify_observation(control, observation)
    _verify_repository_scan(root, repository_scan)
    _verify_external_scan(root, external_scan)
    _verify_auth_contract(root, control, auth_contract)
    _verify_review(root, refs, control, control_digest, review, review_verification,
                   verification, migration, observation, external_scan, auth_contract)

    profiles = observation["profiles"]
    request_count = sum(
        profile[phase]["resolutionCount"] for profile in profiles for phase in ("phaseB", "phaseC")
    )
    totals = observation["totals"]
    reviewer = review["reviewerRefDigest"]
    review_digest = hashlib.sha256(canonical_bytes(review)).hexdigest()
    narrowing = totals.get("AUTH_WIDER_THAN_AGENT", 0)
    evidence = {
        "schemaVersion": SCHEMA,
        "state": "OPEN_04_001_EXIT_APPROVED",
        "authority": {
            "topic": "04_CONTROLLED_MIGRATION",
            "documentRef": refs["design"] + "#DR-04-045",
            "documentStatus": "In Review",
            "exitApprovalRef": review["reviewId"],
            "operatorRefDigest": control["operatorRefDigest"],
            "independentReviewerRefDigest": reviewer,
            "exitApprovalEvidenceDigest": review_digest,
        },
        "controlRecord": {
            "ref": refs["control"],
            "verificationRef": refs["verification"],
            "recordDigest": control_digest,
            "signatureVerified": True,
            "environmentClass": control["environmentClass"],
            "enabledModelTargetIdsEmpty": control["enabledModelTargetIds"] == [],
            "runtimeToolTrafficEnabled": control["runtimeToolTrafficEnabled"],
            "businessTrafficEnabled": control["businessTrafficEnabled"],
        },
        "observation": {
            "evidenceRef": refs["observation"],
            "windowStart": observation["windowStart"],
            "windowEnd": observation["windowEnd"],
            "trafficProfileRef": control["trafficProfileRef"],
            "controlledProfileCoverageComplete": True,
            "requestCount": request_count,
            "thresholdsRef": control["thresholdsRef"],
            "thresholdsPassed": observation["thresholdsPassed"],
            "legacyDecisionReadCount": observation["legacyDecisionReadCount"],
            "diff": {
                "AGENT_WIDER_THAN_AUTH": totals["AGENT_WIDER_THAN_AUTH"],
                "UNMAPPABLE": totals["UNMAPPABLE"],
                "AUTH_WIDER_THAN_AGENT": narrowing,
            },
            **({"narrowingApprovalRef": review["reviewId"]} if narrowing > 0 else {}),
        },
        "policy": {
            "mode": "AGENT_FIELD_AUTHORITY",
            "policyVersion": control["policyVersion"],
            "policyDigest": control["policyDigest"],
            "policyEpoch": migration["finalState"]["policyEpoch"],
            "rollbackExercisePassed": migration["rollbackExercisePassed"],
            "migrationResultRef": refs["migration"],
        },
        "consumerScan": {
            "scopeRef": refs["repository_scan"],
            "externalScopeRef": refs["external_scan"],
            "repositoryUnexpectedConsumersZero": repository_scan["repositoryUnexpectedConsumersZero"],
            "externalConsumersZero": external_scan["externalConsumersZero"],
        },
        "validation": {
            "authContractPassed": auth_contract["passed"],
            "authContractEvidenceRef": refs["auth_contract"],
            "allKnownProfilesRecomputable": True,
            "negativeTestsPassed": True,
            "independentReviewPassed": True,
            "independentReviewRef": refs["review"],
            "independentReviewVerificationRef": refs["review_verification"],
            "independentReviewEvidenceDigest": review_digest,
        },
    }
    hash_refs = {refs["design"], *[ref for name, ref in refs.items() if name != "design"]}
    evidence["sourceHashes"] = {
        ref: sha256_file(resolve_inside(root, ref)) for ref in sorted(hash_refs)
    }
    failures = verify(evidence, root)
    if failures:
        raise ValueError("assembled evidence failed exit verification: " + "; ".join(failures))
    return evidence


def _verify_operations(control, actual):
    expected = [{key: value for key, value in operation.items() if key != "fromPolicyDigest"}
                for operation in control["policyOperations"]]
    if actual != expected:
        raise ValueError("verifiedOperations do not match the signed control record")


def _verify_migration(control, migration):
    final = migration.get("finalState")
    if not isinstance(final, dict):
        raise ValueError("migration finalState is required")
    expected = {
        "policyVersion": control["policyVersion"], "policyDigest": control["policyDigest"],
        "policyEpoch": 3, "stateVersion": 3,
    }
    for key, value in expected.items():
        _equals(value, final.get(key), f"migration finalState.{key}")
    if migration.get("policyVersionCount") != 2 or migration.get("activationAuditCount") != 3 \
            or migration.get("rollbackExercisePassed") is not True:
        raise ValueError("migration result does not prove the exact rollback exercise")


def _verify_observation(control, observation):
    start = _time(observation.get("windowStart"), "observation.windowStart")
    end = _time(observation.get("windowEnd"), "observation.windowEnd")
    if not (_time(control["windowNotBefore"], "control.windowNotBefore") <= start < end
            <= _time(control["windowNotAfter"], "control.windowNotAfter")):
        raise ValueError("observation window is outside the signed control window")
    if observation.get("thresholdsPassed") is not True or observation.get("legacyDecisionReadCount") != 0:
        raise ValueError("observation thresholds or phase-C legacy reads failed")
    if observation.get("sourceDigests", {}).get(control["trafficProfileRef"]) != control["trafficProfileDigest"]:
        raise ValueError("observation traffic profile binding does not match control record")
    if observation.get("sourceDigests", {}).get(control["thresholdsRef"]) != control["thresholdsDigest"]:
        raise ValueError("observation thresholds binding does not match control record")


def _verify_repository_scan(root, scan):
    if scan.get("repositoryUnexpectedConsumersZero") is not True or scan.get("unexpectedLegacyConsumers") != []:
        raise ValueError("repository legacy consumer scan did not pass")
    _verify_nested_hashes(root, scan.get("sourceHashes"), "repository scan")


def _verify_external_scan(root, scan):
    if scan.get("externalScopeDeclaredComplete") is not True or scan.get("externalConsumersZero") is not True \
            or scan.get("legacyConsumers") != []:
        raise ValueError("external consumer scan did not pass")
    declaration = {
        "schemaVersion": "auth-field-external-consumer-scope-v0.1",
        "declarationRef": scan.get("scopeDeclarationRef"),
        "declaredByRefDigest": scan.get("declaredByRefDigest"),
        "externalScopeDeclaredComplete": scan.get("externalScopeDeclaredComplete"),
        "systems": scan.get("declaredSystems"),
    }
    _equals(hashlib.sha256(canonical_bytes(declaration)).hexdigest(), scan.get("scopeDeclarationDigest"),
            "external scope declaration digest")
    declared = scan.get("declaredSystems")
    scanned = scan.get("scannedSystems")
    if not isinstance(declared, list) or not declared or not isinstance(scanned, list) or not scanned:
        raise ValueError("external declaredSystems and scannedSystems must be non-empty lists")
    declared_identity = [(item.get("systemId"), item.get("revision")) for item in declared
                         if isinstance(item, dict)]
    scanned_identity = [(item.get("systemId"), item.get("revision")) for item in scanned
                        if isinstance(item, dict)]
    if len(declared_identity) != len(declared) or len(scanned_identity) != len(scanned) \
            or len(set(declared_identity)) != len(declared_identity) \
            or sorted(declared_identity) != sorted(scanned_identity):
        raise ValueError("external scanned systems do not exactly match declared system revisions")
    _verify_nested_hashes(root, scan.get("sourceHashes"), "external scan")


def _verify_auth_contract(root, control, evidence):
    if evidence.get("passed") is not True or evidence.get("testsRun", 0) <= 0 \
            or evidence.get("failures") != 0 or evidence.get("errors") != 0 or evidence.get("skipped") != 0:
        raise ValueError("Auth contract evidence did not pass")
    _equals(control["repositoryRevision"], evidence.get("repositoryRevision"), "Auth contract revision")
    _equals(list(AUTH_CONTRACTS), evidence.get("validatedContracts"), "Auth validated contracts")
    _verify_nested_hashes(root, evidence.get("sourceHashes"), "Auth contract sources")
    _verify_nested_hashes(root, evidence.get("reportHashes"), "Auth contract reports")


def _verify_review(root, refs, control, control_digest, review, verification,
                   control_verification, migration, observation, external_scan, auth_contract):
    if review.get("decision") != "APPROVE_OPEN_04_001_EXIT" or review.get("findings") != []:
        raise ValueError("independent review is not an approval")
    _equals(control["operatorRefDigest"], review.get("operatorRefDigest"), "review operator")
    _equals(control["approverRefDigest"], review.get("reviewerRefDigest"), "reviewer identity")
    _equals(control.get("verificationKey"), review.get("verificationKey"), "review verification key")
    reviewed_at = _time(review.get("reviewedAt"), "review.reviewedAt")
    latest_artifact = max(
        _time(control_verification.get("verifiedAt"), "verification.verifiedAt"),
        _time(migration.get("completedAt"), "migration.completedAt"),
        _time(observation.get("windowEnd"), "observation.windowEnd"),
        _time(external_scan.get("generatedAt"), "externalScan.generatedAt"),
        _time(auth_contract.get("generatedAt"), "authContract.generatedAt"),
    )
    if reviewed_at <= latest_artifact or reviewed_at > _time(control.get("validUntil"), "control.validUntil"):
        raise ValueError("independent review time is outside the signed review window")
    expected_roles = {
        "designRef": refs["design"], "controlRecordRef": refs["control"],
        "controlVerificationRef": refs["verification"], "migrationResultRef": refs["migration"],
        "observationRef": refs["observation"], "repositoryConsumerScanRef": refs["repository_scan"],
        "externalConsumerScanRef": refs["external_scan"], "authContractEvidenceRef": refs["auth_contract"],
    }
    expected_hashes = {ref: sha256_file(resolve_inside(root, ref)) for ref in expected_roles.values()}
    for role, ref in expected_roles.items():
        _equals(ref, review.get(role), f"review {role}")
    _equals(dict(sorted(expected_hashes.items())), review.get("reviewedArtifactHashes"), "review artifact hashes")
    review_digest = hashlib.sha256(canonical_bytes(review)).hexdigest()
    if verification.get("signatureVerified") is not True:
        raise ValueError("independent review signature is not verified")
    verified_at = _time(verification.get("verifiedAt"), "reviewVerification.verifiedAt")
    if verified_at < reviewed_at:
        raise ValueError("review verification predates the signed review")
    _equals(refs["review"], verification.get("reviewRef"), "review verification ref")
    _equals(review.get("reviewId"), verification.get("reviewId"), "review verification id")
    _equals(review_digest, verification.get("reviewDigest"), "review verification digest")
    _equals(control_digest, verification.get("controlRecordDigest"), "review control digest")
    _equals(review["reviewerRefDigest"], verification.get("reviewerRefDigest"), "review verification reviewer")
    _equals(review["operatorRefDigest"], verification.get("operatorRefDigest"), "review verification operator")
    _equals(review["reviewedArtifactHashes"], verification.get("reviewedArtifactHashes"),
            "review verification artifact hashes")


def _verify_nested_hashes(root, hashes, label):
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError(f"{label} nested hashes are required")
    for ref, expected in hashes.items():
        _equals(expected, sha256_file(resolve_inside(root, ref)), f"{label} hash {ref}")


def _time(value, label):
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an ISO-8601 timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _equals(expected, actual, label):
    if expected != actual:
        raise ValueError(f"{label} does not match")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    for name in ("design", "control", "verification", "migration", "observation", "repository-scan",
                 "external-scan", "auth-contract", "review", "review-verification"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    refs = {
        "design": args.design, "control": args.control, "verification": args.verification,
        "migration": args.migration, "observation": args.observation,
        "repository_scan": args.repository_scan, "external_scan": args.external_scan,
        "auth_contract": args.auth_contract, "review": args.review,
        "review_verification": args.review_verification,
    }
    try:
        atomic_write_json_new(args.output, assemble(args.root.resolve(), refs))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"OPEN-04-001 EXIT ASSEMBLY BLOCKED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
