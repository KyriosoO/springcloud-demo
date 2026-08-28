from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any, cast

import pytest

from agent_runtime.adapters.transaction.definition import transaction_search_definition
from agent_runtime.adapters.transaction.protected_input import TransactionProtectedValueExtractor
from agent_runtime.adapters.transaction.settings import TransactionAdapterSettings
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
from agent_runtime.capability_api.contracts import InvalidCapabilityArguments, JsonObject
from agent_runtime.model.contracts import QuestionEgressDisposition
from agent_runtime.model.input_guard import QuestionEgressGuard


def _snapshot(
    env: dict[str, str] | None = None,
) -> tuple[BusinessActionDefinition[Any, Any, Any, Any], BusinessConfigurationSnapshot]:
    definition = transaction_search_definition()
    settings = TransactionAdapterSettings.from_env(env or {}).action
    action = replace(settings, enabled=True)
    snapshot = BusinessSettingsValidator().validate(
        (definition,),
        BusinessConfigurationSource(
            global_settings=BusinessGlobalSettings(),
            actions=(("transaction.search", action),),
            service_bindings=(
                BusinessServiceBinding(
                    service_key=BusinessServiceKey("mq-procedure-service"),
                    base_endpoint="http://transaction.test",
                ),
            ),
        ),
        core_max_domain_result_bytes=1048576,
    )
    return definition, snapshot


def _decode_validate(payload: dict[str, object]) -> tuple[BusinessActionDefinition[Any, Any, Any, Any], ValidatedBusinessQueryPlan]:
    definition, snapshot = _snapshot()
    result = DefaultBusinessQueryPlanValidator((definition,)).validate(
        ExactBusinessQueryPlanDecoder().decode(payload),  # type: ignore[arg-type]
        snapshot=snapshot,
    )
    assert isinstance(result, ValidatedBusinessQueryPlan)
    return definition, result


def test_transaction_literal_plan_binds_then_reuses_exact_argument_validator() -> None:
    definition, validated = _decode_validate(
        {
            "domain": "transaction",
            "action": "transaction.search",
            "arguments": {
                "trans_type": {"literal": "PAYMENT"},
                "amount_gt": {"literal": "100.00"},
                "amount_lt": {"literal": "500.00"},
                "size": {"literal": 20},
                "sorts": {"literal": ({"field": "amount", "direction": "DESC"},)},
            },
        }
    )
    candidate = RequestProtectedValueBinder().bind(
        validated,
        slots=TransactionProtectedValueExtractor().extract("查询交易类型 PAYMENT", request_id="request-1"),
        request_id="request-1",
    )
    value = definition.argument_validator.validate(candidate.arguments)

    assert candidate.capability_id == "transaction.search"
    assert value.amount_gt == Decimal("100.00")
    assert value.amount_lt == Decimal("500.00")
    assert value.size == 20
    assert value.sorts[0].field == "amount"


def test_transaction_protected_id_is_request_bound_and_never_model_visible() -> None:
    raw = "TXN-20260824-001"
    definition, validated = _decode_validate(
        {
            "domain": "transaction",
            "action": "transaction.search",
            "arguments": {"trans_id": {"value_ref": "slot-1"}},
        }
    )
    slots = TransactionProtectedValueExtractor().extract(
        f"查询交易，交易号 {raw}",
        request_id="request-1",
    )
    decision = QuestionEgressGuard().evaluate_business(
        f"查询交易，交易号 {raw}",
        protected_values=slots.values,
    )
    candidate = RequestProtectedValueBinder().bind(
        validated,
        slots=slots,
        request_id="request-1",
    )

    assert decision.disposition is QuestionEgressDisposition.ALLOWED
    assert decision.minimized_question is not None and raw not in decision.minimized_question
    assert raw not in repr(slots)
    assert definition.argument_validator.validate(candidate.arguments).trans_id == raw
    with pytest.raises(InvalidProtectedValue):
        RequestProtectedValueBinder().bind(validated, slots=slots, request_id="request-2")


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"size": {"literal": 20}},
        {"trans_id": {"literal": "TXN-1"}},
        {"trans_type": {"value_ref": "slot-1"}},
        {"trans_type": {"literal": "PAY"}, "trans_type_contains": {"literal": "PAY"}},
        {"amount": {"literal": "1"}, "amount_gt": {"literal": "0"}},
        {"amount": {"literal": "1"}, "amount_lt": {"literal": "2"}},
        {"amount": {"literal": 1}},
        {"amount": {"literal": "01"}},
        {"amount": {"literal": "1.000"}},
        {"trans_type_contains": {"literal": "%PAY"}},
        {"trans_type": {"literal": "PAY/SQL"}},
        {"trans_type": {"literal": " PAY"}},
        {"trans_type": {"literal": "PAY "}},
        {"trans_type": {"literal": "PAY"}, "size": {"literal": 51}},
        {"trans_type": {"literal": "PAY"}, "sorts": {"literal": ({"field": "date", "direction": "DESC"},)}},
        {"trans_type": {"literal": "PAY"}, "sorts": {"literal": ({"field": "amount", "direction": "DOWN"},)}},
        {"trans_type": {"literal": "PAY"}, "sorts": {"literal": ({"field": "amount", "direction": "ASC"}, {"field": "amount", "direction": "DESC"})}},
    ],
)
def test_transaction_invalid_plan_fails_before_argument_binding(arguments: dict[str, object]) -> None:
    definition, snapshot = _snapshot()
    with pytest.raises(InvalidBusinessQueryPlan):
        DefaultBusinessQueryPlanValidator((definition,)).validate(
            ExactBusinessQueryPlanDecoder().decode(
                cast(
                    JsonObject,
                    {"domain": "transaction", "action": "transaction.search", "arguments": arguments},
                )
            ),
            snapshot=snapshot,
        )


def test_transaction_range_order_remains_final_argument_validator_responsibility() -> None:
    definition, validated = _decode_validate(
        {
            "domain": "transaction",
            "action": "transaction.search",
            "arguments": {"amount_gt": {"literal": "2"}, "amount_lt": {"literal": "1"}},
        }
    )
    candidate = RequestProtectedValueBinder().bind(
        validated,
        slots=TransactionProtectedValueExtractor().extract("查询交易金额范围", request_id="request-1"),
        request_id="request-1",
    )
    with pytest.raises(InvalidCapabilityArguments):
        definition.argument_validator.validate(candidate.arguments)


@pytest.mark.parametrize("action", ["transaction.detail", "transaction.aggregate", "transaction.write"])
def test_transaction_non_search_actions_are_unsupported(action: str) -> None:
    definition, snapshot = _snapshot()
    result = DefaultBusinessQueryPlanValidator((definition,)).validate(
        ExactBusinessQueryPlanDecoder().decode(
            {"domain": "transaction", "action": action, "arguments": {}}
        ),
        snapshot=snapshot,
    )
    assert isinstance(result, UnsupportedBusinessQueryPlan)


def test_transaction_disabled_field_is_unsupported_and_catalog_is_physical_detail_free() -> None:
    definition, snapshot = _snapshot(
        {"AGENT_TRANSACTION_SEARCH_FILTER_FIELDS": "trans_type"}
    )
    result = DefaultBusinessQueryPlanValidator((definition,)).validate(
        ExactBusinessQueryPlanDecoder().decode(
            {
                "domain": "transaction",
                "action": "transaction.search",
                "arguments": {"amount": {"literal": "1.00"}},
            }
        ),
        snapshot=snapshot,
    )
    catalog = build_business_planner_catalog((definition,), snapshot)
    text = str(catalog.payload).casefold()

    assert isinstance(result, UnsupportedBusinessQueryPlan)
    assert "transaction.search" in text and "trans_type" in text
    assert "amount_gt" not in text
    for marker in ("/txn/search", "http", "sql", "index", "table", "role_", "jwt", "bigdecimal"):
        assert marker not in text


def test_transaction_protected_input_rejects_multiple_identifiers() -> None:
    with pytest.raises(InvalidProtectedValue):
        TransactionProtectedValueExtractor().extract(
            "查询交易，交易号 TXN-1，流水号 TXN-2",
            request_id="request-1",
        )


def test_business_guard_does_not_hide_a_second_unprotected_transaction_identifier() -> None:
    decision = QuestionEgressGuard().evaluate_business(
        "查询交易，交易号 TXN-1，流水号 TXN-2",
        protected_values={"slot-1": "TXN-1"},
    )

    assert decision.disposition is QuestionEgressDisposition.DENIED
