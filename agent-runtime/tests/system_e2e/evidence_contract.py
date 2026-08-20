from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path


_EXPECTED_CASES = {
    "system-k-admin": ("success", "knowledge.query"),
    "system-k-deny": ("forbidden", "knowledge.query"),
    "system-emp-admin": ("success", "employee.detail"),
    "system-emp-deny": ("forbidden", "employee.detail"),
    "system-txn-admin": ("no_result", "transaction.search"),
    "system-txn-deny": ("forbidden", "transaction.search"),
    "system-invalid": ("invalid_argument", None),
}
_COUNT_KEYS = {
    "knowledgeSearch",
    "embedding",
    "rerank",
    "employee",
    "transaction",
    "otherBusinessEndpoints",
    "localKnowledgeModel",
    "answerGeneration",
    "externalModelOutbound",
}


def runtime_evidence(
    *,
    cases: Mapping[str, tuple[str, str | None]],
    request_counts: Mapping[str, int],
    runtime_closed: bool = True,
) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "workPackage": "WP-SYSTEM-E2E-01",
        "status": "runtime_closed",
        "failureCode": None,
        "providers": {
            "knowledge": "real",
            "employee": "real",
            "transaction": "real",
            "model": "stub",
        },
        "cases": [
            {"caseId": key, "status": status, "capabilityId": capability_id}
            for key, (status, capability_id) in sorted(cases.items())
        ],
        "requestCounts": dict(request_counts),
        "security": {"logLeakCount": 0, "sensitivePersistence": False},
        "cleanup": {
            "runtimeClosed": runtime_closed,
            "ownedProcessesStopped": False,
            "rawLogsDeleted": False,
        },
    }


def write_runtime_evidence(
    path: Path,
    *,
    cases: Mapping[str, tuple[str, str | None]],
    request_counts: Mapping[str, int],
    runtime_closed: bool = True,
) -> None:
    value = runtime_evidence(
        cases=cases,
        request_counts=request_counts,
        runtime_closed=runtime_closed,
    )
    validate_system_e2e_evidence(value, final=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    temporary.replace(path)


def validate_system_e2e_evidence(value: object, *, final: bool) -> None:
    if type(value) is not dict or set(value) != {
        "schemaVersion",
        "workPackage",
        "status",
        "failureCode",
        "providers",
        "cases",
        "requestCounts",
        "security",
        "cleanup",
    }:
        raise ValueError("system_e2e.evidence_shape_invalid")
    if value["schemaVersion"] != 1 or value["workPackage"] != "WP-SYSTEM-E2E-01":
        raise ValueError("system_e2e.evidence_identity_invalid")
    if value["status"] not in {"runtime_closed", "passed", "failed"}:
        raise ValueError("system_e2e.evidence_status_invalid")
    if value["failureCode"] is not None and (
        type(value["failureCode"]) is not str or not str(value["failureCode"]).startswith("system_e2e.")
    ):
        raise ValueError("system_e2e.evidence_failure_invalid")
    providers = value["providers"]
    if providers != {"knowledge": "real", "employee": "real", "transaction": "real", "model": "stub"}:
        raise ValueError("system_e2e.evidence_provider_invalid")
    cases = value["cases"]
    if type(cases) is not list:
        raise ValueError("system_e2e.evidence_cases_invalid")
    observed: dict[str, tuple[str, str | None]] = {}
    for item in cases:
        if type(item) is not dict or set(item) != {"caseId", "status", "capabilityId"}:
            raise ValueError("system_e2e.evidence_cases_invalid")
        case_id = item["caseId"]
        if type(case_id) is not str or case_id in observed:
            raise ValueError("system_e2e.evidence_cases_invalid")
        status = item["status"]
        capability_id = item["capabilityId"]
        if type(status) is not str or (capability_id is not None and type(capability_id) is not str):
            raise ValueError("system_e2e.evidence_cases_invalid")
        observed[case_id] = (status, capability_id)
    counts = value["requestCounts"]
    if type(counts) is not dict or set(counts) != _COUNT_KEYS or any(type(item) is not int or item < 0 for item in counts.values()):
        raise ValueError("system_e2e.evidence_counts_invalid")
    security = value["security"]
    cleanup = value["cleanup"]
    if (
        type(security) is not dict
        or set(security) != {"logLeakCount", "sensitivePersistence"}
        or type(security["logLeakCount"]) is not int
        or type(security["sensitivePersistence"]) is not bool
        or type(cleanup) is not dict
        or set(cleanup) != {"runtimeClosed", "ownedProcessesStopped", "rawLogsDeleted"}
        or any(type(cleanup[key]) is not bool for key in cleanup)
    ):
        raise ValueError("system_e2e.evidence_safety_invalid")
    if final:
        if value["status"] != "passed" or value["failureCode"] is not None or observed != _EXPECTED_CASES:
            raise ValueError("system_e2e.evidence_result_invalid")
        if not (2 <= counts["knowledgeSearch"] <= 8 and counts["embedding"] == 2 and counts["rerank"] == 1):
            raise ValueError("system_e2e.evidence_knowledge_counts_invalid")
        if (
            counts["employee"] != 2
            or counts["transaction"] != 2
            or counts["otherBusinessEndpoints"] != 0
            or counts["localKnowledgeModel"] != 3
            or counts["answerGeneration"] != 0
            or counts["externalModelOutbound"] != 0
        ):
            raise ValueError("system_e2e.evidence_boundary_counts_invalid")
        if security != {"logLeakCount": 0, "sensitivePersistence": False} or not all(cleanup.values()):
            raise ValueError("system_e2e.evidence_safety_invalid")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("system_e2e.evidence_path_required")
    value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    validate_system_e2e_evidence(value, final=True)


if __name__ == "__main__":
    main()
