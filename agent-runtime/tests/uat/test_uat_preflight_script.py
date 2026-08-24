from __future__ import annotations

from pathlib import Path


_SCRIPT = Path(__file__).parents[2] / "scripts" / "run-uat-preflight.ps1"


def test_preflight_is_read_only_and_defaults_to_stub_model() -> None:
    text = _SCRIPT.read_text(encoding="utf-8")

    assert "[ValidateSet('Preparation', 'Execution')]" in text
    assert "[string]$RepositoryRoot = ''" in text
    assert "if ([string]::IsNullOrWhiteSpace($RepositoryRoot))" in text
    assert "$catalog.executionProfile.modelProvider -eq 'stub'" in text
    assert "$catalog.executionProfile.externalModelOutboundMax -eq 0" in text
    assert "LLM_API_KEY" not in text
    for forbidden in (
        "Invoke-WebRequest",
        "Invoke-RestMethod",
        "Start-Process",
        "Set-Content",
        "Add-Content",
        "Remove-Item",
        "git commit",
        "git push",
    ):
        assert forbidden not in text


def test_preflight_checks_infrastructure_inputs_and_production_diff() -> None:
    text = _SCRIPT.read_text(encoding="utf-8")

    for expected in (
        "Test-TcpReady 9200",
        "Test-TcpReady 8908",
        "Test-TcpReady 8909",
        "Test-PortFree 8090",
        "Test-PortFree 9201",
        "Test-PortFree 9210",
        "Test-PortFree 8182",
        "SYSTEM_E2E_EMPLOYEE_IDENTIFIER",
        "UAT_TRANSACTION_TYPE",
        "dirtyProductionPaths",
        "conflictingBuildProcessIds",
        "org.codehaus.plexus.classworlds.launcher.Launcher",
        "mq-procedure-service",
    ):
        assert expected in text
