from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast


_ASSET = Path(__file__).with_name("uat_cases.v1.json")
_STRUCTURED_RUNNER = Path(__file__).parents[2] / "scripts" / "run-structured-query-uat.ps1"
_CASE_KEYS = {
    "caseId",
    "domain",
    "principal",
    "requestVariant",
    "questionTemplate",
    "expectedHttpStatus",
    "expectedStatus",
    "expectedCapabilityId",
    "automationReference",
    "mandatory",
}
_CASE_ID = re.compile(r"^UAT-(?:ACCESS|KNOWLEDGE|EMPLOYEE|TRANSACTION)-[0-9]{3}$")
_FORBIDDEN_LITERAL = re.compile(
    r"(?:eyJ[a-zA-Z0-9_-]{12,}|\b[1-9][0-9]{16}[0-9Xx]\b|LLM_API_KEY\s*=|Authorization:\s*Bearer)",
    re.IGNORECASE,
)


def _load() -> dict[str, Any]:
    value = json.loads(_ASSET.read_text(encoding="utf-8"))
    assert type(value) is dict
    return cast(dict[str, Any], value)


def test_uat_catalog_has_strict_safe_profile_and_runtime_inputs() -> None:
    value = _load()

    assert set(value) == {
        "schemaVersion",
        "suiteId",
        "executionProfile",
        "runtimeInputs",
        "cases",
    }
    assert value["schemaVersion"] == 1
    assert value["suiteId"] == "single-agent-uat-v1"
    assert value["executionProfile"] == {
        "knowledgeProvider": "real",
        "employeeProvider": "real",
        "transactionProvider": "real",
        "modelProvider": "stub",
        "businessModelEgress": False,
        "externalModelOutboundMax": 0,
        "maxActionsPerRequest": 1,
    }
    assert value["runtimeInputs"] == [
        {
            "name": "SYSTEM_E2E_EMPLOYEE_IDENTIFIER",
            "classification": "sensitive",
            "persistence": "process_only",
        },
        {
            "name": "UAT_TRANSACTION_TYPE",
            "classification": "business_test_filter",
            "persistence": "process_only",
        },
    ]


def test_uat_catalog_is_complete_unique_and_contains_no_sensitive_values() -> None:
    cases = cast(list[dict[str, Any]], _load()["cases"])

    assert len(cases) == 16
    assert len({case["caseId"] for case in cases}) == len(cases)
    assert all(set(case) == _CASE_KEYS for case in cases)
    assert all(_CASE_ID.fullmatch(case["caseId"]) for case in cases)
    assert all(case["mandatory"] is True for case in cases)
    assert {case["domain"] for case in cases} == {
        "access",
        "knowledge",
        "employee",
        "transaction",
    }
    assert {case["principal"] for case in cases} == {
        "admin",
        "viewer",
        "unknown",
        "missing",
        "malformed",
    }
    assert not _FORBIDDEN_LITERAL.search(_ASSET.read_text(encoding="utf-8"))


def test_uat_case_contract_uses_only_bounded_values() -> None:
    cases = cast(list[dict[str, Any]], _load()["cases"])
    expected_capability_by_domain = {
        "knowledge": "knowledge.query",
        "employee": "employee.detail",
        "transaction": "transaction.search",
    }

    assert {domain: sum(case["domain"] == domain for case in cases) for domain in {
        "access",
        "knowledge",
        "employee",
        "transaction",
    }} == {
        "access": 4,
        "knowledge": 3,
        "employee": 4,
        "transaction": 5,
    }
    for case in cases:
        assert type(case["questionTemplate"]) is str and case["questionTemplate"].strip()
        assert type(case["automationReference"]) is str and case[
            "automationReference"
        ].strip()
        assert case["requestVariant"] in {"valid_json", "unknown_request_field"}
        assert type(case["expectedHttpStatus"]) is int
        assert case["expectedHttpStatus"] in {200, 400, 401, 403, 422}
        assert case["expectedStatus"] in {
            "success",
            "unauthenticated",
            "forbidden",
            "invalid_argument",
            "unsupported",
        }
        assert case["expectedCapabilityId"] is None or type(
            case["expectedCapabilityId"]
        ) is str
        assert type(case["mandatory"]) is bool
        if case["expectedStatus"] in {"success", "forbidden"}:
            assert case["expectedCapabilityId"] == expected_capability_by_domain[
                case["domain"]
            ]
        else:
            assert case["expectedCapabilityId"] is None


def test_uat_catalog_covers_required_capability_and_failure_matrix() -> None:
    cases = cast(list[dict[str, Any]], _load()["cases"])
    observed = {
        (
            case["domain"],
            case["principal"],
            case["expectedHttpStatus"],
            case["expectedStatus"],
            case["expectedCapabilityId"],
        )
        for case in cases
    }

    required = {
        ("access", "missing", 401, "unauthenticated", None),
        ("access", "malformed", 401, "unauthenticated", None),
        ("knowledge", "admin", 200, "success", "knowledge.query"),
        ("knowledge", "viewer", 200, "success", "knowledge.query"),
        ("knowledge", "unknown", 403, "forbidden", "knowledge.query"),
        ("employee", "admin", 200, "success", "employee.detail"),
        ("employee", "viewer", 200, "success", "employee.detail"),
        ("employee", "unknown", 403, "forbidden", "employee.detail"),
        ("transaction", "admin", 200, "success", "transaction.search"),
        ("transaction", "viewer", 200, "success", "transaction.search"),
        ("transaction", "unknown", 403, "forbidden", "transaction.search"),
    }
    assert required <= observed


def test_uat_catalog_uses_placeholders_instead_of_employee_or_transaction_values() -> None:
    cases = cast(list[dict[str, Any]], _load()["cases"])
    employee_questions = [
        case["questionTemplate"] for case in cases if case["domain"] == "employee"
    ]
    transaction_success_questions = [
        case["questionTemplate"]
        for case in cases
        if case["caseId"] in {"UAT-TRANSACTION-001", "UAT-TRANSACTION-002"}
    ]

    assert all(
        "${SYSTEM_E2E_EMPLOYEE_IDENTIFIER}" in item for item in employee_questions
    )
    assert all("${UAT_TRANSACTION_TYPE}" in item for item in transaction_success_questions)


def test_structured_query_runner_is_stub_only_bounded_and_does_not_read_model_key() -> None:
    source = _STRUCTURED_RUNNER.read_text(encoding="utf-8")

    assert "LLM_API_KEY" not in source
    assert "$env:AGENT_MODEL_PROVIDER = 'stub'" in source
    assert "RUN_STRUCTURED_QUERY_UAT" in source
    assert "Get-TransactionType" in source
    assert source.count("SELECT TRANS_TYPE FROM t_transaction") == 1
    assert "transaction.search" not in source
    assert "employee.detail" not in source
    assert "Remove-Item -LiteralPath $runRoot -Recurse -Force" in source
