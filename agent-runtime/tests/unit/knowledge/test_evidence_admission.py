"""Candidate-only evidence admission; old selection and real gold stay intact."""
from dataclasses import replace
import hashlib

import pytest

from agent_runtime.knowledge.evidence.admission import ScoreAwareEvidenceSelector
from agent_runtime.knowledge.evidence.builder import DeterministicEvidenceSelector, EvidenceIntegrityError, EvidenceIntegrityVerifier
from agent_runtime.knowledge.evidence.contracts import KnowledgeEvidenceLimits
from tests.requirement_evidence_helpers import requirement_input


def scored_input(scores=(0.1, 0.2, 0.3, 0.499, 0.5, 0.9), *, merged=False):
    source = requirement_input(count=len(scores), merged=merged)
    return replace(source, batch=replace(source.batch, candidates=tuple(
        replace(item, rerank_score=score) for item, score in zip(source.batch.candidates, scores, strict=True))))


def select(source, *, selector=None):
    return (selector or ScoreAwareEvidenceSelector()).select(
        candidates=EvidenceIntegrityVerifier().verify(input=source), input=source,
        minimized_question=source.original_question, limits=KnowledgeEvidenceLimits.quality_v3())


def test_optional_filter_keeps_anchors_original_ranks_threshold_and_immutable_input():
    source = scored_input()
    before = repr(source)
    chosen = select(source)
    assert chosen.sufficient
    assert [e.rank for e in chosen.bundle.evidence] == [1, 2, 3, 5, 6]
    assert chosen.bundle.coverage == select(source, selector=DeterministicEvidenceSelector()).bundle.coverage
    assert [e.rank for e in select(source, selector=DeterministicEvidenceSelector()).bundle.evidence] == list(range(1, 7))
    assert repr(source) == before
    assert ScoreAwareEvidenceSelector.VERSION == "optional-evidence-score-v1"
    assert ScoreAwareEvidenceSelector.MIN_OPTIONAL_SCORE == 0.5


@pytest.mark.parametrize("score,kept", [(0, False), (0.499999, False), (0.5, True), (1, True)])
def test_optional_score_boundary(score, kept):
    result = select(scored_input((0.9, 0.9, 0.9, score)))
    assert [e.rank for e in result.bundle.evidence] == ([1, 2, 3, 4] if kept else [1, 2, 3])


def test_low_score_merged_anchor_retains_all_requirement_opportunities():
    source = scored_input((0.0, 0.1, 0.2), merged=True)
    result = select(source)
    assert result.sufficient and len(result.bundle.evidence) == 1
    assert source.batch.candidates[0].requirement_ids == ("r1", "r2", "r3")
    assert result.bundle.evidence[0].rank == 1


def test_missing_anchor_and_empty_input_are_not_repaired():
    assert not select(scored_input((1, 1))).sufficient
    source = scored_input()
    assert not ScoreAwareEvidenceSelector().select(candidates=(), input=source,
        minimized_question=source.original_question, limits=KnowledgeEvidenceLimits.quality_v3()).sufficient


@pytest.mark.parametrize("score", [-0.1, 1.1, True, "0.9", None, float("nan"), float("inf"), -float("inf"), 10**400])
def test_invalid_scores_rejected_even_when_candidate_would_be_discarded(score):
    source = scored_input()
    verified = EvidenceIntegrityVerifier().verify(input=source)
    verified = verified[:-1] + (replace(verified[-1], rerank_score=score),)
    with pytest.raises(EvidenceIntegrityError, match="^knowledge.evidence_admission_input_invalid$"):
        ScoreAwareEvidenceSelector().select(candidates=verified, input=source,
            minimized_question=source.original_question, limits=KnowledgeEvidenceLimits.quality_v3())


@pytest.mark.parametrize("fault", ["version", "limits", "list", "item", "too_many"])
def test_incompatible_input_is_not_silently_treated_as_legacy(fault):
    source = scored_input()
    verified = EvidenceIntegrityVerifier().verify(input=source)
    limits = KnowledgeEvidenceLimits.quality_v3()
    if fault == "version": source = replace(source, quality_version=None)
    elif fault == "limits": limits = KnowledgeEvidenceLimits.v1()
    elif fault == "list": verified = list(verified)
    elif fault == "item": verified = (object(),)
    else: verified = verified * 4
    with pytest.raises(EvidenceIntegrityError):
        ScoreAwareEvidenceSelector().select(candidates=verified, input=source,
            minimized_question=source.original_question, limits=limits)


def test_total_eight_and_oversized_anchor_limits_are_preserved():
    source = scored_input((1,) * 20)
    assert len(select(source).bundle.evidence) == 8
    # Each source fits the 4096-character service contract; together the three
    # required anchors exceed the 32768-byte summary contract.
    body = "合" * 4096
    source = replace(source, batch=replace(source.batch, candidates=tuple(
        replace(item, candidate=replace(item.candidate, content=body,
            content_sha256=hashlib.sha256(body.encode()).hexdigest()))
        if item.coverage_anchor else item for item in source.batch.candidates)))
    assert not select(source).sufficient


def test_selector_has_no_request_state_and_does_not_rerank():
    selector = ScoreAwareEvidenceSelector()
    low, high = scored_input(), scored_input((0.9,) * 6)
    before = select(low, selector=selector)
    assert len(select(high, selector=selector).bundle.evidence) == 6
    assert select(low, selector=selector) == before
