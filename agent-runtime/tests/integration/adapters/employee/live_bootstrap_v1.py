from __future__ import annotations

import argparse
import os
import secrets
from pathlib import Path
from typing import Final

from tests.integration.adapters.business_egress_live_bootstrap import (
    BootstrapBinding,
    BootstrapPhaseError,
    CleanupOutcome,
    LocalProcessRuntime,
    OwnedProcess,
    assert_loopback_port_free,
    common_security_arguments,
    execute_bootstrap,
    issue_auth_cookie,
    limited_child_environment,
    resolve_noop_user_password,
    validate_prepared_assets,
)


RUN_ID: Final = "employee-egress-live-bootstrap-v1-20260817-candidate-01"
AUTHORIZATION_REFERENCE: Final = "P3_00:GATE-024"
CANDIDATE_RUN_ID: Final = "employee-egress-v4-20260817-candidate-04"
CANDIDATE_MANIFEST_SHA256: Final = (
    "b2de9dce219fa8de1bba4e96b68951ad51b46407d8c5b91240a23531ab4328eb"
)
CANDIDATE_AUTHORIZATION_SHA256: Final = (
    "fd14adc193244a4a91c785b2eb10710fa0c08cb81107d630164ee8fb7228e0d2"
)
AUTH_PORT: Final = 8090
BOOTSTRAP_ASSET_PATHS: Final = frozenset(
    {
        "agent-runtime/scripts/run-employee-egress-live-host-candidate-01.ps1",
        "agent-runtime/tests/integration/adapters/business_egress_live_bootstrap.py",
        "agent-runtime/tests/integration/adapters/test_business_egress_live_bootstrap.py",
        "agent-runtime/tests/integration/adapters/evidence/business-egress-live-bootstrap-v1-lifecycle.schema.json",
        "agent-runtime/tests/integration/adapters/evidence/business-egress-live-bootstrap-v1-result.schema.json",
        "agent-runtime/tests/integration/adapters/employee/live_bootstrap_v1.py",
        "agent-runtime/tests/integration/adapters/employee/test_employee_live_bootstrap_v1.py",
        "agent-runtime/tests/integration/adapters/employee/test_employee_live_bootstrap_v1_history.py",
    }
)
BOOTSTRAP_HISTORY_PATHS: Final = frozenset(
    {
        "agent-runtime/tests/integration/adapters/employee/evidence/wp-emp-egress-env-diag-01-20260814T004517Z.json",
        "agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-v3-20260817-candidate-03.manifest.json",
        "agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-v3-20260817-candidate-03.authorization.json",
        "agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-v3-20260817-candidate-03.lifecycle.jsonl",
        "agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-v3-20260817-candidate-03.authorization.consumed.json",
        "agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-v3-20260817-candidate-03.result.json",
    }
)


def evidence_directory(repository_root: Path) -> Path:
    return repository_root / "agent-runtime/tests/integration/adapters/employee/evidence"


def manifest_path(repository_root: Path) -> Path:
    return evidence_directory(repository_root) / f"{RUN_ID}.manifest.json"


def authorization_path(repository_root: Path) -> Path:
    return evidence_directory(repository_root) / f"{RUN_ID}.authorization.json"


def output_paths(repository_root: Path) -> tuple[Path, Path]:
    root = evidence_directory(repository_root)
    return root / f"{RUN_ID}.lifecycle.jsonl", root / f"{RUN_ID}.result.json"


def candidate_output_paths(repository_root: Path) -> tuple[Path, ...]:
    root = evidence_directory(repository_root)
    return tuple(
        root / f"{CANDIDATE_RUN_ID}.{suffix}"
        for suffix in (
            "lifecycle.jsonl",
            "authorization.consumed.json",
            "pending.json",
            "staging.json",
            "result.json",
        )
    )


class EmployeeLiveBootstrapOperations:
    def __init__(self, *, repository_root: Path, binding: BootstrapBinding) -> None:
        self.repository_root = repository_root.resolve()
        self.binding = binding
        run_root = self.repository_root / "agent-runtime/.codex-live" / RUN_ID
        self.runtime = LocalProcessRuntime(run_root)
        self.auth_process: OwnedProcess | None = None
        self.hmac_secret: str | None = None
        self.admin_password: str | None = None
        self.admin_jwt: str | None = None
        self._candidate_started = False

    @property
    def candidate_started(self) -> bool:
        return self._candidate_started

    def run_phase(self, phase: str, *, deadline_seconds: float) -> None:
        handlers = {
            "asset_preflight": self._asset_preflight,
            "config_resolution": self._config_resolution,
            "auth_start": self._auth_start,
            "auth_readiness": self._auth_readiness,
            "auth_login": self._auth_login,
            "candidate_invoke": self._candidate_invoke,
        }
        handler = handlers.get(phase)
        if handler is None:
            raise BootstrapPhaseError("internal_failure")
        handler(deadline_seconds)

    def _asset_preflight(self, _deadline_seconds: float) -> None:
        current = validate_prepared_assets(
            repository_root=self.repository_root,
            manifest_path=manifest_path(self.repository_root),
            authorization_path=authorization_path(self.repository_root),
        )
        if current != self.binding:
            raise BootstrapPhaseError("authorization_binding_invalid")
        if any(path.exists() for path in candidate_output_paths(self.repository_root)):
            raise BootstrapPhaseError("asset_hash_invalid")

    def _config_resolution(self, _deadline_seconds: float) -> None:
        self.admin_password = resolve_noop_user_password(
            self.repository_root / "auth-service/src/main/resources/auth-users.yml",
            user_id="admin",
        )

    def _auth_start(self, _deadline_seconds: float) -> None:
        assert_loopback_port_free(AUTH_PORT)
        auth_jar = self.repository_root / "auth-service/target/auth-service-0.0.1-SNAPSHOT.jar"
        if not auth_jar.is_file():
            raise BootstrapPhaseError("asset_hash_invalid")
        self.hmac_secret = secrets.token_urlsafe(48)
        self.runtime.secret_literals.append(self.hmac_secret)
        environment = limited_child_environment(
            {"COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE": self.hmac_secret}
        )
        self.auth_process = self.runtime.start(
            name="auth-service",
            command=("java", "-jar", str(auth_jar), *common_security_arguments(port=AUTH_PORT)),
            working_directory=self.repository_root / "auth-service",
            environment=environment,
        )

    def _auth_readiness(self, deadline_seconds: float) -> None:
        if self.auth_process is None:
            raise BootstrapPhaseError("internal_failure")
        self.runtime.wait_http(
            f"http://127.0.0.1:{AUTH_PORT}/public/test",
            self.auth_process,
            port=AUTH_PORT,
            deadline_seconds=deadline_seconds,
        )

    def _auth_login(self, deadline_seconds: float) -> None:
        if self.admin_password is None:
            raise BootstrapPhaseError("internal_failure")
        self.admin_jwt = issue_auth_cookie(
            base_url=f"http://127.0.0.1:{AUTH_PORT}",
            user_id="admin",
            password=self.admin_password,
            deadline_seconds=deadline_seconds,
        )
        self.runtime.secret_literals.extend((self.admin_password, self.admin_jwt))

    def _candidate_invoke(self, deadline_seconds: float) -> None:
        api_key = os.environ.get("LLM_API_KEY")
        if not api_key or self.hmac_secret is None or self.admin_jwt is None:
            raise BootstrapPhaseError("config_missing")
        self.runtime.secret_literals.append(api_key)
        environment = limited_child_environment(
            {
                "COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE": self.hmac_secret,
                "EMPLOYEE_EGRESS_V4_ADMIN_JWT": self.admin_jwt,
                "EMPLOYEE_EGRESS_V4_EXPECTED_MANIFEST_SHA256": CANDIDATE_MANIFEST_SHA256,
                "EMPLOYEE_EGRESS_V4_LIVE_AUTHORIZED": "1",
                "LLM_API_KEY": api_key,
            }
        )
        launcher = self.repository_root / "agent-runtime/scripts/run-employee-egress-live-candidate-04.ps1"
        candidate = self.runtime.start(
            name="employee-candidate",
            command=("pwsh", "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(launcher)),
            working_directory=self.repository_root,
            environment=environment,
        )
        self._candidate_started = True
        self.runtime.wait_exit(candidate, deadline_seconds=max(deadline_seconds, 1_800.0))

    def cleanup(self, *, candidate_started: bool, deadline_seconds: float) -> CleanupOutcome:
        del candidate_started, deadline_seconds
        outcome = self.runtime.cleanup()
        self.hmac_secret = None
        self.admin_password = None
        self.admin_jwt = None
        return outcome


def run(*, repository_root: Path, expected_manifest_sha256: str) -> dict[str, object]:
    if os.environ.get("EMPLOYEE_EGRESS_BOOTSTRAP_LIVE_AUTHORIZED") != "1":
        raise BootstrapPhaseError("authorization_binding_invalid")
    binding = validate_prepared_assets(
        repository_root=repository_root,
        manifest_path=manifest_path(repository_root),
        authorization_path=authorization_path(repository_root),
    )
    if (
        binding.run_id != RUN_ID
        or binding.manifest_sha256 != expected_manifest_sha256
        or binding.authorization_reference != AUTHORIZATION_REFERENCE
        or binding.domain != "employee"
        or binding.candidate_run_id != CANDIDATE_RUN_ID
        or binding.candidate_manifest_sha256 != CANDIDATE_MANIFEST_SHA256
        or binding.candidate_authorization_sha256 != CANDIDATE_AUTHORIZATION_SHA256
    ):
        raise BootstrapPhaseError("authorization_binding_invalid")
    lifecycle, result = output_paths(repository_root)
    operations = EmployeeLiveBootstrapOperations(repository_root=repository_root, binding=binding)
    return execute_bootstrap(
        binding=binding,
        operations=operations,
        lifecycle_path=lifecycle,
        result_path=result,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    arguments = parser.parse_args()
    result = run(
        repository_root=arguments.repository_root.resolve(),
        expected_manifest_sha256=arguments.manifest_sha256,
    )
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
