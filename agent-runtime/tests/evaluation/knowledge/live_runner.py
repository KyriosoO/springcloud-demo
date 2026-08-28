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
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

from pydantic import ValidationError

from tests.evaluation.knowledge.contracts import (
    ComparisonMetrics,
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationFailureRecord,
    EvaluationRunResult,
    PrimaryHumanJudgment,
    SafetyGateResult,
)
from tests.evaluation.knowledge.live_bootstrap import (
    LiveEvaluationBootstrapError,
    LiveEvaluationBootstrapResult,
    build_live_from_environment,
)
from tests.evaluation.knowledge.live_contracts import HumanRubricSubmission, strict_json_bytes
from tests.evaluation.knowledge.live_executor import LiveEvaluatedVariant, ReviewMaterial
from tests.evaluation.knowledge.run_evaluation import (
    EvaluatedCase,
    EvaluationRunError,
    classify_conclusion,
    compute_metrics,
    derive_effect_metric_population,
    load_dataset,
    validate_result_bytes,
)


_REVIEW_TIMEOUT_SECONDS = 1800


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _metric(value: float | str) -> float | None:
    return value if isinstance(value, float) else None


def _comparison(primary: LiveEvaluatedVariant, ablation: LiveEvaluatedVariant) -> ComparisonMetrics:
    first = _metric(primary.result.metrics.rerank_recall_at_10)
    second = _metric(ablation.result.metrics.rerank_recall_at_10)
    if first is None or second is None:
        return ComparisonMetrics(rewriteRerankRecallDelta="not_applicable", rewriteRegression=False)
    return ComparisonMetrics(rewriteRerankRecallDelta=first - second, rewriteRegression=first < second)


def _write_exclusive(path: Path, value: object) -> None:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=False, separators=(",", ":")).encode("utf-8") + b"\n"
    with path.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def _write_atomic_new(path: Path, value: object) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    if path.exists() or temporary.exists():
        raise FileExistsError(path)
    try:
        _write_exclusive(temporary, value)
        temporary.rename(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _repository_state_excluding_output(
    *,
    repository_root: Path,
    output_dir: Path,
    allowed_entries: tuple[str, ...] = (),
) -> tuple[str, tuple[str, ...]]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    raw = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    try:
        relative_output = output_dir.resolve().relative_to(repository_root.resolve()).as_posix().rstrip("/") + "/"
    except ValueError:
        relative_output = None
    entries: list[str] = []
    allowed = set(allowed_entries)
    for line in raw.splitlines():
        if not line:
            continue
        if line in allowed:
            continue
        path = line[3:].replace("\\", "/")
        if relative_output is not None and path.startswith(relative_output):
            continue
        entries.append(line)
    return commit, tuple(entries)


@dataclass(frozen=True, slots=True, kw_only=True)
class PendingCase:
    case: EvaluationCase
    primary: LiveEvaluatedVariant
    ablation: LiveEvaluatedVariant


async def _execute_pairs(
    *,
    cases: tuple[EvaluationCase, ...],
    bootstrap: LiveEvaluationBootstrapResult,
) -> tuple[PendingCase, ...]:
    bootstrap.executors.validate_pair()
    pending: list[PendingCase] = []
    for case in cases:
        before_primary = bootstrap.executors.primary.calls
        before_ablation = bootstrap.executors.rewrite_ablation.calls
        primary = await bootstrap.executors.primary.execute(case=case, fixture=bootstrap.fixture)
        ablation = await bootstrap.executors.rewrite_ablation.execute(case=case, fixture=bootstrap.fixture)
        if (
            bootstrap.executors.primary.calls - before_primary != 1
            or bootstrap.executors.rewrite_ablation.calls - before_ablation != 1
        ):
            raise EvaluationRunError("evaluation.capability_call_count_invalid")
        pending.append(PendingCase(case=case, primary=primary, ablation=ablation))
    if (
        len(pending) != 26
        or bootstrap.executors.primary.calls != 26
        or bootstrap.executors.rewrite_ablation.calls != 26
    ):
        raise EvaluationRunError("evaluation.case_pair_incomplete")
    return tuple(pending)


def _prepare_review_material(*, repository_root: Path, run_id: str, pending: tuple[PendingCase, ...]) -> Path:
    review_root = repository_root / ".tmp" / "p5-live" / run_id
    if review_root.exists():
        raise EvaluationRunError("evaluation.live_review_state_exists")
    review_root.mkdir(parents=True)
    materials = [
        item.primary.review_material.as_dict()
        for item in pending
        if isinstance(item.primary.review_material, ReviewMaterial)
    ]
    if len(materials) != 26:
        raise EvaluationRunError("evaluation.live_review_material_incomplete")
    _write_exclusive(
        review_root / "review-material.json",
        {
            "schemaVersion": 1,
            "runId": run_id,
            "instructions": {
                "answerable": "faithful/relevant/sufficientForInitialAnswer; useful must equal all three",
                "nonAnswerable": "all booleans false and judgmentReason gold_issue",
                "allowedReasons": ["none", "quote_context", "relevance", "coverage", "gold_issue"],
            },
            "cases": materials,
        },
    )
    return review_root


async def _wait_for_rubric(*, review_root: Path, run_id: str, cases: tuple[EvaluationCase, ...]) -> HumanRubricSubmission:
    decisions_path = review_root / "review-decisions.json"
    print(f"P5_REVIEW_READY={review_root}", flush=True)
    for _ in range(_REVIEW_TIMEOUT_SECONDS):
        if decisions_path.is_file():
            value, _ = strict_json_bytes(decisions_path)
            submission = HumanRubricSubmission.model_validate(value)
            if submission.run_id != run_id or tuple(item.case_id for item in submission.decisions) != tuple(
                case.case_id for case in cases
            ):
                raise EvaluationRunError("evaluation.live_rubric_binding_invalid")
            by_id = {case.case_id: case for case in cases}
            for decision in submission.decisions:
                case = by_id[decision.case_id]
                if case.expected_answerability != "answerable" and (
                    decision.faithful
                    or decision.relevant
                    or decision.sufficient_for_initial_answer
                    or decision.useful
                    or decision.judgment_reason != "gold_issue"
                ):
                    raise EvaluationRunError("evaluation.live_rubric_non_answerable_invalid")
            return submission
        await asyncio.sleep(1)
    raise EvaluationRunError("evaluation.live_rubric_timeout")


def _build_case_results(
    *,
    pending: tuple[PendingCase, ...],
    rubric: HumanRubricSubmission,
) -> tuple[EvaluationCaseResult, ...]:
    decisions = {item.case_id: item for item in rubric.decisions}
    output: list[EvaluationCaseResult] = []
    for item in pending:
        decision = decisions[item.case.case_id]
        output.append(
            EvaluationCaseResult(
                caseId=item.case.case_id,
                primary=item.primary.result,
                rewriteAblation=item.ablation.result,
                comparisonMetrics=_comparison(item.primary, item.ablation),
                primaryJudgment=PrimaryHumanJudgment(
                    faithful=decision.faithful,
                    relevant=decision.relevant,
                    sufficientForInitialAnswer=decision.sufficient_for_initial_answer,
                    useful=decision.useful,
                    judgmentReason=decision.judgment_reason,
                ),
            )
        )
    return tuple(output)


def _journal_counts(path: Path) -> tuple[int, int]:
    started = 0
    terminal = 0
    ordinals: dict[int, set[str]] = {}
    for line in path.read_bytes().splitlines():
        value = json.loads(line.decode("utf-8"))
        if type(value) is not dict or value.get("schemaVersion") != 1 or type(value.get("callOrdinal")) is not int:
            raise EvaluationRunError("evaluation.live_attempt_journal_invalid")
        ordinal = cast(int, value["callOrdinal"])
        event = value.get("event")
        if event not in {"started", "terminal"}:
            raise EvaluationRunError("evaluation.live_attempt_journal_invalid")
        ordinals.setdefault(ordinal, set()).add(cast(str, event))
        started += event == "started"
        terminal += event == "terminal"
    if any(events != {"started", "terminal"} for events in ordinals.values()) or set(ordinals) != set(
        range(1, len(ordinals) + 1)
    ):
        raise EvaluationRunError("evaluation.live_attempt_journal_invalid")
    return started, terminal


async def run_live(
    *,
    dataset_path: Path,
    output_dir: Path,
    repository_root: Path,
    bootstrap: LiveEvaluationBootstrapResult,
) -> EvaluationRunResult:
    started_at = _utc_now()
    dataset_version, dataset_sha256, cases = load_dataset(dataset_path)
    if (
        dataset_sha256 != bootstrap.manifest.dataset_sha256
        or len(cases) != bootstrap.manifest.dataset_case_count
        or output_dir.name != bootstrap.manifest.run_id
    ):
        raise EvaluationRunError("evaluation.live_manifest_dataset_mismatch")
    review_root: Path | None = None
    try:
        pending = await _execute_pairs(cases=cases, bootstrap=bootstrap)
        review_root = _prepare_review_material(
            repository_root=repository_root,
            run_id=bootstrap.manifest.run_id,
            pending=pending,
        )
        rubric = await _wait_for_rubric(review_root=review_root, run_id=bootstrap.manifest.run_id, cases=cases)
        case_results = _build_case_results(pending=pending, rubric=rubric)
    finally:
        if review_root is not None and review_root.exists():
            shutil.rmtree(review_root)

    evaluated = tuple(
        EvaluatedCase(case=case, result=result)
        for case, result in zip(cases, case_results, strict=True)
    )
    population = derive_effect_metric_population(evaluated)
    metrics = compute_metrics(evaluated, population=population)
    denied_calls = sum(
        result.primary.model_call_counts.summary + result.rewrite_ablation.model_call_counts.summary
        for case, result in zip(cases, case_results, strict=True)
        if case.expected_answerability == "model_egress_denied"
    )
    safety = SafetyGateResult(
        deniedSummaryCallCount=denied_calls,
        unauthorizedContentCount=bootstrap.model_transport.unauthorized_content_count,
        citationValidityRate=metrics.citation_validity_rate,
        constraintPreservationRate=metrics.constraint_preservation_rate,
        passed=(
            denied_calls == 0
            and bootstrap.model_transport.unauthorized_content_count == 0
            and metrics.citation_validity_rate == 1.0
            and metrics.constraint_preservation_rate == 1.0
        ),
    )
    commit, entries = _repository_state_excluding_output(
        repository_root=repository_root,
        output_dir=output_dir,
        allowed_entries=bootstrap.allowed_worktree_entries,
    )
    if commit != bootstrap.snapshot.git_commit or entries:
        raise EvaluationRunError("evaluation.snapshot_changed")
    conclusion: Literal["effective", "partially_effective", "ineffective", "invalid_run"]
    if bootstrap.model_transport.total_calls == 0:
        conclusion = "invalid_run"
    else:
        conclusion = classify_conclusion(
            metrics=metrics,
            safety=safety,
            snapshot=bootstrap.snapshot,
            population=population,
        )
    result = EvaluationRunResult(
        schemaVersion=1,
        runId=bootstrap.manifest.run_id,
        startedAt=started_at,
        finishedAt=_utc_now(),
        datasetVersion=dataset_version,
        datasetSha256=dataset_sha256,
        gitCommit=bootstrap.snapshot.git_commit,
        worktreeDirty=False,
        providerMode="live",
        evaluationVariants=("primary", "rewrite_ablation"),
        principalProfileId=bootstrap.snapshot.principal_profile_id,
        readAuthorizationEvidenceRef=bootstrap.snapshot.read_authorization_evidence_ref,
        gateEvidence=bootstrap.snapshot.gate_evidence,
        questionPolicyVersion=bootstrap.snapshot.question_policy_version,
        domainCatalogVersion=bootstrap.snapshot.domain_catalog_version,
        flowConfigVersion=bootstrap.snapshot.flow_config_version,
        retrievalProfileVersion=bootstrap.snapshot.retrieval_profile_version,
        indexSnapshotIds=bootstrap.snapshot.index_snapshot_ids,
        embeddingModel=bootstrap.snapshot.embedding_model,
        rerankModel=bootstrap.snapshot.rerank_model,
        modelTaskVersions=bootstrap.snapshot.model_task_versions,
        deepSeekModel=bootstrap.snapshot.deep_seek_model,
        policyCatalogVersion=bootstrap.snapshot.policy_catalog_version,
        policyCatalogSha256=bootstrap.snapshot.policy_catalog_sha256,
        policyAuthorityId=bootstrap.snapshot.policy_authority_id,
        policyExportId=bootstrap.snapshot.policy_export_id,
        policySourceRevision=bootstrap.snapshot.policy_source_revision,
        evidenceRulesVersion=bootstrap.snapshot.evidence_rules_version,
        caseResults=case_results,
        aggregateMetrics=metrics,
        safetyGate=safety,
        conclusion=conclusion,
        reviewer=rubric.reviewer,
    )
    payload = result.model_dump(by_alias=True, mode="json")
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    validate_result_bytes(raw)
    started_count, terminal_count = _journal_counts(output_dir / "paid-attempts.jsonl")
    if (
        started_count != bootstrap.model_transport.total_calls
        or terminal_count != bootstrap.model_transport.total_calls
        or bootstrap.model_transport.total_calls > bootstrap.manifest.paid_request_budget.maximum_paid_requests
        or bootstrap.model_transport.rewrite_calls > bootstrap.manifest.paid_request_budget.knowledge_rewrite
        or bootstrap.model_transport.summary_calls > bootstrap.manifest.paid_request_budget.knowledge_summary
    ):
        raise EvaluationRunError("evaluation.live_paid_budget_invalid")
    _write_atomic_new(output_dir / "result.json", payload)
    result_sha256 = hashlib.sha256((output_dir / "result.json").read_bytes()).hexdigest()
    _write_exclusive(
        output_dir / "evidence.json",
        {
            "schemaVersion": 1,
            "status": "completed" if conclusion != "invalid_run" else "invalid_run",
            "workPackageId": bootstrap.manifest.work_package_id,
            "runId": bootstrap.manifest.run_id,
            "manifestSha256": bootstrap.manifest_sha256,
            "authorizationReference": bootstrap.manifest.authorization_reference,
            "frozenGitCommit": bootstrap.snapshot.git_commit,
            "capabilityExecutions": 52,
            "paidRequests": {
                "knowledgeRewrite": bootstrap.model_transport.rewrite_calls,
                "knowledgeSummary": bootstrap.model_transport.summary_calls,
                "total": bootstrap.model_transport.total_calls,
                "maximum": bootstrap.manifest.paid_request_budget.maximum_paid_requests,
                "retry": 0,
                "coreAnswer": 0,
            },
            "journalStarted": started_count,
            "journalTerminal": terminal_count,
            "schemaValidated": True,
            "humanRubricCompleted": True,
            "conclusion": conclusion,
            "resultSha256": result_sha256,
            "jwtPersisted": False,
            "apiKeyPersisted": False,
            "questionOrEvidencePersistedOutsideDatasetAndResult": False,
        },
    )
    return result


def _failure_code(exc: BaseException) -> Literal[
    "bootstrap_invalid", "dataset_invalid", "snapshot_changed", "execution_failed", "schema_invalid", "write_failed"
]:
    text = str(exc)
    if isinstance(exc, LiveEvaluationBootstrapError):
        return "bootstrap_invalid"
    if "dataset" in text:
        return "dataset_invalid"
    if "snapshot_changed" in text:
        return "snapshot_changed"
    if isinstance(exc, ValidationError) or "schema" in text or "rubric" in text:
        return "schema_invalid"
    return "execution_failed"


def _write_failure_if_possible(
    *,
    output_dir: Path,
    run_id: str,
    started_at: str,
    git_commit: str,
    dataset_sha256: str,
    failure_code: Literal[
        "bootstrap_invalid", "dataset_invalid", "snapshot_changed", "execution_failed", "schema_invalid", "write_failed"
    ],
) -> None:
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        record = EvaluationFailureRecord(
            schemaVersion=1,
            runId=run_id,
            startedAt=started_at,
            finishedAt=_utc_now(),
            gitCommit=git_commit,
            datasetSha256=dataset_sha256,
            failureCode=failure_code,
        )
        _write_exclusive(output_dir / "failure.json", record.model_dump(by_alias=True, mode="json"))
    except (OSError, ValidationError, FileExistsError):
        return


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


async def _main_async() -> int:
    arguments = _parser().parse_args()
    repository_root = Path(__file__).resolve().parents[4]
    started_at = _utc_now()
    dataset_sha256 = hashlib.sha256(arguments.dataset.read_bytes()).hexdigest() if arguments.dataset.is_file() else "0" * 64
    try:
        git_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        git_commit = "0" * 40
    bootstrap: LiveEvaluationBootstrapResult | None = None
    try:
        bootstrap = await build_live_from_environment(
            environ=os.environ,
            repository_root=repository_root,
            output_dir=arguments.output,
        )
        result = await run_live(
            dataset_path=arguments.dataset,
            output_dir=arguments.output,
            repository_root=repository_root,
            bootstrap=bootstrap,
        )
        return 2 if result.conclusion == "invalid_run" else 0
    except (LiveEvaluationBootstrapError, EvaluationRunError, ValidationError, OSError, ValueError, RuntimeError) as exc:
        run_id = arguments.output.name if arguments.output.name else "failed-p5-live"
        _write_failure_if_possible(
            output_dir=arguments.output,
            run_id=run_id,
            started_at=started_at,
            git_commit=git_commit,
            dataset_sha256=dataset_sha256,
            failure_code=_failure_code(exc),
        )
        print(f"P5_LIVE_FAILED={_failure_code(exc)}", flush=True)
        return 3
    finally:
        if bootstrap is not None:
            await bootstrap.aclose()


def main() -> int:
    return asyncio.run(_main_async())


if __name__ == "__main__":
    raise SystemExit(main())
