from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from agent_runtime.adapters.employee.definition import employee_detail_definition
from agent_runtime.adapters.employee.protected_input import EmployeeProtectedValueExtractor
from agent_runtime.adapters.employee.settings import EmployeeAdapterSettings
from agent_runtime.business.contracts import BusinessActionDefinition, BusinessServiceKey
from agent_runtime.business.planner_catalog import build_business_planner_catalog
from agent_runtime.business.query_plan import (
    DefaultBusinessQueryPlanValidator,
    ExactBusinessQueryPlanDecoder,
    InvalidBusinessQueryPlan,
    InvalidProtectedValue,
    RequestProtectedValueBinder,
    UnsupportedBusinessQueryPlan,
    ValidatedBusinessQueryPlan,
)
from agent_runtime.business.settings import (
    BusinessConfigurationSource,
    BusinessConfigurationSnapshot,
    BusinessGlobalSettings,
    BusinessServiceBinding,
    BusinessSettingsValidator,
)
from agent_runtime.model.contracts import QuestionEgressDisposition
from agent_runtime.model.input_guard import QuestionEgressGuard


def _snapshot() -> tuple[
    BusinessActionDefinition[Any, Any, Any, Any],
    BusinessConfigurationSnapshot,
]:
    definition = employee_detail_definition()
    action = replace(EmployeeAdapterSettings.from_env({}).action, enabled=True)
    snapshot = BusinessSettingsValidator().validate(
        (definition,),
        BusinessConfigurationSource(
            global_settings=BusinessGlobalSettings(),
            actions=(("employee.detail", action),),
            service_bindings=(
                BusinessServiceBinding(
                    service_key=BusinessServiceKey("employee-service"),
                    base_endpoint="http://employee.test",
                ),
            ),
        ),
        core_max_domain_result_bytes=1048576,
    )
    return definition, snapshot


def test_employee_exact_ref_plan_binds_once_and_reuses_argument_validator() -> None:
    definition, snapshot = _snapshot()
    decoded = ExactBusinessQueryPlanDecoder().decode(
        {
            "domain": "employee",
            "action": "employee.detail",
            "arguments": {"employee_identifier": {"value_ref": "slot-1"}},
        }
    )
    validated = DefaultBusinessQueryPlanValidator((definition,)).validate(
        decoded,
        snapshot=snapshot,
    )
    assert isinstance(validated, ValidatedBusinessQueryPlan)
    slots = EmployeeProtectedValueExtractor().extract(
        "请查看员工详情，身份证号 ABCDE",
        request_id="request-1",
    )
    candidate = RequestProtectedValueBinder().bind(
        validated,
        slots=slots,
        request_id="request-1",
    )

    assert candidate.capability_id == "employee.detail"
    assert definition.argument_validator.validate(candidate.arguments).employee_identifier == "ABCDE"


def test_employee_literal_identifier_is_rejected_before_binding() -> None:
    definition, snapshot = _snapshot()
    decoded = ExactBusinessQueryPlanDecoder().decode(
        {
            "domain": "employee",
            "action": "employee.detail",
            "arguments": {"employee_identifier": {"literal": "ABCDE"}},
        }
    )

    with pytest.raises(InvalidBusinessQueryPlan):
        DefaultBusinessQueryPlanValidator((definition,)).validate(
            decoded,
            snapshot=snapshot,
        )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "domain": "employee",
            "action": "employee.search",
            "arguments": {"work_base_si": {"literal": "上海"}},
        },
        {
            "domain": "employee",
            "action": "employee.detail",
            "arguments": {"work_base_si": {"literal": "上海"}},
        },
    ],
)
def test_employee_search_or_non_detail_field_is_unsupported(payload: dict[str, object]) -> None:
    definition, snapshot = _snapshot()
    result = DefaultBusinessQueryPlanValidator((definition,)).validate(
        ExactBusinessQueryPlanDecoder().decode(payload),  # type: ignore[arg-type]
        snapshot=snapshot,
    )

    assert isinstance(result, UnsupportedBusinessQueryPlan)


def test_employee_protected_input_is_single_request_local_value_and_model_safe() -> None:
    raw = "654322199307261222"
    slots = EmployeeProtectedValueExtractor().extract(
        f"请查看员工详情，身份证号 {raw}",
        request_id="request-1",
    )
    decision = QuestionEgressGuard().evaluate_business(
        f"请查看员工详情，身份证号 {raw}",
        protected_values=slots.values,
    )

    assert decision.disposition is QuestionEgressDisposition.ALLOWED
    assert decision.minimized_question is not None
    assert raw not in decision.minimized_question
    assert raw not in repr(slots)
    assert set(slots.values) == {"slot-1"}


def test_employee_protected_input_rejects_multiple_identifiers() -> None:
    with pytest.raises(InvalidProtectedValue):
        EmployeeProtectedValueExtractor().extract(
            "查询员工，员工编号 ABCDE，身份证号 FGHIJ",
            request_id="request-1",
        )


def test_employee_catalog_contains_only_logical_detail_contract() -> None:
    definition, snapshot = _snapshot()
    catalog = build_business_planner_catalog((definition,), snapshot)
    text = str(catalog.payload).casefold()

    assert catalog.snapshot_id == snapshot.snapshot_id
    assert "employee.detail" in text
    assert "employee_identifier" in text
    for marker in ("/employees", "http", "sql", "index", "role_", "jwt", "idcardno"):
        assert marker not in text
