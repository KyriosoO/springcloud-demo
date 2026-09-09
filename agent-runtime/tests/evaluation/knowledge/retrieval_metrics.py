"""Offline retrieval scoring; no text, model answer, I/O, or online gold use."""
from __future__ import annotations

from dataclasses import dataclass
from math import log2
import re
from typing import Literal

CorpusState = Literal["present", "missing", "unknown"]


@dataclass(frozen=True, slots=True)
class SourceRef:
    chunk_id: str
    sha256: str


@dataclass(frozen=True, slots=True)
class RelevanceGrade:
    source: SourceRef
    grade: int


@dataclass(frozen=True, slots=True)
class RetrievalMetrics:
    corpus_state: CorpusState
    k: int
    candidate_count: int
    evidence_count: int
    required_group_count: int
    judged_pool_size: int
    unjudged_top_count: int
    necessary_recall_at_k: float | None
    mrr_at_k: float | None
    evidence_coverage: float | None
    precision_at_k: float | None
    ndcg_at_k: float | None


def _source_valid(source: SourceRef) -> bool:
    return (
        type(source) is SourceRef
        and type(source.chunk_id) is str
        and re.fullmatch(r"[A-Za-z0-9._#-]{1,256}", source.chunk_id) is not None
        and type(source.sha256) is str
        and re.fullmatch(r"[0-9a-f]{64}", source.sha256) is not None
    )


def _sources_valid(sources: tuple[SourceRef, ...], maximum: int) -> bool:
    return (
        type(sources) is tuple
        and len(sources) <= maximum
        and all(_source_valid(source) for source in sources)
        and len(set(sources)) == len(sources)
    )


def score_retrieval(
    *, corpus_state: CorpusState, k: int, ranked: tuple[SourceRef, ...],
    required_groups: tuple[tuple[SourceRef, ...], ...], evidence: tuple[SourceRef, ...],
    grades: tuple[RelevanceGrade, ...] = (),
) -> RetrievalMetrics:
    """Score human-confirmed source groups, independently of summary success.

    Missing/unknown corpus is unscored, never silently counted as success/miss.
    Precision uses the requested k, including unfilled ranks as zero. Graded
    metrics are relative to the declared judgment pool, not the entire corpus.
    """
    if (type(corpus_state) is not str or corpus_state not in ("present", "missing", "unknown")
        or type(k) is not int or not 1 <= k <= 80
        or not _sources_valid(ranked, 80) or not _sources_valid(evidence, 8)
        or not set(evidence).issubset(ranked)
        or type(required_groups) is not tuple or len(required_groups) > 8
        or any(not _sources_valid(group, 16) or not group for group in required_groups)
        or (bool(required_groups) != (corpus_state == "present"))
        or type(grades) is not tuple or len(grades) > 256):
        raise ValueError("knowledge.retrieval_metrics_input_invalid")
    if any(
        type(item) is not RelevanceGrade or not _source_valid(item.source)
        or type(item.grade) is not int or not 0 <= item.grade <= 3
        for item in grades
    ):
        raise ValueError("knowledge.retrieval_metrics_input_invalid")
    grade_map = {item.source: item.grade for item in grades}
    required = {source for group in required_groups for source in group}
    if len(grade_map) != len(grades) or any(grade_map.get(source) == 0 for source in required):
        raise ValueError("knowledge.retrieval_metrics_input_invalid")
    top = ranked[:k]
    unjudged = sum(source not in grade_map for source in top)
    recall = mrr = coverage = precision = ndcg = None
    if corpus_state == "present":
        recall = sum(any(source in top for source in group) for group in required_groups) / len(required_groups)
        coverage = sum(any(source in evidence for source in group) for group in required_groups) / len(required_groups)
        relevant = required | {source for source, grade in grade_map.items() if grade > 0}
        mrr = next((1.0 / rank for rank, source in enumerate(top, 1) if source in relevant), 0.0)
        if not unjudged:
            precision = sum(grade_map[source] > 0 for source in top) / k
            dcg = sum((2 ** grade_map[source] - 1) / log2(rank + 1) for rank, source in enumerate(top, 1))
            ideal = sum((2 ** grade - 1) / log2(rank + 1) for rank, grade in enumerate(sorted(grade_map.values(), reverse=True)[:k], 1))
            if ideal > 0:
                ndcg = dcg / ideal
    return RetrievalMetrics(
        corpus_state=corpus_state, k=k, candidate_count=len(ranked), evidence_count=len(evidence),
        required_group_count=len(required_groups), judged_pool_size=len(grades), unjudged_top_count=unjudged,
        necessary_recall_at_k=recall, mrr_at_k=mrr, evidence_coverage=coverage,
        precision_at_k=precision, ndcg_at_k=ndcg,
    )
