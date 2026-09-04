"""No-LLM controlled retrieval comparison on the unchanged Stage A alias."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import time

from agent_runtime.capability_api.contracts import OpaqueUserToken
from agent_runtime.knowledge.contracts import (
    KNOWLEDGE_QUALITY_VERSION, KnowledgeEvidenceInput, KnowledgeRetrievalContext,
    KnowledgeRetrievalPlan, RetrievalPath, RetrievalPlanItem, RetrievalStageKind,
)
from agent_runtime.knowledge.evidence.builder import DeterministicEvidenceSelector, EvidenceIntegrityVerifier
from agent_runtime.knowledge.evidence.contracts import KnowledgeEvidenceLimits
from agent_runtime.knowledge.retrieval.bge_embedding import BgeM3EmbeddingAdapter
from agent_runtime.knowledge.retrieval.bge_rerank import BgeRerankAdapter
from agent_runtime.knowledge.retrieval.es_adapter import EsKnowledgeSearchAdapter
from agent_runtime.knowledge.retrieval.http import HttpxKnowledgeTransport, build_knowledge_http_client
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.model.contracts import QuestionEgressDisposition
from tests.system_e2e.knowledge_stage_b_probe import NeverCancelled, finite
from tests.system_e2e.knowledge_stage_b_services import local_services

CASES = (
    ("classification", "住宿服务的增值税服务分类是什么？", (("tax.policy", "住宿服务生活服务政策分类"),)),
    ("policy_and_law", "住宿服务的政策分类和增值税法税率规定是什么？",
     (("tax.policy", "住宿服务生活服务政策分类"), ("tax.law", "住宿服务增值税法税率"))),
    ("general", "一般纳税人提供住宿服务适用什么增值税税率？",
     (("tax.policy", "一般纳税人住宿服务生活服务政策分类"), ("tax.law", "一般纳税人住宿服务增值税法税率"))),
    ("holdout", "软件产品增值税即征即退的适用条件是什么？", (("tax.policy", "软件产品增值税即征即退适用条件"),)),
)


async def validate(token, emit, case_id_filter=None, serialize_rerank=False):
    counts = {"search": 0, "embedding": 0, "rerank": 0, "model": 0}
    async def count(request):
        kind = {"/es/knowledge/search": "search", "/embed": "embedding", "/rerank": "rerank"}.get(request.url.path)
        if kind is None:
            raise ValueError("stage_b.unexpected_endpoint")
        counts[kind] += 1
        if counts[kind] > {"search": 12, "embedding": 6, "rerank": 6}[kind]:
            raise ValueError("stage_b.local_budget_exceeded")
    async def response_status(response):
        emit({"stage": "http_status", "path": response.request.url.path, "httpStatus": response.status_code})
    async with (build_knowledge_http_client("http://127.0.0.1:19201") as es,
                build_knowledge_http_client("http://127.0.0.1:8908") as embedding,
                build_knowledge_http_client("http://127.0.0.1:8909") as rerank):
        for client in (es, embedding, rerank):
            client.event_hooks["request"].append(count)
            client.event_hooks["response"].append(response_status)
        rerank_adapter = BgeRerankAdapter(HttpxKnowledgeTransport(rerank))
        class SequentialCalibration:
            def __init__(self):
                self.lock = asyncio.Lock()
            async def rerank(self, **kwargs):
                async with self.lock:
                    return await rerank_adapter.rerank(**kwargs)
        stage = DefaultKnowledgeRetrievalStage(search=EsKnowledgeSearchAdapter(HttpxKnowledgeTransport(es)),
            embedding=BgeM3EmbeddingAdapter(HttpxKnowledgeTransport(embedding)),
            rerank=SequentialCalibration() if serialize_rerank else rerank_adapter)
        try:
            for case_id, question, queries in CASES:
                if case_id_filter is not None and case_id != case_id_filter:
                    continue
                if any(QuestionEgressGuard().evaluate(text).disposition is not QuestionEgressDisposition.ALLOWED
                       for text in (question, *(q for _, q in queries))):
                    raise ValueError("stage_b.unsafe_offline_fixture")
                plan = KnowledgeRetrievalPlan(selected_domain_ids=tuple(d for d, _ in queries),
                    config_version="knowledge-flow-config-v1", quality_version=KNOWLEDGE_QUALITY_VERSION,
                    items=tuple(RetrievalPlanItem(logical_domain_id=d, query_text=q, path=p, candidate_limit=20, ordinal=i)
                        for i, (d, q, p) in enumerate(((d, q, p) for d, q in queries for p in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR)), 1)))
                context = KnowledgeRetrievalContext(request_id=case_id, correlation_id=case_id, subject="admin",
                    user_token=OpaqueUserToken.from_raw(token), deadline_monotonic=time.monotonic() + 30,
                    cancellation=NeverCancelled())
                result = await stage.execute(plan=plan, context=context, timeout_s=20)
                if result.kind is not RetrievalStageKind.SUCCESS:
                    emit({"caseId": case_id, "status": result.kind.value,
                          "stageCode": result.stage_code.value if result.stage_code else None})
                    raise RuntimeError("stage_b.local_retrieval_failed")
                source = KnowledgeEvidenceInput(original_question=question, selected_query=queries[0][1],
                    selected_domain_ids=plan.selected_domain_ids, coverage=result.coverage, question_policy_version="local-probe",
                    question_egress_denied=False, batch=result.batch, quality_version=KNOWLEDGE_QUALITY_VERSION)
                selection = DeterministicEvidenceSelector().select(candidates=EvidenceIntegrityVerifier().verify(input=source),
                    input=source, minimized_question=question, limits=KnowledgeEvidenceLimits.quality_v1())
                selected = {item.chunk_id for item in selection.bundle.evidence} if selection.bundle else set()
                emit({"caseId": case_id, "status": "sufficient" if selection.sufficient else "insufficient_evidence",
                      "ranked": [{**finite(item.candidate, item.rank), "anchor": item.coverage_anchor,
                                  "evidenceSelected": item.candidate.chunk_id in selected} for item in result.batch.candidates]})
                calibration = DeterministicEvidenceSelector().select(candidates=EvidenceIntegrityVerifier().verify(input=source),
                    input=source, minimized_question=question, limits=KnowledgeEvidenceLimits.v1())
                emit({"caseId": case_id, "stage": "offline_legacy_quota_calibration", "perDocument": 2,
                      "productionPass": False,
                      "chunkIds": [item.chunk_id for item in calibration.bundle.evidence] if calibration.bundle else []})
        finally:
            emit({"stage": "counts", **counts})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", choices=[item[0] for item in CASES])
    parser.add_argument("--serialize-rerank", action="store_true", help="offline concurrency calibration, not a production pass")
    options = parser.parse_args()
    with options.output.open("x", encoding="utf-8") as output:
        def emit(value):
            output.write(json.dumps(value, ensure_ascii=True) + "\n")
            output.flush()
            print(json.dumps({key: item for key, item in value.items() if key != "ranked"}), flush=True)
        try:
            with local_services(emit) as (token, binding):
                emit({"stage": "ready", "indexUuid": binding["expectedIndexUuid"], "modelBudget": 0})
                asyncio.run(validate(token, emit, options.case, options.serialize_rerank))
        except Exception as error:
            emit({"stage": "failure", "kind": type(error).__name__})
            raise SystemExit(1) from None


if __name__ == "__main__":
    main()
