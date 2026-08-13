from __future__ import annotations

import asyncio
import json
import os
import re
from enum import StrEnum
from pathlib import Path
from typing import Awaitable, Callable, Literal, TypeVar

from pydantic import ValidationError


_SAFE_ID = re.compile(r"^[A-Za-z0-9._:/+-]{1,128}$")
_MAX_BUFFERED_EVENTS = 2048
_T = TypeVar("_T")


class LiveDiagnosticPhase(StrEnum):
    VARIANT_EXECUTION = "variant_execution"
    CAPABILITY = "capability"
    REWRITE = "rewrite"
    RETRIEVAL = "retrieval"
    EVIDENCE = "evidence"
    VARIANT_PACK = "variant_pack"


class LiveDiagnosticReason(StrEnum):
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    VALIDATION_ERROR = "validation_error"
    VALUE_ERROR = "value_error"
    RUNTIME_ERROR = "runtime_error"
    OS_ERROR = "os_error"
    UNEXPECTED_ERROR = "unexpected_error"


LiveVariant = Literal["primary", "rewrite_ablation"]


def classify_diagnostic_reason(exc: BaseException) -> LiveDiagnosticReason:
    if isinstance(exc, asyncio.CancelledError):
        return LiveDiagnosticReason.CANCELLED
    if isinstance(exc, TimeoutError):
        return LiveDiagnosticReason.TIMEOUT
    if isinstance(exc, ValidationError):
        return LiveDiagnosticReason.VALIDATION_ERROR
    if isinstance(exc, ValueError):
        return LiveDiagnosticReason.VALUE_ERROR
    if isinstance(exc, RuntimeError):
        return LiveDiagnosticReason.RUNTIME_ERROR
    if isinstance(exc, OSError):
        return LiveDiagnosticReason.OS_ERROR
    return LiveDiagnosticReason.UNEXPECTED_ERROR


class LivePhaseCheckpointJournal:
    """Append-only, content-free checkpoints for the isolated live P5 evaluator."""

    def __init__(self, *, output_dir: Path, run_id: str) -> None:
        if not _safe_identifier(run_id, max_length=64):
            raise ValueError("evaluation.live_diagnostic_run_id_invalid")
        self._output_dir = output_dir
        self._path = output_dir / "phase-checkpoints.jsonl"
        self._run_id = run_id
        self._sequence = 0
        self._buffer: list[dict[str, object]] = []
        self._persisted = False
        self._active_case_id: str | None = None
        self._active_variant: LiveVariant | None = None
        self._phase_stack: list[LiveDiagnosticPhase] = []

    @property
    def path(self) -> Path:
        return self._path

    def begin_variant(self, *, case_id: str, variant: LiveVariant) -> None:
        if self._active_case_id is not None or self._phase_stack:
            raise RuntimeError("evaluation.live_diagnostic_variant_overlap")
        if not _safe_identifier(case_id, max_length=64) or variant not in {"primary", "rewrite_ablation"}:
            raise ValueError("evaluation.live_diagnostic_context_invalid")
        self._active_case_id = case_id
        self._active_variant = variant

    def end_variant(self) -> None:
        if self._active_case_id is None or self._active_variant is None or self._phase_stack:
            raise RuntimeError("evaluation.live_diagnostic_variant_state_invalid")
        self._active_case_id = None
        self._active_variant = None

    async def run_async(self, *, phase: LiveDiagnosticPhase, operation: Awaitable[_T]) -> _T:
        self._start_phase(phase)
        try:
            result = await operation
        except BaseException as exc:
            try:
                self._finish_phase(phase=phase, status="failed", reason=classify_diagnostic_reason(exc))
            except BaseException as diagnostic_exc:
                raise exc from diagnostic_exc
            raise
        self._finish_phase(phase=phase, status="completed", reason=None)
        return result

    def run_sync(self, *, phase: LiveDiagnosticPhase, operation: Callable[[], _T]) -> _T:
        self._start_phase(phase)
        try:
            result = operation()
        except BaseException as exc:
            try:
                self._finish_phase(phase=phase, status="failed", reason=classify_diagnostic_reason(exc))
            except BaseException as diagnostic_exc:
                raise exc from diagnostic_exc
            raise
        self._finish_phase(phase=phase, status="completed", reason=None)
        return result

    def _start_phase(self, phase: LiveDiagnosticPhase) -> None:
        if not isinstance(phase, LiveDiagnosticPhase):
            raise ValueError("evaluation.live_diagnostic_phase_invalid")
        self._require_context()
        self._phase_stack.append(phase)
        try:
            self._append(phase=phase, event="started", status=None, reason=None)
        except BaseException:
            self._phase_stack.pop()
            raise

    def _finish_phase(
        self,
        *,
        phase: LiveDiagnosticPhase,
        status: Literal["completed", "failed"],
        reason: LiveDiagnosticReason | None,
    ) -> None:
        if not self._phase_stack or self._phase_stack[-1] is not phase:
            raise RuntimeError("evaluation.live_diagnostic_phase_state_invalid")
        if (status == "completed") != (reason is None):
            raise ValueError("evaluation.live_diagnostic_terminal_invalid")
        try:
            self._append(phase=phase, event="terminal", status=status, reason=reason)
        finally:
            self._phase_stack.pop()

    def _require_context(self) -> tuple[str, LiveVariant]:
        if self._active_case_id is None or self._active_variant is None:
            raise RuntimeError("evaluation.live_diagnostic_context_missing")
        return self._active_case_id, self._active_variant

    def _append(
        self,
        *,
        phase: LiveDiagnosticPhase,
        event: Literal["started", "terminal"],
        status: Literal["completed", "failed"] | None,
        reason: LiveDiagnosticReason | None,
    ) -> None:
        case_id, variant = self._require_context()
        self._sequence += 1
        value: dict[str, object] = {
            "schemaVersion": 1,
            "runId": self._run_id,
            "sequence": self._sequence,
            "caseId": case_id,
            "variant": variant,
            "phase": phase.value,
            "event": event,
        }
        if status is not None:
            value["status"] = status
        if reason is not None:
            value["reasonCode"] = reason.value
        if len(self._buffer) >= _MAX_BUFFERED_EVENTS:
            raise RuntimeError("evaluation.live_diagnostic_buffer_exhausted")
        self._buffer.append(value)
        self._flush_if_authorization_consumed()

    def _flush_if_authorization_consumed(self) -> None:
        if not self._output_dir.is_dir():
            return
        if self._persisted and not self._path.is_file():
            raise OSError("evaluation.live_diagnostic_journal_missing")
        if not self._persisted and self._path.exists():
            raise RuntimeError("evaluation.live_diagnostic_state_exists")
        if not self._buffer:
            return
        mode = "ab" if self._persisted else "xb"
        with self._path.open(mode) as stream:
            for value in self._buffer:
                encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
                stream.write(encoded + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        self._buffer.clear()
        self._persisted = True


def _safe_identifier(value: object, *, max_length: int) -> bool:
    return isinstance(value, str) and len(value) <= max_length and _SAFE_ID.fullmatch(value) is not None
