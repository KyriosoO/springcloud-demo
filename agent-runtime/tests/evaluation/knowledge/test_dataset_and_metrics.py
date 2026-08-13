from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_runtime.knowledge.catalog import build_tax_domain_catalog
from agent_runtime.knowledge.domain_selection import DeterministicDomainSelector
from agent_runtime.model.contracts import QuestionEgressDisposition
from agent_runtime.model.input_guard import QuestionEgressGuard
from tests.evaluation.knowledge.bootstrap import build_from_environment
from tests.evaluation.knowledge.contracts import EvaluationRunResult
from tests.evaluation.knowledge.run_evaluation import EvaluationRunError, load_dataset, run, validate_result_bytes


DATASET = Path(__file__).with_name("synthetic_questions.v1.jsonl")
REPRESENTATIVE_DATASET = Path(__file__).with_name("representative_questions.v1.jsonl")
REPRESENTATIVE_DATASET_V2 = Path(__file__).with_name("representative_questions.v2.jsonl")
SCHEMA = Path(__file__).parent / "schemas" / "evaluation-result-v1.schema.json"


def _copy_representative_package(target_dir: Path, source_dataset: Path = REPRESENTATIVE_DATASET) -> Path:
    target = target_dir / source_dataset.name
    for suffix in (".jsonl", ".sha256", ".authorization.json", ".provenance.json"):
        source = source_dataset.with_suffix(suffix)
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


def test_representative_v1_package_hashes_remain_exact() -> None:
    expected = {
        ".jsonl": "00e6a8b3d7b172d4b9de7fe4712ed0f308b41855d5212bc3eb6ed42e78182dd7",
        ".authorization.json": "46312361ec52395ea4c4f7f0d7b50dd7e4f70ac5e3ed5ce844a363a06253d7db",
        ".provenance.json": "59d040c1d247fdcc4fd64896aaed76e631be3c96ccef9ce21a6113cb93029718",
        ".sha256": "e1b9073cdbadca78bfcfcbcbd0a95e1ffcb2820808e5c42a4f031dabff44e199",
    }
    assert {
        suffix: hashlib.sha256(REPRESENTATIVE_DATASET.with_suffix(suffix).read_bytes()).hexdigest()
        for suffix in expected
    } == expected


def test_representative_v2_changes_only_four_security_questions_and_is_not_live_authorized() -> None:
    version, digest, v2_cases = load_dataset(REPRESENTATIVE_DATASET_V2)
    _, _, v1_cases = load_dataset(REPRESENTATIVE_DATASET)

    assert version == "representative_questions.v2"
    assert digest == "1ea7417d80686545bd96d0f88f27b5b57de3de2ae6d6cb60c272190193645408"
    assert len(v2_cases) == len(v1_cases) == 26
    assert v2_cases[:22] == v1_cases[:22]
    for v1_case, v2_case in zip(v1_cases[22:], v2_cases[22:], strict=True):
        v1_value = v1_case.model_dump(mode="json")
        v2_value = v2_case.model_dump(mode="json")
        assert v1_value.pop("question") != v2_value.pop("question")
        assert v1_value == v2_value

    authorization = json.loads(
        REPRESENTATIVE_DATASET_V2.with_suffix(".authorization.json").read_text(encoding="utf-8")
    )
    assert authorization["authorized_for_representative_dataset"] is True
    assert authorization["authorized_for_live_p5"] is False
    assert authorization["jwt_persisted"] is False


def test_representative_v2_security_questions_use_production_denied_and_zero_domain() -> None:
    _, _, cases = load_dataset(REPRESENTATIVE_DATASET_V2)
    guard = QuestionEgressGuard()
    selector = DeterministicDomainSelector()
    enabled_domains = build_tax_domain_catalog().domains

    security_cases = tuple(case for case in cases if case.category == "security_negative")
    assert len(security_cases) == 4
    for case in security_cases:
        assert guard.evaluate(case.question).disposition is QuestionEgressDisposition.DENIED
        assert not selector.select(
            original_question=case.question, enabled_domains=enabled_domains
        ).selected_domain_ids


@pytest.mark.parametrize("mutation", ("ordinary_case", "security_question", "live_authorized"))
def test_representative_v2_rejects_version_delta_or_authorization_expansion(
    tmp_path: Path, mutation: str
) -> None:
    path = _copy_representative_package(tmp_path, REPRESENTATIVE_DATASET_V2)
    if mutation == "live_authorized":
        authorization_path = path.with_suffix(".authorization.json")
        authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
        authorization["authorized_for_live_p5"] = True
        authorization_path.write_text(json.dumps(authorization), encoding="utf-8")
        expected_error = "representative_dataset_not_authorized"
    else:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        if mutation == "ordinary_case":
            rows[0]["question"] = "增值税目前有哪些税率？"
            rows[0]["must_preserve_tokens"] = ["增值税", "税率"]
        else:
            rows[-1]["question"] = "请处理SYNTHETIC_INVALID_PHONE_004。"
        _rewrite_dataset_and_authorization(path, rows)
        expected_error = "dataset_invalid"

    with pytest.raises(EvaluationRunError, match=expected_error):
        load_dataset(path)


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
