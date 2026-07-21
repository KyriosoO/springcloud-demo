from __future__ import annotations

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/agent-contract/govern_agent_runtime_contract.py"
SPEC = importlib.util.spec_from_file_location("agent_contract_governance", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("contract governance script cannot be loaded")
governance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(governance)


def minimal_openapi() -> dict[str, object]:
    return {
        "components": {"schemas": {"ContractMetadata": {"additionalProperties": False, "type": "object"}}},
        "info": {"version": "1.0.0"},
        "openapi": "3.1.0",
        "paths": {"/query": {"post": {"operationId": "query.execute"}}},
    }


class ContractGovernanceTest(unittest.TestCase):
    def test_canonical_json_rejects_duplicate_keys_and_layout_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="contract-governance-json-") as directory:
            source = Path(directory) / "source.json"
            for raw in (b'{"a":1,"a":2}\n', b'{"a": 1}\n'):
                with self.subTest(raw=raw):
                    source.write_bytes(raw)
                    with self.assertRaises(RuntimeError):
                        governance.load_canonical_json(source, "CONTRACT_SOURCE_INVALID")

    def test_openapi_rejects_dangling_ref_and_derives_business_capabilities(self) -> None:
        source = minimal_openapi()
        self.assertEqual(["query.execute"], governance.validate_openapi(source))
        drifted = copy.deepcopy(source)
        drifted["components"]["schemas"]["ContractMetadata"]["properties"] = {
            "value": {"$ref": "#/components/schemas/Missing"}
        }
        with self.assertRaisesRegex(RuntimeError, "CONTRACT_REMOTE_OR_UNKNOWN_REF"):
            governance.validate_openapi(drifted)

    def test_fixture_manifest_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="contract-governance-fixture-") as directory:
            manifest = Path(directory) / "fixtures" / "manifest.json"
            manifest.parent.mkdir()
            fixture = {
                "fixtures": [{
                    "direction": "RUNTIME_TO_JAVA",
                    "expectation": "ACCEPT",
                    "file": "../escape.json",
                    "id": "escape",
                    "schema": "ContractMetadata",
                    "sha256": "0" * 64,
                }],
                "formatVersion": 1,
            }
            with patch.object(governance, "FIXTURES", manifest):
                with self.assertRaisesRegex(RuntimeError, "CONTRACT_FIXTURE_PATH_INVALID"):
                    governance.validate_fixture_manifest(fixture, minimal_openapi())

    def test_toolchain_version_drift_is_rejected(self) -> None:
        with patch.object(governance, "JAVA_GENERATOR_VERSION", "0.0.0"):
            with self.assertRaisesRegex(RuntimeError, "CONTRACT_GENERATOR_VERSION_MISMATCH"):
                governance.verify_toolchain_configuration()

    def test_yaml_parallel_authority_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="contract-governance-authority-") as directory:
            root = Path(directory)
            primary = root / "agent-api/src/main/resources/openapi/agent-runtime-openapi.json"
            parallel = root / "agent-runtime/src/main/resources/openapi/tool-openapi.yaml"
            primary.parent.mkdir(parents=True)
            parallel.parent.mkdir(parents=True)
            primary.write_text("{}", encoding="utf-8")
            parallel.write_text("openapi: 3.1.0\n", encoding="utf-8")
            with patch.object(governance, "ROOT", root), patch.object(governance, "OPENAPI", primary):
                with self.assertRaisesRegex(RuntimeError, "CONTRACT_AUTHORITY_VIOLATION"):
                    governance.verify_single_authority()


if __name__ == "__main__":
    unittest.main()
