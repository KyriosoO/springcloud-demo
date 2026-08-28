from __future__ import annotations

from tests.uat.employee_nl.contracts import cases
from tests.uat.employee_nl.runner import _plan_shape_matches


def test_plan_shape_match_remains_exact_for_supported_cases() -> None:
    case = next(item for item in cases() if item.case_id == "UAT-EMP-NL-301")

    assert _plan_shape_matches(
        case,
        (
            "employee.search",
            ("chinese_name",),
            ("prefix",),
            ("value_ref",),
        ),
    )
    assert not _plan_shape_matches(
        case,
        (
            "employee.search",
            ("contact_address",),
            ("contains",),
            ("literal",),
        ),
    )


def test_unsupported_case_accepts_no_plan_shape_but_not_downstream_execution() -> None:
    case = next(item for item in cases() if item.case_id == "UAT-EMP-NL-314")

    assert case.expected_action is None
    assert case.expected_employee_calls == 0
    assert _plan_shape_matches(
        case,
        ("", (), (), ()),
    )
