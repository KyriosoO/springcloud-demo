from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tests.evaluation.knowledge.staging.review_candidates import _snippet
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


def test_representative_dataset_is_frozen_and_gate_028_is_closed() -> None:
    summary = validate_package(ROOT)
    assert summary["status"] == "representative_dataset_frozen"
    assert summary["candidate_count"] == summary["annotation_count"] == 26
    assert summary["category_counts"] == {
        "insufficient": 2,
        "mixed": 4,
        "no_match": 2,
        "security_negative": 4,
        "tax_law": 6,
        "tax_policy": 8,
    }
    assert summary["gate_028_status"] == "closed"
    assert summary["proposal_count"] == 26
    assert summary["maintainer_decision_count"] == 26
    assert summary["proposal_action_counts"] == {
        "confirm_as_proposed": 18,
        "confirm_no_result": 5,
        "revise_or_replace": 3,
    }
    assert len(summary["proposed_decisions_sha256"]) == 64
    assert len(summary["maintainer_decisions_sha256"]) == 64
    assert summary["representative_case_count"] == 26
    assert summary["representative_dataset_sha256"] == "00e6a8b3d7b172d4b9de7fe4712ed0f308b41855d5212bc3eb6ed42e78182dd7"
    assert summary["representative_designation_confirmed"]
    assert summary["formal_dataset_freeze_authorized"]


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


def test_review_runner_is_transient_and_has_no_model_or_file_output_dependency() -> None:
    source = (ROOT / "review_candidates.py").read_text(encoding="utf-8").lower()
    for forbidden in ("deepseek", "structuredmodelgateway", "knowledge.evidence", "write_text", "write_bytes", "--output"):
        assert forbidden not in source
    assert "source_url" not in source
    assert '"persistence_allowed": false' in source


def test_review_snippet_is_bounded_and_focuses_preserved_token() -> None:
    prefix = "前置内容" * 100
    value = f"{prefix} 财税〔2023〕12号 后置内容"
    snippet, truncated, focus = _snippet(value, focus_tokens=("财税〔2023〕12号",))
    assert len(snippet) <= 240
    assert "财税〔2023〕12号" in snippet
    assert truncated
    assert focus == "财税〔2023〕12号"


def test_proposed_decisions_are_pending_and_limited_to_frozen_candidates() -> None:
    proposals = read_jsonl(ROOT / "proposed_decisions.v1.jsonl")
    annotations = {
        item["candidate_id"]: {
            (document["document_id"], document["evidence_id"])
            for document in item["candidate_documents"]
        }
        for item in read_jsonl(ROOT / "candidate_retrieval_annotations.v1.jsonl")
    }
    assert len(proposals) == 26
    assert all(item["proposal_status"] == "assistant_proposal_pending_maintainer" for item in proposals)
    assert all(item["maintainer_confirmation"] == "pending" for item in proposals)
    for proposal in proposals:
        selected = set(zip(proposal["suggested_document_ids"], proposal["suggested_evidence_ids"], strict=True))
        assert selected <= annotations[proposal["candidate_id"]]
    raw = (ROOT / "proposed_decisions.v1.jsonl").read_text(encoding="utf-8").lower()
    for forbidden_key in ('"content":', '"title":', '"snippet":', '"question":', '"jwt":', '"subject":', '"maintainer_id":'):
        assert forbidden_key not in raw


def test_maintainer_decisions_accept_every_proposal_and_authorize_freeze() -> None:
    proposals = read_jsonl(ROOT / "proposed_decisions.v1.jsonl")
    decisions = json.loads((ROOT / "maintainer_case_decisions.v1.json").read_text(encoding="utf-8"))
    assert decisions["status"] == "case_recommendations_confirmed"
    assert [item["candidate_id"] for item in decisions["case_decisions"]] == [
        item["candidate_id"] for item in proposals
    ]
    assert [item["accepted_recommended_action"] for item in decisions["case_decisions"]] == [
        item["recommended_action"] for item in proposals
    ]
    assert sum(item["decision"] == "accepted_with_label_revision" for item in decisions["case_decisions"]) == 3
    assert decisions["representative_designation_confirmed"]
    assert decisions["formal_dataset_freeze_authorized"]
    assert decisions["gate_028_status"] == "closed"
    raw = (ROOT / "maintainer_case_decisions.v1.json").read_text(encoding="utf-8").lower()
    for forbidden_key in ('"question":', '"content":', '"title":', '"jwt":', '"subject":', '"maintainer_id":'):
        assert forbidden_key not in raw


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


def test_validator_rejects_proposal_confirmation_without_maintainer_workflow(tmp_path: Path) -> None:
    copied = _copy_package(tmp_path / "package")
    proposals = copied / "proposed_decisions.v1.jsonl"
    rows = [json.loads(line) for line in proposals.read_text(encoding="utf-8").splitlines()]
    rows[0]["maintainer_confirmation"] = "confirmed"
    proposals.write_text("\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows) + "\n", encoding="utf-8")
    with pytest.raises(CandidatePackageError, match="unauthorized_proposal_confirmation"):
        validate_package(copied, repository_root=REPOSITORY_ROOT)


def test_validator_rejects_maintainer_decision_that_differs_from_proposal(tmp_path: Path) -> None:
    copied = _copy_package(tmp_path / "package")
    decisions_path = copied / "maintainer_case_decisions.v1.json"
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    decisions["case_decisions"][0]["accepted_recommended_action"] = "confirm_no_result"
    decisions_path.write_text(json.dumps(decisions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(CandidatePackageError, match="maintainer_decision_mismatch"):
        validate_package(copied, repository_root=REPOSITORY_ROOT)


def test_validator_rejects_missing_representative_or_freeze_confirmation(tmp_path: Path) -> None:
    copied = _copy_package(tmp_path / "package")
    decisions_path = copied / "maintainer_case_decisions.v1.json"
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    decisions["representative_designation_confirmed"] = False
    decisions["formal_dataset_freeze_authorized"] = False
    decisions_path.write_text(json.dumps(decisions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(CandidatePackageError, match="dataset_freeze_not_confirmed"):
        validate_package(copied, repository_root=REPOSITORY_ROOT)


def test_validator_rejects_invalid_maintainer_confirmation_timestamp(tmp_path: Path) -> None:
    copied = _copy_package(tmp_path / "package")
    decisions_path = copied / "maintainer_case_decisions.v1.json"
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    decisions["confirmed_at"] = "2026-99-99T99:99:99Z"
    decisions_path.write_text(json.dumps(decisions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(CandidatePackageError, match="invalid_maintainer_timestamp"):
        validate_package(copied, repository_root=REPOSITORY_ROOT)


def test_validator_rejects_proposed_evidence_outside_frozen_candidates(tmp_path: Path) -> None:
    copied = _copy_package(tmp_path / "package")
    proposals = copied / "proposed_decisions.v1.jsonl"
    rows = [json.loads(line) for line in proposals.read_text(encoding="utf-8").splitlines()]
    rows[0]["suggested_document_ids"][0] = "tax-not-in-frozen-candidates"
    proposals.write_text("\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows) + "\n", encoding="utf-8")
    with pytest.raises(CandidatePackageError, match="proposal_outside_candidate_set"):
        validate_package(copied, repository_root=REPOSITORY_ROOT)


def test_validator_requires_evidence_for_every_suggested_logical_domain(tmp_path: Path) -> None:
    copied = _copy_package(tmp_path / "package")
    proposals = copied / "proposed_decisions.v1.jsonl"
    rows = [json.loads(line) for line in proposals.read_text(encoding="utf-8").splitlines()]
    mixed = next(row for row in rows if row["candidate_id"] == "draft-mixed-eit-article-28-policy")
    mixed["suggested_document_ids"] = mixed["suggested_document_ids"][:1]
    mixed["suggested_evidence_ids"] = mixed["suggested_evidence_ids"][:1]
    proposals.write_text("\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows) + "\n", encoding="utf-8")
    with pytest.raises(CandidatePackageError, match="proposal_domain_evidence_gap"):
        validate_package(copied, repository_root=REPOSITORY_ROOT)


def test_validator_rejects_provenance_source_hash_drift(tmp_path: Path) -> None:
    copied = _copy_package(tmp_path / "package")
    provenance_path = copied / "dataset_provenance.template.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["inputs"][0]["sha256"] = "0" * 64
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(CandidatePackageError, match="provenance_input_hash_mismatch"):
        validate_package(copied, repository_root=REPOSITORY_ROOT)


def test_validator_rejects_provenance_decision_hash_drift(tmp_path: Path) -> None:
    copied = _copy_package(tmp_path / "package")
    provenance_path = copied / "dataset_provenance.template.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["maintainer_case_decisions_sha256"] = "0" * 64
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(CandidatePackageError, match="provenance_decision_hash_mismatch"):
        validate_package(copied, repository_root=REPOSITORY_ROOT)
