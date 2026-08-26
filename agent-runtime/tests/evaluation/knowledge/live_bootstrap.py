from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, cast

import httpx

from agent_runtime.bootstrap import KnowledgeCompositionRoot
from agent_runtime.capability_api.contracts import CapabilityExecutionContext, OpaqueUserToken, SubjectType
from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.knowledge.capability import KnowledgeQueryCapability
from agent_runtime.knowledge.catalog import CATALOG_VERSION, build_tax_domain_catalog
from agent_runtime.knowledge.contracts import KnowledgeQuestionRewriteStage
from agent_runtime.knowledge.domain_selection import DeterministicDomainSelector
from agent_runtime.knowledge.evidence.catalog import KnowledgeEgressPolicyCatalog
from agent_runtime.knowledge.evidence.contracts import KnowledgeSummaryInput, KnowledgeSummaryOutput
from agent_runtime.knowledge.evidence.stage import DefaultKnowledgeEvidenceStage
from agent_runtime.knowledge.planning import KnowledgeRetrievalPlanBuilder
from agent_runtime.knowledge.question_semantics import QuestionSemanticGuard
from agent_runtime.knowledge.retrieval.bge_embedding import BgeM3EmbeddingAdapter
from agent_runtime.knowledge.retrieval.bge_rerank import BgeRerankAdapter
from agent_runtime.knowledge.retrieval.contracts import RankedKnowledgeBatch
from agent_runtime.knowledge.retrieval.es_adapter import EsKnowledgeSearchAdapter
from agent_runtime.knowledge.retrieval.http import HttpxKnowledgeTransport, build_knowledge_http_client
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from agent_runtime.knowledge.rewrite import (
    KnowledgeQuestionRewriter,
    KnowledgeRewriteInput,
    KnowledgeRewriteOutput,
)
from agent_runtime.knowledge.settings import KnowledgeSettings
from agent_runtime.model.context import ModelCallContextAccessor
from agent_runtime.model.contracts import ModelTaskDefinition, StructuredModelGateway
from agent_runtime.model.deepseek.action_selector import build_action_selection_task_definition
from agent_runtime.model.deepseek.answer_generator import build_answer_generation_task_definition
from agent_runtime.model.deepseek.transport import DeepSeekChatTransport, build_deepseek_http_client
from agent_runtime.model.gateway import BoundedStructuredModelGateway
from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.model.settings import ModelProvider, ModelSettings

from tests.evaluation.knowledge.bootstrap import read_repository_state
from tests.evaluation.knowledge.contracts import EvaluationExecutionFixture, EvaluationSystemSnapshot, GateEvidenceRecord
from tests.evaluation.knowledge.executor import IdentityQuestionRewriter
from tests.evaluation.knowledge.live_contracts import (
    BudgetedLiveModelTransport,
    LiveAuthorizationRecord,
    LiveP5Manifest,
    load_authorization,
    load_manifest,
    verify_manifest_assets,
)
from tests.evaluation.knowledge.live_executor import (
    LiveEvaluationExecutors,
    LiveKnowledgeEvaluationCaseExecutor,
    RecordingEmbedding,
    RecordingEvidenceStage,
    RecordingFusion,
    RecordingKnowledgeSearch,
    RecordingQuestionRewriter,
    RecordingRerank,
    RecordingRetrievalStage,
)
from tests.evaluation.knowledge.live_diagnostics import LivePhaseCheckpointJournal
from tests.helpers import ManualCancellationSignal


_P5_KEYS = frozenset(
    {
        "P5_KNOWLEDGE_MODE",
        "P5_KNOWLEDGE_LIVE_OPT_IN",
        "P5_KNOWLEDGE_USER_JWT",
        "P5_KNOWLEDGE_AUTH_EVIDENCE_REF",
        "P5_KNOWLEDGE_CANDIDATE",
    }
)
_LIVE_OPT_IN = "I_UNDERSTAND_LIVE_EXTERNAL_CALLS"
LiveCandidateId = Literal["candidate-03", "candidate-04"]
_DEFAULT_LIVE_CANDIDATE: LiveCandidateId = "candidate-03"


@dataclass(frozen=True, slots=True, kw_only=True)
class LiveCandidateBinding:
    manifest_relative: Path
    authorization_relative: Path
    run_id: str
    dataset_path: str


_CANDIDATE_BINDINGS: dict[LiveCandidateId, LiveCandidateBinding] = {
    "candidate-03": LiveCandidateBinding(
        manifest_relative=Path(
            "agent-runtime/tests/evaluation/knowledge/live/evidence/"
            "knowledge-p5-live-v1-20260813-candidate-03.manifest.json"
        ),
        authorization_relative=Path(
            "agent-runtime/tests/evaluation/knowledge/live/evidence/"
            "knowledge-p5-live-v1-20260813-candidate-03.authorization.json"
        ),
        run_id="knowledge-p5-live-v1-20260813-candidate-03",
        dataset_path="agent-runtime/tests/evaluation/knowledge/representative_questions.v1.jsonl",
    ),
    "candidate-04": LiveCandidateBinding(
        manifest_relative=Path(
            "agent-runtime/tests/evaluation/knowledge/live/evidence/"
            "knowledge-p5-live-v1-20260813-candidate-04.manifest.json"
        ),
        authorization_relative=Path(
            "agent-runtime/tests/evaluation/knowledge/live/evidence/"
            "knowledge-p5-live-v1-20260813-candidate-04.authorization.json"
        ),
        run_id="knowledge-p5-live-v1-20260813-candidate-04",
        dataset_path="agent-runtime/tests/evaluation/knowledge/representative_questions.v2.jsonl",
    ),
}


class LiveEvaluationBootstrapError(ValueError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class LiveEvaluationBootstrapResult:
    manifest: LiveP5Manifest
    manifest_sha256: str
    authorization: LiveAuthorizationRecord
    snapshot: EvaluationSystemSnapshot
    executors: LiveEvaluationExecutors
    fixture: EvaluationExecutionFixture
    model_transport: BudgetedLiveModelTransport
    diagnostics: LivePhaseCheckpointJournal
    _clients: tuple[httpx.AsyncClient, ...]

    async def aclose(self) -> None:
        for client in reversed(self._clients):
            await client.aclose()


def _candidate_id(raw: str) -> LiveCandidateId:
    if raw not in _CANDIDATE_BINDINGS:
        raise LiveEvaluationBootstrapError("evaluation.live_candidate_invalid")
    return cast(LiveCandidateId, raw)


def manifest_path(repository_root: Path, candidate_id: LiveCandidateId = _DEFAULT_LIVE_CANDIDATE) -> Path:
    return repository_root / _CANDIDATE_BINDINGS[candidate_id].manifest_relative


def authorization_path(repository_root: Path, candidate_id: LiveCandidateId = _DEFAULT_LIVE_CANDIDATE) -> Path:
    return repository_root / _CANDIDATE_BINDINGS[candidate_id].authorization_relative


def _required(environ: Mapping[str, str], key: str) -> str:
    value = environ.get(key)
    if value is None or not value.strip():
        raise LiveEvaluationBootstrapError(f"evaluation.live_environment_missing:{key}")
    return value


def _knowledge_settings(environ: Mapping[str, str]) -> KnowledgeSettings:
    values = {
        "AGENT_KNOWLEDGE_ENABLED": "true",
        "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,tax.law",
        "AGENT_KNOWLEDGE_REWRITE_MAX_CANDIDATES": "3",
        "AGENT_KNOWLEDGE_ALLOW_ORIGINAL_FALLBACK": "true",
        "AGENT_KNOWLEDGE_MAX_RETRIEVAL_QUERY_CHARS": "1024",
        "AGENT_KNOWLEDGE_PER_PATH_CANDIDATES": "20",
        "AGENT_KNOWLEDGE_MIN_PARTIAL_CANDIDATES": "3",
        "AGENT_KNOWLEDGE_REWRITE_TIMEOUT_MS": "8000",
        "AGENT_KNOWLEDGE_RETRIEVAL_TIMEOUT_MS": "20000",
        "AGENT_KNOWLEDGE_EVIDENCE_TIMEOUT_MS": "15000",
    }
    for key in (
        "AGENT_KNOWLEDGE_ES_BASE_URL",
        "AGENT_KNOWLEDGE_EMBEDDING_BASE_URL",
        "AGENT_KNOWLEDGE_RERANK_BASE_URL",
    ):
        values[key] = _required(environ, key)
    return KnowledgeSettings.from_env(values)


def _build_executor(
    *,
    variant: Literal["primary", "rewrite_ablation"],
    settings: KnowledgeSettings,
    gateway: StructuredModelGateway,
    context_accessor: ModelCallContextAccessor,
    model_transport: BudgetedLiveModelTransport,
    search_adapter: EsKnowledgeSearchAdapter,
    embedding_adapter: BgeM3EmbeddingAdapter,
    rerank_adapter: BgeRerankAdapter,
    catalog: KnowledgeEgressPolicyCatalog,
    tasks: object,
    diagnostics: LivePhaseCheckpointJournal,
    component_signature: str,
) -> LiveKnowledgeEvaluationCaseExecutor:
    typed_tasks = cast(Any, tasks)
    if variant == "primary":
        rewrite_definition = cast(ModelTaskDefinition[KnowledgeRewriteInput, KnowledgeRewriteOutput], typed_tasks.rewrite)
        rewriter_delegate: KnowledgeQuestionRewriteStage = KnowledgeQuestionRewriter(
            guard=QuestionEgressGuard(max_question_chars=4096),
            semantic_guard=QuestionSemanticGuard(),
            gateway=gateway,
            context=context_accessor,
            definition=rewrite_definition,
            max_candidates=settings.rewrite_max_candidates,
            max_retrieval_query_chars=settings.max_retrieval_query_chars,
            allow_original_fallback=settings.allow_original_fallback,
        )
    elif variant == "rewrite_ablation":
        rewriter_delegate = IdentityQuestionRewriter()
    else:
        raise ValueError("evaluation.live_variant_invalid")
    rewriter = RecordingQuestionRewriter(rewriter_delegate, diagnostics)
    search = RecordingKnowledgeSearch(search_adapter)
    embedding = RecordingEmbedding(embedding_adapter)
    fusion = RecordingFusion()
    rerank = RecordingRerank(rerank_adapter)
    retrieval = RecordingRetrievalStage(
        DefaultKnowledgeRetrievalStage(
            search=search,
            embedding=embedding,
            rerank=rerank,
            fusion=cast(Any, fusion),
            final_candidates=20,
        ),
        diagnostics,
    )
    summary_definition = cast(ModelTaskDefinition[KnowledgeSummaryInput, KnowledgeSummaryOutput], typed_tasks.summary)
    evidence = RecordingEvidenceStage(
        DefaultKnowledgeEvidenceStage(
            catalog=catalog,
            guard=QuestionEgressGuard(max_question_chars=4096),
            context=context_accessor,
            gateway=gateway,
            definition=summary_definition,
        ),
        diagnostics,
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
    return LiveKnowledgeEvaluationCaseExecutor(
        variant=variant,
        capability=capability,
        rewriter=rewriter,
        search=search,
        embedding=embedding,
        fusion=fusion,
        rerank=rerank,
        retrieval=retrieval,
        evidence=evidence,
        model_transport=model_transport,
        diagnostics=diagnostics,
        component_signature=component_signature,
    )


async def build_live_from_environment(
    *,
    environ: Mapping[str, str],
    repository_root: Path,
    output_dir: Path,
) -> LiveEvaluationBootstrapResult:
    unknown = sorted(key for key in environ if key.startswith("P5_KNOWLEDGE_") and key not in _P5_KEYS)
    if unknown:
        raise LiveEvaluationBootstrapError("evaluation.unknown_environment_key")
    if _required(environ, "P5_KNOWLEDGE_MODE") != "live":
        raise LiveEvaluationBootstrapError("evaluation.live_mode_required")
    if _required(environ, "P5_KNOWLEDGE_LIVE_OPT_IN") != _LIVE_OPT_IN:
        raise LiveEvaluationBootstrapError("evaluation.live_opt_in_required")
    jwt = _required(environ, "P5_KNOWLEDGE_USER_JWT")
    read_authorization_ref = _required(environ, "P5_KNOWLEDGE_AUTH_EVIDENCE_REF")
    if output_dir.exists():
        raise LiveEvaluationBootstrapError("evaluation.output_exists")

    candidate_id = _candidate_id(environ.get("P5_KNOWLEDGE_CANDIDATE", _DEFAULT_LIVE_CANDIDATE))
    manifest, manifest_sha256 = load_manifest(manifest_path(repository_root, candidate_id))
    authorization = load_authorization(authorization_path(repository_root, candidate_id))
    binding = _CANDIDATE_BINDINGS[candidate_id]
    verify_manifest_assets(manifest=manifest, repository_root=repository_root)
    if (
        manifest.run_id != binding.run_id
        or manifest.dataset_path != binding.dataset_path
        or authorization.run_id != manifest.run_id
        or authorization.authorization_reference != manifest.authorization_reference
        or authorization.maximum_paid_requests != manifest.paid_request_budget.maximum_paid_requests
        or authorization.dataset_sha256 != manifest.dataset_sha256
        or read_authorization_ref != manifest.read_authorization_evidence_ref
    ):
        raise LiveEvaluationBootstrapError("evaluation.live_authorization_binding_invalid")
    frozen_head, dirty, worktree_entries = read_repository_state(repository_root)
    if dirty or worktree_entries:
        raise LiveEvaluationBootstrapError("evaluation.live_worktree_dirty")

    model_settings = ModelSettings.from_env(
        {
            "AGENT_MODEL_PROVIDER": "deepseek",
            "AGENT_MODEL_MAX_CONCURRENCY": "1",
            "AGENT_MODEL_ACTION_TIMEOUT_MS": "8000",
            "AGENT_MODEL_ANSWER_TIMEOUT_MS": "15000",
            "LLM_API_KEY": _required(environ, "LLM_API_KEY"),
        }
    )
    if model_settings.provider is not ModelProvider.DEEPSEEK:
        raise LiveEvaluationBootstrapError("evaluation.live_provider_invalid")
    settings = _knowledge_settings(environ)
    tasks = KnowledgeCompositionRoot.task_definitions(enabled=True)
    if tasks is None:
        raise LiveEvaluationBootstrapError("evaluation.live_tasks_missing")

    model_client = build_deepseek_http_client(model_settings)
    es_client = build_knowledge_http_client(_required(environ, "AGENT_KNOWLEDGE_ES_BASE_URL"))
    embedding_client = build_knowledge_http_client(_required(environ, "AGENT_KNOWLEDGE_EMBEDDING_BASE_URL"))
    rerank_client = build_knowledge_http_client(_required(environ, "AGENT_KNOWLEDGE_RERANK_BASE_URL"))
    clients = (model_client, es_client, embedding_client, rerank_client)
    try:
        raw_transport = DeepSeekChatTransport(settings=model_settings, client=model_client)
        budgeted_transport = BudgetedLiveModelTransport(
            delegate=raw_transport,
            output_dir=output_dir,
            manifest=manifest,
            manifest_sha256=manifest_sha256,
            frozen_head=frozen_head,
        )
        diagnostics = LivePhaseCheckpointJournal(output_dir=output_dir, run_id=manifest.run_id)
        action_definition = build_action_selection_task_definition(timeout_ms=model_settings.action_timeout_ms)
        answer_definition = build_answer_generation_task_definition(timeout_ms=model_settings.answer_timeout_ms)
        gateway = BoundedStructuredModelGateway(
            transport=budgeted_transport,
            definitions=(action_definition, answer_definition, *tasks.as_tuple()),
            max_concurrency=1,
        )
        context_accessor = ModelCallContextAccessor()
        catalog = KnowledgeEgressPolicyCatalog.load_v1_resource()
        search_adapter = EsKnowledgeSearchAdapter(HttpxKnowledgeTransport(es_client))
        embedding_adapter = BgeM3EmbeddingAdapter(HttpxKnowledgeTransport(embedding_client))
        rerank_adapter = BgeRerankAdapter(HttpxKnowledgeTransport(rerank_client))
        signature = f"knowledge-live-p5-v1|{manifest_sha256}|summary-v2|retrieval-v1|catalog-{catalog.snapshot.source_sha256}"
        primary = _build_executor(
            variant="primary",
            settings=settings,
            gateway=gateway,
            context_accessor=context_accessor,
            model_transport=budgeted_transport,
            search_adapter=search_adapter,
            embedding_adapter=embedding_adapter,
            rerank_adapter=rerank_adapter,
            catalog=catalog,
            tasks=tasks,
            diagnostics=diagnostics,
            component_signature=signature,
        )
        ablation = _build_executor(
            variant="rewrite_ablation",
            settings=settings,
            gateway=gateway,
            context_accessor=context_accessor,
            model_transport=budgeted_transport,
            search_adapter=search_adapter,
            embedding_adapter=embedding_adapter,
            rerank_adapter=rerank_adapter,
            catalog=catalog,
            tasks=tasks,
            diagnostics=diagnostics,
            component_signature=signature,
        )
    except Exception:
        for client in reversed(clients):
            await client.aclose()
        raise

    def make_scope(case_id: str, variant: str, question: str) -> RequestExecutionScope:
        import asyncio

        loop = asyncio.get_running_loop()
        return RequestExecutionScope(
            context=CapabilityExecutionContext(
                request_id=f"p5-{case_id}-{variant}",
                correlation_id=f"p5-corr-{case_id}-{variant}",
                original_question=question,
                subject_id="admin",
                subject_type=SubjectType.USER,
                user_token=OpaqueUserToken.from_raw(jwt),
                deadline_monotonic=loop.time() + 55.0,
                cancellation=ManualCancellationSignal(),
            )
        )

    gates = tuple(
        GateEvidenceRecord(gateId=item.gate_id, evidenceRef=item.evidence_ref)
        for item in manifest.gate_evidence
    )
    snapshot = EvaluationSystemSnapshot(
        repository_root=str(repository_root),
        worktree_entries=(),
        git_commit=frozen_head,
        worktree_dirty=False,
        provider_mode="live",
        principal_profile_id=manifest.principal_profile_id,
        read_authorization_evidence_ref=manifest.read_authorization_evidence_ref,
        gate_evidence=cast(Any, gates),
        question_policy_version="question-egress-v1",
        domain_catalog_version=CATALOG_VERSION,
        flow_config_version=settings.config_version,
        retrieval_profile_version="tax-knowledge-search-v1",
        index_snapshot_ids=manifest.index_snapshot_ids,
        embedding_model="BGE-M3",
        rerank_model="BAAI/bge-reranker-v2-m3",
        model_task_versions={
            "action_selection": action_definition.task_version,
            "answer_generation": answer_definition.task_version,
            "knowledge_rewrite": cast(Any, tasks.rewrite).task_version,
            "knowledge_summary": cast(Any, tasks.summary).task_version,
        },
        deep_seek_model=ModelSettings.MODEL_NAME,
        policy_catalog_version=catalog.snapshot.catalog_version,
        policy_catalog_sha256=catalog.snapshot.source_sha256,
        policy_authority_id=catalog.snapshot.authority_id,
        policy_export_id=catalog.snapshot.export_id,
        policy_source_revision=catalog.snapshot.source_revision,
        evidence_rules_version="knowledge-evidence-v1",
    )
    executors = LiveEvaluationExecutors(primary=primary, rewrite_ablation=ablation)
    executors.validate_pair()
    return LiveEvaluationBootstrapResult(
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        authorization=authorization,
        snapshot=snapshot,
        executors=executors,
        fixture=EvaluationExecutionFixture(make_scope=make_scope, synthetic_only=False),
        model_transport=budgeted_transport,
        diagnostics=diagnostics,
        _clients=clients,
    )
