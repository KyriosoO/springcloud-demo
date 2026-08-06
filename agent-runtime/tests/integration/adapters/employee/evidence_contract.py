from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

_MATRIX = {
    "adminPrimary": "allowed",
    "adminSecondary": "allowed",
    "viewer": "allowed",
    "unknownRole": "forbidden",
    "missingToken": "unauthenticated",
    "malformedToken": "unauthenticated",
    "serviceToken": "unauthenticated",
}
_PROBE_COUNTS = {
    "employee": 7,
    "adapter": 6,
    "otherEmployeeEndpoints": 0,
    "model": 0,
}
_FINAL_COUNTS = {
    **_PROBE_COUNTS,
    "serviceDetail": 3,
    "mapperSelectByIdCardNo": 3,
    "otherServiceMethods": 0,
}
_FINAL_KEYS = {
    "schemaVersion",
    "workPackage",
    "status",
    "startedAtUtc",
    "completedAtUtc",
    "durationMs",
    "authorizationMatrix",
    "requestCounts",
    "responseVisibility",
    "logSafety",
    "runtimeIsolation",
}
_GATEWAY_COUNTS = {
    "gateway": 1,
    "servlet": 1,
    "serviceDetail": 1,
    "mapperSelectByIdCardNo": 1,
    "otherServiceMethods": 0,
}
_GATEWAY_KEYS = {
    "schemaVersion",
    "workPackage",
    "validation",
    "status",
    "startedAtUtc",
    "completedAtUtc",
    "durationMs",
    "requestCounts",
    "responseStatus",
    "logSafety",
    "runtimeIsolation",
}


def _invalid() -> NoReturn:
    raise ValueError("employee.live_evidence_invalid")


def _exact_object(value: object, expected_keys: set[str]) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected_keys:
        _invalid()
    return value


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        _invalid()
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        _invalid()
    if parsed.tzinfo is None:
        _invalid()
    return parsed


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _invalid()
        result[key] = value
    return result


def load_strict_json(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    if not raw or len(raw) > 16_384 or raw.startswith(b"\xef\xbb\xbf"):
        _invalid()
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError):
        _invalid()
    if type(value) is not dict:
        _invalid()
    return value


def validate_probe_evidence(value: object) -> dict[str, object]:
    probe = _exact_object(
        value,
        {"schemaVersion", "authorizationMatrix", "requestCounts", "responseVisibility"},
    )
    if probe["schemaVersion"] != 1 or probe["responseVisibility"] != "validated_by_employee_adapter_and_fixture":
        _invalid()
    if _exact_object(probe["authorizationMatrix"], set(_MATRIX)) != _MATRIX:
        _invalid()
    if _exact_object(probe["requestCounts"], set(_PROBE_COUNTS)) != _PROBE_COUNTS:
        _invalid()
    return probe


def validate_final_evidence(value: object) -> dict[str, object]:
    evidence = _exact_object(value, _FINAL_KEYS)
    if (
        evidence["schemaVersion"] != 1
        or evidence["workPackage"] != "WP-EMP-REAL-01"
        or evidence["status"] != "passed"
        or evidence["responseVisibility"] != "validated_by_employee_adapter_and_fixture"
    ):
        _invalid()
    started = _timestamp(evidence["startedAtUtc"])
    completed = _timestamp(evidence["completedAtUtc"])
    duration = evidence["durationMs"]
    if type(duration) is not int or duration < 0 or completed < started:
        _invalid()
    if _exact_object(evidence["authorizationMatrix"], set(_MATRIX)) != _MATRIX:
        _invalid()
    if _exact_object(evidence["requestCounts"], set(_FINAL_COUNTS)) != _FINAL_COUNTS:
        _invalid()
    if _exact_object(
        evidence["logSafety"],
        {"logLeakCount", "rawLogsDeleted", "identifierPersisted", "jwtPersisted", "hmacKeyPersisted"},
    ) != {
        "logLeakCount": 0,
        "rawLogsDeleted": True,
        "identifierPersisted": False,
        "jwtPersisted": False,
        "hmacKeyPersisted": False,
    }:
        _invalid()
    if _exact_object(
        evidence["runtimeIsolation"],
        {"authService", "employeeService", "gatewayStarted", "esCalled", "workflowCalled", "deepSeekCalled"},
    ) != {
        "authService": "isolated_local",
        "employeeService": "spring_boot_test",
        "gatewayStarted": False,
        "esCalled": False,
        "workflowCalled": False,
        "deepSeekCalled": False,
    }:
        _invalid()
    return evidence


def validate_gateway_log_evidence(value: object) -> dict[str, object]:
    evidence = _exact_object(value, _GATEWAY_KEYS)
    if (
        evidence["schemaVersion"] != 1
        or evidence["workPackage"] != "WP-EMP-REAL-01"
        or evidence["validation"] != "VAL-EMP-005"
        or evidence["status"] != "passed"
        or evidence["responseStatus"] != 400
    ):
        _invalid()
    started = _timestamp(evidence["startedAtUtc"])
    completed = _timestamp(evidence["completedAtUtc"])
    duration = evidence["durationMs"]
    if type(duration) is not int or duration < 0 or completed < started:
        _invalid()
    if _exact_object(evidence["requestCounts"], set(_GATEWAY_COUNTS)) != _GATEWAY_COUNTS:
        _invalid()
    if _exact_object(
        evidence["logSafety"],
        {
            "logLeakCount",
            "rawLogsDeleted",
            "sentinelPersisted",
            "jwtPersisted",
            "hmacKeyPersisted",
            "fullPathPersisted",
        },
    ) != {
        "logLeakCount": 0,
        "rawLogsDeleted": True,
        "sentinelPersisted": False,
        "jwtPersisted": False,
        "hmacKeyPersisted": False,
        "fullPathPersisted": False,
    }:
        _invalid()
    if _exact_object(
        evidence["runtimeIsolation"],
        {
            "gatewayService",
            "employeeService",
            "permanentEmployeeRoute",
            "realEmployeeIdentifierUsed",
            "deepSeekCalled",
        },
    ) != {
        "gatewayService": "actual_jar_test_route",
        "employeeService": "spring_boot_test_servlet",
        "permanentEmployeeRoute": False,
        "realEmployeeIdentifierUsed": False,
        "deepSeekCalled": False,
    }:
        _invalid()
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    evidence = load_strict_json(args.path)
    if evidence.get("validation") == "VAL-EMP-005":
        validate_gateway_log_evidence(evidence)
    else:
        validate_final_evidence(evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
