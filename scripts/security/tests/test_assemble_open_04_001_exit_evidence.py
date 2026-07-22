import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from scripts.security.tests.open_04_001_exit_fixture import build


SCRIPT = Path(__file__).parents[1] / "assemble_open_04_001_exit_evidence.py"
SPEC = importlib.util.spec_from_file_location("assemble_open_04_001_exit_evidence", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class AssembleOpen04001ExitEvidenceTest(unittest.TestCase):
    def test_derives_complete_exit_and_rejects_migration_or_review_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            refs = build(root)
            evidence = MODULE.assemble(root, refs)
            self.assertEqual("OPEN_04_001_EXIT_APPROVED", evidence["state"])
            self.assertEqual(3, evidence["policy"]["policyEpoch"])
            self.assertEqual(200, evidence["observation"]["requestCount"])
            self.assertEqual(10, len(evidence["sourceHashes"]))

            migration_path = root / refs["migration"]
            migration = json.loads(migration_path.read_text(encoding="utf-8"))
            migration["activationAuditCount"] = 2
            migration_path.write_text(json.dumps(migration), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "migration result"):
                MODULE.assemble(root, refs)

    def test_rejects_manual_review_or_external_scope_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            refs = build(root)
            external_path = root / refs["external_scan"]
            external = json.loads(external_path.read_text(encoding="utf-8"))
            external["scopeDeclarationDigest"] = "0" * 64
            external_path.write_text(json.dumps(external), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "scope declaration digest"):
                MODULE.assemble(root, refs)

    def test_rejects_scanned_revision_or_fixed_auth_contract_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            refs = build(root)
            external_path = root / refs["external_scan"]
            external = json.loads(external_path.read_text(encoding="utf-8"))
            external["scannedSystems"][0]["revision"] = "different-revision"
            external_path.write_text(json.dumps(external), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "declared system revisions"):
                MODULE.assemble(root, refs)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            refs = build(root)
            auth_path = root / refs["auth_contract"]
            auth = json.loads(auth_path.read_text(encoding="utf-8"))
            auth["validatedContracts"] = ["tenantRef required and exact"]
            auth_path.write_text(json.dumps(auth), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "validated contracts"):
                MODULE.assemble(root, refs)


if __name__ == "__main__":
    unittest.main()
