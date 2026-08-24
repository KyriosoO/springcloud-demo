from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path


_COUNT_KEYS = {
    "queryPlanModel",
    "otherModelTasks",
    "employee",
    "transaction",
    "otherBusinessEndpoints",
    "fallbackSelector",
    "answerGeneration",
    "externalModelOutbound",
}
_EXPECTED_CASES = {
    "bq-nonlive-cross": ("unsupported", None),
    "bq-nonlive-emp-deny": ("forbidden", "employee.detail"),
    "bq-nonlive-emp-ok": ("success", "employee.detail"),
    "bq-nonlive-invalid": ("invalid_argument", None),
    "bq-nonlive-second": ("invalid_argument", None),
    "bq-nonlive-sensitive": ("forbidden", None),
    "bq-nonlive-timeout": ("timeout", None),
    "bq-nonlive-txn-deny": ("forbidden", "transaction.search"),
    "bq-nonlive-txn-ok": ("success", "transaction.search"),
    "bq-nonlive-unsupported": ("unsupported", None),
}
_EXPECTED_COUNTS = {
    "queryPlanModel": 9,
    "otherModelTasks": 0,
    "employee": 2,
    "transaction": 2,
    "otherBusinessEndpoints": 0,
    "fallbackSelector": 0,
    "answerGeneration": 0,
    "externalModelOutbound": 0,
}


def write_business_query_plan_evidence(
    path: Path,
    *,
    cases: Mapping[str, tuple[str, str | None]],
    request_counts: Mapping[str, int],
    runtime_closed: bool,
) -> None:
    passed = (
        runtime_closed
        and dict(cases) == _EXPECTED_CASES
        and dict(request_counts) == _EXPECTED_COUNTS
    )
    value: dict[str, object] = {
        "schemaVersion": 1,
        "workPackage": "WP-BQ-QUERYPLAN-NONLIVE-E2E-01",
        "status": "passed" if passed else "failed",
        "providers": {"model": "fake", "employee": "fake", "transaction": "fake"},
        "cases": [
            {"caseId": case_id, "status": status, "capabilityId": capability_id}
            for case_id, (status, capability_id) in sorted(cases.items())
        ],
        "requestCounts": dict(request_counts),
        "security": {"sensitivePersistence": False, "logLeakCount": 0},
        "cleanup": {"runtimeClosed": runtime_closed},
    }
    validate_business_query_plan_evidence(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary.replace(path)


def validate_business_query_plan_evidence(value: object) -> None:
    if type(value) is not dict or set(value) != {
        "schemaVersion",
        "workPackage",
        "status",
        "providers",
        "cases",
        "requestCounts",
        "security",
        "cleanup",
    }:
        raise ValueError("business_query_plan_e2e.evidence_shape_invalid")
    if (
        value["schemaVersion"] != 1
        or value["workPackage"] != "WP-BQ-QUERYPLAN-NONLIVE-E2E-01"
        or value["status"] not in {"passed", "failed"}
        or value["providers"] != {"model": "fake", "employee": "fake", "transaction": "fake"}
    ):
        raise ValueError("business_query_plan_e2e.evidence_identity_invalid")
    cases = value["cases"]
    if type(cases) is not list:
        raise ValueError("business_query_plan_e2e.evidence_cases_invalid")
    seen: set[str] = set()
    for item in cases:
        if type(item) is not dict or set(item) != {"caseId", "status", "capabilityId"}:
            raise ValueError("business_query_plan_e2e.evidence_cases_invalid")
        case_id = item["caseId"]
        capability_id = item["capabilityId"]
        if (
            type(case_id) is not str
            or case_id in seen
            or type(item["status"]) is not str
            or (capability_id is not None and type(capability_id) is not str)
        ):
            raise ValueError("business_query_plan_e2e.evidence_cases_invalid")
        seen.add(case_id)
    counts = value["requestCounts"]
    if (
        type(counts) is not dict
        or set(counts) != _COUNT_KEYS
        or any(type(item) is not int or item < 0 for item in counts.values())
    ):
        raise ValueError("business_query_plan_e2e.evidence_counts_invalid")
    if value["security"] != {"sensitivePersistence": False, "logLeakCount": 0}:
        raise ValueError("business_query_plan_e2e.evidence_security_invalid")
    cleanup = value["cleanup"]
    if type(cleanup) is not dict or set(cleanup) != {"runtimeClosed"} or type(cleanup["runtimeClosed"]) is not bool:
        raise ValueError("business_query_plan_e2e.evidence_cleanup_invalid")
    if value["status"] == "passed":
        actual_cases = {
            item["caseId"]: (item["status"], item["capabilityId"])
            for item in cases
        }
        if actual_cases != _EXPECTED_CASES or counts != _EXPECTED_COUNTS or not cleanup["runtimeClosed"]:
            raise ValueError("business_query_plan_e2e.evidence_pass_invariant_invalid")
