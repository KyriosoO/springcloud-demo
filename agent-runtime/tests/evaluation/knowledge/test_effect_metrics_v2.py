from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from tests.evaluation.knowledge.bootstrap import build_from_environment
from tests.evaluation.knowledge.contracts import EvaluationRunResult, SafetyGateResult
from tests.evaluation.knowledge.run_evaluation import (
    EvaluatedCase,
    classify_conclusion,
    compute_metrics,
    derive_effect_metric_population,
    load_dataset,
)


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "representative_questions.v2.jsonl"
RESULT = ROOT / "results/knowledge-p5-live-v2-20260826-candidate-05/result.json"


def _evaluated() -> tuple[EvaluatedCase, ...]:
    _, _, cases = load_dataset(DATASET)
    result = EvaluationRunResult.model_validate_json(RESULT.read_bytes())
    return tuple(
        EvaluatedCase(case=case, result=case_result)
        for case, case_result in zip(cases, result.case_results, strict=True)
    )


def test_v2_population_excludes_only_security_negatives_from_summary() -> None:
    evaluated = _evaluated()
    population = derive_effect_metric_population(evaluated)
    metrics = compute_metrics(evaluated, population=population)

    assert len(population.summary_cases) == 22
    assert all(item.case.category != "security_negative" for item in population.summary_cases)
    assert metrics.summary_valid_completion_rate == 1.0
    assert all(
        item.result.primary.model_call_counts.summary == 0
        for item in evaluated
        if item.case.category == "security_negative"
    )

    ordinary = next(item for item in population.summary_cases if item.result.primary.summary_status == "answer")
    failed_primary = ordinary.result.primary.model_copy(update={"summary_status": "not_called"})
    failed_result = ordinary.result.model_copy(update={"primary": failed_primary})
    failed_cases = tuple(
        replace(item, result=failed_result) if item.case.case_id == ordinary.case.case_id else item
        for item in evaluated
    )
    failed_population = derive_effect_metric_population(failed_cases)
    assert compute_metrics(
        failed_cases, population=failed_population
    ).summary_valid_completion_rate == 21 / 22


def test_v2_quality_population_separates_explicit_gold_issue_and_keeps_thresholds() -> None:
    evaluated = _evaluated()
    population = derive_effect_metric_population(evaluated)
    metrics = compute_metrics(evaluated, population=population)

    assert population.answerable_count == 14
    assert population.answerable_gold_issue_count == 1
    assert population.quality_coverage_rate == 13 / 14
    assert population.valid is True
    assert metrics.faithfulness_rate == 1.0
    assert metrics.usefulness_rate == 10 / 13
    assert metrics.q3 is True
    assert metrics.q4 is False

    additional = next(
        item
        for item in population.quality_cases
        if item.result.primary_judgment.judgment_reason != "gold_issue"
    )
    judgment = additional.result.primary_judgment.model_copy(update={"judgment_reason": "gold_issue"})
    result = additional.result.model_copy(update={"primary_judgment": judgment})
    degraded = tuple(
        replace(item, result=result) if item.case.case_id == additional.case.case_id else item
        for item in evaluated
    )
    degraded_population = derive_effect_metric_population(degraded)
    assert degraded_population.answerable_gold_issue_count == 2
    assert degraded_population.quality_coverage_rate == 12 / 14
    assert degraded_population.valid is False

    snapshot = build_from_environment(environ={}).snapshot
    first, second, third, fourth = snapshot.gate_evidence
    live_snapshot = replace(
        snapshot,
        provider_mode="live",
        worktree_dirty=False,
        gate_evidence=(
            first.model_copy(update={"evidence_ref": "P3_00:closed"}),
            second.model_copy(update={"evidence_ref": "P3_00:closed"}),
            third.model_copy(update={"evidence_ref": "P3_00:closed"}),
            fourth.model_copy(update={"evidence_ref": "P3_00:closed"}),
        ),
    )
    safety = SafetyGateResult(
        deniedSummaryCallCount=0,
        unauthorizedContentCount=0,
        citationValidityRate=1.0,
        constraintPreservationRate=1.0,
        passed=True,
    )
    assert classify_conclusion(
        metrics=metrics,
        safety=safety,
        snapshot=live_snapshot,
        population=population,
    ) == "partially_effective"
    assert classify_conclusion(
        metrics=compute_metrics(degraded, population=degraded_population),
        safety=safety,
        snapshot=live_snapshot,
        population=degraded_population,
    ) == "invalid_run"
