from __future__ import annotations

from copy import deepcopy

import pytest

from tests.system_e2e.evidence_contract import runtime_evidence
from tests.uat.evidence_contract import (
    build_access_evidence,
    build_closure_evidence,
    build_runtime_stage_evidence,
    validate_closure_evidence,
    validate_stage_evidence,
    write_evidence,
)


_HEAD = "a" * 40
_ZERO_COUNTS = {
    "knowledgeSearch": 0,
    "embedding": 0,
    "rerank": 0,
    "employee": 0,
    "transaction": 0,
    "otherBusinessEndpoints": 0,
    "localKnowledgeModel": 0,
    "answerGeneration": 0,
    "externalModelOutbound": 0,
}


def test_access_evidence_is_strict_and_zero_call() -> None:
    value = build_access_evidence(git_head=_HEAD)

    validate_stage_evidence(value)
    assert value["stage"] == "access"
    assert len(value["cases"]) == 4
    assert value["requestCounts"] == _ZERO_COUNTS


@pytest.mark.parametrize(
    ("stage", "cases"),
    [
        (
            "employee",
            {
                "system-uat-emp-admin": ("success", "employee.detail"),
                "system-uat-emp-viewer": ("success", "employee.detail"),
                "system-uat-emp-deny": ("forbidden", "employee.detail"),
                "system-uat-emp-invalid": ("invalid_argument", None),
            },
        ),
        (
            "transaction",
            {
                "system-uat-txn-admin": ("success", "transaction.search"),
                "system-uat-txn-viewer": ("success", "transaction.search"),
                "system-uat-txn-deny": ("forbidden", "transaction.search"),
                "system-uat-txn-scale": ("invalid_argument", None),
                "system-uat-txn-aggregate": ("invalid_argument", None),
            },
        ),
    ],
)
def test_runtime_stage_evidence_requires_exact_cases_and_three_domain_calls(
    stage: str, cases: dict[str, tuple[str, str | None]]
) -> None:
    counts = dict(_ZERO_COUNTS)
    counts[stage] = 3
    runtime = runtime_evidence(cases=cases, request_counts=counts)

    value = build_runtime_stage_evidence(stage=stage, git_head=_HEAD, runtime_evidence=runtime)

    validate_stage_evidence(value)
    assert value["stage"] == stage
    assert value["requestCounts"][stage] == 3


def test_runtime_stage_rejects_wrong_capability_and_forbidden_model_call() -> None:
    counts = dict(_ZERO_COUNTS)
    counts["employee"] = 3
    runtime = runtime_evidence(
        cases={
            "system-uat-emp-admin": ("success", "employee.detail"),
            "system-uat-emp-viewer": ("success", "employee.detail"),
            "system-uat-emp-deny": ("forbidden", "employee.detail"),
            "system-uat-emp-invalid": ("invalid_argument", None),
        },
        request_counts=counts,
    )
    wrong_capability = deepcopy(runtime)
    wrong_capability["cases"][0]["capabilityId"] = "transaction.search"
    with pytest.raises(ValueError, match="uat_evidence.case_mismatch"):
        build_runtime_stage_evidence(stage="employee", git_head=_HEAD, runtime_evidence=wrong_capability)

    model_call = deepcopy(runtime)
    model_call["requestCounts"]["externalModelOutbound"] = 1
    with pytest.raises(ValueError, match="uat_evidence.runtime_counts_invalid"):
        build_runtime_stage_evidence(stage="employee", git_head=_HEAD, runtime_evidence=model_call)


def test_closure_binds_three_exact_stage_evidence_files(tmp_path) -> None:
    access = build_access_evidence(git_head=_HEAD)
    employee_counts = dict(_ZERO_COUNTS)
    employee_counts["employee"] = 3
    employee = build_runtime_stage_evidence(
        stage="employee",
        git_head=_HEAD,
        runtime_evidence=runtime_evidence(
            cases={
                "system-uat-emp-admin": ("success", "employee.detail"),
                "system-uat-emp-viewer": ("success", "employee.detail"),
                "system-uat-emp-deny": ("forbidden", "employee.detail"),
                "system-uat-emp-invalid": ("invalid_argument", None),
            },
            request_counts=employee_counts,
        ),
    )
    transaction_counts = dict(_ZERO_COUNTS)
    transaction_counts["transaction"] = 3
    transaction = build_runtime_stage_evidence(
        stage="transaction",
        git_head=_HEAD,
        runtime_evidence=runtime_evidence(
            cases={
                "system-uat-txn-admin": ("success", "transaction.search"),
                "system-uat-txn-viewer": ("success", "transaction.search"),
                "system-uat-txn-deny": ("forbidden", "transaction.search"),
                "system-uat-txn-scale": ("invalid_argument", None),
                "system-uat-txn-aggregate": ("invalid_argument", None),
            },
            request_counts=transaction_counts,
        ),
    )
    paths = {}
    for stage, value in {"access": access, "employee": employee, "transaction": transaction}.items():
        path = tmp_path / f"{stage}.json"
        write_evidence(path, value)
        paths[stage] = path

    closure = build_closure_evidence(git_head=_HEAD, stage_paths=paths)

    validate_closure_evidence(closure)
    assert len(closure["cases"]) == 13
    assert closure["requestCounts"]["employee"] == 3
    assert closure["requestCounts"]["transaction"] == 3
    assert closure["scope"]["fullUatGateClosed"] is False
