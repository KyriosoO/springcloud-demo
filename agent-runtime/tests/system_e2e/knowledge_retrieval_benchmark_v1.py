"""UAT_01 14.41: one local, read-only benchmark; no Rewrite/Summary or paid call.

Reuse the frozen operational harness, observations and current production
components. Only test orchestration handles NO_RESULT as a measured zero.
"""
from __future__ import annotations

import asyncio
from contextlib import ExitStack
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time
import types
import unicodedata
from unittest.mock import patch

import httpx

from agent_runtime.knowledge.retrieval.bge_rerank_context import ContextualBgeRerankAdapter
from tests.evaluation.knowledge.retrieval_benchmark_dataset import Dataset, load_dataset
from tests.evaluation.knowledge.retrieval_metrics import SourceRef, score_retrieval
from tests.system_e2e import knowledge_stage_b_quality_v3_probe as base

BASE_SHA = "618bae17d518623edd526baf861d2249920bb475f553aa8593006bb5d45c6542"


def verify_sources(dataset, value):
    """Offline audit of exact known sources, not an online retrieval shortcut."""
    hits = value["hits"]["hits"]
    if type(hits) is not list or len(hits) != len(dataset.sources):
        raise ValueError("benchmark_source_changed")
    expected = {s.chunk_id: s for s in dataset.sources}
    seen = set()
    for hit in hits:
        source = hit["_source"]
        identifier, content = source["chunkId"], source["content"]
        if identifier not in expected or identifier in seen or type(content) is not str:
            raise ValueError("benchmark_source_changed")
        if content != unicodedata.normalize("NFC", content):
            raise ValueError("benchmark_source_changed")
        rule = expected[identifier]
        domain = "tax.law" if source["channel"] in ("法律", "行政法规") else "tax.policy"
        if (hashlib.sha256(content.encode()).hexdigest() != rule.sha256 or domain != rule.domain_id
                or any(anchor not in content for anchor in rule.anchors)):
            raise ValueError("benchmark_source_changed")
        seen.add(identifier)


def audit_sources(support, binding, dataset):
    with httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False, follow_redirects=False,
                      timeout=5, headers={"Accept-Encoding": "identity"}) as client:
        status, raw = support.bounded_request(client, "POST", f'/{binding["expectedIndexName"]}/_search',
            json={"size": 40, "_source": ["chunkId", "content", "channel"],
                  "query": {"terms": {"chunkId": [s.chunk_id for s in dataset.sources]}}})
    if status != 200:
        raise ValueError("benchmark_source_http_failed")
    verify_sources(dataset, json.loads(raw, object_pairs_hook=base._unique, parse_constant=base._reject_constant))


def measure_case(case, dataset, ranked, evidence):
    sources = {s.id: SourceRef(s.chunk_id, s.sha256) for s in dataset.sources}
    return asdict(score_retrieval(corpus_state="present", k=20,
        ranked=tuple(SourceRef(s["chunkId"], s["sha256"]) for s in ranked),
        evidence=tuple(SourceRef(s["chunkId"], s["sha256"]) for s in evidence),
        required_groups=tuple((sources[s],) for s in case.sources)))


async def diagnose(dataset, binding, token, emit, budget, *, client_factory=base.build_knowledge_http_client):
    catalog = base.KnowledgeEgressPolicyCatalog.load_current_resource()
    if catalog.snapshot.source_sha256 != base.CATALOG_SHA:
        raise ValueError("probe_catalog_changed")
    measured = complete = 0
    async with client_factory("http://127.0.0.1:19201") as es, \
            client_factory("http://127.0.0.1:8908") as embedding, client_factory("http://127.0.0.1:8909") as rerank:
        for client in (es, embedding, rerank):
            client.event_hooks["request"].append(budget.request)
        for case, spec in zip(dataset.cases, base.SPECIFICATIONS, strict=True):
            question, plan = base.plan_for(spec)
            budget.current = dict.fromkeys(base.LIMITS, 0)
            rows = []
            stage = base.DefaultKnowledgeRetrievalStage(
                search=base.ObservedSearch(base.EsKnowledgeSearchAdapter(base.HttpxKnowledgeTransport(es)), binding, rows),
                embedding=base.BgeM3EmbeddingAdapter(base.HttpxKnowledgeTransport(embedding)),
                rerank=base.ObservedRerank(ContextualBgeRerankAdapter(base.HttpxKnowledgeTransport(rerank)), rows),
                fusion=base.ObservedFusion(rows))
            context = base.KnowledgeRetrievalContext(request_id=case.id, correlation_id=case.id, subject="admin",
                user_token=base.OpaqueUserToken.from_raw(token), deadline_monotonic=time.monotonic() + 30,
                cancellation=base.MutableCancellationSignal())
            result = await stage.execute(plan=plan, context=context, timeout_s=20)
            for row in rows:
                emit({"event": "retrieval_stage", "caseId": case.id, **row})
            if (result.kind not in (base.RetrievalStageKind.SUCCESS, base.RetrievalStageKind.NO_RESULT)
                    or budget.stopped or result.coverage is None or result.coverage.failed_paths):
                emit({"event": "case", "caseId": case.id, "status": "retrieval_failed", "kind": result.kind.value,
                      "stageCode": result.stage_code.value if result.stage_code else None, "counts": dict(budget.current)})
                raise ValueError("probe_retrieval_failed")
            ranked, evidence, checks = [], [], {}
            sufficient = policy_allowed = False
            if result.kind is base.RetrievalStageKind.SUCCESS:
                value = base.KnowledgeEvidenceInput(original_question=question, selected_query=question,
                    selected_domain_ids=plan.selected_domain_ids, coverage=result.coverage, batch=result.batch,
                    question_policy_version=base.QuestionEgressGuard().evaluate(question).policy_version,
                    question_egress_denied=False, quality_version=plan.quality_version,
                    question_kind=plan.question_kind, evidence_requirements=plan.evidence_requirements)
                selection = base.DeterministicEvidenceSelector().select(
                    candidates=base.EvidenceIntegrityVerifier().verify(input=value), input=value,
                    minimized_question=question, limits=base.KnowledgeEvidenceLimits.quality_v3())
                policy = base.KnowledgeEvidenceEgressDecider().decide(bundle=selection.bundle, catalog=catalog) if selection.bundle else None
                if policy and policy.allowed:
                    projected = policy.summary_input
                    payload = base.KnowledgeRequirementSummaryInput(schema_version=2, question=projected.question,
                        coverage=projected.coverage, evidence=projected.evidence, requirements=plan.evidence_requirements)
                    if len(base.requirement_summary_input_json(payload).encode()) > base.KnowledgeEvidenceLimits.quality_v3().max_summary_input_bytes:
                        raise ValueError("probe_payload_limit")
                checks = base.assess_sources(case.id, rows, result.batch, selection.bundle, policy.summary_input if policy else None)
                ranked = [{**base.identity(c.candidate), "rank": c.rank, "requirementIds": list(c.requirement_ids)} for c in result.batch.candidates]
                evidence = [base.identity(c) for c in selection.bundle.evidence] if selection.bundle else []
                sufficient, policy_allowed = selection.sufficient, bool(policy and policy.allowed)
            metrics = measure_case(case, dataset, ranked, evidence)
            measured += 1
            complete += bool(checks) and all(c["allowedOriginalClause"] for c in checks.values())
            emit({"event": "case", "caseId": case.id, "split": case.split, "status": "measured",
                  "kind": result.kind.value, "counts": dict(budget.current), "coverageComplete": result.coverage.complete,
                  "selectionSufficient": sufficient, "policyAllowed": policy_allowed, "requiredSources": checks,
                  "ranked": ranked, "evidence": evidence, "metrics": metrics})
    return {"casesMeasured": measured, "casesWithRequiredSources": complete}


def main():
    dataset = load_dataset()
    if hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest() != BASE_SHA:
        raise ValueError("benchmark_base_changed")
    original_check, original_emit = base.check_index, base.emit_line
    startup = {"rerankCalls": 0, "sourceAudits": 0}

    def check(support, binding):
        support.java_executable()  # Before any warmup or service start.
        original_check(support, binding)
        if startup["sourceAudits"] >= 2:
            raise ValueError("benchmark_source_budget")
        startup["sourceAudits"] += 1
        audit_sources(support, binding, dataset)
        if startup["rerankCalls"] == 0:
            module = types.ModuleType("benchmark_warmup")
            warmup_path = base.REPO / "serviceCenter/warmup-knowledge-reranker.py"
            exec(compile(warmup_path.read_bytes(), str(warmup_path), "exec"), module.__dict__)
            startup["rerankCalls"] = 1  # Count the attempt even when it fails.
            asyncio.run(module.warmup())

    def emit(stream, value):
        if value["event"] == "prepared":
            value = {**value, "benchmarkSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                     "datasetSha256": dataset.sha256, "datasetId": "retrieval-benchmark-v1",
                     "rerankInputVersion": ContextualBgeRerankAdapter.INPUT_VERSION,
                     "startupRerankBudget": 1, "sourceAuditBudget": 2}
        if value["event"] == "terminal":
            value.update(startupRerankCalls=startup["rerankCalls"], sourceAudits=startup["sourceAudits"])
        original_emit(stream, value)

    with ExitStack() as scope:
        scope.enter_context(patch.multiple(base, **dataset.probe_inputs()))
        scope.enter_context(patch.object(base, "BINDING_SHA", dataset.binding_sha256))
        scope.enter_context(patch.object(base, "check_index", check))
        scope.enter_context(patch.object(base, "emit_line", emit))
        scope.enter_context(patch.object(base, "diagnose", lambda *a, **kw: diagnose(dataset, *a, **kw)))
        return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
