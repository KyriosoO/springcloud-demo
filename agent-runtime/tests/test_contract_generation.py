from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from importlib.resources import files
from pathlib import Path

from agent_runtime.contracts.generated_models import ContractMetadata, RuntimeError, RuntimeReadiness
from agent_runtime.contracts.metadata import contract_readiness, load_contract_metadata
from agent_runtime.contracts.validation import (
    ContractPayloadValidationError,
    parse_contract_payload,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = ROOT / "agent-api/src/test/resources/contract/fixtures/agent-runtime"


class ContractGenerationTest(unittest.TestCase):
    def test_governance_check_is_clean(self) -> None:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/agent-contract/govern_agent_runtime_contract.py"), "--check"],
            check=True,
        )

    def test_package_resources_and_readiness(self) -> None:
        self.assertTrue(files("agent_runtime.contracts").joinpath("contract_metadata.json").is_file())
        self.assertTrue(files("agent_runtime.contracts").joinpath("contract_schema.json").is_file())
        self.assertEqual("1.0.0", load_contract_metadata().contract_version)
        self.assertEqual("CONTRACT_READY", contract_readiness().status.value)

    def test_shared_fixtures(self) -> None:
        model_types = {
            "ContractMetadata": ContractMetadata,
            "RuntimeError": RuntimeError,
            "RuntimeReadiness": RuntimeReadiness,
        }
        manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))
        for fixture in manifest["fixtures"]:
            with self.subTest(fixture=fixture["id"]):
                payload = (FIXTURE_ROOT / fixture["file"]).read_bytes()
                self.assertEqual(fixture["sha256"], hashlib.sha256(payload).hexdigest())
                if fixture["expectation"] == "ACCEPT":
                    parsed = parse_contract_payload(payload, fixture["schema"], model_types[fixture["schema"]])
                    self.assertIsInstance(parsed, model_types[fixture["schema"]])
                else:
                    with self.assertRaisesRegex(ContractPayloadValidationError, "CONTRACT_PAYLOAD_INVALID"):
                        parse_contract_payload(payload, fixture["schema"], model_types[fixture["schema"]])

    def test_duplicate_keys_and_trailing_tokens_are_rejected(self) -> None:
        for payload in (
            b'{"contractVersion":"1.0.0","contractVersion":"1.0.1"}',
            b'{} {}',
        ):
            with self.assertRaises(ContractPayloadValidationError):
                parse_contract_payload(payload, "ContractMetadata", ContractMetadata)


if __name__ == "__main__":
    unittest.main()
