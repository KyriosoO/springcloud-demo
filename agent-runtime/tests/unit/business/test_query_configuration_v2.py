from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any, cast

import pytest

from agent_runtime.business.contracts import BusinessInputExposure, BusinessQueryOperator
from agent_runtime.business.settings import BusinessConfigurationError, BusinessQueryConfigurationLoader


def _payload() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            files("agent_runtime.business")
            .joinpath("business-query.v2.json")
            .read_text(encoding="utf-8")
        ),
    )


def _load(payload: dict[str, Any]) -> object:
    return BusinessQueryConfigurationLoader.load_v2_bytes(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )


def test_unified_config_binds_three_actions_and_code_bound_field_matrices() -> None:
    configuration = BusinessQueryConfigurationLoader.load_v2_resource()
    actions = dict(configuration.actions)

    assert configuration.config_version == "business-query-v2"
    assert set(actions) == {
        "employee.search",
        "employee.semantic_search",
        "transaction.search",
    }
    employee_fields = {item.logical_name: item for item in actions["employee.search"].query_fields}
    assert employee_fields["contact_address"].service_field == "contactAddress"
    assert employee_fields["contact_address"].input_exposure is (
        BusinessInputExposure.LITERAL_OR_PROTECTED_REF
    )
    assert BusinessQueryOperator.CONTAINS in employee_fields["contact_address"].allowed_operators
    assert actions["employee.search"].keyword_service_field_ids == (
        "contactAddress", "chineseName", "idCardNo"
    )
    assert actions["employee.semantic_search"].semantic_profile_id == "employee-default-v1"
    assert actions["transaction.search"].max_decimal_scale == 2
    assert actions["transaction.search"].max_page == 1000
    assert actions["transaction.search"].allowed_sort_field_ids == (
        "trans_id", "trans_type", "trans_date", "amount"
    )


def test_unconfigured_field_is_unreachable_through_generic_allowlist() -> None:
    payload = _payload()
    action = payload["domains"][0]["actions"][0]
    unconfigured = deepcopy(action["fields"][0])
    unconfigured["logical_name"] = "work_base_si"
    unconfigured["service_field"] = "workBaseSi"
    action["fields"].append(unconfigured)

    with pytest.raises(BusinessConfigurationError, match="business.invalid_query_fields"):
        _load(payload)


@pytest.mark.parametrize(
    "mutation,error",
    (
        (lambda payload: payload.__setitem__("endpoint", "http://not-allowed"),
         "business.configuration_schema_invalid"),
        (lambda payload: payload.__setitem__("config_version", "business-query-v1"),
         "business.configuration_version_mismatch"),
        (lambda payload: payload["domains"][0]["actions"][0]["fields"][0].__setitem__(
            "service_field", "differentField"
        ), "business.invalid_query_fields"),
        (lambda payload: payload["domains"][0]["actions"][0]["fields"][0].__setitem__(
            "allowed_operators", ["gt"]
        ), "business.invalid_query_fields"),
        (lambda payload: payload["domains"][0]["actions"][0]["fields"][1].__setitem__(
            "input_exposure", "literal"
        ), "business.invalid_query_fields"),
        (lambda payload: payload["domains"][0]["actions"][0]["keyword"].__setitem__(
            "service_field_ids", ["contactAddress", "position", "idCardNo"]
        ), "business.invalid_keyword_policy"),
        (lambda payload: payload["domains"][0]["actions"][0]["fields"][1].__setitem__(
            "model_visible", True
        ), "business.invalid_model_fields"),
        (lambda payload: payload["domains"][1]["actions"][0]["decimal"].__setitem__(
            "max_scale", 3
        ), "business.configuration_schema_invalid"),
        (lambda payload: payload["domains"][1]["actions"][0]["time"].__setitem__(
            "allow_relative_dates", True
        ), "business.invalid_dimension"),
        (lambda payload: payload["domains"][0]["actions"][1].__setitem__(
            "semantic_profile_id", "unregistered-profile"
        ), "business.configuration_profile_invalid"),
    ),
)
def test_unified_config_rejects_contract_or_exposure_expansion(
    mutation: Any,
    error: str,
) -> None:
    payload = _payload()
    mutation(payload)
    with pytest.raises(BusinessConfigurationError, match=error):
        _load(payload)


def test_unified_config_rejects_duplicate_json_keys_and_numeric_float() -> None:
    with pytest.raises(BusinessConfigurationError, match="business.configuration_duplicate_key"):
        BusinessQueryConfigurationLoader.load_v2_bytes(
            b'{"config_version":"business-query-v2","config_version":"duplicate"}'
        )
    with pytest.raises(BusinessConfigurationError, match="business.configuration_schema_invalid"):
        BusinessQueryConfigurationLoader.load_v2_bytes(b'{"value":1.25}')


def test_disabled_domain_disables_its_actions_without_expanding_another_domain() -> None:
    payload = _payload()
    payload["domains"][0]["enabled"] = False
    configuration = BusinessQueryConfigurationLoader.load_v2_bytes(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )
    actions = dict(configuration.actions)
    assert not actions["employee.search"].enabled
    assert not actions["employee.semantic_search"].enabled
    assert actions["transaction.search"].enabled
