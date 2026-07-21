from __future__ import annotations

import hashlib
import json
import os
import copy
import subprocess
import sys
import tempfile
import unittest
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator
from agent_runtime.contracts.generated_models import ContractMetadata, RuntimeError, RuntimeReadiness
from agent_runtime.contracts.metadata import (
    _parse_contract_metadata,
    _reject_duplicate_keys,
    contract_readiness,
    load_contract_metadata,
)
from agent_runtime.contracts.validation import (
    _FORMAT_CHECKER,
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

    def test_malformed_packaged_metadata_is_rejected_with_stable_code(self) -> None:
        valid = json.loads(
            (ROOT / "agent-runtime/src/agent_runtime/contracts/contract_metadata.json")
            .read_text(encoding="utf-8")
        )
        malformed = []
        for field, value in (
            ("capabilities", None),
            ("capabilities", ["b", "a"]),
            ("contractFingerprint", "sha256:" + "b" * 64),
            ("lockFormatVersion", 2),
        ):
            payload = copy.deepcopy(valid)
            payload[field] = value
            malformed.append(payload)
        payload = copy.deepcopy(valid)
        payload["unexpected"] = True
        malformed.append(payload)
        for payload in malformed:
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(ValueError, "^CONTRACT_METADATA_INVALID$"):
                    _parse_contract_metadata(payload)
        with self.assertRaisesRegex(ValueError, "^CONTRACT_METADATA_INVALID$"):
            json.loads('{"lockFormatVersion":1,"lockFormatVersion":2}', object_pairs_hook=_reject_duplicate_keys)

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
                if fixture.get("stage", "PARSE") == "COMPATIBILITY":
                    parsed = parse_contract_payload(payload, fixture["schema"], model_types[fixture["schema"]])
                    self.assertIsInstance(parsed, model_types[fixture["schema"]])
                elif fixture["expectation"] == "ACCEPT":
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

    def test_isolated_conformance_schema(self) -> None:
        schema = json.loads(
            (ROOT / "agent-api/src/test/resources/contract/conformance/m1-conformance-schema.json")
            .read_text(encoding="utf-8")
        )
        validator = Draft202012Validator(schema, format_checker=_FORMAT_CHECKER)
        validator.validate(
            {"durationMs": 0, "kind": "TYPE_A", "occurredAt": "2026-07-21T00:00:00Z", "valueA": "ok"}
        )
        invalid_payloads = (
            {"durationMs": 0, "kind": "UNKNOWN", "occurredAt": "2026-07-21T00:00:00Z"},
            {"durationMs": -1, "kind": "TYPE_A", "occurredAt": "2026-07-21T00:00:00Z", "valueA": "x"},
            {"durationMs": 1.5, "kind": "TYPE_A", "occurredAt": "2026-07-21T00:00:00Z", "valueA": "x"},
            {"durationMs": 1, "kind": "TYPE_A", "occurredAt": "2026-07-21T00:00:00+08:00", "valueA": "x"},
            {"durationMs": 1, "kind": "TYPE_A", "occurredAt": "2026-13-40T00:00:00Z", "valueA": "x"},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                self.assertTrue(list(validator.iter_errors(payload)))

    def test_wheel_contains_exact_contract_resources(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agent-runtime-wheel-") as directory:
            root = Path(directory)
            wheel_dir = root / "wheel"
            install_dir = root / "install"
            wheel_dir.mkdir()
            install_dir.mkdir()
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "wheel",
                    "--no-deps",
                    "--no-build-isolation",
                    "--wheel-dir",
                    str(wheel_dir),
                    str(ROOT / "agent-runtime"),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            wheel = next(wheel_dir.glob("agent_runtime-*.whl"))
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--no-deps",
                    "--no-index",
                    "--target",
                    str(install_dir),
                    str(wheel),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            script = (
                "import hashlib; from importlib.resources import files; "
                "root=files('agent_runtime.contracts'); "
                "print(hashlib.sha256(root.joinpath('contract_metadata.json').read_bytes()).hexdigest()); "
                "print(hashlib.sha256(root.joinpath('contract_schema.json').read_bytes()).hexdigest())"
            )
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(install_dir)
            completed = subprocess.run(
                [sys.executable, "-S", "-c", script],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            actual_hashes = completed.stdout.splitlines()
            expected_hashes = [
                hashlib.sha256(
                    (ROOT / "agent-runtime/src/agent_runtime/contracts/contract_metadata.json").read_bytes()
                ).hexdigest(),
                hashlib.sha256(
                    (ROOT / "agent-runtime/src/agent_runtime/contracts/contract_schema.json").read_bytes()
                ).hexdigest(),
            ]
            self.assertEqual(expected_hashes, actual_hashes)


if __name__ == "__main__":
    unittest.main()
