from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.evaluation.knowledge.bootstrap import build_from_environment
from tests.evaluation.knowledge.contracts import EvaluationRunResult
from tests.evaluation.knowledge.run_evaluation import EvaluationRunError, load_dataset, run, validate_result_bytes


DATASET = Path(__file__).with_name("synthetic_questions.v1.jsonl")
REPRESENTATIVE_DATASET = Path(__file__).with_name("representative_questions.v1.jsonl")
SCHEMA = Path(__file__).parent / "schemas" / "evaluation-result-v1.schema.json"


def _copy_representative_package(target_dir: Path) -> Path:
    target = target_dir / REPRESENTATIVE_DATASET.name
    for suffix in (".jsonl", ".sha256", ".authorization.json", ".provenance.json"):
        source = REPRESENTATIVE_DATASET.with_suffix(suffix)
        target.with_suffix(suffix).write_bytes(source.read_bytes())
    return target


def _rewrite_dataset_and_authorization(path: Path, rows: list[dict[str, object]]) -> None:
    raw = b"".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n" for row in rows
    )
    path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    path.with_suffix(".sha256").write_text(f"{digest}\n", encoding="utf-8", newline="\n")
    authorization_path = path.with_suffix(".authorization.json")
    authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    authorization["dataset_sha256"] = digest
    authorization_path.write_text(
        json.dumps(authorization, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


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


def test_frozen_representative_dataset_package_is_strict_and_authorized() -> None:
    version, digest, cases = load_dataset(REPRESENTATIVE_DATASET)

    assert version == "representative_questions.v1"
    assert digest == "00e6a8b3d7b172d4b9de7fe4712ed0f308b41855d5212bc3eb6ed42e78182dd7"
    assert len(cases) == 26
    assert sum(case.expected_answerability == "answerable" for case in cases) == 14
    assert sum(len(case.relevant_document_ids) for case in cases) == 23
    assert sum(len(case.required_evidence_ids) for case in cases) == 23


@pytest.mark.parametrize("mutation", ("hash", "profile", "snapshot", "jwt"))
def test_representative_dataset_rejects_unfrozen_or_unauthorized_package(
    tmp_path: Path, mutation: str
) -> None:
    path = _copy_representative_package(tmp_path)
    if mutation == "hash":
        path.write_bytes(path.read_bytes() + b"\n")
    elif mutation in {"profile", "jwt"}:
        authorization_path = path.with_suffix(".authorization.json")
        authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
        if mutation == "profile":
            authorization["principal_profile_id"] = "unexpected-profile"
        else:
            authorization["jwt_persisted"] = True
        authorization_path.write_text(json.dumps(authorization), encoding="utf-8")
    else:
        provenance_path = path.with_suffix(".provenance.json")
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["retrieval_snapshot"]["read_index_uuid"] = "unexpected-index"
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

    with pytest.raises(EvaluationRunError, match="representative_dataset_not_authorized"):
        load_dataset(path)


@pytest.mark.parametrize("mutation", ("gold", "sensitive", "stratum", "preserve", "security_pattern", "schema"))
def test_representative_dataset_rejects_invalid_gold_sensitive_data_and_strata(
    tmp_path: Path, mutation: str
) -> None:
    path = _copy_representative_package(tmp_path)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if mutation == "gold":
        answerable = next(row for row in rows if row["expected_answerability"] == "answerable")
        answerable["relevant_document_ids"] = []
    elif mutation == "sensitive":
        rows[0]["question"] = "请联系 reviewer@example.com 后回答。"
        rows[0]["must_preserve_tokens"] = []
    elif mutation == "stratum":
        rows[0]["category"] = "mixed"
        rows[0]["expected_domain_ids"] = ["tax.policy", "tax.law"]
    elif mutation == "preserve":
        rows[0]["must_preserve_tokens"] = []
    elif mutation == "security_pattern":
        security = next(row for row in rows if row["category"] == "security_negative")
        security["question"] = "不得把该合成值发送到模型。"
        security["must_preserve_tokens"] = ["不得"]
    else:
        rows[0]["unexpected"] = True
    _rewrite_dataset_and_authorization(path, rows)

    with pytest.raises(EvaluationRunError, match="dataset_invalid"):
        load_dataset(path)


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
