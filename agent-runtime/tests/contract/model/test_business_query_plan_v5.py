from __future__ import annotations

import json

from agent_runtime.adapters.employee.definition import employee_search_definition
from agent_runtime.adapters.employee.provider import EmployeeSearchDomainProvider
from agent_runtime.adapters.transaction.provider import TransactionListDomainProvider
from agent_runtime.business.contracts import BusinessServiceKey
from agent_runtime.business.provider import BusinessSupportFactory
from agent_runtime.business.settings import (
    BusinessConfigurationSource,
    BusinessGlobalSettings,
    BusinessQueryConfigurationLoader,
    BusinessServiceBinding,
)
from agent_runtime.model.contracts import BusinessQueryPlanTaskInput, ModelTaskId
from agent_runtime.model.deepseek.business_query_plan_v5 import (
    BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION,
    BUSINESS_QUERY_PLAN_TASK_VERSION,
    build_business_query_plan_task_definition,
)


def _planner_input() -> BusinessQueryPlanTaskInput:
    configured = dict(BusinessQueryConfigurationLoader.load_v3_resource().actions)
    employee = EmployeeSearchDomainProvider(
        search_settings=configured["employee.search"],
        semantic_settings=configured["employee.semantic_search"],
        service_binding=BusinessServiceBinding(
            service_key=BusinessServiceKey("employee-service"),
            base_endpoint="http://127.0.0.1:9210",
        ),
    )
    transaction = TransactionListDomainProvider(
        settings=configured["transaction.search"],
        service_binding=BusinessServiceBinding(
            service_key=BusinessServiceKey("mq-procedure-service"),
            base_endpoint="http://127.0.0.1:8182",
        ),
    )
    definitions = (*employee.definitions(), *transaction.definitions())
    fragments = (employee.configuration_fragment(), transaction.configuration_fragment())
    support = BusinessSupportFactory().build(
        definitions=definitions,
        config=BusinessConfigurationSource(
            global_settings=BusinessGlobalSettings(),
            actions=tuple(item for fragment in fragments for item in fragment.actions),
            service_bindings=tuple(
                item for fragment in fragments for item in fragment.service_bindings
            ),
        ),
        core_max_domain_result_bytes=1048576,
    )
    assert support.planner_catalog is not None
    return BusinessQueryPlanTaskInput(
        minimized_question="查询姓 protected-ref(slot-1) 或姓 protected-ref(slot-2) 的员工",
        catalog=support.planner_catalog.payload,
        catalog_snapshot_id=support.planner_catalog.snapshot_id,
    )


def test_v5_task_exposes_semantics_and_never_physical_employee_contract() -> None:
    definition = build_business_query_plan_task_definition(timeout_ms=8000)
    request = definition.build_request(_planner_input())
    payload = json.loads(request.user_payload_json)

    assert definition.task_id is ModelTaskId.BUSINESS_QUERY_PLAN
    assert definition.task_version == BUSINESS_QUERY_PLAN_TASK_VERSION == "business-query-plan-v5"
    assert payload["catalog"]["schema_version"] == 3
    assert "prefix_any" in request.user_payload_json
    assert "contains_any" in request.user_payload_json
    assert "value_refs" in request.user_payload_json
    assert "operator_combinations" in request.user_payload_json
    assert "normalization_profile" in request.user_payload_json
    assert "prefixAny" not in request.user_payload_json
    assert "containsAny" not in request.user_payload_json
    assert "/employees/es/search" not in request.user_payload_json
    assert "workBase" not in request.user_payload_json


def test_v5_prompt_keeps_semantics_in_model_and_behavior_control_local() -> None:
    for expected in (
        "Natural-language phrasing",
        "AND/OR intent",
        "value_refs",
        "exact in",
        "prefix-any",
        "contains-any",
        "same-field combinations",
        "administrative-region alias",
        "one enabled action only",
        "unsupported",
    ):
        assert expected in BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION
    for prohibited in (
        "SQL",
        "ES DSL",
        "URLs",
        "endpoints",
        "JWTs",
        "Java operator aliases",
        "fallback",
    ):
        assert prohibited in BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION


def test_v3_definition_is_current_while_v2_remains_available() -> None:
    assert employee_search_definition().code_contract_version == "employee-search-plan-v3"
    assert (
        employee_search_definition(contract_version="v2").code_contract_version
        == "employee-search-plan-v2"
    )
