from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.evaluation.knowledge.bootstrap import build_from_environment
from tests.evaluation.knowledge.contracts import EvaluationRunResult
from tests.evaluation.knowledge.run_evaluation import EvaluationRunError, load_dataset, run, validate_result_bytes


DATASET = Path(__file__).with_name("synthetic_questions.v1.jsonl")
SCHEMA = Path(__file__).parent / "schemas" / "evaluation-result-v1.schema.json"


def _walk(value: object) -> list[str]:
    keys: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            keys.append(key)
            keys.extend(_walk(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(_walk(child))
    return keys


def test_synthetic_dataset_is_strict_and_not_representative(tmp_path: Path) -> None:
    version, digest, cases = load_dataset(DATASET)
    assert version == "synthetic_questions.v1"
    assert len(digest) == 64
    assert len(cases) == 1
    assert cases[0].case_id == "synthetic-tax-policy-001"

    unauthorized = tmp_path / "representative_questions.v1.jsonl"
    unauthorized.write_bytes(DATASET.read_bytes())
    with pytest.raises(EvaluationRunError, match="representative_dataset_not_authorized"):
        load_dataset(unauthorized)


@pytest.mark.parametrize(
    "line",
    (
        b'{"case_id":"a","case_id":"b"}',
        b'{"case_id":"a","question":"q","category":"tax_policy","expected_domain_ids":[],"expected_answerability":"answerable","relevant_document_ids":[],"required_evidence_ids":[],"must_preserve_tokens":[],"extra":1}',
    ),
)
def test_dataset_rejects_duplicate_and_unknown_fields(tmp_path: Path, line: bytes) -> None:
    path = tmp_path / "synthetic_invalid.jsonl"
    path.write_bytes(line)
    with pytest.raises(EvaluationRunError, match="dataset_invalid"):
        load_dataset(path)


def test_committed_json_schema_is_closed_at_every_object_definition() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    for definition in schema["$defs"].values():
        if definition.get("type") == "object":
            assert definition["additionalProperties"] is False
            assert set(definition["required"]) == set(definition["properties"])
    failure_schema = json.loads((SCHEMA.parent / "evaluation-failure-v1.schema.json").read_text(encoding="utf-8"))
    assert failure_schema["additionalProperties"] is False
    assert set(failure_schema["required"]) == set(failure_schema["properties"])


@pytest.mark.asyncio
async def test_stub_result_is_schema_typed_invalid_run_without_sensitive_slots(tmp_path: Path) -> None:
    bootstrap = build_from_environment(environ={})
    output = tmp_path / "run"
    result = await run(
        dataset_path=DATASET,
        output_dir=output,
        snapshot=bootstrap.snapshot,
        executors=bootstrap.executors,
        fixture=bootstrap.fixture,
    )
    raw = (output / "result.json").read_bytes()
    validated = EvaluationRunResult.model_validate_json(raw)
    assert validated == result
    assert result.provider_mode == "stub"
    assert result.conclusion == "invalid_run"
    assert result.case_results[0].primary.model_call_counts.core_answer == 0
    assert result.case_results[0].rewrite_ablation.model_call_counts.rewrite == 0
    forbidden = {"question", "selectedQuery", "content", "quote", "title", "url", "notes", "jwt", "subject"}
    assert forbidden.isdisjoint(_walk(json.loads(raw)))

    value = json.loads(raw)
    value["unexpected"] = True
    with pytest.raises(ValidationError):
        EvaluationRunResult.model_validate(value)

    duplicate = raw.replace(b'{"schemaVersion":1,', b'{"schemaVersion":1,"schemaVersion":1,', 1)
    with pytest.raises(EvaluationRunError, match="schema_invalid"):
        validate_result_bytes(duplicate)
