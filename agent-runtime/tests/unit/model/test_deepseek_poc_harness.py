from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_runtime.model.contracts import QuestionEgressDisposition
from agent_runtime.model.input_guard import QuestionEgressGuard
from tests.poc.contracts import DeepSeekPocResult, PocCallRecord, parse_result, write_append_only_result
from tests.poc.fixtures import ACTION_CASES, ANSWER_CASES


def _result() -> DeepSeekPocResult:
    calls = tuple(
        PocCallRecord(
            ordinal=index,
            case_id=f"synthetic_{index}",
            repetition=1,
            decision="knowledge.query",
            structure_valid=True,
            expected_match=True,
            latency_ms=1,
            usage_total_tokens=1,
        )
        for index in range(1, 31)
    )
    return DeepSeekPocResult(
        task="action_selection",
        task_version="action-selection-v2",
        started_at_utc="2026-08-03T00:00:00.000000Z",
        finished_at_utc="2026-08-03T00:00:01.000000Z",
        authorized_call_limit=30,
        attempted_calls=30,
        completed_calls=30,
        total_tokens=30,
        conclusion="passed",
        structure_valid_calls=30,
        expected_calls=30,
        grounding_expected_calls=None,
        calls=calls,
    )


def test_all_live_fixtures_are_fixed_synthetic_and_allowed_by_egress_guard() -> None:
    guard = QuestionEgressGuard()
    ids = [case.case_id for case in ACTION_CASES] + [case.case_id for case in ANSWER_CASES]

    assert len(ACTION_CASES) == 10
    assert len(ANSWER_CASES) == 3
    assert len(ids) == len(set(ids))
    assert all(guard.evaluate(case.question).disposition is QuestionEgressDisposition.ALLOWED for case in ACTION_CASES)
    assert all(guard.evaluate(case.question).disposition is QuestionEgressDisposition.ALLOWED for case in ANSWER_CASES)


def test_result_contract_is_strict_closed_and_rejects_duplicate_keys() -> None:
    valid = _result().model_dump()
    with pytest.raises(ValidationError):
        DeepSeekPocResult.model_validate({**valid, "question": "must never persist"}, strict=True)
    with pytest.raises(ValueError, match="poc.result_duplicate_key"):
        parse_result(b'{"schema_version":1,"schema_version":1}')


def test_append_only_writer_refuses_overwrite_and_round_trips(tmp_path: Path) -> None:
    result = _result()
    path = write_append_only_result(result, directory=tmp_path)

    assert parse_result(path.read_bytes()) == result
    with pytest.raises(FileExistsError):
        write_append_only_result(result, directory=tmp_path)
