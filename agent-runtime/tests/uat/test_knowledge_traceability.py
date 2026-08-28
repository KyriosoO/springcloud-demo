from __future__ import annotations

from copy import deepcopy
from collections.abc import Callable
from typing import Any

import pytest

from tests.uat.knowledge_traceability import (
    load_knowledge_uat_traceability,
    validate_knowledge_uat_traceability,
)


def test_knowledge_functional_uat_traceability_closes_all_37_cases() -> None:
    value = load_knowledge_uat_traceability()
    cases = value["cases"]
    assert isinstance(cases, list)
    assert len(cases) == 37
    assert {item["status"] for item in cases} == {"passed"}
    assert value["authority"] == "UAT_01 v1.12"
    assert value["functionalConclusion"] == "passed"
    effectiveness = value["effectiveness"]
    assert isinstance(effectiveness, dict)
    assert effectiveness["latestValid"]["conclusion"] == "partially_effective"
    assert effectiveness["latestExecution"]["conclusion"] == "invalid_run"
    assert effectiveness["latestExecution"]["state"] == "failed_unconsumed"
    assert effectiveness["currentVersion"] == {
        "summaryTaskVersion": "4",
        "evidenceStatus": "missing",
    }


@pytest.mark.parametrize(
    "mutation,error",
    (
        (lambda value: value["cases"].pop(), "knowledge_uat_traceability.cases_invalid"),
        (
            lambda value: value["cases"][0].__setitem__("status", "passed_without_evidence"),
            "knowledge_uat_traceability.case_invalid",
        ),
        (
            lambda value: value["cases"][0]["evidenceRefs"][0].__setitem__(
                "symbol", "missing_test_symbol"
            ),
            "knowledge_uat_traceability.symbol_missing",
        ),
        (
            lambda value: value["cases"][0].__setitem__("question", "forbidden"),
            "knowledge_uat_traceability.case_shape_invalid",
        ),
        (
            lambda value: value["effectiveness"]["latestValid"].__setitem__(
                "conclusion", "effective"
            ),
            "knowledge_uat_traceability.latest_valid_invalid",
        ),
        (
            lambda value: value["effectiveness"]["latestExecution"].__setitem__(
                "state", "passed"
            ),
            "knowledge_uat_traceability.latest_execution_invalid",
        ),
        (
            lambda value: value["effectiveness"]["currentVersion"].__setitem__(
                "evidenceStatus", "measured"
            ),
            "knowledge_uat_traceability.current_version_invalid",
        ),
    ),
)
def test_knowledge_uat_traceability_fails_closed(
    mutation: Callable[[dict[str, Any]], None], error: str
) -> None:
    value = deepcopy(load_knowledge_uat_traceability())
    mutation(value)
    with pytest.raises(ValueError, match=error):
        validate_knowledge_uat_traceability(value)
