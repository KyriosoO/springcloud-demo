from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from agent_runtime.adapters.employee.definition import employee_detail_definition
from agent_runtime.adapters.employee.settings import EmployeeAdapterSettings
from agent_runtime.adapters.transaction.definition import transaction_search_definition
from agent_runtime.adapters.transaction.settings import TransactionAdapterSettings
from agent_runtime.capability_api.contracts import JsonObject, canonical_json_bytes
from agent_runtime.business.contracts import (
    BusinessCombinationRule,
    BusinessCombinationRuleKind,
    BusinessInputExposure,
    BusinessQueryFieldDefinition,
    BusinessQueryFieldSettings,
    BusinessQueryOperator,
    BusinessQueryValueType,
    BusinessServiceKey,
    BusinessTextPolicyId,
    BusinessActionDefinition,
)
from agent_runtime.business.planner_catalog import build_business_planner_catalog
from agent_runtime.business.query_plan import (
    DefaultBusinessQueryPlanValidator,
    ExactBusinessQueryPlanDecoder,
    InvalidBusinessQueryPlan,
    InvalidProtectedValue,
    ProtectedValueSlots,
    RequestProtectedValueBinder,
    UnsupportedBusinessQueryPlan,
    ValidatedBusinessQueryPlan,
)
from agent_runtime.business.settings import (
    BusinessConfigurationError,
    BusinessConfigurationSnapshot,
    BusinessConfigurationSource,
    BusinessGlobalSettings,
    BusinessServiceBinding,
    BusinessSettingsValidator,
)


Definition = BusinessActionDefinition[Any, Any, Any, Any]


def _definitions() -> tuple[Definition, Definition]:
    employee = replace(
        employee_detail_definition(),
        local_action_resolver=None,
        query_fields=(
            BusinessQueryFieldDefinition(
                logical_name="employee_identifier",
                model_safe_description="当前请求中单一员工标识的受保护引用",
                value_type=BusinessQueryValueType.IDENTIFIER,
                allowed_operators=frozenset({BusinessQueryOperator.EQ}),
                input_exposure=BusinessInputExposure.PROTECTED_REF,
                required=True,
            ),
        ),
        code_contract_version="employee-detail-plan-v1",
        service_contract_ref="employee-detail-v1",
    )
    transaction = replace(
        transaction_search_definition(),
        local_action_resolver=None,
        query_fields=(
            BusinessQueryFieldDefinition(
                logical_name="trans_type",
                model_safe_description="Transaction type exact token",
                value_type=BusinessQueryValueType.TEXT,
                allowed_operators=frozenset({BusinessQueryOperator.EQ}),
                input_exposure=BusinessInputExposure.MODEL_LITERAL,
                required=False,
                max_text_chars=128,
                text_policy_id=BusinessTextPolicyId.SAFE_TOKEN,
            ),
            BusinessQueryFieldDefinition(
                logical_name="amount_gt",
                model_safe_description="Exact decimal lower bound",
                value_type=BusinessQueryValueType.DECIMAL,
                allowed_operators=frozenset({BusinessQueryOperator.GT}),
                input_exposure=BusinessInputExposure.MODEL_LITERAL,
                required=False,
                allow_negative=True,
            ),
            BusinessQueryFieldDefinition(
                logical_name="size",
                model_safe_description="Maximum rows on fixed first page",
                value_type=BusinessQueryValueType.INTEGER,
                allowed_operators=frozenset({BusinessQueryOperator.EQ}),
                input_exposure=BusinessInputExposure.MODEL_LITERAL,
                required=False,
                minimum_integer=1,
                maximum_integer=50,
            ),
            BusinessQueryFieldDefinition(
                logical_name="sorts",
                model_safe_description="Bounded logical sort list",
                value_type=BusinessQueryValueType.SORT_LIST,
                allowed_operators=frozenset({BusinessQueryOperator.EQ}),
                input_exposure=BusinessInputExposure.MODEL_LITERAL,
                required=False,
            ),
        ),
        combination_rules=(
            BusinessCombinationRule(
                rule_id="transaction-filter-at-least-one",
                kind=BusinessCombinationRuleKind.AT_LEAST_ONE,
                field_names=("trans_type", "amount_gt"),
            ),
        ),
        contract_limits=replace(
            transaction_search_definition().contract_limits,
            max_decimal_abs="9999999999999999.99",
            max_decimal_scale=2,
            fixed_page=1,
            allowed_sort_directions=frozenset({"ASC", "DESC"}),
            max_sort_items=2,
        ),
        code_contract_version="transaction-search-plan-v1",
        service_contract_ref="transaction-search-v1",
    )
    return employee, transaction


def _snapshot() -> tuple[tuple[Definition, Definition], BusinessConfigurationSnapshot]:
    employee, transaction = _definitions()
    employee_action = replace(
        EmployeeAdapterSettings.from_env({}).action,
        enabled=True,
        config_version="employee-detail-config-v1",
        code_contract_version="employee-detail-plan-v1",
        service_contract_ref="employee-detail-v1",
        query_fields=(
            BusinessQueryFieldSettings(
                logical_name="employee_identifier",
                enabled=True,
                model_safe_description="当前请求中单一员工标识的受保护引用",
                allowed_operators=(BusinessQueryOperator.EQ,),
                required=True,
            ),
        ),
    )
    transaction_action = replace(
        TransactionAdapterSettings.from_env({}).action,
        enabled=True,
        config_version="transaction-search-config-v1",
        code_contract_version="transaction-search-plan-v1",
        service_contract_ref="transaction-search-v1",
        query_fields=(
            BusinessQueryFieldSettings(
                logical_name="trans_type",
                enabled=True,
                model_safe_description="Transaction type exact token",
                allowed_operators=(BusinessQueryOperator.EQ,),
                required=False,
                max_text_chars=128,
            ),
            BusinessQueryFieldSettings(
                logical_name="amount_gt",
                enabled=True,
                model_safe_description="Exact decimal lower bound",
                allowed_operators=(BusinessQueryOperator.GT,),
                required=False,
            ),
            BusinessQueryFieldSettings(
                logical_name="size",
                enabled=True,
                model_safe_description="Maximum rows on fixed first page",
                allowed_operators=(BusinessQueryOperator.EQ,),
                required=False,
            ),
            BusinessQueryFieldSettings(
                logical_name="sorts",
                enabled=True,
                model_safe_description="Bounded logical sort list",
                allowed_operators=(BusinessQueryOperator.EQ,),
                required=False,
            ),
        ),
        combination_rule_ids=("transaction-filter-at-least-one",),
        max_decimal_abs="9999999999999999.99",
        max_decimal_scale=2,
        fixed_page=1,
        allowed_sort_directions=("ASC", "DESC"),
        max_sort_items=2,
    )
    source = BusinessConfigurationSource(
        global_settings=BusinessGlobalSettings(),
        actions=(
            ("employee.detail", employee_action),
            ("transaction.search", transaction_action),
        ),
        service_bindings=(
            BusinessServiceBinding(
                service_key=BusinessServiceKey("employee-service"),
                base_endpoint="http://employee.test",
            ),
            BusinessServiceBinding(
                service_key=BusinessServiceKey("mq-procedure-service"),
                base_endpoint="http://transaction.test",
            ),
        ),
    )
    definitions = (employee, transaction)
    snapshot = BusinessSettingsValidator().validate(
        definitions,
        source,
        core_max_domain_result_bytes=1048576,
    )
    return definitions, snapshot


def test_exact_decode_validate_bind_and_unsupported_terminal() -> None:
    definitions, snapshot = _snapshot()
    decoder = ExactBusinessQueryPlanDecoder()
    validator = DefaultBusinessQueryPlanValidator(definitions)
    plan = decoder.decode(
        {
            "domain": "employee",
            "action": "employee.detail",
            "arguments": {
                "employee_identifier": {"value_ref": "slot-1"},
            },
        }
    )

    validated = validator.validate(plan, snapshot=snapshot)

    assert isinstance(validated, ValidatedBusinessQueryPlan)
    slots = ProtectedValueSlots(request_id="request-1", values={"slot-1": "ABCDE"})
    candidate = RequestProtectedValueBinder().bind(
        validated,
        slots=slots,
        request_id="request-1",
    )
    assert candidate.capability_id == "employee.detail"
    assert candidate.arguments == {"employee_identifier": "ABCDE"}
    assert "ABCDE" not in repr(slots)
    with pytest.raises(TypeError):
        hash(slots)

    unsupported = validator.validate(
        decoder.decode(
            {
                "domain": "employee",
                "action": "unsupported",
                "arguments": {},
            }
        ),
        snapshot=snapshot,
    )
    assert isinstance(unsupported, UnsupportedBusinessQueryPlan)


@pytest.mark.parametrize(
    "payload",
    (
        {"domain": "employee", "action": "employee.detail", "arguments": {}, "extra": 1},
        {"domain": "transaction", "action": "transaction.search", "arguments": {"amount_gt": {"literal": 1.5}}},
        {"domain": "transaction", "action": "transaction.search", "arguments": {"sql": {"literal": "x"}}},
        {"domain": "employee", "action": "employee.detail", "arguments": {"employee_identifier": {"literal": "ABCDE"}}},
    ),
)
def test_invalid_plans_fail_before_binding(payload: object) -> None:
    definitions, snapshot = _snapshot()
    decoder = ExactBusinessQueryPlanDecoder()
    validator = DefaultBusinessQueryPlanValidator(definitions)
    if not isinstance(payload, dict):
        raise AssertionError("fixture must be an object")
    try:
        plan = decoder.decode(payload)
    except InvalidBusinessQueryPlan:
        return
    with pytest.raises(InvalidBusinessQueryPlan):
        validator.validate(plan, snapshot=snapshot)


def test_transaction_types_limits_combinations_and_sort_are_strict() -> None:
    definitions, snapshot = _snapshot()
    decoder = ExactBusinessQueryPlanDecoder()
    validator = DefaultBusinessQueryPlanValidator(definitions)
    valid = decoder.decode(
        {
            "domain": "transaction",
            "action": "transaction.search",
            "arguments": {
                "trans_type": {"literal": "PAYMENT"},
                "amount_gt": {"literal": "100.00"},
                "size": {"literal": 20},
                "sorts": {"literal": ({"field": "amount", "direction": "DESC"},)},
            },
        }
    )
    assert isinstance(
        validator.validate(valid, snapshot=snapshot),
        ValidatedBusinessQueryPlan,
    )
    invalid_arguments: tuple[JsonObject, ...] = (
        {},
        {"amount_gt": {"literal": "100.001"}},
        {"amount_gt": {"literal": "-0.00"}},
        {"trans_type": {"literal": "PAYMENT:SQL"}},
        {"trans_type": {"literal": "PAYMENT"}, "size": {"literal": 51}},
        {
            "trans_type": {"literal": "PAYMENT"},
            "sorts": {"literal": (
                {"field": "amount", "direction": "DESC"},
                {"field": "amount", "direction": "ASC"},
            )},
        },
    )
    for arguments in invalid_arguments:
        plan = decoder.decode(
            {
                "domain": "transaction",
                "action": "transaction.search",
                "arguments": arguments,
            }
        )
        with pytest.raises(InvalidBusinessQueryPlan):
            validator.validate(plan, snapshot=snapshot)


def test_missing_or_reused_protected_values_fail_closed() -> None:
    definitions, snapshot = _snapshot()
    decoder = ExactBusinessQueryPlanDecoder()
    validator = DefaultBusinessQueryPlanValidator(definitions)
    validated = validator.validate(
        decoder.decode(
            {
                "domain": "employee",
                "action": "employee.detail",
                "arguments": {"employee_identifier": {"value_ref": "slot-1"}},
            }
        ),
        snapshot=snapshot,
    )
    assert isinstance(validated, ValidatedBusinessQueryPlan)
    with pytest.raises(InvalidProtectedValue):
        RequestProtectedValueBinder().bind(
            validated,
            slots=ProtectedValueSlots(request_id="request-1", values={}),
            request_id="request-1",
        )


def test_protected_slot_binding_rejects_cross_request_context() -> None:
    definitions, snapshot = _snapshot()
    plan = ExactBusinessQueryPlanDecoder().decode(
        {
            "domain": "employee",
            "action": "employee.detail",
            "arguments": {"employee_identifier": {"value_ref": "slot-1"}},
        }
    )
    validated = DefaultBusinessQueryPlanValidator(definitions).validate(
        plan,
        snapshot=snapshot,
    )
    assert isinstance(validated, ValidatedBusinessQueryPlan)

    with pytest.raises(InvalidProtectedValue):
        RequestProtectedValueBinder().bind(
            validated,
            slots=ProtectedValueSlots(
                request_id="request-1",
                values={"slot-1": "ABCDE"},
            ),
            request_id="request-2",
        )


def test_configuration_is_narrowing_and_catalog_is_model_safe() -> None:
    definitions, snapshot = _snapshot()
    employee, transaction = definitions
    source = BusinessConfigurationSource(
        global_settings=snapshot.global_settings,
        actions=snapshot.actions,
        service_bindings=snapshot.service_bindings,
    )
    transaction_settings = source.actions[1][1]
    reordered_transaction = replace(
        transaction_settings,
        query_fields=tuple(reversed(transaction_settings.query_fields)),
        allowed_sort_directions=tuple(
            reversed(transaction_settings.allowed_sort_directions or ())
        ),
    )
    reordered_snapshot = BusinessSettingsValidator().validate(
        (transaction, employee),
        replace(
            source,
            actions=(
                ("transaction.search", reordered_transaction),
                source.actions[0],
            ),
            service_bindings=tuple(reversed(source.service_bindings)),
        ),
        core_max_domain_result_bytes=1048576,
    )
    assert reordered_snapshot.snapshot_id == snapshot.snapshot_id
    widened = replace(
        transaction_settings,
        query_fields=(
            *transaction_settings.query_fields,
            BusinessQueryFieldSettings(
                logical_name="date",
                enabled=True,
                model_safe_description="Date",
                allowed_operators=(BusinessQueryOperator.EQ,),
                required=False,
            ),
        ),
    )
    with pytest.raises(BusinessConfigurationError, match="business.invalid_query_fields"):
        BusinessSettingsValidator().validate(
            (employee, transaction),
            replace(source, actions=(source.actions[0], ("transaction.search", widened))),
            core_max_domain_result_bytes=1048576,
        )

    catalog = build_business_planner_catalog(
        (employee, transaction),
        snapshot,
    )
    material = canonical_json_bytes(catalog.payload).decode("utf-8").casefold()
    assert catalog.snapshot_id == snapshot.snapshot_id
    for forbidden in ("endpoint", "http", "sql", "dsl", "jwt", "role", "result_fields"):
        assert forbidden not in material
