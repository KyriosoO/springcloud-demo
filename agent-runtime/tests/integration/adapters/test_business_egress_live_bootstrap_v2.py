from __future__ import annotations

import subprocess
from pathlib import Path
from typing import cast

import pytest

from tests.integration.adapters.business_egress_live_bootstrap import (
    BootstrapBinding,
    BootstrapContractError,
    OwnedProcess,
)
from tests.integration.adapters.business_egress_live_bootstrap_v2 import (
    ProcessDiagnostic,
    classify_process_exit,
    load_process_diagnostic,
)


@pytest.mark.parametrize(
    ("message", "expected"),
    (
        ("java.lang.NoClassDefFoundError: example/Missing", "class_loading"),
        ("Port 8090 was already in use", "port_binding"),
        ("ConfigurationPropertiesBindException", "configuration_binding"),
        ("Communications link failure", "dependency_connectivity"),
        ("APPLICATION FAILED TO START", "application_context"),
        ("unclassified failure", "unknown"),
    ),
)
def test_process_exit_classification_is_finite(message: str, expected: str) -> None:
    assert classify_process_exit(("", message)) == expected


def test_unreadable_or_oversized_log_fails_to_unknown() -> None:
    assert classify_process_exit((None, "APPLICATION FAILED TO START")) == "unknown"


class _ExitedProcess:
    def poll(self) -> int:
        return 1


def test_process_diagnostic_persists_only_finite_fields(tmp_path: Path) -> None:
    sentinel = "never-persist-this-secret"
    stdout = tmp_path / "auth.out.log"
    stderr = tmp_path / "auth.err.log"
    stdout.write_text("", encoding="utf-8")
    stderr.write_text(
        f"BeanCreationException password={sentinel}",
        encoding="utf-8",
    )
    process = OwnedProcess(
        cast(subprocess.Popen[bytes], _ExitedProcess()),
        stdout,
        stderr,
    )
    binding = BootstrapBinding(
        run_id="diagnostic-test",
        manifest_sha256="a" * 64,
        authorization_reference="P3_00:GATE-061",
        domain="transaction",
        wrapper_source_commit="b" * 40,
        candidate_run_id="candidate-test",
        candidate_manifest_sha256="c" * 64,
        candidate_authorization_sha256="d" * 64,
    )
    diagnostic = ProcessDiagnostic.inspect(
        process=process,
        service="auth-service",
        phase="auth_readiness",
        secret_literals=(sentinel,),
    )
    path = tmp_path / "diagnostic.json"
    diagnostic.write(path=path, binding=binding)

    persisted = path.read_text(encoding="utf-8")
    assert sentinel not in persisted
    assert "BeanCreationException" not in persisted
    assert str(tmp_path) not in persisted
    value = load_process_diagnostic(path, binding=binding)
    assert value["classification"] == "application_context"
    assert value["exitCodePresent"] is True
    assert value["safety"] == {
        "forbiddenFields": 0,
        "secretPersistence": 0,
        "logLeakCount": 2,
    }


def test_process_diagnostic_rejects_extra_fields(tmp_path: Path) -> None:
    binding = BootstrapBinding(
        run_id="diagnostic-test",
        manifest_sha256="a" * 64,
        authorization_reference="P3_00:GATE-061",
        domain="transaction",
        wrapper_source_commit="b" * 40,
        candidate_run_id="candidate-test",
        candidate_manifest_sha256="c" * 64,
        candidate_authorization_sha256="d" * 64,
    )
    path = tmp_path / "diagnostic.json"
    path.write_text("{\"unexpected\":true}", encoding="utf-8")
    with pytest.raises(BootstrapContractError, match="bootstrap_v2_invalid"):
        load_process_diagnostic(path, binding=binding)
