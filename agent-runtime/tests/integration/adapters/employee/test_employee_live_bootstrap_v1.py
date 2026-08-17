from __future__ import annotations

import ast
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.integration.adapters.business_egress_live_bootstrap import (
    EMPLOYEE_PHASES,
    BootstrapPhaseError,
)
from tests.integration.adapters.employee.live_bootstrap_v1 import (
    AUTHORIZATION_REFERENCE,
    CANDIDATE_AUTHORIZATION_SHA256,
    CANDIDATE_MANIFEST_SHA256,
    CANDIDATE_RUN_ID,
    RUN_ID,
    output_paths,
    run,
)


ROOT = Path(__file__).resolve().parents[5]
RUNTIME = ROOT / "agent-runtime"


def test_employee_profile_keeps_employee_service_inside_existing_candidate() -> None:
    source_path = RUNTIME / "tests/integration/adapters/employee/live_bootstrap_v1.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert EMPLOYEE_PHASES == (
        "asset_preflight",
        "config_resolution",
        "auth_start",
        "auth_readiness",
        "auth_login",
        "candidate_invoke",
    )
    assert CANDIDATE_RUN_ID == "employee-egress-v4-20260817-candidate-04"
    assert len(CANDIDATE_MANIFEST_SHA256) == 64
    assert len(CANDIDATE_AUTHORIZATION_SHA256) == 64
    assert "employee-service-0.0.1-SNAPSHOT.jar" not in source
    assert "domain_start" not in source
    assert "run-employee-egress-live-candidate-04.ps1" in source
    assert any(isinstance(node, ast.ClassDef) for node in ast.walk(tree))


def test_employee_wrapper_requires_exact_future_live_binding() -> None:
    path = RUNTIME / "scripts/run-employee-egress-live-host-candidate-01.ps1"
    script = path.read_text(encoding="utf-8")
    assert RUN_ID in script
    assert AUTHORIZATION_REFERENCE in script
    assert "EMPLOYEE_EGRESS_BOOTSTRAP_LIVE_AUTHORIZED" in script
    assert "LLM_API_KEY" not in script
    assert "Start-Process" not in script
    assert "employee-service" not in script

    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is not None:
        escaped = str(path).replace("'", "''")
        command = (
            "$tokens=$null;$errors=$null;"
            f"[Management.Automation.Language.Parser]::ParseFile('{escaped}',[ref]$tokens,[ref]$errors)|Out-Null;"
            "if($errors.Count -ne 0){exit 7}"
        )
        completed = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr


def test_employee_bootstrap_without_new_live_authorization_has_zero_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("EMPLOYEE_EGRESS_BOOTSTRAP_LIVE_AUTHORIZED", raising=False)
    with pytest.raises(BootstrapPhaseError, match="authorization_binding_invalid"):
        run(repository_root=tmp_path, expected_manifest_sha256="a" * 64)
    assert all(not path.exists() for path in output_paths(tmp_path))
    assert not (tmp_path / "agent-runtime/.codex-live").exists()


def test_common_bootstrap_schemas_are_closed_and_finite() -> None:
    schema_root = RUNTIME / "tests/integration/adapters/evidence"
    lifecycle = json.loads(
        (schema_root / "business-egress-live-bootstrap-v1-lifecycle.schema.json").read_text(
            encoding="utf-8"
        )
    )
    result = json.loads(
        (schema_root / "business-egress-live-bootstrap-v1-result.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert lifecycle["additionalProperties"] is False
    assert result["additionalProperties"] is False
    assert result["properties"]["counts"]["properties"]["retry"] == {"const": 0}
    assert result["properties"]["counts"]["properties"]["resume"] == {"const": 0}
