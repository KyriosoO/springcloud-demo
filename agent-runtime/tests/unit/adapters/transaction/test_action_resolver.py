from __future__ import annotations

import inspect
from decimal import Decimal

import pytest

from agent_runtime.adapters.transaction.action_resolver import TransactionSearchLocalActionResolver
from agent_runtime.adapters.transaction.codec import TransactionSearchRequestMapper
from agent_runtime.adapters.transaction.definition import transaction_search_definition
from agent_runtime.adapters.transaction.settings import TransactionAdapterSettings
from agent_runtime.business.contracts import InvalidBusinessArguments
from agent_runtime.capability_api.action_resolution import (
    LocalActionInvalidReason,
    LocalActionResolutionKind,
)
from agent_runtime.capability_api.contracts import InvalidCapabilityArguments


@pytest.mark.parametrize(
    "intent",
    ("查询交易", "交易查询", "查询交易记录", "交易记录查询"),
)
def test_each_transaction_intent_produces_a_local_candidate(intent: str) -> None:
    result = TransactionSearchLocalActionResolver().resolve(f"{intent} 交易号=T001")

    assert result.kind is LocalActionResolutionKind.CANDIDATE
    assert result.arguments == {"trans_id": "T001"}


@pytest.mark.parametrize("separator", (",", "，", ";", "；"))
def test_transaction_clause_table_maps_to_exact_execution_arguments(separator: str) -> None:
    question = separator.join(
        (
            "查询交易 交易标识=TX-1",
            "交易类型包含PAY",
            "金额大于100.10",
            "金额<200.01",
            "条数:10",
            "排序=金额降序",
            "排序=交易号升序",
        )
    )
    result = TransactionSearchLocalActionResolver().resolve(question)

    assert result.kind is LocalActionResolutionKind.CANDIDATE
    assert result.arguments == {
        "trans_id": "TX-1",
        "trans_type_contains": "PAY",
        "amount_gt": "100.10",
        "amount_lt": "200.01",
        "size": 10,
        "sorts": (
            {"field": "amount", "direction": "DESC"},
            {"field": "trans_id", "direction": "ASC"},
        ),
    }


@pytest.mark.parametrize("operator", ("为", "是", "=", ":", "："))
def test_transaction_exact_operators_are_finite(operator: str) -> None:
    result = TransactionSearchLocalActionResolver().resolve(
        f"查询交易 交易号{operator}T001"
    )

    assert result.kind is LocalActionResolutionKind.CANDIDATE
    assert result.arguments == {"trans_id": "T001"}


@pytest.mark.parametrize(
    ("operator", "expected_key"),
    [
        ("大于", "amount_gt"),
        (">", "amount_gt"),
        ("小于", "amount_lt"),
        ("<", "amount_lt"),
        ("为", "amount"),
        ("是", "amount"),
        ("=", "amount"),
        (":", "amount"),
        ("：", "amount"),
    ],
)
def test_transaction_amount_operators_preserve_canonical_text(
    operator: str,
    expected_key: str,
) -> None:
    result = TransactionSearchLocalActionResolver().resolve(
        f"查询交易 金额{operator}100.10"
    )

    assert result.kind is LocalActionResolutionKind.CANDIDATE
    assert result.arguments == {expected_key: "100.10"}


@pytest.mark.parametrize(
    ("field", "expected_field"),
    (("交易号", "trans_id"), ("交易类型", "trans_type"), ("金额", "amount")),
)
@pytest.mark.parametrize(
    ("direction", "expected_direction"),
    (("升序", "ASC"), ("降序", "DESC")),
)
def test_transaction_sort_field_and_direction_mapping_is_closed(
    field: str,
    expected_field: str,
    direction: str,
    expected_direction: str,
) -> None:
    result = TransactionSearchLocalActionResolver().resolve(
        f"查询交易 交易号=T001，排序={field}{direction}"
    )

    assert result.kind is LocalActionResolutionKind.CANDIDATE
    assert result.arguments == {
        "trans_id": "T001",
        "sorts": ({"field": expected_field, "direction": expected_direction},),
    }


def test_transaction_structural_spaces_and_single_terminal_punctuation_are_bounded() -> None:
    valid = TransactionSearchLocalActionResolver().resolve(
        "请帮我　交易记录查询，　交易类型　是　PAY　；　金额　>　-0.10？"
    )
    invalid = TransactionSearchLocalActionResolver().resolve(
        "交易查询     交易类型=PAY"
    )

    assert valid.kind is LocalActionResolutionKind.CANDIDATE
    assert valid.arguments == {"trans_type": "PAY", "amount_gt": "-0.10"}
    assert invalid.kind is LocalActionResolutionKind.INVALID
    assert invalid.reason is LocalActionInvalidReason.UNSUPPORTED_CLAUSE


@pytest.mark.parametrize(
    ("question", "reason"),
    [
        ("查询交易", LocalActionInvalidReason.MISSING_REQUIRED),
        ("查询交易 条数=10", LocalActionInvalidReason.MISSING_REQUIRED),
        ("查询交易 排序=金额降序", LocalActionInvalidReason.MISSING_REQUIRED),
        ("查询交易 交易号=T1，交易标识=T2", LocalActionInvalidReason.DUPLICATE_ARGUMENT),
        ("查询交易 排序=金额降序，排序=金额升序，交易号=T1", LocalActionInvalidReason.DUPLICATE_ARGUMENT),
        ("查询交易 交易类型=PAY，交易类型包含PA", LocalActionInvalidReason.CONFLICTING_ARGUMENT),
        ("查询交易 金额=1.00，金额>0", LocalActionInvalidReason.CONFLICTING_ARGUMENT),
        ("查询交易 金额>2.00，金额<2.00", LocalActionInvalidReason.CONFLICTING_ARGUMENT),
        ("查询交易 金额=1.000", LocalActionInvalidReason.MALFORMED_VALUE),
        ("查询交易 金额=10000000000000000", LocalActionInvalidReason.MALFORMED_VALUE),
        ("查询交易 条数=01，交易号=T1", LocalActionInvalidReason.MALFORMED_VALUE),
        ("查询交易 日期=2026-01-01", LocalActionInvalidReason.UNSUPPORTED_CLAUSE),
        ("查询交易 聚合=金额", LocalActionInvalidReason.UNSUPPORTED_CLAUSE),
        ("查询交易 交易号=T1 OR T2", LocalActionInvalidReason.UNSUPPORTED_CLAUSE),
        ("查询交易 交易类型=PAY(REFUND)", LocalActionInvalidReason.UNSUPPORTED_CLAUSE),
        ("查询交易 金额=(1.00)", LocalActionInvalidReason.UNSUPPORTED_CLAUSE),
        ("查询交易 交易号=T1？继续", LocalActionInvalidReason.UNSUPPORTED_CLAUSE),
        ("查询交易 交易号=T1？？", LocalActionInvalidReason.UNSUPPORTED_CLAUSE),
        ("查询交易 交易号=T1,,交易类型=PAY", LocalActionInvalidReason.UNSUPPORTED_CLAUSE),
        ("查询交易 交易号=T1，", LocalActionInvalidReason.UNSUPPORTED_CLAUSE),
        ("查询交易 交易类型=PAY，REFUND", LocalActionInvalidReason.UNSUPPORTED_CLAUSE),
        ("查询交易 交易号", LocalActionInvalidReason.MISSING_REQUIRED),
        ("查询交易 交易号=", LocalActionInvalidReason.MISSING_REQUIRED),
        ("查询交易 交易号=T1\n", LocalActionInvalidReason.MALFORMED_VALUE),
    ],
)
def test_transaction_recognized_but_invalid_questions_fail_closed(
    question: str,
    reason: LocalActionInvalidReason,
) -> None:
    result = TransactionSearchLocalActionResolver().resolve(question)

    assert result.kind is LocalActionResolutionKind.INVALID
    assert result.reason is reason
    assert result.arguments is None


def test_transaction_non_domain_question_is_no_match() -> None:
    result = TransactionSearchLocalActionResolver().resolve("查询员工详情 员工标识=ABCDE")

    assert result.kind is LocalActionResolutionKind.NO_MATCH


def test_transaction_head_separator_accepts_punctuation_or_four_spaces_and_rejects_five() -> None:
    resolver = TransactionSearchLocalActionResolver()

    assert resolver.resolve("查询交易,交易号=T1").kind is LocalActionResolutionKind.CANDIDATE
    assert resolver.resolve("查询交易    交易号=T1").kind is LocalActionResolutionKind.CANDIDATE
    rejected = resolver.resolve("查询交易     交易号=T1")
    assert rejected.kind is LocalActionResolutionKind.INVALID
    assert rejected.reason is LocalActionInvalidReason.UNSUPPORTED_CLAUSE


def test_transaction_clause_count_is_bounded_before_duplicate_resolution() -> None:
    resolver = TransactionSearchLocalActionResolver()
    eight = "查询交易 " + "，".join(("交易号=T1",) * 8)
    nine = "查询交易 " + "，".join(("交易号=T1",) * 9)

    assert resolver.resolve(eight).reason is LocalActionInvalidReason.DUPLICATE_ARGUMENT
    assert resolver.resolve(nine).reason is LocalActionInvalidReason.UNSUPPORTED_CLAUSE


def test_transaction_candidate_preserves_amount_text_and_passes_real_validator_and_mapper() -> None:
    definition = transaction_search_definition()
    result = TransactionSearchLocalActionResolver().resolve(
        "查询交易 金额=100.10，条数=20，排序=金额降序"
    )

    assert result.arguments is not None
    assert result.arguments["amount"] == "100.10"
    typed = definition.argument_validator.validate(result.arguments)
    assert typed.amount == Decimal("100.10")
    mapped = TransactionSearchRequestMapper().map(
        typed,
        TransactionAdapterSettings.from_env({}).action,
    )
    assert mapped.condition.amount == Decimal("100.10")
    assert mapped.size == 20
    source = inspect.getsource(TransactionSearchLocalActionResolver)
    assert "float(" not in source
    assert "Decimal(" not in source


def test_transaction_candidate_is_rechecked_against_narrower_runtime_settings() -> None:
    definition = transaction_search_definition()
    result = TransactionSearchLocalActionResolver().resolve("查询交易 交易类型=PAY，条数=50")
    assert result.arguments is not None
    typed = definition.argument_validator.validate(result.arguments)
    narrowed = TransactionAdapterSettings.from_env(
        {"AGENT_TRANSACTION_SEARCH_MAX_PAGE_SIZE": "10"}
    ).action

    with pytest.raises(InvalidBusinessArguments):
        TransactionSearchRequestMapper().map(typed, narrowed)


def test_transaction_resolver_does_not_replace_the_final_text_validator() -> None:
    definition = transaction_search_definition()
    result = TransactionSearchLocalActionResolver().resolve(
        "查询交易 交易类型包含%PAY"
    )

    assert result.kind is LocalActionResolutionKind.CANDIDATE
    assert result.arguments is not None
    with pytest.raises(InvalidCapabilityArguments):
        definition.argument_validator.validate(result.arguments)
