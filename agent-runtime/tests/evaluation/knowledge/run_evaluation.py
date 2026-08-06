from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    _AGENT_RUNTIME_ROOT = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(_AGENT_RUNTIME_ROOT))
    sys.path.insert(0, str(_AGENT_RUNTIME_ROOT / "src"))

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import ValidationError

from tests.evaluation.knowledge.bootstrap import EvaluationBootstrapError, build_from_environment, read_repository_state
from tests.evaluation.knowledge.contracts import (
    ComparisonMetrics,
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationExecutionFixture,
    EvaluationFailureRecord,
    EvaluationMetrics,
    EvaluationRunResult,
    EvaluationSystemSnapshot,
    PathHitAggregate,
    PrimaryHumanJudgment,
    SafetyGateResult,
    finite_mean,
)
from tests.evaluation.knowledge.executor import EvaluationExecutors


class EvaluationRunError(RuntimeError):
    pass


_REPRESENTATIVE_DATASET_NAME = "representative_questions.v1.jsonl"
_REPRESENTATIVE_DATASET_VERSION = "representative_questions.v1"
_REPRESENTATIVE_PROFILE_ID = "tax-knowledge-admin-reader-v1"
_REPRESENTATIVE_AUTHORIZATION_REF = "WP-KRET-REAL-01:authorizationMatrix.admin"
_REPRESENTATIVE_DOMAINS = ("tax.policy", "tax.law")
_REPRESENTATIVE_CATEGORY_COUNTS = {
    "insufficient": 2,
    "mixed": 4,
    "no_match": 2,
    "security_negative": 4,
    "tax_law": 6,
    "tax_policy": 8,
}
_REPRESENTATIVE_AUTHORIZATION_FIELDS = {
    "schema_version",
    "status",
    "work_package_id",
    "dataset_version",
    "dataset_sha256",
    "principal_profile_id",
    "read_authorization_evidence_ref",
    "allowed_logical_domain_ids",
    "authorized_for_representative_dataset",
    "authorized_for_live_p5",
    "jwt_persisted",
    "confirmed_by",
    "confirmed_at",
}
_REPRESENTATIVE_PROVENANCE_FIELDS = {
    "schema_version",
    "status",
    "work_package_id",
    "frozen_at",
    "dataset_path",
    "dataset_version",
    "dataset_sha256",
    "dataset_hash_path",
    "authorization_path",
    "authorization_sha256",
    "source_assets",
    "retrieval_snapshot",
    "case_count",
    "category_counts",
    "answerable_count",
    "relevant_document_reference_count",
    "required_evidence_reference_count",
    "sensitive_data_check",
    "representative_dataset_approved",
    "gold_approved",
    "authorization_fixture_approved",
    "gate_028_status",
    "live_p5_authorized",
}
_REPRESENTATIVE_SOURCE_ASSETS = (
    (
        "agent-runtime/tests/evaluation/knowledge/staging/candidate_questions.v1.jsonl",
        "d0206f1c22c292451bf6d6c0d57dbbea953a000118591c08df464a4c64aeb232",
        "maintainer_reviewed_questions",
    ),
    (
        "agent-runtime/tests/evaluation/knowledge/staging/candidate_retrieval_annotations.v1.jsonl",
        "5422b519796716bb59e7fd6aeae69989a029c79b56d6ca1827b750e1d601465f",
        "frozen_retrieval_candidates",
    ),
    (
        "agent-runtime/tests/evaluation/knowledge/staging/proposed_decisions.v1.jsonl",
        "355d74362622c5c81e8aea3c92b1ab148587137a7a8dd7df45eb63ca981acfdd",
        "assistant_proposals",
    ),
    (
        "agent-runtime/tests/evaluation/knowledge/staging/maintainer_case_decisions.v1.json",
        "7e1fa47027042d5fa19a2a609720df970cad2b01aa88f43f8f89f5cf606ddbb3",
        "maintainer_case_confirmations",
    ),
    (
        "agent-runtime/tests/integration/knowledge/evidence/wp-kret-real-01-20260803.json",
        "a0547439e9b4434b63b3efa73a901d2cb96d52ee9307bcc5cb9ff22dfc63bdd3",
        "retrieval_authorization_and_snapshot_evidence",
    ),
)
_REPRESENTATIVE_RETRIEVAL_SNAPSHOT = {
    "read_index": "agent-doc-tax-policy-v3-20260803-agent-read-v1",
    "read_index_uuid": "k97bn1gxROSfVm7zGfzbOg",
    "mapping_version": "agent-knowledge-tax-v1",
    "retrieval_profile_version": "tax-knowledge-search-v1",
    "profiles": [
        {
            "logical_domain_id": "tax.policy",
            "retrieval_profile_id": "tax-policy-v1",
            "index_snapshot_id": "7c71202794927a9497fed9df7cc0db5a052a53f0f6c2afdb6c0a16089f1c96ed",
        },
        {
            "logical_domain_id": "tax.law",
            "retrieval_profile_id": "tax-law-v1",
            "index_snapshot_id": "99ae962ae1c8e5026187c864eada38b3c3b82d6b017e6e8f076f116aba53fce2",
        },
    ],
}
_RFC3339_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
_EVIDENCE_ID = re.compile(r"^ev-[0-9a-f]{64}$")
_BOUNDARY_SIGNAL = re.compile(r"\d|〔|〕|第.{0,12}条|未|无|不|否")
_SENSITIVE_PATTERNS = (
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    re.compile(r"(?i)\b(?:api[_-]?key|authorization|bearer)\s*[:=]\s*\S+"),
    re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)"),
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise EvaluationRunError("evaluation.duplicate_json_key")
        output[key] = value
    return output


def _strict_json_object(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError, EvaluationRunError) as exc:
        raise EvaluationRunError("evaluation.representative_dataset_not_authorized") from exc
    if not isinstance(value, dict):
        raise EvaluationRunError("evaluation.representative_dataset_not_authorized")
    return value, raw


def _is_valid_utc_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not _RFC3339_UTC.fullmatch(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo == UTC


def _validate_representative_cases(cases: tuple[EvaluationCase, ...]) -> dict[str, int]:
    counts: dict[str, int] = dict(sorted(Counter(case.category for case in cases).items()))
    if counts != _REPRESENTATIVE_CATEGORY_COUNTS:
        raise EvaluationRunError("evaluation.dataset_invalid")
    questions: set[str] = set()
    for case in cases:
        normalized_question = unicodedata.normalize("NFC", case.question).strip()
        if normalized_question != case.question or any(unicodedata.category(char) == "Cc" for char in case.question):
            raise EvaluationRunError("evaluation.dataset_invalid")
        case_values = (
            case.question,
            *case.relevant_document_ids,
            *case.required_evidence_ids,
            *case.must_preserve_tokens,
        )
        if normalized_question in questions or any(
            value != unicodedata.normalize("NFC", value)
            or any(unicodedata.category(char) == "Cc" for char in value)
            or any(pattern.search(value) for pattern in _SENSITIVE_PATTERNS)
            for value in case_values
        ):
            raise EvaluationRunError("evaluation.dataset_invalid")
        questions.add(normalized_question)
        if not case.must_preserve_tokens or any(token not in case.question for token in case.must_preserve_tokens):
            raise EvaluationRunError("evaluation.dataset_invalid")
        if any(not _EVIDENCE_ID.fullmatch(item) for item in case.required_evidence_ids):
            raise EvaluationRunError("evaluation.dataset_invalid")
        if case.category == "tax_policy" and case.expected_domain_ids != ("tax.policy",):
            raise EvaluationRunError("evaluation.dataset_invalid")
        if case.category == "tax_law" and case.expected_domain_ids != ("tax.law",):
            raise EvaluationRunError("evaluation.dataset_invalid")
        if case.category == "mixed" and case.expected_domain_ids != _REPRESENTATIVE_DOMAINS:
            raise EvaluationRunError("evaluation.dataset_invalid")
        if case.category in {"no_match", "security_negative"} and case.expected_domain_ids:
            raise EvaluationRunError("evaluation.dataset_invalid")
        if case.category == "security_negative":
            if case.expected_answerability != "model_egress_denied" or "SYNTHETIC_INVALID_" not in case.question:
                raise EvaluationRunError("evaluation.dataset_invalid")
        if case.category in {"no_match", "insufficient"} and case.expected_answerability != "no_result":
            raise EvaluationRunError("evaluation.dataset_invalid")
        if case.category in {"tax_policy", "tax_law", "mixed"} and case.expected_answerability not in {
            "answerable",
            "no_result",
        }:
            raise EvaluationRunError("evaluation.dataset_invalid")
        if case.expected_answerability == "answerable":
            if not case.relevant_document_ids:
                raise EvaluationRunError("evaluation.dataset_invalid")
        elif case.relevant_document_ids or case.required_evidence_ids:
            raise EvaluationRunError("evaluation.dataset_invalid")
    for category in _REPRESENTATIVE_CATEGORY_COUNTS:
        if not any(case.category == category and _BOUNDARY_SIGNAL.search(case.question) for case in cases):
            raise EvaluationRunError("evaluation.dataset_invalid")
    return counts


def _validate_representative_package(
    *, path: Path, digest: str, cases: tuple[EvaluationCase, ...]
) -> None:
    hash_path = path.with_suffix(".sha256")
    authorization_path = path.with_suffix(".authorization.json")
    provenance_path = path.with_suffix(".provenance.json")
    try:
        hash_value = hash_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EvaluationRunError("evaluation.representative_dataset_not_authorized") from exc
    if hash_value != f"{digest}\n":
        raise EvaluationRunError("evaluation.representative_dataset_not_authorized")

    authorization, authorization_raw = _strict_json_object(authorization_path)
    if set(authorization) != _REPRESENTATIVE_AUTHORIZATION_FIELDS:
        raise EvaluationRunError("evaluation.representative_dataset_not_authorized")
    expected_authorization = {
        "schema_version": 1,
        "status": "representative_dataset_authorized",
        "work_package_id": "WP-KP5-DATASET-01",
        "dataset_version": _REPRESENTATIVE_DATASET_VERSION,
        "dataset_sha256": digest,
        "principal_profile_id": _REPRESENTATIVE_PROFILE_ID,
        "read_authorization_evidence_ref": _REPRESENTATIVE_AUTHORIZATION_REF,
        "allowed_logical_domain_ids": list(_REPRESENTATIVE_DOMAINS),
        "authorized_for_representative_dataset": True,
        "authorized_for_live_p5": False,
        "jwt_persisted": False,
    }
    if any(authorization.get(key) != value for key, value in expected_authorization.items()):
        raise EvaluationRunError("evaluation.representative_dataset_not_authorized")
    if authorization.get("confirmed_by") != "project-maintainer" or not _is_valid_utc_timestamp(
        authorization.get("confirmed_at")
    ):
        raise EvaluationRunError("evaluation.representative_dataset_not_authorized")

    counts = _validate_representative_cases(cases)
    provenance, _ = _strict_json_object(provenance_path)
    if set(provenance) != _REPRESENTATIVE_PROVENANCE_FIELDS:
        raise EvaluationRunError("evaluation.representative_dataset_not_authorized")
    authorization_sha256 = hashlib.sha256(authorization_raw).hexdigest()
    source_assets = provenance.get("source_assets")
    if not isinstance(source_assets, list) or [
        (item.get("path"), item.get("sha256"), item.get("role")) if isinstance(item, dict) and set(item) == {
            "path",
            "sha256",
            "role",
        } else None
        for item in source_assets
    ] != list(_REPRESENTATIVE_SOURCE_ASSETS):
        raise EvaluationRunError("evaluation.representative_dataset_not_authorized")
    expected_provenance = {
        "schema_version": 1,
        "status": "representative_dataset_frozen",
        "work_package_id": "WP-KP5-DATASET-01",
        "dataset_path": f"agent-runtime/tests/evaluation/knowledge/{_REPRESENTATIVE_DATASET_NAME}",
        "dataset_version": _REPRESENTATIVE_DATASET_VERSION,
        "dataset_sha256": digest,
        "dataset_hash_path": "agent-runtime/tests/evaluation/knowledge/representative_questions.v1.sha256",
        "authorization_path": "agent-runtime/tests/evaluation/knowledge/representative_questions.v1.authorization.json",
        "authorization_sha256": authorization_sha256,
        "retrieval_snapshot": _REPRESENTATIVE_RETRIEVAL_SNAPSHOT,
        "case_count": len(cases),
        "category_counts": counts,
        "answerable_count": sum(case.expected_answerability == "answerable" for case in cases),
        "relevant_document_reference_count": sum(len(case.relevant_document_ids) for case in cases),
        "required_evidence_reference_count": sum(len(case.required_evidence_ids) for case in cases),
        "sensitive_data_check": "passed_no_real_sensitive_or_secret_values",
        "representative_dataset_approved": True,
        "gold_approved": True,
        "authorization_fixture_approved": True,
        "gate_028_status": "closed",
        "live_p5_authorized": False,
    }
    if any(provenance.get(key) != value for key, value in expected_provenance.items()):
        raise EvaluationRunError("evaluation.representative_dataset_not_authorized")
    if not _is_valid_utc_timestamp(provenance.get("frozen_at")) or provenance.get("frozen_at") != authorization.get(
        "confirmed_at"
    ):
        raise EvaluationRunError("evaluation.representative_dataset_not_authorized")


def load_dataset(path: Path) -> tuple[str, str, tuple[EvaluationCase, ...]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise EvaluationRunError("evaluation.dataset_invalid") from exc
    digest = hashlib.sha256(raw).hexdigest()
    cases: list[EvaluationCase] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            json.loads(line.decode("utf-8"), object_pairs_hook=_unique_pairs)
            cases.append(EvaluationCase.model_validate_json(line))
        except (UnicodeError, json.JSONDecodeError, ValidationError, EvaluationRunError) as exc:
            raise EvaluationRunError("evaluation.dataset_invalid") from exc
    if not cases or len({case.case_id for case in cases}) != len(cases):
        raise EvaluationRunError("evaluation.dataset_invalid")
    frozen_cases = tuple(cases)
    if path.name == _REPRESENTATIVE_DATASET_NAME:
        _validate_representative_package(path=path, digest=digest, cases=frozen_cases)
    elif not path.name.startswith("synthetic_"):
        raise EvaluationRunError("evaluation.representative_dataset_not_authorized")
    return path.stem, digest, frozen_cases


def validate_result_bytes(raw: bytes) -> EvaluationRunResult:
    try:
        json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
        return EvaluationRunResult.model_validate_json(raw)
    except (UnicodeError, json.JSONDecodeError, ValidationError, EvaluationRunError) as exc:
        raise EvaluationRunError("evaluation.schema_invalid") from exc


def _metric(value: float | str) -> float | None:
    return value if isinstance(value, float) else None


def _mean(values: list[float]) -> float | None:
    result = finite_mean(values)
    return result if isinstance(result, float) else None


@dataclass(frozen=True, slots=True, kw_only=True)
class EvaluatedCase:
    case: EvaluationCase
    result: EvaluationCaseResult


def compute_metrics(cases: tuple[EvaluatedCase, ...]) -> EvaluationMetrics:
    primary = tuple(item.result.primary for item in cases)
    constraint = [value for item in primary if (value := _metric(item.metrics.constraint_preserved)) is not None]
    delta = [
        value
        for item in cases
        if (value := _metric(item.result.comparison_metrics.rewrite_rerank_recall_delta)) is not None
    ]
    regressions = [1.0 if item.result.comparison_metrics.rewrite_regression else 0.0 for item in cases]
    domain_matches = [
        1.0 if item.result.primary.selected_domain_ids == item.case.expected_domain_ids else 0.0
        for item in cases
        if item.case.category != "security_negative"
    ]
    fusion_recall = [value for item in primary if (value := _metric(item.metrics.fusion_recall_at_10)) is not None]
    fusion_mrr = [value for item in primary if (value := _metric(item.metrics.fusion_mrr_at_10)) is not None]
    rerank_recall = [value for item in primary if (value := _metric(item.metrics.rerank_recall_at_10)) is not None]
    rerank_mrr = [value for item in primary if (value := _metric(item.metrics.rerank_mrr_at_10)) is not None]
    evidence = [value for item in primary if (value := _metric(item.metrics.required_evidence_coverage)) is not None]
    citations = [
        value
        for case in cases
        for variant in (case.result.primary, case.result.rewrite_ablation)
        if (value := _metric(variant.metrics.citation_validity_rate)) is not None
    ]
    summary = [1.0 if item.summary_status in {"answer", "insufficient_evidence"} else 0.0 for item in primary]
    path_values: dict[tuple[str, str], list[float]] = {
        ("tax.policy", "keyword"): [],
        ("tax.policy", "vector"): [],
        ("tax.law", "keyword"): [],
        ("tax.law", "vector"): [],
    }
    for item in primary:
        hit = _metric(item.metrics.path_hit_at_10)
        if hit is not None:
            for ranking in item.path_rankings:
                path_values[(ranking.logical_domain_id, ranking.path)].append(hit)
    faithfulness = [
        1.0 if item.result.primary_judgment.faithful else 0.0
        for item in cases
        if item.case.expected_answerability == "answerable"
    ]
    usefulness = [
        1.0 if item.result.primary_judgment.useful else 0.0
        for item in cases
        if item.case.expected_answerability == "answerable"
    ]
    delta_mean = _mean(delta)
    regression_mean = _mean(regressions)
    domain_mean = _mean(domain_matches)
    rerank_recall_mean = _mean(rerank_recall)
    rerank_mrr_mean = _mean(rerank_mrr)
    fusion_mrr_mean = _mean(fusion_mrr)
    faithfulness_mean = _mean(faithfulness)
    summary_mean = _mean(summary)
    usefulness_mean = _mean(usefulness)
    q1 = all(value is not None for value in (delta_mean, regression_mean, domain_mean)) and (
        delta_mean is not None
        and regression_mean is not None
        and domain_mean is not None
        and delta_mean >= 0
        and regression_mean <= 0.10
        and domain_mean >= 0.85
    )
    q2 = all(value is not None for value in (rerank_recall_mean, rerank_mrr_mean, fusion_mrr_mean)) and (
        rerank_recall_mean is not None
        and rerank_mrr_mean is not None
        and fusion_mrr_mean is not None
        and rerank_recall_mean >= 0.80
        and rerank_mrr_mean >= fusion_mrr_mean
    )
    q3 = faithfulness_mean is not None and faithfulness_mean >= 0.95
    q4 = (
        summary_mean is not None
        and usefulness_mean is not None
        and summary_mean >= 0.90
        and usefulness_mean >= 0.80
    )
    return EvaluationMetrics(
        constraintPreservationRate=finite_mean(constraint),
        rewriteRerankRecallDelta=finite_mean(delta),
        rewriteRegressionRate=finite_mean(regressions),
        domainExactMatchRate=finite_mean(domain_matches),
        pathHitAt10ByDomainPath=PathHitAggregate(
            taxPolicyKeyword=finite_mean(path_values[("tax.policy", "keyword")]),
            taxPolicyVector=finite_mean(path_values[("tax.policy", "vector")]),
            taxLawKeyword=finite_mean(path_values[("tax.law", "keyword")]),
            taxLawVector=finite_mean(path_values[("tax.law", "vector")]),
        ),
        fusionRecallAt10=finite_mean(fusion_recall),
        fusionMrrAt10=finite_mean(fusion_mrr),
        rerankRecallAt10=finite_mean(rerank_recall),
        rerankMrrAt10=finite_mean(rerank_mrr),
        requiredEvidenceCoverage=finite_mean(evidence),
        summaryValidCompletionRate=finite_mean(summary),
        citationValidityRate=finite_mean(citations),
        faithfulnessRate=finite_mean(faithfulness),
        usefulnessRate=finite_mean(usefulness),
        q1=q1,
        q2=q2,
        q3=q3,
        q4=q4,
    )


def classify_conclusion(
    *, metrics: EvaluationMetrics, safety: SafetyGateResult, snapshot: EvaluationSystemSnapshot
) -> Literal["effective", "partially_effective", "ineffective", "invalid_run"]:
    gates_closed = all(item.evidence_ref != "open-synthetic-only" for item in snapshot.gate_evidence)
    if snapshot.provider_mode != "live" or snapshot.worktree_dirty or not gates_closed or not safety.passed:
        return "invalid_run"
    achieved = sum((metrics.q1, metrics.q2, metrics.q3, metrics.q4))
    return "effective" if achieved == 4 else "partially_effective" if achieved >= 2 else "ineffective"


def _comparison(primary: Any, ablation: Any) -> ComparisonMetrics:
    first = _metric(primary.metrics.rerank_recall_at_10)
    second = _metric(ablation.metrics.rerank_recall_at_10)
    if first is None or second is None:
        return ComparisonMetrics(rewriteRerankRecallDelta="not_applicable", rewriteRegression=False)
    return ComparisonMetrics(rewriteRerankRecallDelta=first - second, rewriteRegression=first < second)


async def run(
    *,
    dataset_path: Path,
    output_dir: Path,
    snapshot: EvaluationSystemSnapshot,
    executors: EvaluationExecutors,
    fixture: EvaluationExecutionFixture,
) -> EvaluationRunResult:
    if output_dir.exists():
        raise EvaluationRunError("evaluation.output_exists")
    if snapshot.provider_mode != "stub" or not fixture.synthetic_only:
        raise EvaluationRunError("evaluation.live_run_not_authorized")
    started = _utc_now()
    dataset_version, dataset_sha256, cases = load_dataset(dataset_path)
    executors.validate_pair()
    results: list[EvaluationCaseResult] = []
    for case in cases:
        before_primary = executors.primary.calls
        before_ablation = executors.rewrite_ablation.calls
        primary = await executors.primary.execute(case=case, fixture=fixture)
        ablation = await executors.rewrite_ablation.execute(case=case, fixture=fixture)
        if executors.primary.calls - before_primary != 1 or executors.rewrite_ablation.calls - before_ablation != 1:
            raise EvaluationRunError("evaluation.capability_call_count_invalid")
        results.append(
            EvaluationCaseResult(
                caseId=case.case_id,
                primary=primary,
                rewriteAblation=ablation,
                comparisonMetrics=_comparison(primary, ablation),
                primaryJudgment=PrimaryHumanJudgment(
                    faithful=False,
                    relevant=False,
                    sufficientForInitialAnswer=False,
                    useful=False,
                    judgmentReason="gold_issue",
                ),
            )
        )
    case_results = tuple(results)
    if len(case_results) != len(cases):
        raise EvaluationRunError("evaluation.case_pair_incomplete")
    evaluated_cases = tuple(EvaluatedCase(case=case, result=result) for case, result in zip(cases, case_results, strict=True))
    metrics = compute_metrics(evaluated_cases)
    safety = SafetyGateResult(
        deniedSummaryCallCount=0,
        unauthorizedContentCount=0,
        citationValidityRate=metrics.citation_validity_rate,
        constraintPreservationRate=metrics.constraint_preservation_rate,
        passed=(metrics.citation_validity_rate == 1.0 and metrics.constraint_preservation_rate == 1.0),
    )
    conclusion = classify_conclusion(metrics=metrics, safety=safety, snapshot=snapshot)
    final_commit, _, final_entries = read_repository_state(Path(snapshot.repository_root))
    if final_commit != snapshot.git_commit or final_entries != snapshot.worktree_entries:
        raise EvaluationRunError("evaluation.snapshot_changed")
    result = EvaluationRunResult(
        schemaVersion=1,
        runId=f"stub-{dataset_sha256[:12]}",
        startedAt=started,
        finishedAt=_utc_now(),
        datasetVersion=dataset_version,
        datasetSha256=dataset_sha256,
        gitCommit=snapshot.git_commit,
        worktreeDirty=snapshot.worktree_dirty,
        providerMode=snapshot.provider_mode,
        evaluationVariants=("primary", "rewrite_ablation"),
        principalProfileId=snapshot.principal_profile_id,
        readAuthorizationEvidenceRef=snapshot.read_authorization_evidence_ref,
        gateEvidence=snapshot.gate_evidence,
        questionPolicyVersion=snapshot.question_policy_version,
        domainCatalogVersion=snapshot.domain_catalog_version,
        flowConfigVersion=snapshot.flow_config_version,
        retrievalProfileVersion=snapshot.retrieval_profile_version,
        indexSnapshotIds=snapshot.index_snapshot_ids,
        embeddingModel=snapshot.embedding_model,
        rerankModel=snapshot.rerank_model,
        modelTaskVersions=snapshot.model_task_versions,
        deepSeekModel=snapshot.deep_seek_model,
        policyCatalogVersion=snapshot.policy_catalog_version,
        policyCatalogSha256=snapshot.policy_catalog_sha256,
        policyAuthorityId=snapshot.policy_authority_id,
        policyExportId=snapshot.policy_export_id,
        policySourceRevision=snapshot.policy_source_revision,
        evidenceRulesVersion=snapshot.evidence_rules_version,
        caseResults=case_results,
        aggregateMetrics=metrics,
        safetyGate=safety,
        conclusion=conclusion,
        reviewer="synthetic-harness",
    )
    payload = result.model_dump(by_alias=True, mode="json")
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=False, separators=(",", ":")).encode("utf-8")
    validate_result_bytes(encoded)
    _write_result(output_dir=output_dir, filename="result.json", payload=payload)
    return result


def _write_result(*, output_dir: Path, filename: str, payload: dict[str, Any]) -> None:
    output_dir.mkdir(parents=False, exist_ok=False)
    temporary = output_dir / f"{filename}.tmp"
    destination = output_dir / filename
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=False, separators=(",", ":")).encode("utf-8")
    with temporary.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, destination)


def write_failure(
    *,
    output_dir: Path,
    run_id: str,
    started_at: str,
    git_commit: str,
    dataset_sha256: str,
    failure_code: Literal[
        "bootstrap_invalid", "dataset_invalid", "snapshot_changed", "execution_failed", "schema_invalid", "write_failed"
    ],
) -> EvaluationFailureRecord:
    record = EvaluationFailureRecord(
        schemaVersion=1,
        runId=run_id,
        startedAt=started_at,
        finishedAt=_utc_now(),
        gitCommit=git_commit,
        datasetSha256=dataset_sha256,
        failureCode=failure_code,
    )
    _write_result(output_dir=output_dir, filename="failure.json", payload=record.model_dump(by_alias=True, mode="json"))
    return record


def _try_write_failure(**kwargs: Any) -> None:
    try:
        write_failure(**kwargs)
    except (OSError, ValidationError):
        return


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


async def _main_async() -> int:
    arguments = _parser().parse_args()
    started = _utc_now()
    dataset_sha256 = hashlib.sha256(arguments.dataset.read_bytes()).hexdigest() if arguments.dataset.is_file() else "0" * 64
    try:
        repository_root = Path(__file__).resolve().parents[4]
        git_commit = read_repository_state(repository_root)[0]
    except (OSError, subprocess.SubprocessError):
        git_commit = "0" * 40
    try:
        bootstrap = build_from_environment(environ=os.environ)
        result = await run(
            dataset_path=arguments.dataset,
            output_dir=arguments.output,
            snapshot=bootstrap.snapshot,
            executors=bootstrap.executors,
            fixture=bootstrap.fixture,
        )
    except EvaluationBootstrapError:
        _try_write_failure(
            output_dir=arguments.output,
            run_id=f"failed-{dataset_sha256[:12]}",
            started_at=started,
            git_commit=git_commit,
            dataset_sha256=dataset_sha256,
            failure_code="bootstrap_invalid",
        )
        return 3
    except (EvaluationRunError, ValidationError) as exc:
        failure_code: Literal["dataset_invalid", "snapshot_changed", "execution_failed", "schema_invalid"]
        if isinstance(exc, EvaluationRunError) and "dataset" in str(exc):
            failure_code = "dataset_invalid"
        elif isinstance(exc, EvaluationRunError) and "snapshot_changed" in str(exc):
            failure_code = "snapshot_changed"
        elif isinstance(exc, ValidationError) or (isinstance(exc, EvaluationRunError) and "schema_invalid" in str(exc)):
            failure_code = "schema_invalid"
        else:
            failure_code = "execution_failed"
        _try_write_failure(
            output_dir=arguments.output,
            run_id=f"failed-{dataset_sha256[:12]}",
            started_at=started,
            git_commit=git_commit,
            dataset_sha256=dataset_sha256,
            failure_code=failure_code,
        )
        return 3
    return 2 if result.conclusion == "invalid_run" else 0


def main() -> int:
    return asyncio.run(_main_async())


if __name__ == "__main__":
    raise SystemExit(main())
