from __future__ import annotations

from copy import deepcopy
from collections.abc import Callable
from typing import Any

import pytest

from tests.uat.current_traceability import (
    load_current_uat_traceability,
    validate_current_uat_traceability,
)


def test_current_uat_traceability_closes_all_35_cases_without_relabeling_history() -> None:
    value = load_current_uat_traceability()
    cases = value["cases"]
    assert isinstance(cases, list)
    assert sum(item["hasRealLlmEvidence"] is True for item in cases) == 18
    assert sum(item["hasRealLlmEvidence"] is False for item in cases) == 17
    assert {item["stage"] for item in cases} == {"public", "employee", "transaction"}
    assert value["authority"] == "UAT_00 v1.23"


@pytest.mark.parametrize(
    "mutation,error",
    (
        (lambda value: value["cases"].pop(), "uat_traceability.cases_invalid"),
        (
            lambda value: value["cases"][0].__setitem__("hasRealLlmEvidence", True),
            "uat_traceability.real_case_mismatch",
        ),
        (
            lambda value: value["cases"][0]["evidenceRefs"][0].__setitem__(
                "symbol", "missing_test_symbol"
            ),
            "uat_traceability.symbol_missing",
        ),
    ),
)
def test_current_uat_traceability_fails_closed(
    mutation: Callable[[dict[str, Any]], None], error: str
) -> None:
    value = deepcopy(load_current_uat_traceability())
    mutation(value)
    with pytest.raises(ValueError, match=error):
        validate_current_uat_traceability(value)
