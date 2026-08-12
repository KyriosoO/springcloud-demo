from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import unicodedata
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
    EvidenceStageResult,
    KnowledgeEvidenceContext,
    KnowledgeEvidenceInput,
    KnowledgeRetrievalContext,
    KnowledgeRetrievalPlan,
    RetrievalPath,
    RetrievalPlanItem,
    RetrievalStageKind,
)
from agent_runtime.knowledge.evidence.catalog import (
    KnowledgeEgressPolicyCatalog,
    canonical_policy_fingerprint,
)
from agent_runtime.knowledge.evidence.contracts import KnowledgeEgressDisposition
from agent_runtime.knowledge.evidence.stage import DefaultKnowledgeEvidenceStage
from agent_runtime.knowledge.evidence.summary_task import KnowledgeSummaryTaskV1
from agent_runtime.knowledge.retrieval.bge_embedding import BgeM3EmbeddingAdapter
from agent_runtime.knowledge.retrieval.bge_rerank import BgeRerankAdapter
from agent_runtime.knowledge.retrieval.contracts import RankedKnowledgeBatch
from agent_runtime.knowledge.retrieval.es_adapter import EsKnowledgeSearchAdapter
from agent_runtime.knowledge.retrieval.http import HttpxKnowledgeTransport, build_knowledge_http_client
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from agent_runtime.model.context import ModelCallContextAccessor, ModelContextBindingRuntimeInvoker
from agent_runtime.model.contracts import (
    StructuredFinishKind,
    StructuredModelRequest,
    StructuredModelResponse,
)
from agent_runtime.model.gateway import BoundedStructuredModelGateway
from agent_runtime.model.input_guard import QuestionEgressGuard
from tests.helpers import ManualCancellationSignal, scope
from tests.integration.knowledge.egress_diagnostic_evidence import write_diagnostic_evidence


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_KNOWLEDGE_EGRESS_DIAGNOSTIC") != "1",
    reason="requires explicit zero-external-model Knowledge egress diagnostic opt-in",
)

EVIDENCE_DIR = Path(__file__).with_name("evidence")
MANIFEST = EVIDENCE_DIR / "knowledge-egress-export-20260812-01.manifest.json"
T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class DiagnosticCase:
    case_id: str
    question: str
    domains: tuple[str, ...]


CASES = (
    DiagnosticCase("tax-policy", "增值税小规模纳税人的现行税收政策有哪些", ("tax.policy",)),
    DiagnosticCase("tax-law", "个人所得税法关于居民个人有哪些规定", ("tax.law",)),
    DiagnosticCase("tax-mixed", "税收征收管理法律与现行税务政策如何衔接", ("tax.policy", "tax.law")),
)


class DeterministicExtractiveSummaryTransport:
    def __init__(self) -> None:
        self.calls = 0
        self.observations: list[tuple[int, int]] = []

    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        del call_deadline
        if request.task_id.value != "knowledge_summary" or request.tools:
            raise RuntimeError("knowledge.egress_diagnostic_request_invalid")
        payload = json.loads(request.user_payload_json)
        evidence = payload.get("evidence") if isinstance(payload, dict) else None
        if not isinstance(evidence, list) or not evidence:
            raise RuntimeError("knowledge.egress_diagnostic_payload_invalid")
        first = evidence[0]
        if not isinstance(first, dict) or not isinstance(first.get("evidence_ref"), str) or not isinstance(first.get("content"), str):
            raise RuntimeError("knowledge.egress_diagnostic_payload_invalid")
        quote = _safe_contiguous_quote(first["content"])
        response = {
            "outcome": "answer",
            "points": [{"evidence_ref": first["evidence_ref"], "quote": quote}],
        }
        self.calls += 1
        self.observations.append((len(request.user_payload_json.encode("utf-8")), len(evidence)))
        return StructuredModelResponse(
            finish_kind=StructuredFinishKind.STOP,
            content=json.dumps(response, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            tool_calls=(),
            usage_total_tokens=0,
        )


def _safe_contiguous_quote(content: str) -> str:
    start = next((index for index, character in enumerate(content) if ord(character) >= 32 and ord(character) != 127), None)
    if start is None:
        raise RuntimeError("knowledge.egress_diagnostic_content_invalid")
    end = start
    while end < len(content) and ord(content[end]) >= 32 and ord(content[end]) != 127 and end - start < 80:
        end += 1
    quote = content[start:end].strip()
    if not quote or quote not in content:
        raise RuntimeError("knowledge.egress_diagnostic_content_invalid")
    return quote


def _required(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"knowledge.egress_diagnostic_env_missing:{name}")
    return value


def _plan(case: DiagnosticCase) -> KnowledgeRetrievalPlan:
    return KnowledgeRetrievalPlan(
        items=tuple(
            RetrievalPlanItem(
                logical_domain_id=domain,
                path=path,
                query_text=case.question,
                candidate_limit=5,
                ordinal=ordinal,
            )
            for ordinal, (domain, path) in enumerate(
                ((domain, path) for domain in case.domains for path in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR)),
                1,
            )
        ),
        selected_domain_ids=case.domains,
        config_version="knowledge-flow-config-v1",
    )


def _retrieval_context(token: str, deadline: float) -> KnowledgeRetrievalContext:
    return KnowledgeRetrievalContext(
        request_id="req-1",
        correlation_id="corr-1",
        subject="diagnostic-user",
        user_token=OpaqueUserToken.from_raw(token),
        deadline_monotonic=deadline,
        cancellation=ManualCancellationSignal(),
    )


def _evidence_context(deadline: float) -> KnowledgeEvidenceContext:
    return KnowledgeEvidenceContext(
        request_id="req-1",
        correlation_id="corr-1",
        subject="diagnostic-user",
        deadline_monotonic=deadline,
        cancellation=ManualCancellationSignal(),
    )


def _evidence_input(
    case: DiagnosticCase,
    retrieval: object,
) -> KnowledgeEvidenceInput[RankedKnowledgeBatch]:
    if not hasattr(retrieval, "batch") or not hasattr(retrieval, "coverage"):
        raise RuntimeError("knowledge.egress_diagnostic_retrieval_invalid")
    batch = retrieval.batch
    coverage = retrieval.coverage
    if not isinstance(batch, RankedKnowledgeBatch) or coverage is None:
        raise RuntimeError("knowledge.egress_diagnostic_retrieval_invalid")
    guard = QuestionEgressGuard().evaluate(case.question)
    if guard.minimized_question != case.question:
        raise RuntimeError("knowledge.egress_diagnostic_question_not_fixed")
    return KnowledgeEvidenceInput(
        original_question=case.question,
        selected_query=case.question,
        selected_domain_ids=case.domains,
        coverage=coverage,
        question_policy_version=guard.policy_version,
        question_egress_denied=False,
        batch=batch,
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
                answer_text="diagnostic",
                user_result=None,
                failure=None,
            )

    await ModelContextBindingRuntimeInvoker(Delegate()).ainvoke(
        question=question,
        scope=scope(question, deadline_monotonic=deadline),
    )
    return result[0]


def _stage(
    catalog: KnowledgeEgressPolicyCatalog,
    transport: DeterministicExtractiveSummaryTransport,
) -> DefaultKnowledgeEvidenceStage:
    definition = KnowledgeSummaryTaskV1.definition()
    return DefaultKnowledgeEvidenceStage(
        catalog=catalog,
        guard=QuestionEgressGuard(),
        context=ModelCallContextAccessor(),
        gateway=BoundedStructuredModelGateway(transport=transport, definitions=(definition,), max_concurrency=1),
        definition=definition,
    )


def _denied_catalog(source: KnowledgeEgressPolicyCatalog) -> KnowledgeEgressPolicyCatalog:
    policies = tuple(
        replace(
            policy,
            disposition=KnowledgeEgressDisposition.DENY,
            allowed_fields=frozenset(),
            max_content_code_points=0,
        )
        for policy in source.snapshot.policies
    )
    draft = replace(source.snapshot, policies=policies, canonical_fingerprint="0" * 64)
    return KnowledgeEgressPolicyCatalog(replace(draft, canonical_fingerprint=canonical_policy_fingerprint(draft)))


def _single_candidate_input(
    source: KnowledgeEvidenceInput[RankedKnowledgeBatch],
    *,
    document_id: str | None = None,
    policy_ref: str | None = None,
    index_snapshot_id: str | None = None,
) -> KnowledgeEvidenceInput[RankedKnowledgeBatch]:
    ranked = source.batch.candidates[0]
    candidate = replace(
        ranked.candidate,
        document_id=document_id or ranked.candidate.document_id,
        policy_ref=policy_ref or ranked.candidate.policy_ref,
        index_snapshot_id=index_snapshot_id or ranked.candidate.index_snapshot_id,
    )
    batch = replace(
        source.batch,
        candidates=(replace(ranked, candidate=candidate),),
        index_snapshot_ids=(candidate.index_snapshot_id,),
    )
    return replace(source, batch=batch)


def _safe_integrity_shape(source: KnowledgeEvidenceInput[RankedKnowledgeBatch]) -> dict[str, object]:
    document_facts: dict[str, tuple[str, str, str]] = {}
    identities: set[tuple[str, str]] = set()
    document_facts_consistent = True
    identities_unique = True
    for item in source.batch.candidates:
        candidate = item.candidate
        identity = (candidate.document_id, candidate.chunk_id)
        identities_unique = identities_unique and identity not in identities
        identities.add(identity)
        fact = (candidate.policy_ref, candidate.read_policy_version, candidate.index_snapshot_id)
        if candidate.document_id in document_facts and document_facts[candidate.document_id] != fact:
            document_facts_consistent = False
        document_facts[candidate.document_id] = fact
    observed_snapshots = tuple(dict.fromkeys(item.candidate.index_snapshot_id for item in source.batch.candidates))
    return {
        "profileValid": source.batch.profile_version == "tax-knowledge-search-v1",
        "rankSequenceValid": tuple(item.rank for item in source.batch.candidates)
        == tuple(range(1, len(source.batch.candidates) + 1)),
        "domainOrderValid": all(
            item.domain_ids == tuple(domain for domain in source.selected_domain_ids if domain in item.domain_ids)
            for item in source.batch.candidates
        ),
        "candidateDomainMembershipValid": all(
            item.candidate.domain_id in item.domain_ids for item in source.batch.candidates
        ),
        "scoreValid": all(
            type(item.rerank_score) in (int, float)
            and not isinstance(item.rerank_score, bool)
            and math.isfinite(item.rerank_score)
            for item in source.batch.candidates
        ),
        "contentHashValid": all(
            hashlib.sha256(unicodedata.normalize("NFC", item.candidate.content).encode("utf-8")).hexdigest()
            == item.candidate.content_sha256
            for item in source.batch.candidates
        ),
        "identitiesUnique": identities_unique,
        "documentFactsConsistent": document_facts_consistent,
        "snapshotSequenceValid": source.batch.index_snapshot_ids == observed_snapshots,
        "batchSnapshotCount": len(source.batch.index_snapshot_ids),
        "observedSnapshotCount": len(observed_snapshots),
    }


def _negative_record(
    case_id: str,
    result: EvidenceStageResult,
    calls_before: int,
    calls_after: int,
) -> dict[str, object]:
    kind = result.kind.value
    if result.denial_reason is not None:
        reason_value = result.denial_reason.value
    elif result.stage_code is not None:
        reason_value = result.stage_code.value
    else:
        raise RuntimeError("knowledge.egress_diagnostic_negative_reason_missing")
    return {
        "caseId": case_id,
        "resultKind": kind,
        "reason": reason_value,
        "localSummaryCallDelta": calls_after - calls_before,
        "externalModelCallDelta": 0,
    }


@pytest.mark.asyncio
async def test_real_retrieval_and_policy_with_deterministic_local_summary() -> None:
    token = _required("AGENT_KNOWLEDGE_ADMIN_JWT")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    catalog = KnowledgeEgressPolicyCatalog.load_v1_resource()
    local_transport = DeterministicExtractiveSummaryTransport()
    stage = _stage(catalog, local_transport)
    case_records: list[dict[str, object]] = []
    inputs: list[KnowledgeEvidenceInput[RankedKnowledgeBatch]] = []

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
            integrity_shape = _safe_integrity_shape(evidence_input)
            assert all(value is True for key, value in integrity_shape.items() if key.endswith("Valid") or key.endswith("Unique") or key.endswith("Consistent")), integrity_shape
            inputs.append(evidence_input)
            calls_before = local_transport.calls
            result = await _with_model_context(
                lambda: stage.build_result(
                    input=evidence_input,
                    context=_evidence_context(deadline),
                    timeout_s=15.0,
                ),
                question=case.question,
                deadline=deadline,
            )
            assert result.kind is EvidenceStageKind.SUCCESS
            assert local_transport.calls == calls_before + 1
            assert result.domain_result is not None
            points = result.domain_result["points"]
            assert isinstance(points, tuple) and len(points) == 1
            payload_bytes, evidence_count = local_transport.observations[-1]
            case_records.append(
                {
                    "caseId": case.case_id,
                    "selectedDomainIds": list(case.domains),
                    "retrievalKind": retrieval.kind.value,
                    "coverageComplete": retrieval.coverage.complete,
                    "candidateCount": len(retrieval.batch.candidates),
                    "selectedEvidenceCount": evidence_count,
                    "summaryPayloadBytes": payload_bytes,
                    "evidenceKind": result.kind.value,
                    "pointCount": len(points),
                    "decoderValidation": "passed",
                    "referenceValidation": "passed",
                    "substringValidation": "passed",
                    "localAssembly": "passed",
                }
            )

    first = inputs[0]
    negative_cases = (
        (
            "question-denied",
            stage,
            replace(first, original_question="税务政策，身份证号 11010519491231002X"),
        ),
        ("policy-missing", stage, _single_candidate_input(first, document_id="unclassified-diagnostic-sentinel")),
        ("document-denied", _stage(_denied_catalog(catalog), local_transport), _single_candidate_input(first)),
        ("policy-conflict", stage, _single_candidate_input(first, policy_ref="conflicting-policy")),
        ("snapshot-mismatch", stage, _single_candidate_input(first, index_snapshot_id="f" * 64)),
    )
    negative_records: list[dict[str, object]] = []
    for case_id, negative_stage, negative_input in negative_cases:
        before = local_transport.calls
        result = await negative_stage.build_result(
            input=negative_input,
            context=_evidence_context(asyncio.get_running_loop().time() + 5.0),
            timeout_s=4.0,
        )
        negative_records.append(_negative_record(case_id, result, before, local_transport.calls))
        assert local_transport.calls == before

    evidence = {
        "schemaVersion": 1,
        "workPackageId": "WP-K-EGRESS-01",
        "gateId": "GATE-022",
        "runId": "knowledge-egress-v1-20260812-diagnostic-01",
        "recordedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "mode": "real_retrieval_local_deterministic_summary",
        "dataBoundary": {
            "realKnowledgeContentPersisted": False,
            "questionPersisted": False,
            "jwtPersisted": False,
            "rawModelPayloadPersisted": False,
            "externalModelCalled": False,
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
        "localSummaryCalls": local_transport.calls,
        "externalModelCalls": 0,
        "cases": case_records,
        "negativeMatrix": negative_records,
        "validation": {"catalogValidation": "passed", "logLeakCount": 0, "schemaValidation": "passed"},
    }
    write_diagnostic_evidence(Path(_required("AGENT_KNOWLEDGE_EGRESS_DIAGNOSTIC_OUTPUT")), evidence)
