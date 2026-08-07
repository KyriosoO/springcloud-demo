from __future__ import annotations

import pytest

from agent_runtime.adapters.employee.action_resolver import EmployeeDetailLocalActionResolver
from agent_runtime.adapters.employee.definition import employee_detail_definition
from agent_runtime.capability_api.action_resolution import (
    LocalActionInvalidReason,
    LocalActionResolutionKind,
)
from agent_runtime.capability_api.contracts import InvalidCapabilityArguments


@pytest.mark.parametrize(
    "intent",
    ("查询员工详情", "查询员工", "查看员工详情", "查看员工", "员工详情"),
)
def test_each_employee_intent_produces_the_single_identifier_candidate(intent: str) -> None:
    result = EmployeeDetailLocalActionResolver().resolve(f"{intent} 员工标识=ABCDE")

    assert result.kind is LocalActionResolutionKind.CANDIDATE
    assert result.arguments == {"employee_identifier": "ABCDE"}
    assert result.reason is None


@pytest.mark.parametrize("label", ("员工标识", "员工编号", "身份证号", "证件号"))
@pytest.mark.parametrize("operator", ("为", "是", "=", ":", "："))
def test_employee_labels_and_operators_are_finite_and_deterministic(label: str, operator: str) -> None:
    result = EmployeeDetailLocalActionResolver().resolve(
        f"请帮我　查看员工详情，　{label}　{operator}　ABCDE？"
    )

    assert result.kind is LocalActionResolutionKind.CANDIDATE
    assert result.arguments == {"employee_identifier": "ABCDE"}


@pytest.mark.parametrize(
    ("question", "reason"),
    [
        ("查询员工详情", LocalActionInvalidReason.MISSING_REQUIRED),
        ("查询员工详情 员工标识=", LocalActionInvalidReason.MISSING_REQUIRED),
        ("查询员工详情 部门=研发", LocalActionInvalidReason.UNSUPPORTED_CLAUSE),
        ("查询员工详情,,员工标识=ABCDE", LocalActionInvalidReason.UNSUPPORTED_CLAUSE),
        ("查询员工详情 员工标识=ABCDE，身份证号=FGHIJ", LocalActionInvalidReason.DUPLICATE_ARGUMENT),
        ("查询员工详情 员工标识=ABCDE；查询列表", LocalActionInvalidReason.UNSUPPORTED_CLAUSE),
        ("查询员工详情 员工标识=ABCDE？继续", LocalActionInvalidReason.UNSUPPORTED_CLAUSE),
        ("查询员工详情 员工标识=ABCDE并删除", LocalActionInvalidReason.UNSUPPORTED_CLAUSE),
        ("查询员工详情 员工标识=ABCDE？？", LocalActionInvalidReason.UNSUPPORTED_CLAUSE),
        ("查询员工详情     员工标识=ABCDE", LocalActionInvalidReason.UNSUPPORTED_CLAUSE),
        ("查询员工详情 员工标识=ABC\nDE", LocalActionInvalidReason.MALFORMED_VALUE),
    ],
)
def test_employee_recognized_but_invalid_questions_fail_closed(
    question: str,
    reason: LocalActionInvalidReason,
) -> None:
    result = EmployeeDetailLocalActionResolver().resolve(question)

    assert result.kind is LocalActionResolutionKind.INVALID
    assert result.reason is reason
    assert result.arguments is None


def test_employee_non_domain_question_is_no_match() -> None:
    result = EmployeeDetailLocalActionResolver().resolve("查询交易 交易号=T001")

    assert result.kind is LocalActionResolutionKind.NO_MATCH
    assert result.arguments is None
    assert result.reason is None


def test_employee_delimiter_accepts_zero_or_four_spaces_and_rejects_five() -> None:
    resolver = EmployeeDetailLocalActionResolver()

    assert resolver.resolve("查询员工详情员工标识=ABCDE").kind is LocalActionResolutionKind.CANDIDATE
    assert resolver.resolve("查询员工详情    员工标识=ABCDE").kind is LocalActionResolutionKind.CANDIDATE
    rejected = resolver.resolve("查询员工详情     员工标识=ABCDE")
    assert rejected.kind is LocalActionResolutionKind.INVALID
    assert rejected.reason is LocalActionInvalidReason.UNSUPPORTED_CLAUSE


def test_employee_candidate_still_passes_the_real_validator() -> None:
    definition = employee_detail_definition()
    valid = EmployeeDetailLocalActionResolver().resolve("员工详情 证件号:ABCDE")
    invalid_for_execution = EmployeeDetailLocalActionResolver().resolve("员工详情 证件号:AB CDE")

    assert valid.arguments is not None
    assert definition.argument_validator.validate(valid.arguments).employee_identifier == "ABCDE"
    assert invalid_for_execution.kind is LocalActionResolutionKind.CANDIDATE
    assert invalid_for_execution.arguments is not None
    with pytest.raises(InvalidCapabilityArguments):
        definition.argument_validator.validate(invalid_for_execution.arguments)
