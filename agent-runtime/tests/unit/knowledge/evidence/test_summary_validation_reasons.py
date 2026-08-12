from __future__ import annotations

from dataclasses import replace

import pytest

from agent_runtime.knowledge.evidence.builder import DeterministicEvidenceSelector, EvidenceIntegrityVerifier
from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeEvidence,
    KnowledgeEvidenceBundle,
    KnowledgeEvidenceLimits,
    KnowledgeSummaryOutput,
    KnowledgeSummaryPoint,
    SummaryOutcome,
)
from agent_runtime.knowledge.evidence.summary_validation import (
    ExtractiveSummaryValidator,
    InvalidSummary,
    SummaryValidationFailureReason,
)
from tests.evidence_helpers import evidence_input


def _bundle() -> KnowledgeEvidenceBundle:
    source = evidence_input()
    selection = DeterministicEvidenceSelector().select(
        candidates=EvidenceIntegrityVerifier().verify(input=source),
        input=source,
        minimized_question="现行增值税政策是什么",
        limits=KnowledgeEvidenceLimits.v1(),
    )
    assert selection.bundle is not None
    return selection.bundle


def _output(*points: KnowledgeSummaryPoint, outcome: SummaryOutcome = SummaryOutcome.ANSWER) -> KnowledgeSummaryOutput:
    return KnowledgeSummaryOutput(outcome=outcome, points=points)


def _assert_reason(
    output: KnowledgeSummaryOutput,
    reason: SummaryValidationFailureReason,
    *,
    bundle: KnowledgeEvidenceBundle | None = None,
    limits: KnowledgeEvidenceLimits | None = None,
) -> None:
    with pytest.raises(InvalidSummary, match="^knowledge.invalid_summary$") as raised:
        ExtractiveSummaryValidator().validate(
            output=output,
            bundle=bundle or _bundle(),
            limits=limits or KnowledgeEvidenceLimits.v1(),
        )
    assert raised.value.reason is reason
    assert str(raised.value) == "knowledge.invalid_summary"


def test_outcome_and_point_count_reasons_are_finite() -> None:
    _assert_reason(
        _output(
            KnowledgeSummaryPoint(evidence_ref="e1", quote="税务政策正文"),
            outcome=SummaryOutcome.INSUFFICIENT_EVIDENCE,
        ),
        SummaryValidationFailureReason.OUTCOME_POINTS_MISMATCH,
    )
    _assert_reason(_output(), SummaryValidationFailureReason.POINT_COUNT_INVALID)


def test_reference_reasons_are_distinct() -> None:
    _assert_reason(
        _output(KnowledgeSummaryPoint(evidence_ref="e2", quote="税务政策正文")),
        SummaryValidationFailureReason.UNKNOWN_EVIDENCE_REF,
    )
    _assert_reason(
        _output(
            KnowledgeSummaryPoint(evidence_ref="e1", quote="税务政策"),
            KnowledgeSummaryPoint(evidence_ref="e1", quote="正文"),
        ),
        SummaryValidationFailureReason.DUPLICATE_EVIDENCE_REF,
    )


@pytest.mark.parametrize(
    ("quote", "reason", "limits"),
    (
        ("", SummaryValidationFailureReason.QUOTE_EMPTY, KnowledgeEvidenceLimits.v1()),
        (
            "税务政策",
            SummaryValidationFailureReason.QUOTE_TOO_LONG,
            replace(KnowledgeEvidenceLimits.v1(), max_quote_chars=2),
        ),
        ("税\n务", SummaryValidationFailureReason.QUOTE_CONTROL_CHARACTER, KnowledgeEvidenceLimits.v1()),
        ("不存在的片段", SummaryValidationFailureReason.QUOTE_NOT_SUBSTRING, KnowledgeEvidenceLimits.v1()),
    ),
)
def test_quote_reasons_are_distinct(
    quote: str,
    reason: SummaryValidationFailureReason,
    limits: KnowledgeEvidenceLimits,
) -> None:
    _assert_reason(
        _output(KnowledgeSummaryPoint(evidence_ref="e1", quote=quote)),
        reason,
        limits=limits,
    )


def test_answer_and_result_size_reasons_are_distinct() -> None:
    base = _bundle()
    quote = "税" * 512
    evidence = tuple(
        replace(
            base.evidence[0],
            evidence_id=f"ev-{ordinal}",
            document_id=f"d{ordinal}",
            chunk_id=f"c{ordinal}",
            content=quote,
        )
        for ordinal in range(1, 8)
    )
    large_bundle = replace(base, evidence=evidence)
    points = tuple(
        KnowledgeSummaryPoint(evidence_ref=f"e{ordinal}", quote=quote)
        for ordinal in range(1, 8)
    )
    _assert_reason(
        _output(*points),
        SummaryValidationFailureReason.ANSWER_TOO_LARGE,
        bundle=large_bundle,
        limits=replace(KnowledgeEvidenceLimits.v1(), max_summary_points=8),
    )
    _assert_reason(
        _output(KnowledgeSummaryPoint(evidence_ref="e1", quote="税务政策正文")),
        SummaryValidationFailureReason.RESULT_TOO_LARGE,
        limits=replace(KnowledgeEvidenceLimits.v1(), max_domain_result_bytes=1),
    )


def test_valid_summary_behavior_is_unchanged() -> None:
    result = ExtractiveSummaryValidator().validate(
        output=_output(KnowledgeSummaryPoint(evidence_ref="e1", quote="税务政策正文")),
        bundle=_bundle(),
        limits=KnowledgeEvidenceLimits.v1(),
    )

    assert not result.insufficient
    assert result.domain_result is not None
    assert result.domain_result["answerSummary"] == "1. 税务政策正文"


def test_reason_enum_contains_only_the_documented_values() -> None:
    assert {item.value for item in SummaryValidationFailureReason} == {
        "outcome_points_mismatch",
        "point_count_invalid",
        "unknown_evidence_ref",
        "duplicate_evidence_ref",
        "quote_empty",
        "quote_too_long",
        "quote_control_character",
        "quote_not_substring",
        "answer_too_large",
        "result_too_large",
    }
