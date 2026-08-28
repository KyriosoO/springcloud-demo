from __future__ import annotations

import json
from importlib.resources import files

import pytest

from agent_runtime.adapters.employee.provider import EmployeeSearchDomainProvider
from agent_runtime.adapters.transaction.provider import TransactionListDomainProvider
from agent_runtime.business.contracts import BusinessQueryOperator, BusinessServiceKey
from agent_runtime.business.provider import BusinessSupportFactory, BusinessSupportSnapshot
from agent_runtime.business.settings import (
    BusinessConfigurationError,
    BusinessConfigurationSource,
    BusinessGlobalSettings,
    BusinessQueryConfigurationLoader,
    BusinessServiceBinding,
)
from agent_runtime.model.contracts import canonical_object_json


def _support() -> BusinessSupportSnapshot:
    configured = BusinessQueryConfigurationLoader.load_v3_resource()
    actions = dict(configured.actions)
    employee = EmployeeSearchDomainProvider(
        search_settings=actions["employee.search"],
        semantic_settings=actions["employee.semantic_search"],
        service_binding=BusinessServiceBinding(
            service_key=BusinessServiceKey("employee-service"),
            base_endpoint="http://127.0.0.1:9210",
        ),
    )
    transaction = TransactionListDomainProvider(
        settings=actions["transaction.search"],
        service_binding=BusinessServiceBinding(
            service_key=BusinessServiceKey("mq-procedure-service"),
            base_endpoint="http://127.0.0.1:8182",
        ),
    )
    fragments = (employee.configuration_fragment(), transaction.configuration_fragment())
    return BusinessSupportFactory().build(
        definitions=(*employee.definitions(), *transaction.definitions()),
        config=BusinessConfigurationSource(
            global_settings=BusinessGlobalSettings(),
            actions=tuple(item for fragment in fragments for item in fragment.actions),
            service_bindings=tuple(
                item for fragment in fragments for item in fragment.service_bindings
            ),
        ),
        core_max_domain_result_bytes=1048576,
    )


def test_v3_employee_fields_are_code_bound_and_workbase_is_absent() -> None:
    configuration = BusinessQueryConfigurationLoader.load_v3_resource()
    search = dict(configuration.actions)["employee.search"]
    fields = {item.logical_name: item for item in search.query_fields}

    assert search.config_version == "business-query-v3"
    assert {"contact_address", "chinese_name", "position"}.issubset(fields)
    assert fields["contact_address"].allowed_operators == (
        BusinessQueryOperator.CONTAINS,
        BusinessQueryOperator.CONTAINS_ANY,
    )
    assert fields["contact_address"].normalization_profile == "cn-admin-region-v1"
    assert fields["chinese_name"].allowed_operator_combinations == (
        frozenset({BusinessQueryOperator.CONTAINS, BusinessQueryOperator.PREFIX}),
        frozenset({BusinessQueryOperator.EQ, BusinessQueryOperator.PREFIX}),
    )
    assert "work_base_si" not in repr(configuration)
    assert "work_base_af" not in repr(configuration)


def test_v3_catalog_exposes_logical_semantics_without_physical_contract() -> None:
    support = _support()
    catalog = support.planner_catalog
    assert catalog is not None
    encoded = canonical_object_json(catalog.payload)

    assert catalog.payload["schema_version"] == 3
    assert "prefix_any" in encoded
    assert "contains_any" in encoded
    assert "operator_contracts" in encoded
    assert "operator_combinations" in encoded
    assert "cn-admin-region-v1" in encoded
    for physical in (
        "contactAddress",
        "chineseName",
        "prefixAny",
        "containsAny",
        "/employees/es/search",
        "workBase",
    ):
        assert physical not in encoded


def test_v3_loader_rejects_unknown_normalization_and_operator_expansion() -> None:
    resource = files("agent_runtime.business").joinpath("business-query.v3.json").read_bytes()
    raw = json.loads(resource)
    contact = next(
        item
        for domain in raw["domains"]
        for action in domain["actions"]
        if action["action"] == "employee.search"
        for item in action["fields"]
        if item["logical_name"] == "contact_address"
    )
    contact["normalization_profile"] = "runtime-regex-profile"
    with pytest.raises(BusinessConfigurationError, match="business.invalid_query_fields"):
        BusinessQueryConfigurationLoader.load_v3_bytes(
            json.dumps(raw, ensure_ascii=False).encode("utf-8")
        )

    raw = json.loads(resource)
    contact = next(
        item
        for domain in raw["domains"]
        for action in domain["actions"]
        if action["action"] == "employee.search"
        for item in action["fields"]
        if item["logical_name"] == "contact_address"
    )
    contact["allowed_operators"].append("prefix")
    with pytest.raises(BusinessConfigurationError, match="business.invalid_query_fields"):
        BusinessQueryConfigurationLoader.load_v3_bytes(
            json.dumps(raw, ensure_ascii=False).encode("utf-8")
        )
