from __future__ import annotations

from decimal import Decimal

import pytest

from agent_runtime.adapters.transaction.contracts import TransactionRecord, TransactionSearchWireResponse
from agent_runtime.adapters.transaction.fields import transaction_field_definitions
from agent_runtime.adapters.transaction.normalizer import TransactionSearchResponseNormalizer
from agent_runtime.adapters.transaction.settings import TransactionAdapterSettings
from agent_runtime.business.contracts import BusinessFailureResult, BusinessNoResult, BusinessRecordsResult


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
    assert not TransactionAdapterSettings.from_env({}).action.enabled
    with pytest.raises(ValueError):
        TransactionAdapterSettings.from_env({"AGENT_TRANSACTION_SEARCH_FILTER_FIELDS": "trans_date"})
    with pytest.raises(ValueError):
        TransactionAdapterSettings.from_env({"AGENT_TRANSACTION_SEARCH_USER_FIELDS": "transaction_id_masked"})
    with pytest.raises(ValueError, match="business.transaction_settings_invalid"):
        TransactionAdapterSettings.from_env({"AGENT_TRANSACTION_SEARCH_MAX_PAGE_SIZE": "020"})
