"""Test-only finite failure projection. No IO, raw payloads, or runtime registration."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import json
import sys
from threading import Lock
from typing import cast
from unittest.mock import patch

from agent_runtime.knowledge.errors import KnowledgeInputError
from agent_runtime.model.contracts import InvalidModelOutput
from agent_runtime.model import gateway


# Exact literals, not prefixes: a malicious/unknown error code cannot become evidence.
_CODES = {
    "model.json_non_finite_number": "json_boundary",
    "model.json_duplicate_key": "json_boundary",
    "model.json_invalid_unicode": "json_boundary",
    "model.json_bytes_exceeded": "json_boundary",
    "model.json_invalid_utf8": "json_boundary",
    "model.json_type_invalid": "json_boundary",
    "model.json_invalid": "json_boundary",
    "model.json_object_required": "json_boundary",
    "model.provider_response_mismatch": "provider_response",
    "model.provider_choices_invalid": "provider_response",
    "model.provider_choice_invalid": "provider_response",
    "model.provider_finish_reason_invalid": "provider_response",
    "model.provider_message_invalid": "provider_response",
    "model.provider_content_invalid": "provider_response",
    "model.provider_tool_calls_invalid": "provider_response",
    "model.provider_tool_call_invalid": "provider_response",
    "model.provider_usage_invalid": "provider_response",
    "model.invalid_response": "model_boundary",
    "model.invalid_tool_call": "model_boundary",
    "knowledge.invalid_requirement_plan": "rewrite_decoder",
}
_CAUSES = {
    json.JSONDecodeError: "json_syntax",
    KnowledgeInputError: "semantic_contract",
    ValueError: "shape_or_enum",
    TypeError: "type_shape",
    UnicodeDecodeError: "encoding",
    UnicodeEncodeError: "encoding",
    RecursionError: "nesting",
}


@dataclass(frozen=True, slots=True)
class FailureDiagnostic:
    phase: str
    code: str
    cause: str


def project_failure(error: BaseException | None) -> FailureDiagnostic:
    """Classify existing exceptions without re-parsing, messages, args, or frame locals."""
    if type(error) is not InvalidModelOutput or type(error.code) is not str or error.code not in _CODES:
        return FailureDiagnostic("unknown", "unknown", "unknown")
    cause = "unknown"
    current = error.__cause__
    for _ in range(8):
        if current is None:
            break
        if type(current) in _CAUSES:
            cause = _CAUSES[type(current)]
            break
        if type(current) is not InvalidModelOutput:
            break  # Do not follow attributes of unknown/custom exception types.
        current = current.__cause__
    return FailureDiagnostic(_CODES[error.code], error.code, cause)


class FailureCollector:
    __slots__ = ("_records", "_active", "overflowed")

    def __init__(self) -> None:
        self._records: list[FailureDiagnostic] = []
        self._active = True
        self.overflowed = False

    @property
    def records(self) -> tuple[FailureDiagnostic, ...]:
        return tuple(self._records)

    def record(self, error: BaseException | None) -> None:
        if not self._active:
            return
        if len(self._records) == 8:
            self.overflowed = True
            return
        self._records.append(project_failure(error))


_INSTALL = Lock()
_CURRENT: ContextVar[FailureCollector | None] = ContextVar("test_model_failure_probe_v1", default=None)


@contextmanager
def observe_failures() -> Iterator[FailureCollector]:
    """One process-local installation; only the explicit caller context is observed."""
    if not _INSTALL.acquire(blocking=False):
        raise RuntimeError("failure_probe.overlapping_scope")
    collector = FailureCollector()
    token = _CURRENT.set(collector)
    original = cast(Callable[[int | None, str], None], getattr(gateway, "model_call_failed"))

    def failed(sequence: int | None, kind: str) -> None:
        current = _CURRENT.get()
        if current is not None and kind == "invalid_output":
            current.record(sys.exception())
        original(sequence, kind)

    try:
        with patch.object(gateway, "model_call_failed", failed):
            yield collector
    finally:
        collector._active = False
        _CURRENT.reset(token)
        _INSTALL.release()
