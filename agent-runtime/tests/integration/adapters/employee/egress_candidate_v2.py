from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Final, Literal, NoReturn

import httpx

from agent_runtime.adapters.employee.definition import employee_detail_definition
from agent_runtime.adapters.employee.settings import EmployeeAdapterSettings
from agent_runtime.business.http_client import FakeDomainHttpRequest, FakeDomainHttpResponse
from agent_runtime.business.settings import (
    BusinessConfigurationSource,
    BusinessConfigurationSnapshot,
    BusinessGlobalSettings,
    BusinessServiceBinding,
    BusinessSettingsValidator,
)
from agent_runtime.model.contracts import (
    ModelTaskId,
    StructuredModelRequest,
    StructuredModelResponse,
    StructuredModelTransport,
    StructuredOutputMode,
    StructuredToolMode,
)


RUN_ID: Final = "employee-egress-v2-20260814-candidate-02"
PREPARATION_WORK_PACKAGE_ID: Final = "WP-EMP-EGRESS-CANDIDATE-02-PREP"
WORK_PACKAGE_ID: Final = "WP-EMP-EGRESS-01"
PREPARATION_GATE_ID: Final = "GATE-048"
GATE_ID: Final = "GATE-024"
AUTHORIZATION_REFERENCE: Final = "P3_00:GATE-024"
MAXIMUM_PAID_ANSWER_CALLS: Final = 30
MINIMUM_VALID_ANSWER_CALLS: Final = 27
MODEL_VISIBLE_FIELD_IDS: Final = ("position", "work_base_si")
MODEL_TASK_BINDING: Final = {
    "taskId": "answer_generation",
    "taskVersion": "answer-generation-v1",
    "modelName": "deepseek-v4-pro",
}
AUTHORIZATION_EVIDENCE_REFS: Final = (
    "WP-EMP-REAL-01:authorizationMatrix.admin",
    "WP-EMP-REAL-01:VAL-EMP-005",
)
AUTHORIZATION_EVIDENCE_ASSETS: Final = (
    (
        "WP-EMP-REAL-01:authorizationMatrix.admin",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "wp-emp-real-01-20260806T075036Z.json",
        "f5af997fd9b7b8cce6a6b99fcd6c00dddc43ff105ab2c69c085801d7d2ff382c",
    ),
    (
        "WP-EMP-REAL-01:VAL-EMP-005",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "wp-emp-gateway-log-20260806T091456Z.json",
        "eb9342b550f2bc2a3a391563e24045baccfade687790ab2e5dbe396d3a92396e",
    ),
)
CANDIDATE_01_HISTORY_SHA256: Final = {
    "manifest": "c3cdfacd32797474f68e11758ec094df97a95d56fb0efed9355ccfaa6a145c57",
    "authorization": "52b9075117f3e5f3ea84f1ea3c5da846c7b168f013fc4d8523d7ed52979f416c",
    "environment_diagnostic": "2bc16cf63f3775d778925a5a5a66cfbae5138401e2f209e8288f4db076598a2c",
    "pre_model_failure": "1a55b324fc912ee4e9133c2946183473347eb8e7f3337f8e33286bdf96f0b76f",
}
CANDIDATE_01_HISTORY_PATHS: Final = {
    "manifest": (
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-v1-20260813-candidate-01.manifest.json"
    ),
    "authorization": (
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-v1-20260813-candidate-01.authorization.json"
    ),
    "environment_diagnostic": (
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "wp-emp-egress-env-diag-01-20260814T004517Z.json"
    ),
    "pre_model_failure": (
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-v1-20260813-candidate-01.pre-model-failure-20260814T005222Z.json"
    ),
}
REQUIRED_ASSET_PATHS: Final = frozenset(
    {
        "agent-runtime/scripts/run-employee-egress-live-candidate-02.ps1",
        "agent-runtime/src/agent_runtime/bootstrap.py",
        "agent-runtime/src/agent_runtime/business/egress.py",
        "agent-runtime/src/agent_runtime/business/grounding.py",
        "agent-runtime/src/agent_runtime/business/handler.py",
        "agent-runtime/src/agent_runtime/business/settings.py",
        "agent-runtime/src/agent_runtime/graph/nodes.py",
        "agent-runtime/src/agent_runtime/model/deepseek/answer_generator.py",
        "agent-runtime/src/agent_runtime/model/input_guard.py",
        "agent-runtime/src/agent_runtime/model/question_policy.py",
        "agent-runtime/src/agent_runtime/adapters/employee/definition.py",
        "agent-runtime/src/agent_runtime/adapters/employee/fields.py",
        "agent-runtime/src/agent_runtime/adapters/employee/settings.py",
        "agent-runtime/src/agent_runtime/adapters/employee/codec.py",
        "agent-runtime/src/agent_runtime/adapters/employee/normalizer.py",
        "agent-runtime/tests/fixtures/employee_egress_field_matrix.json",
        "agent-runtime/tests/unit/adapters/employee/test_egress.py",
        "agent-runtime/tests/integration/adapters/employee/test_sensitive_egress_zero_call.py",
        "agent-runtime/tests/integration/business/test_business_text_is_data.py",
        "agent-runtime/tests/integration/adapters/employee/egress_candidate_v2.py",
        "agent-runtime/tests/integration/adapters/employee/test_real_employee_egress_candidate_v2.py",
        "agent-runtime/tests/integration/adapters/employee/"
        "test_employee_egress_candidate_v2_harness.py",
        "agent-runtime/tests/integration/adapters/employee/"
        "test_employee_egress_candidate_01_history.py",
        "agent-runtime/tests/integration/adapters/employee/evidence/"
        "employee-egress-live-evidence-v2.schema.json",
    }
)
_SAFE_QUESTION: Final = "查询单个员工详情"
_TERMINAL_MODEL_STATUSES: Final = frozenset(
    {"answer", "invalid_output", "input_denied", "timeout", "provider_failure"}
)
class EmployeeEgressCandidateV2Error(ValueError):
    pass


class EmployeeEgressEvidenceWriteV2Error(RuntimeError):
    pass


class EmployeeEgressFailurePhase(str, Enum):
    EMPLOYEE_REQUEST = "employee_request"
    EMPLOYEE_RESULT = "employee_result"
    EGRESS_PROJECTION = "egress_projection"
    MODEL_SETUP = "model_setup"
    MODEL_CALL = "model_call"
    THRESHOLD = "threshold"
    CLEANUP = "cleanup"
    INTERNAL = "internal"


class EmployeeEgressFailureReason(str, Enum):
    EMPLOYEE_REQUEST_FAILED = "employee_request_failed"
    EMPLOYEE_RESULT_INVALID = "employee_result_invalid"
    EGRESS_PROJECTION_INVALID = "egress_projection_invalid"
    MODEL_SETUP_FAILED = "model_setup_failed"
    MODEL_REQUEST_INVALID = "model_request_invalid"
    MODEL_CALL_FAILED = "model_call_failed"
    THRESHOLD_NOT_MET = "threshold_not_met"
    CLEANUP_FAILED = "cleanup_failed"
    LOG_LEAK_DETECTED = "log_leak_detected"
    EVIDENCE_WRITE_FAILED = "evidence_write_failed"
    INTERNAL_FAILURE = "internal_failure"


_FAILURE_REASONS_BY_PHASE: Final = {
    EmployeeEgressFailurePhase.EMPLOYEE_REQUEST: frozenset(
        {EmployeeEgressFailureReason.EMPLOYEE_REQUEST_FAILED}
    ),
    EmployeeEgressFailurePhase.EMPLOYEE_RESULT: frozenset(
        {EmployeeEgressFailureReason.EMPLOYEE_RESULT_INVALID}
    ),
    EmployeeEgressFailurePhase.EGRESS_PROJECTION: frozenset(
        {EmployeeEgressFailureReason.EGRESS_PROJECTION_INVALID}
    ),
    EmployeeEgressFailurePhase.MODEL_SETUP: frozenset(
        {EmployeeEgressFailureReason.MODEL_SETUP_FAILED}
    ),
    EmployeeEgressFailurePhase.MODEL_CALL: frozenset(
        {
            EmployeeEgressFailureReason.MODEL_REQUEST_INVALID,
            EmployeeEgressFailureReason.MODEL_CALL_FAILED,
        }
    ),
    EmployeeEgressFailurePhase.THRESHOLD: frozenset(
        {EmployeeEgressFailureReason.THRESHOLD_NOT_MET}
    ),
    EmployeeEgressFailurePhase.CLEANUP: frozenset(
        {
            EmployeeEgressFailureReason.CLEANUP_FAILED,
            EmployeeEgressFailureReason.LOG_LEAK_DETECTED,
        }
    ),
    EmployeeEgressFailurePhase.INTERNAL: frozenset(
        {
            EmployeeEgressFailureReason.EVIDENCE_WRITE_FAILED,
            EmployeeEgressFailureReason.INTERNAL_FAILURE,
        }
    ),
}


RunTerminalStatus = Literal["passed", "failed_unconsumed", "failed_consumed"]
EmployeeTerminalStatus = Literal["completed", "failed"]
ModelTerminalStatus = Literal[
    "answer", "invalid_output", "input_denied", "timeout", "provider_failure"
]


@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeEgressLifecycleSnapshotV2:
    record_count: int
    employee_detail_requests: int
    employee_detail_terminal: EmployeeTerminalStatus | None
    model_outbound_calls: int
    model_terminal_records: int
    model_outcomes: tuple[ModelTerminalStatus, ...]
    valid_answers: int
    authorization_consumed: bool
    run_status: RunTerminalStatus
    failure_phase: EmployeeEgressFailurePhase | None
    failure_reason: EmployeeEgressFailureReason | None


@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeEgressSafetySnapshotV2:
    forbidden_payload_field_count: int = 0
    forbidden_literal_count: int = 0
    log_leak_count: int = 0

    def __post_init__(self) -> None:
        for value in (
            self.forbidden_payload_field_count,
            self.forbidden_literal_count,
            self.log_leak_count,
        ):
            if type(value) is not int or value < 0 or value > 1_000:
                _invalid()


def _invalid() -> NoReturn:
    raise EmployeeEgressCandidateV2Error("employee.egress_candidate_v2_invalid")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _invalid()
        result[key] = value
    return result


def load_strict_json(path: Path, *, max_bytes: int = 262_144) -> dict[str, Any]:
    raw = path.read_bytes()
    if not raw or len(raw) > max_bytes or raw.startswith(b"\xef\xbb\xbf"):
        _invalid()
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError):
        _invalid()
    if type(value) is not dict:
        _invalid()
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repository_file(repository_root: Path, relative: str) -> Path:
    root = repository_root.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        _invalid()
    if not path.is_file():
        _invalid()
    return path


def write_exclusive_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def build_employee_egress_snapshot() -> BusinessConfigurationSnapshot:
    definition = employee_detail_definition()
    action = EmployeeAdapterSettings.from_env(
        {
            "AGENT_EMPLOYEE_DETAIL_ENABLED": "true",
            "AGENT_EMPLOYEE_DETAIL_MODEL_FIELDS": ",".join(MODEL_VISIBLE_FIELD_IDS),
        }
    ).action
    return BusinessSettingsValidator().validate(
        (definition,),
        BusinessConfigurationSource(
            global_settings=BusinessGlobalSettings(egress_enabled=True),
            actions=((definition.descriptor.capability_id, action),),
            service_bindings=(
                BusinessServiceBinding(
                    service_key=definition.service_key,
                    base_endpoint="http://127.0.0.1:9210",
                ),
            ),
        ),
        core_max_domain_result_bytes=262_144,
    )


def lifecycle_path_for(directory: Path) -> Path:
    return directory / f"{RUN_ID}.lifecycle.jsonl"


def consumed_path_for(directory: Path) -> Path:
    return directory / f"{RUN_ID}.authorization.consumed.json"


def evidence_path_for(directory: Path) -> Path:
    return directory / f"{RUN_ID}.result.json"


def _common_record(*, manifest_sha256: str) -> dict[str, object]:
    return {
        "schemaVersion": 2,
        "workPackageId": WORK_PACKAGE_ID,
        "gateId": GATE_ID,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
    }


class EmployeeEgressLifecycleJournalV2:
    def __init__(self, path: Path, *, run_id: str, manifest_sha256: str) -> None:
        if run_id != RUN_ID or not _is_sha256(manifest_sha256):
            _invalid()
        self._path = path
        self._manifest_sha256 = manifest_sha256
        self._consumed_path = consumed_path_for(path.parent)
        self._employee_started = False
        self._employee_terminal: EmployeeTerminalStatus | None = None
        self._model_started = 0
        self._model_terminal = 0
        self._model_outcomes: list[ModelTerminalStatus] = []
        self._run_terminal = False
        write_exclusive_json(
            path,
            {
                **_common_record(manifest_sha256=manifest_sha256),
                "event": "run_started",
                "maximumPaidAnswerCalls": MAXIMUM_PAID_ANSWER_CALLS,
                "retryAllowed": False,
                "resumeAllowed": False,
            },
        )

    @property
    def path(self) -> Path:
        return self._path

    @property
    def consumed_marker_path(self) -> Path:
        return self._consumed_path

    @property
    def manifest_sha256(self) -> str:
        return self._manifest_sha256

    def record_employee_detail_started(self) -> None:
        if self._employee_started or self._run_terminal:
            _invalid()
        self._append({"event": "employee_detail_started", "requestOrdinal": 1})
        self._employee_started = True

    def record_employee_detail_terminal(self, *, status: EmployeeTerminalStatus) -> None:
        if (
            not self._employee_started
            or self._employee_terminal is not None
            or self._run_terminal
            or status not in {"completed", "failed"}
        ):
            _invalid()
        self._append(
            {
                "event": "employee_detail_terminal",
                "requestOrdinal": 1,
                "status": status,
            }
        )
        self._employee_terminal = status

    def record_model_outbound_started(self, *, ordinal: int) -> None:
        if (
            self._run_terminal
            or self._employee_terminal != "completed"
            or ordinal != self._model_started + 1
            or ordinal != self._model_terminal + 1
            or ordinal > MAXIMUM_PAID_ANSWER_CALLS
        ):
            _invalid()
        validate_consumed_marker(
            load_strict_json(self._consumed_path),
            manifest_sha256=self._manifest_sha256,
        )
        self._append({"event": "model_outbound_started", "attemptOrdinal": ordinal})
        self._model_started = ordinal

    def record_model_terminal(self, *, ordinal: int, status: ModelTerminalStatus) -> None:
        if (
            self._run_terminal
            or ordinal != self._model_started
            or ordinal != self._model_terminal + 1
            or status not in _TERMINAL_MODEL_STATUSES
        ):
            _invalid()
        self._append(
            {
                "event": "model_call_terminal",
                "attemptOrdinal": ordinal,
                "status": status,
            }
        )
        self._model_terminal = ordinal
        self._model_outcomes.append(status)

    def record_run_terminal(
        self,
        *,
        status: RunTerminalStatus,
        failure_phase: EmployeeEgressFailurePhase | None,
        failure_reason: EmployeeEgressFailureReason | None,
    ) -> None:
        consumed = self._consumed_path.is_file()
        if consumed:
            validate_consumed_marker(
                load_strict_json(self._consumed_path),
                manifest_sha256=self._manifest_sha256,
            )
        if self._run_terminal:
            _invalid()
        if status == "passed":
            if (
                not consumed
                or failure_phase is not None
                or failure_reason is not None
                or self._employee_terminal != "completed"
                or self._model_started != MAXIMUM_PAID_ANSWER_CALLS
                or self._model_terminal != MAXIMUM_PAID_ANSWER_CALLS
                or Counter(self._model_outcomes)["answer"] < MINIMUM_VALID_ANSWER_CALLS
            ):
                _invalid()
        elif status == "failed_unconsumed":
            if (
                consumed
                or failure_phase is None
                or failure_reason is None
                or failure_reason not in _FAILURE_REASONS_BY_PHASE[failure_phase]
            ):
                _invalid()
        elif status == "failed_consumed":
            if (
                not consumed
                or failure_phase is None
                or failure_reason is None
                or failure_reason not in _FAILURE_REASONS_BY_PHASE[failure_phase]
            ):
                _invalid()
        else:
            _invalid()
        self._append(
            {
                "event": "run_terminal",
                "status": status,
                "failurePhase": None if failure_phase is None else failure_phase.value,
                "failureReason": None if failure_reason is None else failure_reason.value,
            }
        )
        self._run_terminal = True

    def _append(self, value: Mapping[str, object]) -> None:
        record = {**_common_record(manifest_sha256=self._manifest_sha256), **value}
        with self._path.open("a", encoding="utf-8", newline="\n") as stream:
            json.dump(record, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())


class LiveEmployeeTransportV2:
    def __init__(self, client: httpx.AsyncClient, journal: EmployeeEgressLifecycleJournalV2) -> None:
        self._client = client
        self._journal = journal
        self.calls = 0

    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        if self.calls:
            raise RuntimeError("employee.egress_candidate_v2_employee_budget_exhausted")
        self._journal.record_employee_detail_started()
        self.calls = 1
        try:
            response = await self._client.get(
                request.request.relative_path,
                headers={"Authorization": request.authorization, "Accept-Encoding": "identity"},
            )
            content_type = response.headers.get("Content-Type")
            result = FakeDomainHttpResponse(
                status_code=response.status_code,
                content_type=None
                if content_type is None
                else content_type.split(";", 1)[0].strip().lower(),
                body=response.content,
            )
        except BaseException:
            self._journal.record_employee_detail_terminal(status="failed")
            raise
        self._journal.record_employee_detail_terminal(status="completed")
        return result

    async def aclose(self) -> None:
        await self._client.aclose()


class BudgetedEmployeeAnswerTransportV2:
    def __init__(
        self,
        *,
        delegate: StructuredModelTransport,
        journal: EmployeeEgressLifecycleJournalV2,
        forbidden_literals: Sequence[str] = (),
    ) -> None:
        self._delegate = delegate
        self._journal = journal
        self._forbidden_literals = tuple(value for value in forbidden_literals if value)
        self.calls = 0
        self.terminal_calls = 0
        self.retry_count = 0
        self.forbidden_payload_field_count = 0
        self.forbidden_literal_count = 0
        self.requests: list[StructuredModelRequest] = []

    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        if self.calls >= MAXIMUM_PAID_ANSWER_CALLS:
            raise RuntimeError("employee.egress_candidate_v2_budget_exhausted")
        self._validate_request(request)
        ordinal = self.calls + 1
        if ordinal == 1:
            write_consumed_marker(
                self._journal.consumed_marker_path,
                manifest_sha256=self._journal.manifest_sha256,
            )
        self._journal.record_model_outbound_started(ordinal=ordinal)
        self.calls = ordinal
        self.requests.append(request)
        return await self._delegate.complete(request, call_deadline=call_deadline)

    def record_terminal(self, status: ModelTerminalStatus) -> None:
        ordinal = self.terminal_calls + 1
        if ordinal > self.calls:
            _invalid()
        self._journal.record_model_terminal(ordinal=ordinal, status=status)
        self.terminal_calls = ordinal

    def _validate_request(self, request: StructuredModelRequest) -> None:
        if (
            request.task_id is not ModelTaskId.ANSWER_GENERATION
            or request.task_version != "answer-generation-v1"
            or request.tools
            or request.tool_mode is not StructuredToolMode.NONE
            or request.output_mode is not StructuredOutputMode.JSON_OBJECT
        ):
            raise RuntimeError("employee.egress_candidate_v2_request_invalid")
        try:
            payload = json.loads(request.user_payload_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("employee.egress_candidate_v2_request_invalid") from exc
        if type(payload) is not dict or set(payload) != {"question", "safe_payload"}:
            raise RuntimeError("employee.egress_candidate_v2_request_invalid")
        if payload["question"] != _SAFE_QUESTION:
            raise RuntimeError("employee.egress_candidate_v2_question_invalid")
        safe_payload = payload["safe_payload"]
        if type(safe_payload) is not dict:
            raise RuntimeError("employee.egress_candidate_v2_request_invalid")
        facts = safe_payload.get("facts")
        if type(facts) is not list or len(facts) != len(MODEL_VISIBLE_FIELD_IDS):
            raise RuntimeError("employee.egress_candidate_v2_field_boundary_invalid")
        field_ids: list[str] = []
        for fact in facts:
            if type(fact) is not dict:
                raise RuntimeError("employee.egress_candidate_v2_field_boundary_invalid")
            source = fact.get("source")
            if type(source) is not dict or type(source.get("field_id")) is not str:
                raise RuntimeError("employee.egress_candidate_v2_field_boundary_invalid")
            field_ids.append(source["field_id"])
        if tuple(field_ids) != MODEL_VISIBLE_FIELD_IDS:
            raise RuntimeError("employee.egress_candidate_v2_field_boundary_invalid")
        forbidden_keys = {
            "employee_id_masked",
            "member_no_masked",
            "chinese_name",
            "public_email",
            "financial_account",
            "credential",
            "jwt",
            "user_token",
            "idCardNo",
            "memberNo",
            "chineseName",
            "publicEmail",
        }
        self.forbidden_payload_field_count += _count_keys(payload, forbidden_keys)
        raw = request.user_payload_json
        self.forbidden_literal_count += sum(value in raw for value in self._forbidden_literals)
        if self.forbidden_payload_field_count or self.forbidden_literal_count:
            raise RuntimeError("employee.egress_candidate_v2_payload_forbidden")


def _count_keys(value: object, forbidden: frozenset[str] | set[str]) -> int:
    if isinstance(value, dict):
        return sum(key in forbidden for key in value) + sum(
            _count_keys(item, forbidden) for item in value.values()
        )
    if isinstance(value, list):
        return sum(_count_keys(item, forbidden) for item in value)
    return 0


def count_forbidden_log_literals(text: str, literals: Sequence[str]) -> int:
    unique_literals = frozenset(literal for literal in literals if literal)
    return min(1_000, sum(text.count(literal) for literal in unique_literals))


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def write_consumed_marker(path: Path, *, manifest_sha256: str) -> None:
    if not _is_sha256(manifest_sha256):
        _invalid()
    write_exclusive_json(
        path,
        {
            "schemaVersion": 2,
            "status": "consumed",
            "workPackageId": WORK_PACKAGE_ID,
            "gateId": GATE_ID,
            "runId": RUN_ID,
            "manifestSha256": manifest_sha256,
            "authorizationReference": AUTHORIZATION_REFERENCE,
            "consumedAt": datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "maximumPaidAnswerCalls": MAXIMUM_PAID_ANSWER_CALLS,
            "retryAllowed": False,
            "resumeAllowed": False,
        },
    )


def validate_consumed_marker(value: object, *, manifest_sha256: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != {
        "schemaVersion",
        "status",
        "workPackageId",
        "gateId",
        "runId",
        "manifestSha256",
        "authorizationReference",
        "consumedAt",
        "maximumPaidAnswerCalls",
        "retryAllowed",
        "resumeAllowed",
    }:
        _invalid()
    if (
        value["schemaVersion"] != 2
        or value["status"] != "consumed"
        or value["workPackageId"] != WORK_PACKAGE_ID
        or value["gateId"] != GATE_ID
        or value["runId"] != RUN_ID
        or value["manifestSha256"] != manifest_sha256
        or value["authorizationReference"] != AUTHORIZATION_REFERENCE
        or value["maximumPaidAnswerCalls"] != MAXIMUM_PAID_ANSWER_CALLS
        or value["retryAllowed"] is not False
        or value["resumeAllowed"] is not False
        or not _is_utc_timestamp(value["consumedAt"])
    ):
        _invalid()
    return value


def validate_employee_egress_lifecycle_v2(
    path: Path,
    *,
    consumed_path: Path,
    manifest_sha256: str,
) -> EmployeeEgressLifecycleSnapshotV2:
    raw_lines = path.read_bytes().splitlines()
    if not raw_lines or len(raw_lines) > 64:
        _invalid()
    records: list[dict[str, Any]] = []
    for raw in raw_lines:
        if not raw or len(raw) > 4096:
            _invalid()
        try:
            value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
        except (UnicodeError, json.JSONDecodeError):
            _invalid()
        if type(value) is not dict:
            _invalid()
        records.append(value)
    common = _common_record(manifest_sha256=manifest_sha256)
    if records[0] != {
        **common,
        "event": "run_started",
        "maximumPaidAnswerCalls": MAXIMUM_PAID_ANSWER_CALLS,
        "retryAllowed": False,
        "resumeAllowed": False,
    }:
        _invalid()
    terminal_record = records[-1]
    if (
        set(terminal_record) != {*common, "event", "status", "failurePhase", "failureReason"}
        or terminal_record.get("event") != "run_terminal"
    ):
        _invalid()
    cursor = 1
    employee_requests = 0
    employee_terminal: EmployeeTerminalStatus | None = None
    if cursor < len(records) - 1 and records[cursor].get("event") == "employee_detail_started":
        if records[cursor] != {**common, "event": "employee_detail_started", "requestOrdinal": 1}:
            _invalid()
        employee_requests = 1
        cursor += 1
        if cursor >= len(records) - 1 or records[cursor].get("event") != "employee_detail_terminal":
            _invalid()
        employee_value = records[cursor]
        if (
            set(employee_value) != {*common, "event", "requestOrdinal", "status"}
            or employee_value["requestOrdinal"] != 1
            or employee_value["status"] not in {"completed", "failed"}
        ):
            _invalid()
        employee_terminal = employee_value["status"]
        cursor += 1
    outcomes: list[ModelTerminalStatus] = []
    ordinal = 1
    while cursor < len(records) - 1:
        started = records[cursor]
        if started != {**common, "event": "model_outbound_started", "attemptOrdinal": ordinal}:
            _invalid()
        cursor += 1
        if cursor >= len(records) - 1:
            _invalid()
        terminal = records[cursor]
        if (
            set(terminal) != {*common, "event", "attemptOrdinal", "status"}
            or terminal["event"] != "model_call_terminal"
            or terminal["attemptOrdinal"] != ordinal
            or terminal["status"] not in _TERMINAL_MODEL_STATUSES
        ):
            _invalid()
        outcomes.append(terminal["status"])
        cursor += 1
        ordinal += 1
    if cursor != len(records) - 1 or len(outcomes) > MAXIMUM_PAID_ANSWER_CALLS:
        _invalid()
    consumed = consumed_path.is_file()
    if consumed:
        validate_consumed_marker(
            load_strict_json(consumed_path),
            manifest_sha256=manifest_sha256,
        )
    status = terminal_record["status"]
    phase_raw = terminal_record["failurePhase"]
    reason_raw = terminal_record["failureReason"]
    try:
        phase = None if phase_raw is None else EmployeeEgressFailurePhase(phase_raw)
        reason = None if reason_raw is None else EmployeeEgressFailureReason(reason_raw)
    except ValueError:
        _invalid()
    valid_answers = Counter(outcomes)["answer"]
    if status == "passed":
        if (
            not consumed
            or employee_requests != 1
            or employee_terminal != "completed"
            or len(outcomes) != MAXIMUM_PAID_ANSWER_CALLS
            or valid_answers < MINIMUM_VALID_ANSWER_CALLS
            or phase is not None
            or reason is not None
        ):
            _invalid()
    elif status == "failed_unconsumed":
        if (
            consumed
            or outcomes
            or phase is None
            or reason is None
            or reason not in _FAILURE_REASONS_BY_PHASE[phase]
        ):
            _invalid()
    elif status == "failed_consumed":
        if (
            not consumed
            or phase is None
            or reason is None
            or reason not in _FAILURE_REASONS_BY_PHASE[phase]
        ):
            _invalid()
    else:
        _invalid()
    return EmployeeEgressLifecycleSnapshotV2(
        record_count=len(records),
        employee_detail_requests=employee_requests,
        employee_detail_terminal=employee_terminal,
        model_outbound_calls=len(outcomes),
        model_terminal_records=len(outcomes),
        model_outcomes=tuple(outcomes),
        valid_answers=valid_answers,
        authorization_consumed=consumed,
        run_status=status,
        failure_phase=phase,
        failure_reason=reason,
    )


def _is_utc_timestamp(value: object) -> bool:
    if type(value) is not str or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.tzinfo is not None


def validate_manifest(value: object, *, repository_root: Path) -> dict[str, Any]:
    if type(value) is not dict or set(value) != {
        "schemaVersion",
        "status",
        "preparationWorkPackageId",
        "preparationGateId",
        "workPackageId",
        "gateId",
        "runId",
        "authorizationReference",
        "preparedAt",
        "modelBinding",
        "businessSnapshot",
        "fieldBoundary",
        "authorizationEvidence",
        "candidate01History",
        "executionBoundary",
        "assetHashes",
    }:
        _invalid()
    if (
        value["schemaVersion"] != 2
        or value["status"] != "prepared_unconsumed"
        or value["preparationWorkPackageId"] != PREPARATION_WORK_PACKAGE_ID
        or value["preparationGateId"] != PREPARATION_GATE_ID
        or value["workPackageId"] != WORK_PACKAGE_ID
        or value["gateId"] != GATE_ID
        or value["runId"] != RUN_ID
        or value["authorizationReference"] != AUTHORIZATION_REFERENCE
        or value["modelBinding"] != MODEL_TASK_BINDING
        or not _is_utc_timestamp(value["preparedAt"])
    ):
        _invalid()
    expected_snapshot = build_employee_egress_snapshot()
    if value["businessSnapshot"] != {
        "policyVersion": "business-egress-v1",
        "configSnapshotId": expected_snapshot.snapshot_id,
        "serviceBaseEndpoint": "http://127.0.0.1:9210",
        "employeeActionEnabled": True,
        "globalEgressEnabled": True,
    }:
        _invalid()
    if value["fieldBoundary"] != {
        "modelVisibleFieldIds": list(MODEL_VISIBLE_FIELD_IDS),
        "defaultDeny": True,
        "minimumSafeFactCount": 2,
    }:
        _invalid()
    _validate_hashed_evidence_list(
        value["authorizationEvidence"],
        repository_root=repository_root,
        expected_refs=AUTHORIZATION_EVIDENCE_REFS,
    )
    history = value["candidate01History"]
    if type(history) is not list or len(history) != 4:
        _invalid()
    history_kinds: set[str] = set()
    for item in history:
        if type(item) is not dict or set(item) != {"kind", "path", "sha256"}:
            _invalid()
        kind = item["kind"]
        if type(kind) is not str or type(item["path"]) is not str or kind in history_kinds:
            _invalid()
        history_kinds.add(kind)
        if (
            CANDIDATE_01_HISTORY_SHA256.get(kind) != item["sha256"]
            or CANDIDATE_01_HISTORY_PATHS.get(kind) != item["path"]
        ):
            _invalid()
        path = _repository_file(repository_root, item["path"])
        if sha256_file(path) != item["sha256"]:
            _invalid()
    if set(history_kinds) != set(CANDIDATE_01_HISTORY_SHA256):
        _invalid()
    if value["executionBoundary"] != {
        "employeeDetailRequests": 1,
        "plannedAnswerCalls": MAXIMUM_PAID_ANSWER_CALLS,
        "maximumPaidAnswerCalls": MAXIMUM_PAID_ANSWER_CALLS,
        "minimumValidAnswerCalls": MINIMUM_VALID_ANSWER_CALLS,
        "firstModelOutboundConsumesAuthorization": True,
        "retryAllowed": False,
        "resumeAllowed": False,
        "answerOnly": True,
        "sensitiveQuestionAllowed": False,
        "rawEmployeeDataPersistenceAllowed": False,
        "lifecycleJournalOutputPath": (
            "agent-runtime/tests/integration/adapters/employee/evidence/"
            f"{RUN_ID}.lifecycle.jsonl"
        ),
        "consumedMarkerPath": (
            "agent-runtime/tests/integration/adapters/employee/evidence/"
            f"{RUN_ID}.authorization.consumed.json"
        ),
        "evidenceOutputPath": (
            "agent-runtime/tests/integration/adapters/employee/evidence/"
            f"{RUN_ID}.result.json"
        ),
    }:
        _invalid()
    assets = value["assetHashes"]
    if type(assets) is not list or not assets:
        _invalid()
    paths: set[str] = set()
    for item in assets:
        if type(item) is not dict or set(item) != {"path", "sha256"}:
            _invalid()
        relative = item["path"]
        if type(relative) is not str or relative in paths or not _is_sha256(item["sha256"]):
            _invalid()
        paths.add(relative)
        path = _repository_file(repository_root, relative)
        if sha256_file(path) != item["sha256"]:
            _invalid()
    if paths != REQUIRED_ASSET_PATHS:
        _invalid()
    return value


def _validate_hashed_evidence_list(
    value: object,
    *,
    repository_root: Path,
    expected_refs: tuple[str, ...],
) -> None:
    if type(value) is not list or len(value) != len(expected_refs):
        _invalid()
    refs: list[str] = []
    for index, item in enumerate(value):
        if type(item) is not dict or set(item) != {"evidenceRef", "path", "sha256"}:
            _invalid()
        if (
            type(item["evidenceRef"]) is not str
            or type(item["path"]) is not str
            or not _is_sha256(item["sha256"])
        ):
            _invalid()
        refs.append(item["evidenceRef"])
        if (
            item["evidenceRef"],
            item["path"],
            item["sha256"],
        ) != AUTHORIZATION_EVIDENCE_ASSETS[index]:
            _invalid()
        path = _repository_file(repository_root, item["path"])
        if sha256_file(path) != item["sha256"]:
            _invalid()
    if tuple(refs) != expected_refs:
        _invalid()


def validate_authorization(value: object, *, manifest_sha256: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != {
        "schemaVersion",
        "status",
        "preparationWorkPackageId",
        "preparationGateId",
        "workPackageId",
        "gateId",
        "runId",
        "manifestSha256",
        "authorizationReference",
        "singleUse",
        "maximumPaidAnswerCalls",
        "retryAllowed",
        "resumeAllowed",
        "liveExecutionAuthorized",
        "confirmedBy",
        "preparedAt",
    }:
        _invalid()
    if (
        value["schemaVersion"] != 2
        or value["status"] != "prepared_unconsumed"
        or value["preparationWorkPackageId"] != PREPARATION_WORK_PACKAGE_ID
        or value["preparationGateId"] != PREPARATION_GATE_ID
        or value["workPackageId"] != WORK_PACKAGE_ID
        or value["gateId"] != GATE_ID
        or value["runId"] != RUN_ID
        or value["manifestSha256"] != manifest_sha256
        or value["authorizationReference"] != AUTHORIZATION_REFERENCE
        or value["singleUse"] is not True
        or value["maximumPaidAnswerCalls"] != MAXIMUM_PAID_ANSWER_CALLS
        or value["retryAllowed"] is not False
        or value["resumeAllowed"] is not False
        or value["liveExecutionAuthorized"] is not False
        or value["confirmedBy"] != "project-maintainer-pending-live-authorization"
        or not _is_utc_timestamp(value["preparedAt"])
    ):
        _invalid()
    return value


def validate_live_evidence(value: object) -> dict[str, Any]:
    if type(value) is not dict or set(value) != {
        "schemaVersion",
        "status",
        "workPackageId",
        "gateId",
        "runId",
        "manifestSha256",
        "authorizationReference",
        "recordedAt",
        "modelBinding",
        "fieldBoundary",
        "businessSnapshot",
        "authorizationEvidenceRefs",
        "authorizationState",
        "lifecycleJournal",
        "counts",
        "failure",
        "safety",
        "outcomes",
    }:
        _invalid()
    status = value["status"]
    if (
        value["schemaVersion"] != 2
        or status not in {"passed", "failed_unconsumed", "failed_consumed"}
        or value["workPackageId"] != WORK_PACKAGE_ID
        or value["gateId"] != GATE_ID
        or value["runId"] != RUN_ID
        or not _is_sha256(value["manifestSha256"])
        or value["authorizationReference"] != AUTHORIZATION_REFERENCE
        or not _is_utc_timestamp(value["recordedAt"])
        or value["modelBinding"] != MODEL_TASK_BINDING
        or value["fieldBoundary"] != {"modelVisibleFieldIds": list(MODEL_VISIBLE_FIELD_IDS)}
        or value["authorizationEvidenceRefs"] != list(AUTHORIZATION_EVIDENCE_REFS)
    ):
        _invalid()
    business_snapshot = value["businessSnapshot"]
    if (
        type(business_snapshot) is not dict
        or set(business_snapshot) != {"policyVersion", "configSnapshotId"}
        or business_snapshot["policyVersion"] != "business-egress-v1"
        or not _is_sha256(business_snapshot["configSnapshotId"])
    ):
        _invalid()
    authorization_state = value["authorizationState"]
    consumed = status in {"passed", "failed_consumed"}
    if (
        type(authorization_state) is not dict
        or set(authorization_state) != {"consumed", "consumedMarkerSha256"}
        or authorization_state["consumed"] is not consumed
        or (
            consumed
            and not _is_sha256(authorization_state["consumedMarkerSha256"])
        )
        or (not consumed and authorization_state["consumedMarkerSha256"] is not None)
    ):
        _invalid()
    lifecycle = value["lifecycleJournal"]
    if (
        type(lifecycle) is not dict
        or set(lifecycle) != {"recordCount", "sha256"}
        or type(lifecycle["recordCount"]) is not int
        or not 2 <= lifecycle["recordCount"] <= 64
        or not _is_sha256(lifecycle["sha256"])
    ):
        _invalid()
    counts = value["counts"]
    if type(counts) is not dict or set(counts) != {
        "employeeDetailRequests",
        "otherEmployeeEndpoints",
        "plannedAnswerCalls",
        "maximumPaidAnswerCalls",
        "actualAnswerCalls",
        "terminalAnswerRecords",
        "validAnswers",
        "retryCount",
        "resumeCount",
    }:
        _invalid()
    if (
        type(counts["employeeDetailRequests"]) is not int
        or not 0 <= counts["employeeDetailRequests"] <= 1
        or counts["otherEmployeeEndpoints"] != 0
        or counts["plannedAnswerCalls"] != MAXIMUM_PAID_ANSWER_CALLS
        or counts["maximumPaidAnswerCalls"] != MAXIMUM_PAID_ANSWER_CALLS
        or type(counts["actualAnswerCalls"]) is not int
        or not 0 <= counts["actualAnswerCalls"] <= MAXIMUM_PAID_ANSWER_CALLS
        or counts["terminalAnswerRecords"] != counts["actualAnswerCalls"]
        or type(counts["validAnswers"]) is not int
        or not 0 <= counts["validAnswers"] <= counts["actualAnswerCalls"]
        or counts["retryCount"] != 0
        or counts["resumeCount"] != 0
    ):
        _invalid()
    failure = value["failure"]
    if type(failure) is not dict or set(failure) != {"phase", "reason"}:
        _invalid()
    if status == "passed":
        if (
            failure != {"phase": None, "reason": None}
            or counts["employeeDetailRequests"] != 1
            or counts["actualAnswerCalls"] != MAXIMUM_PAID_ANSWER_CALLS
            or counts["validAnswers"] < MINIMUM_VALID_ANSWER_CALLS
        ):
            _invalid()
    else:
        try:
            phase = EmployeeEgressFailurePhase(failure["phase"])
            reason = EmployeeEgressFailureReason(failure["reason"])
        except (TypeError, ValueError):
            _invalid()
        if reason not in _FAILURE_REASONS_BY_PHASE[phase]:
            _invalid()
        if status == "failed_unconsumed" and counts["actualAnswerCalls"] != 0:
            _invalid()
    safety = value["safety"]
    if type(safety) is not dict or set(safety) != {
        "forbiddenPayloadFieldCount",
        "forbiddenLiteralCount",
        "logLeakCount",
        "jwtPersisted",
        "identifierPersisted",
        "employeeDataPersisted",
        "rawModelResponsePersisted",
    }:
        _invalid()
    for key in ("forbiddenPayloadFieldCount", "forbiddenLiteralCount", "logLeakCount"):
        if type(safety[key]) is not int or safety[key] < 0 or safety[key] > 1_000:
            _invalid()
    if any(
        safety[key] is not False
        for key in (
            "jwtPersisted",
            "identifierPersisted",
            "employeeDataPersisted",
            "rawModelResponsePersisted",
        )
    ):
        _invalid()
    outcomes = value["outcomes"]
    if type(outcomes) is not list or len(outcomes) != counts["actualAnswerCalls"]:
        _invalid()
    for ordinal, item in enumerate(outcomes, 1):
        if (
            type(item) is not dict
            or set(item) != {"attemptOrdinal", "status"}
            or item["attemptOrdinal"] != ordinal
            or item["status"] not in _TERMINAL_MODEL_STATUSES
        ):
            _invalid()
    if Counter(item["status"] for item in outcomes)["answer"] != counts["validAnswers"]:
        _invalid()
    if status == "passed" and any(
        safety[key] != 0
        for key in ("forbiddenPayloadFieldCount", "forbiddenLiteralCount", "logLeakCount")
    ):
        _invalid()
    return value


def record_failure_terminal(
    journal: EmployeeEgressLifecycleJournalV2,
    *,
    phase: EmployeeEgressFailurePhase,
    reason: EmployeeEgressFailureReason,
) -> RunTerminalStatus:
    status: RunTerminalStatus = (
        "failed_consumed" if journal.consumed_marker_path.is_file() else "failed_unconsumed"
    )
    journal.record_run_terminal(status=status, failure_phase=phase, failure_reason=reason)
    return status


def finalize_employee_egress_evidence_v2(
    *,
    journal: EmployeeEgressLifecycleJournalV2,
    evidence_path: Path,
    config_snapshot_id: str,
    safety: EmployeeEgressSafetySnapshotV2 = EmployeeEgressSafetySnapshotV2(),
) -> dict[str, Any]:
    snapshot = validate_employee_egress_lifecycle_v2(
        journal.path,
        consumed_path=journal.consumed_marker_path,
        manifest_sha256=journal.manifest_sha256,
    )
    marker_sha = (
        sha256_file(journal.consumed_marker_path)
        if journal.consumed_marker_path.is_file()
        else None
    )
    evidence: dict[str, Any] = {
        "schemaVersion": 2,
        "status": snapshot.run_status,
        "workPackageId": WORK_PACKAGE_ID,
        "gateId": GATE_ID,
        "runId": RUN_ID,
        "manifestSha256": journal.manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "recordedAt": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "modelBinding": dict(MODEL_TASK_BINDING),
        "fieldBoundary": {"modelVisibleFieldIds": list(MODEL_VISIBLE_FIELD_IDS)},
        "businessSnapshot": {
            "policyVersion": "business-egress-v1",
            "configSnapshotId": config_snapshot_id,
        },
        "authorizationEvidenceRefs": list(AUTHORIZATION_EVIDENCE_REFS),
        "authorizationState": {
            "consumed": snapshot.authorization_consumed,
            "consumedMarkerSha256": marker_sha,
        },
        "lifecycleJournal": {
            "recordCount": snapshot.record_count,
            "sha256": sha256_file(journal.path),
        },
        "counts": {
            "employeeDetailRequests": snapshot.employee_detail_requests,
            "otherEmployeeEndpoints": 0,
            "plannedAnswerCalls": MAXIMUM_PAID_ANSWER_CALLS,
            "maximumPaidAnswerCalls": MAXIMUM_PAID_ANSWER_CALLS,
            "actualAnswerCalls": snapshot.model_outbound_calls,
            "terminalAnswerRecords": snapshot.model_terminal_records,
            "validAnswers": snapshot.valid_answers,
            "retryCount": 0,
            "resumeCount": 0,
        },
        "failure": {
            "phase": None if snapshot.failure_phase is None else snapshot.failure_phase.value,
            "reason": None if snapshot.failure_reason is None else snapshot.failure_reason.value,
        },
        "safety": {
            "forbiddenPayloadFieldCount": safety.forbidden_payload_field_count,
            "forbiddenLiteralCount": safety.forbidden_literal_count,
            "logLeakCount": safety.log_leak_count,
            "jwtPersisted": False,
            "identifierPersisted": False,
            "employeeDataPersisted": False,
            "rawModelResponsePersisted": False,
        },
        "outcomes": [
            {"attemptOrdinal": ordinal, "status": status}
            for ordinal, status in enumerate(snapshot.model_outcomes, 1)
        ],
    }
    validate_live_evidence(evidence)
    try:
        write_exclusive_json(evidence_path, evidence)
    except OSError as exc:
        raise EmployeeEgressEvidenceWriteV2Error(
            "employee.egress_candidate_v2_evidence_write_failed"
        ) from None
    return evidence


def safe_question() -> str:
    return _SAFE_QUESTION
