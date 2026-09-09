"""Replay frozen rankings, NOT real source bytes, policy or summary quality.

Bodies/document metadata below are synthetic. Real chunk IDs only align the
saved ordering and evaluator sources; gold never enters ranking or admission.
"""
import asyncio
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from agent_runtime.knowledge.contracts import (
    DomainCandidateCount, KnowledgeRetrievalPlan, KnowledgeQuestionKind,
    PathRef, RetrievalCoverage, RetrievalPlanItem, RetrievalPath, KNOWLEDGE_QUALITY_VERSION_V3,
)
from agent_runtime.knowledge.evidence.admission import ScoreAwareEvidenceSelector
from agent_runtime.knowledge.evidence.builder import EvidenceIntegrityVerifier
from agent_runtime.knowledge.evidence.contracts import KnowledgeEvidenceLimits
from agent_runtime.knowledge.retrieval.contracts import PathCandidateSet, RankedKnowledgeBatch, RerankScore
from agent_runtime.knowledge.retrieval.fusion import ReciprocalRankFusion
from agent_runtime.knowledge.retrieval.quality_ranking_v3 import rank_requirement_candidates
from tests.evaluation.knowledge.retrieval_benchmark_dataset import load_dataset
from tests.evidence_helpers import evidence_input
from tests.retrieval_helpers import candidate


@pytest.mark.asyncio
async def test_frozen_first_selection_replay_preserves_sources_but_does_not_establish_precision():
    raw = Path(__file__).with_name("retrieval_benchmark.document_number.result.v1.jsonl").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "b50ee584b09dc3b8d724886240a25b0e9de23e046d5245ef5ef395b81e865299"
    rows, dataset = [json.loads(line) for line in raw.splitlines()], load_dataset()
    totals = {split: {"ranked": 0, "admitted": 0, "selected": 0, "required": 0} for split in ("development", "holdout")}
    for case in dataset.cases:
        part = [r for r in rows if r.get("caseId") == case.id]
        saved = next(r for r in part if r["event"] == "case")
        paths = [r for r in part if r.get("stage") == "path"]
        sets = tuple(PathCandidateSet(logical_domain_id=r["domain"], retrieval_profile_id="synthetic-replay",
            path=RetrievalPath(r["path"]), profile_version="tax-knowledge-search-v1", index_snapshot_id="a" * 64,
            read_policy_version="tax-public-authenticated-v1", truncated=False,
            candidates=tuple(replace(candidate(chunk=c["chunkId"], domain=r["domain"], rank=i),
                document_id=c["chunkId"]) for i, c in enumerate(r["candidates"], 1))) for r in paths)
        plan = KnowledgeRetrievalPlan(config_version="knowledge-flow-config-v1", quality_version=KNOWLEDGE_QUALITY_VERSION_V3,
            question_kind=KnowledgeQuestionKind.LOOKUP, selected_domain_ids=case.domains, evidence_requirements=case.requirements,
            items=tuple(RetrievalPlanItem(logical_domain_id=d, query_text=case.question, path=p, candidate_limit=20, ordinal=i)
                for i, (d, p) in enumerate(((d, p) for d in case.domains for p in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR)), 1)))
        score_rows = sorted((r for r in part if r.get("stage") == "rerank"), key=lambda r: r["ordinal"])

        class Replay:
            def __init__(self): self.n = 0

            async def rerank(self, *, query, candidates, timeout_s):
                assert query == case.requirements[self.n].focus
                scored = {c["chunkId"]: c["score"] for c in score_rows[self.n]["candidates"]}
                self.n += 1
                assert set(scored) == {c.chunk_id for c in candidates}
                return tuple(RerankScore(candidate_index=i, score=scored[c.chunk_id]) for i, c in enumerate(candidates))

        rerank, fusion = Replay(), ReciprocalRankFusion()
        ranked = await rank_requirement_candidates(plan=plan, sets=sets, fused=fusion.fuse(sets), fusion=fusion,
            rerank=rerank, deadline=asyncio.get_running_loop().time() + 5, final_candidates=20)
        assert rerank.n == len(case.requirements)
        assert [(c.candidate.chunk_id, c.rank, list(c.requirement_ids)) for c in ranked] == [
            (c["chunkId"], c["rank"], c["requirementIds"]) for c in saved["ranked"]], case.id
        source = replace(evidence_input(), original_question=case.question, selected_query=case.question,
            selected_domain_ids=case.domains, quality_version=plan.quality_version, question_kind=plan.question_kind,
            evidence_requirements=case.requirements,
            batch=RankedKnowledgeBatch(candidates=ranked, profile_version="tax-knowledge-search-v1", index_snapshot_ids=("a" * 64,)),
            coverage=RetrievalCoverage(successful_paths=tuple(PathRef(logical_domain_id=r.logical_domain_id, path=r.path) for r in sets),
                no_result_paths=(), failed_paths=(), complete=True,
                candidate_count_by_domain=tuple(DomainCandidateCount(logical_domain_id=d,
                    count=sum(d in c.domain_ids for c in ranked)) for d in case.domains)))
        selected = ScoreAwareEvidenceSelector().select(candidates=EvidenceIntegrityVerifier().verify(input=source), input=source,
            minimized_question=case.question, limits=KnowledgeEvidenceLimits.quality_v3())
        assert selected.sufficient
        admitted = tuple(c for c in ranked if c.coverage_anchor or c.rerank_score >= 0.5)
        assert [e.chunk_id for e in selected.bundle.evidence] == [c.candidate.chunk_id for c in admitted[:8]]
        # Evaluation-only join occurs after both online components finish.
        required = {s.chunk_id for s in dataset.sources if s.id in case.sources}
        assert required <= {e.chunk_id for e in selected.bundle.evidence}, case.id
        assert saved["metrics"]["precision_at_k"] is saved["metrics"]["ndcg_at_k"] is None
        group = totals[case.split]
        group["ranked"] += len(ranked)
        group["admitted"] += len(admitted)
        group["selected"] += len(selected.bundle.evidence)
        group["required"] += len(required)
    assert totals == {
        "development": {"ranked": 320, "admitted": 161, "selected": 97, "required": 22},
        "holdout": {"ranked": 160, "admitted": 56, "selected": 43, "required": 8},
    }
