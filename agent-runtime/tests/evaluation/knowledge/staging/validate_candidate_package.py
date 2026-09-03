from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from tests.evaluation.knowledge.run_evaluation import EvaluationRunError, load_dataset


_TRACKED_PROVENANCE_MIRRORS = {
    ".tmp/chinatax-v2/post-cutover-gold-report.json": "post-cutover-gold-report.json",
    ".tmp/chinatax-v2/build_manifest.json": "build_manifest.json",
}
_TRACKED_PROVENANCE_ROOT = Path(__file__).resolve().parent / "provenance_inputs"


_CANDIDATE_FIELDS = {
    "candidate_id",
    "question",
    "proposed_category",
    "proposed_expected_domain_ids",
    "proposed_expected_answerability",
    "must_preserve_tokens",
    "source_kind",
    "source_ref",
    "review_status",
    "sensitive_review_status",
}
_ANNOTATION_FIELDS = {
    "candidate_id",
    "retrieval_status",
    "retrieval_reason",
    "retrieval_profile_version",
    "index_snapshot_ids",
    "candidate_documents",
    "document_relevance_review",
    "evidence_relevance_review",
    "selected_document_ids",
    "selected_evidence_ids",
    "reviewer",
    "reviewed_at",
}
_DOCUMENT_FIELDS = {"rank", "document_id", "evidence_id", "domain_ids"}
_AUTHORIZATION_FIELDS = {
    "schema_version",
    "status",
    "principal_profile_id",
    "read_authorization_evidence_ref",
    "allowed_logical_domain_ids",
    "authorized_for_representative_dataset",
    "authorized_for_live_p5",
    "jwt_persisted",
    "maintainer_id",
    "confirmed_at",
}
_PROVENANCE_FIELDS = {
    "schema_version",
    "status",
    "work_package_id",
    "generated_at",
    "candidate_questions_sha256",
    "retrieval_annotations_sha256",
    "proposed_decisions_sha256",
    "maintainer_case_decisions_sha256",
    "inputs",
    "current_retrieval_snapshot",
    "candidate_retrieval_identity_ref",
    "representative_dataset_approved",
    "gold_approved",
    "authorization_fixture_approved",
    "gate_028_status",
    "prohibited_claims",
}
_PROVENANCE_INPUT_FIELDS = {"path", "sha256", "role", "status"}
_SNAPSHOT_FIELDS = {
    "source_index",
    "read_index",
    "read_index_uuid",
    "mapping_version",
    "profile_version",
    "profiles",
}
_PROFILE_FIELDS = {"logical_domain_id", "retrieval_profile_id", "index_snapshot_id"}
_CHECKLIST_FIELDS = {
    "schema_version",
    "status",
    "candidate_count",
    "category_counts",
    "case_confirmations",
    "package_confirmations",
    "gate_028_close_allowed",
}
_CASE_CONFIRMATION_FIELDS = {
    "candidate_id",
    "representative",
    "sensitive_data",
    "expected_domains",
    "expected_answerability",
    "document_relevance",
    "evidence_relevance",
}
_PACKAGE_CONFIRMATION_FIELDS = {
    "snapshot_binding",
    "principal_profile",
    "read_authorization_evidence",
    "freeze_approval",
}
_PROPOSAL_FIELDS = {
    "candidate_id",
    "proposal_status",
    "suggested_category",
    "suggested_expected_domain_ids",
    "suggested_expected_answerability",
    "sensitive_data_assessment",
    "suggested_document_ids",
    "suggested_evidence_ids",
    "confidence",
    "basis_codes",
    "ambiguity_codes",
    "recommended_action",
    "maintainer_confirmation",
}
_MAINTAINER_DECISION_FIELDS = {
    "schema_version",
    "status",
    "work_package_id",
    "source_proposed_decisions_sha256",
    "confirmed_by",
    "confirmed_at",
    "case_decisions",
    "representative_designation_confirmed",
    "formal_dataset_freeze_authorized",
    "gate_028_status",
}
_CASE_DECISION_FIELDS = {"candidate_id", "decision", "accepted_recommended_action"}

_CATEGORIES = {"tax_policy", "tax_law", "mixed", "no_match", "insufficient", "security_negative"}
_DOMAINS = {"tax.policy", "tax.law"}
_ANSWERABILITY = {"answerable", "no_result", "model_egress_denied"}
_SENSITIVE_ASSESSMENTS = {"no_real_sensitive_data_observed", "synthetic_invalid_sentinel_only"}
_CONFIDENCE = {"high", "medium", "low"}
_RECOMMENDED_ACTIONS = {"confirm_as_proposed", "confirm_no_result", "revise_or_replace"}
_BASIS_CODES = {
    "article_reference_mismatch",
    "cross_domain_evidence_match",
    "current_policy_source_missing",
    "current_summary_match",
    "direct_clause_match",
    "fictional_reference_no_match",
    "insufficient_user_facts",
    "no_exact_reference_match",
    "obsolete_higher_rank_detected",
    "synthetic_negative_boundary",
    "temporal_conflict_detected",
}
_AMBIGUITY_CODES = {
    "article_reference_mismatch",
    "broad_scope",
    "current_policy_source_missing",
    "document_number_not_found",
    "obsolete_higher_rank_candidate",
    "temporal_policy_conflict",
}
_DECISION_BY_ACTION = {
    "confirm_as_proposed": "accepted_as_proposed",
    "confirm_no_result": "accepted_no_result",
    "revise_or_replace": "accepted_with_label_revision",
}
_LOWER_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_CANDIDATE_ID = re.compile(r"^[a-z0-9-]{1,64}$")
_EVIDENCE_ID = re.compile(r"^ev-[0-9a-f]{64}$")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b")
_API_KEY = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16}|Bearer\s+\S+)", re.IGNORECASE)
_CHINESE_ID = re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)")
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_BOUNDARY = re.compile(r"(?:\d|〔|第[一二三四五六七八九十百零〇]+条|不|未|否)")
_RFC3339_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_OPAQUE_ACTOR = re.compile(r"^[A-Za-z0-9._:+/-]{1,128}$")


class CandidatePackageError(RuntimeError):
    pass


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise CandidatePackageError("candidate_package.duplicate_json_key")
        value[key] = child
    return value


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CandidatePackageError(f"candidate_package.invalid_json:{path.name}") from exc
    if not isinstance(value, dict):
        raise CandidatePackageError(f"candidate_package.invalid_object:{path.name}")
    return value


def read_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CandidatePackageError(f"candidate_package.missing_file:{path.name}") from exc
    values: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line.decode("utf-8"), object_pairs_hook=_unique_pairs)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise CandidatePackageError(f"candidate_package.invalid_jsonl:{path.name}") from exc
        if not isinstance(value, dict):
            raise CandidatePackageError(f"candidate_package.invalid_jsonl_object:{path.name}")
        values.append(value)
    if not values:
        raise CandidatePackageError(f"candidate_package.empty_jsonl:{path.name}")
    return tuple(values)


def _validate_text(value: Any, *, code: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= maximum:
        raise CandidatePackageError(code)
    if value != unicodedata.normalize("NFC", value) or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise CandidatePackageError(code)
    return value


def _validate_utc_timestamp(value: Any, *, code: str) -> str:
    if not isinstance(value, str) or not _RFC3339_UTC.fullmatch(value):
        raise CandidatePackageError(code)
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise CandidatePackageError(code) from exc
    return value


def _validate_no_sensitive_value(question: str) -> None:
    if any(pattern.search(question) for pattern in (_JWT, _API_KEY, _CHINESE_ID, _PHONE, _EMAIL)):
        raise CandidatePackageError("candidate_package.sensitive_value_detected")


def _resolve_provenance_input(repository_root: Path, relative: str) -> Path:
    primary = (repository_root / relative).resolve()
    if not primary.is_relative_to(repository_root):
        raise CandidatePackageError("candidate_package.provenance_input_missing")
    if primary.is_file():
        return primary
    mirror_name = _TRACKED_PROVENANCE_MIRRORS.get(relative)
    if mirror_name is None:
        raise CandidatePackageError("candidate_package.provenance_input_missing")
    mirror_root = _TRACKED_PROVENANCE_ROOT.resolve()
    mirror = (mirror_root / mirror_name).resolve()
    if not mirror.is_relative_to(mirror_root) or not mirror.is_file():
        raise CandidatePackageError("candidate_package.provenance_input_missing")
    return mirror


def _validate_candidates(path: Path, *, repository_root: Path) -> tuple[tuple[dict[str, Any], ...], Counter[str]]:
    candidates = read_jsonl(path)
    if len(candidates) < 24:
        raise CandidatePackageError("candidate_package.insufficient_candidate_count")
    ids: list[str] = []
    questions: list[str] = []
    categories: Counter[str] = Counter()
    questions_by_category: dict[str, list[str]] = {category: [] for category in _CATEGORIES}
    legacy_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        if set(candidate) != _CANDIDATE_FIELDS:
            raise CandidatePackageError("candidate_package.invalid_candidate_fields")
        candidate_id = _validate_text(candidate["candidate_id"], code="candidate_package.invalid_candidate_id", maximum=64)
        if not _CANDIDATE_ID.fullmatch(candidate_id):
            raise CandidatePackageError("candidate_package.invalid_candidate_id")
        question = _validate_text(candidate["question"], code="candidate_package.invalid_question")
        _validate_no_sensitive_value(question)
        category = candidate["proposed_category"]
        if category not in _CATEGORIES:
            raise CandidatePackageError("candidate_package.invalid_category")
        domains = candidate["proposed_expected_domain_ids"]
        if not isinstance(domains, list) or len(domains) > 2 or len(set(domains)) != len(domains) or any(item not in _DOMAINS for item in domains):
            raise CandidatePackageError("candidate_package.invalid_domains")
        expected_domains = {
            "tax_policy": ["tax.policy"],
            "tax_law": ["tax.law"],
            "mixed": ["tax.policy", "tax.law"],
            "no_match": [],
            "security_negative": [],
        }
        if category in expected_domains and domains != expected_domains[category]:
            raise CandidatePackageError("candidate_package.invalid_category_domains")
        if category == "insufficient" and not domains:
            raise CandidatePackageError("candidate_package.invalid_category_domains")
        answerability = candidate["proposed_expected_answerability"]
        if answerability not in _ANSWERABILITY:
            raise CandidatePackageError("candidate_package.invalid_answerability")
        if category == "security_negative":
            if answerability != "model_egress_denied" or "SYNTHETIC_INVALID_" not in question:
                raise CandidatePackageError("candidate_package.invalid_security_negative")
        elif category in {"no_match", "insufficient"} and answerability != "no_result":
            raise CandidatePackageError("candidate_package.invalid_negative_answerability")
        tokens = candidate["must_preserve_tokens"]
        if not isinstance(tokens, list) or not tokens or len(set(tokens)) != len(tokens):
            raise CandidatePackageError("candidate_package.invalid_preserve_tokens")
        for token in tokens:
            token_value = _validate_text(token, code="candidate_package.invalid_preserve_token", maximum=256)
            if token_value not in question:
                raise CandidatePackageError("candidate_package.preserve_token_not_in_question")
        if candidate["source_kind"] not in {"legacy_candidate", "assistant_draft"}:
            raise CandidatePackageError("candidate_package.invalid_source_kind")
        _validate_text(candidate["source_ref"], code="candidate_package.invalid_source_ref", maximum=512)
        if candidate["source_kind"] == "legacy_candidate":
            legacy_candidates.append(candidate)
        elif candidate["source_ref"] != "wp-kp5-dataset-01-candidate-preparation":
            raise CandidatePackageError("candidate_package.invalid_draft_source_ref")
        if candidate["review_status"] != "pending_maintainer_review" or candidate["sensitive_review_status"] != "pending_maintainer_review":
            raise CandidatePackageError("candidate_package.unauthorized_candidate_approval")
        ids.append(candidate_id)
        questions.append(question)
        categories[category] += 1
        questions_by_category[category].append(question)
    if len(set(ids)) != len(ids) or len(set(questions)) != len(questions):
        raise CandidatePackageError("candidate_package.duplicate_candidate")
    if categories["tax_policy"] < 6 or categories["tax_law"] < 6 or categories["mixed"] < 4:
        raise CandidatePackageError("candidate_package.insufficient_primary_strata")
    if categories["no_match"] + categories["insufficient"] < 4 or categories["security_negative"] < 4:
        raise CandidatePackageError("candidate_package.insufficient_negative_strata")
    grouped_boundaries = (
        questions_by_category["tax_policy"],
        questions_by_category["tax_law"],
        questions_by_category["mixed"],
        questions_by_category["no_match"] + questions_by_category["insufficient"],
        questions_by_category["security_negative"],
    )
    if any(not any(_BOUNDARY.search(question) for question in group) for group in grouped_boundaries):
        raise CandidatePackageError("candidate_package.missing_stratum_boundary")
    if len(legacy_candidates) != 6:
        raise CandidatePackageError("candidate_package.legacy_candidate_count_mismatch")
    legacy_path = _resolve_provenance_input(
        repository_root,
        ".tmp/chinatax-v2/post-cutover-gold-report.json",
    )
    legacy_report = _read_json(legacy_path)
    legacy_questions = {
        item["caseId"]: item["query"]
        for item in legacy_report.get("results", [])
        if isinstance(item, dict) and isinstance(item.get("caseId"), str) and isinstance(item.get("query"), str)
    }
    for candidate in legacy_candidates:
        source_ref = candidate["source_ref"]
        prefix = ".tmp/chinatax-v2/post-cutover-gold-report.json#"
        if not source_ref.startswith(prefix) or legacy_questions.get(source_ref[len(prefix) :]) != candidate["question"]:
            raise CandidatePackageError("candidate_package.legacy_candidate_source_mismatch")
    return candidates, categories


def _validate_annotations(path: Path, candidates: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    annotations = read_jsonl(path)
    if tuple(item["candidate_id"] for item in annotations) != tuple(item["candidate_id"] for item in candidates):
        raise CandidatePackageError("candidate_package.annotation_order_mismatch")
    category_by_id = {item["candidate_id"]: item["proposed_category"] for item in candidates}
    for annotation in annotations:
        if set(annotation) != _ANNOTATION_FIELDS:
            raise CandidatePackageError("candidate_package.invalid_annotation_fields")
        candidate_id = annotation["candidate_id"]
        status = annotation["retrieval_status"]
        if status not in {"retrieved", "no_result", "skipped_by_design"}:
            raise CandidatePackageError("candidate_package.incomplete_retrieval_annotation")
        if annotation["document_relevance_review"] != "pending_maintainer_review" or annotation["evidence_relevance_review"] != "pending_maintainer_review":
            raise CandidatePackageError("candidate_package.unauthorized_relevance_approval")
        if annotation["selected_document_ids"] != [] or annotation["selected_evidence_ids"] != []:
            raise CandidatePackageError("candidate_package.automatic_gold_detected")
        if annotation["reviewer"] is not None or annotation["reviewed_at"] is not None:
            raise CandidatePackageError("candidate_package.unauthorized_reviewer")
        snapshots = annotation["index_snapshot_ids"]
        documents = annotation["candidate_documents"]
        if not isinstance(snapshots, list) or not isinstance(documents, list):
            raise CandidatePackageError("candidate_package.invalid_annotation_collections")
        if category_by_id[candidate_id] == "security_negative":
            if status != "skipped_by_design" or annotation["retrieval_reason"] != "security_negative_pre_retrieval_stop":
                raise CandidatePackageError("candidate_package.security_negative_retrieved")
            if annotation["retrieval_profile_version"] is not None or snapshots or documents:
                raise CandidatePackageError("candidate_package.security_negative_has_retrieval_data")
            continue
        if annotation["retrieval_reason"] != "none" or annotation["retrieval_profile_version"] != "tax-knowledge-search-v1":
            raise CandidatePackageError("candidate_package.invalid_retrieval_metadata")
        if not snapshots or len(set(snapshots)) != len(snapshots) or any(not isinstance(item, str) or not _LOWER_HEX_64.fullmatch(item) for item in snapshots):
            raise CandidatePackageError("candidate_package.invalid_retrieval_snapshot")
        if status == "retrieved" and not documents:
            raise CandidatePackageError("candidate_package.retrieved_without_documents")
        if status == "no_result" and documents:
            raise CandidatePackageError("candidate_package.no_result_with_documents")
        ranks: list[int] = []
        for document in documents:
            if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
                raise CandidatePackageError("candidate_package.invalid_candidate_document")
            if not isinstance(document["rank"], int) or not 1 <= document["rank"] <= 10:
                raise CandidatePackageError("candidate_package.invalid_candidate_rank")
            _validate_text(document["document_id"], code="candidate_package.invalid_document_id", maximum=256)
            if not isinstance(document["evidence_id"], str) or not _EVIDENCE_ID.fullmatch(document["evidence_id"]):
                raise CandidatePackageError("candidate_package.invalid_evidence_id")
            domains = document["domain_ids"]
            if not isinstance(domains, list) or not domains or len(set(domains)) != len(domains) or any(item not in _DOMAINS for item in domains):
                raise CandidatePackageError("candidate_package.invalid_document_domains")
            ranks.append(document["rank"])
        if ranks != list(range(1, len(ranks) + 1)):
            raise CandidatePackageError("candidate_package.non_contiguous_candidate_ranks")
    return annotations


def _validate_proposals(
    path: Path,
    candidates: tuple[dict[str, Any], ...],
    annotations: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    proposals = read_jsonl(path)
    candidate_ids = tuple(item["candidate_id"] for item in candidates)
    if tuple(item.get("candidate_id") for item in proposals) != candidate_ids:
        raise CandidatePackageError("candidate_package.proposal_order_mismatch")
    expected_domains = {
        "tax_policy": ["tax.policy"],
        "tax_law": ["tax.law"],
        "mixed": ["tax.policy", "tax.law"],
        "no_match": [],
        "security_negative": [],
    }
    for candidate, annotation, proposal in zip(candidates, annotations, proposals, strict=True):
        if set(proposal) != _PROPOSAL_FIELDS:
            raise CandidatePackageError("candidate_package.invalid_proposal_fields")
        if proposal["proposal_status"] != "assistant_proposal_pending_maintainer":
            raise CandidatePackageError("candidate_package.invalid_proposal_status")
        if proposal["maintainer_confirmation"] != "pending":
            raise CandidatePackageError("candidate_package.unauthorized_proposal_confirmation")
        category = proposal["suggested_category"]
        domains = proposal["suggested_expected_domain_ids"]
        answerability = proposal["suggested_expected_answerability"]
        if category not in _CATEGORIES or answerability not in _ANSWERABILITY:
            raise CandidatePackageError("candidate_package.invalid_proposal_classification")
        if not isinstance(domains, list) or len(domains) > 2 or len(set(domains)) != len(domains) or any(item not in _DOMAINS for item in domains):
            raise CandidatePackageError("candidate_package.invalid_proposal_domains")
        if category in expected_domains and domains != expected_domains[category]:
            raise CandidatePackageError("candidate_package.invalid_proposal_domains")
        if category == "insufficient" and not domains:
            raise CandidatePackageError("candidate_package.invalid_proposal_domains")
        if category in {"no_match", "insufficient"} and answerability != "no_result":
            raise CandidatePackageError("candidate_package.invalid_proposal_answerability")
        assessment = proposal["sensitive_data_assessment"]
        if assessment not in _SENSITIVE_ASSESSMENTS:
            raise CandidatePackageError("candidate_package.invalid_sensitive_assessment")
        is_security = candidate["proposed_category"] == "security_negative"
        expected_assessment = "synthetic_invalid_sentinel_only" if is_security else "no_real_sensitive_data_observed"
        if assessment != expected_assessment:
            raise CandidatePackageError("candidate_package.invalid_sensitive_assessment")
        if is_security and (category != "security_negative" or answerability != "model_egress_denied"):
            raise CandidatePackageError("candidate_package.invalid_security_proposal")

        document_ids = proposal["suggested_document_ids"]
        evidence_ids = proposal["suggested_evidence_ids"]
        if (
            not isinstance(document_ids, list)
            or not isinstance(evidence_ids, list)
            or len(document_ids) != len(evidence_ids)
            or len(set(document_ids)) != len(document_ids)
            or len(set(evidence_ids)) != len(evidence_ids)
        ):
            raise CandidatePackageError("candidate_package.invalid_proposal_selection")
        candidate_pairs = {
            (item["document_id"], item["evidence_id"]): set(item["domain_ids"])
            for item in annotation["candidate_documents"]
        }
        if any((document_id, evidence_id) not in candidate_pairs for document_id, evidence_id in zip(document_ids, evidence_ids, strict=True)):
            raise CandidatePackageError("candidate_package.proposal_outside_candidate_set")
        selected_domains: set[str] = set()
        for document_id, evidence_id in zip(document_ids, evidence_ids, strict=True):
            selected_domains.update(candidate_pairs[(document_id, evidence_id)])
        if answerability == "answerable" and not set(domains).issubset(selected_domains):
            raise CandidatePackageError("candidate_package.proposal_domain_evidence_gap")

        confidence = proposal["confidence"]
        action = proposal["recommended_action"]
        basis_codes = proposal["basis_codes"]
        ambiguity_codes = proposal["ambiguity_codes"]
        if confidence not in _CONFIDENCE or action not in _RECOMMENDED_ACTIONS:
            raise CandidatePackageError("candidate_package.invalid_proposal_judgment")
        if not isinstance(basis_codes, list) or not basis_codes or len(set(basis_codes)) != len(basis_codes) or any(code not in _BASIS_CODES for code in basis_codes):
            raise CandidatePackageError("candidate_package.invalid_proposal_basis")
        if not isinstance(ambiguity_codes, list) or len(set(ambiguity_codes)) != len(ambiguity_codes) or any(code not in _AMBIGUITY_CODES for code in ambiguity_codes):
            raise CandidatePackageError("candidate_package.invalid_proposal_ambiguity")
        if action == "confirm_no_result" and (answerability != "no_result" or document_ids):
            raise CandidatePackageError("candidate_package.invalid_no_result_proposal")
        if action == "revise_or_replace" and (not ambiguity_codes or document_ids):
            raise CandidatePackageError("candidate_package.invalid_revision_proposal")
        if answerability == "answerable" and not document_ids:
            raise CandidatePackageError("candidate_package.answerable_proposal_without_evidence")
        if answerability != "answerable" and document_ids:
            raise CandidatePackageError("candidate_package.non_answerable_proposal_with_evidence")
    return proposals


def _validate_maintainer_case_decisions(
    path: Path,
    *,
    proposals_path: Path,
    proposals: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    value = _read_json(path)
    if set(value) != _MAINTAINER_DECISION_FIELDS or value["schema_version"] != 1:
        raise CandidatePackageError("candidate_package.invalid_maintainer_decisions")
    if value["status"] != "case_recommendations_confirmed" or value["work_package_id"] != "WP-KP5-DATASET-01":
        raise CandidatePackageError("candidate_package.invalid_maintainer_decision_status")
    if value["source_proposed_decisions_sha256"] != _sha256(proposals_path):
        raise CandidatePackageError("candidate_package.maintainer_decision_source_drift")
    if not isinstance(value["confirmed_by"], str) or not _OPAQUE_ACTOR.fullmatch(value["confirmed_by"]):
        raise CandidatePackageError("candidate_package.invalid_maintainer_actor")
    _validate_utc_timestamp(value["confirmed_at"], code="candidate_package.invalid_maintainer_timestamp")
    decisions = value["case_decisions"]
    if not isinstance(decisions, list) or len(decisions) != len(proposals):
        raise CandidatePackageError("candidate_package.maintainer_decision_count_mismatch")
    if tuple(item.get("candidate_id") for item in decisions if isinstance(item, dict)) != tuple(
        proposal["candidate_id"] for proposal in proposals
    ):
        raise CandidatePackageError("candidate_package.maintainer_decision_order_mismatch")
    for decision, proposal in zip(decisions, proposals, strict=True):
        if not isinstance(decision, dict) or set(decision) != _CASE_DECISION_FIELDS:
            raise CandidatePackageError("candidate_package.invalid_case_decision")
        action = proposal["recommended_action"]
        if decision["accepted_recommended_action"] != action or decision["decision"] != _DECISION_BY_ACTION[action]:
            raise CandidatePackageError("candidate_package.maintainer_decision_mismatch")
        if decision["decision"] == "accepted_with_label_revision" and proposal["suggested_expected_answerability"] != "no_result":
            raise CandidatePackageError("candidate_package.invalid_label_revision")
    if not value["representative_designation_confirmed"] or not value["formal_dataset_freeze_authorized"]:
        raise CandidatePackageError("candidate_package.dataset_freeze_not_confirmed")
    if value["gate_028_status"] != "closed":
        raise CandidatePackageError("candidate_package.gate_028_not_closed")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_authorization(path: Path) -> None:
    value = _read_json(path)
    if set(value) != _AUTHORIZATION_FIELDS or value["schema_version"] != 1:
        raise CandidatePackageError("candidate_package.invalid_authorization_template")
    if value["status"] != "template_pending_maintainer":
        raise CandidatePackageError("candidate_package.authorization_not_pending")
    if value["allowed_logical_domain_ids"] != ["tax.policy", "tax.law"]:
        raise CandidatePackageError("candidate_package.invalid_authorization_domains")
    if value["authorized_for_representative_dataset"] or value["authorized_for_live_p5"] or value["jwt_persisted"]:
        raise CandidatePackageError("candidate_package.unauthorized_authorization_state")
    if value["maintainer_id"] is not None or value["confirmed_at"] is not None:
        raise CandidatePackageError("candidate_package.authorization_confirmation_present")
    if "jwt" in {key.lower() for key in value if key != "jwt_persisted"}:
        raise CandidatePackageError("candidate_package.jwt_slot_forbidden")


def _validate_provenance(
    path: Path,
    *,
    questions_path: Path,
    annotations_path: Path,
    proposals_path: Path,
    maintainer_decisions_path: Path,
    repository_root: Path,
) -> dict[str, Any]:
    value = _read_json(path)
    if set(value) != _PROVENANCE_FIELDS or value["schema_version"] != 1:
        raise CandidatePackageError("candidate_package.invalid_provenance")
    if value["status"] != "representative_dataset_frozen" or value["work_package_id"] != "WP-KP5-DATASET-01":
        raise CandidatePackageError("candidate_package.invalid_provenance_status")
    _validate_utc_timestamp(value["generated_at"], code="candidate_package.invalid_provenance_timestamp")
    if value["candidate_questions_sha256"] != _sha256(questions_path) or value["retrieval_annotations_sha256"] != _sha256(annotations_path):
        raise CandidatePackageError("candidate_package.provenance_hash_mismatch")
    if value["proposed_decisions_sha256"] != _sha256(proposals_path) or value["maintainer_case_decisions_sha256"] != _sha256(maintainer_decisions_path):
        raise CandidatePackageError("candidate_package.provenance_decision_hash_mismatch")
    if not isinstance(value["inputs"], list) or not value["inputs"]:
        raise CandidatePackageError("candidate_package.missing_provenance_inputs")
    inputs_by_role: dict[str, Path] = {}
    for item in value["inputs"]:
        if not isinstance(item, dict) or set(item) != _PROVENANCE_INPUT_FIELDS:
            raise CandidatePackageError("candidate_package.invalid_provenance_input")
        _validate_text(item["path"], code="candidate_package.invalid_provenance_path", maximum=512)
        if not isinstance(item["sha256"], str) or not _LOWER_HEX_64.fullmatch(item["sha256"]):
            raise CandidatePackageError("candidate_package.invalid_provenance_hash")
        input_path = _resolve_provenance_input(repository_root, item["path"])
        if _sha256(input_path) != item["sha256"]:
            raise CandidatePackageError("candidate_package.provenance_input_hash_mismatch")
        if not isinstance(item["role"], str) or item["role"] in inputs_by_role:
            raise CandidatePackageError("candidate_package.invalid_provenance_role")
        inputs_by_role[item["role"]] = input_path
    expected_roles = {
        "legacy_question_candidate_source",
        "legacy_source_metadata_reference",
        "current_retrieval_snapshot_evidence",
    }
    if set(inputs_by_role) != expected_roles:
        raise CandidatePackageError("candidate_package.invalid_provenance_roles")
    snapshot = value["current_retrieval_snapshot"]
    if not isinstance(snapshot, dict) or set(snapshot) != _SNAPSHOT_FIELDS:
        raise CandidatePackageError("candidate_package.invalid_snapshot")
    if snapshot["profile_version"] != "tax-knowledge-search-v1":
        raise CandidatePackageError("candidate_package.invalid_profile_version")
    profiles = snapshot["profiles"]
    if not isinstance(profiles, list) or len(profiles) != 2:
        raise CandidatePackageError("candidate_package.invalid_snapshot_profiles")
    for profile in profiles:
        if not isinstance(profile, dict) or set(profile) != _PROFILE_FIELDS:
            raise CandidatePackageError("candidate_package.invalid_snapshot_profile")
        if profile["logical_domain_id"] not in _DOMAINS or not _LOWER_HEX_64.fullmatch(profile["index_snapshot_id"]):
            raise CandidatePackageError("candidate_package.invalid_snapshot_profile")
    retrieval_evidence = _read_json(inputs_by_role["current_retrieval_snapshot_evidence"])
    evidence_snapshot = retrieval_evidence.get("indexSnapshot")
    evidence_profiles = retrieval_evidence.get("retrievalProfiles")
    if not isinstance(evidence_snapshot, dict) or not isinstance(evidence_profiles, list):
        raise CandidatePackageError("candidate_package.invalid_retrieval_evidence")
    expected_snapshot = {
        "source_index": evidence_snapshot.get("sourceIndex"),
        "read_index": evidence_snapshot.get("readIndex"),
        "read_index_uuid": evidence_snapshot.get("readIndexUuid"),
        "mapping_version": evidence_snapshot.get("mappingVersion"),
        "profile_version": "tax-knowledge-search-v1",
        "profiles": [
            {
                "logical_domain_id": item.get("logicalDomainId"),
                "retrieval_profile_id": item.get("retrievalProfileId"),
                "index_snapshot_id": item.get("indexSnapshotId"),
            }
            for item in evidence_profiles
            if isinstance(item, dict)
        ],
    }
    if snapshot != expected_snapshot:
        raise CandidatePackageError("candidate_package.snapshot_evidence_mismatch")
    if not value["representative_dataset_approved"] or not value["gold_approved"] or not value["authorization_fixture_approved"]:
        raise CandidatePackageError("candidate_package.provenance_approval_missing")
    if value["gate_028_status"] != "closed" or value["prohibited_claims"] != ["live_p5_effectiveness"]:
        raise CandidatePackageError("candidate_package.invalid_closed_gate_state")
    return value


def _validate_checklist(path: Path, candidates: tuple[dict[str, Any], ...], categories: Counter[str]) -> None:
    value = _read_json(path)
    if set(value) != _CHECKLIST_FIELDS or value["schema_version"] != 1:
        raise CandidatePackageError("candidate_package.invalid_checklist")
    if value["status"] != "representative_dataset_frozen" or not value["gate_028_close_allowed"]:
        raise CandidatePackageError("candidate_package.invalid_checklist_status")
    if value["candidate_count"] != len(candidates) or value["category_counts"] != dict(sorted(categories.items())):
        raise CandidatePackageError("candidate_package.checklist_count_mismatch")
    confirmations = value["case_confirmations"]
    if not isinstance(confirmations, list) or tuple(item.get("candidate_id") for item in confirmations if isinstance(item, dict)) != tuple(item["candidate_id"] for item in candidates):
        raise CandidatePackageError("candidate_package.checklist_case_mismatch")
    for item in confirmations:
        if set(item) != _CASE_CONFIRMATION_FIELDS or item["representative"] != "confirmed":
            raise CandidatePackageError("candidate_package.case_confirmation_missing")
        confirmed_fields = _CASE_CONFIRMATION_FIELDS - {"candidate_id", "representative"}
        if any(item[field] != "confirmed" for field in confirmed_fields):
            raise CandidatePackageError("candidate_package.case_recommendation_not_confirmed")
    package = value["package_confirmations"]
    if not isinstance(package, dict) or set(package) != _PACKAGE_CONFIRMATION_FIELDS or any(status != "confirmed" for status in package.values()):
        raise CandidatePackageError("candidate_package.package_confirmation_missing")


def _validate_formal_dataset(
    *,
    repository_root: Path,
    candidates: tuple[dict[str, Any], ...],
    proposals: tuple[dict[str, Any], ...],
    maintainer_decisions: dict[str, Any],
) -> tuple[str, int]:
    dataset_path = repository_root / "agent-runtime/tests/evaluation/knowledge/representative_questions.v1.jsonl"
    try:
        _, digest, cases = load_dataset(dataset_path)
    except EvaluationRunError as exc:
        raise CandidatePackageError(f"candidate_package.formal_dataset_invalid:{exc}") from exc
    decisions = maintainer_decisions["case_decisions"]
    if len(cases) != len(candidates) or len(cases) != len(proposals) or len(cases) != len(decisions):
        raise CandidatePackageError("candidate_package.formal_dataset_count_mismatch")
    for case, candidate, proposal, decision in zip(cases, candidates, proposals, decisions, strict=True):
        if decision["candidate_id"] != case.case_id:
            raise CandidatePackageError("candidate_package.formal_dataset_decision_mismatch")
        expected = {
            "case_id": candidate["candidate_id"],
            "question": candidate["question"],
            "category": proposal["suggested_category"],
            "expected_domain_ids": tuple(proposal["suggested_expected_domain_ids"]),
            "expected_answerability": proposal["suggested_expected_answerability"],
            "relevant_document_ids": tuple(proposal["suggested_document_ids"]),
            "required_evidence_ids": tuple(proposal["suggested_evidence_ids"]),
            "must_preserve_tokens": tuple(candidate["must_preserve_tokens"]),
        }
        actual = {
            "case_id": case.case_id,
            "question": case.question,
            "category": case.category,
            "expected_domain_ids": case.expected_domain_ids,
            "expected_answerability": case.expected_answerability,
            "relevant_document_ids": case.relevant_document_ids,
            "required_evidence_ids": case.required_evidence_ids,
            "must_preserve_tokens": case.must_preserve_tokens,
        }
        if actual != expected:
            raise CandidatePackageError(f"candidate_package.formal_dataset_source_mismatch:{case.case_id}")

    formal_provenance = _read_json(dataset_path.with_suffix(".provenance.json"))
    source_assets = formal_provenance.get("source_assets")
    if not isinstance(source_assets, list):
        raise CandidatePackageError("candidate_package.formal_source_assets_missing")
    for asset in source_assets:
        if not isinstance(asset, dict) or set(asset) != {"path", "sha256", "role"}:
            raise CandidatePackageError("candidate_package.invalid_formal_source_asset")
        source_path = (repository_root / asset["path"]).resolve()
        if not source_path.is_relative_to(repository_root) or not source_path.is_file():
            raise CandidatePackageError("candidate_package.formal_source_asset_missing")
        if _sha256(source_path) != asset["sha256"]:
            raise CandidatePackageError("candidate_package.formal_source_asset_hash_mismatch")
    return digest, len(cases)


def validate_package(root: Path, *, repository_root: Path | None = None) -> dict[str, Any]:
    resolved_root = root.resolve()
    resolved_repository_root = repository_root.resolve() if repository_root is not None else resolved_root.parents[4]
    expected_names = {
        "__init__.py",
        "authorization_fixture.template.json",
        "candidate_questions.v1.jsonl",
        "candidate_retrieval_annotations.v1.jsonl",
        "collect_candidate_retrieval.py",
        "dataset_provenance.template.json",
        "maintainer_case_decisions.v1.json",
        "maintainer_review_checklist.v1.json",
        "proposed_decisions.v1.jsonl",
        "review_candidates.py",
        "run_candidate_retrieval.ps1",
        "test_candidate_package.py",
        "validate_candidate_package.py",
    }
    actual_names = {path.name for path in resolved_root.iterdir() if path.is_file()}
    if actual_names != expected_names:
        raise CandidatePackageError("candidate_package.unexpected_file_manifest")
    if any("representative" in name.lower() or "gold" in name.lower() for name in actual_names):
        raise CandidatePackageError("candidate_package.forbidden_staging_filename")
    questions_path = resolved_root / "candidate_questions.v1.jsonl"
    annotations_path = resolved_root / "candidate_retrieval_annotations.v1.jsonl"
    candidates, categories = _validate_candidates(questions_path, repository_root=resolved_repository_root)
    annotations = _validate_annotations(annotations_path, candidates)
    proposals_path = resolved_root / "proposed_decisions.v1.jsonl"
    proposals = _validate_proposals(proposals_path, candidates, annotations)
    maintainer_decisions_path = resolved_root / "maintainer_case_decisions.v1.json"
    maintainer_decisions = _validate_maintainer_case_decisions(
        maintainer_decisions_path,
        proposals_path=proposals_path,
        proposals=proposals,
    )
    _validate_authorization(resolved_root / "authorization_fixture.template.json")
    provenance = _validate_provenance(
        resolved_root / "dataset_provenance.template.json",
        questions_path=questions_path,
        annotations_path=annotations_path,
        proposals_path=proposals_path,
        maintainer_decisions_path=maintainer_decisions_path,
        repository_root=resolved_repository_root,
    )
    snapshot_by_domain = {
        item["logical_domain_id"]: item["index_snapshot_id"]
        for item in provenance["current_retrieval_snapshot"]["profiles"]
    }
    for candidate, annotation in zip(candidates, annotations, strict=True):
        if candidate["proposed_category"] == "security_negative":
            continue
        domains = candidate["proposed_expected_domain_ids"] or ["tax.policy", "tax.law"]
        expected_snapshots = [snapshot_by_domain[domain] for domain in domains]
        if annotation["index_snapshot_ids"] != expected_snapshots:
            raise CandidatePackageError("candidate_package.annotation_snapshot_mismatch")
    _validate_checklist(resolved_root / "maintainer_review_checklist.v1.json", candidates, categories)
    representative_dataset_sha256, representative_case_count = _validate_formal_dataset(
        repository_root=resolved_repository_root,
        candidates=candidates,
        proposals=proposals,
        maintainer_decisions=maintainer_decisions,
    )
    return {
        "status": "representative_dataset_frozen",
        "candidate_count": len(candidates),
        "annotation_count": len(annotations),
        "category_counts": dict(sorted(categories.items())),
        "candidate_questions_sha256": provenance["candidate_questions_sha256"],
        "retrieval_annotations_sha256": provenance["retrieval_annotations_sha256"],
        "proposed_decisions_sha256": _sha256(proposals_path),
        "proposal_count": len(proposals),
        "proposal_action_counts": dict(sorted(Counter(item["recommended_action"] for item in proposals).items())),
        "maintainer_decision_count": len(maintainer_decisions["case_decisions"]),
        "maintainer_decisions_sha256": _sha256(maintainer_decisions_path),
        "representative_case_count": representative_case_count,
        "representative_dataset_sha256": representative_dataset_sha256,
        "representative_designation_confirmed": True,
        "formal_dataset_freeze_authorized": True,
        "gate_028_status": "closed",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    arguments = parser.parse_args()
    try:
        summary = validate_package(arguments.root.resolve())
    except CandidatePackageError as exc:
        print(str(exc))
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
