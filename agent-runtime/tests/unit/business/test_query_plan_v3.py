from __future__ import annotations

from dataclasses import replace

import pytest

from agent_runtime.capability_api.contracts import JsonObject
from agent_runtime.adapters.employee.codec import (
    EmployeeSearchArgumentValidator,
    EmployeeSearchRequestMapper,
)
from agent_runtime.adapters.employee.definition import employee_search_definition
from agent_runtime.business.query_plan import (
    BusinessQueryPlan,
    DefaultBusinessQueryPlanValidator,
    ExactBusinessQueryPlanDecoder,
    InvalidBusinessQueryPlan,
    InvalidProtectedValue,
    ProtectedValueSlots,
    RequestProtectedValueBinder,
    ValidatedBusinessQueryPlan,
)
from agent_runtime.business.settings import (
    BusinessConfigurationSnapshot,
    BusinessGlobalSettings,
    BusinessQueryConfigurationLoader,
)


def _snapshot() -> BusinessConfigurationSnapshot:
    settings = dict(BusinessQueryConfigurationLoader.load_v3_resource().actions)[
        "employee.search"
    ]
    return BusinessConfigurationSnapshot(
        global_settings=BusinessGlobalSettings(),
        actions=(("employee.search", settings),),
        service_bindings=(),
        snapshot_id="snapshot-v3",
    )


def _decode(filters: tuple[JsonObject, ...]) -> BusinessQueryPlan:
    return ExactBusinessQueryPlanDecoder().decode(
        {
            "domain": "employee",
            "action": "employee.search",
            "arguments": {
                "filters": filters,
                "page": 1,
                "size": 20,
                "sorts": (),
            },
        }
    )


def test_value_refs_prefix_any_is_typed_and_bound_to_an_immutable_tuple() -> None:
    plan = _decode(
        (
            {
                "field": "chinese_name",
                "operator": "prefix_any",
                "value": {"value_refs": ("slot-1", "slot-2")},
            },
        )
    )
    validated = DefaultBusinessQueryPlanValidator(
        (employee_search_definition(),)
    ).validate(plan, snapshot=_snapshot())
    assert isinstance(validated, ValidatedBusinessQueryPlan)

    candidate = RequestProtectedValueBinder().bind(
        validated,
        slots=ProtectedValueSlots(
            request_id="request-1",
            values={"slot-1": "杨", "slot-2": "王"},
            logical_fields={"slot-1": "chinese_name", "slot-2": "chinese_name"},
        ),
        request_id="request-1",
    )

    assert candidate.arguments["filters"] == (
        {"field": "chinese_name", "operator": "prefix_any", "value": ("杨", "王")},
    )


def test_value_refs_reject_duplicates_missing_slots_and_cross_field_binding() -> None:
    with pytest.raises(InvalidBusinessQueryPlan):
        _decode(
            (
                {
                    "field": "chinese_name",
                    "operator": "prefix_any",
                    "value": {"value_refs": ("slot-1", "slot-1")},
                },
            )
        )

    plan = _decode(
        (
            {
                "field": "chinese_name",
                "operator": "prefix_any",
                "value": {"value_refs": ("slot-1", "slot-2")},
            },
        )
    )
    validated = DefaultBusinessQueryPlanValidator(
        (employee_search_definition(),)
    ).validate(plan, snapshot=_snapshot())
    assert isinstance(validated, ValidatedBusinessQueryPlan)
    with pytest.raises(InvalidProtectedValue):
        RequestProtectedValueBinder().bind(
            validated,
            slots=ProtectedValueSlots(
                request_id="request-1",
                values={"slot-1": "杨", "slot-2": "上海市测试路"},
                logical_fields={
                    "slot-1": "chinese_name",
                    "slot-2": "contact_address",
                },
            ),
            request_id="request-1",
        )


def test_operator_shapes_and_same_field_combination_fail_closed() -> None:
    validator = DefaultBusinessQueryPlanValidator((employee_search_definition(),))
    accepted = _decode(
        (
            {
                "field": "chinese_name",
                "operator": "prefix",
                "value": {"value_ref": "slot-1"},
            },
            {
                "field": "chinese_name",
                "operator": "contains",
                "value": {"value_ref": "slot-2"},
            },
        )
    )
    assert isinstance(validator.validate(accepted, snapshot=_snapshot()), ValidatedBusinessQueryPlan)

    rejected = _decode(
        (
            {
                "field": "chinese_name",
                "operator": "prefix_any",
                "value": {"value_ref": "slot-1"},
            },
        )
    )
    with pytest.raises(InvalidBusinessQueryPlan):
        validator.validate(rejected, snapshot=_snapshot())

    unsupported_combination = _decode(
        (
            {
                "field": "chinese_name",
                "operator": "contains",
                "value": {"value_ref": "slot-1"},
            },
            {
                "field": "chinese_name",
                "operator": "eq",
                "value": {"value_ref": "slot-2"},
            },
        )
    )
    with pytest.raises(InvalidBusinessQueryPlan):
        validator.validate(unsupported_combination, snapshot=_snapshot())


def test_region_aliases_validate_and_map_to_existing_contains_any_contract() -> None:
    plan = _decode(
        (
            {
                "field": "contact_address",
                "operator": "contains_any",
                "value": {"literal": ("上海市", "浙江省")},
            },
        )
    )
    assert isinstance(
        DefaultBusinessQueryPlanValidator((employee_search_definition(),)).validate(
            plan, snapshot=_snapshot()
        ),
        ValidatedBusinessQueryPlan,
    )

    settings = dict(_snapshot().actions)["employee.search"]
    wire = EmployeeSearchRequestMapper().map(
        EmployeeSearchArgumentValidator().validate(
            {
                "filters": (
                    {
                        "field": "contact_address",
                        "operator": "contains_any",
                        "value": ("上海市", "浙江省"),
                    },
                ),
                "page": 1,
                "size": 20,
                "sorts": (),
            }
        ),
        settings,
    )
    assert wire.filters[0].field == "contactAddress"
    assert wire.filters[0].operator == "containsAny"
    assert wire.filters[0].values == ("上海", "浙江")

    unknown_region = _decode(
        (
            {
                "field": "contact_address",
                "operator": "contains",
                "value": {"literal": "任意自由文本"},
            },
        )
    )
    with pytest.raises(InvalidBusinessQueryPlan):
        DefaultBusinessQueryPlanValidator((employee_search_definition(),)).validate(
            unknown_region, snapshot=_snapshot()
        )

    invalid_wire_input = EmployeeSearchArgumentValidator().validate(
        {
            "filters": (
                {
                    "field": "contact_address",
                    "operator": "contains",
                    "value": "任意自由文本",
                },
            ),
            "page": 1,
            "size": 20,
            "sorts": (),
        }
    )
    with pytest.raises(ValueError, match="business.invalid_arguments"):
        EmployeeSearchRequestMapper().map(
            invalid_wire_input,
            dict(_snapshot().actions)["employee.search"],
        )


def test_v3_configuration_can_tighten_same_field_combinations() -> None:
    snapshot = _snapshot()
    settings = dict(snapshot.actions)["employee.search"]
    fields = tuple(
        replace(item, allowed_operator_combinations=())
        if item.logical_name == "chinese_name"
        else item
        for item in settings.query_fields
    )
    restricted = replace(
        snapshot,
        actions=(("employee.search", replace(settings, query_fields=fields)),),
    )
    plan = _decode(
        (
            {
                "field": "chinese_name",
                "operator": "prefix",
                "value": {"value_ref": "slot-1"},
            },
            {
                "field": "chinese_name",
                "operator": "contains",
                "value": {"value_ref": "slot-2"},
            },
        )
    )
    with pytest.raises(InvalidBusinessQueryPlan):
        DefaultBusinessQueryPlanValidator((employee_search_definition(),)).validate(
            plan, snapshot=restricted
        )

    typed = EmployeeSearchArgumentValidator().validate(
        {
            "filters": (
                {"field": "chinese_name", "operator": "prefix", "value": "杨"},
                {"field": "chinese_name", "operator": "contains", "value": "明"},
            ),
            "page": 1,
            "size": 20,
            "sorts": (),
        }
    )
    with pytest.raises(ValueError, match="business.invalid_arguments"):
        EmployeeSearchRequestMapper().map(
            typed,
            replace(settings, query_fields=fields),
        )
