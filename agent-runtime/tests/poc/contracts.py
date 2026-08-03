from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PocCallRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    ordinal: int = Field(ge=1, le=36)
    case_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")
    repetition: int = Field(ge=1, le=3)
    decision: str = Field(min_length=1, max_length=128)
    structure_valid: bool
    expected_match: bool
    grounding_accepted: bool | None = None
    public_unsupported_claim: bool = False
    latency_ms: int = Field(ge=0, le=120000)
    usage_total_tokens: int | None = Field(default=None, ge=0)


class DeepSeekPocResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal[1] = 1
    task: Literal["action_selection", "answer_generation"]
    model: Literal["deepseek-v4-pro"] = "deepseek-v4-pro"
    task_version: str = Field(min_length=1, max_length=64)
    started_at_utc: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")
    finished_at_utc: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")
    authorized_call_limit: int = Field(ge=1, le=30)
    attempted_calls: int = Field(ge=0, le=30)
    completed_calls: int = Field(ge=0, le=30)
    total_tokens: int = Field(ge=0)
    conclusion: Literal["passed", "failed", "incomplete"]
    structure_valid_calls: int = Field(ge=0, le=30)
    expected_calls: int = Field(ge=0, le=30)
    grounding_expected_calls: int | None = Field(default=None, ge=0, le=6)
    invalid_execution_count: Literal[0] = 0
    public_unsupported_claims: Literal[0] = 0
    calls: tuple[PocCallRecord, ...]

    @model_validator(mode="after")
    def validate_counts(self) -> "DeepSeekPocResult":
        if self.attempted_calls != len(self.calls):
            raise ValueError("poc.call_count_mismatch")
        if self.completed_calls > self.attempted_calls:
            raise ValueError("poc.completed_count_invalid")
        if self.structure_valid_calls > self.completed_calls or self.expected_calls > self.completed_calls:
            raise ValueError("poc.metric_count_invalid")
        expected_limit = 30 if self.task == "action_selection" else 6
        if self.authorized_call_limit != expected_limit:
            raise ValueError("poc.authorized_limit_invalid")
        if self.task == "action_selection" and self.grounding_expected_calls is not None:
            raise ValueError("poc.action_grounding_forbidden")
        if self.task == "answer_generation" and self.grounding_expected_calls is None:
            raise ValueError("poc.answer_grounding_required")
        return self


def write_append_only_result(result: DeepSeekPocResult, *, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stem = result.started_at_utc.replace(":", "").replace("-", "").replace(".", "")
    target = directory / f"{result.task}-{stem}.json"
    encoded = result.model_dump_json(indent=2).encode("utf-8") + b"\n"
    with target.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    decoded = DeepSeekPocResult.model_validate_json(target.read_bytes(), strict=True)
    if decoded != result:
        raise RuntimeError("poc.result_round_trip_failed")
    return target


def parse_result(raw: bytes) -> DeepSeekPocResult:
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except _DuplicateKey as exc:
        raise ValueError("poc.result_duplicate_key") from exc
    except (TypeError, ValueError) as exc:
        raise ValueError("poc.result_json_invalid") from exc
    return DeepSeekPocResult.model_validate(_freeze_lists(value), strict=True)


class _DuplicateKey(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey
        result[key] = value
    return result


def _freeze_lists(value: object) -> object:
    if isinstance(value, list):
        return tuple(_freeze_lists(item) for item in value)
    if isinstance(value, dict):
        return {key: _freeze_lists(item) for key, item in value.items()}
    return value
