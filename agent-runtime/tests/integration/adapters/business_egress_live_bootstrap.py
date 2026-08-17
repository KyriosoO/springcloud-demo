from __future__ import annotations

import hashlib
import http.cookiejar
import json
import os
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, NoReturn, Protocol, cast


Domain = Literal["employee", "transaction"]
BootstrapStatus = Literal[
    "passed",
    "failed_pre_candidate_unconsumed",
    "failed_candidate",
    "failed_cleanup_required",
]
PhaseStatus = Literal["started", "passed", "failed"]

COMMON_PHASES: Final = (
    "asset_preflight",
    "config_resolution",
    "auth_start",
    "auth_readiness",
    "auth_login",
)
EMPLOYEE_PHASES: Final = COMMON_PHASES + ("candidate_invoke",)
TRANSACTION_PHASES: Final = COMMON_PHASES + (
    "domain_start",
    "domain_readiness",
    "candidate_invoke",
)
TERMINAL_PHASE: Final = "cleanup"
SCHEMA_VERSION: Final = 1
_SHA256 = re.compile(r"[0-9a-f]{64}")
_FAILURE_REASONS: Final = frozenset(
    {
        "none",
        "asset_hash_invalid",
        "authorization_binding_invalid",
        "config_missing",
        "config_duplicate",
        "config_invalid",
        "port_occupied",
        "process_start_failed",
        "process_exited",
        "readiness_timeout",
        "readiness_pid_mismatch",
        "login_failed",
        "candidate_failed",
        "phase_timeout",
        "cancelled",
        "cleanup_failed",
        "log_leak_detected",
        "log_delete_failed",
        "evidence_write_failed",
        "internal_failure",
    }
)
_RESULT_KEYS: Final = frozenset(
    {
        "schemaVersion",
        "runId",
        "manifestSha256",
        "authorizationReference",
        "domain",
        "status",
        "candidateInvoked",
        "counts",
        "safety",
        "failure",
    }
)
_EVENT_KEYS: Final = frozenset(
    {
        "schemaVersion",
        "runId",
        "manifestSha256",
        "authorizationReference",
        "domain",
        "sequence",
        "phase",
        "status",
        "reason",
    }
)


class BootstrapContractError(RuntimeError):
    pass


class BootstrapPhaseError(RuntimeError):
    def __init__(self, reason: str) -> None:
        if reason not in _FAILURE_REASONS or reason == "none":
            reason = "internal_failure"
        super().__init__(reason)
        self.reason = reason


def _invalid() -> NoReturn:
    raise BootstrapContractError("business.egress_live_bootstrap_invalid")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _invalid()
        value[key] = item
    return value


def load_strict_json(path: Path, *, maximum_bytes: int = 1_048_576) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size > maximum_bytes:
        _invalid()
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda _value: _invalid(),
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        _invalid()
    if not isinstance(value, dict):
        _invalid()
    return cast(dict[str, Any], value)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_exclusive(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise BootstrapContractError("business.egress_live_bootstrap_output_exists") from exc


@dataclass(frozen=True)
class BootstrapBinding:
    run_id: str
    manifest_sha256: str
    authorization_reference: str
    domain: Domain
    wrapper_source_commit: str
    candidate_run_id: str
    candidate_manifest_sha256: str
    candidate_authorization_sha256: str

    def validate(self) -> None:
        if (
            not self.run_id
            or self.domain not in {"employee", "transaction"}
            or not _SHA256.fullmatch(self.manifest_sha256)
            or not self.authorization_reference.startswith("P3_00:GATE-")
            or not re.fullmatch(r"[0-9a-f]{40}", self.wrapper_source_commit)
            or not self.candidate_run_id
            or not _SHA256.fullmatch(self.candidate_manifest_sha256)
            or not _SHA256.fullmatch(self.candidate_authorization_sha256)
        ):
            _invalid()


@dataclass(frozen=True)
class CleanupOutcome:
    completed: bool
    owned_processes_stopped: bool
    raw_logs_deleted: bool
    log_leak_count: int = 0

    def validate(self) -> None:
        if self.log_leak_count < 0:
            _invalid()


class BootstrapOperations(Protocol):
    @property
    def candidate_started(self) -> bool: ...

    def run_phase(self, phase: str, *, deadline_seconds: float) -> None: ...

    def cleanup(self, *, candidate_started: bool, deadline_seconds: float) -> CleanupOutcome: ...


class BootstrapJournal:
    def __init__(self, path: Path, binding: BootstrapBinding) -> None:
        binding.validate()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._handle = path.open("x", encoding="utf-8", newline="\n")
        except FileExistsError as exc:
            raise BootstrapContractError("business.egress_live_bootstrap_output_exists") from exc
        self._binding = binding
        self._sequence = 0

    def append(self, phase: str, status: PhaseStatus, reason: str = "none") -> None:
        if reason not in _FAILURE_REASONS:
            _invalid()
        self._sequence += 1
        record = {
            "schemaVersion": SCHEMA_VERSION,
            "runId": self._binding.run_id,
            "manifestSha256": self._binding.manifest_sha256,
            "authorizationReference": self._binding.authorization_reference,
            "domain": self._binding.domain,
            "sequence": self._sequence,
            "phase": phase,
            "status": status,
            "reason": reason,
        }
        self._handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        self._handle.flush()
        os.fsync(self._handle.fileno())

    def close(self) -> None:
        self._handle.close()


def phases_for(domain: Domain) -> tuple[str, ...]:
    return EMPLOYEE_PHASES if domain == "employee" else TRANSACTION_PHASES


def execute_bootstrap(
    *,
    binding: BootstrapBinding,
    operations: BootstrapOperations,
    lifecycle_path: Path,
    result_path: Path,
    phase_deadline_seconds: float = 120.0,
    cleanup_deadline_seconds: float = 30.0,
) -> dict[str, object]:
    binding.validate()
    if phase_deadline_seconds <= 0 or cleanup_deadline_seconds <= 0 or result_path.exists():
        _invalid()
    journal = BootstrapJournal(lifecycle_path, binding)
    candidate_started = False
    failure_phase: str | None = None
    failure_reason = "none"
    status: BootstrapStatus = "passed"
    cleanup_outcome = CleanupOutcome(False, False, False, 0)
    started_count = 0
    terminal_count = 0
    try:
        for phase in phases_for(binding.domain):
            journal.append(phase, "started")
            started_count += 1
            try:
                operations.run_phase(phase, deadline_seconds=phase_deadline_seconds)
            except BootstrapPhaseError as exc:
                candidate_started = operations.candidate_started
                failure_phase = phase
                failure_reason = exc.reason
                journal.append(phase, "failed", exc.reason)
                terminal_count += 1
                status = (
                    "failed_candidate" if candidate_started else "failed_pre_candidate_unconsumed"
                )
                break
            except KeyboardInterrupt:
                candidate_started = operations.candidate_started
                failure_phase = phase
                failure_reason = "cancelled"
                journal.append(phase, "failed", failure_reason)
                terminal_count += 1
                status = (
                    "failed_candidate" if candidate_started else "failed_pre_candidate_unconsumed"
                )
                break
            except Exception:
                candidate_started = operations.candidate_started
                failure_phase = phase
                failure_reason = "internal_failure"
                journal.append(phase, "failed", failure_reason)
                terminal_count += 1
                status = (
                    "failed_candidate" if candidate_started else "failed_pre_candidate_unconsumed"
                )
                break
            else:
                candidate_started = operations.candidate_started
                journal.append(phase, "passed")
                terminal_count += 1
    finally:
        journal.append(TERMINAL_PHASE, "started")
        started_count += 1
        try:
            cleanup_outcome = operations.cleanup(
                candidate_started=candidate_started,
                deadline_seconds=cleanup_deadline_seconds,
            )
            cleanup_outcome.validate()
            if (
                not cleanup_outcome.completed
                or not cleanup_outcome.owned_processes_stopped
                or not cleanup_outcome.raw_logs_deleted
                or cleanup_outcome.log_leak_count != 0
            ):
                failure_reason = (
                    "log_leak_detected"
                    if cleanup_outcome.log_leak_count
                    else (
                        "log_delete_failed"
                        if not cleanup_outcome.raw_logs_deleted
                        else "cleanup_failed"
                    )
                )
                failure_phase = TERMINAL_PHASE
                status = "failed_cleanup_required" if candidate_started else "failed_pre_candidate_unconsumed"
                journal.append(TERMINAL_PHASE, "failed", failure_reason)
            else:
                journal.append(TERMINAL_PHASE, "passed")
            terminal_count += 1
        except Exception:
            failure_phase = TERMINAL_PHASE
            failure_reason = "cleanup_failed"
            status = "failed_cleanup_required" if candidate_started else "failed_pre_candidate_unconsumed"
            journal.append(TERMINAL_PHASE, "failed", failure_reason)
            terminal_count += 1
        finally:
            journal.close()

    result: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "runId": binding.run_id,
        "manifestSha256": binding.manifest_sha256,
        "authorizationReference": binding.authorization_reference,
        "domain": binding.domain,
        "status": status,
        "candidateInvoked": candidate_started,
        "counts": {
            "phaseStarted": started_count,
            "phaseTerminal": terminal_count,
            "candidateInvocations": 1 if candidate_started else 0,
            "retry": 0,
            "resume": 0,
        },
        "safety": {
            "forbiddenFields": 0,
            "secretPersistence": 0,
            "logLeakCount": cleanup_outcome.log_leak_count,
            "rawLogsDeleted": cleanup_outcome.raw_logs_deleted,
            "ownedProcessesStopped": cleanup_outcome.owned_processes_stopped,
        },
        "failure": {"phase": failure_phase, "reason": failure_reason},
    }
    validate_result(result, binding=binding)
    _write_json_exclusive(result_path, result)
    return result


def validate_result(value: Mapping[str, object], *, binding: BootstrapBinding) -> None:
    if set(value) != _RESULT_KEYS:
        _invalid()
    if (
        value.get("schemaVersion") != SCHEMA_VERSION
        or value.get("runId") != binding.run_id
        or value.get("manifestSha256") != binding.manifest_sha256
        or value.get("authorizationReference") != binding.authorization_reference
        or value.get("domain") != binding.domain
        or value.get("status")
        not in {"passed", "failed_pre_candidate_unconsumed", "failed_candidate", "failed_cleanup_required"}
        or not isinstance(value.get("candidateInvoked"), bool)
    ):
        _invalid()
    counts = value.get("counts")
    safety = value.get("safety")
    failure = value.get("failure")
    if not isinstance(counts, Mapping) or set(counts) != {
        "phaseStarted",
        "phaseTerminal",
        "candidateInvocations",
        "retry",
        "resume",
    }:
        _invalid()
    if not isinstance(safety, Mapping) or set(safety) != {
        "forbiddenFields",
        "secretPersistence",
        "logLeakCount",
        "rawLogsDeleted",
        "ownedProcessesStopped",
    }:
        _invalid()
    if not isinstance(failure, Mapping) or set(failure) != {"phase", "reason"}:
        _invalid()
    integer_counts = (
        counts.get("phaseStarted"),
        counts.get("phaseTerminal"),
        counts.get("candidateInvocations"),
        counts.get("retry"),
        counts.get("resume"),
    )
    if any(not isinstance(item, int) or isinstance(item, bool) or item < 0 for item in integer_counts):
        _invalid()
    if (
        counts.get("phaseStarted") != counts.get("phaseTerminal")
        or counts.get("candidateInvocations") not in {0, 1}
        or counts.get("retry") != 0
        or counts.get("resume") != 0
    ):
        _invalid()
    if (
        safety.get("forbiddenFields") != 0
        or safety.get("secretPersistence") != 0
        or not isinstance(safety.get("logLeakCount"), int)
        or isinstance(safety.get("logLeakCount"), bool)
        or cast(int, safety.get("logLeakCount")) < 0
        or not isinstance(safety.get("rawLogsDeleted"), bool)
        or not isinstance(safety.get("ownedProcessesStopped"), bool)
    ):
        _invalid()
    status = value["status"]
    candidate_invoked = value["candidateInvoked"]
    if status == "failed_pre_candidate_unconsumed" and candidate_invoked is not False:
        _invalid()
    if status in {"failed_candidate", "failed_cleanup_required"} and candidate_invoked is not True:
        _invalid()
    reason = failure.get("reason")
    if not isinstance(reason, str) or reason not in _FAILURE_REASONS:
        _invalid()
    if status == "passed" and (failure.get("phase") is not None or reason != "none"):
        _invalid()
    if status == "passed" and (
        candidate_invoked is not True
        or counts.get("candidateInvocations") != 1
        or safety.get("logLeakCount") != 0
        or safety.get("rawLogsDeleted") is not True
        or safety.get("ownedProcessesStopped") is not True
    ):
        _invalid()
    if candidate_invoked is not (counts.get("candidateInvocations") == 1):
        _invalid()
    if status != "passed" and (failure.get("phase") is None or reason == "none"):
        _invalid()


def read_lifecycle(path: Path, *, binding: BootstrapBinding) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for expected_sequence, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        value = json.loads(line, object_pairs_hook=_unique_object)
        if not isinstance(value, dict) or set(value) != _EVENT_KEYS:
            _invalid()
        if (
            value.get("schemaVersion") != SCHEMA_VERSION
            or value.get("runId") != binding.run_id
            or value.get("manifestSha256") != binding.manifest_sha256
            or value.get("authorizationReference") != binding.authorization_reference
            or value.get("domain") != binding.domain
            or value.get("sequence") != expected_sequence
            or value.get("status") not in {"started", "passed", "failed"}
            or value.get("reason") not in _FAILURE_REASONS
        ):
            _invalid()
        records.append(cast(dict[str, object], value))
    if not records:
        _invalid()
    expected_phases = phases_for(binding.domain)
    cursor = 0
    failed = False
    for phase in expected_phases:
        if cursor >= len(records) or records[cursor].get("phase") == TERMINAL_PHASE:
            break
        started = records[cursor]
        if (
            started.get("phase") != phase
            or started.get("status") != "started"
            or started.get("reason") != "none"
        ):
            _invalid()
        cursor += 1
        if cursor >= len(records):
            _invalid()
        terminal = records[cursor]
        if terminal.get("phase") != phase or terminal.get("status") not in {"passed", "failed"}:
            _invalid()
        if terminal.get("status") == "passed" and terminal.get("reason") != "none":
            _invalid()
        if terminal.get("status") == "failed":
            if terminal.get("reason") == "none":
                _invalid()
            failed = True
        cursor += 1
        if failed:
            break
    if cursor + 2 != len(records):
        _invalid()
    cleanup_started, cleanup_terminal = records[cursor], records[cursor + 1]
    if (
        cleanup_started.get("phase") != TERMINAL_PHASE
        or cleanup_started.get("status") != "started"
        or cleanup_started.get("reason") != "none"
        or cleanup_terminal.get("phase") != TERMINAL_PHASE
        or cleanup_terminal.get("status") not in {"passed", "failed"}
        or (
            cleanup_terminal.get("status") == "passed"
            and cleanup_terminal.get("reason") != "none"
        )
        or (
            cleanup_terminal.get("status") == "failed"
            and cleanup_terminal.get("reason") == "none"
        )
    ):
        _invalid()
    return records


def validate_prepared_assets(
    *, repository_root: Path, manifest_path: Path, authorization_path: Path
) -> BootstrapBinding:
    manifest = load_strict_json(manifest_path)
    manifest_sha = sha256_file(manifest_path)
    authorization = load_strict_json(authorization_path)
    required_manifest = {
        "schemaVersion",
        "status",
        "runId",
        "authorizationReference",
        "domain",
        "wrapperSourceCommit",
        "candidate",
        "assetHashes",
        "historyHashes",
        "executionBoundary",
    }
    if set(manifest) != required_manifest or manifest.get("schemaVersion") != SCHEMA_VERSION:
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
        domain=cast(Domain, manifest.get("domain")),
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
    }:
        _invalid()
    if (
        authorization.get("schemaVersion") != SCHEMA_VERSION
        or authorization.get("runId") != binding.run_id
        or authorization.get("manifestSha256") != manifest_sha
        or authorization.get("authorizationReference") != binding.authorization_reference
        or authorization.get("liveExecutionAuthorized") is not False
    ):
        _invalid()
    execution_boundary = manifest.get("executionBoundary")
    if not isinstance(execution_boundary, Mapping) or set(execution_boundary) != {
        "liveExecutionAuthorized",
        "sideEffectsAllowed",
        "candidateInvocationsMaximum",
        "retryAllowed",
        "resumeAllowed",
    }:
        _invalid()
    if (
        execution_boundary.get("liveExecutionAuthorized") is not False
        or execution_boundary.get("sideEffectsAllowed") is not False
        or execution_boundary.get("candidateInvocationsMaximum") != 1
        or execution_boundary.get("retryAllowed") is not False
        or execution_boundary.get("resumeAllowed") is not False
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
        target = (repository_root / relative).resolve()
        if (
            repository_root.resolve() not in target.parents
            or not target.is_file()
            or sha256_file(target) != expected
        ):
            _invalid()
    for key in ("assetHashes", "historyHashes"):
        rows = manifest.get(key)
        if not isinstance(rows, list) or not rows:
            _invalid()
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
            ):
                _invalid()
            seen.add(relative)
            candidate_path = (repository_root / relative).resolve()
            if (
                repository_root.resolve() not in candidate_path.parents
                or not _SHA256.fullmatch(expected)
                or not candidate_path.is_file()
                or sha256_file(candidate_path) != expected
            ):
                _invalid()
    return binding


def resolve_yaml_scalar_paths(path: Path, required_paths: Sequence[str]) -> dict[str, str]:
    """Resolve a tiny YAML mapping subset without serializing resolved values."""
    wanted = set(required_paths)
    if not wanted or len(wanted) != len(required_paths):
        _invalid()
    stack: list[tuple[int, str]] = []
    found: dict[str, str] = {}
    key_pattern = re.compile(r"([A-Za-z0-9_.-]+):(?:[ \t]+(.*))?")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        raise BootstrapPhaseError("config_missing")
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent_text = raw[: len(raw) - len(raw.lstrip(" "))]
        if "\t" in indent_text or len(indent_text) % 2:
            raise BootstrapPhaseError("config_invalid")
        content = raw[len(indent_text) :]
        match = key_pattern.fullmatch(content)
        if match is None:
            raise BootstrapPhaseError("config_invalid")
        indent = len(indent_text)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        key = match.group(1)
        value = match.group(2)
        path_key = ".".join([item[1] for item in stack] + [key])
        if value is None or not value.strip():
            stack.append((indent, key))
            continue
        scalar = value.strip()
        if scalar.startswith(("|", ">", "&", "*", "!", "[", "{")) or "${" in scalar:
            raise BootstrapPhaseError("config_invalid")
        if scalar[0:1] in {"'", '"'}:
            quote = scalar[0]
            if len(scalar) < 2 or scalar[-1] != quote:
                raise BootstrapPhaseError("config_invalid")
            scalar = scalar[1:-1]
        elif " #" in scalar:
            scalar = scalar.split(" #", 1)[0].rstrip()
        if path_key in wanted:
            if path_key in found:
                raise BootstrapPhaseError("config_duplicate")
            if not scalar or any(ord(character) < 32 for character in scalar):
                raise BootstrapPhaseError("config_invalid")
            found[path_key] = scalar
    if set(found) != wanted:
        raise BootstrapPhaseError("config_missing")
    return found


def resolve_noop_user_password(path: Path, *, user_id: str) -> str:
    """Read one local noop fixture without multiline regular expressions."""
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", user_id):
        raise BootstrapPhaseError("config_invalid")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        raise BootstrapPhaseError("config_missing")
    matches: list[str] = []
    in_auth = False
    in_users = False
    in_target = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        spaces = len(line) - len(line.lstrip(" "))
        if spaces == 0:
            in_auth = stripped == "auth:"
            in_users = False
            in_target = False
        elif spaces == 2 and in_auth:
            in_users = stripped == "users:"
            in_target = False
        elif spaces == 4 and in_users and stripped.endswith(":"):
            in_target = stripped[:-1] == user_id
        elif spaces == 6 and in_target and stripped.startswith("password:"):
            scalar = stripped.removeprefix("password:").strip()
            if scalar[:1] in {"'", '"'}:
                quote = scalar[0]
                if len(scalar) < 2 or scalar[-1] != quote:
                    raise BootstrapPhaseError("config_invalid")
                scalar = scalar[1:-1]
            if not scalar.startswith("{noop}") or len(scalar) <= len("{noop}"):
                raise BootstrapPhaseError("config_invalid")
            matches.append(scalar[len("{noop}") :])
    if not matches:
        raise BootstrapPhaseError("config_missing")
    if len(matches) != 1:
        raise BootstrapPhaseError("config_duplicate")
    return matches[0]


def assert_loopback_port_free(port: int) -> None:
    if not 1 <= port <= 65_535:
        raise BootstrapPhaseError("config_invalid")
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        probe.bind(("127.0.0.1", port))
    except OSError as exc:
        raise BootstrapPhaseError("port_occupied") from exc
    finally:
        probe.close()


def assert_process_owns_listener(*, port: int, process: OwnedProcess) -> None:
    if process.process.poll() is not None:
        raise BootstrapPhaseError("process_exited")
    if os.name != "nt":
        raise BootstrapPhaseError("readiness_pid_mismatch")
    command = (
        "$ErrorActionPreference='Stop';"
        f"$rows=@(Get-NetTCPConnection -State Listen -LocalPort {port});"
        "if($rows.Count -lt 1){exit 3};"
        "$owners=@($rows|Select-Object -ExpandProperty OwningProcess -Unique);"
        "if($owners.Count -ne 1){exit 4};"
        "[Console]::Out.Write([string]$owners[0])"
    )
    try:
        completed = subprocess.run(
            ["pwsh", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BootstrapPhaseError("readiness_pid_mismatch") from exc
    if completed.returncode != 0 or completed.stdout.strip() != str(process.process.pid):
        raise BootstrapPhaseError("readiness_pid_mismatch")


def wait_owned_listener(
    *, port: int, process: OwnedProcess, deadline_seconds: float
) -> None:
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        if process.process.poll() is not None:
            raise BootstrapPhaseError("process_exited")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.25)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                assert_process_owns_listener(port=port, process=process)
                return
        time.sleep(0.25)
    raise BootstrapPhaseError("readiness_timeout")


def issue_auth_cookie(
    *, base_url: str, user_id: str, password: str, deadline_seconds: float
) -> str:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    request = urllib.request.Request(
        f"{base_url}/login",
        data=json.dumps(
            {"userId": user_id, "password": password}, separators=(",", ":")
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener.open(request, timeout=deadline_seconds) as response:
            if response.status != 200:
                raise BootstrapPhaseError("login_failed")
    except BootstrapPhaseError:
        raise
    except (OSError, urllib.error.URLError) as exc:
        raise BootstrapPhaseError("login_failed") from exc
    tokens = [cookie.value for cookie in jar if cookie.name == "AUTH_TOKEN" and cookie.value]
    if len(tokens) != 1:
        raise BootstrapPhaseError("login_failed")
    return tokens[0]


def limited_child_environment(overrides: Mapping[str, str]) -> dict[str, str]:
    inherited = (
        "PATH",
        "JAVA_HOME",
        "MAVEN_HOME",
        "M2_HOME",
        "USERPROFILE",
        "HOMEDRIVE",
        "HOMEPATH",
        "SystemRoot",
        "TEMP",
        "TMP",
        "LOCALAPPDATA",
        "APPDATA",
        "ProgramFiles",
        "ProgramFiles(x86)",
        "ProgramData",
        "ComSpec",
        "PATHEXT",
    )
    environment = {name: os.environ[name] for name in inherited if name in os.environ}
    for name, value in overrides.items():
        if not name or not isinstance(value, str) or "\0" in value:
            raise BootstrapPhaseError("config_invalid")
        environment[name] = value
    return environment


def common_security_arguments(*, port: int) -> tuple[str, ...]:
    return (
        f"--server.port={port}",
        "--spring.main.banner-mode=off",
        "--spring.cloud.config.enabled=false",
        "--spring.config.import=",
        "--eureka.client.enabled=false",
        "--management.endpoints.enabled-by-default=false",
        "--common.security.secrets.source-order[0]=environment",
        "--common.security.secrets.allow-config-values=false",
        "--common.security.secrets.fail-fast=true",
        "--common.security.secrets.jwt.active-key-id=ACTIVE",
        "--common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE",
        "--common.security.secrets.jwt.keys.ACTIVE.value=",
    )


@dataclass
class OwnedProcess:
    process: subprocess.Popen[bytes]
    stdout_path: Path
    stderr_path: Path


class LocalProcessRuntime:
    def __init__(self, temp_directory: Path) -> None:
        self.temp_directory = temp_directory
        self._created = False
        self.processes: list[OwnedProcess] = []
        self.secret_literals: list[str] = []

    def start(
        self,
        *,
        name: str,
        command: Sequence[str],
        working_directory: Path,
        environment: Mapping[str, str],
    ) -> OwnedProcess:
        if not self._created:
            if self.temp_directory.exists():
                raise BootstrapPhaseError("process_start_failed")
            self.temp_directory.mkdir(parents=True, exist_ok=False)
            self._created = True
        stdout_path = self.temp_directory / f"{name}.out.log"
        stderr_path = self.temp_directory / f"{name}.err.log"
        stdout_handle = stdout_path.open("xb")
        stderr_handle = stderr_path.open("xb")
        try:
            process = subprocess.Popen(
                list(command),
                cwd=working_directory,
                env=dict(environment),
                stdout=stdout_handle,
                stderr=stderr_handle,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            raise BootstrapPhaseError("process_start_failed") from exc
        finally:
            stdout_handle.close()
            stderr_handle.close()
        owned = OwnedProcess(process, stdout_path, stderr_path)
        self.processes.append(owned)
        return owned

    @staticmethod
    def wait_http(
        uri: str,
        process: OwnedProcess,
        *,
        port: int,
        deadline_seconds: float,
    ) -> None:
        deadline = time.monotonic() + deadline_seconds
        while time.monotonic() < deadline:
            if process.process.poll() is not None:
                raise BootstrapPhaseError("process_exited")
            try:
                with urllib.request.urlopen(uri, timeout=2) as response:
                    if response.status == 200:
                        assert_process_owns_listener(port=port, process=process)
                        return
            except (OSError, urllib.error.URLError):
                time.sleep(0.25)
        raise BootstrapPhaseError("readiness_timeout")

    @staticmethod
    def wait_exit(process: OwnedProcess, *, deadline_seconds: float) -> None:
        try:
            exit_code = process.process.wait(timeout=deadline_seconds)
        except subprocess.TimeoutExpired as exc:
            raise BootstrapPhaseError("phase_timeout") from exc
        if exit_code != 0:
            raise BootstrapPhaseError("candidate_failed")

    def cleanup(self) -> CleanupOutcome:
        stopped = True
        for owned in reversed(self.processes):
            if owned.process.poll() is None:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(owned.process.pid), "/T"],
                        check=False,
                        capture_output=True,
                        timeout=10,
                    )
                else:
                    owned.process.terminate()
                try:
                    owned.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    if os.name == "nt":
                        subprocess.run(
                            ["taskkill", "/PID", str(owned.process.pid), "/T", "/F"],
                            check=False,
                            capture_output=True,
                            timeout=10,
                        )
                    else:
                        owned.process.kill()
                    try:
                        owned.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        stopped = False
        leak_count = 0
        if not self.temp_directory.exists():
            return CleanupOutcome(
                completed=stopped,
                owned_processes_stopped=stopped,
                raw_logs_deleted=True,
                log_leak_count=0,
            )
        for path in self.temp_directory.glob("*.log"):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                leak_count += 1
                continue
            leak_count += sum(1 for literal in self.secret_literals if literal and literal in text)
            if re.search(r"(?i)(?:authorization|jwt|api[_-]?key|password)\s*[:=]\s*\S+", text):
                leak_count += 1
        logs_deleted = False
        try:
            for path in self.temp_directory.iterdir():
                if path.is_file():
                    path.unlink()
            self.temp_directory.rmdir()
            logs_deleted = not self.temp_directory.exists()
        except OSError:
            logs_deleted = False
        return CleanupOutcome(
            completed=stopped and logs_deleted and leak_count == 0,
            owned_processes_stopped=stopped,
            raw_logs_deleted=logs_deleted,
            log_leak_count=leak_count,
        )
