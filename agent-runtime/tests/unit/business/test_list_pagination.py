from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import pytest

from agent_runtime.adapters.employee.definition import employee_search_definition
from agent_runtime.adapters.transaction.definition import transaction_list_search_definition
from agent_runtime.business.contracts import BusinessActionDefinition, BusinessActionSettings, InvalidBusinessArguments
from agent_runtime.business.provider import BusinessSupportFactory
from agent_runtime.business.query_plan import (
    DefaultBusinessQueryPlanValidator,
    ExactBusinessQueryPlanDecoder,
    InvalidBusinessQueryPlan,
    ProtectedValueSlots,
    RequestProtectedValueBinder,
    ValidatedBusinessQueryPlan,
)
from agent_runtime.business.settings import (
    BusinessConfigurationError,
    BusinessConfigurationSnapshot,
    BusinessConfigurationSource,
    BusinessGlobalSettings,
    BusinessQueryConfigurationLoader,
    BusinessServiceBinding,
)
from agent_runtime.capability_api.contracts import (
    ActionCandidate,
    CapabilityRegistrationCandidate,
    CapabilityStatus,
    InvalidCapabilityArguments,
    JsonValue,
)
from agent_runtime.core.execution import CapabilityExecutionCore
from agent_runtime.core.registry import CapabilityRegistryBuilder
from agent_runtime.settings import CoreRuntimeSettings
from tests.helpers import ResultHandler, scope, success_result


@pytest.fixture(params=(employee_search_definition(), transaction_list_search_definition()))
def definition(request: pytest.FixtureRequest) -> BusinessActionDefinition[Any, Any, Any, Any]:
    return request.param


def _arguments(action: str) -> dict[str, JsonValue]:
    field, value = ("position", "工程师") if action == "employee.search" else ("trans_type", "PAY")
    return {
        "filters": ({"field": field, "operator": "eq", "value": value},),
        "page": 1000,
        "size": 50,
        "sorts": (),
    }


def _plan(action: str, arguments: dict[str, JsonValue]):
    return ExactBusinessQueryPlanDecoder().decode({
        "domain": action.split(".")[0],
        "action": action,
        "arguments": {
            **arguments,
            "filters": tuple(
                {**item, "value": {"literal": item["value"]}}
                for item in arguments["filters"]
            ),
        },
    })


def _snapshot(action: str, settings: BusinessActionSettings) -> BusinessConfigurationSnapshot:
    return BusinessConfigurationSnapshot(
        global_settings=BusinessGlobalSettings(),
        actions=((action, settings),),
        service_bindings=(),
        snapshot_id="pagination-boundary",
    )


def test_maximum_pagination_reaches_wire_through_validated_plan(definition) -> None:
    action = definition.descriptor.capability_id
    settings = dict(BusinessQueryConfigurationLoader.load_v3_resource().actions)[action]
    validated = DefaultBusinessQueryPlanValidator((definition,)).validate(
        _plan(action, _arguments(action)), snapshot=_snapshot(action, settings)
    )
    assert isinstance(validated, ValidatedBusinessQueryPlan)
    candidate = RequestProtectedValueBinder().bind(
        validated, slots=ProtectedValueSlots(request_id="req-1", values={}), request_id="req-1"
    )
    selected = definition.argument_validator.validate(candidate.arguments)
    wire = definition.wire_codec.encode(definition.request_mapper.map(selected, settings))
    assert wire.json_body is not None
    payload = json.loads(wire.json_body.content)
    assert payload["size"] == 50
    if action == "employee.search":
        assert payload["from"] == 49950
    else:
        assert payload["page"] == 1000


@pytest.mark.parametrize(
    "key,value",
    (
        ("page", 0), ("page", 1001), ("page", 2147483648),
        ("page", True), ("page", 1.0), ("page", "1"),
        ("size", 0), ("size", 51), ("size", 2147483648),
        ("size", True), ("size", 1.0), ("size", "1"),
    ),
)
@pytest.mark.asyncio
async def test_invalid_pagination_is_rejected_at_model_and_core_entries(
    definition, key: str, value: JsonValue
) -> None:
    action = definition.descriptor.capability_id
    arguments = _arguments(action)
    arguments[key] = value
    with pytest.raises(InvalidBusinessQueryPlan):
        _plan(action, arguments)
    with pytest.raises(InvalidCapabilityArguments):
        definition.argument_validator.validate(arguments)

    handler = ResultHandler(success_result())
    core_settings = CoreRuntimeSettings()
    registry = CapabilityRegistryBuilder(core_settings).build((
        CapabilityRegistrationCandidate(
            descriptor=definition.descriptor,
            enabled=True,
            argument_validator=definition.argument_validator,
            handler=handler,
        ),
    ))
    result = await CapabilityExecutionCore(registry, core_settings).execute(
        candidate=ActionCandidate(capability_id=action, arguments=arguments), scope=scope()
    )
    assert result.status is CapabilityStatus.INVALID_ARGUMENT
    assert handler.calls == 0


@pytest.mark.parametrize("limit,value", (("max_page", 999), ("max_page_size", 49), ("max_result_count", 49)))
def test_configuration_still_tightens_pagination(definition, limit: str, value: int) -> None:
    action = definition.descriptor.capability_id
    settings = dict(BusinessQueryConfigurationLoader.load_v3_resource().actions)[action]
    narrowed = replace(settings, **{limit: value})
    arguments = _arguments(action)
    with pytest.raises(InvalidBusinessArguments):
        definition.request_mapper.map(definition.argument_validator.validate(arguments), narrowed)
    if limit != "max_result_count":
        with pytest.raises(InvalidBusinessQueryPlan):
            DefaultBusinessQueryPlanValidator((definition,)).validate(
                _plan(action, arguments), snapshot=_snapshot(action, narrowed)
            )


@pytest.mark.parametrize("limit,value", (("max_page", 1001), ("max_page_size", 51)))
def test_configuration_cannot_expand_code_pagination_limits(definition, limit: str, value: int) -> None:
    source = BusinessQueryConfigurationLoader.load_v3_resource()
    action = definition.descriptor.capability_id
    settings = dict(source.actions)[action]
    config = BusinessConfigurationSource(
        global_settings=BusinessGlobalSettings(),
        actions=((action, settings),),
        service_bindings=(BusinessServiceBinding(
            service_key=definition.service_key, base_endpoint="http://127.0.0.1:9210"
        ),),
    )
    factory = BusinessSupportFactory()
    factory.build(definitions=(definition,), config=config, core_max_domain_result_bytes=262144)
    invalid = replace(config, actions=((action, replace(settings, **{limit: value})),))
    error_code = "business.invalid_page_limits" if limit == "max_page" else "business.invalid_dimension"
    with pytest.raises(BusinessConfigurationError, match=error_code):
        factory.build(
            definitions=(definition,), config=invalid, core_max_domain_result_bytes=262144
        )
