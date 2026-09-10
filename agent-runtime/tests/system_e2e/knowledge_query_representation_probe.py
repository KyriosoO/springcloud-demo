"""P3 20.82: read-only manual-query ablation, never a production composition root."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import time
from unittest.mock import patch

import httpx

from agent_runtime.knowledge.contracts import DomainCandidateCount, PathRef, RetrievalCoverage
from agent_runtime.knowledge.evidence.admission import ScoreAwareEvidenceSelector
from agent_runtime.knowledge.retrieval.bge_rerank_context import ContextualBgeRerankAdapter
from agent_runtime.knowledge.retrieval.contracts import KnowledgePathRequest, PathCandidateSet, PathResultKind, RankedKnowledgeBatch
from agent_runtime.knowledge.retrieval.quality_ranking_v3 import rank_requirement_candidates
from tests.evaluation.knowledge.retrieval_benchmark_dataset import load_dataset
from tests.system_e2e import knowledge_stage_b_quality_v3_probe as base
from tests.system_e2e import knowledge_stage_b_services as services
from tests.system_e2e.knowledge_retrieval_benchmark_v1 import measure_case, verify_sources

REPO = Path(__file__).resolve().parents[3]
BINDING = REPO / "serviceCenter/knowledge-runtime-binding.v2.json"
OUTPUT = Path(__file__).parents[1] / "evaluation/knowledge/query_representation.result.v1.jsonl"
LIMITS = {"search": 81, "embedding": 27, "rerank": 58}
ARMS = ("focused_both", "original_keyword")


def require(condition, reason):
    if not condition:
        raise ValueError("query_representation." + reason)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def executable_fingerprint():
    # All service bytecode/resources/classpaths stay identical between the arms.
    files = tuple(sorted((REPO/"es-query-service/target/classes").rglob("*")))
    files += (REPO/"es-query-service/target/stage-b-classpath.txt",
              REPO/"auth-service/target/auth-service-0.0.1-SNAPSHOT.jar")
    return digest(json.dumps([(str(p.relative_to(REPO)),digest(p.read_bytes())) for p in files if p.is_file()],
        separators=(",", ":")).encode())


def prepare_cases(dataset):
    """No source IDs, gold clauses or body access in query construction."""
    rows = []
    for case in dataset.cases:
        queries = tuple((domain, " ".join(r.focus for r in case.requirements if r.domain_id == domain))
                        for domain in case.domains)
        require(all(1 <= len(q) <= 1024 for _, q in queries), "query_length")
        require(all(base.QuestionEgressGuard().evaluate(q).disposition is base.QuestionEgressDisposition.ALLOWED
                    for q in (case.question, *(q for _, q in queries))), "unsafe_query")
        plan = base.KnowledgeRetrievalPlan(config_version="knowledge-flow-config-v1",
            quality_version=base.KNOWLEDGE_QUALITY_VERSION_V3, question_kind=base.KnowledgeQuestionKind.LOOKUP,
            selected_domain_ids=case.domains, evidence_requirements=case.requirements,
            items=tuple(base.RetrievalPlanItem(logical_domain_id=d, query_text=q, path=p, candidate_limit=20, ordinal=i)
                        for i, (d, q, p) in enumerate(((d, q, p) for d, q in queries
                            for p in (base.RetrievalPath.KEYWORD, base.RetrievalPath.VECTOR)), 1)))
        base.validate_plan_requirements(quality_version=plan.quality_version, question_kind=plan.question_kind,
            requirements=plan.evidence_requirements, domain_ids=plan.selected_domain_ids)
        rows.append((case, queries, plan))
    require(len(rows) == 24 and sum(len(q) for _, q, _ in rows) == 27, "dataset_shape")
    return tuple(rows)


class Budget:
    def __init__(self):
        self.counts = dict.fromkeys(LIMITS, 0)
        self.stopped = False

    async def request(self, request):
        routes = {"http://127.0.0.1:19201/es/knowledge/search": "search",
                  "http://127.0.0.1:8908/embed": "embedding", "http://127.0.0.1:8909/rerank": "rerank"}
        kind = routes.get(str(request.url))
        if (self.stopped or request.method != "POST" or kind is None
                or request.url.port != 19201 and "authorization" in request.headers
                or self.counts.get(kind, 0) >= LIMITS.get(kind, 0)):
            self.stopped = True
            raise ValueError("query_representation.outbound_rejected")
        self.counts[kind] += 1


def candidate_set(result, domain, path, binding):
    require(result.kind in (PathResultKind.CANDIDATES, PathResultKind.NO_RESULT), "path_failed")
    require(result.logical_domain_id == domain and result.path is path
        and result.index_snapshot_id == binding["lawSnapshotId" if domain == "tax.law" else "policySnapshotId"]
        and result.profile_version == "tax-knowledge-search-v1" and bool(result.read_policy_version), "path_binding")
    require(len(result.candidates) <= 20 and (bool(result.candidates) == (result.kind is PathResultKind.CANDIDATES)), "path_shape")
    return PathCandidateSet(logical_domain_id=domain, retrieval_profile_id=result.retrieval_profile_id,
        path=path, profile_version=result.profile_version, index_snapshot_id=result.index_snapshot_id,
        read_policy_version=result.read_policy_version, truncated=result.truncated, candidates=result.candidates)


def required_ranks(case, dataset, candidates):
    expected = {s.id: s for s in dataset.sources if s.id in case.sources}
    return {name: [i for i, c in enumerate(candidates, 1)
                   if (c.chunk_id, c.content_sha256) == (source.chunk_id, source.sha256)]
            for name, source in expected.items()}


async def measure(case, dataset, plan, sets, rerank, catalog):
    fusion = base.ReciprocalRankFusion()
    fused = fusion.fuse(sets)
    ranked = await rank_requirement_candidates(plan=plan, sets=sets, fused=fused, fusion=fusion,
        rerank=rerank, deadline=asyncio.get_running_loop().time() + 20, final_candidates=20) if fused else ()
    selection = policy = None
    if ranked:
        batch = RankedKnowledgeBatch(candidates=ranked, profile_version="tax-knowledge-search-v1",
            index_snapshot_ids=tuple(dict.fromkeys(s.index_snapshot_id for s in sets)))
        coverage = RetrievalCoverage(
            successful_paths=tuple(PathRef(logical_domain_id=s.logical_domain_id, path=s.path) for s in sets if s.candidates),
            no_result_paths=tuple(PathRef(logical_domain_id=s.logical_domain_id, path=s.path) for s in sets if not s.candidates),
            failed_paths=(), complete=True,
            candidate_count_by_domain=tuple(DomainCandidateCount(logical_domain_id=d,
                count=sum(d in c.domain_ids for c in ranked)) for d in case.domains))
        value = base.KnowledgeEvidenceInput(original_question=case.question, selected_query=plan.items[0].query_text,
            selected_domain_ids=case.domains, coverage=coverage, batch=batch,
            question_policy_version=base.QuestionEgressGuard().evaluate(case.question).policy_version,
            question_egress_denied=False, quality_version=plan.quality_version,
            question_kind=plan.question_kind, evidence_requirements=plan.evidence_requirements)
        selection = ScoreAwareEvidenceSelector().select(candidates=base.EvidenceIntegrityVerifier().verify(input=value),
            input=value, minimized_question=case.question, limits=base.KnowledgeEvidenceLimits.quality_v3())
        if selection.bundle:
            policy = base.KnowledgeEvidenceEgressDecider().decide(bundle=selection.bundle, catalog=catalog)
    ranked_rows = [base.identity(c.candidate) for c in ranked]
    evidence = [base.identity(c) for c in selection.bundle.evidence] if selection and selection.bundle else []
    return dict(poolRequiredRanks=required_ranks(case, dataset, [c.candidate for c in fused]),
        ranked=ranked_rows, evidence=evidence, metrics=measure_case(case, dataset, ranked_rows, evidence),
        selectionSufficient=bool(selection and selection.sufficient), policyAllowed=bool(policy and policy.allowed))


async def diagnose(prepared, dataset, binding, token, emit, budget):
    catalog = base.KnowledgeEgressPolicyCatalog.load_current_resource()
    require(catalog.snapshot.source_sha256 == base.CATALOG_SHA, "policy_changed")
    async with base.build_knowledge_http_client("http://127.0.0.1:19201") as es, \
            base.build_knowledge_http_client("http://127.0.0.1:8908") as embed, \
            base.build_knowledge_http_client("http://127.0.0.1:8909") as rank:
        for client in (es, embed, rank):
            client.event_hooks["request"].append(budget.request)
        search = base.EsKnowledgeSearchAdapter(base.HttpxKnowledgeTransport(es))
        embedding = base.BgeM3EmbeddingAdapter(base.HttpxKnowledgeTransport(embed))
        rerank = ContextualBgeRerankAdapter(base.HttpxKnowledgeTransport(rank))
        for case, queries, plan in prepared:
            before = dict(budget.counts)
            emit(dict(event="case_started", caseId=case.id))
            context = base.KnowledgeRetrievalContext(request_id=case.id, correlation_id=case.id, subject="admin",
                user_token=base.OpaqueUserToken.from_raw(token), deadline_monotonic=time.monotonic()+60,
                cancellation=base.MutableCancellationSignal())
            arms, paths = {a: [] for a in ARMS}, []
            for domain, focused in queries:
                vector = await embedding.embed(text=focused, timeout_s=3)
                received = []
                for label, path, query in (("original_keyword", base.RetrievalPath.KEYWORD, case.question),
                        ("focused_keyword", base.RetrievalPath.KEYWORD, focused),
                        ("focused_vector", base.RetrievalPath.VECTOR, focused)):
                    result = await search.search(request=KnowledgePathRequest(logical_domain_id=domain,
                        retrieval_profile_id={"tax.policy":"tax-policy-v1", "tax.law":"tax-law-v1"}[domain],
                        path=path, query_text=query if path is base.RetrievalPath.KEYWORD else None,
                        query_vector=vector if path is base.RetrievalPath.VECTOR else None, candidate_limit=20),
                        context=context, timeout_s=5)
                    value = candidate_set(result, domain, path, binding)
                    received.append(value)
                    paths.append(dict(domain=domain, path=label, querySha256=digest(query.encode()),
                        count=len(value.candidates), requiredRanks=required_ranks(case, dataset, value.candidates)))
                # Never add the third path to an arm; only the vector is shared.
                arms["focused_both"].extend((received[1], received[2]))
                arms["original_keyword"].extend((received[0], received[2]))
            results = {}
            for arm in ARMS:
                results[arm] = await measure(case, dataset, plan, tuple(arms[arm]), rerank, catalog)
            emit(dict(event="case", caseId=case.id, split=case.split, paths=paths, arms=results,
                counts={k: budget.counts[k]-before[k] for k in LIMITS}))
    require(all(c.is_closed for c in (es, embed, rank)), "clients_not_closed")


class ServiceRoot:
    def __truediv__(self, path):
        return BINDING if path == "serviceCenter/knowledge-runtime-binding.v1.json" else REPO/path


def audit(binding, dataset):
    """Maintenance-only source check; never supplied to any search Adapter."""
    with httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False, follow_redirects=False, timeout=5) as client:
        r = client.get("/_alias/"+binding["readAlias"])
        require(r.status_code == 200 and list(r.json()) == [binding["expectedIndexName"]], "alias_changed")
        r = client.get("/"+binding["expectedIndexName"]+"/_settings",
            params={"filter_path":"*.settings.index.uuid,*.settings.index.blocks.write"})
        require(r.status_code == 200, "settings_failed")
        state = r.json()[binding["expectedIndexName"]]["settings"]["index"]
        require(state["uuid"] == binding["expectedIndexUuid"] and str(state["blocks"]["write"]).lower() == "true", "index_changed")
        r = client.post("/"+binding["expectedIndexName"]+"/_search", json={"size":40,
            "_source":["chunkId","content","channel"],"query":{"terms":{"chunkId":[s.chunk_id for s in dataset.sources]}}})
        require(r.status_code == 200 and len(r.content) <= 2*1024*1024, "source_audit_failed")
        verify_sources(dataset, r.json())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-local", action="store_true")
    args = parser.parse_args()
    require(args.execute_local, "explicit_local_execution_required")
    os.environ.pop("LLM_API_KEY", None)  # Remove, never inspect or propagate the credential.
    dataset = load_dataset()
    prepared = prepare_cases(dataset)
    binding = json.loads(BINDING.read_text(encoding="utf-8-sig"))
    require(digest(BINDING.read_bytes()) == dataset.binding_sha256, "binding_changed")
    require(not subprocess.check_output(["git","status","--porcelain"],cwd=REPO), "dirty_worktree")
    head = subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO).decode().strip()
    java = shutil.which("java")
    require(java is not None and Path(java).resolve() == Path("C:/Program Files/Java/jdk-25.0.2/bin/java.exe").resolve(), "java_binding")
    executable_sha = executable_fingerprint()
    budget = Budget()
    # Do not accept arbitrary output paths or overwrite a prior diagnostic.
    with OUTPUT.open("x", encoding="utf-8", newline="\n") as stream:
        def emit(value):
            stream.write(json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(",",":"))+"\n")
            stream.flush()
            if value.get("event") in ("case_started","terminal") or value.get("stage") == "cleanup":
                print(json.dumps(value,ensure_ascii=False),flush=True)
        emit(dict(event="prepared",head=head,probeSha256=digest(Path(__file__).read_bytes()),
            datasetSha256=dataset.sha256,bindingSha256=dataset.binding_sha256,limits=LIMITS,
            queryOrigin="manual_focus_not_model_output",arms=list(ARMS),cases=[c.id for c,_,_ in prepared],
            classSha256=digest((REPO/"es-query-service/target/classes/com/dylan/esquery/service/DocumentNumberQuery.class").read_bytes()),
            executableFingerprint=executable_sha, javaSha256=digest(Path(java).read_bytes()),
            selectorVersion=ScoreAwareEvidenceSelector.VERSION,rerankInputVersion=ContextualBgeRerankAdapter.INPUT_VERSION))
        status, failure, warmup_calls = "failed", None, 0
        try:
            audit(binding, dataset)
            warmup_calls = 1
            warmup = runpy.run_path(str(REPO/"serviceCenter/warmup-knowledge-reranker.py"))["warmup"]
            asyncio.run(warmup())
            with patch.object(services,"REPO",ServiceRoot()), services.local_services(emit) as (token, actual):
                require(actual == binding, "service_binding_changed")
                asyncio.run(diagnose(prepared,dataset,binding,token,emit,budget))
            audit(binding, dataset)
            require(executable_fingerprint() == executable_sha and
                subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO).decode().strip() == head and
                not subprocess.check_output(["git","diff","HEAD","--name-only"],cwd=REPO), "code_changed")
            status = "measured"
        except (Exception, KeyboardInterrupt, asyncio.CancelledError) as exc:
            # Preserve finite partial evidence; never print response/credential-bearing messages.
            failure = type(exc).__name__
        emit(dict(event="terminal",status=status,failureClass=failure,counts=budget.counts,
            startupRerankCalls=warmup_calls,modelCalls=0,businessCalls=0,indexWrites=0,retry=0,resume=0,
            limitations=["manual_focus_not_model_output","not_production_stage_or_summary_uat","ungraded_precision_ndcg"]))
    return 0 if status == "measured" else 1


if __name__ == "__main__":
    raise SystemExit(main())
