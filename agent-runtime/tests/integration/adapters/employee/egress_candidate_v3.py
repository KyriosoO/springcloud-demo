from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, NoReturn, cast


RUN_ID: Final = "employee-egress-v3-20260817-candidate-03"
PREPARATION_WORK_PACKAGE_ID: Final = "WP-EMP-EGRESS-CANDIDATE-03-PREP"
WORK_PACKAGE_ID: Final = "WP-EMP-EGRESS-01"
PREPARATION_GATE_ID: Final = "GATE-052"
GATE_ID: Final = "GATE-024"
AUTHORIZATION_REFERENCE: Final = "P3_00:GATE-024"
SCHEMA_VERSION: Final = 3
MAX_DATABASE_SELECTS: Final = 3
MAX_DATABASE_INSERTS: Final = 1
MAX_DATABASE_DELETES: Final = 1
MAX_EMPLOYEE_DETAILS: Final = 1
MAXIMUM_PAID_ANSWER_CALLS: Final = 30
MINIMUM_VALID_ANSWER_CALLS: Final = 27
EXPECTED_PASSED_RECORDS: Final = 76
MODEL_VISIBLE_FIELD_IDS: Final = ("position", "work_base_si")

RunStatus = Literal[
    "passed", "failed_unconsumed", "failed_consumed", "failed_cleanup_required"
]
ModelTerminal = Literal[
    "answer", "invalid_output", "input_denied", "timeout", "provider_failure"
]
FaultPhase = Literal[
    "none",
    "fixture_precheck",
    "fixture_insert",
    "fixture_verify",
    "employee_detail",
    "model_setup",
    "forbidden_payload",
    "model_answer",
    "threshold",
    "cleanup_delete",
    "cleanup_verify",
    "host_validation",
]

_SHA256 = frozenset("0123456789abcdef")
_TERMINAL_MODEL_STATES = frozenset(
    {"answer", "invalid_output", "input_denied", "timeout", "provider_failure"}
)
_NON_RUN_PHASES = (
    "fixture_precheck",
    "fixture_insert",
    "fixture_verify",
    "employee_detail",
    "model_answer",
    "cleanup_delete",
    "cleanup_verify",
    "host_validation",
)
_PHASE_ORDER = {phase: index for index, phase in enumerate(_NON_RUN_PHASES)}
_FAILURE_REASONS = frozenset(
    {
        "none",
        "identifier_conflict",
        "database_operation_failed",
        "employee_request_failed",
        "employee_result_invalid",
        "egress_projection_invalid",
        "model_setup_failed",
        "model_call_failed",
        "threshold_not_met",
        "cleanup_failed",
        "log_leak_detected",
        "host_failed",
        "evidence_write_failed",
    }
)
_RECORD_KEYS = frozenset(
    {
        "schemaVersion",
        "runId",
        "manifestSha256",
        "authorizationReference",
        "sequence",
        "phase",
        "state",
        "reason",
        "failurePhase",
        "ordinal",
    }
)
_FAILURE_PHASES = frozenset(
    {
        "none",
        "fixture_precheck",
        "fixture_insert",
        "fixture_verify",
        "employee_detail",
        "model_setup",
        "model_answer",
        "threshold",
        "cleanup_delete",
        "cleanup_verify",
        "host_validation",
    }
)

HISTORY_ASSETS: Final = (
    (
        "employee_real_authorization_matrix",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "wp-emp-real-01-20260806T075036Z.json",
        "f5af997fd9b7b8cce6a6b99fcd6c00dddc43ff105ab2c69c085801d7d2ff382c",
    ),
    (
        "employee_gateway_log_safety",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "wp-emp-gateway-log-20260806T091456Z.json",
        "eb9342b550f2bc2a3a391563e24045baccfade687790ab2e5dbe396d3a92396e",
    ),
    (
        "qualification_v6_manifest",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v6-20260816-candidate-06.manifest.json",
        "44f25232b445e0f1c8184b31ccf2dff4d5751a796b4f3ec327fb1ea2cbb702b2",
    ),
    (
        "qualification_v6_authorization",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v6-20260816-candidate-06.authorization.json",
        "bd0cb4d67c00e2aeba7756860f02a4f7df1fd9f17eb9420cc3ece4e524a697c5",
    ),
    (
        "qualification_v6_host_lifecycle",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v6-20260816-candidate-06.host-lifecycle.jsonl",
        "9c4f7d9981bef665bd06068a96155433bfbe838ebad65d4ac5dc4424106c28d5",
    ),
    (
        "qualification_v6_lifecycle",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v6-20260816-candidate-06.lifecycle.jsonl",
        "ec87bcb430fc90b3e9511871625bba60c07f7d4cc7e12842f3e18255624f6677",
    ),
    (
        "qualification_v6_result",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-input-qualification-v6-20260816-candidate-06.result.json",
        "750f2e0d13866203116884e1950734bcb2b06100343f142cb5e96c63fe55a9cd",
    ),
    (
        "egress_v1_manifest",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-v1-20260813-candidate-01.manifest.json",
        "c3cdfacd32797474f68e11758ec094df97a95d56fb0efed9355ccfaa6a145c57",
    ),
    (
        "egress_v1_authorization",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-v1-20260813-candidate-01.authorization.json",
        "52b9075117f3e5f3ea84f1ea3c5da846c7b168f013fc4d8523d7ed52979f416c",
    ),
    (
        "egress_v1_environment_diagnostic",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "wp-emp-egress-env-diag-01-20260814T004517Z.json",
        "2bc16cf63f3775d778925a5a5a66cfbae5138401e2f209e8288f4db076598a2c",
    ),
    (
        "egress_v1_pre_model_failure",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-v1-20260813-candidate-01.pre-model-failure-20260814T005222Z.json",
        "1a55b324fc912ee4e9133c2946183473347eb8e7f3337f8e33286bdf96f0b76f",
    ),
    (
        "egress_v2_manifest",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-v2-20260814-candidate-02.manifest.json",
        "28cd7b04b0700b43e5feed7bdef22e9da0494cd941e2e9f96b698a75b21b03b1",
    ),
    (
        "egress_v2_authorization",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-v2-20260814-candidate-02.authorization.json",
        "6fe6489fb5d32481909b88b860325dbbc35dec0c242d86f106327222e790c971",
    ),
    (
        "egress_v2_lifecycle",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-v2-20260814-candidate-02.lifecycle.jsonl",
        "15982e15d454795d7052215ad46221b6f85cc26726ca0267a597f6d6002ec679",
    ),
    (
        "egress_v2_result",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-v2-20260814-candidate-02.result.json",
        "dd8a5bac1586da4e44cc6a583c07289a91012bc34892f848ffb4a0241ae7561d",
    ),
    (
        "fixture_metadata_result",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-fixture-metadata-diagnostic-v2-20260814-candidate-02.result.json",
        "9973863d43112a8142bf54eaa1ea18905112d8ca802a24dda7eed5599ab7cd51",
    ),
    (
        "fixture_candidate_result",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-synthetic-fixture-v1-20260814-candidate-01.result.json",
        "f0003ec559fa4606edda2982f0ae6878bfa066262168236128705d0c40aa0e4a",
    ),
)

REQUIRED_ASSET_PATHS: Final = frozenset(
    {
        "agent-runtime/scripts/run-employee-egress-live-candidate-03.ps1",
        "agent-runtime/src/agent_runtime/bootstrap.py",
        "agent-runtime/src/agent_runtime/business/egress.py",
        "agent-runtime/src/agent_runtime/business/grounding.py",
        "agent-runtime/src/agent_runtime/business/handler.py",
        "agent-runtime/src/agent_runtime/business/settings.py",
        "agent-runtime/src/agent_runtime/business/user_projection.py",
        "agent-runtime/src/agent_runtime/model/deepseek/answer_generator.py",
        "agent-runtime/src/agent_runtime/model/deepseek/transport.py",
        "agent-runtime/src/agent_runtime/model/input_guard.py",
        "agent-runtime/src/agent_runtime/model/question_policy.py",
        "agent-runtime/src/agent_runtime/adapters/employee/definition.py",
        "agent-runtime/src/agent_runtime/adapters/employee/fields.py",
        "agent-runtime/src/agent_runtime/adapters/employee/settings.py",
        "agent-runtime/src/agent_runtime/adapters/employee/codec.py",
        "agent-runtime/src/agent_runtime/adapters/employee/normalizer.py",
        "agent-runtime/tests/fixtures/employee_egress_field_matrix.json",
        "agent-runtime/tests/integration/adapters/employee/egress_candidate_v3.py",
        "agent-runtime/tests/integration/adapters/employee/test_employee_egress_candidate_v3_harness.py",
        "agent-runtime/tests/integration/adapters/employee/test_employee_egress_candidate_v3_preparation.py",
        "agent-runtime/tests/integration/adapters/employee/test_employee_egress_candidate_v3_history.py",
        "agent-runtime/tests/integration/adapters/employee/test_real_employee_egress_candidate_v3.py",
        "agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-v3-lifecycle.schema.json",
        "agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-v3-consumed.schema.json",
        "agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-v3-staging.schema.json",
        "agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-v3-pending.schema.json",
        "agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-v3-result.schema.json",
        "employee-service/src/test/java/com/dylan/employee/live/EmployeeEgressCandidateV3LiveIntegrationTest.java",
    }
)


class EmployeeEgressCandidateV3Error(ValueError):
    pass


def _invalid() -> NoReturn:
    raise EmployeeEgressCandidateV3Error("employee.egress_candidate_v3_invalid")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _invalid()
        value[key] = item
    return value


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and set(value).issubset(_SHA256)
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_strict_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    if type(value) is not dict:
        _invalid()
    return cast(dict[str, Any], value)


def _write_exclusive(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def _append(path: Path, value: Mapping[str, object]) -> None:
    payload = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND)
    try:
        with os.fdopen(descriptor, "ab", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


@dataclass(frozen=True, slots=True, kw_only=True)
class LifecycleSnapshot:
    record_count: int
    status: RunStatus
    failure_phase: str
    failure_reason: str
    authorization_consumed: bool
    valid_answers: int
    counts: Mapping[str, int]


class LifecycleJournal:
    def __init__(self, path: Path, *, manifest_sha256: str, create: bool = True) -> None:
        if not _is_sha256(manifest_sha256):
            _invalid()
        self.path = path
        self.manifest_sha256 = manifest_sha256
        self.sequence = 0
        if create:
            if path.exists():
                _invalid()
            self._record("run", "started", "none", "none", None)
        else:
            records = _load_records(path, manifest_sha256=manifest_sha256)
            self.sequence = len(records)

    def pair(
        self,
        phase: str,
        *,
        terminal: str = "succeeded",
        reason: str = "none",
        ordinal: int | None = None,
    ) -> None:
        self._record(phase, "started", "none", "none", ordinal)
        self._record(phase, terminal, reason, "none", ordinal)

    def started(self, phase: str, *, ordinal: int | None = None) -> None:
        self._record(phase, "started", "none", "none", ordinal)

    def finished(
        self,
        phase: str,
        *,
        terminal: str,
        reason: str = "none",
        ordinal: int | None = None,
    ) -> None:
        self._record(phase, terminal, reason, "none", ordinal)

    def terminal(self, status: RunStatus, *, phase: str, reason: str) -> None:
        self._record("run", status, reason, phase, None)

    def _record(
        self,
        phase: str,
        state: str,
        reason: str,
        failure_phase: str,
        ordinal: int | None,
    ) -> None:
        record: dict[str, object] = {
            "schemaVersion": SCHEMA_VERSION,
            "runId": RUN_ID,
            "manifestSha256": self.manifest_sha256,
            "authorizationReference": AUTHORIZATION_REFERENCE,
            "sequence": self.sequence,
            "phase": phase,
            "state": state,
            "reason": reason,
            "failurePhase": failure_phase,
            "ordinal": ordinal,
        }
        if self.sequence == 0:
            _write_exclusive(self.path, record)
        else:
            _append(self.path, record)
        self.sequence += 1


def write_consumed_marker(path: Path, *, manifest_sha256: str) -> None:
    if not _is_sha256(manifest_sha256):
        _invalid()
    _write_exclusive(
        path,
        {
            "schemaVersion": SCHEMA_VERSION,
            "status": "consumed",
            "runId": RUN_ID,
            "manifestSha256": manifest_sha256,
            "authorizationReference": AUTHORIZATION_REFERENCE,
            "maximumPaidAnswerCalls": MAXIMUM_PAID_ANSWER_CALLS,
        },
    )


def validate_consumed_marker(value: object, *, manifest_sha256: str) -> dict[str, Any]:
    if type(value) is not dict:
        _invalid()
    result = cast(dict[str, Any], value)
    if set(result) != {
        "schemaVersion",
        "status",
        "runId",
        "manifestSha256",
        "authorizationReference",
        "maximumPaidAnswerCalls",
    }:
        _invalid()
    if (
        result["schemaVersion"] != SCHEMA_VERSION
        or result["status"] != "consumed"
        or result["runId"] != RUN_ID
        or result["manifestSha256"] != manifest_sha256
        or result["authorizationReference"] != AUTHORIZATION_REFERENCE
        or result["maximumPaidAnswerCalls"] != MAXIMUM_PAID_ANSWER_CALLS
    ):
        _invalid()
    return result


def _load_records(path: Path, *, manifest_sha256: str) -> list[dict[str, Any]]:
    if not path.is_file() or not _is_sha256(manifest_sha256):
        _invalid()
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line, object_pairs_hook=_unique_object)
        if type(value) is not dict:
            _invalid()
        record = cast(dict[str, Any], value)
        if set(record) != _RECORD_KEYS:
            _invalid()
        records.append(record)
    return records


def validate_lifecycle(
    path: Path,
    *,
    consumed_path: Path,
    manifest_sha256: str,
) -> LifecycleSnapshot:
    records = _load_records(path, manifest_sha256=manifest_sha256)
    if len(records) < 4:
        _invalid()
    common = {
        "schemaVersion": SCHEMA_VERSION,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
    }
    for sequence, record in enumerate(records):
        if any(record[key] != value for key, value in common.items()):
            _invalid()
        if record["sequence"] != sequence or record["reason"] not in _FAILURE_REASONS:
            _invalid()
        if record["failurePhase"] not in _FAILURE_PHASES:
            _invalid()
        if record["ordinal"] is not None and (
            type(record["ordinal"]) is not int
            or not 1 <= record["ordinal"] <= MAXIMUM_PAID_ANSWER_CALLS
        ):
            _invalid()
    first, last = records[0], records[-1]
    if (
        first["phase"] != "run"
        or first["state"] != "started"
        or first["reason"] != "none"
        or first["failurePhase"] != "none"
        or first["ordinal"] is not None
        or last["phase"] != "run"
        or last["state"]
        not in {"passed", "failed_unconsumed", "failed_consumed", "failed_cleanup_required"}
        or last["ordinal"] is not None
    ):
        _invalid()

    counts: Counter[str] = Counter()
    valid_answers = 0
    model_ordinals: list[int] = []
    failed_non_run_terminals = 0
    last_order = -1
    cursor = 1
    while cursor < len(records) - 1:
        started = records[cursor]
        if started["phase"] == "run" or started["state"] != "started":
            _invalid()
        phase = cast(str, started["phase"])
        if phase not in _PHASE_ORDER or cursor + 1 >= len(records):
            _invalid()
        terminal = records[cursor + 1]
        if (
            terminal["phase"] != phase
            or terminal["ordinal"] != started["ordinal"]
            or terminal["state"] == "started"
            or started["failurePhase"] != "none"
            or terminal["failurePhase"] != "none"
        ):
            _invalid()
        order = _PHASE_ORDER[phase]
        if order < last_order:
            _invalid()
        last_order = order
        if phase != "model_answer" and started["ordinal"] is not None:
            _invalid()
        if phase == "model_answer":
            ordinal = cast(int, started["ordinal"])
            if terminal["state"] not in _TERMINAL_MODEL_STATES:
                _invalid()
            model_ordinals.append(ordinal)
            if terminal["state"] == "answer":
                valid_answers += 1
        else:
            if terminal["state"] not in {"succeeded", "failed"}:
                _invalid()
            if terminal["state"] == "succeeded" and terminal["reason"] != "none":
                _invalid()
            if terminal["state"] == "failed":
                if terminal["reason"] == "none":
                    _invalid()
                failed_non_run_terminals += 1
            counts[f"{phase}Started"] += 1
            counts[f"{phase}Terminal"] += 1
            if counts[f"{phase}Started"] > 1:
                _invalid()
        cursor += 2

    if model_ordinals != list(range(1, len(model_ordinals) + 1)):
        _invalid()
    counts["modelAnswerStarted"] = len(model_ordinals)
    counts["modelAnswerTerminal"] = len(model_ordinals)
    counts["validAnswers"] = valid_answers
    counts["databaseSelectStarted"] = sum(
        counts[f"{phase}Started"]
        for phase in ("fixture_precheck", "fixture_verify", "cleanup_verify")
    )
    counts["databaseSelectTerminal"] = sum(
        counts[f"{phase}Terminal"]
        for phase in ("fixture_precheck", "fixture_verify", "cleanup_verify")
    )
    counts["databaseInsertStarted"] = counts["fixture_insertStarted"]
    counts["databaseInsertTerminal"] = counts["fixture_insertTerminal"]
    counts["databaseDeleteStarted"] = counts["cleanup_deleteStarted"]
    counts["databaseDeleteTerminal"] = counts["cleanup_deleteTerminal"]
    counts["employeeDetailStarted"] = counts["employee_detailStarted"]
    counts["employeeDetailTerminal"] = counts["employee_detailTerminal"]

    if (
        counts["databaseSelectStarted"] > MAX_DATABASE_SELECTS
        or counts["databaseInsertStarted"] > MAX_DATABASE_INSERTS
        or counts["databaseDeleteStarted"] > MAX_DATABASE_DELETES
        or counts["employeeDetailStarted"] > MAX_EMPLOYEE_DETAILS
        or counts["modelAnswerStarted"] > MAXIMUM_PAID_ANSWER_CALLS
    ):
        _invalid()
    if counts["host_validationStarted"] != 1:
        _invalid()

    consumed = consumed_path.is_file()
    if consumed:
        validate_consumed_marker(
            load_strict_json(consumed_path), manifest_sha256=manifest_sha256
        )
    status = cast(RunStatus, last["state"])
    inserted = counts["fixture_insertStarted"] == 1
    if inserted:
        if status != "failed_cleanup_required" and counts["cleanup_deleteStarted"] != 1:
            _invalid()
        if status == "failed_cleanup_required" and counts["cleanup_deleteStarted"] > 1:
            _invalid()
        if status != "failed_cleanup_required" and counts["cleanup_verifyStarted"] != 1:
            _invalid()
        if counts["cleanup_verifyStarted"] > counts["cleanup_deleteStarted"]:
            _invalid()
    elif counts["cleanup_deleteStarted"] != 0 or counts["cleanup_verifyStarted"] != 0:
        _invalid()
    if status == "passed":
        expected = {
            "databaseSelectStarted": 3,
            "databaseInsertStarted": 1,
            "databaseDeleteStarted": 1,
            "employeeDetailStarted": 1,
            "modelAnswerStarted": MAXIMUM_PAID_ANSWER_CALLS,
        }
        if (
            not consumed
            or len(records) != EXPECTED_PASSED_RECORDS
            or any(counts[key] != value for key, value in expected.items())
            or valid_answers < MINIMUM_VALID_ANSWER_CALLS
            or failed_non_run_terminals != 0
            or last["reason"] != "none"
            or last["failurePhase"] != "none"
        ):
            _invalid()
    elif status == "failed_unconsumed":
        if consumed or last["reason"] == "none" or last["failurePhase"] == "none":
            _invalid()
    elif status == "failed_consumed":
        if not consumed or last["reason"] == "none" or last["failurePhase"] == "none":
            _invalid()
    elif status == "failed_cleanup_required" and last["reason"] != "cleanup_failed":
        _invalid()
    if consumed and counts["modelAnswerStarted"] == 0:
        _invalid()

    return LifecycleSnapshot(
        record_count=len(records),
        status=status,
        failure_phase=cast(str, last["failurePhase"]),
        failure_reason=cast(str, last["reason"]),
        authorization_consumed=consumed,
        valid_answers=valid_answers,
        counts=dict(counts),
    )


def validate_pending(value: object, *, manifest_sha256: str) -> dict[str, Any]:
    if type(value) is not dict:
        _invalid()
    pending = cast(dict[str, Any], value)
    if set(pending) != {
        "schemaVersion",
        "runId",
        "manifestSha256",
        "authorizationReference",
        "failure",
        "counts",
        "safety",
    }:
        _invalid()
    failure = pending["failure"]
    counts = pending["counts"]
    safety = pending["safety"]
    if (
        pending["schemaVersion"] != SCHEMA_VERSION
        or pending["runId"] != RUN_ID
        or pending["manifestSha256"] != manifest_sha256
        or pending["authorizationReference"] != AUTHORIZATION_REFERENCE
        or type(failure) is not dict
        or set(failure) != {"phase", "reason"}
        or failure["phase"] not in _FAILURE_PHASES
        or failure["reason"] not in _FAILURE_REASONS
        or type(counts) is not dict
        or set(counts)
        != {
            "databaseSelectStarted",
            "databaseSelectTerminal",
            "databaseInsertStarted",
            "databaseInsertTerminal",
            "databaseDeleteStarted",
            "databaseDeleteTerminal",
            "preexisting",
            "inserted",
            "verified",
            "deleted",
            "remaining",
            "employeeDetailStarted",
            "employeeDetailTerminal",
            "modelAnswerStarted",
            "modelAnswerTerminal",
            "validAnswers",
        }
        or any(type(item) is not int or item < 0 for item in counts.values())
        or type(safety) is not dict
        or set(safety)
        != {
            "retryCount",
            "resumeCount",
            "otherEndpointCalls",
            "forbiddenPayloadFieldCount",
            "forbiddenLiteralCount",
            "runtimeLogLeakCount",
        }
        or any(type(item) is not int or item < 0 for item in safety.values())
    ):
        _invalid()
    if (
        counts["databaseSelectStarted"] > MAX_DATABASE_SELECTS
        or counts["databaseInsertStarted"] > MAX_DATABASE_INSERTS
        or counts["databaseDeleteStarted"] > MAX_DATABASE_DELETES
        or counts["employeeDetailStarted"] > MAX_EMPLOYEE_DETAILS
        or counts["modelAnswerStarted"] > MAXIMUM_PAID_ANSWER_CALLS
        or counts["databaseSelectTerminal"] > counts["databaseSelectStarted"]
        or counts["databaseInsertTerminal"] > counts["databaseInsertStarted"]
        or counts["databaseDeleteTerminal"] > counts["databaseDeleteStarted"]
        or counts["employeeDetailTerminal"] > counts["employeeDetailStarted"]
        or counts["modelAnswerTerminal"] > counts["modelAnswerStarted"]
        or counts["validAnswers"] > counts["modelAnswerTerminal"]
        or safety["retryCount"] != 0
        or safety["resumeCount"] != 0
        or safety["otherEndpointCalls"] != 0
        or safety["forbiddenPayloadFieldCount"] > 1_000
        or safety["forbiddenLiteralCount"] > 1_000
        or safety["runtimeLogLeakCount"] > 1_000
    ):
        _invalid()
    return pending


def write_fallback_pending(
    *,
    lifecycle_path: Path,
    pending_path: Path,
    manifest_sha256: str,
) -> dict[str, Any]:
    if pending_path.exists():
        _invalid()
    records = _load_records(lifecycle_path, manifest_sha256=manifest_sha256)
    if not records or records[-1]["phase"] == "run" and records[-1]["state"] != "started":
        _invalid()
    journal = LifecycleJournal(lifecycle_path, manifest_sha256=manifest_sha256, create=False)
    if records[-1]["state"] == "started" and records[-1]["phase"] != "run":
        phase = cast(str, records[-1]["phase"])
        ordinal = cast(int | None, records[-1]["ordinal"])
        reason = "model_call_failed" if phase == "model_answer" else "database_operation_failed"
        if phase == "employee_detail":
            reason = "employee_request_failed"
        elif phase.startswith("cleanup_"):
            reason = "cleanup_failed"
        journal.finished(phase, terminal="failed", reason=reason, ordinal=ordinal)
        records = _load_records(lifecycle_path, manifest_sha256=manifest_sha256)

    phase_started = Counter(
        cast(str, record["phase"])
        for record in records
        if record["state"] == "started"
    )
    phase_succeeded = Counter(
        cast(str, record["phase"])
        for record in records
        if record["state"] in {"succeeded", "answer"}
    )
    model_terminals = [
        record
        for record in records
        if record["phase"] == "model_answer" and record["state"] != "started"
    ]
    insert_may_have_occurred = phase_started["fixture_insert"] == 1
    cleanup_proven = phase_succeeded["cleanup_delete"] == 1 and phase_succeeded[
        "cleanup_verify"
    ] == 1
    if insert_may_have_occurred and not cleanup_proven:
        failure_phase = (
            "cleanup_verify" if phase_started["cleanup_delete"] else "cleanup_delete"
        )
        failure_reason = "cleanup_failed"
    else:
        failure_phase = "host_validation"
        failure_reason = "host_failed"
    pending: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "failure": {"phase": failure_phase, "reason": failure_reason},
        "counts": {
            "databaseSelectStarted": sum(
                phase_started[phase]
                for phase in ("fixture_precheck", "fixture_verify", "cleanup_verify")
            ),
            "databaseSelectTerminal": sum(
                phase_started[phase]
                for phase in ("fixture_precheck", "fixture_verify", "cleanup_verify")
            ),
            "databaseInsertStarted": phase_started["fixture_insert"],
            "databaseInsertTerminal": phase_started["fixture_insert"],
            "databaseDeleteStarted": phase_started["cleanup_delete"],
            "databaseDeleteTerminal": phase_started["cleanup_delete"],
            "preexisting": 0,
            "inserted": 1 if insert_may_have_occurred else 0,
            "verified": phase_succeeded["fixture_verify"],
            "deleted": phase_succeeded["cleanup_delete"],
            "remaining": 0 if cleanup_proven else 1,
            "employeeDetailStarted": phase_started["employee_detail"],
            "employeeDetailTerminal": phase_started["employee_detail"],
            "modelAnswerStarted": phase_started["model_answer"],
            "modelAnswerTerminal": len(model_terminals),
            "validAnswers": phase_succeeded["model_answer"],
        },
        "safety": {
            "retryCount": 0,
            "resumeCount": 0,
            "otherEndpointCalls": 0,
            "forbiddenPayloadFieldCount": 0,
            "forbiddenLiteralCount": 0,
            "runtimeLogLeakCount": 0,
        },
    }
    validate_pending(pending, manifest_sha256=manifest_sha256)
    _write_exclusive(pending_path, pending)
    return pending


def finalize_candidate(
    *,
    lifecycle_path: Path,
    consumed_path: Path,
    pending_path: Path,
    result_path: Path,
    manifest_sha256: str,
    failure_phase: str = "none",
    failure_reason: str = "none",
    host_exit_code: int = 0,
    log_leak_count: int = 0,
    raw_logs_deleted: bool = True,
) -> dict[str, Any]:
    if (
        result_path.exists()
        or failure_reason not in _FAILURE_REASONS
        or failure_phase not in _FAILURE_PHASES
        or not pending_path.is_file()
    ):
        _invalid()
    pending = validate_pending(
        load_strict_json(pending_path), manifest_sha256=manifest_sha256
    )
    journal = LifecycleJournal(lifecycle_path, manifest_sha256=manifest_sha256, create=False)
    pending_safety = cast(dict[str, int], pending["safety"])
    effective_log_leak_count = min(
        1_000, log_leak_count + pending_safety["runtimeLogLeakCount"]
    )
    host_failed = host_exit_code != 0 or effective_log_leak_count != 0
    if host_failed and failure_reason == "none":
        failure_phase = "host_validation"
        failure_reason = "log_leak_detected" if effective_log_leak_count else "host_failed"
    journal.pair(
        "host_validation",
        terminal="failed" if host_failed else "succeeded",
        reason=failure_reason if host_failed else "none",
    )
    cleanup_failed = failure_reason == "cleanup_failed"
    if cleanup_failed:
        status: RunStatus = "failed_cleanup_required"
    elif failure_reason == "none":
        status = "passed"
    elif consumed_path.is_file():
        status = "failed_consumed"
    else:
        status = "failed_unconsumed"
    journal.terminal(status, phase=failure_phase, reason=failure_reason)
    snapshot = validate_lifecycle(
        lifecycle_path,
        consumed_path=consumed_path,
        manifest_sha256=manifest_sha256,
    )
    counts = snapshot.counts
    pending_counts = cast(dict[str, int], pending["counts"])
    for key in (
        "databaseSelectStarted",
        "databaseSelectTerminal",
        "databaseInsertStarted",
        "databaseInsertTerminal",
        "databaseDeleteStarted",
        "databaseDeleteTerminal",
        "employeeDetailStarted",
        "employeeDetailTerminal",
        "modelAnswerStarted",
        "modelAnswerTerminal",
        "validAnswers",
    ):
        if pending_counts[key] != counts[key]:
            _invalid()
    if (
        (not host_failed and pending["failure"] != {"phase": failure_phase, "reason": failure_reason})
        or snapshot.failure_phase != failure_phase
        or snapshot.failure_reason != failure_reason
    ):
        _invalid()
    result: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "status": snapshot.status,
        "failure": {"phase": failure_phase, "reason": failure_reason},
        "authorizationConsumed": snapshot.authorization_consumed,
        "counts": {
            "databaseSelectStarted": counts["databaseSelectStarted"],
            "databaseSelectTerminal": counts["databaseSelectTerminal"],
            "databaseInsertStarted": counts["databaseInsertStarted"],
            "databaseInsertTerminal": counts["databaseInsertTerminal"],
            "databaseDeleteStarted": counts["databaseDeleteStarted"],
            "databaseDeleteTerminal": counts["databaseDeleteTerminal"],
            "employeeDetailStarted": counts["employeeDetailStarted"],
            "employeeDetailTerminal": counts["employeeDetailTerminal"],
            "modelAnswerStarted": counts["modelAnswerStarted"],
            "modelAnswerTerminal": counts["modelAnswerTerminal"],
            "validAnswers": snapshot.valid_answers,
            "retryCount": pending_safety["retryCount"],
            "resumeCount": pending_safety["resumeCount"],
            "otherEndpointCalls": pending_safety["otherEndpointCalls"],
            "preexisting": pending_counts["preexisting"],
            "inserted": pending_counts["inserted"],
            "verified": pending_counts["verified"],
        },
        "cleanup": {
            "deleted": pending_counts["deleted"],
            "remaining": pending_counts["remaining"],
        },
        "safety": {
            "forbiddenPayloadFieldCount": pending_safety[
                "forbiddenPayloadFieldCount"
            ],
            "forbiddenLiteralCount": pending_safety["forbiddenLiteralCount"],
            "logLeakCount": effective_log_leak_count,
            "rawLogsDeleted": raw_logs_deleted,
        },
        "lifecycle": {
            "recordCount": snapshot.record_count,
            "sha256": sha256_file(lifecycle_path),
        },
        "consumedMarkerSha256": (
            sha256_file(consumed_path) if consumed_path.is_file() else None
        ),
    }
    validate_result(result)
    _write_exclusive(result_path, result)
    return result


def validate_result(value: object) -> dict[str, Any]:
    if type(value) is not dict:
        _invalid()
    result = cast(dict[str, Any], value)
    expected_keys = {
        "schemaVersion",
        "runId",
        "manifestSha256",
        "authorizationReference",
        "status",
        "failure",
        "authorizationConsumed",
        "counts",
        "cleanup",
        "safety",
        "lifecycle",
        "consumedMarkerSha256",
    }
    if set(result) != expected_keys:
        _invalid()
    if (
        result["schemaVersion"] != SCHEMA_VERSION
        or result["runId"] != RUN_ID
        or not _is_sha256(result["manifestSha256"])
        or result["authorizationReference"] != AUTHORIZATION_REFERENCE
        or result["status"]
        not in {"passed", "failed_unconsumed", "failed_consumed", "failed_cleanup_required"}
        or type(result["authorizationConsumed"]) is not bool
    ):
        _invalid()
    failure = result["failure"]
    counts = result["counts"]
    cleanup = result["cleanup"]
    safety = result["safety"]
    lifecycle = result["lifecycle"]
    if (
        type(failure) is not dict
        or set(failure) != {"phase", "reason"}
        or failure["reason"] not in _FAILURE_REASONS
        or type(failure["phase"]) is not str
        or type(counts) is not dict
        or set(counts)
        != {
            "databaseSelectStarted",
            "databaseSelectTerminal",
            "databaseInsertStarted",
            "databaseInsertTerminal",
            "databaseDeleteStarted",
            "databaseDeleteTerminal",
            "employeeDetailStarted",
            "employeeDetailTerminal",
            "modelAnswerStarted",
            "modelAnswerTerminal",
            "validAnswers",
            "retryCount",
            "resumeCount",
            "otherEndpointCalls",
            "preexisting",
            "inserted",
            "verified",
        }
        or any(type(item) is not int or item < 0 for item in counts.values())
        or type(cleanup) is not dict
        or set(cleanup) != {"deleted", "remaining"}
        or type(cleanup["deleted"]) is not int
        or cleanup["deleted"] not in {0, 1}
        or type(cleanup["remaining"]) is not int
        or cleanup["remaining"] not in {0, 1}
        or type(safety) is not dict
        or set(safety)
        != {
            "forbiddenPayloadFieldCount",
            "forbiddenLiteralCount",
            "logLeakCount",
            "rawLogsDeleted",
        }
        or type(lifecycle) is not dict
        or set(lifecycle) != {"recordCount", "sha256"}
        or type(lifecycle["recordCount"]) is not int
        or not _is_sha256(lifecycle["sha256"])
    ):
        _invalid()
    if result["status"] == "passed" and (
        failure != {"phase": "none", "reason": "none"}
        or result["authorizationConsumed"] is not True
        or not _is_sha256(result["consumedMarkerSha256"])
        or counts["databaseSelectStarted"] != MAX_DATABASE_SELECTS
        or counts["databaseInsertStarted"] != MAX_DATABASE_INSERTS
        or counts["databaseDeleteStarted"] != MAX_DATABASE_DELETES
        or counts["employeeDetailStarted"] != MAX_EMPLOYEE_DETAILS
        or counts["modelAnswerStarted"] != MAXIMUM_PAID_ANSWER_CALLS
        or counts["modelAnswerTerminal"] != MAXIMUM_PAID_ANSWER_CALLS
        or counts["validAnswers"] < MINIMUM_VALID_ANSWER_CALLS
        or counts["preexisting"] != 0
        or counts["inserted"] != 1
        or counts["verified"] != 1
        or cleanup != {"deleted": 1, "remaining": 0}
        or any(
            safety[key] != 0
            for key in ("forbiddenPayloadFieldCount", "forbiddenLiteralCount", "logLeakCount")
        )
        or safety["rawLogsDeleted"] is not True
        or lifecycle["recordCount"] != EXPECTED_PASSED_RECORDS
    ):
        _invalid()
    return result


def execute_fake_candidate(
    directory: Path,
    *,
    manifest_sha256: str,
    fault: FaultPhase = "none",
) -> dict[str, Any]:
    lifecycle_path = directory / f"{RUN_ID}.lifecycle.jsonl"
    consumed_path = directory / f"{RUN_ID}.authorization.consumed.json"
    result_path = directory / f"{RUN_ID}.result.json"
    pending_path = directory / f"{RUN_ID}.pending.json"
    journal = LifecycleJournal(lifecycle_path, manifest_sha256=manifest_sha256)
    inserted = False
    failure_phase = "none"
    failure_reason = "none"

    def stage(phase: str, failure: str) -> bool:
        nonlocal failure_phase, failure_reason
        if fault == phase:
            journal.pair(phase, terminal="failed", reason=failure)
            failure_phase, failure_reason = phase, failure
            return False
        journal.pair(phase)
        return True

    if stage("fixture_precheck", "database_operation_failed"):
        inserted = True
        if stage("fixture_insert", "database_operation_failed") and stage(
            "fixture_verify", "database_operation_failed"
        ):
            if stage("employee_detail", "employee_request_failed"):
                if fault in {"model_setup", "forbidden_payload"}:
                    failure_phase = "model_setup"
                    failure_reason = (
                        "egress_projection_invalid"
                        if fault == "forbidden_payload"
                        else "model_setup_failed"
                    )
                else:
                    write_consumed_marker(consumed_path, manifest_sha256=manifest_sha256)
                    outcomes: Sequence[ModelTerminal]
                    if fault == "threshold":
                        outcomes = cast(
                            Sequence[ModelTerminal],
                            (*(["answer"] * 26), *(["invalid_output"] * 4)),
                        )
                    else:
                        outcomes = cast(
                            Sequence[ModelTerminal],
                            ["answer"] * MAXIMUM_PAID_ANSWER_CALLS,
                        )
                    for ordinal, outcome in enumerate(outcomes, start=1):
                        if fault == "model_answer" and ordinal == 1:
                            journal.pair(
                                "model_answer",
                                terminal="provider_failure",
                                reason="model_call_failed",
                                ordinal=ordinal,
                            )
                            failure_phase, failure_reason = "model_answer", "model_call_failed"
                            break
                        journal.pair(
                            "model_answer", terminal=outcome, reason="none", ordinal=ordinal
                        )
                    if fault == "threshold":
                        failure_phase, failure_reason = "threshold", "threshold_not_met"

    if inserted:
        cleanup_ok = stage("cleanup_delete", "cleanup_failed")
        if cleanup_ok:
            cleanup_ok = stage("cleanup_verify", "cleanup_failed")
        if not cleanup_ok:
            failure_reason = "cleanup_failed"

    host_exit_code = 1 if fault == "host_validation" else 0
    if fault == "host_validation":
        failure_phase, failure_reason = "host_validation", "host_failed"
    records = _load_records(lifecycle_path, manifest_sha256=manifest_sha256)
    phase_counts = Counter(
        cast(str, record["phase"])
        for record in records
        if record["state"] == "started"
    )
    model_terminals = [
        record
        for record in records
        if record["phase"] == "model_answer" and record["state"] != "started"
    ]
    valid_answers = sum(record["state"] == "answer" for record in model_terminals)
    pending: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "failure": {"phase": failure_phase, "reason": failure_reason},
        "counts": {
            "databaseSelectStarted": sum(
                phase_counts[phase]
                for phase in ("fixture_precheck", "fixture_verify", "cleanup_verify")
            ),
            "databaseSelectTerminal": sum(
                phase_counts[phase]
                for phase in ("fixture_precheck", "fixture_verify", "cleanup_verify")
            ),
            "databaseInsertStarted": phase_counts["fixture_insert"],
            "databaseInsertTerminal": phase_counts["fixture_insert"],
            "databaseDeleteStarted": phase_counts["cleanup_delete"],
            "databaseDeleteTerminal": phase_counts["cleanup_delete"],
            "preexisting": 0,
            "inserted": 1 if phase_counts["fixture_insert"] else 0,
            "verified": 1 if phase_counts["fixture_verify"] else 0,
            "deleted": 1 if phase_counts["cleanup_delete"] and fault != "cleanup_delete" else 0,
            "remaining": 0 if phase_counts["cleanup_verify"] and fault != "cleanup_verify" else 1,
            "employeeDetailStarted": phase_counts["employee_detail"],
            "employeeDetailTerminal": phase_counts["employee_detail"],
            "modelAnswerStarted": phase_counts["model_answer"],
            "modelAnswerTerminal": len(model_terminals),
            "validAnswers": valid_answers,
        },
        "safety": {
            "retryCount": 0,
            "resumeCount": 0,
            "otherEndpointCalls": 0,
            "forbiddenPayloadFieldCount": 1 if fault == "forbidden_payload" else 0,
            "forbiddenLiteralCount": 0,
            "runtimeLogLeakCount": 0,
        },
    }
    _write_exclusive(pending_path, pending)
    return finalize_candidate(
        lifecycle_path=lifecycle_path,
        consumed_path=consumed_path,
        pending_path=pending_path,
        result_path=result_path,
        manifest_sha256=manifest_sha256,
        failure_phase=failure_phase,
        failure_reason=failure_reason,
        host_exit_code=host_exit_code,
        raw_logs_deleted=True,
    )


def verify_history(repository_root: Path) -> None:
    for _name, relative_path, expected_hash in HISTORY_ASSETS:
        path = repository_root / relative_path
        if not path.is_file() or sha256_file(path) != expected_hash:
            _invalid()


def validate_manifest(value: object, *, repository_root: Path) -> dict[str, Any]:
    if type(value) is not dict:
        _invalid()
    manifest = cast(dict[str, Any], value)
    if set(manifest) != {
        "schemaVersion",
        "status",
        "runId",
        "preparationWorkPackageId",
        "workPackageId",
        "preparationGateId",
        "gateId",
        "authorizationReference",
        "executionBoundary",
        "fieldBoundary",
        "historyHashes",
        "assetHashes",
    }:
        _invalid()
    boundary = manifest["executionBoundary"]
    fields = manifest["fieldBoundary"]
    if (
        manifest["schemaVersion"] != SCHEMA_VERSION
        or manifest["status"] != "prepared_unconsumed"
        or manifest["runId"] != RUN_ID
        or manifest["preparationWorkPackageId"] != PREPARATION_WORK_PACKAGE_ID
        or manifest["workPackageId"] != WORK_PACKAGE_ID
        or manifest["preparationGateId"] != PREPARATION_GATE_ID
        or manifest["gateId"] != GATE_ID
        or manifest["authorizationReference"] != AUTHORIZATION_REFERENCE
        or type(boundary) is not dict
        or boundary
        != {
            "databaseSelects": 3,
            "databaseInserts": 1,
            "databaseDeletes": 1,
            "employeeDetailRequests": 1,
            "plannedAnswerCalls": 30,
            "maximumPaidAnswerCalls": 30,
            "minimumValidAnswers": 27,
            "retryAllowed": False,
            "resumeAllowed": False,
        }
        or fields != {"modelVisibleFieldIds": list(MODEL_VISIBLE_FIELD_IDS)}
    ):
        _invalid()
    _validate_hash_entries(
        manifest["historyHashes"],
        repository_root=repository_root,
        expected_paths={relative for _, relative, _ in HISTORY_ASSETS},
    )
    assets = manifest["assetHashes"]
    if not isinstance(assets, list) or len(assets) != len(REQUIRED_ASSET_PATHS):
        _invalid()
    _validate_hash_entries(assets, repository_root=repository_root)
    if {cast(str, item["path"]) for item in assets} != REQUIRED_ASSET_PATHS:
        _invalid()
    verify_history(repository_root)
    return manifest


def _validate_hash_entries(
    value: object,
    *,
    repository_root: Path,
    expected_paths: set[str] | None = None,
) -> None:
    if not isinstance(value, list):
        _invalid()
    seen: set[str] = set()
    root = repository_root.resolve()
    for item in value:
        if type(item) is not dict or set(item) != {"path", "sha256"}:
            _invalid()
        relative = item["path"]
        expected_hash = item["sha256"]
        if not isinstance(relative, str) or relative in seen or not _is_sha256(expected_hash):
            _invalid()
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            _invalid()
        if not path.is_file() or sha256_file(path) != expected_hash:
            _invalid()
        seen.add(relative)
    if expected_paths is not None and seen != expected_paths:
        _invalid()


def validate_authorization(value: object, *, manifest_sha256: str) -> dict[str, Any]:
    if type(value) is not dict:
        _invalid()
    authorization = cast(dict[str, Any], value)
    if set(authorization) != {
        "schemaVersion",
        "status",
        "runId",
        "preparationWorkPackageId",
        "workPackageId",
        "preparationGateId",
        "gateId",
        "manifestSha256",
        "authorizationReference",
        "singleUse",
        "liveExecutionAuthorized",
        "maximumPaidAnswerCalls",
        "retryAllowed",
        "resumeAllowed",
    }:
        _invalid()
    if authorization != {
        "schemaVersion": SCHEMA_VERSION,
        "status": "prepared_unconsumed",
        "runId": RUN_ID,
        "preparationWorkPackageId": PREPARATION_WORK_PACKAGE_ID,
        "workPackageId": WORK_PACKAGE_ID,
        "preparationGateId": PREPARATION_GATE_ID,
        "gateId": GATE_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "singleUse": True,
        "liveExecutionAuthorized": False,
        "maximumPaidAnswerCalls": MAXIMUM_PAID_ANSWER_CALLS,
        "retryAllowed": False,
        "resumeAllowed": False,
    }:
        _invalid()
    return authorization
