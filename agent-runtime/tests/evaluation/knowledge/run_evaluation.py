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
import subprocess
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


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise EvaluationRunError("evaluation.duplicate_json_key")
        output[key] = value
    return output


def load_dataset(path: Path) -> tuple[str, str, tuple[EvaluationCase, ...]]:
    raw = path.read_bytes()
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
    if not path.name.startswith("synthetic_"):
        raise EvaluationRunError("evaluation.representative_dataset_not_authorized")
    return path.stem, digest, tuple(cases)


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
