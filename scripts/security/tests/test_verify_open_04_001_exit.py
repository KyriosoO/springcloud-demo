import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "verify_open_04_001_exit.py"
SPEC = importlib.util.spec_from_file_location("verify_open_04_001_exit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class VerifyOpen04001ExitTest(unittest.TestCase):
    def test_complete_independent_evidence_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.txt"
            source.write_text("bound", encoding="utf-8")
            authority = root / "12A.md"
            authority.write_text("approved", encoding="utf-8")
            consumer = root / "consumer-scan.json"
            external_consumer = root / "external-consumer-scan.json"
            external_consumer.write_text(json.dumps(self.external_consumer_scan()), encoding="utf-8")
            consumer_source = root / "consumer-source.java"
            consumer_source.write_text("safe", encoding="utf-8")
            consumer.write_text(
                json.dumps(self.consumer_scan(consumer_source)), encoding="utf-8"
            )
            evidence = self.complete_evidence()
            evidence["sourceHashes"] = {
                "source.txt": hashlib.sha256(source.read_bytes()).hexdigest(),
                "12A.md": hashlib.sha256(authority.read_bytes()).hexdigest(),
                "consumer-scan.json": hashlib.sha256(consumer.read_bytes()).hexdigest(),
                "external-consumer-scan.json": hashlib.sha256(external_consumer.read_bytes()).hexdigest(),
            }
            self.assertEqual([], MODULE.verify(evidence, root))

    def test_pending_authority_metrics_and_external_scan_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.txt"
            source.write_text("bound", encoding="utf-8")
            authority = root / "12A.md"
            authority.write_text("approved", encoding="utf-8")
            consumer = root / "consumer-scan.json"
            external_consumer = root / "external-consumer-scan.json"
            external_consumer.write_text(
                json.dumps({"externalConsumersZero": True, "scannedSystems": []}),
                encoding="utf-8",
            )
            consumer_source = root / "consumer-source.java"
            consumer_source.write_text("safe", encoding="utf-8")
            consumer.write_text(
                json.dumps(self.consumer_scan(consumer_source)), encoding="utf-8"
            )
            consumer_source.write_text("drifted", encoding="utf-8")
            evidence = self.complete_evidence()
            evidence["authority"]["documentStatus"] = "Missing"
            evidence["observation"]["diff"]["UNMAPPABLE"] = 1
            evidence["observation"]["diff"]["AGENT_WIDER_THAN_AUTH"] = False
            evidence["observation"]["diff"]["AUTH_WIDER_THAN_AGENT"] = 2
            evidence["consumerScan"]["externalConsumersZero"] = False
            evidence["observation"]["legacyDecisionReadCount"] = 1
            evidence["sourceHashes"] = {
                "source.txt": hashlib.sha256(b"changed").hexdigest(),
                "12A.md": hashlib.sha256(authority.read_bytes()).hexdigest(),
                "consumer-scan.json": hashlib.sha256(consumer.read_bytes()).hexdigest(),
                "external-consumer-scan.json": hashlib.sha256(external_consumer.read_bytes()).hexdigest(),
            }
            failures = MODULE.verify(evidence, root)
            self.assertTrue(any("authority.documentStatus" in item for item in failures))
            self.assertTrue(any("UNMAPPABLE" in item for item in failures))
            self.assertTrue(any("AGENT_WIDER_THAN_AUTH" in item for item in failures))
            self.assertTrue(any("narrowingApprovalRef" in item for item in failures))
            self.assertTrue(any("externalConsumersZero" in item for item in failures))
            self.assertTrue(any("unsupported scan evidence schema" in item for item in failures))
            self.assertTrue(any("scannedSystems" in item for item in failures))
            self.assertTrue(any("legacyDecisionReadCount" in item for item in failures))
            self.assertTrue(any("digest mismatch" in item for item in failures))
            self.assertTrue(any("consumerScan.sourceHashes" in item for item in failures))

    @staticmethod
    def external_consumer_scan():
        return {
            "schemaVersion": "auth-field-external-consumer-scan-v0.1",
            "externalConsumersZero": True,
            "scannedSystems": ["auth-service", "consumer-a"],
        }

    @staticmethod
    def consumer_scan(source):
        return {
            "schemaVersion": "auth-field-legacy-consumer-scan-v0.1",
            "repositoryUnexpectedConsumersZero": True,
            "unexpectedLegacyConsumers": [],
            "runtimeDecisionInvariants": {
                "dualReadIsOnlyLegacyDecisionMode": True,
            },
            "sourceHashes": {
                "consumer-source.java": hashlib.sha256(source.read_bytes()).hexdigest(),
            },
        }

    @staticmethod
    def complete_evidence():
        return {
            "schemaVersion": MODULE.SCHEMA,
            "state": "OPEN_04_001_EXIT_APPROVED",
            "authority": {
                "topic": "12A",
                "documentRef": "12A.md#approval",
                "documentStatus": "Approved",
                "exitApprovalRef": "approval-1",
                "operatorRefDigest": "a" * 64,
                "independentReviewerRefDigest": "b" * 64,
                "exitApprovalEvidenceDigest": "c" * 64,
            },
            "observation": {
                "windowStart": "2026-07-22T00:00:00Z",
                "windowEnd": "2026-07-22T01:00:00Z",
                "trafficProfileRef": "profile-1",
                "representativeTraffic": True,
                "requestCount": 100,
                "thresholdsRef": "thresholds-1",
                "thresholdsPassed": True,
                "legacyDecisionReadCount": 0,
                "diff": {
                    "AGENT_WIDER_THAN_AUTH": 0,
                    "UNMAPPABLE": 0,
                    "AUTH_WIDER_THAN_AGENT": 0,
                },
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


if __name__ == "__main__":
    unittest.main()
