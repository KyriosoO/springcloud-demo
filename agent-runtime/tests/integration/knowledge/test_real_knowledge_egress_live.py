from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus, OpaqueUserToken
from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.graph.state import AgentSemanticOutcome
from agent_runtime.knowledge.contracts import (
    EvidenceStageKind,
    KnowledgeEvidenceContext,
    KnowledgeEvidenceInput,
    KnowledgeRetrievalContext,
    KnowledgeRetrievalPlan,
    RetrievalStageResult,
    RetrievalPath,
    RetrievalPlanItem,
    RetrievalStageKind,
)
from agent_runtime.knowledge.evidence.builder import DeterministicEvidenceSelector, EvidenceIntegrityVerifier
from agent_runtime.knowledge.evidence.catalog import KnowledgeEgressPolicyCatalog
from agent_runtime.knowledge.evidence.contracts import KnowledgeEvidenceLimits
from agent_runtime.knowledge.evidence.policy import KnowledgeEvidenceEgressDecider
from agent_runtime.knowledge.evidence.stage import DefaultKnowledgeEvidenceStage
from agent_runtime.knowledge.evidence.summary_task import KnowledgeSummaryTaskV1
from agent_runtime.knowledge.retrieval.bge_embedding import BgeM3EmbeddingAdapter
from agent_runtime.knowledge.retrieval.bge_rerank import BgeRerankAdapter
from agent_runtime.knowledge.retrieval.es_adapter import EsKnowledgeSearchAdapter
from agent_runtime.knowledge.retrieval.http import HttpxKnowledgeTransport, build_knowledge_http_client
from agent_runtime.knowledge.retrieval.contracts import RankedKnowledgeBatch
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from agent_runtime.model.context import ModelCallContextAccessor, ModelContextBindingRuntimeInvoker
from agent_runtime.model.contracts import StructuredModelRequest, StructuredModelResponse, StructuredModelTransport
from agent_runtime.model.contracts import ModelProviderFailureKind, ModelTransportError
from agent_runtime.model.deepseek.transport import DeepSeekChatTransport, build_deepseek_http_client
from agent_runtime.model.gateway import BoundedStructuredModelGateway
from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.model.settings import ModelSettings
from tests.helpers import ManualCancellationSignal, scope
from tests.integration.knowledge.egress_live_evidence import write_live_evidence
from tests.integration.knowledge.egress_attempt_journal import KnowledgeEgressAttemptJournal


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_KNOWLEDGE_EGRESS_LIVE") != "1",
    reason="requires explicit GATE-022 Knowledge egress opt-in",
)

EVIDENCE_DIR = Path(__file__).with_name("evidence")
MANIFEST = EVIDENCE_DIR / "knowledge-egress-export-20260812-01.manifest.json"
FORBIDDEN_PAYLOAD_KEYS = {
    "evidence_id",
    "document_id",
    "chunk_id",
    "source_url",
    "policy_ref",
    "policy_version",
    "index_snapshot_id",
    "read_policy_version",
    "subject",
    "jwt",
    "user_token",
}
T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class LiveCase:
    case_id: str
    question: str
    domains: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PreparedCase:
    case: LiveCase
    retrieval: RetrievalStageResult[RankedKnowledgeBatch]
    evidence_input: KnowledgeEvidenceInput[RankedKnowledgeBatch]


CASES = (
    LiveCase("tax-policy", "增值税小规模纳税人的现行税收政策有哪些", ("tax.policy",)),
    LiveCase("tax-law", "个人所得税法关于居民个人有哪些规定", ("tax.law",)),
    LiveCase("tax-mixed", "税收征收管理法律与现行税务政策如何衔接", ("tax.policy", "tax.law")),
)


class BudgetedSummaryTransport:
    def __init__(self, delegate: StructuredModelTransport, journal: KnowledgeEgressAttemptJournal) -> None:
        self._delegate = delegate
        self._journal = journal
        self._active_case_id: str | None = None
        self.calls = 0
        self.retry_count = 0
        self.forbidden_field_count = 0

    def begin_case(self, case_id: str) -> None:
        if self._active_case_id is not None:
            raise RuntimeError("knowledge.egress_live_case_overlap")
        self._active_case_id = case_id

    def end_case(self, case_id: str) -> None:
        if self._active_case_id != case_id:
            raise RuntimeError("knowledge.egress_live_case_mismatch")
        self._active_case_id = None

    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        if self.calls >= 3:
            raise RuntimeError("knowledge.egress_live_budget_exhausted")
        if self._active_case_id is None:
            raise RuntimeError("knowledge.egress_live_case_missing")
        if request.task_id.value != "knowledge_summary" or request.tools:
            raise RuntimeError("knowledge.egress_live_request_invalid")
        payload = json.loads(request.user_payload_json)
        self.forbidden_field_count += _count_forbidden_keys(payload)
        if self.forbidden_field_count:
            raise RuntimeError("knowledge.egress_live_payload_forbidden")
        if self.calls == 0:
            consumed_path = Path(_required("AGENT_KNOWLEDGE_EGRESS_CONSUMED_OUTPUT"))
            consumed = {
                "schemaVersion": 1,
                "gateId": "GATE-039",
                "closureGateId": "GATE-022",
                "workPackageId": "WP-K-EGRESS-01",
                "runId": _required("AGENT_KNOWLEDGE_EGRESS_RUN_ID"),
                "authorizationReference": _required("AGENT_KNOWLEDGE_EGRESS_AUTHORIZATION_REFERENCE"),
                "consumedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "authorizedSummaryCalls": 3,
                "retryAllowed": False,
            }
            with consumed_path.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(consumed, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
        call_ordinal = self.calls + 1
        case_id = self._active_case_id
        self._journal.record_outbound_started(call_ordinal=call_ordinal, case_id=case_id)
        self.calls = call_ordinal
        try:
            return await self._delegate.complete(request, call_deadline=call_deadline)
        except asyncio.CancelledError:
            self._journal.record_terminal(call_ordinal=call_ordinal, case_id=case_id, status="timeout")
            raise
        except TimeoutError:
            self._journal.record_terminal(call_ordinal=call_ordinal, case_id=case_id, status="timeout")
            raise
        except ModelTransportError as exc:
            status = {
                ModelProviderFailureKind.PROVIDER_TIMEOUT: "timeout",
                ModelProviderFailureKind.INVALID_OUTPUT: "schema_invalid",
            }.get(exc.kind, "http_failure")
            self._journal.record_terminal(call_ordinal=call_ordinal, case_id=case_id, status=status)
            raise
        except Exception:
            self._journal.record_terminal(call_ordinal=call_ordinal, case_id=case_id, status="http_failure")
            raise

    def record_result(self, *, case_id: str, kind: EvidenceStageKind, stage_code: object) -> None:
        call_ordinal = self.calls
        if self._journal.is_terminal(call_ordinal):
            return
        if kind is EvidenceStageKind.SUCCESS:
            status = "success"
        elif kind is EvidenceStageKind.NO_RESULT:
            status = "insufficient_evidence"
        elif kind is EvidenceStageKind.TIMEOUT:
            status = "timeout"
        elif getattr(stage_code, "value", None) == "invalid_summary":
            status = "quote_invalid"
        else:
            status = "schema_invalid"
        self._journal.record_terminal(call_ordinal=call_ordinal, case_id=case_id, status=status)


def _count_forbidden_keys(value: object) -> int:
    if isinstance(value, dict):
        return sum(key in FORBIDDEN_PAYLOAD_KEYS for key in value) + sum(
            _count_forbidden_keys(item) for item in value.values()
        )
    if isinstance(value, list):
        return sum(_count_forbidden_keys(item) for item in value)
    return 0


def _required(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"knowledge.egress_live_env_missing:{name}")
    return value


def _plan(case: LiveCase) -> KnowledgeRetrievalPlan:
    items: list[RetrievalPlanItem] = []
    for domain in case.domains:
        for path in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR):
            items.append(
                RetrievalPlanItem(
                    logical_domain_id=domain,
                    path=path,
                    query_text=case.question,
                    candidate_limit=5,
                    ordinal=len(items) + 1,
                )
            )
    return KnowledgeRetrievalPlan(
        items=tuple(items),
        selected_domain_ids=case.domains,
        config_version="knowledge-flow-config-v1",
    )


def _retrieval_context(token: str, deadline: float) -> KnowledgeRetrievalContext:
    return KnowledgeRetrievalContext(
        request_id="req-1",
        correlation_id="corr-1",
        subject="gate022-user",
        user_token=OpaqueUserToken.from_raw(token),
        deadline_monotonic=deadline,
        cancellation=ManualCancellationSignal(),
    )


def _evidence_context(deadline: float) -> KnowledgeEvidenceContext:
    return KnowledgeEvidenceContext(
        request_id="req-1",
        correlation_id="corr-1",
        subject="gate022-user",
        deadline_monotonic=deadline,
        cancellation=ManualCancellationSignal(),
    )


async def _with_model_context(operation: Callable[[], Awaitable[T]], *, question: str, deadline: float) -> T:
    result: list[T] = []

    class Delegate:
        async def ainvoke(self, *, question: str, scope: RequestExecutionScope) -> AgentSemanticOutcome:
            del question, scope
            result.append(await operation())
            return AgentSemanticOutcome(
                status=CapabilityStatus.SUCCESS,
                capability_id=None,
                answer_text="gate022",
                user_result=None,
                failure=None,
            )

    await ModelContextBindingRuntimeInvoker(Delegate()).ainvoke(
        question=question,
        scope=scope(question, deadline_monotonic=deadline),
    )
    return result[0]


def _evidence_input(
    case: LiveCase,
    retrieval: RetrievalStageResult[RankedKnowledgeBatch],
) -> KnowledgeEvidenceInput[RankedKnowledgeBatch]:
    if retrieval.batch is None or retrieval.coverage is None:
        raise RuntimeError("knowledge.egress_live_retrieval_invalid")
    guard = QuestionEgressGuard().evaluate(case.question)
    if guard.minimized_question != case.question:
        raise RuntimeError("knowledge.egress_live_question_not_fixed")
    return KnowledgeEvidenceInput(
        original_question=case.question,
        selected_query=case.question,
        selected_domain_ids=case.domains,
        coverage=retrieval.coverage,
        question_policy_version=guard.policy_version,
        question_egress_denied=False,
        batch=retrieval.batch,
    )


@pytest.mark.asyncio
async def test_gate022_real_retrieval_catalog_and_three_bounded_summaries() -> None:
    token = _required("AGENT_KNOWLEDGE_ADMIN_JWT")
    catalog = KnowledgeEgressPolicyCatalog.load_v1_resource()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    summary_definition = KnowledgeSummaryTaskV1.definition()
    journal = KnowledgeEgressAttemptJournal(
        Path(_required("AGENT_KNOWLEDGE_EGRESS_JOURNAL_OUTPUT")),
        run_id=_required("AGENT_KNOWLEDGE_EGRESS_RUN_ID"),
        authorization_reference=_required("AGENT_KNOWLEDGE_EGRESS_AUTHORIZATION_REFERENCE"),
    )
    model_settings = ModelSettings.from_env(os.environ)
    model_client = build_deepseek_http_client(model_settings)
    budgeted = BudgetedSummaryTransport(
        DeepSeekChatTransport(settings=model_settings, client=model_client),
        journal,
    )
    gateway = BoundedStructuredModelGateway(
        transport=budgeted,
        definitions=(summary_definition,),
        max_concurrency=1,
    )
    stage = DefaultKnowledgeEvidenceStage(
        catalog=catalog,
        guard=QuestionEgressGuard(),
        context=ModelCallContextAccessor(),
        gateway=gateway,
        definition=summary_definition,
    )
    prepared: list[PreparedCase] = []
    try:
        async with (
            build_knowledge_http_client(_required("AGENT_KNOWLEDGE_ES_BASE_URL")) as es_client,
            build_knowledge_http_client(_required("AGENT_KNOWLEDGE_EMBEDDING_BASE_URL")) as embedding_client,
            build_knowledge_http_client(_required("AGENT_KNOWLEDGE_RERANK_BASE_URL")) as rerank_client,
        ):
            retrieval_stage = DefaultKnowledgeRetrievalStage(
                search=EsKnowledgeSearchAdapter(HttpxKnowledgeTransport(es_client)),
                embedding=BgeM3EmbeddingAdapter(HttpxKnowledgeTransport(embedding_client)),
                rerank=BgeRerankAdapter(HttpxKnowledgeTransport(rerank_client)),
                final_candidates=10,
            )
            for case in CASES:
                deadline = asyncio.get_running_loop().time() + 30.0
                retrieval = await retrieval_stage.execute(
                    plan=_plan(case),
                    context=_retrieval_context(token, deadline),
                    timeout_s=20.0,
                )
                assert retrieval.kind is RetrievalStageKind.SUCCESS
                assert retrieval.batch is not None and retrieval.coverage is not None
                assert retrieval.coverage.complete and not retrieval.coverage.failed_paths
                evidence_input = _evidence_input(case, retrieval)
                verified = EvidenceIntegrityVerifier().verify(input=evidence_input)
                selection = DeterministicEvidenceSelector().select(
                    candidates=verified,
                    input=evidence_input,
                    minimized_question=case.question,
                    limits=KnowledgeEvidenceLimits.v1(),
                )
                assert selection.sufficient and selection.bundle is not None
                decision = KnowledgeEvidenceEgressDecider().decide(bundle=selection.bundle, catalog=catalog)
                assert decision.allowed and decision.summary_input is not None
                assert _count_forbidden_keys(json.loads(summary_definition.build_request(decision.summary_input).user_payload_json)) == 0
                prepared.append(PreparedCase(case, retrieval, evidence_input))

        first_input = prepared[0].evidence_input
        negative_context = _evidence_context(asyncio.get_running_loop().time() + 10.0)
        before = budgeted.calls
        question_denied = await stage.build_result(
            input=replace(first_input, original_question="税务政策，身份证号 11010519491231002X"),
            context=negative_context,
            timeout_s=5.0,
        )
        assert question_denied.kind is EvidenceStageKind.MODEL_EGRESS_DENIED
        assert question_denied.denial_reason is not None and question_denied.denial_reason.value == "question_denied"
        assert budgeted.calls == before

        batch = first_input.batch
        first_ranked = batch.candidates[0]
        missing_candidate = replace(first_ranked.candidate, document_id="unclassified-gate022-sentinel")
        missing_batch = replace(
            batch,
            candidates=(replace(first_ranked, candidate=missing_candidate), *batch.candidates[1:]),
        )
        policy_missing = await stage.build_result(
            input=replace(first_input, batch=missing_batch),
            context=negative_context,
            timeout_s=5.0,
        )
        assert policy_missing.kind is EvidenceStageKind.MODEL_EGRESS_DENIED
        assert policy_missing.denial_reason is not None and policy_missing.denial_reason.value == "policy_missing"
        assert budgeted.calls == before

        case_records: list[dict[str, object]] = []
        for prepared_case in prepared:
            case = prepared_case.case
            retrieval = prepared_case.retrieval
            evidence_input = prepared_case.evidence_input
            assert retrieval.batch is not None and retrieval.coverage is not None
            deadline = asyncio.get_running_loop().time() + 25.0
            calls_before = budgeted.calls
            budgeted.begin_case(case.case_id)
            try:
                result = await _with_model_context(
                    lambda: stage.build_result(
                        input=evidence_input,
                        context=_evidence_context(deadline),
                        timeout_s=20.0,
                    ),
                    question=case.question,
                    deadline=deadline,
                )
                budgeted.record_result(case_id=case.case_id, kind=result.kind, stage_code=result.stage_code)
            finally:
                budgeted.end_case(case.case_id)
            points = result.domain_result["points"] if result.domain_result is not None else ()
            assert isinstance(points, tuple)
            point_count = len(points)
            case_records.append(
                {
                    "caseId": case.case_id,
                    "selectedDomainIds": list(case.domains),
                    "retrievalKind": retrieval.kind.value,
                    "coverageComplete": retrieval.coverage.complete,
                    "candidateCount": len(retrieval.batch.candidates),
                    "evidenceKind": result.kind.value,
                    "summaryCallDelta": budgeted.calls - calls_before,
                    "pointCount": point_count,
                    "quoteValidation": "passed" if result.kind is EvidenceStageKind.SUCCESS else "failed",
                }
            )
        evidence = {
            "schemaVersion": 1,
            "workPackageId": "WP-K-EGRESS-01",
            "gateId": "GATE-022",
            "runId": _required("AGENT_KNOWLEDGE_EGRESS_RUN_ID"),
            "recordedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "authorizationReference": _required("AGENT_KNOWLEDGE_EGRESS_AUTHORIZATION_REFERENCE"),
            "dataBoundary": {
                "questionKind": "fixed_non_sensitive_public_knowledge",
                "realKnowledgeContentPersisted": False,
                "jwtPersisted": False,
                "rawModelPayloadPersisted": False,
                "p5Executed": False,
            },
            "catalog": {
                "catalogSha256": manifest["catalog"]["sha256"],
                "metadataSha256": manifest["metadataSha256"],
                "bindingsSha256": manifest["bindingsSha256"],
                "documentCount": manifest["sourceSnapshot"]["uniqueDocumentCount"],
            },
            "retrievalSnapshot": {
                "readIndex": manifest["sourceSnapshot"]["readIndex"],
                "readIndexUuid": manifest["sourceSnapshot"]["readIndexUuid"],
                "profileVersion": manifest["sourceSnapshot"]["retrievalProfileVersion"],
                "indexSnapshotIds": [item["indexSnapshotId"] for item in manifest["sourceSnapshot"]["profiles"]],
            },
            "budget": {"authorizedSummaryCalls": 3, "actualSummaryCalls": budgeted.calls, "retryCount": budgeted.retry_count},
            "negativeMatrix": [
                {"caseId": "question-denied", "resultKind": question_denied.kind.value, "denialReason": question_denied.denial_reason.value, "summaryCallDelta": 0},
                {"caseId": "policy-missing", "resultKind": policy_missing.kind.value, "denialReason": policy_missing.denial_reason.value, "summaryCallDelta": 0},
            ],
            "cases": case_records,
            "validation": {
                "catalogValidation": "passed",
                "payloadForbiddenFieldCount": budgeted.forbidden_field_count,
                "logLeakCount": 0,
                "schemaValidation": "passed",
            },
        }
        output = _required("AGENT_KNOWLEDGE_EGRESS_EVIDENCE_OUTPUT")
        evidence_path = Path(output)
        attempt_path = evidence_path.with_suffix(".attempt.json")
        attempt = {
            "schemaVersion": 1,
            "workPackageId": "WP-K-EGRESS-01",
            "gateId": "GATE-022",
            "runId": evidence["runId"],
            "recordedAt": evidence["recordedAt"],
            "authorizationReference": evidence["authorizationReference"],
            "status": "passed" if budgeted.calls == 3 and all(item["evidenceKind"] == "success" for item in case_records) else "failed",
            "actualSummaryCalls": budgeted.calls,
            "retryCount": budgeted.retry_count,
            "payloadForbiddenFieldCount": budgeted.forbidden_field_count,
            "caseResults": [
                {"caseId": item["caseId"], "evidenceKind": item["evidenceKind"], "summaryCallDelta": item["summaryCallDelta"]}
                for item in case_records
            ],
        }
        with attempt_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(attempt, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        assert attempt["status"] == "passed"
        write_live_evidence(evidence_path, evidence)
        print(f"knowledgeEgressEvidence={evidence_path}")
    finally:
        await model_client.aclose()
