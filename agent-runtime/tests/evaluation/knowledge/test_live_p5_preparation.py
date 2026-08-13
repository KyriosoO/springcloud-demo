from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal, cast

import pytest
from pydantic import ValidationError

from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.model.contracts import (
    ModelTaskId,
    StructuredFinishKind,
    StructuredModelRequest,
    StructuredModelResponse,
    StructuredOutputMode,
    StructuredToolMode,
)
from tests.evaluation.knowledge.bootstrap import build_from_environment
from tests.evaluation.knowledge.contracts import (
    EvaluationCase,
    EvaluationExecutionFixture,
    EvaluationVariantResult,
    ModelCallCountRecord,
    PathRankingRecord,
    VariantCaseMetrics,
)
from tests.evaluation.knowledge.live_bootstrap import authorization_path, manifest_path
from tests.evaluation.knowledge.live_contracts import (
    BudgetedLiveModelTransport,
    HumanRubricSubmission,
    LiveP5Manifest,
    load_authorization,
    load_manifest,
    verify_manifest_assets,
)
from tests.evaluation.knowledge.live_executor import LiveEvaluatedVariant, _top_document_ids
from tests.evaluation.knowledge.live_runner import _execute_pairs, _repository_state_excluding_output
from tests.evaluation.knowledge.run_evaluation import load_dataset, run, validate_result_bytes


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DATASET = Path(__file__).with_name("representative_questions.v1.jsonl")


class FakeTransport:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        del request, call_deadline
        self.calls += 1
        if self.fail:
            raise RuntimeError("synthetic.transport_failure")
        return StructuredModelResponse(
            finish_kind=StructuredFinishKind.STOP,
            content='{"outcome":"insufficient_evidence","points":[]}',
            tool_calls=(),
            usage_total_tokens=1,
        )


def _request(task_id: ModelTaskId) -> StructuredModelRequest:
    payload = '{"question":"synthetic"}' if task_id is ModelTaskId.KNOWLEDGE_REWRITE else '{"evidence":[]}'
    return StructuredModelRequest(
        task_id=task_id,
        task_version="1" if task_id is ModelTaskId.KNOWLEDGE_REWRITE else "2",
        system_instruction="synthetic fixed instruction",
        user_payload_json=payload,
        tools=(),
        tool_mode=StructuredToolMode.NONE,
        output_mode=StructuredOutputMode.JSON_OBJECT,
        max_output_tokens=16,
    )


def _variant(variant: Literal["primary", "rewrite_ablation"]) -> EvaluationVariantResult:
    return EvaluationVariantResult(
        variant=variant,
        terminalStatus="no_result",
        rewriteMode="model" if variant == "primary" else "original_fallback",
        selectedDomainIds=(),
        pathRankings=(),
        fusedTop10DocumentIds=(),
        rerankedTop10DocumentIds=(),
        adoptedEvidenceIds=(),
        summaryStatus="not_called",
        modelCallCounts=ModelCallCountRecord(
            rewrite=1 if variant == "primary" else 0,
            embedding=0,
            keywordRetrieval=0,
            vectorRetrieval=0,
            rerank=0,
            summary=0,
            coreAnswer=0,
        ),
        metrics=VariantCaseMetrics(
            constraintPreserved=1.0 if variant == "primary" else "not_applicable",
            pathHitAt10="not_applicable",
            fusionRecallAt10="not_applicable",
            fusionMrrAt10="not_applicable",
            rerankRecallAt10="not_applicable",
            rerankMrrAt10="not_applicable",
            requiredEvidenceCoverage="not_applicable",
            citationValidityRate="not_applicable",
        ),
    )


class FakeExecutor:
    def __init__(self, variant: Literal["primary", "rewrite_ablation"]) -> None:
        self.variant = variant
        self.calls = 0
        self.component_signature = "fake-live-pair-v1"

    async def execute(
        self,
        *,
        case: EvaluationCase,
        fixture: EvaluationExecutionFixture,
    ) -> LiveEvaluatedVariant:
        del case, fixture
        self.calls += 1
        return LiveEvaluatedVariant(result=_variant(self.variant), review_material=None)


class FakeExecutors:
    def __init__(self) -> None:
        self.primary = FakeExecutor("primary")
        self.rewrite_ablation = FakeExecutor("rewrite_ablation")

    def validate_pair(self) -> None:
        assert self.primary.component_signature == self.rewrite_ablation.component_signature


def _unused_scope(case_id: str, variant: str, question: str) -> RequestExecutionScope:
    del case_id, variant, question
    raise AssertionError("fake pair executor must not request a scope")


def test_frozen_live_manifest_authorization_and_assets_are_strict() -> None:
    manifest, digest = load_manifest(manifest_path(REPOSITORY_ROOT))
    authorization = load_authorization(authorization_path(REPOSITORY_ROOT))

    assert len(digest) == 64
    assert manifest.run_id == authorization.run_id
    assert manifest.authorization_reference == authorization.authorization_reference
    assert manifest.paid_request_budget.capability_executions == 52
    assert manifest.paid_request_budget.maximum_paid_requests == 78
    assert authorization.maximum_paid_requests == 78
    assert manifest.schema_version == 2
    assert manifest.retrieval_binding is not None
    assert manifest.index_snapshot_ids == (
        manifest.retrieval_binding.policy_snapshot_id,
        manifest.retrieval_binding.law_snapshot_id,
    )
    verify_manifest_assets(manifest=manifest, repository_root=REPOSITORY_ROOT)


def test_live_document_rankings_deduplicate_before_top_ten() -> None:
    raw = ("doc-1", "doc-1", *(f"doc-{index}" for index in range(2, 12)))

    actual = _top_document_ids(raw)
    ranking = PathRankingRecord(logicalDomainId="tax.policy", path="keyword", documentIds=actual)

    assert actual == tuple(f"doc-{index}" for index in range(1, 11))
    assert ranking.document_ids == actual
    with pytest.raises(ValidationError, match="evaluation.invalid_document_ids"):
        PathRankingRecord(logicalDomainId="tax.policy", path="keyword", documentIds=raw[:2])


def test_live_manifest_retrieval_binding_is_fail_closed_and_launcher_owned() -> None:
    manifest, _ = load_manifest(manifest_path(REPOSITORY_ROOT))
    payload = manifest.model_dump(by_alias=True, mode="json")
    payload["retrievalBinding"]["policySnapshotId"] = "0" * 64

    with pytest.raises(ValidationError, match="policySnapshotId"):
        LiveP5Manifest.model_validate(payload)

    launcher = (REPOSITORY_ROOT / "agent-runtime/scripts/run-knowledge-p5-live.ps1").read_text(encoding="utf-8")
    for key, field in {
        "AGENT_KNOWLEDGE_READ_ALIAS": "readAlias",
        "AGENT_KNOWLEDGE_EXPECTED_INDEX_NAME": "expectedIndexName",
        "AGENT_KNOWLEDGE_EXPECTED_INDEX_UUID": "expectedIndexUuid",
        "AGENT_KNOWLEDGE_MAPPING_VERSION": "mappingVersion",
        "AGENT_KNOWLEDGE_POLICY_SNAPSHOT_ID": "policySnapshotId",
        "AGENT_KNOWLEDGE_LAW_SNAPSHOT_ID": "lawSnapshotId",
    }.items():
        assert f"$env:{key} = [string]$manifest.retrievalBinding.{field}" in launcher


@pytest.mark.asyncio
async def test_fake_pair_executor_runs_exactly_fifty_two_capability_executions() -> None:
    _, _, cases = load_dataset(DATASET)
    executors = FakeExecutors()
    bootstrap = SimpleNamespace(
        executors=executors,
        fixture=EvaluationExecutionFixture(make_scope=_unused_scope, synthetic_only=True),
    )

    result = await _execute_pairs(cases=cases, bootstrap=cast(Any, bootstrap))

    assert len(result) == 26
    assert executors.primary.calls == 26
    assert executors.rewrite_ablation.calls == 26


@pytest.mark.asyncio
async def test_fake_transport_enforces_exact_paid_ceiling_and_zero_retry(tmp_path: Path) -> None:
    manifest, digest = load_manifest(manifest_path(REPOSITORY_ROOT))
    delegate = FakeTransport()
    transport = BudgetedLiveModelTransport(
        delegate=delegate,
        output_dir=tmp_path / "run",
        manifest=manifest,
        manifest_sha256=digest,
        frozen_head="a" * 40,
    )

    for ordinal in range(26):
        case_id = f"case-{ordinal:02d}"
        transport.begin(case_id=case_id, variant="primary")
        await transport.complete(_request(ModelTaskId.KNOWLEDGE_REWRITE), call_deadline=1.0)
        await transport.complete(_request(ModelTaskId.KNOWLEDGE_SUMMARY), call_deadline=1.0)
        transport.end()
        transport.begin(case_id=case_id, variant="rewrite_ablation")
        await transport.complete(_request(ModelTaskId.KNOWLEDGE_SUMMARY), call_deadline=1.0)
        transport.end()

    assert delegate.calls == 78
    assert transport.rewrite_calls == 26
    assert transport.summary_calls == 52
    assert transport.total_calls == 78
    assert len((tmp_path / "run" / "paid-attempts.jsonl").read_text(encoding="utf-8").splitlines()) == 156
    transport.begin(case_id="overflow", variant="primary")
    with pytest.raises(RuntimeError, match="budget_exhausted"):
        await transport.complete(_request(ModelTaskId.KNOWLEDGE_REWRITE), call_deadline=1.0)
    transport.end()


@pytest.mark.asyncio
async def test_fake_transport_failure_is_terminal_and_same_attempt_cannot_retry(tmp_path: Path) -> None:
    manifest, digest = load_manifest(manifest_path(REPOSITORY_ROOT))
    transport = BudgetedLiveModelTransport(
        delegate=FakeTransport(fail=True),
        output_dir=tmp_path / "failed",
        manifest=manifest,
        manifest_sha256=digest,
        frozen_head="b" * 40,
    )
    transport.begin(case_id="case-failure", variant="primary")
    with pytest.raises(RuntimeError, match="synthetic.transport_failure"):
        await transport.complete(_request(ModelTaskId.KNOWLEDGE_REWRITE), call_deadline=1.0)
    with pytest.raises(RuntimeError, match="retry_forbidden"):
        await transport.complete(_request(ModelTaskId.KNOWLEDGE_REWRITE), call_deadline=1.0)
    transport.end()

    events = [json.loads(line) for line in (tmp_path / "failed" / "paid-attempts.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [item["event"] for item in events] == ["started", "terminal"]
    assert events[-1]["status"] == "failed"


@pytest.mark.asyncio
async def test_existing_fake_harness_runs_representative_pairs_and_emits_strict_result_schema(tmp_path: Path) -> None:
    bootstrap = build_from_environment(environ={})

    result = await run(
        dataset_path=DATASET,
        output_dir=tmp_path / "stub-result",
        snapshot=bootstrap.snapshot,
        executors=bootstrap.executors,
        fixture=bootstrap.fixture,
    )

    assert bootstrap.executors.primary.calls == 26
    assert bootstrap.executors.rewrite_ablation.calls == 26
    assert result.conclusion == "invalid_run"
    validate_result_bytes((tmp_path / "stub-result" / "result.json").read_bytes())


def test_human_rubric_is_strict_and_useful_is_derived_from_three_axes() -> None:
    with pytest.raises(ValidationError, match="live_rubric"):
        HumanRubricSubmission.model_validate(
            {
                "schemaVersion": 1,
                "runId": "knowledge-p5-live-v1-20260813-candidate-01",
                "reviewer": "project-maintainer",
                "decisions": [
                    {
                        "caseId": f"case-{index:02d}",
                        "faithful": True,
                        "relevant": True,
                        "sufficientForInitialAnswer": True,
                        "useful": False,
                        "judgmentReason": "none",
                    }
                    for index in range(26)
                ],
            }
        )


def test_repository_state_supports_output_outside_worktree(tmp_path: Path) -> None:
    commit, entries = _repository_state_excluding_output(
        repository_root=REPOSITORY_ROOT,
        output_dir=tmp_path / "external-run",
    )

    assert len(commit) == 40
    assert all(entry for entry in entries)
