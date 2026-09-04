"""Offline rank-signal experiment; never reads text, credentials or services.

The original domain/path/rerank orders are fixed. Synthetic strict scores replay
the observed order, not real BGE scores. Document IDs, lengths and model output
were not retained: this deliberately does NOT replay Evidence quotas or Summary.
The alternative mergers are experiments, never production policies.
"""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, replace
from fractions import Fraction
import hashlib
import json

from agent_runtime.knowledge.contracts import (
    KNOWLEDGE_QUALITY_VERSION, KnowledgeRetrievalPlan, RetrievalPath, RetrievalPlanItem,
)
from agent_runtime.knowledge.retrieval.contracts import PathCandidateSet, RerankScore
from agent_runtime.knowledge.retrieval.fusion import ReciprocalRankFusion
from agent_runtime.knowledge.retrieval.quality_ranking import rank_by_domain
from tests.retrieval_helpers import candidate
from tests.system_e2e import test_knowledge_stage_b_run_01_history as run01
from tests.system_e2e import test_knowledge_stage_b_run_02_history as run02
from tests.system_e2e import test_knowledge_stage_b_run_03_history as run03
from tests.system_e2e import test_knowledge_stage_b_run_04_history as run04

Key = tuple[str, str]
MODES = ("keyword_first", "rerank_first", "rrf_keyword_rerank", "rrf_three_lists")


def keys(row) -> tuple[Key, ...]:
    items = tuple((item["chunkId"], item["sha256"]) for item in row["candidates"])
    if (len(items) > 80 or any(not isinstance(chunk, str) or not chunk
            or not isinstance(sha, str) or len(sha) != 64
            or any(char not in "0123456789abcdef" for char in sha) for chunk, sha in items)
            or len(set(items)) != len(items)):
        raise ValueError("replay.invalid_candidate_identity")
    return items


@dataclass(frozen=True)
class DomainRanks:
    domain: str
    keyword: tuple[Key, ...]
    vector: tuple[Key, ...]
    rerank: tuple[Key, ...]


def parse_ranks(case) -> tuple[DomainRanks, ...]:
    domains = tuple(case["domains"])
    if not 1 <= len(domains) <= 2 or len(set(domains)) != len(domains) or not set(domains) <= {"tax.policy", "tax.law"}:
        raise ValueError("replay.invalid_domains")
    stages = case["retrievalStages"]
    paths = [row for row in stages if row["stage"] == "path"]
    reranks = [keys(row) for row in stages if row["stage"] == "rerank"]
    if len(paths) != 2 * len(domains) or len(reranks) != len(domains):
        raise ValueError("replay.incomplete_stages")
    result = []
    seen = set()
    for domain in domains:
        ordered_paths = []
        for path in ("keyword", "vector"):
            matches = [row for row in paths if row["domain"] == domain and row["path"] == path]
            if len(matches) != 1 or len(matches[0]["candidates"]) > 20:
                raise ValueError("replay.incomplete_path")
            ordered_paths.append(keys(matches[0]))
        union = set(ordered_paths[0]) | set(ordered_paths[1])
        # Finite evidence lacks document identity; do not infer cross-domain dedup.
        if not union or seen & union:
            raise ValueError("replay.ambiguous_domain_identity")
        seen.update(union)
        matching = [row for row in reranks if set(row) == union]
        if len(matching) != 1:
            raise ValueError("replay.ambiguous_rerank_order")
        result.append(DomainRanks(domain, *ordered_paths, matching[0]))
    if len({chunk for chunk, _ in seen}) != len(seen):
        raise ValueError("replay.content_conflict")
    return tuple(result)


async def replay_current(ranks: tuple[DomainRanks, ...]) -> tuple[Key, ...]:
    """Call real production ranking using synthetic candidates and score orders."""
    by_chunk = {key[0]: key for domain in ranks for key in domain.rerank}
    sets = tuple(PathCandidateSet(
        logical_domain_id=domain.domain, retrieval_profile_id=domain.domain.replace(".", "-") + "-v1",
        path=path, profile_version="tax-knowledge-search-v1", index_snapshot_id="a" * 64,
        read_policy_version="tax-public-authenticated-v1", truncated=False,
        candidates=tuple(replace(candidate(chunk=chunk, domain=domain.domain, rank=ordinal,
            content="synthetic-" + sha), document_id="synthetic-" + chunk)
            for ordinal, (chunk, sha) in enumerate(values, 1)),
    ) for domain in ranks for path, values in (
        (RetrievalPath.KEYWORD, domain.keyword), (RetrievalPath.VECTOR, domain.vector)))
    plan = KnowledgeRetrievalPlan(
        selected_domain_ids=tuple(domain.domain for domain in ranks),
        config_version="offline-rank-replay", quality_version=KNOWLEDGE_QUALITY_VERSION,
        items=tuple(RetrievalPlanItem(logical_domain_id=part.logical_domain_id, path=part.path,
            query_text=part.logical_domain_id, candidate_limit=20, ordinal=i)
            for i, part in enumerate(sets, 1)),
    )

    class OrderedScores:
        async def rerank(self, *, query, candidates, timeout_s):
            domain, = [item for item in ranks if item.domain == query]
            positions = {chunk: rank for rank, (chunk, _) in enumerate(domain.rerank, 1)}
            return tuple(RerankScore(candidate_index=i, score=float(-positions[item.chunk_id]))
                         for i, item in enumerate(candidates))

    fusion = ReciprocalRankFusion()
    result = await rank_by_domain(plan=plan, sets=sets, fused=fusion.fuse(sets), fusion=fusion,
        rerank=OrderedScores(), deadline=asyncio.get_running_loop().time() + 10, final_candidates=20)
    return tuple(by_chunk[item.candidate.chunk_id] for item in result)


def experimental_order(ranks: tuple[DomainRanks, ...], mode: str) -> tuple[Key, ...]:
    """Rank signals only: no case, question, source content or gold input."""
    if mode not in MODES:
        raise ValueError("replay.unknown_mode")
    selected: list[Key] = []
    for domain in ranks:
        for key in domain.keyword[:1] + domain.rerank[:1]:
            if key not in selected:
                selected.append(key)
    queues = []
    for domain in ranks:
        if mode == "keyword_first":
            ordered = tuple(dict.fromkeys(domain.keyword + domain.rerank))
        elif mode == "rerank_first":
            ordered = domain.rerank
        else:
            inputs = (domain.keyword, domain.rerank) + ((domain.vector,) if mode == "rrf_three_lists" else ())
            scores: dict[Key, Fraction] = {}
            for values in inputs:
                for ordinal, key in enumerate(values, 1):
                    scores[key] = scores.get(key, Fraction(0)) + Fraction(1, 60 + ordinal)
            ordered = tuple(sorted(scores, key=lambda key: (-scores[key], key)))
        queues.append(deque(key for key in ordered if key not in selected))
    while any(queues) and len(selected) < 20:
        for queue in queues:
            while queue and len(selected) < 20:
                key = queue.popleft()
                if key not in selected:
                    selected.append(key)
                    break
    return tuple(selected)


def gold_ranks(order, required, gold):
    # Evaluation only, after order is final. Never supplied to a merger.
    return {label: order.index((gold[label]["chunk"], gold[label]["sha256"])) + 1
            if (gold[label]["chunk"], gold[label]["sha256"]) in order else None for label in required}


async def report():
    comparisons = []
    for history in (run01, run02, run03, run04):
        for name, expected in history.HASHES.items():
            if hashlib.sha256((history.ROOT / name).read_bytes()).hexdigest() != expected:
                raise ValueError("replay.history_changed")
        manifest = json.loads((history.ROOT / "manifest.json").read_bytes())
        result = json.loads((history.ROOT / "result.json").read_bytes())
        for case in result["cases"]:
            if not case["retrievalStages"]:
                continue
            ranks = parse_ranks(case)
            actual, = [keys(row) for row in case["retrievalStages"] if row["stage"] == "final_rank"]
            replayed = await replay_current(ranks)
            if replayed != actual:
                raise ValueError("replay.current_order_mismatch")
            required = next(spec["requiredGold"] for spec in manifest["cases"] if spec["caseId"] == case["caseId"])
            orders = {"current": replayed, **{mode: experimental_order(ranks, mode) for mode in MODES}}
            comparisons.append({"runId": result["runId"], "caseId": case["caseId"],
                "currentOrderReproduced": True,
                "finalGoldRanks": {mode: gold_ranks(order, required, manifest["gold"]) for mode, order in orders.items()},
                "observedEvidenceGold": {label: manifest["gold"][label]["sha256"] in case["evidenceContentHashes"] for label in required}})
    return {"scope": "rank-only-counterfactual-not-UAT-or-model-or-evidence-replay",
            "externalCalls": 0, "comparisons": comparisons}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(report()), ensure_ascii=False, sort_keys=True, indent=2))
