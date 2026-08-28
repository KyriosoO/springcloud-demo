from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from agent_runtime.adapters.employee.codec import (
    EmployeeSearchArgumentValidator,
    EmployeeSearchRequestMapper,
)
from agent_runtime.adapters.employee.definition import employee_search_definition
from agent_runtime.adapters.employee.provider import EmployeeSearchDomainProvider
from agent_runtime.adapters.employee.protected_input import EmployeeProtectedValueExtractor
from agent_runtime.business.contracts import (
    BusinessAnswerMode,
    BusinessActionSettings,
    BusinessServiceKey,
    InvalidBusinessArguments,
)
from agent_runtime.business.provider import BusinessSupportFactory
from agent_runtime.business.settings import (
    BusinessConfigurationSource,
    BusinessGlobalSettings,
    BusinessQueryConfigurationLoader,
    BusinessServiceBinding,
)
from agent_runtime.capability_api.contracts import InvalidCapabilityArguments, JsonValue
from agent_runtime.model.contracts import QuestionEgressDisposition
from agent_runtime.model.input_guard import QuestionEgressGuard


def _settings() -> BusinessActionSettings:
    return dict(BusinessQueryConfigurationLoader.load_v3_resource().actions)["employee.search"]


def _arguments() -> dict[str, JsonValue]:
    return {
        "filters": ({"field": "contact_address", "operator": "contains", "value": "上海"},),
        "page": 1,
        "size": 20,
        "sorts": (),
    }


def test_employee_search_definition_uses_only_code_bound_list_fields() -> None:
    definition = employee_search_definition()
    assert definition.descriptor.capability_id == "employee.search"
    assert definition.answer_mode is BusinessAnswerMode.STRUCTURED_ONLY
    assert definition.local_action_resolver is None
    assert {item.field_id for item in definition.field_definitions} == {
        "contact_address", "chinese_name", "employee_identifier", "member_no",
        "phone_no", "email", "position",
    }
    assert definition.required_user_field_ids == ("chinese_name", "employee_identifier")


def test_employee_search_maps_shanghai_to_existing_contact_address_filter() -> None:
    validated = EmployeeSearchArgumentValidator().validate(_arguments())
    wire = EmployeeSearchRequestMapper().map(validated, _settings())
    assert wire.from_index == 0
    assert wire.size == 20
    assert len(wire.filters) == 1
    assert wire.filters[0].field == "contactAddress"
    assert wire.filters[0].operator == "contains"
    assert wire.filters[0].value == "上海"


def test_employee_search_maps_position_eq_and_keyword_without_expanding_fields() -> None:
    arguments: dict[str, JsonValue] = {
        "filters": ({"field": "position", "operator": "eq", "value": "架构师"},),
        "page": 1,
        "size": 20,
        "sorts": (),
        "keyword": "受控关键字",
    }

    wire = EmployeeSearchRequestMapper().map(
        EmployeeSearchArgumentValidator().validate(arguments), _settings()
    )

    assert wire.filters[0].field == "position"
    assert wire.filters[0].operator == "eq"
    assert wire.filters[0].value == "架构师"
    assert wire.keyword == "受控关键字"


def test_employee_search_maps_in_values_page_and_sort_without_aggregate() -> None:
    arguments: dict[str, JsonValue] = {
        "filters": ({"field": "position", "operator": "in", "value": ("工程师", "架构师")},),
        "page": 3,
        "size": 10,
        "sorts": ({"field": "chinese_name", "direction": "DESC"},),
    }
    wire = EmployeeSearchRequestMapper().map(
        EmployeeSearchArgumentValidator().validate(arguments), _settings()
    )
    assert wire.from_index == 20
    assert wire.filters[0].values == ("工程师", "架构师")
    assert wire.sorts[0].field == "chineseName"


@pytest.mark.parametrize(
    "field,operator,value",
    (
        ("work_base_si", "contains", "上海"),
        ("undeclared_field", "eq", "上海"),
        ("employee_identifier", "contains", "ABCDE"),
        ("position", "in", ()),
        ("position", "contains", "bad\x00value"),
    ),
)
def test_employee_search_rejects_any_unconfigured_field_or_operator(
    field: str,
    operator: str,
    value: object,
) -> None:
    arguments = _arguments()
    arguments["filters"] = (
        {"field": field, "operator": operator, "value": cast(JsonValue, value)},
    )
    with pytest.raises(InvalidCapabilityArguments):
        EmployeeSearchArgumentValidator().validate(arguments)


def test_employee_search_rejects_match_all_and_restricted_configuration() -> None:
    arguments = _arguments()
    arguments["filters"] = ()
    with pytest.raises(InvalidCapabilityArguments):
        EmployeeSearchArgumentValidator().validate(arguments)

    validated = EmployeeSearchArgumentValidator().validate(_arguments())
    with pytest.raises(InvalidBusinessArguments):
        EmployeeSearchRequestMapper().map(
            validated,
            replace(_settings(), allowed_filter_field_ids=("position",)),
        )


def test_employee_search_provider_builds_one_snapshot_and_no_detail_action() -> None:
    settings = _settings()
    provider = EmployeeSearchDomainProvider(
        search_settings=settings,
        service_binding=BusinessServiceBinding(
            service_key=BusinessServiceKey("employee-service"),
            base_endpoint="http://127.0.0.1:9210",
        ),
    )
    fragment = provider.configuration_fragment()
    support = BusinessSupportFactory().build(
        definitions=provider.definitions(),
        config=BusinessConfigurationSource(
            global_settings=BusinessGlobalSettings(),
            actions=fragment.actions,
            service_bindings=fragment.service_bindings,
        ),
        core_max_domain_result_bytes=262144,
    )
    assert tuple(item.definition.descriptor.capability_id for item in support.actions) == (
        "employee.search",
    )


@pytest.mark.parametrize(
    "question,secret",
    (
        ("查询员工姓名 张三", "张三"),
        ("查询员工会员编号 MEMBER12345", "MEMBER12345"),
        ("查询员工联系电话 13800000000", "13800000000"),
        ("查询员工邮箱 demo@example.invalid", "demo@example.invalid"),
        ("查询员工联系地址 上海市测试街道", "上海市测试街道"),
    ),
)
def test_employee_search_protected_fields_are_redacted_before_model(
    question: str,
    secret: str,
) -> None:
    slots = EmployeeProtectedValueExtractor().extract(question, request_id="request-1")
    assert slots.values == {"slot-1": secret}
    decision = QuestionEgressGuard().evaluate_business(question, protected_values=slots.values)
    assert decision.disposition is QuestionEgressDisposition.ALLOWED
    assert decision.minimized_question is not None
    assert secret not in decision.minimized_question
    assert "protected-ref(slot-1)" in decision.minimized_question


def test_employee_search_safe_city_fragment_remains_model_visible() -> None:
    question = "帮我查一下在上海的员工"
    slots = EmployeeProtectedValueExtractor().extract(question, request_id="request-1")
    assert slots.values == {}
    decision = QuestionEgressGuard().evaluate_business(question, protected_values=slots.values)
    assert decision.disposition is QuestionEgressDisposition.ALLOWED
    assert decision.minimized_question is not None
    assert "上海" in decision.minimized_question
