from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from tests.evaluation.knowledge.bootstrap import EvaluationBootstrapError, build_from_environment
from tests.evaluation.knowledge.run_evaluation import EvaluationRunError, run, write_failure


DATASET = Path(__file__).with_name("synthetic_questions.v1.jsonl")


@pytest.mark.parametrize(
    "environment,code",
    (
        ({"P5_KNOWLEDGE_UNKNOWN": "x"}, "unknown_environment_key"),
        ({"P5_KNOWLEDGE_MODE": "live"}, "live_not_available"),
        ({"P5_KNOWLEDGE_USER_JWT": "header.payload.signature"}, "stub_rejects_live_credentials"),
        ({"P5_KNOWLEDGE_AUTH_EVIDENCE_REF": "fake"}, "stub_rejects_live_credentials"),
    ),
)
def test_stub_bootstrap_fails_closed_for_live_inputs(environment: dict[str, str], code: str) -> None:
    with pytest.raises(EvaluationBootstrapError, match=code):
        build_from_environment(environ=environment)


@pytest.mark.asyncio
async def test_paired_execution_calls_capability_once_per_variant_and_is_reproducible(tmp_path: Path) -> None:
    first_bootstrap = build_from_environment(environ={})
    second_bootstrap = build_from_environment(environ={})
    first = await run(
        dataset_path=DATASET,
        output_dir=tmp_path / "first",
        snapshot=first_bootstrap.snapshot,
        executors=first_bootstrap.executors,
        fixture=first_bootstrap.fixture,
    )
    second = await run(
        dataset_path=DATASET,
        output_dir=tmp_path / "second",
        snapshot=second_bootstrap.snapshot,
        executors=second_bootstrap.executors,
        fixture=second_bootstrap.fixture,
    )
    assert first_bootstrap.executors.primary.calls == 1
    assert first_bootstrap.executors.rewrite_ablation.calls == 1
    assert first.case_results == second.case_results
    assert first.aggregate_metrics == second.aggregate_metrics
    assert first.safety_gate == second.safety_gate
    assert first.conclusion == second.conclusion == "invalid_run"


@pytest.mark.asyncio
async def test_runner_never_overwrites_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    bootstrap = build_from_environment(environ={})
    with pytest.raises(EvaluationRunError, match="output_exists"):
        await run(
            dataset_path=DATASET,
            output_dir=output,
            snapshot=bootstrap.snapshot,
            executors=bootstrap.executors,
            fixture=bootstrap.fixture,
        )
    assert list(output.iterdir()) == []


@pytest.mark.asyncio
async def test_direct_runner_rejects_manually_constructed_live_snapshot(tmp_path: Path) -> None:
    bootstrap = build_from_environment(environ={})
    with pytest.raises(EvaluationRunError, match="live_run_not_authorized"):
        await run(
            dataset_path=DATASET,
            output_dir=tmp_path / "live",
            snapshot=replace(bootstrap.snapshot, provider_mode="live"),
            executors=bootstrap.executors,
            fixture=bootstrap.fixture,
        )


@pytest.mark.asyncio
async def test_persisted_result_contains_only_two_fixed_variants(tmp_path: Path) -> None:
    bootstrap = build_from_environment(environ={})
    output = tmp_path / "run"
    await run(
        dataset_path=DATASET,
        output_dir=output,
        snapshot=bootstrap.snapshot,
        executors=bootstrap.executors,
        fixture=bootstrap.fixture,
    )
    value = json.loads((output / "result.json").read_text(encoding="utf-8"))
    assert value["evaluationVariants"] == ["primary", "rewrite_ablation"]
    assert value["caseResults"][0]["primary"]["variant"] == "primary"
    assert value["caseResults"][0]["rewriteAblation"]["variant"] == "rewrite_ablation"


def test_failure_record_is_bounded_and_append_only(tmp_path: Path) -> None:
    output = tmp_path / "failure"
    record = write_failure(
        output_dir=output,
        run_id="failed-synthetic",
        started_at="2026-08-03T00:00:00Z",
        git_commit="0" * 40,
        dataset_sha256="1" * 64,
        failure_code="dataset_invalid",
    )
    value = json.loads((output / "failure.json").read_text(encoding="utf-8"))
    assert value == record.model_dump(by_alias=True, mode="json")
    assert set(value) == {"schemaVersion", "runId", "startedAt", "finishedAt", "gitCommit", "datasetSha256", "failureCode"}
    with pytest.raises(FileExistsError):
        write_failure(
            output_dir=output,
            run_id="failed-synthetic",
            started_at="2026-08-03T00:00:00Z",
            git_commit="0" * 40,
            dataset_sha256="1" * 64,
            failure_code="dataset_invalid",
        )
