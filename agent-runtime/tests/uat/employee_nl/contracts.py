from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.model.deepseek.business_query_plan_v5 import (
    BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION,
    BUSINESS_QUERY_PLAN_TASK_VERSION,
)


RUN_ID: Final = "employee-natural-language-v1-20260828-candidate-02"
AUTHORIZATION_REFERENCE: Final = "P3_00:GATE-082"
WORK_PACKAGE: Final = "WP-EMP-NL-UAT-10"
MODEL_CALL_BUDGET: Final = 29
EMPLOYEE_SEARCH_BUDGET: Final = 30
CASE_COUNT: Final = 15
_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_GIT_SHA: Final = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeNaturalLanguageCase:
    case_id: str
    input_class: str
    question: str
    principal: str
    expected_statuses: tuple[CapabilityStatus, ...]
    expected_action: str | None
    expected_fields: tuple[str, ...] = ()
    expected_operators: tuple[str, ...] = ()
    expected_value_shapes: tuple[str, ...] = ()
    expected_model_calls: int = 1
    expected_employee_calls: int = 1
    minimum_rows: int = 0


def cases() -> tuple[EmployeeNaturalLanguageCase, ...]:
    list_statuses = (CapabilityStatus.SUCCESS, CapabilityStatus.NO_RESULT)
    return (
        EmployeeNaturalLanguageCase(case_id="UAT-EMP-NL-301", input_class="single_surname_prefix", question="姓杨的员工", principal="admin", expected_statuses=list_statuses, expected_action="employee.search", expected_fields=("chinese_name",), expected_operators=("prefix",), expected_value_shapes=("value_ref",)),
        EmployeeNaturalLanguageCase(case_id="UAT-EMP-NL-302", input_class="compound_surname_prefix", question="欧阳姓员工", principal="admin", expected_statuses=list_statuses, expected_action="employee.search", expected_fields=("chinese_name",), expected_operators=("prefix",), expected_value_shapes=("value_ref",)),
        EmployeeNaturalLanguageCase(case_id="UAT-EMP-NL-303", input_class="multiple_surnames_prefix_any", question="查询姓杨或姓王的员工", principal="admin", expected_statuses=list_statuses, expected_action="employee.search", expected_fields=("chinese_name",), expected_operators=("prefix_any",), expected_value_shapes=("value_refs",)),
        EmployeeNaturalLanguageCase(case_id="UAT-EMP-NL-304", input_class="multiple_full_names_in", question="查询姓名为杨明或王芳的员工", principal="admin", expected_statuses=list_statuses, expected_action="employee.search", expected_fields=("chinese_name",), expected_operators=("in",), expected_value_shapes=("value_refs",)),
        EmployeeNaturalLanguageCase(case_id="UAT-EMP-NL-305", input_class="surname_and_name_fragment", question="查询姓杨且姓名中包含明的员工", principal="admin", expected_statuses=list_statuses, expected_action="employee.search", expected_fields=("chinese_name", "chinese_name"), expected_operators=("prefix", "contains"), expected_value_shapes=("value_ref", "value_ref")),
        EmployeeNaturalLanguageCase(case_id="UAT-EMP-NL-306", input_class="region_preposition", question="查询在上海的员工", principal="admin", expected_statuses=(CapabilityStatus.SUCCESS,), expected_action="employee.search", expected_fields=("contact_address",), expected_operators=("contains",), expected_value_shapes=("literal",), minimum_rows=1),
        EmployeeNaturalLanguageCase(case_id="UAT-EMP-NL-307", input_class="region_area_alias", question="查询上海地区的员工", principal="admin", expected_statuses=list_statuses, expected_action="employee.search", expected_fields=("contact_address",), expected_operators=("contains",), expected_value_shapes=("literal",)),
        EmployeeNaturalLanguageCase(case_id="UAT-EMP-NL-308", input_class="province_suffix_alias", question="查询江苏省的员工", principal="admin", expected_statuses=list_statuses, expected_action="employee.search", expected_fields=("contact_address",), expected_operators=("contains",), expected_value_shapes=("literal",)),
        EmployeeNaturalLanguageCase(case_id="UAT-EMP-NL-309", input_class="province_short_alias", question="查询浙江的员工", principal="admin", expected_statuses=list_statuses, expected_action="employee.search", expected_fields=("contact_address",), expected_operators=("contains",), expected_value_shapes=("literal",)),
        EmployeeNaturalLanguageCase(case_id="UAT-EMP-NL-310", input_class="multiple_regions_contains_any", question="查询江苏、浙江或上海的员工", principal="admin", expected_statuses=list_statuses, expected_action="employee.search", expected_fields=("contact_address",), expected_operators=("contains_any",), expected_value_shapes=("literal_list",)),
        EmployeeNaturalLanguageCase(case_id="UAT-EMP-NL-311", input_class="implicit_employee_question", question="是否有姓杨的", principal="admin", expected_statuses=list_statuses, expected_action="employee.search", expected_fields=("chinese_name",), expected_operators=("prefix",), expected_value_shapes=("value_ref",)),
        EmployeeNaturalLanguageCase(case_id="UAT-EMP-NL-312", input_class="imperative_variant", question="请查一下杨姓员工", principal="admin", expected_statuses=list_statuses, expected_action="employee.search", expected_fields=("chinese_name",), expected_operators=("prefix",), expected_value_shapes=("value_ref",)),
        EmployeeNaturalLanguageCase(case_id="UAT-EMP-NL-313", input_class="endpoint_authorization_denied", question="查询在上海的员工", principal="denied", expected_statuses=(CapabilityStatus.FORBIDDEN,), expected_action="employee.search", expected_fields=("contact_address",), expected_operators=("contains",), expected_value_shapes=("literal",)),
        EmployeeNaturalLanguageCase(case_id="UAT-EMP-NL-314", input_class="unconfigured_workbase", question="查询员工的workBaseSi等于上海", principal="admin", expected_statuses=(CapabilityStatus.UNSUPPORTED, CapabilityStatus.INVALID_ARGUMENT), expected_action=None, expected_model_calls=1, expected_employee_calls=0),
        EmployeeNaturalLanguageCase(case_id="UAT-EMP-NL-315", input_class="protected_value_limit", question="查询姓赵、姓钱、姓孙、姓李、姓周、姓吴、姓郑、姓王、姓冯、姓陈、姓褚、姓卫、姓蒋、姓沈、姓韩、姓杨或姓朱的员工", principal="admin", expected_statuses=(CapabilityStatus.INVALID_ARGUMENT,), expected_action=None, expected_model_calls=0, expected_employee_calls=0),
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prompt_sha256() -> str:
    return hashlib.sha256(
        BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION.encode("utf-8")
    ).hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def write_exclusive_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical_json_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def append_json_line(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "ab") as stream:
        stream.write(canonical_json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())


def validate_manifest(value: object, *, repository: Path) -> dict[str, object]:
    manifest = _exact_mapping(
        value,
        {
            "schemaVersion", "state", "workPackage", "runId",
            "authorizationReference", "sourceHead", "model", "task",
            "configuration", "cases", "budgets", "assets", "constraints",
        },
    )
    if (
        manifest["schemaVersion"] != 1
        or manifest["state"] != "prepared_unconsumed"
        or manifest["workPackage"] != WORK_PACKAGE
        or manifest["runId"] != RUN_ID
        or manifest["authorizationReference"] != AUTHORIZATION_REFERENCE
        or not _is_git_sha(manifest["sourceHead"])
    ):
        raise ValueError("employee_nl_uat.manifest_binding_invalid")
    model = _exact_mapping(manifest["model"], {"provider", "name", "requestMode"})
    if model != {
        "provider": "deepseek",
        "name": "deepseek-v4-pro",
        "requestMode": "json_object_no_tools",
    }:
        raise ValueError("employee_nl_uat.manifest_model_invalid")
    task = _exact_mapping(manifest["task"], {"id", "version", "promptSha256"})
    if task != {
        "id": "business_query_plan",
        "version": BUSINESS_QUERY_PLAN_TASK_VERSION,
        "promptSha256": prompt_sha256(),
    }:
        raise ValueError("employee_nl_uat.manifest_task_invalid")
    configuration = _exact_mapping(
        manifest["configuration"],
        {"contractVersion", "snapshotId", "fileSha256", "employeeBaseUrl"},
    )
    if (
        configuration.get("contractVersion") != 3
        or not _is_sha256(configuration.get("snapshotId"))
        or not _is_sha256(configuration.get("fileSha256"))
        or configuration.get("employeeBaseUrl") != "http://127.0.0.1:19210"
    ):
        raise ValueError("employee_nl_uat.manifest_configuration_invalid")
    configured_cases = _exact_sequence(manifest["cases"], CASE_COUNT)
    expected_cases = tuple(
        {
            "caseId": case.case_id,
            "inputClass": case.input_class,
            "principal": case.principal,
            "expectedAction": case.expected_action,
            "expectedModelCalls": case.expected_model_calls,
            "expectedEmployeeSearchCalls": case.expected_employee_calls,
        }
        for case in cases()
    )
    if configured_cases != expected_cases:
        raise ValueError("employee_nl_uat.manifest_cases_invalid")
    budgets = _exact_mapping(
        manifest["budgets"],
        {
            "maximumModelCalls", "maximumEmployeeSearchCalls", "employeeSemantic",
            "transaction", "knowledge", "answer", "otherEmployeeEndpoints",
            "retry", "resume",
        },
    )
    if budgets != {
        "maximumModelCalls": MODEL_CALL_BUDGET,
        "maximumEmployeeSearchCalls": EMPLOYEE_SEARCH_BUDGET,
        "employeeSemantic": 0,
        "transaction": 0,
        "knowledge": 0,
        "answer": 0,
        "otherEmployeeEndpoints": 0,
        "retry": 0,
        "resume": 0,
    }:
        raise ValueError("employee_nl_uat.manifest_budget_invalid")
    assets = _exact_sequence(manifest["assets"], minimum=1)
    seen_paths: set[str] = set()
    for raw in assets:
        asset = _exact_mapping(raw, {"path", "sha256"})
        relative = asset.get("path")
        if (
            type(relative) is not str
            or not relative
            or relative in seen_paths
            or "\\" in relative
            or relative.startswith("/")
            or ":" in relative
            or ".." in relative.split("/")
            or not _is_sha256(asset.get("sha256"))
        ):
            raise ValueError("employee_nl_uat.manifest_asset_invalid")
        seen_paths.add(relative)
        path = repository / relative
        if not path.is_file() or sha256_file(path) != asset["sha256"]:
            raise ValueError("employee_nl_uat.manifest_asset_hash_invalid")
    constraints = _exact_mapping(
        manifest["constraints"],
        {
            "firstModelOutboundConsumes", "noRetry", "noResume", "singleAction",
            "noFallback", "noAnswer", "noKnowledge", "noSemantic",
            "noTransaction", "noRawPersistence", "historicalAssetsImmutable",
        },
    )
    if set(constraints.values()) != {True}:
        raise ValueError("employee_nl_uat.manifest_constraints_invalid")
    return manifest


def validate_authorization(
    value: object, *, manifest_sha256: str, frozen_head: str
) -> dict[str, object]:
    authorization = _exact_mapping(
        value,
        {
            "schemaVersion", "state", "liveExecutionAuthorized", "singleUse",
            "runId", "authorizationReference", "frozenHead", "manifestSha256",
            "maximumModelCalls", "maximumEmployeeSearchCalls", "constraints",
        },
    )
    if (
        authorization["schemaVersion"] != 1
        or authorization["state"] != "authorized_unconsumed"
        or authorization["liveExecutionAuthorized"] is not True
        or authorization["singleUse"] is not True
        or authorization["runId"] != RUN_ID
        or authorization["authorizationReference"] != AUTHORIZATION_REFERENCE
        or authorization["frozenHead"] != frozen_head
        or authorization["manifestSha256"] != manifest_sha256
        or authorization["maximumModelCalls"] != MODEL_CALL_BUDGET
        or authorization["maximumEmployeeSearchCalls"] != EMPLOYEE_SEARCH_BUDGET
    ):
        raise ValueError("employee_nl_uat.authorization_binding_invalid")
    constraints = _exact_mapping(
        authorization["constraints"],
        {"noRetry", "noResume", "noRawPersistence", "noOtherEndpoints"},
    )
    if set(constraints.values()) != {True}:
        raise ValueError("employee_nl_uat.authorization_constraints_invalid")
    return authorization


def validate_result(value: object) -> dict[str, object]:
    result = _exact_mapping(
        value,
        {
            "schemaVersion", "status", "runId", "authorizationReference",
            "frozenHead", "manifestSha256", "cases", "counts", "security",
            "cleanup", "failureReason",
        },
    )
    if (
        result["schemaVersion"] != 1
        or result["status"] not in {"passed", "failed_unconsumed", "failed_consumed"}
        or result["runId"] != RUN_ID
        or result["authorizationReference"] != AUTHORIZATION_REFERENCE
        or not _is_git_sha(result["frozenHead"])
        or not _is_sha256(result["manifestSha256"])
    ):
        raise ValueError("employee_nl_uat.result_binding_invalid")
    result_cases = _exact_sequence(result["cases"], minimum=0)
    if len(result_cases) > CASE_COUNT:
        raise ValueError("employee_nl_uat.result_cases_invalid")
    seen: set[str] = set()
    validated_cases: list[dict[str, object]] = []
    recorded_model_calls = 0
    recorded_employee_calls = 0
    for raw in result_cases:
        item = _exact_mapping(
            raw,
            {
                "caseId", "inputClass", "status", "capabilityId", "fields",
                "operators", "valueShapes", "modelCalls", "employeeSearchCalls",
                "rowCount", "securityPassed", "passed",
            },
        )
        case_id = item.get("caseId")
        model_calls = item.get("modelCalls")
        employee_calls = item.get("employeeSearchCalls")
        row_count = item.get("rowCount")
        if (
            type(case_id) is not str
            or case_id in seen
            or case_id not in {case.case_id for case in cases()}
            or type(model_calls) is not int
            or model_calls not in {0, 1}
            or type(employee_calls) is not int
            or employee_calls not in {0, 1}
            or type(row_count) is not int
            or row_count < 0
            or type(item.get("securityPassed")) is not bool
            or type(item.get("passed")) is not bool
        ):
            raise ValueError("employee_nl_uat.result_case_invalid")
        seen.add(case_id)
        recorded_model_calls += model_calls
        recorded_employee_calls += employee_calls
        validated_cases.append(item)
    counts = _exact_mapping(
        result["counts"],
        {
            "modelCalls", "employeeSearchCalls", "employeeSemantic", "transaction",
            "knowledge", "answer", "otherEmployeeEndpoints", "retry", "resume",
        },
    )
    model_total = counts.get("modelCalls")
    employee_total = counts.get("employeeSearchCalls")
    if (
        any(type(item) is not int or item < 0 for item in counts.values())
        or type(model_total) is not int
        or model_total > MODEL_CALL_BUDGET
        or type(employee_total) is not int
        or employee_total > EMPLOYEE_SEARCH_BUDGET
        or any(
            counts[name] != 0
            for name in (
                "employeeSemantic", "transaction", "knowledge", "answer",
                "otherEmployeeEndpoints", "retry", "resume",
            )
        )
        or model_total != recorded_model_calls
        or employee_total != recorded_employee_calls
    ):
        raise ValueError("employee_nl_uat.result_counts_invalid")
    security = _exact_mapping(
        result["security"],
        {"forbiddenPlanValues", "forbiddenPersistence", "logLeakCount"},
    )
    cleanup = _exact_mapping(
        result["cleanup"], {"runtimeClosed", "modelClosed", "domainClientClosed"}
    )
    if any(type(item) is not int or item < 0 for item in security.values()):
        raise ValueError("employee_nl_uat.result_security_invalid")
    if result["status"] == "passed" and (
        len(result_cases) != CASE_COUNT
        or any(item["passed"] is not True for item in validated_cases)
        or any(item["securityPassed"] is not True for item in validated_cases)
        or set(security.values()) != {0}
        or set(cleanup.values()) != {True}
        or result["failureReason"] is not None
    ):
        raise ValueError("employee_nl_uat.result_terminal_invalid")
    return result


def current_head(repository: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    head = completed.stdout.strip()
    if not _is_git_sha(head):
        raise ValueError("employee_nl_uat.git_head_invalid")
    return head


def _exact_mapping(value: object, keys: set[str]) -> dict[str, object]:
    if type(value) is not dict or set(cast(dict[str, object], value)) != keys:
        raise ValueError("employee_nl_uat.schema_invalid")
    return cast(dict[str, object], value)


def _exact_sequence(value: object, length: int | None = None, *, minimum: int = 0) -> tuple[object, ...]:
    if type(value) is not list:
        raise ValueError("employee_nl_uat.schema_invalid")
    items = tuple(cast(list[object], value))
    if (length is not None and len(items) != length) or len(items) < minimum:
        raise ValueError("employee_nl_uat.schema_invalid")
    return items


def _is_sha256(value: object) -> bool:
    return type(value) is str and _SHA256.fullmatch(value) is not None


def _is_git_sha(value: object) -> bool:
    return type(value) is str and _GIT_SHA.fullmatch(value) is not None
