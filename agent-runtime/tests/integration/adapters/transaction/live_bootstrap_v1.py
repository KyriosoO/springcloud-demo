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
    resolve_yaml_scalar_paths,
    validate_prepared_assets,
    wait_owned_listener,
)


RUN_ID: Final = "transaction-egress-live-bootstrap-v1-20260817-candidate-01"
AUTHORIZATION_REFERENCE: Final = "P3_00:GATE-026"
CANDIDATE_RUN_ID: Final = "transaction-egress-v4-20260817-candidate-04"
CANDIDATE_MANIFEST_SHA256: Final = (
    "ca440b8f3cf664cfe77b803c6a7786816935d391bc56e50a522f6cb76f0535d3"
)
CANDIDATE_AUTHORIZATION_SHA256: Final = (
    "885ddb8854b34ccebf29d481e78fb84b1b6a550adf5330bf321eea5085690359"
)
AUTH_PORT: Final = 8090
TRANSACTION_PORT: Final = 8182
DATASOURCE_PATHS: Final = (
    "spring.datasource.url",
    "spring.datasource.username",
    "spring.datasource.password",
    "spring.datasource.driver-class-name",
)


def evidence_directory(repository_root: Path) -> Path:
    return repository_root / "agent-runtime/tests/integration/adapters/transaction/evidence"


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
            "host-preflight.jsonl",
            "host-result.json",
            "lifecycle.jsonl",
            "authorization.consumed.json",
            "result.json",
        )
    )


class TransactionLiveBootstrapOperations:
    def __init__(self, *, repository_root: Path, binding: BootstrapBinding) -> None:
        self.repository_root = repository_root.resolve()
        self.binding = binding
        run_root = self.repository_root / "agent-runtime/.codex-live" / RUN_ID
        self.runtime = LocalProcessRuntime(run_root)
        self.auth_process: OwnedProcess | None = None
        self.transaction_process: OwnedProcess | None = None
        self.hmac_secret: str | None = None
        self.admin_password: str | None = None
        self.admin_jwt: str | None = None
        self.datasource: dict[str, str] = {}
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
            "domain_start": self._domain_start,
            "domain_readiness": self._domain_readiness,
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
        self.datasource = resolve_yaml_scalar_paths(
            self.repository_root / "config-service/src/main/resources/config/application-datasource.yml",
            DATASOURCE_PATHS,
        )
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

    def _domain_start(self, _deadline_seconds: float) -> None:
        if self.hmac_secret is None or set(self.datasource) != set(DATASOURCE_PATHS):
            raise BootstrapPhaseError("internal_failure")
        assert_loopback_port_free(TRANSACTION_PORT)
        service_jar = (
            self.repository_root
            / "mq-procedure-service/target/mq-procedure-service-0.0.1-SNAPSHOT.jar"
        )
        if not service_jar.is_file():
            raise BootstrapPhaseError("asset_hash_invalid")
        datasource_environment = {
            "COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE": self.hmac_secret,
            "SPRING_DATASOURCE_URL": self.datasource["spring.datasource.url"],
            "SPRING_DATASOURCE_USERNAME": self.datasource["spring.datasource.username"],
            "SPRING_DATASOURCE_PASSWORD": self.datasource["spring.datasource.password"],
            "SPRING_DATASOURCE_DRIVER_CLASS_NAME": self.datasource[
                "spring.datasource.driver-class-name"
            ],
        }
        self.runtime.secret_literals.extend(
            (
                self.datasource["spring.datasource.username"],
                self.datasource["spring.datasource.password"],
            )
        )
        service_arguments = common_security_arguments(port=TRANSACTION_PORT) + (
            "--spring.profiles.active=",
        )
        self.transaction_process = self.runtime.start(
            name="transaction-service",
            command=("java", "-jar", str(service_jar), *service_arguments),
            working_directory=self.repository_root / "mq-procedure-service",
            environment=limited_child_environment(datasource_environment),
        )

    def _domain_readiness(self, deadline_seconds: float) -> None:
        if self.transaction_process is None:
            raise BootstrapPhaseError("internal_failure")
        wait_owned_listener(
            port=TRANSACTION_PORT,
            process=self.transaction_process,
            deadline_seconds=deadline_seconds,
        )

    def _candidate_invoke(self, deadline_seconds: float) -> None:
        api_key = os.environ.get("LLM_API_KEY")
        if (
            not api_key
            or self.admin_jwt is None
            or set(self.datasource) != set(DATASOURCE_PATHS)
        ):
            raise BootstrapPhaseError("config_missing")
        self.runtime.secret_literals.append(api_key)
        environment = limited_child_environment(
            {
                "LLM_API_KEY": api_key,
                "TRANSACTION_EGRESS_LIVE_USER_JWT": self.admin_jwt,
                "TRANSACTION_EGRESS_LIVE_BASE_URL": f"http://127.0.0.1:{TRANSACTION_PORT}",
                "TRANSACTION_EGRESS_LIVE_DB_URL": self.datasource["spring.datasource.url"],
                "TRANSACTION_EGRESS_LIVE_DB_USERNAME": self.datasource[
                    "spring.datasource.username"
                ],
                "TRANSACTION_EGRESS_LIVE_DB_PASSWORD": self.datasource[
                    "spring.datasource.password"
                ],
            }
        )
        launcher = (
            self.repository_root / "agent-runtime/scripts/run-transaction-egress-live-candidate-04.ps1"
        )
        candidate = self.runtime.start(
            name="transaction-candidate",
            command=(
                "pwsh",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(launcher),
                "-ManifestSha256",
                CANDIDATE_MANIFEST_SHA256,
                "-RunId",
                CANDIDATE_RUN_ID,
                "-AuthorizationReference",
                AUTHORIZATION_REFERENCE,
                "-RepositoryRoot",
                str(self.repository_root),
            ),
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
        self.datasource.clear()
        return outcome


def run(*, repository_root: Path, expected_manifest_sha256: str) -> dict[str, object]:
    if os.environ.get("TRANSACTION_EGRESS_BOOTSTRAP_LIVE_AUTHORIZED") != "1":
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
        or binding.domain != "transaction"
        or binding.candidate_run_id != CANDIDATE_RUN_ID
        or binding.candidate_manifest_sha256 != CANDIDATE_MANIFEST_SHA256
        or binding.candidate_authorization_sha256 != CANDIDATE_AUTHORIZATION_SHA256
    ):
        raise BootstrapPhaseError("authorization_binding_invalid")
    lifecycle, result = output_paths(repository_root)
    operations = TransactionLiveBootstrapOperations(
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
