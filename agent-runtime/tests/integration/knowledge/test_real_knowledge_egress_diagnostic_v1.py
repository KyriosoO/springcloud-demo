from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from agent_runtime.knowledge.contracts import EvidenceStageKind, RetrievalStageKind
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
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from agent_runtime.model.context import ModelCallContextAccessor
from agent_runtime.model.deepseek.transport import DeepSeekChatTransport, build_deepseek_http_client
from agent_runtime.model.gateway import BoundedStructuredModelGateway
from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.model.settings import ModelSettings
from tests.integration.knowledge.egress_diagnostic_journal import (
    AUTHORIZED_SUMMARY_CALLS,
    KnowledgeEgressDiagnosticJournal,
    validate_diagnostic_journal,
    write_diagnostic_result_from_journal,
)
from tests.integration.knowledge.knowledge_egress_diagnostic_support import (
    CASES,
    DiagnosticBudgetedSummaryTransport,
    PreparedDiagnosticCase,
    RecordingExtractiveSummaryValidator,
    count_forbidden_keys,
    evidence_context,
    evidence_input,
    required_environment,
    retrieval_context,
    retrieval_plan,
    with_model_context,
)


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_KNOWLEDGE_EGRESS_DIAGNOSTIC_V1") != "1",
    reason="requires explicit GATE-041 Knowledge validator diagnostic opt-in",
)

EVIDENCE_DIR = Path(__file__).with_name("evidence")
EXPORT_MANIFEST = EVIDENCE_DIR / "knowledge-egress-export-20260812-01.manifest.json"


@pytest.mark.asyncio
async def test_gate041_real_retrieval_and_nine_bounded_diagnostic_summaries() -> None:
    token = required_environment("AGENT_KNOWLEDGE_ADMIN_JWT")
    catalog = KnowledgeEgressPolicyCatalog.load_v1_resource()
    export_manifest = json.loads(EXPORT_MANIFEST.read_text(encoding="utf-8"))
    assert export_manifest["catalog"]["sha256"]
    definition = KnowledgeSummaryTaskV1.definition()
    journal_path = Path(required_environment("AGENT_KNOWLEDGE_DIAGNOSTIC_JOURNAL_OUTPUT"))
    journal = KnowledgeEgressDiagnosticJournal(
        journal_path,
        run_id=required_environment("AGENT_KNOWLEDGE_DIAGNOSTIC_RUN_ID"),
        authorization_reference=required_environment("AGENT_KNOWLEDGE_DIAGNOSTIC_AUTHORIZATION_REFERENCE"),
        manifest_sha256=required_environment("AGENT_KNOWLEDGE_DIAGNOSTIC_MANIFEST_SHA256"),
    )
    validator = RecordingExtractiveSummaryValidator()
    model_settings = ModelSettings.from_env(os.environ)
    model_client = build_deepseek_http_client(model_settings)
    transport = DiagnosticBudgetedSummaryTransport(
        DeepSeekChatTransport(settings=model_settings, client=model_client),
        journal,
        validator,
    )
    gateway = BoundedStructuredModelGateway(
        transport=transport,
        definitions=(definition,),
        max_concurrency=1,
    )
    stage = DefaultKnowledgeEvidenceStage(
        catalog=catalog,
        guard=QuestionEgressGuard(),
        context=ModelCallContextAccessor(),
        gateway=gateway,
        definition=definition,
        validator=validator,
    )
    prepared: list[PreparedDiagnosticCase] = []
    try:
        async with (
            build_knowledge_http_client(required_environment("AGENT_KNOWLEDGE_ES_BASE_URL")) as es_client,
            build_knowledge_http_client(required_environment("AGENT_KNOWLEDGE_EMBEDDING_BASE_URL")) as embedding_client,
            build_knowledge_http_client(required_environment("AGENT_KNOWLEDGE_RERANK_BASE_URL")) as rerank_client,
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
                    plan=retrieval_plan(case),
                    context=retrieval_context(token, deadline),
                    timeout_s=20.0,
                )
                assert retrieval.kind is RetrievalStageKind.SUCCESS
                assert retrieval.batch is not None and retrieval.coverage is not None
                assert retrieval.coverage.complete and not retrieval.coverage.failed_paths
                source = evidence_input(case, retrieval)
                verified = EvidenceIntegrityVerifier().verify(input=source)
                selection = DeterministicEvidenceSelector().select(
                    candidates=verified,
                    input=source,
                    minimized_question=case.question,
                    limits=KnowledgeEvidenceLimits.v1(),
                )
                assert selection.sufficient and selection.bundle is not None
                decision = KnowledgeEvidenceEgressDecider().decide(bundle=selection.bundle, catalog=catalog)
                assert decision.allowed and decision.summary_input is not None
                request = definition.build_request(decision.summary_input)
                assert count_forbidden_keys(json.loads(request.user_payload_json)) == 0
                prepared.append(PreparedDiagnosticCase(case, retrieval, source))

        for _ in range(3):
            for prepared_case in prepared:
                call_ordinal = transport.calls + 1
                deadline = asyncio.get_running_loop().time() + 25.0
                transport.begin_case(prepared_case.case.case_id)
                try:
                    result = await with_model_context(
                        lambda: stage.build_result(
                            input=prepared_case.evidence_input,
                            context=evidence_context(deadline, call_ordinal),
                            timeout_s=20.0,
                        ),
                        question=prepared_case.case.question,
                        deadline=deadline,
                        call_ordinal=call_ordinal,
                    )
                    transport.record_result(
                        case_id=prepared_case.case.case_id,
                        kind=result.kind,
                        stage_code=result.stage_code,
                    )
                finally:
                    transport.end_case(prepared_case.case.case_id)
                assert result.kind in {
                    EvidenceStageKind.SUCCESS,
                    EvidenceStageKind.NO_RESULT,
                    EvidenceStageKind.TIMEOUT,
                    EvidenceStageKind.DOWNSTREAM_FAILURE,
                }

        records = validate_diagnostic_journal(journal_path)
        assert transport.calls == AUTHORIZED_SUMMARY_CALLS
        assert transport.retry_count == 0
        assert transport.forbidden_field_count == 0
        assert sum(record["event"] == "outbound_started" for record in records) == AUTHORIZED_SUMMARY_CALLS
        assert sum(record["event"] == "call_terminal" for record in records) == AUTHORIZED_SUMMARY_CALLS
        write_diagnostic_result_from_journal(
            journal_path=journal_path,
            output_path=Path(required_environment("AGENT_KNOWLEDGE_DIAGNOSTIC_RESULT_OUTPUT")),
        )
    finally:
        await model_client.aclose()
