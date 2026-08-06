from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tests.evaluation.knowledge.staging.validate_candidate_package import (
    CandidatePackageError,
    read_jsonl,
    validate_package,
)


ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parents[4]


def _copy_package(destination: Path) -> Path:
    destination.mkdir()
    for source in ROOT.iterdir():
        if source.is_file():
            shutil.copy2(source, destination / source.name)
    return destination


def test_candidate_package_is_complete_but_not_approved() -> None:
    summary = validate_package(ROOT)
    assert summary["status"] == "candidate_only_pending_maintainer"
    assert summary["candidate_count"] == summary["annotation_count"] == 26
    assert summary["category_counts"] == {
        "insufficient": 2,
        "mixed": 4,
        "no_match": 2,
        "security_negative": 4,
        "tax_law": 6,
        "tax_policy": 8,
    }
    assert summary["gate_028_status"] == "open"


def test_retrieval_annotations_are_candidates_without_sensitive_slots() -> None:
    annotations = read_jsonl(ROOT / "candidate_retrieval_annotations.v1.jsonl")
    assert sum(item["retrieval_status"] == "retrieved" for item in annotations) == 22
    assert sum(item["retrieval_status"] == "skipped_by_design" for item in annotations) == 4
    assert sum(len(item["candidate_documents"]) for item in annotations) == 220
    assert all(not item["selected_document_ids"] and not item["selected_evidence_ids"] for item in annotations)
    raw = (ROOT / "candidate_retrieval_annotations.v1.jsonl").read_text(encoding="utf-8")
    for forbidden_key in ('"content":', '"title":', '"source_url":', '"sourceUrl":', '"question":', '"jwt":', '"subject":'):
        assert forbidden_key not in raw


def test_security_negative_cases_stop_before_retrieval() -> None:
    candidates = {item["candidate_id"]: item for item in read_jsonl(ROOT / "candidate_questions.v1.jsonl")}
    annotations = {item["candidate_id"]: item for item in read_jsonl(ROOT / "candidate_retrieval_annotations.v1.jsonl")}
    for candidate_id, candidate in candidates.items():
        if candidate["proposed_category"] != "security_negative":
            continue
        annotation = annotations[candidate_id]
        assert annotation["retrieval_status"] == "skipped_by_design"
        assert annotation["candidate_documents"] == []
        assert annotation["index_snapshot_ids"] == []


def test_collector_has_no_model_or_evidence_stage_dependency() -> None:
    source = (ROOT / "collect_candidate_retrieval.py").read_text(encoding="utf-8").lower()
    assert "deepseek" not in source
    assert "structuredmodelgateway" not in source
    assert "knowledge.evidence" not in source


def test_validator_rejects_maintainer_approval_without_freeze(tmp_path: Path) -> None:
    copied = _copy_package(tmp_path / "package")
    questions = copied / "candidate_questions.v1.jsonl"
    rows = [json.loads(line) for line in questions.read_text(encoding="utf-8").splitlines()]
    rows[0]["review_status"] = "approved"
    questions.write_text("\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows) + "\n", encoding="utf-8")
    with pytest.raises(CandidatePackageError, match="unauthorized_candidate_approval"):
        validate_package(copied, repository_root=REPOSITORY_ROOT)


def test_validator_rejects_automatic_document_selection(tmp_path: Path) -> None:
    copied = _copy_package(tmp_path / "package")
    annotations = copied / "candidate_retrieval_annotations.v1.jsonl"
    rows = [json.loads(line) for line in annotations.read_text(encoding="utf-8").splitlines()]
    rows[0]["selected_document_ids"] = [rows[0]["candidate_documents"][0]["document_id"]]
    annotations.write_text("\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows) + "\n", encoding="utf-8")
    with pytest.raises(CandidatePackageError, match="automatic_gold_detected"):
        validate_package(copied, repository_root=REPOSITORY_ROOT)


def test_validator_rejects_provenance_source_hash_drift(tmp_path: Path) -> None:
    copied = _copy_package(tmp_path / "package")
    provenance_path = copied / "dataset_provenance.template.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["inputs"][0]["sha256"] = "0" * 64
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(CandidatePackageError, match="provenance_input_hash_mismatch"):
        validate_package(copied, repository_root=REPOSITORY_ROOT)
