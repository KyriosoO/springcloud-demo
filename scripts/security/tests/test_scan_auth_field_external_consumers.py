import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scan_auth_field_external_consumers.py"
SPEC = importlib.util.spec_from_file_location("scan_auth_field_external_consumers", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ScanAuthFieldExternalConsumersTest(unittest.TestCase):
    def test_complete_clean_inventory_passes_and_incomplete_or_hit_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            system = root / "candidate"
            system.mkdir()
            source = system / "config.yml"
            source.write_text("safe: true", encoding="utf-8")
            scope = self.scope(True)
            result, passed = MODULE.scan(scope, root)
            self.assertTrue(passed)
            self.assertTrue(result["externalConsumersZero"])

            scope["externalScopeDeclaredComplete"] = False
            self.assertFalse(MODULE.scan(scope, root)[1])
            scope["externalScopeDeclaredComplete"] = True
            source.write_text("filterableFields: [name]", encoding="utf-8")
            result, passed = MODULE.scan(scope, root)
            self.assertFalse(passed)
            self.assertEqual("filterableFields", result["legacyConsumers"][0]["token"])

    @staticmethod
    def scope(complete):
        return {
            "schemaVersion": MODULE.SCHEMA,
            "declarationRef": "scope-1",
            "declaredByRefDigest": "a" * 64,
            "externalScopeDeclaredComplete": complete,
            "systems": [{
                "systemId": "candidate", "kind": "DEPLOYMENT_CANDIDATE", "rootRef": "candidate",
                "revision": "revision-1", "includeGlobs": ["**/*.yml"],
            }],
        }


if __name__ == "__main__":
    unittest.main()
