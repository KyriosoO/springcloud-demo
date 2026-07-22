from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.security.open_04_001_evidence_io import AUTH_CONTRACTS, canonical_bytes, sha256_file


OPERATOR = "a" * 64
REVIEWER = "b" * 64
REVISION = "c" * 40
CONFIG = "c" * 64
DATABASE = "d" * 64


def build(root: Path) -> dict[str, str]:
    def write(relative, value):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, dict):
            path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        else:
            path.write_text(value, encoding="utf-8")
        return relative

    design = write("04.md", "design")
    policy = write("policy.json", "{}")
    drill = write("drill.json", "{\"drill\":true}")
    traffic = write("traffic.json", "traffic")
    thresholds = write("thresholds.json", "thresholds")
    runner = write("runner.py", "runner")
    scanner = write("scanner.py", "scanner")
    exit_verifier = write("exit.py", "exit")
    primary_digest = sha256_file(root / policy)
    drill_digest = sha256_file(root / drill)
    operations = [
        {"operation": "CREATE_AND_ACTIVATE", "fromPolicyDigest": None, "toPolicyDigest": primary_digest,
         "changeClass": "INITIAL", "expectedStateVersion": 0},
        {"operation": "CREATE_AND_ACTIVATE", "fromPolicyDigest": primary_digest, "toPolicyDigest": drill_digest,
         "changeClass": "TIGHTENING", "expectedStateVersion": 1},
        {"operation": "ROLLBACK", "fromPolicyDigest": drill_digest, "toPolicyDigest": primary_digest,
         "changeClass": "EXPANSION", "expectedStateVersion": 2},
    ]
    source_refs = [policy, drill, traffic, thresholds, runner, scanner, exit_verifier]
    control = {
        "schemaVersion": "open-04-001-migration-control-v0.1",
        "recordId": "control-1",
        "environmentClass": "NON_PRODUCTION_CONTROLLED",
        "repositoryRevision": REVISION,
        "configurationDigest": CONFIG,
        "databaseRefDigest": DATABASE,
        "policyVersion": "policy-v1",
        "policyPayloadRef": policy,
        "policyDigest": primary_digest,
        "policySchemaVersion": "agent-field-policy-v0.1",
        "rollbackExercisePolicyVersion": "drill-v1",
        "rollbackExercisePolicyPayloadRef": drill,
        "rollbackExercisePolicyDigest": drill_digest,
        "rollbackExercisePolicySchemaVersion": "agent-field-policy-v0.1",
        "trafficProfileRef": traffic,
        "trafficProfileDigest": sha256_file(root / traffic),
        "thresholdsRef": thresholds,
        "thresholdsDigest": sha256_file(root / thresholds),
        "observationRunnerRef": runner,
        "consumerScannerRef": scanner,
        "exitVerifierRef": exit_verifier,
        "phaseSequence": ["DUAL_READ_ENFORCE_INTERSECTION", "AGENT_FIELD_AUTHORITY"],
        "policyOperations": operations,
        "enabledModelTargetIds": [],
        "runtimeToolTrafficEnabled": False,
        "businessTrafficEnabled": False,
        "operatorRefDigest": OPERATOR,
        "approverRefDigest": REVIEWER,
        "verificationKey": {"keyId": "key-1", "keyVersion": "v1"},
        "issuedAt": "2026-07-22T05:00:00Z",
        "windowNotBefore": "2026-07-22T05:30:00Z",
        "windowNotAfter": "2026-07-22T07:30:00Z",
        "validUntil": "2026-07-22T08:00:00Z",
        "sourceHashes": {ref: sha256_file(root / ref) for ref in sorted(source_refs)},
        "signature": "A" * 86,
    }
    control_ref = write("control.json", control)
    control_digest = hashlib.sha256(canonical_bytes(control)).hexdigest()
    verified_operations = [{key: value for key, value in operation.items() if key != "fromPolicyDigest"}
                           for operation in operations]
    verification = {
        "schemaVersion": "open-04-001-control-verification-v0.1",
        "verifiedAt": "2026-07-22T05:40:00Z",
        "signatureVerified": True,
        "repositoryRevision": REVISION,
        "configurationDigest": CONFIG,
        "databaseRefDigest": DATABASE,
        "controlRecordRef": control_ref,
        "approvalRef": "control-1",
        "evidenceDigest": control_digest,
        "operatorRefDigest": OPERATOR,
        "approverRefDigest": REVIEWER,
        "validUntil": "2026-07-22T08:00:00Z",
        "verifiedOperations": verified_operations,
    }
    verification_ref = write("control-verification.json", verification)
    migration = {
        "schemaVersion": "open-04-001-controlled-migration-result-v0.1",
        "startedAt": "2026-07-22T05:45:00Z",
        "completedAt": "2026-07-22T06:00:00Z",
        "repositoryRevision": REVISION,
        "configurationDigest": CONFIG,
        "databaseRefDigest": DATABASE,
        "controlRecordRef": control_ref,
        "controlRecordId": "control-1",
        "controlRecordDigest": control_digest,
        "signatureVerified": True,
        "operatorRefDigest": OPERATOR,
        "approverRefDigest": REVIEWER,
        "verifiedOperations": verified_operations,
        "completedStepsAtStart": 0,
        "steps": [{"step": index + 1} for index in range(3)],
        "finalState": {"policyVersion": "policy-v1", "policyDigest": primary_digest,
                       "policyEpoch": 3, "stateVersion": 3},
        "policyVersionCount": 2,
        "activationAuditCount": 3,
        "rollbackExercisePassed": True,
    }
    migration_ref = write("migration.json", migration)
    observation = {
        "schemaVersion": "open-04-001-controlled-observation-v0.1",
        "windowStart": "2026-07-22T06:05:00Z",
        "windowEnd": "2026-07-22T06:10:00Z",
        "generatedAt": "2026-07-22T06:10:00Z",
        "sourceDigests": {traffic: control["trafficProfileDigest"], thresholds: control["thresholdsDigest"]},
        "profiles": [{"permissionCode": "agent-admin", "phaseB": {"resolutionCount": 100},
                      "phaseC": {"resolutionCount": 100}}],
        "totals": {"EQUAL": 200, "AUTH_WIDER_THAN_AGENT": 0,
                   "AGENT_WIDER_THAN_AUTH": 0, "UNMAPPABLE": 0},
        "legacyDecisionReadCount": 0,
        "negativeCases": [{"attemptCount": 1, "rejectedCount": 1} for _ in range(5)],
        "thresholdsPassed": True,
    }
    observation_ref = write("observation.json", observation)
    repository_source = write("repository-source.java", "safe")
    repository_scan = {
        "schemaVersion": "auth-field-legacy-consumer-scan-v0.1",
        "repositoryUnexpectedConsumersZero": True,
        "unexpectedLegacyConsumers": [],
        "runtimeDecisionInvariants": {"dualReadIsOnlyLegacyDecisionMode": True},
        "sourceHashes": {repository_source: sha256_file(root / repository_source)},
    }
    repository_scan_ref = write("repository-scan.json", repository_scan)
    external_source = write("external-source.yml", "safe")
    declared_systems = [{"systemId": "candidate", "kind": "DEPLOYMENT_CANDIDATE", "rootRef": ".",
                         "revision": REVISION, "includeGlobs": ["external-source.yml"]}]
    declaration = {
        "schemaVersion": "auth-field-external-consumer-scope-v0.1",
        "declarationRef": "scope-1",
        "declaredByRefDigest": "e" * 64,
        "externalScopeDeclaredComplete": True,
        "systems": declared_systems,
    }
    external_scan = {
        "schemaVersion": "auth-field-external-consumer-scan-v0.1",
        "generatedAt": "2026-07-22T06:20:00Z",
        "scopeDeclarationRef": "scope-1",
        "scopeDeclarationDigest": hashlib.sha256(canonical_bytes(declaration)).hexdigest(),
        "declaredByRefDigest": "e" * 64,
        "externalScopeDeclaredComplete": True,
        "declaredSystems": declared_systems,
        "scannedSystems": [{"systemId": "candidate", "kind": "DEPLOYMENT_CANDIDATE",
                            "revision": REVISION, "matchedFileCount": 1, "legacyConsumers": []}],
        "legacyConsumers": [],
        "externalConsumersZero": True,
        "sourceHashes": {external_source: sha256_file(root / external_source)},
    }
    external_scan_ref = write("external-scan.json", external_scan)
    auth_source = write("auth-source.java", "auth")
    auth_report = write("TEST-auth.xml", "<testsuite tests='1' failures='0' errors='0' skipped='0'/>")
    auth_contract = {
        "schemaVersion": "open-04-001-auth-contract-verification-v0.1",
        "generatedAt": "2026-07-22T06:25:00Z",
        "repositoryRevision": REVISION,
        "passed": True, "testsRun": 1, "failures": 0, "errors": 0, "skipped": 0,
        "validatedContracts": list(AUTH_CONTRACTS),
        "reportHashes": {auth_report: sha256_file(root / auth_report)},
        "sourceHashes": {auth_source: sha256_file(root / auth_source)},
    }
    auth_contract_ref = write("auth-contract.json", auth_contract)
    role_refs = {
        "designRef": design,
        "controlRecordRef": control_ref,
        "controlVerificationRef": verification_ref,
        "migrationResultRef": migration_ref,
        "observationRef": observation_ref,
        "repositoryConsumerScanRef": repository_scan_ref,
        "externalConsumerScanRef": external_scan_ref,
        "authContractEvidenceRef": auth_contract_ref,
    }
    review = {
        "schemaVersion": "open-04-001-independent-exit-review-v0.1",
        "reviewId": "review-1", "reviewerRefDigest": REVIEWER, "operatorRefDigest": OPERATOR,
        "verificationKey": {"keyId": "key-1", "keyVersion": "v1"},
        "reviewedAt": "2026-07-22T07:00:00Z",
        "decision": "APPROVE_OPEN_04_001_EXIT", "findings": [],
        **role_refs,
        "reviewedArtifactHashes": {ref: sha256_file(root / ref) for ref in sorted(role_refs.values())},
        "signature": "B" * 86,
    }
    review_ref = write("review.json", review)
    review_digest = hashlib.sha256(canonical_bytes(review)).hexdigest()
    review_verification = {
        "schemaVersion": "open-04-001-independent-review-verification-v0.1",
        "verifiedAt": "2026-07-22T07:05:00Z", "signatureVerified": True,
        "reviewRef": review_ref, "reviewId": "review-1", "reviewDigest": review_digest,
        "reviewerRefDigest": REVIEWER, "operatorRefDigest": OPERATOR,
        "controlRecordDigest": control_digest,
        "reviewedArtifactHashes": review["reviewedArtifactHashes"],
    }
    review_verification_ref = write("review-verification.json", review_verification)
    return {
        "design": design, "control": control_ref, "verification": verification_ref,
        "migration": migration_ref, "observation": observation_ref,
        "repository_scan": repository_scan_ref, "external_scan": external_scan_ref,
        "auth_contract": auth_contract_ref, "review": review_ref,
        "review_verification": review_verification_ref,
    }
