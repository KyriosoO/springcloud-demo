from __future__ import annotations

from decimal import Decimal

import pytest

from agent_runtime.capability_api.contracts import InvalidCapabilityArguments
from agent_runtime.adapters.transaction.codec import TransactionSearchArgumentValidator, TransactionSearchRequestMapper
from agent_runtime.adapters.transaction.definition import transaction_search_definition
from agent_runtime.adapters.transaction.settings import TransactionAdapterSettings


def test_transaction_definition_contains_only_search_filters_and_no_date_or_aggregate() -> None:
    definition = transaction_search_definition()
    properties = definition.descriptor.argument_schema["properties"]
    assert set(properties) == {"trans_id", "trans_type", "trans_type_contains", "amount", "amount_gt", "amount_lt", "size", "sorts"}  # type: ignore[arg-type]
    assert "Date" not in str(properties)
    assert "aggregate" not in str(properties).casefold()
    assert definition.descriptor.capability_id == "transaction.search"


def test_amount_strings_parse_to_exact_decimal_and_mapper_uses_config_default_size() -> None:
    value = TransactionSearchArgumentValidator().validate({"amount": "100.10"})
    assert value.amount == Decimal("100.10")
    mapped = TransactionSearchRequestMapper().map(value, TransactionAdapterSettings.from_env({}).action)
    assert mapped.size == 20 and mapped.page == 1


def test_amount_accepts_scale2_and_preserves_existing_integer_digit_limit() -> None:
    value = TransactionSearchArgumentValidator().validate({"amount": "9999999999999999.99"})
    assert value.amount == Decimal("9999999999999999.99")


@pytest.mark.parametrize("value", [0, 0.1, True, None, "01", "+1", "1e2", "1.000", "0.001", "10000000000000000"])
def test_amount_rejects_non_string_or_noncanonical_values(value: object) -> None:
    with pytest.raises(InvalidCapabilityArguments):
        TransactionSearchArgumentValidator().validate({"amount": value})  # type: ignore[dict-item]


def test_filter_and_range_mutual_exclusions_fail_before_http() -> None:
    validator = TransactionSearchArgumentValidator()
    for arguments in (
        {"trans_type": "PAY", "trans_type_contains": "PAY"},
        {"amount": "1", "amount_gt": "0"},
        {"amount_gt": "2", "amount_lt": "1"},
        {"trans_type_contains": "%PAY"},
        {"trans_date": "2026-01-01"},
        {},
    ):
        with pytest.raises(InvalidCapabilityArguments):
            validator.validate(arguments)
