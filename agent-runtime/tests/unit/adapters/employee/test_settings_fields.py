from __future__ import annotations

import pytest

from agent_runtime.adapters.employee.fields import employee_field_definitions
from agent_runtime.adapters.employee.settings import EmployeeAdapterSettings
from agent_runtime.business.contracts import BusinessQueryOperator


def test_employee_fields_limit_model_candidates_to_position_and_work_base() -> None:
    fields = employee_field_definitions()
    assert tuple(item.field_id for item in fields) == (
        "employee_id_masked", "member_no_masked", "chinese_name", "public_email", "position", "work_base_si"
    )
    assert {item.field_id for item in fields if item.model_candidate_by_code} == {"position", "work_base_si"}


def test_employee_settings_default_disabled_and_cannot_remove_required_fields() -> None:
    action = EmployeeAdapterSettings.from_env({}).action
    assert not action.enabled
    assert action.config_version == "employee-detail-config-v1"
    assert action.code_contract_version == "employee-detail-plan-v1"
    assert action.service_contract_ref == "employee-detail-v1"
    assert len(action.query_fields) == 1
    query_field = action.query_fields[0]
    assert query_field.logical_name == "employee_identifier"
    assert query_field.allowed_operators == (BusinessQueryOperator.EQ,)
    assert query_field.required
    with pytest.raises(ValueError):
        EmployeeAdapterSettings.from_env({"AGENT_EMPLOYEE_DETAIL_USER_FIELDS": "position"})
    with pytest.raises(ValueError):
        EmployeeAdapterSettings.from_env({"AGENT_EMPLOYEE_DETAIL_UNKNOWN": "x"})
    with pytest.raises(ValueError, match="business.employee_settings_invalid"):
        EmployeeAdapterSettings.from_env({"AGENT_EMPLOYEE_DETAIL_TIMEOUT_MS": "02000"})
    with pytest.raises(ValueError, match="business.employee_settings_invalid"):
        EmployeeAdapterSettings.from_env(
            {"AGENT_EMPLOYEE_DETAIL_CODE_CONTRACT_VERSION": "employee-detail-plan-v2"}
        )
    with pytest.raises(ValueError, match="business.employee_settings_invalid"):
        EmployeeAdapterSettings.from_env(
            {"AGENT_EMPLOYEE_DETAIL_CONFIG_VERSION": "INVALID-V1"}
        )
