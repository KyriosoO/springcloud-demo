from __future__ import annotations

from decimal import Decimal

import pytest

from agent_runtime.adapters.transaction.contracts import TransactionRecord, TransactionSearchWireResponse
from agent_runtime.adapters.transaction.fields import transaction_field_definitions
from agent_runtime.adapters.transaction.normalizer import TransactionSearchResponseNormalizer
from agent_runtime.adapters.transaction.settings import TransactionAdapterSettings
from agent_runtime.business.contracts import (
    BusinessFailureResult,
    BusinessNoResult,
    BusinessQueryOperator,
    BusinessRecordsResult,
)


def test_coverage_distinguishes_exact_and_non_exact_totals() -> None:
    normalizer = TransactionSearchResponseNormalizer()
    empty = normalizer.normalize_success(TransactionSearchWireResponse(rows=(), total=0, total_exact=True, page=1, size=20))
    assert isinstance(empty, BusinessNoResult)
    row = TransactionRecord(trans_id="T0001", trans_type="PAY", amount=Decimal("1.00"))
    non_exact = normalizer.normalize_success(TransactionSearchWireResponse(rows=(row,), total=1, total_exact=False, page=1, size=20))
    assert isinstance(non_exact, BusinessRecordsResult)
    assert non_exact.coverage.total_count is None and non_exact.coverage.truncated
    contradictory = normalizer.normalize_success(TransactionSearchWireResponse(rows=(), total=1, total_exact=True, page=1, size=20))
    assert isinstance(contradictory, BusinessFailureResult)


def test_transaction_field_catalog_omits_short_id_and_limits_model_candidates() -> None:
    definitions = transaction_field_definitions()
    short = TransactionRecord(trans_id="T001", trans_type="PAY", amount=Decimal("1"))
    assert definitions[0].extractor(short) is None
    assert {item.field_id for item in definitions if item.model_candidate_by_code} == {"transaction_type", "amount"}


def test_transaction_settings_default_disabled_and_rejects_date_or_required_field_removal() -> None:
    action = TransactionAdapterSettings.from_env({}).action
    assert not action.enabled
    assert action.config_version == "transaction-search-config-v1"
    assert action.code_contract_version == "transaction-search-plan-v1"
    assert action.service_contract_ref == "transaction-search-v1"
    assert action.max_decimal_abs == "9999999999999999.99"
    assert action.max_decimal_scale == 2
    assert action.fixed_page == 1
    assert action.allowed_sort_directions == ("ASC", "DESC")
    assert action.max_sort_items == 2
    assert tuple(item.logical_name for item in action.query_fields) == (
        "trans_id", "trans_type", "trans_type_contains", "amount", "amount_gt", "amount_lt", "size", "sorts"
    )
    assert action.query_fields[1].allowed_operators == (BusinessQueryOperator.EQ,)
    assert action.query_fields[2].allowed_operators == (BusinessQueryOperator.CONTAINS,)
    with pytest.raises(ValueError):
        TransactionAdapterSettings.from_env({"AGENT_TRANSACTION_SEARCH_FILTER_FIELDS": "trans_date"})
    with pytest.raises(ValueError):
        TransactionAdapterSettings.from_env({"AGENT_TRANSACTION_SEARCH_USER_FIELDS": "transaction_id_masked"})
    with pytest.raises(ValueError, match="business.transaction_settings_invalid"):
        TransactionAdapterSettings.from_env({"AGENT_TRANSACTION_SEARCH_MAX_PAGE_SIZE": "020"})


@pytest.mark.parametrize(
    "env",
    [
        {"AGENT_TRANSACTION_SEARCH_CODE_CONTRACT_VERSION": "transaction-search-plan-v2"},
        {"AGENT_TRANSACTION_SEARCH_SERVICE_CONTRACT_REF": "transaction-search-v2"},
        {"AGENT_TRANSACTION_SEARCH_CONFIG_VERSION": "INVALID-V1"},
        {"AGENT_TRANSACTION_SEARCH_MAX_DECIMAL_ABS": "10000000000000000"},
        {"AGENT_TRANSACTION_SEARCH_MAX_DECIMAL_SCALE": "3"},
        {"AGENT_TRANSACTION_SEARCH_FIXED_PAGE": "2"},
        {"AGENT_TRANSACTION_SEARCH_SORT_DIRECTIONS": "ASC,DOWN"},
        {"AGENT_TRANSACTION_SEARCH_MAX_SORT_ITEMS": "3"},
        {"AGENT_TRANSACTION_SEARCH_UNKNOWN": "x"},
    ],
)
def test_transaction_queryplan_settings_cannot_expand_code_or_service_contract(
    env: dict[str, str],
) -> None:
    with pytest.raises(ValueError):
        TransactionAdapterSettings.from_env(env)


def test_transaction_queryplan_settings_can_only_shrink_fields_and_limits() -> None:
    action = TransactionAdapterSettings.from_env(
        {
            "AGENT_TRANSACTION_SEARCH_FILTER_FIELDS": "trans_type",
            "AGENT_TRANSACTION_SEARCH_SORT_FIELDS": "amount",
            "AGENT_TRANSACTION_SEARCH_SORT_DIRECTIONS": "DESC",
            "AGENT_TRANSACTION_SEARCH_MAX_DECIMAL_ABS": "1000.00",
            "AGENT_TRANSACTION_SEARCH_MAX_DECIMAL_SCALE": "1",
            "AGENT_TRANSACTION_SEARCH_MAX_SORT_ITEMS": "1",
            "AGENT_TRANSACTION_SEARCH_MAX_PAGE_SIZE": "10",
        }
    ).action

    enabled = {item.logical_name for item in action.query_fields if item.enabled}
    assert enabled == {"trans_type", "size", "sorts"}
    assert action.allowed_filter_field_ids == ("trans_type",)
    assert action.allowed_sort_field_ids == ("amount",)
    assert action.allowed_sort_directions == ("DESC",)
    assert action.max_decimal_abs == "1000.00"
    assert action.max_decimal_scale == 1
    assert action.max_sort_items == 1
    assert action.max_page_size == 10
