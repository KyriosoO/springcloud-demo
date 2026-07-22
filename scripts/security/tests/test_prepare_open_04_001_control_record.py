import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "prepare_open_04_001_control_record.py"
SPEC = importlib.util.spec_from_file_location("prepare_open_04_001_control_record", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PrepareOpen04001ControlRecordTest(unittest.TestCase):
    def test_prepare_and_finalize_independent_review_binds_all_eight_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review = {
                "schemaVersion": MODULE.REVIEW_SCHEMA,
                "reviewId": "review-1",
                "reviewerRefDigest": "b" * 64,
                "operatorRefDigest": "a" * 64,
                "verificationKey": {"keyId": "key-1", "keyVersion": "v1"},
                "reviewedAt": "2026-07-22T07:00:00Z",
                "decision": "APPROVE_OPEN_04_001_EXIT",
                "findings": [],
            }
            for index, field in enumerate(MODULE.REVIEW_REF_FIELDS):
                path = root / f"artifact-{index}.json"
                path.write_text(field, encoding="utf-8")
                review[field] = path.name
            request = MODULE.prepare_review(review, root)
            self.assertEqual(8, len(request["reviewWithoutSignature"]["reviewedArtifactHashes"]))
            finalized = MODULE.finalize_review(request, "A" * 86)
            self.assertEqual("A" * 86, finalized["signature"])
            request["reviewWithoutSignature"]["reviewId"] = "drifted"
            with self.assertRaisesRegex(ValueError, "drifted"):
                MODULE.finalize_review(request, "A" * 86)

    def test_execution_bindings_are_derived_from_actual_non_secret_inputs(self):
        first = MODULE.execution_bindings(
            b"public-key", "approval-key", "v1", "a" * 64,
            "jdbc:mysql://127.0.0.1:3306/springboot_db", "root")
        self.assertEqual(
            "b64692fe432ff5a2a129553340bbda8fd790051dc42e4cc9d71cf26268917d77",
            first["configurationDigest"],
        )
        self.assertEqual(
            "3fb1e9fa612179b9631de90a918bc3d8110f08e06df0a61a3e9ef433c54fef4a",
            first["databaseRefDigest"],
        )
        self.assertNotEqual(
            first["configurationDigest"],
            MODULE.execution_bindings(
                b"different-key", "approval-key", "v1", "a" * 64,
                "jdbc:mysql://127.0.0.1:3306/springboot_db", "root")["configurationDigest"],
        )
        self.assertNotEqual(
            first["databaseRefDigest"],
            MODULE.execution_bindings(
                b"public-key", "approval-key", "v1", "a" * 64,
                "jdbc:mysql://127.0.0.1:3307/springboot_db", "root")["databaseRefDigest"],
        )

    def test_prepare_binds_all_seven_refs_and_finalize_detects_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            refs = {}
            for name in ("policy", "drill", "traffic", "thresholds", "runner", "scanner", "verifier"):
                path = root / f"{name}.json"
                path.write_text(name, encoding="utf-8")
                refs[name] = path.name
            spec = self.spec(refs, root)
            request = MODULE.prepare(spec, root)
            self.assertEqual(set(refs.values()), set(request["controlRecordWithoutSignature"]["sourceHashes"]))
            record = MODULE.finalize(request, "A" * 86)
            self.assertEqual("A" * 86, record["signature"])
            request["controlRecordWithoutSignature"]["recordId"] = "drifted"
            with self.assertRaisesRegex(ValueError, "drifted"):
                MODULE.finalize(request, "A" * 86)

    def test_rejects_privileged_flags_same_actor_and_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            refs = {}
            for name in ("policy", "drill", "traffic", "thresholds", "runner", "scanner", "verifier"):
                path = root / f"{name}.json"
                path.write_text(name, encoding="utf-8")
                refs[name] = path.name
            spec = self.spec(refs, root)
            spec["businessTrafficEnabled"] = True
            with self.assertRaisesRegex(ValueError, "flags"):
                MODULE.prepare(spec, root)
            spec = self.spec(refs, root)
            spec["approverRefDigest"] = spec["operatorRefDigest"]
            with self.assertRaisesRegex(ValueError, "different"):
                MODULE.prepare(spec, root)
            spec = self.spec(refs, root)
            spec["exitVerifierRef"] = "../outside"
            with self.assertRaisesRegex(ValueError, "escapes"):
                MODULE.prepare(spec, root)

    @staticmethod
    def spec(refs, root):
        import hashlib

        traffic_digest = hashlib.sha256((root / refs["traffic"]).read_bytes()).hexdigest()
        thresholds_digest = hashlib.sha256((root / refs["thresholds"]).read_bytes()).hexdigest()
        policy_digest = hashlib.sha256((root / refs["policy"]).read_bytes()).hexdigest()
        drill_digest = hashlib.sha256((root / refs["drill"]).read_bytes()).hexdigest()
        return {
            "schemaVersion": MODULE.CONTROL_SCHEMA,
            "recordId": "control-1",
            "environmentClass": "NON_PRODUCTION_CONTROLLED",
            "repositoryRevision": "revision-1",
            "configurationDigest": "c" * 64,
            "databaseRefDigest": "d" * 64,
            "policyVersion": "policy-v1",
            "policyPayloadRef": refs["policy"],
            "policyDigest": policy_digest,
            "policySchemaVersion": "agent-field-policy-v0.1",
            "rollbackExercisePolicyVersion": "policy-v1-drill",
            "rollbackExercisePolicyPayloadRef": refs["drill"],
            "rollbackExercisePolicyDigest": drill_digest,
            "rollbackExercisePolicySchemaVersion": "agent-field-policy-v0.1",
            "trafficProfileRef": refs["traffic"],
            "trafficProfileDigest": traffic_digest,
            "thresholdsRef": refs["thresholds"],
            "thresholdsDigest": thresholds_digest,
            "observationRunnerRef": refs["runner"],
            "consumerScannerRef": refs["scanner"],
            "exitVerifierRef": refs["verifier"],
            "phaseSequence": ["DUAL_READ_ENFORCE_INTERSECTION", "AGENT_FIELD_AUTHORITY"],
            "policyOperations": [
                {"operation": "CREATE_AND_ACTIVATE", "fromPolicyDigest": None,
                 "toPolicyDigest": policy_digest, "changeClass": "INITIAL", "expectedStateVersion": 0},
                {"operation": "CREATE_AND_ACTIVATE", "fromPolicyDigest": policy_digest,
                 "toPolicyDigest": drill_digest, "changeClass": "TIGHTENING", "expectedStateVersion": 1},
                {"operation": "ROLLBACK", "fromPolicyDigest": drill_digest,
                 "toPolicyDigest": policy_digest, "changeClass": "EXPANSION", "expectedStateVersion": 2},
            ],
            "enabledModelTargetIds": [],
            "runtimeToolTrafficEnabled": False,
            "businessTrafficEnabled": False,
            "operatorRefDigest": "a" * 64,
            "approverRefDigest": "b" * 64,
            "verificationKey": {"keyId": "reviewer", "keyVersion": "v1"},
            "issuedAt": "2026-07-22T07:00:00Z",
            "windowNotBefore": "2026-07-22T07:30:00Z",
            "windowNotAfter": "2026-07-22T09:00:00Z",
            "validUntil": "2026-07-22T10:00:00Z",
        }


if __name__ == "__main__":
    unittest.main()
