from __future__ import annotations

import pytest

from agent_runtime.capability_api.contracts import InvalidCapabilityArguments
from agent_runtime.adapters.employee.codec import EmployeeDetailArgumentValidator
from agent_runtime.adapters.employee.definition import employee_detail_definition


def test_employee_definition_is_one_read_only_detail_action() -> None:
    definition = employee_detail_definition()
    assert definition.descriptor.capability_id == "employee.detail"
    assert set(definition.descriptor.argument_schema["properties"]) == {"employee_identifier"}  # type: ignore[arg-type]
    assert definition.filter_field_ids_by_code == frozenset()
    assert definition.sort_field_ids_by_code == frozenset()
    assert definition.required_user_field_ids == ("employee_id_masked", "chinese_name")


def test_employee_identifier_is_normalized_but_not_path_interpreted() -> None:
    validator = EmployeeDetailArgumentValidator()
    assert validator.validate({"employee_identifier": "  ABCDE  "}).employee_identifier == "ABCDE"
    for invalid in ("AB CDE", "AB%20CDE", "AB/CDE", "AB?CDE", "AB#CDE", "ABCD"):
        with pytest.raises(InvalidCapabilityArguments):
            validator.validate({"employee_identifier": invalid})

