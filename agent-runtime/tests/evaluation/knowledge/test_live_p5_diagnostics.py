from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import NoReturn

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from tests.evaluation.knowledge.live_diagnostics import (
    LiveDiagnosticPhase,
    LiveDiagnosticReason,
    LivePhaseCheckpointJournal,
)


RUN_ID = "knowledge-p5-live-diagnostic-fake-01"
SAFE_KEYS = {
    "schemaVersion",
    "runId",
    "sequence",
    "caseId",
    "variant",
    "phase",
    "event",
    "status",
    "reasonCode",
}


class _StrictInteger(BaseModel):
    model_config = ConfigDict(strict=True)
    value: int


def _events(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="ascii").splitlines()]


def test_pre_authorization_checkpoints_stay_in_memory_then_flush_in_order(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    journal = LivePhaseCheckpointJournal(output_dir=output_dir, run_id=RUN_ID)
    journal.begin_variant(case_id="case-01", variant="primary")

    assert journal.run_sync(phase=LiveDiagnosticPhase.VARIANT_EXECUTION, operation=lambda: "first") == "first"
    assert not output_dir.exists()

    output_dir.mkdir()
    assert journal.run_sync(phase=LiveDiagnosticPhase.VARIANT_PACK, operation=lambda: "second") == "second"
    journal.end_variant()

    events = _events(journal.path)
    assert [item["sequence"] for item in events] == [1, 2, 3, 4]
    assert [(item["phase"], item["event"]) for item in events] == [
        ("variant_execution", "started"),
        ("variant_execution", "terminal"),
        ("variant_pack", "started"),
        ("variant_pack", "terminal"),
    ]
    assert all(set(item) <= SAFE_KEYS for item in events)
    assert all("reasonCode" not in item for item in events)
    assert all(item.get("status") in {None, "completed"} for item in events)


def _validation_error() -> ValidationError:
    try:
        _StrictInteger.model_validate({"value": "not-an-integer"})
    except ValidationError as exc:
        return exc
    raise AssertionError("validation error fixture did not fail")


@pytest.mark.parametrize(
    ("factory", "expected"),
    (
        (asyncio.CancelledError, LiveDiagnosticReason.CANCELLED),
        (lambda: TimeoutError("sensitive-timeout-detail"), LiveDiagnosticReason.TIMEOUT),
        (_validation_error, LiveDiagnosticReason.VALIDATION_ERROR),
        (lambda: ValueError("sensitive-value-detail"), LiveDiagnosticReason.VALUE_ERROR),
        (lambda: RuntimeError("sensitive-runtime-detail"), LiveDiagnosticReason.RUNTIME_ERROR),
        (lambda: OSError("sensitive-os-detail"), LiveDiagnosticReason.OS_ERROR),
        (lambda: LookupError("sensitive-unexpected-detail"), LiveDiagnosticReason.UNEXPECTED_ERROR),
    ),
)
@pytest.mark.asyncio
async def test_failure_reason_is_finite_and_original_exception_is_rethrown(
    tmp_path: Path,
    factory: object,
    expected: LiveDiagnosticReason,
) -> None:
    output_dir = tmp_path / expected.value
    output_dir.mkdir()
    journal = LivePhaseCheckpointJournal(output_dir=output_dir, run_id=RUN_ID)
    journal.begin_variant(case_id="case-02", variant="rewrite_ablation")
    exc = factory()  # type: ignore[operator]

    async def fail() -> NoReturn:
        raise exc

    with pytest.raises(type(exc)) as captured:
        await journal.run_async(phase=LiveDiagnosticPhase.CAPABILITY, operation=fail())
    journal.end_variant()

    assert captured.value is exc
    events = _events(journal.path)
    assert [item["event"] for item in events] == ["started", "terminal"]
    assert events[-1]["status"] == "failed"
    assert events[-1]["reasonCode"] == expected.value
    serialized = journal.path.read_text(encoding="ascii")
    assert "sensitive" not in serialized
    assert "traceback" not in serialized.lower()


@pytest.mark.parametrize("phase", tuple(LiveDiagnosticPhase))
@pytest.mark.asyncio
async def test_every_finite_phase_supports_fake_failure_injection(
    tmp_path: Path,
    phase: LiveDiagnosticPhase,
) -> None:
    output_dir = tmp_path / phase.value
    output_dir.mkdir()
    journal = LivePhaseCheckpointJournal(output_dir=output_dir, run_id=RUN_ID)
    journal.begin_variant(case_id="case-03", variant="primary")
    injected = RuntimeError("must-not-be-persisted")

    async def fail() -> NoReturn:
        raise injected

    with pytest.raises(RuntimeError) as captured:
        await journal.run_async(phase=phase, operation=fail())
    journal.end_variant()

    assert captured.value is injected
    events = _events(journal.path)
    assert [item["phase"] for item in events] == [phase.value, phase.value]
    assert events[-1]["reasonCode"] == "runtime_error"


@pytest.mark.asyncio
async def test_diagnostic_write_failure_does_not_replace_original_exception(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    output_dir.mkdir()
    journal = LivePhaseCheckpointJournal(output_dir=output_dir, run_id=RUN_ID)
    journal.begin_variant(case_id="case-04", variant="primary")
    original = RuntimeError("original-must-win")

    async def fail_after_removing_journal() -> NoReturn:
        journal.path.unlink()
        raise original

    with pytest.raises(RuntimeError) as captured:
        await journal.run_async(phase=LiveDiagnosticPhase.RETRIEVAL, operation=fail_after_removing_journal())
    journal.end_variant()

    assert captured.value is original
    assert isinstance(captured.value.__cause__, OSError)


def test_context_overlap_existing_journal_and_free_text_are_fail_closed(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    output_dir.mkdir()
    journal = LivePhaseCheckpointJournal(output_dir=output_dir, run_id=RUN_ID)
    journal.begin_variant(case_id="case-04", variant="primary")
    with pytest.raises(RuntimeError, match="variant_overlap"):
        journal.begin_variant(case_id="case-05", variant="primary")
    journal.end_variant()

    (output_dir / "phase-checkpoints.jsonl").write_text("immutable\n", encoding="ascii")
    second = LivePhaseCheckpointJournal(output_dir=output_dir, run_id=RUN_ID)
    second.begin_variant(case_id="case-04", variant="primary")
    with pytest.raises(RuntimeError, match="state_exists"):
        second.run_sync(phase=LiveDiagnosticPhase.VARIANT_PACK, operation=lambda: None)

    with pytest.raises(ValueError, match="run_id_invalid"):
        LivePhaseCheckpointJournal(output_dir=tmp_path / "bad", run_id="包含自由文本")
    with pytest.raises(ValueError, match="context_invalid"):
        third = LivePhaseCheckpointJournal(output_dir=tmp_path / "third", run_id=RUN_ID)
        third.begin_variant(case_id="身份证 11010519491231002X", variant="primary")
