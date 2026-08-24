from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final, cast

from agent_runtime.model.deepseek.business_query_plan import (
    BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION,
    BUSINESS_QUERY_PLAN_TASK_VERSION,
)


RUN_ID: Final = "business-query-plan-live-v1-20260824-candidate-01"
AUTHORIZATION_REFERENCE: Final = "P3_00:GATE-065"
WORK_PACKAGE: Final = "WP-BQ-QUERYPLAN-LIVE-01"
MODEL_CALL_BUDGET: Final = 6
EMPLOYEE_DETAIL_BUDGET: Final = 2
TRANSACTION_SEARCH_BUDGET: Final = 2

CASE_IDS: Final = (
    "bq-live-emp-admin",
    "bq-live-emp-denied",
    "bq-live-emp-unsupported",
    "bq-live-txn-admin",
    "bq-live-txn-denied",
    "bq-live-txn-unsupported",
)

_SHA256 = frozenset("0123456789abcdef")
_TERMINAL_STATUSES = frozenset({"passed", "failed_unconsumed", "failed_consumed"})
_CASE_STATUSES = {
    "bq-live-emp-admin": frozenset({"success"}),
    "bq-live-emp-denied": frozenset({"forbidden"}),
    "bq-live-emp-unsupported": frozenset({"unsupported"}),
    "bq-live-txn-admin": frozenset({"success", "no_result"}),
    "bq-live-txn-denied": frozenset({"forbidden"}),
    "bq-live-txn-unsupported": frozenset({"unsupported"}),
}
_CASE_CAPABILITIES = {
    "bq-live-emp-admin": "employee.detail",
    "bq-live-emp-denied": "employee.detail",
    "bq-live-emp-unsupported": None,
    "bq-live-txn-admin": "transaction.search",
    "bq-live-txn-denied": "transaction.search",
    "bq-live-txn-unsupported": None,
}
_CASE_DOMAINS = {case_id: ("employee" if "-emp-" in case_id else "transaction") for case_id in CASE_IDS}
_CASE_DOMAIN_CALLS = {
    "bq-live-emp-admin": 1,
    "bq-live-emp-denied": 1,
    "bq-live-emp-unsupported": 0,
    "bq-live-txn-admin": 1,
    "bq-live-txn-denied": 1,
    "bq-live-txn-unsupported": 0,
}
_MANIFEST_CASES: Final = (
    {"caseId": "bq-live-emp-admin", "domain": "employee", "principal": "admin", "questionTemplate": "employee.detail.protected-ref", "expectedStatus": "success", "expectedCapabilityId": "employee.detail"},
    {"caseId": "bq-live-emp-denied", "domain": "employee", "principal": "denied", "questionTemplate": "employee.detail.protected-ref", "expectedStatus": "forbidden", "expectedCapabilityId": "employee.detail"},
    {"caseId": "bq-live-emp-unsupported", "domain": "employee", "principal": "admin", "questionTemplate": "employee.location.unsupported", "expectedStatus": "unsupported", "expectedCapabilityId": None},
    {"caseId": "bq-live-txn-admin", "domain": "transaction", "principal": "admin", "questionTemplate": "transaction.amount.exact", "expectedStatus": "success_or_no_result", "expectedCapabilityId": "transaction.search"},
    {"caseId": "bq-live-txn-denied", "domain": "transaction", "principal": "denied", "questionTemplate": "transaction.amount.exact", "expectedStatus": "forbidden", "expectedCapabilityId": "transaction.search"},
    {"caseId": "bq-live-txn-unsupported", "domain": "transaction", "principal": "admin", "questionTemplate": "transaction.date.unsupported", "expectedStatus": "unsupported", "expectedCapabilityId": None},
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def write_exclusive_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(value)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def append_journal(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(value)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "ab") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def validate_manifest(value: object) -> dict[str, object]:
    if type(value) is not dict:
        raise ValueError("business_query_plan_live.manifest_shape_invalid")
    manifest = cast(dict[str, object], value)
    expected_keys = {
        "schemaVersion",
        "workPackage",
        "state",
        "runId",
        "authorizationReference",
        "preparedHead",
        "model",
        "queryPlanTask",
        "snapshots",
        "cases",
        "budgets",
        "assets",
        "history",
        "constraints",
    }
    if set(manifest) != expected_keys:
        raise ValueError("business_query_plan_live.manifest_shape_invalid")
    if (
        manifest["schemaVersion"] != 1
        or manifest["workPackage"] != WORK_PACKAGE
        or manifest["state"] != "prepared_unconsumed"
        or manifest["runId"] != RUN_ID
        or manifest["authorizationReference"] != AUTHORIZATION_REFERENCE
        or not _is_git_sha(manifest["preparedHead"])
    ):
        raise ValueError("business_query_plan_live.manifest_binding_invalid")
    model = _exact_mapping(manifest["model"], {"provider", "name", "requestMode"})
    if model != {"provider": "deepseek", "name": "deepseek-v4-pro", "requestMode": "json_object_no_tools"}:
        raise ValueError("business_query_plan_live.manifest_model_invalid")
    task = _exact_mapping(manifest["queryPlanTask"], {"id", "version", "systemInstructionSha256"})
    if (
        task.get("id") != "business_query_plan"
        or task.get("version") != BUSINESS_QUERY_PLAN_TASK_VERSION
        or task.get("systemInstructionSha256") != hashlib.sha256(
            BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION.encode("utf-8")
        ).hexdigest()
    ):
        raise ValueError("business_query_plan_live.manifest_task_invalid")
    snapshots = _exact_mapping(manifest["snapshots"], {"catalogSha256", "configSha256"})
    if not all(_is_sha256(item) for item in snapshots.values()):
        raise ValueError("business_query_plan_live.manifest_snapshot_invalid")
    cases = _exact_sequence(manifest["cases"], len(CASE_IDS))
    if tuple(_case_id(item) for item in cases) != CASE_IDS or cases != _MANIFEST_CASES:
        raise ValueError("business_query_plan_live.manifest_cases_invalid")
    budgets = _exact_mapping(
        manifest["budgets"],
        {"modelCalls", "employeeDetail", "transactionSearch", "otherBusinessEndpoints", "retry", "resume"},
    )
    if budgets != {
        "modelCalls": MODEL_CALL_BUDGET,
        "employeeDetail": EMPLOYEE_DETAIL_BUDGET,
        "transactionSearch": TRANSACTION_SEARCH_BUDGET,
        "otherBusinessEndpoints": 0,
        "retry": 0,
        "resume": 0,
    }:
        raise ValueError("business_query_plan_live.manifest_budget_invalid")
    assets = _exact_sequence(manifest["assets"], minimum=1)
    for asset in assets:
        item = _exact_mapping(asset, {"path", "sha256"})
        path = item.get("path")
        if (
            type(path) is not str
            or not path
            or "\\" in path
            or path.startswith("/")
            or ":" in path
            or ".." in path.split("/")
            or not _is_sha256(item.get("sha256"))
        ):
            raise ValueError("business_query_plan_live.manifest_asset_invalid")
    history = _exact_mapping(
        manifest["history"],
        {"nonLiveTestSha256", "nonLiveEvidenceContractSha256", "historicalAssetsImmutable"},
    )
    if (
        not _is_sha256(history.get("nonLiveTestSha256"))
        or not _is_sha256(history.get("nonLiveEvidenceContractSha256"))
        or history.get("historicalAssetsImmutable") is not True
    ):
        raise ValueError("business_query_plan_live.manifest_history_invalid")
    constraints = _exact_mapping(
        manifest["constraints"],
        {
            "firstOutboundConsumes",
            "noRetry",
            "noResume",
            "noAnswerTask",
            "noKnowledgeFallback",
            "noCrossDomainFallback",
            "noRawPersistence",
        },
    )
    if set(constraints.values()) != {True}:
        raise ValueError("business_query_plan_live.manifest_constraints_invalid")
    return manifest


def validate_authorization_template(
    value: object,
    *,
    manifest_sha256: str,
    prepared_head: str,
) -> None:
    item = _exact_mapping(
        value,
        {
            "schemaVersion",
            "state",
            "liveExecutionAuthorized",
            "runId",
            "authorizationReference",
            "sourcePreparedHead",
            "manifestSha256",
            "budgets",
            "requiredBindings",
            "constraints",
        },
    )
    if (
        item["schemaVersion"] != 1
        or item["state"] != "prepared_unconsumed"
        or item["liveExecutionAuthorized"] is not False
        or item["runId"] != RUN_ID
        or item["authorizationReference"] != AUTHORIZATION_REFERENCE
        or item["sourcePreparedHead"] != prepared_head
        or item["manifestSha256"] != manifest_sha256
    ):
        raise ValueError("business_query_plan_live.authorization_template_invalid")
    budgets = _exact_mapping(
        item["budgets"],
        {"modelCalls", "employeeDetail", "transactionSearch", "retry", "resume"},
    )
    if budgets != {
        "modelCalls": MODEL_CALL_BUDGET,
        "employeeDetail": EMPLOYEE_DETAIL_BUDGET,
        "transactionSearch": TRANSACTION_SEARCH_BUDGET,
        "retry": 0,
        "resume": 0,
    }:
        raise ValueError("business_query_plan_live.authorization_template_invalid")
    bindings = _exact_mapping(
        item["requiredBindings"],
        {
            "finalFrozenHead",
            "processLlmApiKey",
            "processEmployeeIdentifier",
            "processAdminJwt",
            "processDeniedJwt",
            "employeeBaseUrl",
            "transactionBaseUrl",
        },
    )
    if bindings != {
        "finalFrozenHead": "required_in_final_authorization",
        "processLlmApiKey": "required_memory_only",
        "processEmployeeIdentifier": "required_memory_only",
        "processAdminJwt": "required_memory_only",
        "processDeniedJwt": "required_memory_only",
        "employeeBaseUrl": "http://127.0.0.1:9210",
        "transactionBaseUrl": "http://127.0.0.1:8182",
    }:
        raise ValueError("business_query_plan_live.authorization_template_invalid")
    constraints = _exact_mapping(
        item["constraints"],
        {"singleUse", "firstOutboundConsumes", "automaticRetry", "rerun", "resume", "answerTask"},
    )
    if constraints != {
        "singleUse": True,
        "firstOutboundConsumes": True,
        "automaticRetry": False,
        "rerun": False,
        "resume": False,
        "answerTask": False,
    }:
        raise ValueError("business_query_plan_live.authorization_template_invalid")


def validate_result(value: object, *, require_passed: bool) -> dict[str, object]:
    if type(value) is not dict:
        raise ValueError("business_query_plan_live.result_shape_invalid")
    result = cast(dict[str, object], value)
    expected_keys = {
        "schemaVersion",
        "workPackage",
        "runId",
        "authorizationReference",
        "manifestSha256",
        "status",
        "reason",
        "cases",
        "counts",
        "security",
        "cleanup",
    }
    if set(result) != expected_keys:
        raise ValueError("business_query_plan_live.result_shape_invalid")
    if (
        result["schemaVersion"] != 1
        or result["workPackage"] != WORK_PACKAGE
        or result["runId"] != RUN_ID
        or result["authorizationReference"] != AUTHORIZATION_REFERENCE
        or not _is_sha256(result["manifestSha256"])
        or result["status"] not in _TERMINAL_STATUSES
        or type(result["reason"]) is not str
    ):
        raise ValueError("business_query_plan_live.result_binding_invalid")
    status = cast(str, result["status"])
    raw_cases = result["cases"]
    if not isinstance(raw_cases, Sequence) or isinstance(raw_cases, (str, bytes, bytearray)):
        raise ValueError("business_query_plan_live.result_cases_invalid")
    cases = tuple(raw_cases)
    case_ids = tuple(_result_case_id(item) for item in cases)
    if case_ids != CASE_IDS[: len(case_ids)] or (status == "passed" and case_ids != CASE_IDS):
        raise ValueError("business_query_plan_live.result_cases_invalid")
    for case in cases:
        item = _exact_mapping(
            case,
            {"caseId", "domain", "status", "capabilityId", "planCalls", "domainCalls"},
        )
        case_id = cast(str, item["caseId"])
        if (
            item["domain"] != _CASE_DOMAINS[case_id]
            or item["status"] not in _CASE_STATUSES[case_id]
            or item["capabilityId"] != _CASE_CAPABILITIES[case_id]
            or item["planCalls"] != 1
            or item["domainCalls"] != _CASE_DOMAIN_CALLS[case_id]
        ):
            raise ValueError("business_query_plan_live.result_case_invalid")
    counts = _exact_mapping(
        result["counts"],
        {
            "modelCalls",
            "employeeDetail",
            "transactionSearch",
            "otherBusinessEndpoints",
            "fallbackSelector",
            "answerGeneration",
            "knowledge",
            "retry",
            "resume",
        },
    )
    expected_counts = {
        "modelCalls": MODEL_CALL_BUDGET,
        "employeeDetail": EMPLOYEE_DETAIL_BUDGET,
        "transactionSearch": TRANSACTION_SEARCH_BUDGET,
        "otherBusinessEndpoints": 0,
        "fallbackSelector": 0,
        "answerGeneration": 0,
        "knowledge": 0,
        "retry": 0,
        "resume": 0,
    }
    security = _exact_mapping(result["security"], {"forbiddenFields", "sensitivePersistence", "logLeakCount"})
    cleanup = _exact_mapping(result["cleanup"], {"runtimeClosed", "modelClientClosed", "domainClientsClosed"})
    if any(type(item) is not int or item < 0 for item in counts.values()):
        raise ValueError("business_query_plan_live.result_counts_invalid")
    if (
        cast(int, counts["modelCalls"]) > MODEL_CALL_BUDGET
        or cast(int, counts["employeeDetail"]) > EMPLOYEE_DETAIL_BUDGET
        or cast(int, counts["transactionSearch"]) > TRANSACTION_SEARCH_BUDGET
        or cast(int, counts["otherBusinessEndpoints"]) > 1
        or cast(int, counts["fallbackSelector"]) > 1
        or cast(int, counts["answerGeneration"]) > 1
        or cast(int, counts["knowledge"]) > 1
        or cast(int, counts["retry"]) != 0
        or cast(int, counts["resume"]) != 0
    ):
        raise ValueError("business_query_plan_live.result_counts_invalid")
    if (
        type(security["forbiddenFields"]) is not int
        or security["forbiddenFields"] < 0
        or type(security["logLeakCount"]) is not int
        or security["logLeakCount"] < 0
        or type(security["sensitivePersistence"]) is not bool
        or any(type(item) is not bool for item in cleanup.values())
    ):
        raise ValueError("business_query_plan_live.result_security_invalid")
    passed = (
        status == "passed"
        and result["reason"] == "business_query_plan_live.passed"
        and counts == expected_counts
        and security == {"forbiddenFields": 0, "sensitivePersistence": False, "logLeakCount": 0}
        and cleanup == {"runtimeClosed": True, "modelClientClosed": True, "domainClientsClosed": True}
    )
    if require_passed and not passed:
        raise ValueError("business_query_plan_live.result_not_passed")
    if status == "passed" and not passed:
        raise ValueError("business_query_plan_live.result_false_positive")
    return result


def validate_lifecycle(value: object, *, manifest_sha256: str) -> None:
    item = _exact_mapping(
        value,
        {"schemaVersion", "runId", "authorizationReference", "manifestSha256", "event"},
    )
    if item != {
        "schemaVersion": 1,
        "runId": RUN_ID,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "manifestSha256": manifest_sha256,
        "event": "run_started",
    }:
        raise ValueError("business_query_plan_live.lifecycle_invalid")


def validate_consumed(value: object, *, manifest_sha256: str) -> None:
    item = _exact_mapping(
        value,
        {"schemaVersion", "runId", "authorizationReference", "manifestSha256", "event"},
    )
    if item != {
        "schemaVersion": 1,
        "runId": RUN_ID,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "manifestSha256": manifest_sha256,
        "event": "first_model_outbound",
    }:
        raise ValueError("business_query_plan_live.consumed_invalid")


def validate_attempt_journal(value: object, *, expected_calls: int) -> None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError("business_query_plan_live.journal_invalid")
    if len(value) != expected_calls or not 0 <= expected_calls <= MODEL_CALL_BUDGET:
        raise ValueError("business_query_plan_live.journal_invalid")
    for ordinal, raw in enumerate(value, start=1):
        item = _exact_mapping(raw, {"caseId", "modelCall", "terminal"})
        if (
            item["caseId"] != CASE_IDS[ordinal - 1]
            or item["modelCall"] != ordinal
            or item["terminal"] not in {"completed", "failed"}
        ):
            raise ValueError("business_query_plan_live.journal_invalid")


def _case_id(value: object) -> str:
    item = _exact_mapping(value, {"caseId", "domain", "principal", "questionTemplate", "expectedStatus", "expectedCapabilityId"})
    case_id = item.get("caseId")
    if type(case_id) is not str or case_id not in CASE_IDS:
        raise ValueError("business_query_plan_live.case_invalid")
    return case_id


def _result_case_id(value: object) -> str:
    item = _exact_mapping(
        value,
        {"caseId", "domain", "status", "capabilityId", "planCalls", "domainCalls"},
    )
    case_id = item.get("caseId")
    if type(case_id) is not str or case_id not in CASE_IDS:
        raise ValueError("business_query_plan_live.case_invalid")
    return case_id


def _exact_mapping(value: object, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys or any(type(key) is not str for key in value):
        raise ValueError("business_query_plan_live.object_shape_invalid")
    return {cast(str, key): item for key, item in value.items()}


def _exact_sequence(value: object, minimum: int) -> tuple[object, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)) or len(value) < minimum:
        raise ValueError("business_query_plan_live.array_shape_invalid")
    if minimum == len(CASE_IDS) and len(value) != minimum:
        raise ValueError("business_query_plan_live.array_shape_invalid")
    return tuple(value)


def _is_sha256(value: object) -> bool:
    return type(value) is str and len(value) == 64 and set(value) <= _SHA256


def _is_git_sha(value: object) -> bool:
    return type(value) is str and len(value) == 40 and set(value) <= _SHA256
