from __future__ import annotations

import json
import socket
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from tests.integration.adapters.business_egress_live_bootstrap import (
    EMPLOYEE_PHASES,
    TRANSACTION_PHASES,
    BootstrapBinding,
    BootstrapContractError,
    BootstrapPhaseError,
    CleanupOutcome,
    Domain,
    execute_bootstrap,
    limited_child_environment,
    read_lifecycle,
    resolve_noop_user_password,
    resolve_yaml_scalar_paths,
    sha256_file,
    validate_prepared_assets,
)


SHA = "a" * 64
OTHER_SHA = "b" * 64


def binding(domain: Domain = "employee") -> BootstrapBinding:
    return BootstrapBinding(
        run_id=f"{domain}-bootstrap",
        manifest_sha256=SHA,
        authorization_reference="P3_00:GATE-024" if domain == "employee" else "P3_00:GATE-026",
        domain=domain,
        wrapper_source_commit="c" * 40,
        candidate_run_id=f"{domain}-candidate",
        candidate_manifest_sha256=OTHER_SHA,
        candidate_authorization_sha256="d" * 64,
    )


@dataclass
class FakeOperations:
    fail_phase: str | None = None
    fail_reason: str = "config_invalid"
    unexpected_phase: str | None = None
    cleanup_outcome: CleanupOutcome = field(
        default_factory=lambda: CleanupOutcome(True, True, True, 0)
    )
    candidate_starts_on_failure: bool = True
    calls: list[str] = field(default_factory=list)
    _candidate_started: bool = False

    @property
    def candidate_started(self) -> bool:
        return self._candidate_started

    def run_phase(self, phase: str, *, deadline_seconds: float) -> None:
        assert deadline_seconds > 0
        self.calls.append(phase)
        if phase == "candidate_invoke" and (
            self.fail_phase != phase or self.candidate_starts_on_failure
        ):
            self._candidate_started = True
        if phase == self.fail_phase:
            raise BootstrapPhaseError(self.fail_reason)
        if phase == self.unexpected_phase:
            raise ValueError("raw failure text must not escape")

    def cleanup(self, *, candidate_started: bool, deadline_seconds: float) -> CleanupOutcome:
        assert deadline_seconds > 0
        self.calls.append(f"cleanup:{candidate_started}")
        return self.cleanup_outcome


@pytest.mark.parametrize(
    ("domain", "expected_phases"),
    [("employee", EMPLOYEE_PHASES), ("transaction", TRANSACTION_PHASES)],
)
def test_success_records_exact_domain_sequence(
    tmp_path: Path, domain: Domain, expected_phases: tuple[str, ...]
) -> None:
    current = binding(domain)
    operations = FakeOperations()
    lifecycle = tmp_path / "lifecycle.jsonl"
    result_path = tmp_path / "result.json"

    result = execute_bootstrap(
        binding=current,
        operations=operations,
        lifecycle_path=lifecycle,
        result_path=result_path,
    )

    assert result["status"] == "passed"
    assert operations.calls == [*expected_phases, "cleanup:True"]
    records = read_lifecycle(lifecycle, binding=current)
    assert [record["phase"] for record in records] == [
        item for phase in (*expected_phases, "cleanup") for item in (phase, phase)
    ]
    assert json.loads(result_path.read_text(encoding="utf-8")) == result


@pytest.mark.parametrize("phase", EMPLOYEE_PHASES[:-1])
def test_employee_pre_candidate_failure_is_unconsumed(tmp_path: Path, phase: str) -> None:
    current = binding()
    operations = FakeOperations(fail_phase=phase)
    result = execute_bootstrap(
        binding=current,
        operations=operations,
        lifecycle_path=tmp_path / "lifecycle.jsonl",
        result_path=tmp_path / "result.json",
    )

    assert result["status"] == "failed_pre_candidate_unconsumed"
    assert result["candidateInvoked"] is False
    assert result["failure"] == {"phase": phase, "reason": "config_invalid"}
    assert operations.calls[-1] == "cleanup:False"


def test_candidate_and_cleanup_failures_are_not_misreported(tmp_path: Path) -> None:
    current = binding()
    candidate_failure = execute_bootstrap(
        binding=current,
        operations=FakeOperations(fail_phase="candidate_invoke", fail_reason="candidate_failed"),
        lifecycle_path=tmp_path / "candidate.lifecycle.jsonl",
        result_path=tmp_path / "candidate.result.json",
    )
    cleanup_failure = execute_bootstrap(
        binding=current,
        operations=FakeOperations(
            cleanup_outcome=CleanupOutcome(False, False, False, 1)
        ),
        lifecycle_path=tmp_path / "cleanup.lifecycle.jsonl",
        result_path=tmp_path / "cleanup.result.json",
    )

    assert candidate_failure["status"] == "failed_candidate"
    assert candidate_failure["candidateInvoked"] is True
    assert cleanup_failure["status"] == "failed_cleanup_required"
    assert cleanup_failure["failure"] == {
        "phase": "cleanup",
        "reason": "log_leak_detected",
    }


def test_candidate_prelaunch_failure_remains_pre_candidate(tmp_path: Path) -> None:
    current = binding()
    result = execute_bootstrap(
        binding=current,
        operations=FakeOperations(
            fail_phase="candidate_invoke",
            fail_reason="config_missing",
            candidate_starts_on_failure=False,
        ),
        lifecycle_path=tmp_path / "lifecycle.jsonl",
        result_path=tmp_path / "result.json",
    )
    assert result["status"] == "failed_pre_candidate_unconsumed"
    assert result["candidateInvoked"] is False


def test_unexpected_failure_is_mapped_without_exception_text(tmp_path: Path) -> None:
    current = binding()
    result = execute_bootstrap(
        binding=current,
        operations=FakeOperations(unexpected_phase="config_resolution"),
        lifecycle_path=tmp_path / "lifecycle.jsonl",
        result_path=tmp_path / "result.json",
    )
    assert result["failure"] == {
        "phase": "config_resolution",
        "reason": "internal_failure",
    }
    assert "raw failure" not in (tmp_path / "result.json").read_text(encoding="utf-8")


def test_lifecycle_rejects_out_of_order_or_nonterminal_records(tmp_path: Path) -> None:
    current = binding()
    path = tmp_path / "lifecycle.jsonl"
    operation = FakeOperations(fail_phase="config_resolution")
    execute_bootstrap(
        binding=current,
        operations=operation,
        lifecycle_path=path,
        result_path=tmp_path / "result.json",
    )
    records = path.read_text(encoding="utf-8").splitlines()
    records[1] = records[1].replace('"status":"passed"', '"status":"started"')
    path.write_text("\n".join(records) + "\n", encoding="utf-8")
    with pytest.raises(BootstrapContractError):
        read_lifecycle(path, binding=current)


def test_fixed_yaml_parser_and_noop_fixture_reader(tmp_path: Path) -> None:
    datasource = tmp_path / "datasource.yml"
    datasource.write_text(
        "spring:\n"
        "  datasource:\n"
        "    url: jdbc:mysql://localhost/test\n"
        "    username: root\n"
        "    password: secret\n"
        "    driver-class-name: com.mysql.cj.jdbc.Driver\n",
        encoding="utf-8",
    )
    assert resolve_yaml_scalar_paths(
        datasource,
        (
            "spring.datasource.url",
            "spring.datasource.username",
            "spring.datasource.password",
            "spring.datasource.driver-class-name",
        ),
    )["spring.datasource.password"] == "secret"

    users = tmp_path / "auth-users.yml"
    users.write_text(
        "auth:\n  users:\n    admin:\n      password: \"{noop}test-only\"\n      roles: [ADMIN]\n",
        encoding="utf-8",
    )
    assert resolve_noop_user_password(users, user_id="admin") == "test-only"


def test_fixed_yaml_parser_fails_closed_for_duplicate_and_unsupported_scalar(
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate.yml"
    duplicate.write_text("spring:\n  datasource:\n    url: one\n    url: two\n", encoding="utf-8")
    with pytest.raises(BootstrapPhaseError, match="config_duplicate"):
        resolve_yaml_scalar_paths(duplicate, ("spring.datasource.url",))

    unsupported = tmp_path / "unsupported.yml"
    unsupported.write_text("spring:\n  datasource:\n    url: ${DB_URL}\n", encoding="utf-8")
    with pytest.raises(BootstrapPhaseError, match="config_invalid"):
        resolve_yaml_scalar_paths(unsupported, ("spring.datasource.url",))


def test_limited_child_environment_does_not_forward_unlisted_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_API_KEY", "must-not-be-inherited")
    environment = limited_child_environment({"SAFE_TEST_VALUE": "ok"})
    assert "LLM_API_KEY" not in environment
    assert environment["SAFE_TEST_VALUE"] == "ok"


def test_prepared_manifest_binds_candidate_and_all_frozen_files(tmp_path: Path) -> None:
    asset = tmp_path / "asset.py"
    history = tmp_path / "history.json"
    candidate_manifest = tmp_path / "candidate.manifest.json"
    candidate_authorization = tmp_path / "candidate.authorization.json"
    for path, value in (
        (asset, "asset"),
        (history, "history"),
        (candidate_manifest, "candidate-manifest"),
        (candidate_authorization, "candidate-authorization"),
    ):
        path.write_text(value, encoding="utf-8")
    manifest_path = tmp_path / "bootstrap.manifest.json"
    manifest = {
        "schemaVersion": 1,
        "status": "prepared_unconsumed",
        "runId": "employee-bootstrap",
        "authorizationReference": "P3_00:GATE-024",
        "domain": "employee",
        "wrapperSourceCommit": "c" * 40,
        "candidate": {
            "runId": "employee-candidate",
            "manifestPath": "candidate.manifest.json",
            "manifestSha256": sha256_file(candidate_manifest),
            "authorizationPath": "candidate.authorization.json",
            "authorizationSha256": sha256_file(candidate_authorization),
        },
        "assetHashes": [{"path": "asset.py", "sha256": sha256_file(asset)}],
        "historyHashes": [{"path": "history.json", "sha256": sha256_file(history)}],
        "executionBoundary": {
            "liveExecutionAuthorized": False,
            "sideEffectsAllowed": False,
            "candidateInvocationsMaximum": 1,
            "retryAllowed": False,
            "resumeAllowed": False,
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    authorization_path = tmp_path / "bootstrap.authorization.json"
    authorization_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "runId": "employee-bootstrap",
                "manifestSha256": sha256_file(manifest_path),
                "authorizationReference": "P3_00:GATE-024",
                "liveExecutionAuthorized": False,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    current = validate_prepared_assets(
        repository_root=tmp_path,
        manifest_path=manifest_path,
        authorization_path=authorization_path,
    )
    assert current.candidate_manifest_sha256 == sha256_file(candidate_manifest)

    candidate_manifest.write_text("tampered", encoding="utf-8")
    with pytest.raises(BootstrapContractError):
        validate_prepared_assets(
            repository_root=tmp_path,
            manifest_path=manifest_path,
            authorization_path=authorization_path,
        )


def test_port_probe_fails_when_listener_is_occupied() -> None:
    from tests.integration.adapters.business_egress_live_bootstrap import (
        assert_loopback_port_free,
    )

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        with pytest.raises(BootstrapPhaseError, match="port_occupied"):
            assert_loopback_port_free(listener.getsockname()[1])
