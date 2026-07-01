from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError


def _load(directory: Path, name: str) -> dict[str, Any]:
    fixture = directory / "negative" / name
    if not fixture.is_file():
        pytest.fail(f"negative fixture not found: {fixture}")
    return json.loads(fixture.read_text(encoding="utf-8"))


def _assert_rejected(
    models: ModuleType,
    directory: Path,
    fixture: str,
    expected_token: str,
) -> None:
    with pytest.raises(ValidationError) as raised:
        TypeAdapter(models.PlanOutcome).validate_python(_load(directory, fixture))
    details = json.dumps(raised.value.errors(), ensure_ascii=False, default=str)
    assert expected_token in details, (
        f"{fixture} failed for an unrelated reason: {raised.value.errors()}"
    )


def test_unknown_plan_kind_rejected(
    candidate_models: ModuleType, candidate_fixture_dir: Path
) -> None:
    _assert_rejected(
        candidate_models, candidate_fixture_dir, "unknown-plan-kind.json", "planKind"
    )


def test_unknown_operator_rejected(
    candidate_models: ModuleType, candidate_fixture_dir: Path
) -> None:
    _assert_rejected(
        candidate_models, candidate_fixture_dir, "unknown-operator.json", "operator"
    )


def test_extra_field_rejected(
    candidate_models: ModuleType, candidate_fixture_dir: Path
) -> None:
    _assert_rejected(
        candidate_models, candidate_fixture_dir, "extra-field.json", "extraField"
    )


def test_missing_query_rejected(
    candidate_models: ModuleType, candidate_fixture_dir: Path
) -> None:
    _assert_rejected(
        candidate_models, candidate_fixture_dir, "missing-query.json", "query"
    )


def test_discriminator_mismatch_rejected(
    candidate_models: ModuleType, candidate_fixture_dir: Path
) -> None:
    payload = _load(candidate_fixture_dir, "discriminator-mismatch.json")
    with pytest.raises(ValidationError) as raised:
        TypeAdapter(candidate_models.PlanOutcome).validate_python(payload)
    details = json.dumps(raised.value.errors(), ensure_ascii=False, default=str)
    assert "aggregate" in details or "query" in details, raised.value.errors()
