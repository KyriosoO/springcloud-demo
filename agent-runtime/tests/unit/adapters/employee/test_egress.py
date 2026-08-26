from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from agent_runtime.adapters.employee.definition import employee_detail_definition
from agent_runtime.adapters.employee.settings import EmployeeAdapterSettings
from agent_runtime.business.contracts import (
    BusinessResultCoverage,
    BusinessUserField,
    BusinessUserRecord,
    BusinessUserResult,
)
from agent_runtime.business.egress import BusinessEgressProjector
from agent_runtime.business.settings import BusinessGlobalSettings, GlobalBusinessEgressPolicy
from agent_runtime.capability_api.contracts import EgressDisposition, JsonObject, JsonValue


_MATRIX = Path(__file__).parents[3] / "fixtures" / "employee_egress_field_matrix.json"


def _json_object(value: JsonValue) -> JsonObject:
    assert isinstance(value, Mapping)
    return value


def _json_array(value: JsonValue) -> tuple[JsonValue, ...]:
    assert isinstance(value, tuple)
    return value


def _user_result() -> BusinessUserResult:
    return BusinessUserResult(
        capability_id="employee.detail",
        records=(
            BusinessUserRecord(
                record_ref="record-0001",
                fields=(
                    BusinessUserField(field_id="employee_id_masked", value="***A001"),
                    BusinessUserField(field_id="member_no_masked", value="***M001"),
                    BusinessUserField(field_id="chinese_name", value="合成员工"),
                    BusinessUserField(field_id="public_email", value="synthetic@example.invalid"),
                    BusinessUserField(field_id="position", value="工程师"),
                ),
            ),
        ),
        coverage=BusinessResultCoverage(returned_count=1, truncated=False, total_count=1),
    )


def _enabled_policy() -> GlobalBusinessEgressPolicy:
    return GlobalBusinessEgressPolicy.from_settings(BusinessGlobalSettings(egress_enabled=True))


def test_employee_egress_field_matrix_matches_code_bound_definition_and_defaults() -> None:
    raw = cast(object, json.loads(_MATRIX.read_text(encoding="utf-8")))
    assert type(raw) is dict
    matrix = cast(dict[str, object], raw)
    assert set(matrix) == {
        "schemaVersion",
        "capabilityId",
        "defaultModelFields",
        "maximumModelFields",
        "fields",
        "zeroCallScenarios",
    }
    assert matrix["schemaVersion"] == 1
    assert matrix["capabilityId"] == "employee.detail"
    assert matrix["defaultModelFields"] == []
    assert matrix["maximumModelFields"] == ["position"]
    assert matrix["zeroCallScenarios"] == [
        "default_empty",
        "identifier_only",
        "member_number_only",
        "name_only",
        "contact_only",
        "financial_account_only",
        "credential_only",
        "instruction_injection_only",
        "unclassified_only",
        "policy_conflict",
        "minimum_user_result_missing",
    ]

    definition = employee_detail_definition()
    field_rows = cast(list[dict[str, object]], matrix["fields"])
    assert all(
        set(row) == {"fieldId", "dataClass", "userVisible", "modelCandidate"}
        for row in field_rows
    )
    assert tuple(row["fieldId"] for row in field_rows) == tuple(
        field.field_id for field in definition.field_definitions
    )
    assert tuple(row["dataClass"] for row in field_rows) == tuple(
        field.data_class.value for field in definition.field_definitions
    )
    assert tuple(row["userVisible"] for row in field_rows) == tuple(
        field.user_visible_by_code for field in definition.field_definitions
    )
    assert tuple(row["modelCandidate"] for row in field_rows) == tuple(
        field.model_candidate_by_code for field in definition.field_definitions
    )
    assert EmployeeAdapterSettings.from_env({}).action.model_field_ids == ()


@pytest.mark.parametrize(
    "field_id",
    (
        "employee_id_masked",
        "member_no_masked",
        "chinese_name",
        "public_email",
        "financial_account",
        "credential",
        "instruction_injection",
        "unclassified",
    ),
)
def test_employee_forbidden_or_unknown_model_field_fails_configuration_closed(field_id: str) -> None:
    with pytest.raises(ValueError, match="business.employee_settings_invalid"):
        EmployeeAdapterSettings.from_env({"AGENT_EMPLOYEE_DETAIL_MODEL_FIELDS": field_id})


def test_employee_egress_projects_only_position_fact() -> None:
    settings = EmployeeAdapterSettings.from_env(
        {"AGENT_EMPLOYEE_DETAIL_MODEL_FIELDS": "position"}
    ).action

    result = BusinessEgressProjector().project(
        definition=employee_detail_definition(),
        settings=settings,
        user_result=_user_result(),
        policy=_enabled_policy(),
        config_snapshot_id="a" * 64,
    )

    assert result.disposition is EgressDisposition.ALLOWED
    assert result.safe_payload is not None
    facts = tuple(_json_object(item) for item in _json_array(result.safe_payload["facts"]))
    assert tuple(_json_object(item["source"])["field_id"] for item in facts) == (
        "position",
    )
    assert tuple(item["value"] for item in facts) == ("工程师",)
    payload_text = json.dumps(result.safe_payload, ensure_ascii=False, default=list)
    for denied_value in ("***A001", "***M001", "合成员工", "synthetic@example.invalid"):
        assert denied_value not in payload_text


def test_employee_default_empty_and_policy_conflict_both_deny_model_egress() -> None:
    default_settings = EmployeeAdapterSettings.from_env({}).action
    default_result = BusinessEgressProjector().project(
        definition=employee_detail_definition(),
        settings=default_settings,
        user_result=_user_result(),
        policy=_enabled_policy(),
        config_snapshot_id="a" * 64,
    )
    assert default_result.disposition is EgressDisposition.DENIED
    assert default_result.reason_code == "business.no_model_fields"

    enabled = EmployeeAdapterSettings.from_env(
        {"AGENT_EMPLOYEE_DETAIL_MODEL_FIELDS": "position"}
    ).action
    conflicted = replace(enabled, model_transforms=())
    conflict_result = BusinessEgressProjector().project(
        definition=employee_detail_definition(),
        settings=conflicted,
        user_result=_user_result(),
        policy=_enabled_policy(),
        config_snapshot_id="a" * 64,
    )
    assert conflict_result.disposition is EgressDisposition.DENIED
    assert conflict_result.reason_code == "business.policy_conflict"
