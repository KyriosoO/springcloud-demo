import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "generate_open_04_001_auth_contract_evidence.py"
SPEC = importlib.util.spec_from_file_location("generate_open_04_001_auth_contract_evidence", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class GenerateOpen04001AuthContractEvidenceTest(unittest.TestCase):
    def test_fixed_source_inventory_exists(self):
        root = Path(__file__).parents[3]
        missing = [relative for relative in MODULE.SOURCE_REFS if not (root / relative).is_file()]
        self.assertEqual([], missing)

    def test_derives_counts_and_rejects_failed_or_missing_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "report.xml"
            source = root / "source.java"
            report.write_text("<testsuite tests='3' failures='0' errors='0' skipped='0'/>", encoding="utf-8")
            source.write_text("safe", encoding="utf-8")
            original_reports, original_sources = MODULE.REPORTS, MODULE.SOURCE_REFS
            MODULE.REPORTS, MODULE.SOURCE_REFS = ("report.xml",), ("source.java",)
            try:
                evidence = MODULE.generate(root, "a" * 40, "report-snapshots")
                self.assertTrue(evidence["passed"])
                self.assertEqual(3, evidence["testsRun"])
                self.assertEqual(
                    ["report-snapshots/report.xml"], list(evidence["reportHashes"]),
                )
                snapshot = (root / "report-snapshots/report.xml").read_text(encoding="utf-8")
                self.assertIn('<testsuite name="" tests="3" failures="0" errors="0" skipped="0" />', snapshot)
                self.assertNotIn("<properties>", snapshot)
                self.assertNotIn(str(root), snapshot)
                report.write_text("<testsuite tests='3' failures='1' errors='0' skipped='0'/>", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "not a complete pass"):
                    MODULE.generate(root, "a" * 40, "failed-report-snapshots")
                with self.assertRaisesRegex(ValueError, "full lowercase Git commit SHA"):
                    MODULE.generate(root, "short-revision", "invalid-revision-snapshots")
            finally:
                MODULE.REPORTS, MODULE.SOURCE_REFS = original_reports, original_sources


if __name__ == "__main__":
    unittest.main()
