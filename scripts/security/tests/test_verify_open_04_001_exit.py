import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from scripts.security.assemble_open_04_001_exit_evidence import assemble
from scripts.security.tests.open_04_001_exit_fixture import build


SCRIPT = Path(__file__).parents[1] / "verify_open_04_001_exit.py"
SPEC = importlib.util.spec_from_file_location("verify_open_04_001_exit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class VerifyOpen04001ExitTest(unittest.TestCase):
    def test_complete_independent_evidence_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = assemble(root, build(root))
            self.assertEqual([], MODULE.verify(evidence, root))

    def test_pending_authority_metrics_and_external_scan_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = self.write_bound_files(root)
            (root / "consumer-source.java").write_text("drifted", encoding="utf-8")
            (root / "external-consumer-scan.json").write_text(json.dumps({
                "schemaVersion": "auth-field-external-consumer-scan-v0.1",
                "externalConsumersZero": True,
                "externalScopeDeclaredComplete": False,
                "scannedSystems": [],
                "legacyConsumers": [],
                "sourceHashes": {},
            }), encoding="utf-8")
            evidence = self.complete_evidence()
            evidence["authority"]["documentStatus"] = "Missing"
            evidence["observation"]["diff"]["UNMAPPABLE"] = 1
            evidence["observation"]["diff"]["AGENT_WIDER_THAN_AUTH"] = False
            evidence["observation"]["diff"]["AUTH_WIDER_THAN_AGENT"] = 2
            evidence["consumerScan"]["externalConsumersZero"] = False
            evidence["observation"]["legacyDecisionReadCount"] = 1
            evidence["sourceHashes"] = {name: self.sha(path) for name, path in files.items()}
            failures = MODULE.verify(evidence, root)
            self.assertTrue(any("authority.documentStatus" in item for item in failures))
            self.assertTrue(any("UNMAPPABLE" in item for item in failures))
            self.assertTrue(any("AGENT_WIDER_THAN_AUTH" in item for item in failures))
            self.assertTrue(any("narrowingApprovalRef" in item for item in failures))
            self.assertTrue(any("externalConsumersZero" in item for item in failures))
            self.assertTrue(any("external scope" in item for item in failures))
            self.assertTrue(any("scannedSystems" in item for item in failures))
            self.assertTrue(any("legacyDecisionReadCount" in item for item in failures))
            self.assertTrue(any("consumerScan.sourceHashes" in item for item in failures))

    def write_bound_files(self, root):
        source = root / "source.txt"
        source.write_text("bound", encoding="utf-8")
        authority = root / "04.md"
        authority.write_text("in review", encoding="utf-8")
        control = root / "control-record.json"
        control.write_text("signed", encoding="utf-8")
        control_verification = root / "control-verification.json"
        control_verification.write_text("verified", encoding="utf-8")
        observation = root / "observation.json"
        observation.write_text(json.dumps(self.observation()), encoding="utf-8")
        consumer_source = root / "consumer-source.java"
        consumer_source.write_text("safe", encoding="utf-8")
        consumer = root / "consumer-scan.json"
        consumer.write_text(json.dumps(self.consumer_scan(consumer_source)), encoding="utf-8")
        external_source = root / "external-source.yml"
        external_source.write_text("safe", encoding="utf-8")
        external = root / "external-consumer-scan.json"
        external.write_text(json.dumps(self.external_consumer_scan(external_source)), encoding="utf-8")
        return {
            "source.txt": source,
            "04.md": authority,
            "control-record.json": control,
            "control-verification.json": control_verification,
            "observation.json": observation,
            "consumer-scan.json": consumer,
            "external-consumer-scan.json": external,
        }

    @staticmethod
    def observation():
        return {
            "schemaVersion": "open-04-001-controlled-observation-v0.1",
            "thresholdsPassed": True,
            "legacyDecisionReadCount": 0,
            "profiles": [{
                "phaseB": {"resolutionCount": 100},
                "phaseC": {"resolutionCount": 100},
            }],
            "totals": {"AGENT_WIDER_THAN_AUTH": 0, "UNMAPPABLE": 0},
            "negativeCases": [
                {"attemptCount": 1, "rejectedCount": 1} for _ in range(5)
            ],
        }

    @staticmethod
    def external_consumer_scan(source):
        return {
            "schemaVersion": "auth-field-external-consumer-scan-v0.1",
            "externalScopeDeclaredComplete": True,
            "externalConsumersZero": True,
            "scannedSystems": [{"systemId": "candidate", "legacyConsumers": []}],
            "legacyConsumers": [],
            "sourceHashes": {"external-source.yml": hashlib.sha256(source.read_bytes()).hexdigest()},
        }

    @staticmethod
    def consumer_scan(source):
        return {
            "schemaVersion": "auth-field-legacy-consumer-scan-v0.1",
            "repositoryUnexpectedConsumersZero": True,
            "unexpectedLegacyConsumers": [],
            "runtimeDecisionInvariants": {"dualReadIsOnlyLegacyDecisionMode": True},
            "sourceHashes": {"consumer-source.java": hashlib.sha256(source.read_bytes()).hexdigest()},
        }

    @staticmethod
    def complete_evidence():
        return {
            "schemaVersion": MODULE.SCHEMA,
            "state": "OPEN_04_001_EXIT_APPROVED",
            "authority": {
                "topic": "04_CONTROLLED_MIGRATION",
                "documentRef": "04.md#DR-04-045",
                "documentStatus": "In Review",
                "exitApprovalRef": "approval-1",
                "operatorRefDigest": "a" * 64,
                "independentReviewerRefDigest": "b" * 64,
                "exitApprovalEvidenceDigest": "c" * 64,
            },
            "controlRecord": {
                "ref": "control-record.json",
                "verificationRef": "control-verification.json",
                "recordDigest": "e" * 64,
                "signatureVerified": True,
                "environmentClass": "NON_PRODUCTION_CONTROLLED",
                "enabledModelTargetIdsEmpty": True,
                "runtimeToolTrafficEnabled": False,
                "businessTrafficEnabled": False,
            },
            "observation": {
                "evidenceRef": "observation.json",
                "windowStart": "2026-07-22T00:00:00Z",
                "windowEnd": "2026-07-22T01:00:00Z",
                "trafficProfileRef": "profile-1",
                "controlledProfileCoverageComplete": True,
                "requestCount": 200,
                "thresholdsRef": "thresholds-1",
                "thresholdsPassed": True,
                "legacyDecisionReadCount": 0,
                "diff": {"AGENT_WIDER_THAN_AUTH": 0, "UNMAPPABLE": 0, "AUTH_WIDER_THAN_AGENT": 0},
            },
            "policy": {
                "mode": "AGENT_FIELD_AUTHORITY",
                "policyVersion": "policy-v1",
                "policyDigest": "d" * 64,
                "policyEpoch": 1,
                "rollbackExercisePassed": True,
            },
            "consumerScan": {
                "scopeRef": "consumer-scan.json",
                "externalScopeRef": "external-consumer-scan.json",
                "repositoryUnexpectedConsumersZero": True,
                "externalConsumersZero": True,
            },
            "validation": {
                "authContractPassed": True,
                "allKnownProfilesRecomputable": True,
                "negativeTestsPassed": True,
                "independentReviewPassed": True,
                "independentReviewRef": "review-1",
                "independentReviewEvidenceDigest": "f" * 64,
            },
        }

    @staticmethod
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
