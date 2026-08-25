from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from typing import cast

import pytest

from agent_runtime.adapters.transaction.codec import (
    TransactionListSearchArgumentValidator,
    TransactionListSearchRequestMapper,
)
from agent_runtime.adapters.transaction.definition import transaction_list_search_definition
from agent_runtime.adapters.transaction.provider import TransactionListDomainProvider
from agent_runtime.business.contracts import (
    BusinessActionSettings,
    BusinessAnswerMode,
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


def _settings() -> BusinessActionSettings:
    return dict(BusinessQueryConfigurationLoader.load_v2_resource().actions)[
        "transaction.search"
    ]


def _arguments() -> dict[str, JsonValue]:
    return {
        "filters": (
            {"field": "trans_type", "operator": "contains", "value": "PAY"},
            {"field": "amount", "operator": "gt", "value": "100.10"},
            {"field": "amount", "operator": "lt", "value": "500.00"},
            {
                "field": "trans_date",
                "operator": "gt",
                "value": "2026-08-25T09:00:00+08:00",
            },
        ),
        "page": 2,
        "size": 20,
        "sorts": ({"field": "trans_date", "direction": "DESC"},),
    }


def test_transaction_list_definition_exposes_only_four_code_bound_fields() -> None:
    definition = transaction_list_search_definition()

    assert definition.descriptor.capability_id == "transaction.search"
    assert definition.answer_mode is BusinessAnswerMode.STRUCTURED_ONLY
    assert definition.local_action_resolver is None
    assert definition.filter_field_ids_by_code == {
        "trans_id", "trans_type", "trans_date", "amount"
    }
    assert definition.sort_field_ids_by_code == {
        "trans_id", "trans_type", "trans_date", "amount"
    }
    assert {field.field_id for field in definition.field_definitions} == {
        "trans_id", "trans_type", "trans_date", "amount"
    }
    assert definition.contract_limits.fixed_page is None


def test_transaction_list_maps_independent_operators_date_decimal_and_second_page() -> None:
    selected = TransactionListSearchArgumentValidator().validate(_arguments())
    request = TransactionListSearchRequestMapper().map(selected, _settings())

    assert request.page == 2
    assert request.size == 20
    assert request.condition.trans_type_contains == "PAY"
    assert request.condition.amount_gt == Decimal("100.10")
    assert request.condition.amount_lt == Decimal("500.00")
    assert request.condition.trans_date_gt == datetime.fromisoformat(
        "2026-08-25T09:00:00+08:00"
    )
    assert request.sorts[0].field == "trans_date"


@pytest.mark.parametrize(
    "field,operator,value",
    (
        ("trans_type_contains", "contains", "PAY"),
        ("trans_date_gt", "gt", "2026-08-25T09:00:00+08:00"),
        ("amount_gt", "gt", "100.00"),
        ("trans_id", "contains", "TXN-0001"),
        ("trans_type", "gt", "PAY"),
        ("trans_type", "contains", "%PAY"),
        ("trans_date", "gt", "2026-08-25T09:00:00"),
        ("trans_date", "gt", "2026-08-25T09:00:00.001+08:00"),
        ("trans_date", "gt", "今天"),
        ("amount", "gt", "100.001"),
        ("amount", "gt", "1e2"),
        ("amount", "gt", "-0.00"),
        ("amount", "gt", cast(JsonValue, 100.25)),
    ),
)
def test_transaction_list_rejects_unsupported_fields_operators_and_wire_types(
    field: str,
    operator: str,
    value: JsonValue,
) -> None:
    arguments = _arguments()
    arguments["filters"] = ({"field": field, "operator": operator, "value": value},)

    with pytest.raises(InvalidCapabilityArguments):
        TransactionListSearchArgumentValidator().validate(arguments)


@pytest.mark.parametrize(
    "filters",
    (
        (),
        (
            {"field": "trans_type", "operator": "eq", "value": "PAY"},
            {"field": "trans_type", "operator": "contains", "value": "PAY"},
        ),
        (
            {"field": "amount", "operator": "eq", "value": "100.00"},
            {"field": "amount", "operator": "lt", "value": "200.00"},
        ),
        (
            {"field": "amount", "operator": "gt", "value": "200.00"},
            {"field": "amount", "operator": "lt", "value": "100.00"},
        ),
        (
            {
                "field": "trans_date", "operator": "gt",
                "value": "2026-08-25T09:00:00+08:00",
            },
            {
                "field": "trans_date", "operator": "lt",
                "value": "2026-08-25T01:00:00+00:00",
            },
        ),
    ),
)
def test_transaction_list_rejects_empty_conflicting_and_non_open_ranges(
    filters: tuple[dict[str, JsonValue], ...],
) -> None:
    arguments = _arguments()
    arguments["filters"] = filters

    with pytest.raises(InvalidCapabilityArguments):
        TransactionListSearchArgumentValidator().validate(arguments)


@pytest.mark.parametrize(
    "key,value",
    (
        ("page", 0), ("page", 1001), ("page", True),
        ("size", 0), ("size", 51), ("size", "20"),
        ("sorts", ({"field": "unknown", "direction": "ASC"},)),
        ("sorts", ({"field": "amount", "direction": "DOWN"},)),
        ("sorts", (
            {"field": "amount", "direction": "ASC"},
            {"field": "amount", "direction": "DESC"},
        )),
    ),
)
def test_transaction_list_rejects_pagination_and_sort_violations(
    key: str, value: JsonValue
) -> None:
    arguments = _arguments()
    arguments[key] = value

    with pytest.raises(InvalidCapabilityArguments):
        TransactionListSearchArgumentValidator().validate(arguments)


def test_transaction_list_mapper_enforces_narrowed_configuration_without_fallback() -> None:
    selected = TransactionListSearchArgumentValidator().validate(_arguments())
    settings = _settings()
    for restricted in (
        replace(settings, max_page=1),
        replace(settings, max_page_size=10),
        replace(settings, max_decimal_abs="50.00"),
        replace(settings, max_decimal_scale=1),
        replace(settings, allowed_filter_field_ids=("trans_type",)),
        replace(settings, allowed_sort_field_ids=("amount",)),
        replace(settings, allowed_sort_directions=("ASC",)),
        replace(settings, code_contract_version="transaction-search-plan-v1"),
    ):
        with pytest.raises(InvalidBusinessArguments):
            TransactionListSearchRequestMapper().map(selected, restricted)


def test_transaction_list_mapper_enforces_configured_absolute_date_window() -> None:
    arguments = _arguments()
    arguments["filters"] = (
        {
            "field": "trans_date", "operator": "gt",
            "value": "2026-08-25T09:00:00+08:00",
        },
        {
            "field": "trans_date", "operator": "lt",
            "value": "2026-08-27T09:00:00+08:00",
        },
    )
    selected = TransactionListSearchArgumentValidator().validate(arguments)

    with pytest.raises(InvalidBusinessArguments):
        TransactionListSearchRequestMapper().map(
            selected, replace(_settings(), max_time_range_days=1)
        )


def test_transaction_list_provider_assembles_only_v2_action_and_snapshot() -> None:
    provider = TransactionListDomainProvider(
        settings=_settings(),
        service_binding=BusinessServiceBinding(
            service_key=BusinessServiceKey("mq-procedure-service"),
            base_endpoint="http://127.0.0.1:8182",
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

    assert tuple(action.definition.code_contract_version for action in support.actions) == (
        "transaction-search-plan-v2",
    )
