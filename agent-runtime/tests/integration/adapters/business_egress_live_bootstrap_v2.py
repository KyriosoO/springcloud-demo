from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, NoReturn, cast

from tests.integration.adapters.business_egress_live_bootstrap import (
    BootstrapBinding,
    BootstrapContractError,
    OwnedProcess,
    load_strict_json,
    sha256_file,
)


ProcessDiagnosticClassification = Literal[
    "configuration_binding",
    "class_loading",
    "port_binding",
    "dependency_connectivity",
    "application_context",
    "unknown",
]

SCHEMA_VERSION: Final = 2
MAXIMUM_LOG_BYTES: Final = 1_048_576
DIAGNOSTIC_CLASSIFICATIONS: Final = frozenset(
    {
        "configuration_binding",
        "class_loading",
        "port_binding",
        "dependency_connectivity",
        "application_context",
        "unknown",
    }
)
EXECUTABLE_ASSET_PATHS: Final = frozenset(
    {
        "auth-service/target/auth-service-0.0.1-SNAPSHOT.jar",
        "mq-procedure-service/target/mq-procedure-service-0.0.1-SNAPSHOT.jar",
    }
)
BUILD_COMMAND: Final = (
    "mvn -f serviceCenter/pom.xml -pl :auth-service,:mq-procedure-service "
    "-am -DskipTests package"
)
_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_SOURCE_COMMIT: Final = re.compile(r"[0-9a-f]{40}")
_DIAGNOSTIC_KEYS: Final = frozenset(
    {
        "schemaVersion",
        "runId",
        "manifestSha256",
        "authorizationReference",
        "domain",
        "service",
        "phase",
        "classification",
        "exitCodePresent",
        "safety",
    }
)
_CLASSIFICATION_PATTERNS: Final = (
    (
        "class_loading",
        re.compile(
            r"(?:ClassNotFoundException|NoClassDefFoundError|UnsupportedClassVersionError|Could not find or load main class)",
            re.IGNORECASE,
        ),
    ),
    (
        "port_binding",
        re.compile(
            r"(?:Port\s+\d+\s+was already in use|Address already in use|BindException[^\r\n]*address)",
            re.IGNORECASE,
        ),
    ),
    (
        "configuration_binding",
        re.compile(
            r"(?:ConfigurationPropertiesBindException|Failed to bind properties|Could not resolve placeholder|Failed to bind\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "dependency_connectivity",
        re.compile(
            r"(?:Connection refused|Communications link failure|RedisConnectionException|Kafka[^\r\n]{0,120}(?:connection|connect)|Connect timed out)",
            re.IGNORECASE,
        ),
    ),
    (
        "application_context",
        re.compile(
            r"(?:APPLICATION FAILED TO START|ApplicationContextException|BeanCreationException|UnsatisfiedDependencyException)",
            re.IGNORECASE,
        ),
    ),
)


def _invalid() -> NoReturn:
    raise BootstrapContractError("business.egress_live_bootstrap_v2_invalid")


def _write_json_exclusive(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise BootstrapContractError("business.egress_live_bootstrap_v2_output_exists") from exc


def _read_bounded_log(path: Path) -> str | None:
    try:
        if not path.is_file() or path.stat().st_size > MAXIMUM_LOG_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def classify_process_exit(log_texts: Sequence[str | None]) -> ProcessDiagnosticClassification:
    if not log_texts or any(text is None for text in log_texts):
        return "unknown"
    combined = "\n".join(cast(str, text) for text in log_texts)
    for classification, pattern in _CLASSIFICATION_PATTERNS:
        if pattern.search(combined):
            return cast(ProcessDiagnosticClassification, classification)
    return "unknown"


def count_log_leaks(log_texts: Sequence[str | None], secret_literals: Sequence[str]) -> int:
    leak_count = 0
    for text in log_texts:
        if text is None:
            leak_count += 1
            continue
        leak_count += sum(1 for literal in secret_literals if literal and literal in text)
        if re.search(r"(?i)(?:authorization|jwt|api[_-]?key|password)\s*[:=]\s*\S+", text):
            leak_count += 1
    return leak_count


@dataclass(frozen=True)
class ProcessDiagnostic:
    service: Literal["auth-service", "transaction-service"]
    phase: str
    classification: ProcessDiagnosticClassification
    exit_code_present: bool
    log_leak_count: int

    @classmethod
    def inspect(
        cls,
        *,
        process: OwnedProcess,
        service: Literal["auth-service", "transaction-service"],
        phase: str,
        secret_literals: Sequence[str],
    ) -> "ProcessDiagnostic":
        log_texts = (
            _read_bounded_log(process.stdout_path),
            _read_bounded_log(process.stderr_path),
        )
        return cls(
            service=service,
            phase=phase,
            classification=classify_process_exit(log_texts),
            exit_code_present=process.process.poll() is not None,
            log_leak_count=count_log_leaks(log_texts, secret_literals),
        )

    def write(self, *, path: Path, binding: BootstrapBinding) -> dict[str, object]:
        value: dict[str, object] = {
            "schemaVersion": SCHEMA_VERSION,
            "runId": binding.run_id,
            "manifestSha256": binding.manifest_sha256,
            "authorizationReference": binding.authorization_reference,
            "domain": binding.domain,
            "service": self.service,
            "phase": self.phase,
            "classification": self.classification,
            "exitCodePresent": self.exit_code_present,
            "safety": {
                "forbiddenFields": 0,
                "secretPersistence": 0,
                "logLeakCount": self.log_leak_count,
            },
        }
        validate_process_diagnostic(value, binding=binding)
        _write_json_exclusive(path, value)
        return value


def validate_process_diagnostic(
    value: Mapping[str, object], *, binding: BootstrapBinding
) -> None:
    if set(value) != _DIAGNOSTIC_KEYS:
        _invalid()
    if (
        value.get("schemaVersion") != SCHEMA_VERSION
        or value.get("runId") != binding.run_id
        or value.get("manifestSha256") != binding.manifest_sha256
        or value.get("authorizationReference") != binding.authorization_reference
        or value.get("domain") != binding.domain
        or value.get("service")
        not in {"auth-service", "transaction-service"}
        or value.get("phase") not in {"auth_readiness", "auth_login", "domain_readiness"}
        or value.get("classification") not in DIAGNOSTIC_CLASSIFICATIONS
        or value.get("exitCodePresent") is not True
    ):
        _invalid()
    safety = value.get("safety")
    if not isinstance(safety, Mapping) or set(safety) != {
        "forbiddenFields",
        "secretPersistence",
        "logLeakCount",
    }:
        _invalid()
    if (
        safety.get("forbiddenFields") != 0
        or safety.get("secretPersistence") != 0
        or not isinstance(safety.get("logLeakCount"), int)
        or isinstance(safety.get("logLeakCount"), bool)
        or cast(int, safety.get("logLeakCount")) < 0
    ):
        _invalid()


def load_process_diagnostic(path: Path, *, binding: BootstrapBinding) -> dict[str, object]:
    value = load_strict_json(path)
    validate_process_diagnostic(value, binding=binding)
    return value


def _validate_hash_rows(
    *, repository_root: Path, rows: object, required_paths: frozenset[str] | None = None
) -> frozenset[str]:
    if not isinstance(rows, list) or not rows:
        _invalid()
    seen: set[str] = set()
    root = repository_root.resolve()
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


def validate_prepared_assets_v2(
    *, repository_root: Path, manifest_path: Path, authorization_path: Path
) -> BootstrapBinding:
    manifest = load_strict_json(manifest_path)
    manifest_sha = sha256_file(manifest_path)
    authorization = load_strict_json(authorization_path)
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
    } or manifest.get("schemaVersion") != SCHEMA_VERSION:
        _invalid()
    if manifest.get("status") != "prepared_unconsumed":
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
        authorization.get("schemaVersion") != SCHEMA_VERSION
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
    }:
        _invalid()
    if (
        not isinstance(build.get("sourceCommit"), str)
        or not _SOURCE_COMMIT.fullmatch(cast(str, build.get("sourceCommit")))
        or build.get("sourceCommit") != binding.wrapper_source_commit
        or build.get("command") != BUILD_COMMAND
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
        target = (repository_root.resolve() / relative).resolve()
        if (
            repository_root.resolve() not in target.parents
            or not target.is_file()
            or sha256_file(target) != expected
        ):
            _invalid()
    _validate_hash_rows(repository_root=repository_root, rows=manifest.get("assetHashes"))
    _validate_hash_rows(
        repository_root=repository_root,
        rows=manifest.get("executableHashes"),
        required_paths=EXECUTABLE_ASSET_PATHS,
    )
    _validate_hash_rows(repository_root=repository_root, rows=manifest.get("historyHashes"))
    return binding
