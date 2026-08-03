from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping, cast

from agent_runtime.capability_api.contracts import CapabilityExecutionContext, OpaqueUserToken, SubjectType
from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.knowledge.capability import KnowledgeQueryCapability
from agent_runtime.knowledge.catalog import build_tax_domain_catalog
from agent_runtime.knowledge.domain_selection import DeterministicDomainSelector
from agent_runtime.knowledge.evidence.stage import DefaultKnowledgeEvidenceStage
from agent_runtime.knowledge.evidence.summary_task import KnowledgeSummaryTaskV1
from agent_runtime.knowledge.planning import KnowledgeRetrievalPlanBuilder
from agent_runtime.knowledge.retrieval.contracts import RankedKnowledgeBatch, RankedKnowledgeCandidate
from agent_runtime.knowledge.settings import KnowledgeSettings
from agent_runtime.model.context import ModelCallContextAccessor
from agent_runtime.model.contracts import StructuredModelGateway
from agent_runtime.model.input_guard import QuestionEgressGuard

from tests.evaluation.knowledge.contracts import (
    EvaluationExecutionFixture,
    EvaluationSystemSnapshot,
    GateEvidenceRecord,
)
from tests.evaluation.knowledge.executor import (
    EvaluationExecutors,
    IdentityQuestionRewriter,
    KnowledgeEvaluationCaseExecutor,
    RecordingEvidenceStage,
    StubQuestionRewriter,
    SyntheticRetrievalStage,
    SyntheticSummaryGateway,
)
from tests.evidence_helpers import synthetic_catalog
from tests.helpers import ManualCancellationSignal
from tests.retrieval_helpers import candidate


_P5_KEYS = frozenset(
    {
        "P5_KNOWLEDGE_MODE",
        "P5_KNOWLEDGE_LIVE_OPT_IN",
        "P5_KNOWLEDGE_USER_JWT",
        "P5_KNOWLEDGE_AUTH_EVIDENCE_REF",
    }
)
_CONTENT = "合成税务政策证据，仅用于本地评估。"


class EvaluationBootstrapError(ValueError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class EvaluationBootstrapResult:
    snapshot: EvaluationSystemSnapshot
    executors: EvaluationExecutors
    fixture: EvaluationExecutionFixture


def read_repository_state(root: Path) -> tuple[str, bool, tuple[str, ...]]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    entries = tuple(line for line in status.splitlines() if line)
    return commit, bool(entries), entries


def _build_executor(*, variant: Literal["primary", "rewrite_ablation"]) -> KnowledgeEvaluationCaseExecutor:
    item = candidate(content=_CONTENT)
    batch = RankedKnowledgeBatch(
        candidates=(RankedKnowledgeCandidate(candidate=item, domain_ids=("tax.policy",), rerank_score=1.0, rank=1),),
        profile_version="tax-knowledge-search-v1",
        index_snapshot_ids=("a" * 64,),
    )
    rewriter = StubQuestionRewriter(mode="primary") if variant == "primary" else IdentityQuestionRewriter()
    retrieval = SyntheticRetrievalStage(batch)
    gateway = SyntheticSummaryGateway(_CONTENT)
    evidence = RecordingEvidenceStage(
        DefaultKnowledgeEvidenceStage(
            catalog=synthetic_catalog(),
            guard=QuestionEgressGuard(),
            context=ModelCallContextAccessor(),
            gateway=cast(StructuredModelGateway, gateway),
            definition=KnowledgeSummaryTaskV1.definition(),
        )
    )
    settings = KnowledgeSettings.from_env(
        {"AGENT_KNOWLEDGE_ENABLED": "true", "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy"}
    )
    capability = KnowledgeQueryCapability(
        settings=settings,
        enabled_domains=build_tax_domain_catalog().enabled(settings.enabled_domain_ids),
        rewriter=rewriter,
        selector=DeterministicDomainSelector(),
        planner=KnowledgeRetrievalPlanBuilder(),
        retrieval=retrieval,
        evidence=evidence,
    )
    return KnowledgeEvaluationCaseExecutor(
        variant=variant,
        capability=capability,
        rewriter=rewriter,
        retrieval=retrieval,
        evidence=evidence,
        summary_gateway=gateway,
        component_signature="knowledge-capability-v1|synthetic-retrieval-v1|evidence-v1|summary-stub-v1",
    )


def build_from_environment(*, environ: Mapping[str, str]) -> EvaluationBootstrapResult:
    unknown = sorted(key for key in environ if key.startswith("P5_KNOWLEDGE_") and key not in _P5_KEYS)
    if unknown:
        raise EvaluationBootstrapError("evaluation.unknown_environment_key")
    mode = environ.get("P5_KNOWLEDGE_MODE", "stub")
    if mode not in {"stub", "live"}:
        raise EvaluationBootstrapError("evaluation.invalid_mode")
    if mode == "live":
        raise EvaluationBootstrapError("evaluation.live_not_available_in_synthetic_harness")
    if any(environ.get(key) for key in _P5_KEYS - {"P5_KNOWLEDGE_MODE"}):
        raise EvaluationBootstrapError("evaluation.stub_rejects_live_credentials")
    repository_root = Path(__file__).resolve().parents[4]
    git_commit, worktree_dirty, worktree_entries = read_repository_state(repository_root)

    def make_scope(case_id: str, variant: str, question: str) -> RequestExecutionScope:
        import asyncio

        loop = asyncio.get_running_loop()
        return RequestExecutionScope(
            context=CapabilityExecutionContext(
                request_id=f"eval-{case_id}-{variant}",
                correlation_id=f"eval-corr-{case_id}-{variant}",
                original_question=question,
                subject_id="synthetic-controlled-user",
                subject_type=SubjectType.USER,
                user_token=OpaqueUserToken.from_raw("synthetic.invalid.token"),
                deadline_monotonic=loop.time() + 10.0,
                cancellation=ManualCancellationSignal(),
            )
        )

    gates = (
        GateEvidenceRecord(gateId="SA-GATE-002", evidenceRef="open-synthetic-only"),
        GateEvidenceRecord(gateId="CR-GATE-003", evidenceRef="open-synthetic-only"),
        GateEvidenceRecord(gateId="SA-GATE-003", evidenceRef="open-synthetic-only"),
        GateEvidenceRecord(gateId="SA-GATE-006", evidenceRef="open-synthetic-only"),
    )
    snapshot = EvaluationSystemSnapshot(
        repository_root=str(repository_root),
        worktree_entries=worktree_entries,
        git_commit=git_commit,
        worktree_dirty=worktree_dirty,
        provider_mode="stub",
        principal_profile_id="synthetic-controlled-user-v1",
        read_authorization_evidence_ref="synthetic-fixture-only",
        gate_evidence=gates,
        question_policy_version="question-egress-v1",
        domain_catalog_version="tax-domain-catalog-v1",
        flow_config_version="knowledge-flow-config-v1",
        retrieval_profile_version="tax-knowledge-search-v1",
        index_snapshot_ids=("a" * 64,),
        embedding_model="synthetic-bge-m3-stub",
        rerank_model="synthetic-bge-reranker-v2-m3-stub",
        model_task_versions={
            "action_selection": "1",
            "answer_generation": "1",
            "knowledge_rewrite": "1",
            "knowledge_summary": "1",
        },
        deep_seek_model="not-used-stub",
        policy_catalog_version="synthetic-v1",
        policy_catalog_sha256="0" * 64,
        policy_authority_id="synthetic-authority",
        policy_export_id="synthetic-export",
        policy_source_revision="synthetic-revision",
        evidence_rules_version="knowledge-evidence-v1",
    )
    executors = EvaluationExecutors(
        primary=_build_executor(variant="primary"),
        rewrite_ablation=_build_executor(variant="rewrite_ablation"),
    )
    executors.validate_pair()
    return EvaluationBootstrapResult(
        snapshot=snapshot,
        executors=executors,
        fixture=EvaluationExecutionFixture(make_scope=make_scope, synthetic_only=True),
    )
