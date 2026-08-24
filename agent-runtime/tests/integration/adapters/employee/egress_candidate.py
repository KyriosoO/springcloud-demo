from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, NoReturn

from agent_runtime.adapters.employee.definition import employee_detail_definition
from agent_runtime.adapters.employee.settings import EmployeeAdapterSettings
from agent_runtime.business.settings import (
    BusinessConfigurationSource,
    BusinessConfigurationSnapshot,
    BusinessGlobalSettings,
    BusinessServiceBinding,
    BusinessSettingsValidator,
)
from agent_runtime.capability_api.contracts import JsonObject
from agent_runtime.capability_api.action_resolution import (
    LocalActionResolution,
    LocalActionResolutionKind,
)
from agent_runtime.model.contracts import (
    ModelTaskId,
    StructuredModelRequest,
    StructuredModelResponse,
    StructuredModelTransport,
    StructuredOutputMode,
    StructuredToolMode,
)


RUN_ID: Final = "employee-egress-v1-20260813-candidate-01"
WORK_PACKAGE_ID: Final = "WP-EMP-EGRESS-01"
GATE_ID: Final = "GATE-024"
AUTHORIZATION_REFERENCE: Final = "P3_00:GATE-024"
MAXIMUM_PAID_ANSWER_CALLS: Final = 30
MINIMUM_VALID_ANSWER_CALLS: Final = 27
MODEL_VISIBLE_FIELD_IDS: Final = ("position", "work_base_si")
FROZEN_CONFIG_SNAPSHOT_ID: Final = (
    "14b609a7d9ca95a97e830e570f8b48ed84e8476a3cf3d4b198558e8a4f6efd28"
)
MODEL_TASK_BINDING: Final = {
    "taskId": "answer_generation",
    "taskVersion": "answer-generation-v1",
    "modelName": "deepseek-v4-pro",
}


class _HistoricalEmployeeResolver:
    __slots__ = ()

    @property
    def capability_id(self) -> str:
        return "employee.detail"

    def resolve(self, question: str) -> LocalActionResolution:
        del question
        return LocalActionResolution(kind=LocalActionResolutionKind.NO_MATCH)
AUTHORIZATION_EVIDENCE_REFS: Final = (
    "WP-EMP-REAL-01:authorizationMatrix.admin",
    "WP-EMP-REAL-01:VAL-EMP-005",
)
_SAFE_QUESTION: Final = "查询单个员工详情"
_EVIDENCE_KEYS: Final = {
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
    "attemptJournal",
    "counts",
    "safety",
    "outcomes",
}


class EmployeeEgressCandidateError(ValueError):
    pass


class EmployeeEgressAttemptJournal:
    def __init__(self, path: Path) -> None:
        self._path = path
        write_exclusive_json(
            path,
            {
                "schemaVersion": 1,
                "event": "attempt_started",
                "workPackageId": WORK_PACKAGE_ID,
                "gateId": GATE_ID,
                "runId": RUN_ID,
                "authorizationReference": AUTHORIZATION_REFERENCE,
                "maximumPaidAnswerCalls": MAXIMUM_PAID_ANSWER_CALLS,
                "retryAllowed": False,
                "resumeAllowed": False,
            },
        )

    def record_outbound_started(self, ordinal: int) -> None:
        self._append({"event": "outbound_started", "attemptOrdinal": ordinal})

    def record_terminal(self, ordinal: int, status: str) -> None:
        if status not in {"answer", "invalid_output", "input_denied", "timeout", "provider_failure"}:
            _invalid()
        self._append(
            {"event": "call_terminal", "attemptOrdinal": ordinal, "status": status}
        )

    def _append(self, value: Mapping[str, object]) -> None:
        record = {
            "schemaVersion": 1,
            "workPackageId": WORK_PACKAGE_ID,
            "gateId": GATE_ID,
            "runId": RUN_ID,
            "authorizationReference": AUTHORIZATION_REFERENCE,
            **value,
        }
        with self._path.open("a", encoding="utf-8", newline="\n") as stream:
            json.dump(record, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())


def validate_attempt_journal(path: Path) -> tuple[dict[str, Any], ...]:
    raw_lines = path.read_bytes().splitlines()
    if not raw_lines or len(raw_lines) > 1 + MAXIMUM_PAID_ANSWER_CALLS * 2:
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
    header = records[0]
    if header != {
        "schemaVersion": 1,
        "event": "attempt_started",
        "workPackageId": WORK_PACKAGE_ID,
        "gateId": GATE_ID,
        "runId": RUN_ID,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "maximumPaidAnswerCalls": MAXIMUM_PAID_ANSWER_CALLS,
        "retryAllowed": False,
        "resumeAllowed": False,
    }:
        _invalid()
    for index, record in enumerate(records[1:], 1):
        expected_ordinal = (index + 1) // 2
        common = {
            "schemaVersion": 1,
            "workPackageId": WORK_PACKAGE_ID,
            "gateId": GATE_ID,
            "runId": RUN_ID,
            "authorizationReference": AUTHORIZATION_REFERENCE,
        }
        if any(record.get(key) != expected for key, expected in common.items()):
            _invalid()
        if index % 2 == 1:
            if record != {**common, "event": "outbound_started", "attemptOrdinal": expected_ordinal}:
                _invalid()
        elif (
            set(record) != {*common, "event", "attemptOrdinal", "status"}
            or record["event"] != "call_terminal"
            or record["attemptOrdinal"] != expected_ordinal
            or record["status"]
            not in {"answer", "invalid_output", "input_denied", "timeout", "provider_failure"}
        ):
            _invalid()
    return tuple(records)


def _invalid() -> NoReturn:
    raise EmployeeEgressCandidateError("employee.egress_candidate_invalid")


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


def build_employee_egress_snapshot() -> BusinessConfigurationSnapshot:
    definition = replace(
        employee_detail_definition(),
        query_fields=(),
        combination_rules=(),
        code_contract_version="legacy-v1",
        service_contract_ref="legacy-v1",
        local_action_resolver=_HistoricalEmployeeResolver(),
    )
    action = replace(
        EmployeeAdapterSettings.from_env(
            {
                "AGENT_EMPLOYEE_DETAIL_ENABLED": "true",
                "AGENT_EMPLOYEE_DETAIL_MODEL_FIELDS": ",".join(MODEL_VISIBLE_FIELD_IDS),
            }
        ).action,
        config_version="legacy-v1",
        code_contract_version="legacy-v1",
        service_contract_ref="legacy-v1",
        query_fields=(),
        combination_rule_ids=(),
    )
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


def validate_manifest(value: object, *, repository_root: Path) -> dict[str, Any]:
    if type(value) is not dict:
        _invalid()
    expected_keys = {
        "schemaVersion",
        "status",
        "workPackageId",
        "gateId",
        "runId",
        "authorizationReference",
        "preparedAt",
        "modelBinding",
        "businessSnapshot",
        "fieldBoundary",
        "authorizationEvidence",
        "executionBoundary",
        "assetHashes",
    }
    if set(value) != expected_keys:
        _invalid()
    if (
        value["schemaVersion"] != 1
        or value["status"] != "prepared_unconsumed"
        or value["workPackageId"] != WORK_PACKAGE_ID
        or value["gateId"] != GATE_ID
        or value["runId"] != RUN_ID
        or value["authorizationReference"] != AUTHORIZATION_REFERENCE
        or value["modelBinding"] != MODEL_TASK_BINDING
    ):
        _invalid()
    snapshot = value["businessSnapshot"]
    if type(snapshot) is not dict or snapshot != {
        "policyVersion": "business-egress-v1",
        "configSnapshotId": FROZEN_CONFIG_SNAPSHOT_ID,
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
    authorization_evidence = value["authorizationEvidence"]
    if type(authorization_evidence) is not list or [
        item.get("evidenceRef") if type(item) is dict else None for item in authorization_evidence
    ] != list(AUTHORIZATION_EVIDENCE_REFS):
        _invalid()
    for item in authorization_evidence:
        if type(item) is not dict or set(item) != {"evidenceRef", "path", "sha256"}:
            _invalid()
        path = repository_root / str(item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            _invalid()
    boundary = value["executionBoundary"]
    if type(boundary) is not dict or boundary != {
        "employeeDetailRequests": 1,
        "plannedAnswerCalls": 30,
        "maximumPaidAnswerCalls": 30,
        "minimumValidAnswerCalls": 27,
        "firstModelOutboundConsumesAuthorization": True,
        "retryAllowed": False,
        "resumeAllowed": False,
        "answerOnly": True,
        "sensitiveQuestionAllowed": False,
        "rawEmployeeDataPersistenceAllowed": False,
        "consumedMarkerPath": (
            "agent-runtime/tests/integration/adapters/employee/evidence/"
            "employee-egress-v1-20260813-candidate-01.authorization.consumed.json"
        ),
        "evidenceOutputPath": (
            "agent-runtime/tests/integration/adapters/employee/evidence/"
            "employee-egress-v1-20260813-candidate-01.result.json"
        ),
        "attemptJournalOutputPath": (
            "agent-runtime/tests/integration/adapters/employee/evidence/"
            "employee-egress-v1-20260813-candidate-01.attempts.jsonl"
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
        if type(relative) is not str or relative in paths:
            _invalid()
        paths.add(relative)
        path = repository_root / relative
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            _invalid()
    return value


def validate_authorization(value: object, *, manifest_sha256: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != {
        "schemaVersion",
        "status",
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
    if value != {
        "schemaVersion": 1,
        "status": "prepared_unconsumed",
        "workPackageId": WORK_PACKAGE_ID,
        "gateId": GATE_ID,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "singleUse": True,
        "maximumPaidAnswerCalls": MAXIMUM_PAID_ANSWER_CALLS,
        "retryAllowed": False,
        "resumeAllowed": False,
        "liveExecutionAuthorized": False,
        "confirmedBy": "project-maintainer-pending-live-authorization",
        "preparedAt": "2026-08-13T09:46:23Z",
    }:
        _invalid()
    return value


def validate_live_evidence(value: object) -> dict[str, Any]:
    if type(value) is not dict or set(value) != _EVIDENCE_KEYS:
        _invalid()
    if (
        value["schemaVersion"] != 1
        or value["status"] not in {"passed", "failed"}
        or value["workPackageId"] != WORK_PACKAGE_ID
        or value["gateId"] != GATE_ID
        or value["runId"] != RUN_ID
        or value["authorizationReference"] != AUTHORIZATION_REFERENCE
        or value["modelBinding"] != MODEL_TASK_BINDING
        or value["fieldBoundary"] != {"modelVisibleFieldIds": list(MODEL_VISIBLE_FIELD_IDS)}
        or value["authorizationEvidenceRefs"] != list(AUTHORIZATION_EVIDENCE_REFS)
    ):
        _invalid()
    manifest_sha = value["manifestSha256"]
    recorded_at = value["recordedAt"]
    snapshot = value["businessSnapshot"]
    if (
        type(manifest_sha) is not str
        or len(manifest_sha) != 64
        or any(character not in "0123456789abcdef" for character in manifest_sha)
        or type(recorded_at) is not str
        or not recorded_at.endswith("Z")
        or type(snapshot) is not dict
        or set(snapshot) != {"policyVersion", "configSnapshotId"}
        or snapshot["policyVersion"] != "business-egress-v1"
        or snapshot["configSnapshotId"] != FROZEN_CONFIG_SNAPSHOT_ID
    ):
        _invalid()
    try:
        if datetime.fromisoformat(recorded_at[:-1] + "+00:00").tzinfo is None:
            _invalid()
    except ValueError:
        _invalid()
    counts = value["counts"]
    attempt_journal = value["attemptJournal"]
    safety = value["safety"]
    outcomes = value["outcomes"]
    if (
        type(attempt_journal) is not dict
        or set(attempt_journal) != {"recordCount", "sha256"}
        or type(attempt_journal["recordCount"]) is not int
        or not 1 <= attempt_journal["recordCount"] <= 61
        or type(attempt_journal["sha256"]) is not str
        or len(attempt_journal["sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in attempt_journal["sha256"])
    ):
        _invalid()
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
    actual = counts["actualAnswerCalls"]
    terminal = counts["terminalAnswerRecords"]
    valid = counts["validAnswers"]
    if (
        counts["employeeDetailRequests"] != 1
        or counts["otherEmployeeEndpoints"] != 0
        or counts["plannedAnswerCalls"] != MAXIMUM_PAID_ANSWER_CALLS
        or counts["maximumPaidAnswerCalls"] != MAXIMUM_PAID_ANSWER_CALLS
        or type(actual) is not int
        or not 0 <= actual <= MAXIMUM_PAID_ANSWER_CALLS
        or type(terminal) is not int
        or terminal != actual
        or type(valid) is not int
        or not 0 <= valid <= actual
        or counts["retryCount"] != 0
        or counts["resumeCount"] != 0
        or attempt_journal["recordCount"] != 1 + terminal * 2
    ):
        _invalid()
    if type(safety) is not dict or safety != {
        "forbiddenPayloadFieldCount": 0,
        "forbiddenLiteralCount": 0,
        "logLeakCount": 0,
        "jwtPersisted": False,
        "identifierPersisted": False,
        "employeeDataPersisted": False,
        "rawModelResponsePersisted": False,
    }:
        _invalid()
    if type(outcomes) is not list or len(outcomes) != actual:
        _invalid()
    allowed_statuses = {"answer", "invalid_output", "input_denied", "timeout", "provider_failure"}
    for ordinal, item in enumerate(outcomes, 1):
        if (
            type(item) is not dict
            or set(item) != {"attemptOrdinal", "status"}
            or item["attemptOrdinal"] != ordinal
            or item["status"] not in allowed_statuses
        ):
            _invalid()
    if Counter(item["status"] for item in outcomes)["answer"] != valid:
        _invalid()
    passed = value["status"] == "passed"
    if passed != (
        actual == MAXIMUM_PAID_ANSWER_CALLS
        and terminal == MAXIMUM_PAID_ANSWER_CALLS
        and valid >= MINIMUM_VALID_ANSWER_CALLS
    ):
        _invalid()
    return value


def write_exclusive_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


class BudgetedEmployeeAnswerTransport:
    def __init__(
        self,
        *,
        delegate: StructuredModelTransport,
        consumed_marker_path: Path,
        journal: EmployeeEgressAttemptJournal,
        manifest_sha256: str,
        forbidden_literals: Sequence[str] = (),
    ) -> None:
        self._delegate = delegate
        self._consumed_marker_path = consumed_marker_path
        self._journal = journal
        self._manifest_sha256 = manifest_sha256
        self._forbidden_literals = tuple(value for value in forbidden_literals if value)
        self.calls = 0
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
            raise RuntimeError("employee.egress_candidate_budget_exhausted")
        self._validate_request(request)
        if self.calls == 0:
            write_exclusive_json(
                self._consumed_marker_path,
                {
                    "schemaVersion": 1,
                    "workPackageId": WORK_PACKAGE_ID,
                    "gateId": GATE_ID,
                    "runId": RUN_ID,
                    "manifestSha256": self._manifest_sha256,
                    "authorizationReference": AUTHORIZATION_REFERENCE,
                    "consumedAt": datetime.now(timezone.utc)
                    .isoformat(timespec="seconds")
                    .replace("+00:00", "Z"),
                    "maximumPaidAnswerCalls": MAXIMUM_PAID_ANSWER_CALLS,
                    "retryAllowed": False,
                    "resumeAllowed": False,
                },
            )
        self.calls += 1
        self._journal.record_outbound_started(self.calls)
        self.requests.append(request)
        return await self._delegate.complete(request, call_deadline=call_deadline)

    def record_terminal(self, status: str) -> None:
        self._journal.record_terminal(self.calls, status)

    def _validate_request(self, request: StructuredModelRequest) -> None:
        if (
            request.task_id is not ModelTaskId.ANSWER_GENERATION
            or request.task_version != "answer-generation-v1"
            or request.tools
            or request.tool_mode is not StructuredToolMode.NONE
            or request.output_mode is not StructuredOutputMode.JSON_OBJECT
        ):
            raise RuntimeError("employee.egress_candidate_request_invalid")
        try:
            payload = json.loads(request.user_payload_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("employee.egress_candidate_request_invalid") from exc
        if type(payload) is not dict or set(payload) != {"question", "safe_payload"}:
            raise RuntimeError("employee.egress_candidate_request_invalid")
        if payload["question"] != _SAFE_QUESTION:
            raise RuntimeError("employee.egress_candidate_question_invalid")
        safe_payload = payload["safe_payload"]
        if type(safe_payload) is not dict:
            raise RuntimeError("employee.egress_candidate_request_invalid")
        facts = safe_payload.get("facts")
        if type(facts) is not list or len(facts) != len(MODEL_VISIBLE_FIELD_IDS):
            raise RuntimeError("employee.egress_candidate_field_boundary_invalid")
        field_ids: list[str] = []
        for fact in facts:
            if type(fact) is not dict:
                raise RuntimeError("employee.egress_candidate_field_boundary_invalid")
            source = fact.get("source")
            if type(source) is not dict or type(source.get("field_id")) is not str:
                raise RuntimeError("employee.egress_candidate_field_boundary_invalid")
            field_ids.append(source["field_id"])
        if tuple(field_ids) != MODEL_VISIBLE_FIELD_IDS:
            raise RuntimeError("employee.egress_candidate_field_boundary_invalid")
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
            raise RuntimeError("employee.egress_candidate_payload_forbidden")


def _count_keys(value: object, forbidden: frozenset[str] | set[str]) -> int:
    if isinstance(value, dict):
        return sum(key in forbidden for key in value) + sum(
            _count_keys(item, forbidden) for item in value.values()
        )
    if isinstance(value, list):
        return sum(_count_keys(item, forbidden) for item in value)
    return 0


def safe_question() -> str:
    return _SAFE_QUESTION
