from __future__ import annotations

import argparse
import os
import re
import secrets
from collections.abc import Mapping
from pathlib import Path
from typing import Final, Literal, NoReturn, cast

from tests.integration.adapters.business_egress_live_bootstrap import (
    EMPLOYEE_PHASES,
    BootstrapBinding,
    BootstrapContractError,
    BootstrapPhaseError,
    CleanupOutcome,
    LocalProcessRuntime,
    OwnedProcess,
    assert_loopback_port_free,
    common_security_arguments,
    execute_bootstrap,
    issue_auth_cookie,
    limited_child_environment,
    load_strict_json,
    resolve_noop_user_password,
    sha256_file,
)
from tests.integration.adapters.business_egress_live_bootstrap_v2 import (
    ProcessDiagnostic,
)


RUN_ID: Final = "employee-egress-live-bootstrap-v2-20260818-candidate-02"
AUTHORIZATION_REFERENCE: Final = "P3_00:GATE-024"
CANDIDATE_RUN_ID: Final = "employee-egress-v4-20260817-candidate-04"
CANDIDATE_AUTHORIZATION_REFERENCE: Final = "P3_00:GATE-024"
CANDIDATE_MANIFEST_SHA256: Final = (
    "b2de9dce219fa8de1bba4e96b68951ad51b46407d8c5b91240a23531ab4328eb"
)
CANDIDATE_AUTHORIZATION_SHA256: Final = (
    "fd14adc193244a4a91c785b2eb10710fa0c08cb81107d630164ee8fb7228e0d2"
)
AUTH_PORT: Final = 8090
EMPLOYEE_EXECUTABLE_ASSET_PATHS: Final = frozenset(
    {"auth-service/target/auth-service-0.0.1-SNAPSHOT.jar"}
)
EMPLOYEE_BUILD_COMMAND: Final = (
    "mvn -f serviceCenter/pom.xml -pl :auth-service -am -DskipTests package"
)
BOOTSTRAP_ASSET_PATHS: Final = frozenset(
    {
        "agent-runtime/scripts/run-employee-egress-live-host-candidate-02.ps1",
        "agent-runtime/tests/integration/adapters/business_egress_live_bootstrap.py",
        "agent-runtime/tests/integration/adapters/business_egress_live_bootstrap_v2.py",
        "agent-runtime/tests/integration/adapters/evidence/business-egress-live-bootstrap-v1-lifecycle.schema.json",
        "agent-runtime/tests/integration/adapters/evidence/business-egress-live-bootstrap-v1-result.schema.json",
        "agent-runtime/tests/integration/adapters/evidence/business-egress-live-bootstrap-v2-diagnostic.schema.json",
        "agent-runtime/tests/integration/adapters/test_business_egress_live_bootstrap_v2.py",
        "agent-runtime/tests/integration/adapters/employee/live_bootstrap_v2.py",
        "agent-runtime/tests/integration/adapters/employee/test_employee_live_bootstrap_v2.py",
        "agent-runtime/tests/integration/adapters/employee/test_employee_live_bootstrap_v2_history.py",
        "agent-runtime/tests/integration/adapters/employee/test_employee_live_bootstrap_v2_preparation.py",
    }
)
BOOTSTRAP_HISTORY_PATHS: Final = frozenset(
    {
        "agent-runtime/scripts/run-employee-egress-live-host-candidate-01.ps1",
        "agent-runtime/tests/integration/adapters/employee/live_bootstrap_v1.py",
        "agent-runtime/tests/integration/adapters/employee/test_employee_live_bootstrap_v1.py",
        "agent-runtime/tests/integration/adapters/employee/test_employee_live_bootstrap_v1_history.py",
        "agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-live-bootstrap-v1-20260817-candidate-01.manifest.json",
        "agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-live-bootstrap-v1-20260817-candidate-01.authorization.json",
        "agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-v4-20260817-candidate-04.manifest.json",
        "agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-v4-20260817-candidate-04.authorization.json",
    }
)
_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_SOURCE_COMMIT: Final = re.compile(r"[0-9a-f]{40}")


def evidence_directory(repository_root: Path) -> Path:
    return repository_root / "agent-runtime/tests/integration/adapters/employee/evidence"


def manifest_path(repository_root: Path) -> Path:
    return evidence_directory(repository_root) / f"{RUN_ID}.manifest.json"


def authorization_path(repository_root: Path) -> Path:
    return evidence_directory(repository_root) / f"{RUN_ID}.authorization.json"


def output_paths(repository_root: Path) -> tuple[Path, Path, Path]:
    root = evidence_directory(repository_root)
    return (
        root / f"{RUN_ID}.lifecycle.jsonl",
        root / f"{RUN_ID}.result.json",
        root / f"{RUN_ID}.diagnostic.json",
    )


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


def _invalid() -> NoReturn:
    raise BootstrapContractError("employee.egress_live_bootstrap_v2_invalid")


def _validate_hash_rows(
    *, repository_root: Path, rows: object, required_paths: frozenset[str] | None = None
) -> frozenset[str]:
    if not isinstance(rows, list) or not rows:
        _invalid()
    root = repository_root.resolve()
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {"path", "sha256"}:
            _invalid()
        relative = row.get("path")
        expected = row.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or relative in seen
            or not isinstance(expected, str)
            or not _SHA256.fullmatch(expected)
        ):
            _invalid()
        target = (root / relative).resolve()
        if root not in target.parents or not target.is_file() or sha256_file(target) != expected:
            _invalid()
        seen.add(relative)
    frozen = frozenset(seen)
    if required_paths is not None and frozen != required_paths:
        _invalid()
    return frozen


def validate_prepared_assets(
    repository_root: Path,
    *,
    prepared_manifest_path: Path | None = None,
    prepared_authorization_path: Path | None = None,
) -> BootstrapBinding:
    root = repository_root.resolve()
    prepared_manifest = prepared_manifest_path or manifest_path(root)
    prepared_authorization = prepared_authorization_path or authorization_path(root)
    manifest = load_strict_json(prepared_manifest)
    manifest_sha = sha256_file(prepared_manifest)
    authorization = load_strict_json(prepared_authorization)
    if set(manifest) != {
        "schemaVersion",
        "status",
        "runId",
        "authorizationReference",
        "domain",
        "wrapperSourceCommit",
        "candidate",
        "buildProvenance",
        "assetHashes",
        "executableHashes",
        "historyHashes",
        "executionBoundary",
    } or manifest.get("schemaVersion") != 2 or manifest.get("status") != "prepared_unconsumed":
        _invalid()
    candidate = manifest.get("candidate")
    if not isinstance(candidate, Mapping) or set(candidate) != {
        "runId",
        "manifestPath",
        "manifestSha256",
        "authorizationPath",
        "authorizationSha256",
    }:
        _invalid()
    binding = BootstrapBinding(
        run_id=str(manifest.get("runId")),
        manifest_sha256=manifest_sha,
        authorization_reference=str(manifest.get("authorizationReference")),
        domain=cast(Literal["employee", "transaction"], manifest.get("domain")),
        wrapper_source_commit=str(manifest.get("wrapperSourceCommit")),
        candidate_run_id=str(candidate.get("runId")),
        candidate_manifest_sha256=str(candidate.get("manifestSha256")),
        candidate_authorization_sha256=str(candidate.get("authorizationSha256")),
    )
    binding.validate()
    if set(authorization) != {
        "schemaVersion",
        "runId",
        "manifestSha256",
        "authorizationReference",
        "liveExecutionAuthorized",
    } or (
        authorization.get("schemaVersion") != 2
        or authorization.get("runId") != binding.run_id
        or authorization.get("manifestSha256") != manifest_sha
        or authorization.get("authorizationReference") != binding.authorization_reference
        or authorization.get("liveExecutionAuthorized") is not False
    ):
        _invalid()
    build = manifest.get("buildProvenance")
    if not isinstance(build, Mapping) or set(build) != {
        "sourceCommit",
        "command",
        "javaVersion",
        "mavenVersion",
    } or (
        not isinstance(build.get("sourceCommit"), str)
        or not _SOURCE_COMMIT.fullmatch(cast(str, build.get("sourceCommit")))
        or build.get("sourceCommit") != binding.wrapper_source_commit
        or build.get("command") != EMPLOYEE_BUILD_COMMAND
        or not isinstance(build.get("javaVersion"), str)
        or not cast(str, build.get("javaVersion")).startswith("25.")
        or not isinstance(build.get("mavenVersion"), str)
        or not cast(str, build.get("mavenVersion")).startswith("3.")
    ):
        _invalid()
    boundary = manifest.get("executionBoundary")
    if not isinstance(boundary, Mapping) or set(boundary) != {
        "liveExecutionAuthorized",
        "sideEffectsAllowed",
        "candidateInvocationsMaximum",
        "retryAllowed",
        "resumeAllowed",
    } or (
        boundary.get("liveExecutionAuthorized") is not False
        or boundary.get("sideEffectsAllowed") is not False
        or boundary.get("candidateInvocationsMaximum") != 1
        or boundary.get("retryAllowed") is not False
        or boundary.get("resumeAllowed") is not False
    ):
        _invalid()
    for path_key, sha_key in (
        ("manifestPath", "manifestSha256"),
        ("authorizationPath", "authorizationSha256"),
    ):
        relative = candidate.get(path_key)
        expected = candidate.get(sha_key)
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or not isinstance(expected, str)
            or not _SHA256.fullmatch(expected)
        ):
            _invalid()
        target = (root / relative).resolve()
        if root not in target.parents or not target.is_file() or sha256_file(target) != expected:
            _invalid()
    _validate_hash_rows(repository_root=root, rows=manifest.get("assetHashes"))
    _validate_hash_rows(
        repository_root=root,
        rows=manifest.get("executableHashes"),
        required_paths=EMPLOYEE_EXECUTABLE_ASSET_PATHS,
    )
    _validate_hash_rows(repository_root=root, rows=manifest.get("historyHashes"))
    return binding


class EmployeeLiveBootstrapV2Operations:
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
        try:
            handler(deadline_seconds)
        except BootstrapPhaseError as exc:
            if exc.reason == "process_exited":
                self._record_process_diagnostic(phase)
            raise

    def _record_process_diagnostic(self, phase: str) -> None:
        if phase not in {"auth_readiness", "auth_login"} or self.auth_process is None:
            return
        try:
            diagnostic = ProcessDiagnostic.inspect(
                process=self.auth_process,
                service="auth-service",
                phase=phase,
                secret_literals=self.runtime.secret_literals,
            )
            diagnostic.write(path=output_paths(self.repository_root)[2], binding=self.binding)
        except (BootstrapContractError, OSError) as exc:
            raise BootstrapPhaseError("evidence_write_failed") from exc

    def _asset_preflight(self, _deadline_seconds: float) -> None:
        if validate_prepared_assets(self.repository_root) != self.binding:
            raise BootstrapPhaseError("authorization_binding_invalid")
        if any(path.exists() for path in output_paths(self.repository_root)):
            raise BootstrapPhaseError("asset_hash_invalid")
        if any(path.exists() for path in candidate_output_paths(self.repository_root)):
            raise BootstrapPhaseError("asset_hash_invalid")

    def _config_resolution(self, _deadline_seconds: float) -> None:
        self.admin_password = resolve_noop_user_password(
            self.repository_root / "auth-service/src/main/resources/auth-users.yml",
            user_id="admin",
        )

    def _auth_start(self, _deadline_seconds: float) -> None:
        assert_loopback_port_free(AUTH_PORT)
        auth_jar = self.repository_root / next(iter(EMPLOYEE_EXECUTABLE_ASSET_PATHS))
        if not auth_jar.is_file():
            raise BootstrapPhaseError("asset_hash_invalid")
        self.hmac_secret = secrets.token_urlsafe(48)
        self.runtime.secret_literals.append(self.hmac_secret)
        self.auth_process = self.runtime.start(
            name="auth-service",
            command=("java", "-jar", str(auth_jar), *common_security_arguments(port=AUTH_PORT)),
            working_directory=self.repository_root / "auth-service",
            environment=limited_child_environment(
                {"COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE": self.hmac_secret}
            ),
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
        candidate = self.runtime.start(
            name="employee-candidate",
            command=(
                "pwsh",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(
                    self.repository_root
                    / "agent-runtime/scripts/run-employee-egress-live-candidate-04.ps1"
                ),
            ),
            working_directory=self.repository_root,
            environment=limited_child_environment(
                {
                    "COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE": self.hmac_secret,
                    "EMPLOYEE_EGRESS_V4_ADMIN_JWT": self.admin_jwt,
                    "EMPLOYEE_EGRESS_V4_EXPECTED_MANIFEST_SHA256": CANDIDATE_MANIFEST_SHA256,
                    "EMPLOYEE_EGRESS_V4_LIVE_AUTHORIZED": "1",
                    "LLM_API_KEY": api_key,
                }
            ),
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
    if os.environ.get("EMPLOYEE_EGRESS_BOOTSTRAP_V2_LIVE_AUTHORIZED") != "1":
        raise BootstrapPhaseError("authorization_binding_invalid")
    binding = validate_prepared_assets(repository_root)
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
    lifecycle, result, _diagnostic = output_paths(repository_root)
    operations = EmployeeLiveBootstrapV2Operations(
        repository_root=repository_root,
        binding=binding,
    )
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
