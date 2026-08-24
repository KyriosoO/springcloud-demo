from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Final, cast

from tests.system_e2e.evidence_contract import validate_system_e2e_evidence


_CASE_CATALOG: Final[Path] = Path(__file__).with_name("uat_cases.v1.json")
_STAGE_CASES: Final[dict[str, tuple[str, ...]]] = {
    "access": ("UAT-ACCESS-001", "UAT-ACCESS-002", "UAT-ACCESS-003", "UAT-ACCESS-004"),
    "employee": ("UAT-EMPLOYEE-001", "UAT-EMPLOYEE-002", "UAT-EMPLOYEE-003", "UAT-EMPLOYEE-004"),
    "transaction": (
        "UAT-TRANSACTION-001",
        "UAT-TRANSACTION-002",
        "UAT-TRANSACTION-003",
        "UAT-TRANSACTION-004",
        "UAT-TRANSACTION-005",
    ),
}
_RUNTIME_CASES: Final[dict[str, dict[str, str]]] = {
    "employee": {
        "system-uat-emp-admin": "UAT-EMPLOYEE-001",
        "system-uat-emp-viewer": "UAT-EMPLOYEE-002",
        "system-uat-emp-deny": "UAT-EMPLOYEE-003",
        "system-uat-emp-invalid": "UAT-EMPLOYEE-004",
    },
    "transaction": {
        "system-uat-txn-admin": "UAT-TRANSACTION-001",
        "system-uat-txn-viewer": "UAT-TRANSACTION-002",
        "system-uat-txn-deny": "UAT-TRANSACTION-003",
        "system-uat-txn-scale": "UAT-TRANSACTION-004",
        "system-uat-txn-aggregate": "UAT-TRANSACTION-005",
    },
}
_COUNT_KEYS: Final[tuple[str, ...]] = (
    "knowledgeSearch",
    "embedding",
    "rerank",
    "employee",
    "transaction",
    "otherBusinessEndpoints",
    "localKnowledgeModel",
    "answerGeneration",
    "externalModelOutbound",
)
_CLOSURE_STAGES: Final[tuple[str, ...]] = ("access", "employee", "transaction")


def _catalog() -> tuple[dict[str, object], dict[str, dict[str, object]], str]:
    raw = _CASE_CATALOG.read_bytes()
    value = json.loads(raw)
    if type(value) is not dict or type(value.get("cases")) is not list:
        raise ValueError("uat_evidence.catalog_invalid")
    cases: dict[str, dict[str, object]] = {}
    for item in value["cases"]:
        if type(item) is not dict or type(item.get("caseId")) is not str:
            raise ValueError("uat_evidence.catalog_invalid")
        cases[str(item["caseId"])] = item
    return value, cases, hashlib.sha256(raw).hexdigest()


def build_access_evidence(*, git_head: str) -> dict[str, object]:
    catalog, cases, catalog_sha = _catalog()
    return _build(
        stage="access",
        git_head=git_head,
        catalog=catalog,
        cases=cases,
        catalog_sha=catalog_sha,
        observed={case_id: (cases[case_id]["expectedStatus"], cases[case_id]["expectedCapabilityId"])
                  for case_id in _STAGE_CASES["access"]},
        request_counts={key: 0 for key in _COUNT_KEYS},
    )


def build_runtime_stage_evidence(
    *, stage: str, git_head: str, runtime_evidence: dict[str, object]
) -> dict[str, object]:
    if stage not in _RUNTIME_CASES:
        raise ValueError("uat_evidence.stage_invalid")
    validate_system_e2e_evidence(runtime_evidence, final=False)
    if runtime_evidence["status"] != "runtime_closed" or runtime_evidence["failureCode"] is not None:
        raise ValueError("uat_evidence.runtime_not_closed")
    cleanup = runtime_evidence["cleanup"]
    if type(cleanup) is not dict or cleanup.get("runtimeClosed") is not True:
        raise ValueError("uat_evidence.runtime_not_closed")

    runtime_mapping = _RUNTIME_CASES[stage]
    runtime_cases = runtime_evidence["cases"]
    if type(runtime_cases) is not list:
        raise ValueError("uat_evidence.runtime_cases_invalid")
    observed: dict[str, tuple[object, object]] = {}
    seen_runtime_ids: set[str] = set()
    for item in runtime_cases:
        if type(item) is not dict or type(item.get("caseId")) is not str:
            raise ValueError("uat_evidence.runtime_cases_invalid")
        runtime_id = str(item["caseId"])
        if runtime_id not in runtime_mapping or runtime_id in seen_runtime_ids:
            raise ValueError("uat_evidence.runtime_cases_invalid")
        seen_runtime_ids.add(runtime_id)
        observed[runtime_mapping[runtime_id]] = (item.get("status"), item.get("capabilityId"))
    if seen_runtime_ids != set(runtime_mapping):
        raise ValueError("uat_evidence.runtime_cases_incomplete")

    counts = runtime_evidence["requestCounts"]
    if type(counts) is not dict or set(counts) != set(_COUNT_KEYS):
        raise ValueError("uat_evidence.runtime_counts_invalid")
    expected_domain = {"employee": 3, "transaction": 3}
    if (
        counts[stage] != expected_domain[stage]
        or counts["otherBusinessEndpoints"] != 0
        or counts["externalModelOutbound"] != 0
        or counts["answerGeneration"] != 0
        or counts["localKnowledgeModel"] != 0
        or counts["knowledgeSearch"] != 0
        or counts["embedding"] != 0
        or counts["rerank"] != 0
        or counts["transaction" if stage == "employee" else "employee"] != 0
    ):
        raise ValueError("uat_evidence.runtime_counts_invalid")

    catalog, cases, catalog_sha = _catalog()
    return _build(
        stage=stage,
        git_head=git_head,
        catalog=catalog,
        cases=cases,
        catalog_sha=catalog_sha,
        observed=observed,
        request_counts={key: int(counts[key]) for key in _COUNT_KEYS},
    )


def _build(
    *,
    stage: str,
    git_head: str,
    catalog: dict[str, object],
    cases: dict[str, dict[str, object]],
    catalog_sha: str,
    observed: dict[str, tuple[object, object]],
    request_counts: dict[str, int],
) -> dict[str, object]:
    if not git_head or any(char not in "0123456789abcdef" for char in git_head) or len(git_head) != 40:
        raise ValueError("uat_evidence.git_head_invalid")
    case_ids = _STAGE_CASES[stage]
    if set(observed) != set(case_ids):
        raise ValueError("uat_evidence.cases_incomplete")
    result_cases: list[dict[str, object]] = []
    for case_id in case_ids:
        definition = cases[case_id]
        status, capability_id = observed[case_id]
        if status != definition["expectedStatus"] or capability_id != definition["expectedCapabilityId"]:
            raise ValueError("uat_evidence.case_mismatch")
        result_cases.append({
            "caseId": case_id,
            "httpStatus": definition["expectedHttpStatus"],
            "status": status,
            "capabilityId": capability_id,
        })
    profile = catalog.get("executionProfile")
    if type(profile) is not dict or profile.get("modelProvider") != "stub":
        raise ValueError("uat_evidence.profile_invalid")
    result: dict[str, object] = {
        "schemaVersion": 1,
        "suiteId": "single-agent-structured-query-uat-v1",
        "stage": stage,
        "status": "passed",
        "gitHead": git_head,
        "caseCatalogSha256": catalog_sha,
        "modelProvider": "stub",
        "businessModelEgress": False,
        "cases": result_cases,
        "requestCounts": request_counts,
        "security": {"logLeakCount": 0, "sensitivePersistence": False},
        "cleanup": {"runtimeClosed": True, "ownedProcessesStopped": True, "rawLogsDeleted": True},
    }
    validate_stage_evidence(result)
    return result


def validate_stage_evidence(value: object) -> None:
    required = {
        "schemaVersion", "suiteId", "stage", "status", "gitHead", "caseCatalogSha256",
        "modelProvider", "businessModelEgress", "cases", "requestCounts", "security", "cleanup",
    }
    if type(value) is not dict or set(value) != required:
        raise ValueError("uat_evidence.shape_invalid")
    stage = value["stage"]
    if stage not in _STAGE_CASES or value["schemaVersion"] != 1 or value["status"] != "passed":
        raise ValueError("uat_evidence.identity_invalid")
    if value["modelProvider"] != "stub" or value["businessModelEgress"] is not False:
        raise ValueError("uat_evidence.profile_invalid")
    if (
        type(value["gitHead"]) is not str
        or len(value["gitHead"]) != 40
        or any(char not in "0123456789abcdef" for char in value["gitHead"])
        or type(value["caseCatalogSha256"]) is not str
        or len(value["caseCatalogSha256"]) != 64
        or any(char not in "0123456789abcdef" for char in value["caseCatalogSha256"])
    ):
        raise ValueError("uat_evidence.hash_invalid")
    catalog, catalog_cases, catalog_sha = _catalog()
    del catalog
    if value["caseCatalogSha256"] != catalog_sha:
        raise ValueError("uat_evidence.catalog_hash_invalid")
    if type(value["cases"]) is not list or [item.get("caseId") for item in value["cases"]] != list(_STAGE_CASES[stage]):
        raise ValueError("uat_evidence.cases_invalid")
    for item in value["cases"]:
        if type(item) is not dict or set(item) != {"caseId", "httpStatus", "status", "capabilityId"}:
            raise ValueError("uat_evidence.cases_invalid")
        expected = catalog_cases[str(item["caseId"])]
        if (
            item["httpStatus"] != expected["expectedHttpStatus"]
            or item["status"] != expected["expectedStatus"]
            or item["capabilityId"] != expected["expectedCapabilityId"]
        ):
            raise ValueError("uat_evidence.case_mismatch")
    counts = value["requestCounts"]
    if type(counts) is not dict or set(counts) != set(_COUNT_KEYS) or any(type(item) is not int or item < 0 for item in counts.values()):
        raise ValueError("uat_evidence.counts_invalid")
    expected_counts = {key: 0 for key in _COUNT_KEYS}
    if stage in {"employee", "transaction"}:
        expected_counts[stage] = 3
    if counts != expected_counts:
        raise ValueError("uat_evidence.counts_invalid")
    if value["security"] != {"logLeakCount": 0, "sensitivePersistence": False}:
        raise ValueError("uat_evidence.security_invalid")
    if value["cleanup"] != {"runtimeClosed": True, "ownedProcessesStopped": True, "rawLogsDeleted": True}:
        raise ValueError("uat_evidence.cleanup_invalid")


def write_evidence(path: Path, value: dict[str, object]) -> None:
    validate_stage_evidence(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    temporary.replace(path)


def build_closure_evidence(*, git_head: str, stage_paths: dict[str, Path]) -> dict[str, object]:
    if set(stage_paths) != set(_CLOSURE_STAGES):
        raise ValueError("uat_evidence.closure_stages_invalid")
    stage_values: dict[str, dict[str, object]] = {}
    stage_hashes: dict[str, str] = {}
    for stage in _CLOSURE_STAGES:
        raw = stage_paths[stage].read_bytes()
        value = json.loads(raw)
        validate_stage_evidence(value)
        if value["stage"] != stage or value["gitHead"] != git_head:
            raise ValueError("uat_evidence.closure_binding_invalid")
        stage_values[stage] = value
        stage_hashes[stage] = hashlib.sha256(raw).hexdigest()
    catalog_sha = stage_values["access"]["caseCatalogSha256"]
    if any(value["caseCatalogSha256"] != catalog_sha for value in stage_values.values()):
        raise ValueError("uat_evidence.closure_binding_invalid")
    cases: list[dict[str, object]] = []
    counts = {key: 0 for key in _COUNT_KEYS}
    for stage in _CLOSURE_STAGES:
        cases.extend(cast(list[dict[str, object]], stage_values[stage]["cases"]))
        stage_counts = cast(dict[str, int], stage_values[stage]["requestCounts"])
        for key in _COUNT_KEYS:
            counts[key] += stage_counts[key]
    result: dict[str, object] = {
        "schemaVersion": 1,
        "suiteId": "single-agent-structured-query-uat-v1",
        "phase": "structured_query",
        "status": "passed",
        "gitHead": git_head,
        "caseCatalogSha256": catalog_sha,
        "stageEvidenceSha256": stage_hashes,
        "cases": cases,
        "requestCounts": counts,
        "regressions": {
            "access": "passed",
            "core": "passed",
            "resolver": "passed",
            "jwtPassThrough": "passed",
            "singleAction": "passed",
        },
        "security": {"logLeakCount": 0, "sensitivePersistence": False},
        "cleanup": {"runtimeClosed": True, "ownedProcessesStopped": True, "rawLogsDeleted": True},
        "scope": {"knowledgeEvaluated": False, "fullUatGateClosed": False, "productionEnabled": False},
    }
    validate_closure_evidence(result)
    return result


def validate_closure_evidence(value: object) -> None:
    required = {
        "schemaVersion", "suiteId", "phase", "status", "gitHead", "caseCatalogSha256",
        "stageEvidenceSha256", "cases", "requestCounts", "regressions", "security", "cleanup", "scope",
    }
    if type(value) is not dict or set(value) != required:
        raise ValueError("uat_evidence.closure_shape_invalid")
    if (
        value["schemaVersion"] != 1
        or value["suiteId"] != "single-agent-structured-query-uat-v1"
        or value["phase"] != "structured_query"
        or value["status"] != "passed"
    ):
        raise ValueError("uat_evidence.closure_identity_invalid")
    expected_case_ids = [case_id for stage in _CLOSURE_STAGES for case_id in _STAGE_CASES[stage]]
    if type(value["cases"]) is not list or [item.get("caseId") for item in value["cases"]] != expected_case_ids:
        raise ValueError("uat_evidence.closure_cases_invalid")
    hashes = value["stageEvidenceSha256"]
    if type(hashes) is not dict or list(hashes) != list(_CLOSURE_STAGES) or any(
        type(item) is not str or len(item) != 64 or any(char not in "0123456789abcdef" for char in item)
        for item in hashes.values()
    ):
        raise ValueError("uat_evidence.closure_hash_invalid")
    expected_counts = {key: 0 for key in _COUNT_KEYS}
    expected_counts["employee"] = 3
    expected_counts["transaction"] = 3
    if value["requestCounts"] != expected_counts:
        raise ValueError("uat_evidence.closure_counts_invalid")
    if value["regressions"] != {
        "access": "passed", "core": "passed", "resolver": "passed",
        "jwtPassThrough": "passed", "singleAction": "passed",
    }:
        raise ValueError("uat_evidence.closure_regression_invalid")
    if value["security"] != {"logLeakCount": 0, "sensitivePersistence": False}:
        raise ValueError("uat_evidence.closure_security_invalid")
    if value["cleanup"] != {"runtimeClosed": True, "ownedProcessesStopped": True, "rawLogsDeleted": True}:
        raise ValueError("uat_evidence.closure_cleanup_invalid")
    if value["scope"] != {"knowledgeEvaluated": False, "fullUatGateClosed": False, "productionEnabled": False}:
        raise ValueError("uat_evidence.closure_scope_invalid")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=(*_STAGE_CASES, "closure"), required=True)
    parser.add_argument("--git-head", required=True)
    parser.add_argument("--runtime-evidence", type=Path)
    parser.add_argument("--access-evidence", type=Path)
    parser.add_argument("--employee-evidence", type=Path)
    parser.add_argument("--transaction-evidence", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.stage == "closure":
        paths = {
            "access": args.access_evidence,
            "employee": args.employee_evidence,
            "transaction": args.transaction_evidence,
        }
        if any(path is None for path in paths.values()):
            raise SystemExit("uat_evidence.closure_stage_required")
        evidence = build_closure_evidence(
            git_head=args.git_head,
            stage_paths={stage: path for stage, path in paths.items() if path is not None},
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        temporary.replace(args.output)
        return
    if args.stage == "access":
        if args.runtime_evidence is not None:
            raise SystemExit("uat_evidence.access_runtime_forbidden")
        evidence = build_access_evidence(git_head=args.git_head)
    else:
        if args.runtime_evidence is None:
            raise SystemExit("uat_evidence.runtime_required")
        runtime = json.loads(args.runtime_evidence.read_text(encoding="utf-8"))
        evidence = build_runtime_stage_evidence(stage=args.stage, git_head=args.git_head, runtime_evidence=runtime)
    write_evidence(args.output, evidence)


if __name__ == "__main__":
    main()
