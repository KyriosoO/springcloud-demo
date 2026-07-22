import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scan_auth_field_legacy_consumers.py"
SPEC = importlib.util.spec_from_file_location("scan_auth_field_legacy_consumers", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ScanAuthFieldLegacyConsumersTest(unittest.TestCase):
    def test_repository_passes_with_only_declared_migration_boundary(self):
        root = Path(__file__).parents[3]
        result = MODULE.scan(root)
        self.assertEqual("PASS", result["state"])
        self.assertEqual([], result["unexpectedLegacyConsumers"])
        self.assertTrue(all(result["runtimeDecisionInvariants"].values()))
        self.assertFalse(result["externalConsumersProvenZero"])

    def test_unexpected_decision_consumer_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unexpected = root / (
                "agent-service/src/main/java/com/dylan/baseline/agent/application/UnsafeDecision.java"
            )
            unexpected.parent.mkdir(parents=True)
            unexpected.write_text("class UnsafeDecision { LegacyAuthFieldView legacyView; }", encoding="utf-8")
            result = MODULE.scan(root)
            self.assertEqual("FAIL", result["state"])
            self.assertEqual(
                ["agent-service/src/main/java/com/dylan/baseline/agent/application/UnsafeDecision.java"],
                result["unexpectedLegacyConsumers"],
            )

    def test_raw_legacy_wire_field_consumer_fails_without_legacy_type_name(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unexpected = root / (
                "agent-service/src/main/java/com/dylan/baseline/agent/application/UnsafeWireConsumer.java"
            )
            unexpected.parent.mkdir(parents=True)
            unexpected.write_text(
                "class UnsafeWireConsumer { void use() { filterableFields(); displayableFields(); "
                "allowedOperators(); allowedFunctions(); } }",
                encoding="utf-8",
            )
            result = MODULE.scan(root)
            self.assertEqual("FAIL", result["state"])
            self.assertEqual(
                ["agent-service/src/main/java/com/dylan/baseline/agent/application/UnsafeWireConsumer.java"],
                result["unexpectedLegacyConsumers"],
            )


if __name__ == "__main__":
    unittest.main()
