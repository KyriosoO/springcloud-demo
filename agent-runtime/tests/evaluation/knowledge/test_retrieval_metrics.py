"""Synthetic metric contracts, not evidence of production retrieval accuracy."""
from dataclasses import FrozenInstanceError, asdict, replace
from math import log2

import pytest

from tests.evaluation.knowledge.retrieval_metrics import RelevanceGrade, SourceRef, score_retrieval


def source(number):
    return SourceRef(f"chunk-{number}", f"{number:064x}")


A, B, C, D = (source(number) for number in range(1, 5))


def score(**changes):
    arguments = dict(corpus_state="present", k=3, ranked=(C, A, B), required_groups=((A,), (B,)), evidence=(A, B))
    arguments.update(changes)
    return score_retrieval(**arguments)


def test_necessary_coverage_and_mrr_without_inventing_relevance_grades():
    value = score()
    assert value.necessary_recall_at_k == value.evidence_coverage == 1.0
    assert value.mrr_at_k == 0.5
    assert value.precision_at_k is value.ndcg_at_k is None
    assert value.judged_pool_size == 0 and value.unjudged_top_count == 3


def test_equivalent_sources_and_shared_source_cover_distinct_requirements():
    value = score(ranked=(D, B), evidence=(D,), required_groups=((A, D), (D,)), k=2)
    assert value.necessary_recall_at_k == value.evidence_coverage == value.mrr_at_k == 1.0


def test_rank_cutoff_and_evidence_are_separate_denominators():
    value = score(k=2, evidence=(B,))
    assert value.necessary_recall_at_k == value.evidence_coverage == 0.5
    assert score(k=1).necessary_recall_at_k == score(k=1).mrr_at_k == 0.0
    assert score(k=1).evidence_coverage == 1.0


def test_same_id_different_content_hash_is_not_same_evidence():
    different = replace(A, sha256="f" * 64)
    value = score(ranked=(different,), evidence=(different,), required_groups=((A,),), k=1)
    assert value.necessary_recall_at_k == value.evidence_coverage == value.mrr_at_k == 0.0


def test_graded_precision_and_ndcg_against_explicit_pool():
    value = score(grades=(RelevanceGrade(A, 3), RelevanceGrade(B, 1), RelevanceGrade(C, 0)))
    expected_dcg = 7 / log2(3) + 1 / log2(4)
    expected_ideal = 7 + 1 / log2(3)
    assert value.precision_at_k == pytest.approx(2 / 3)
    assert value.ndcg_at_k == pytest.approx(expected_dcg / expected_ideal)
    assert value.judged_pool_size == 3 and value.unjudged_top_count == 0


def test_mrr_counts_other_human_judged_relevant_sources_without_required_recall():
    value = score(ranked=(C,), evidence=(), grades=(RelevanceGrade(C, 1),), k=3)
    assert value.necessary_recall_at_k == value.evidence_coverage == 0.0
    assert value.mrr_at_k == 1.0 and value.precision_at_k == pytest.approx(1 / 3)


def test_unjudged_candidate_is_not_assumed_irrelevant():
    value = score(grades=(RelevanceGrade(A, 2), RelevanceGrade(B, 1)))
    assert value.precision_at_k is value.ndcg_at_k is None
    assert value.unjudged_top_count == 1


def test_empty_returned_ranks_and_absent_positive_ideal():
    value = score(ranked=(), evidence=())
    assert value.necessary_recall_at_k == value.mrr_at_k == value.evidence_coverage == 0.0
    assert value.precision_at_k == 0.0 and value.ndcg_at_k is None
    assert score(ranked=(), evidence=(), grades=(RelevanceGrade(A, 1),)).ndcg_at_k == 0.0
    irrelevant = score(ranked=(C,), evidence=(), grades=(RelevanceGrade(C, 0),))
    assert irrelevant.precision_at_k == 0.0 and irrelevant.ndcg_at_k is None


@pytest.mark.parametrize("state", ["missing", "unknown"])
def test_corpus_gap_or_unknown_remains_visible_and_unscored(state):
    value = score(corpus_state=state, required_groups=())
    assert value.corpus_state == state and value.candidate_count == 3
    assert value.required_group_count == 0
    assert all(getattr(value, key) is None for key in (
        "necessary_recall_at_k", "mrr_at_k", "evidence_coverage", "precision_at_k", "ndcg_at_k",
    ))


@pytest.mark.parametrize("changes", [
    {"k": True}, {"k": 0}, {"k": 81}, {"k": 1.0}, {"k": "3"},
    {"corpus_state": "empty"}, {"corpus_state": None},
    {"ranked": [A]}, {"evidence": [A]}, {"required_groups": [(A,)]},
    {"required_groups": ([A],)}, {"grades": []},
    {"ranked": (A, A)}, {"evidence": (A, A)}, {"evidence": (D,)},
    {"required_groups": ()}, {"required_groups": ((),)}, {"required_groups": ((A, A),)},
    {"corpus_state": "missing"}, {"corpus_state": "unknown"},
    {"ranked": tuple(source(n) for n in range(81))},
    {"evidence": tuple(source(n) for n in range(9))},
    {"required_groups": ((A,),) * 9},
    {"required_groups": (tuple(source(n) for n in range(17)),)},
    {"grades": tuple(RelevanceGrade(source(n), 1) for n in range(257))},
    {"grades": (RelevanceGrade(A, 1), RelevanceGrade(A, 2))},
    {"grades": (RelevanceGrade(A, 1), RelevanceGrade(A, 1))},
    {"grades": (RelevanceGrade(A, 0),)},
    {"grades": (RelevanceGrade(A, True),)}, {"grades": (RelevanceGrade(A, -1),)},
    {"grades": (RelevanceGrade(A, 4),)}, {"grades": (RelevanceGrade(A, 1.5),)},
    {"grades": (RelevanceGrade(A, float("nan")),)},
    {"grades": (None,)}, {"grades": (RelevanceGrade(None, 1),)},
    {"ranked": (None,)}, {"ranked": (SourceRef([], "a" * 64),)},
    {"ranked": (SourceRef("chunk", []),)}, {"ranked": (SourceRef("", "a" * 64),)},
    {"ranked": (SourceRef("x" * 257, "a" * 64),)},
    {"ranked": (SourceRef("chunk/secret", "a" * 64),)},
    {"ranked": (SourceRef("含正文", "a" * 64),)},
    {"ranked": (SourceRef("chunk\n", "a" * 64),)},
    {"ranked": (SourceRef("chunk", "A" * 64),)},
    {"ranked": (SourceRef("chunk", "a" * 63),)},
])
def test_invalid_types_bounds_duplicate_or_conflicting_labels_fail_closed(changes):
    with pytest.raises(ValueError, match="^knowledge.retrieval_metrics_input_invalid$"):
        score(**changes)


def test_boundaries_are_inclusive_without_truncating_input():
    ranked = tuple(source(number) for number in range(80))
    value = score(k=80, ranked=ranked, evidence=ranked[:8], required_groups=(ranked[:16],) * 8,
                  grades=tuple(RelevanceGrade(source(number), 1) for number in range(256)))
    assert value.candidate_count == 80 and value.judged_pool_size == 256
    assert value.necessary_recall_at_k == value.evidence_coverage == value.precision_at_k == 1.0
    boundary = SourceRef("_.#-" + "a" * 252, "a" * 64)
    assert score(ranked=(boundary,), evidence=(boundary,), required_groups=((boundary,),)).mrr_at_k == 1.0


def test_inputs_and_finite_output_are_immutable_and_do_not_contain_sources():
    ranked = (C, A, B)
    before = tuple(asdict(item) for item in ranked)
    value = score(ranked=ranked)
    assert tuple(asdict(item) for item in ranked) == before
    assert value == score(ranked=ranked)
    assert "chunk_id" not in str(asdict(value)) and A.sha256 not in str(asdict(value))
    with pytest.raises(FrozenInstanceError): value.k = 2
    with pytest.raises(FrozenInstanceError): A.chunk_id = "changed"


def test_hostile_source_subclass_is_rejected_without_accessing_properties():
    class Hostile(SourceRef):
        def __getattribute__(self, name):
            raise AssertionError("unknown source properties must not be read")
    with pytest.raises(ValueError, match="knowledge.retrieval_metrics_input_invalid"):
        score(ranked=(Hostile("synthetic", "a" * 64),))
