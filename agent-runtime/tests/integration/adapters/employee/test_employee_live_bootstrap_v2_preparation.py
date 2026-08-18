from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tests.integration.adapters.business_egress_live_bootstrap import BootstrapContractError
from tests.integration.adapters.employee.live_bootstrap_v2 import (
    EMPLOYEE_BUILD_COMMAND,
    EMPLOYEE_EXECUTABLE_ASSET_PATHS,
    validate_prepared_assets,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _prepared_fixture(root: Path) -> tuple[Path, Path]:
    candidate_manifest = root / "candidate/manifest.json"
    candidate_authorization = root / "candidate/authorization.json"
    asset = root / "agent-runtime/wrapper.py"
    history = root / "history/result.json"
    _write(candidate_manifest, "candidate-manifest")
    _write(candidate_authorization, "candidate-authorization")
    _write(asset, "wrapper-source")
    _write(history, "immutable-history")
    for relative in EMPLOYEE_EXECUTABLE_ASSET_PATHS:
        _write(root / relative, f"executable:{relative}")

    manifest = {
        "schemaVersion": 2,
        "status": "prepared_unconsumed",
        "runId": "employee-wrapper-v2-test",
        "authorizationReference": "P3_00:GATE-024",
        "domain": "employee",
        "wrapperSourceCommit": "a" * 40,
        "candidate": {
            "runId": "candidate-test",
            "manifestPath": "candidate/manifest.json",
            "manifestSha256": _sha256(candidate_manifest),
            "authorizationPath": "candidate/authorization.json",
            "authorizationSha256": _sha256(candidate_authorization),
        },
        "buildProvenance": {
            "sourceCommit": "a" * 40,
            "command": EMPLOYEE_BUILD_COMMAND,
            "javaVersion": "25.0.2",
            "mavenVersion": "3.9.16",
        },
        "assetHashes": [{"path": "agent-runtime/wrapper.py", "sha256": _sha256(asset)}],
        "executableHashes": [
            {"path": relative, "sha256": _sha256(root / relative)}
            for relative in sorted(EMPLOYEE_EXECUTABLE_ASSET_PATHS)
        ],
        "historyHashes": [{"path": "history/result.json", "sha256": _sha256(history)}],
        "executionBoundary": {
            "liveExecutionAuthorized": False,
            "sideEffectsAllowed": False,
            "candidateInvocationsMaximum": 1,
            "retryAllowed": False,
            "resumeAllowed": False,
        },
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
    authorization = {
        "schemaVersion": 2,
        "runId": "employee-wrapper-v2-test",
        "manifestSha256": _sha256(manifest_path),
        "authorizationReference": "P3_00:GATE-024",
        "liveExecutionAuthorized": False,
    }
    authorization_path = root / "authorization.json"
    authorization_path.write_text(
        json.dumps(authorization, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
    return manifest_path, authorization_path


def _validate(root: Path, manifest: Path, authorization: Path) -> None:
    validate_prepared_assets(
        root,
        prepared_manifest_path=manifest,
        prepared_authorization_path=authorization,
    )


def test_employee_v2_manifest_binds_only_auth_jar(tmp_path: Path) -> None:
    manifest, authorization = _prepared_fixture(tmp_path)
    _validate(tmp_path, manifest, authorization)


def test_employee_v2_manifest_rejects_auth_jar_drift(tmp_path: Path) -> None:
    manifest, authorization = _prepared_fixture(tmp_path)
    target = tmp_path / next(iter(EMPLOYEE_EXECUTABLE_ASSET_PATHS))
    target.write_bytes(target.read_bytes() + b"drift")
    with pytest.raises(BootstrapContractError, match="bootstrap_v2_invalid"):
        _validate(tmp_path, manifest, authorization)


def test_employee_v2_manifest_rejects_transaction_executable_set(tmp_path: Path) -> None:
    manifest_path, authorization_path = _prepared_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    extra = "mq-procedure-service/target/mq-procedure-service-0.0.1-SNAPSHOT.jar"
    _write(tmp_path / extra, "unexpected")
    manifest["executableHashes"].append(
        {"path": extra, "sha256": _sha256(tmp_path / extra)}
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
    authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    authorization["manifestSha256"] = _sha256(manifest_path)
    authorization_path.write_text(
        json.dumps(authorization, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(BootstrapContractError, match="bootstrap_v2_invalid"):
        _validate(tmp_path, manifest_path, authorization_path)
