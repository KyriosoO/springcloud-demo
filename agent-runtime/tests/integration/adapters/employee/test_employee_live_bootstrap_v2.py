from __future__ import annotations

import ast
import shutil
import subprocess
from pathlib import Path
from typing import cast

import pytest

from tests.integration.adapters.business_egress_live_bootstrap import (
    EMPLOYEE_PHASES,
    BootstrapBinding,
    BootstrapPhaseError,
    OwnedProcess,
)
from tests.integration.adapters.business_egress_live_bootstrap_v2 import (
    load_process_diagnostic,
)
from tests.integration.adapters.employee.live_bootstrap_v2 import (
    AUTHORIZATION_REFERENCE,
    CANDIDATE_AUTHORIZATION_REFERENCE,
    CANDIDATE_AUTHORIZATION_SHA256,
    CANDIDATE_MANIFEST_SHA256,
    CANDIDATE_RUN_ID,
    EMPLOYEE_BUILD_COMMAND,
    EMPLOYEE_EXECUTABLE_ASSET_PATHS,
    RUN_ID,
    EmployeeLiveBootstrapV2Operations,
    output_paths,
    run,
)


ROOT = Path(__file__).resolve().parents[5]
RUNTIME = ROOT / "agent-runtime"


def test_employee_v2_profile_keeps_employee_service_inside_candidate() -> None:
    source_path = RUNTIME / "tests/integration/adapters/employee/live_bootstrap_v2.py"
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
    assert EMPLOYEE_EXECUTABLE_ASSET_PATHS == frozenset(
        {"auth-service/target/auth-service-0.0.1-SNAPSHOT.jar"}
    )
    assert EMPLOYEE_BUILD_COMMAND == (
        "mvn -f serviceCenter/pom.xml -pl :auth-service -am -DskipTests package"
    )
    assert CANDIDATE_RUN_ID == "employee-egress-v4-20260817-candidate-04"
    assert CANDIDATE_AUTHORIZATION_REFERENCE == "P3_00:GATE-024"
    assert len(CANDIDATE_MANIFEST_SHA256) == 64
    assert len(CANDIDATE_AUTHORIZATION_SHA256) == 64
    assert "validate_prepared_assets" in source
    assert "ProcessDiagnostic" in source
    assert "employee-service-0.0.1-SNAPSHOT.jar" not in source
    assert "domain_start" not in source
    assert any(isinstance(node, ast.ClassDef) for node in ast.walk(tree))


def test_employee_v2_wrapper_requires_exact_future_live_binding() -> None:
    path = RUNTIME / "scripts/run-employee-egress-live-host-candidate-02.ps1"
    script = path.read_text(encoding="utf-8")
    assert RUN_ID in script
    assert AUTHORIZATION_REFERENCE in script
    assert "EMPLOYEE_EGRESS_BOOTSTRAP_V2_LIVE_AUTHORIZED" in script
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


def test_employee_v2_without_live_authorization_has_zero_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("EMPLOYEE_EGRESS_BOOTSTRAP_V2_LIVE_AUTHORIZED", raising=False)
    with pytest.raises(BootstrapPhaseError, match="authorization_binding_invalid"):
        run(repository_root=tmp_path, expected_manifest_sha256="a" * 64)
    assert all(not path.exists() for path in output_paths(tmp_path))
    assert not (tmp_path / "agent-runtime/.codex-live").exists()


class _ExitedProcess:
    def poll(self) -> int:
        return 1


def test_employee_v2_records_finite_diagnostic_then_deletes_raw_logs(
    tmp_path: Path,
) -> None:
    binding = BootstrapBinding(
        run_id=RUN_ID,
        manifest_sha256="a" * 64,
        authorization_reference=AUTHORIZATION_REFERENCE,
        domain="employee",
        wrapper_source_commit="b" * 40,
        candidate_run_id=CANDIDATE_RUN_ID,
        candidate_manifest_sha256=CANDIDATE_MANIFEST_SHA256,
        candidate_authorization_sha256=CANDIDATE_AUTHORIZATION_SHA256,
    )
    operations = EmployeeLiveBootstrapV2Operations(repository_root=tmp_path, binding=binding)
    run_root = tmp_path / "agent-runtime/.codex-live" / RUN_ID
    run_root.mkdir(parents=True)
    stdout = run_root / "auth-service.out.log"
    stderr = run_root / "auth-service.err.log"
    stdout.write_text("", encoding="utf-8")
    stderr.write_text("APPLICATION FAILED TO START", encoding="utf-8")
    operations.auth_process = OwnedProcess(
        cast(subprocess.Popen[bytes], _ExitedProcess()), stdout, stderr
    )

    with pytest.raises(BootstrapPhaseError, match="process_exited"):
        operations.run_phase("auth_readiness", deadline_seconds=0.01)

    diagnostic_path = output_paths(tmp_path)[2]
    diagnostic = load_process_diagnostic(diagnostic_path, binding=binding)
    assert diagnostic["classification"] == "application_context"
    outcome = operations.cleanup(candidate_started=False, deadline_seconds=1.0)
    assert outcome.completed is True
    assert outcome.raw_logs_deleted is True
    assert not run_root.exists()
    assert diagnostic_path.is_file()
