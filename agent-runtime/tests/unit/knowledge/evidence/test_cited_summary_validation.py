from __future__ import annotations

from dataclasses import replace
import json
from typing import Any, cast

import pytest

from agent_runtime.capability_api.contracts import canonical_json_bytes
from agent_runtime.knowledge.evidence.cited_summary_validation import (
    CitedSummaryValidationFailureReason, CitedSummaryValidator, InvalidCitedSummary,
)
from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeCitedSummaryOutput, KnowledgeCitedSummaryPoint, KnowledgeEvidenceBundle,
    KnowledgeEvidenceLimits, KnowledgeSummaryOutput, SummaryOutcome, SummaryValidationResult,
)
from agent_runtime.knowledge.evidence.builder import DeterministicEvidenceSelector, EvidenceIntegrityVerifier
from agent_runtime.knowledge.evidence.summary_validation import (
    ExtractiveSummaryValidator, InvalidSummary, SummaryValidationFailureReason,
)
from agent_runtime.knowledge.intent_contracts import KnowledgeQueryMode
from tests.evidence_helpers import evidence_input


def _bundle() -> KnowledgeEvidenceBundle:
    source = evidence_input()
    selected = DeterministicEvidenceSelector().select(
        candidates=EvidenceIntegrityVerifier().verify(input=source), input=source,
        minimized_question="现行增值税政策是什么", limits=KnowledgeEvidenceLimits.v1(),
    )
    assert selected.bundle is not None
    return selected.bundle


def _output(*, quote: str = "税务政策正文", claim: str = "", ref: str = "e1") -> KnowledgeCitedSummaryOutput:
    return KnowledgeCitedSummaryOutput(
        outcome=SummaryOutcome.ANSWER,
        points=(KnowledgeCitedSummaryPoint(evidence_ref=ref, quote=quote, claim=claim),),
    )


def _validate(output: KnowledgeCitedSummaryOutput, mode: KnowledgeQueryMode = KnowledgeQueryMode.LOOKUP,
              *, limits: KnowledgeEvidenceLimits | None = None) -> SummaryValidationResult:
    return CitedSummaryValidator().validate(output=output, query_mode=mode, bundle=_bundle(),
                                            limits=limits or KnowledgeEvidenceLimits.minimal_v1())


def test_lookup_retains_extractive_result_shape_and_local_citation() -> None:
    checked = _validate(_output())
    assert not checked.insufficient and checked.domain_result is not None
    result = checked.domain_result
    plain = cast(dict[str, Any], json.loads(canonical_json_bytes(result)))
    assert set(result) == {"schemaVersion", "summaryType", "answerSummary", "points", "coverage"}
    assert result["schemaVersion"] == 1 and result["summaryType"] == "extractive_evidence"
    assert result["answerSummary"] == "1. 税务政策正文"
    assert set(plain["points"][0]) == {"quote", "citation"}
    assert plain["points"][0]["quote"] == "税务政策正文"


@pytest.mark.parametrize("mode", [KnowledgeQueryMode.EXPLANATION, KnowledgeQueryMode.APPLICABILITY])
def test_cited_mode_formats_one_claim_per_original_quote_without_new_result_fields(mode: KnowledgeQueryMode) -> None:
    claim = "若题述事实准确，仅按指定条款，适用条件见引文。" if mode is KnowledgeQueryMode.APPLICABILITY else "该条件见引文。"
    checked = _validate(_output(claim=claim), mode)
    assert checked.domain_result is not None
    result = checked.domain_result
    plain = cast(dict[str, Any], json.loads(canonical_json_bytes(result)))
    assert result["summaryType"] == "cited_limited_answer"
    assert result["answerSummary"] == f"1. {claim}"
    assert plain["points"][0]["quote"] == "税务政策正文"
    assert "claim" not in plain["points"][0]
    assert "claim" not in plain["points"][0]["citation"]


def test_insufficient_keeps_no_result_without_claim_or_model_text() -> None:
    result = _validate(KnowledgeCitedSummaryOutput(outcome=SummaryOutcome.INSUFFICIENT_EVIDENCE, points=()),
                       KnowledgeQueryMode.APPLICABILITY)
    assert result.insufficient and result.domain_result is None


@pytest.mark.parametrize("mode,claim,reason", [
    (KnowledgeQueryMode.LOOKUP, "不能判断", CitedSummaryValidationFailureReason.CLAIM_INVALID),
    (KnowledgeQueryMode.EXPLANATION, "", CitedSummaryValidationFailureReason.CLAIM_INVALID),
    (KnowledgeQueryMode.EXPLANATION, "  ", CitedSummaryValidationFailureReason.CLAIM_INVALID),
    (KnowledgeQueryMode.EXPLANATION, "答" * 161, CitedSummaryValidationFailureReason.CLAIM_TOO_LONG),
    (KnowledgeQueryMode.EXPLANATION, "e\u0301", CitedSummaryValidationFailureReason.CLAIM_INVALID),
    (KnowledgeQueryMode.EXPLANATION, "答\n案", CitedSummaryValidationFailureReason.CLAIM_CONTROL_CHARACTER),
    (KnowledgeQueryMode.EXPLANATION, "答\u2028案", CitedSummaryValidationFailureReason.CLAIM_CONTROL_CHARACTER),
    (KnowledgeQueryMode.EXPLANATION, "https://example.test", CitedSummaryValidationFailureReason.CLAIM_UNSAFE_REFERENCE),
    (KnowledgeQueryMode.EXPLANATION, "详见www.example.test", CitedSummaryValidationFailureReason.CLAIM_UNSAFE_REFERENCE),
    (KnowledgeQueryMode.EXPLANATION, "参考e1证据", CitedSummaryValidationFailureReason.CLAIM_UNSAFE_REFERENCE),
    (KnowledgeQueryMode.EXPLANATION, "sourceUrl自报", CitedSummaryValidationFailureReason.CLAIM_UNSAFE_REFERENCE),
    (KnowledgeQueryMode.EXPLANATION, "evidence_ref自报", CitedSummaryValidationFailureReason.CLAIM_UNSAFE_REFERENCE),
])
def test_claim_shape_and_unsafe_reference_reject_fail_closed(
    mode: KnowledgeQueryMode, claim: str, reason: CitedSummaryValidationFailureReason,
) -> None:
    with pytest.raises(InvalidCitedSummary) as raised:
        _validate(_output(claim=claim), mode)
    assert raised.value.reason is reason


def test_original_quote_ref_validation_runs_before_claim_checks() -> None:
    with pytest.raises(InvalidSummary) as raised:
        _validate(_output(quote="编造原文", claim="https://example.test"), KnowledgeQueryMode.EXPLANATION)
    assert raised.value.reason is SummaryValidationFailureReason.QUOTE_NOT_SUBSTRING
    with pytest.raises(InvalidSummary) as raised:
        _validate(_output(ref="e2", claim="https://example.test"), KnowledgeQueryMode.EXPLANATION)
    assert raised.value.reason is SummaryValidationFailureReason.UNKNOWN_EVIDENCE_REF
    repeated = KnowledgeCitedSummaryOutput(outcome=SummaryOutcome.ANSWER, points=(
        KnowledgeCitedSummaryPoint(evidence_ref="e1", quote="税务政策", claim=""),
        KnowledgeCitedSummaryPoint(evidence_ref="e1", quote="正文", claim=""),
    ))
    with pytest.raises(InvalidSummary) as raised:
        _validate(repeated)
    assert raised.value.reason is SummaryValidationFailureReason.DUPLICATE_EVIDENCE_REF


def test_multiple_claim_lines_follow_their_own_local_quotes_in_order() -> None:
    base = _bundle()
    second = replace(base.evidence[0], evidence_id="ev-second", document_id="d2",
                     chunk_id="c2", content="另一个直接原文")
    bundle = replace(base, evidence=(base.evidence[0], second))
    output = KnowledgeCitedSummaryOutput(outcome=SummaryOutcome.ANSWER, points=(
        KnowledgeCitedSummaryPoint(evidence_ref="e2", quote="另一个直接原文", claim="第二点见原文。"),
        KnowledgeCitedSummaryPoint(evidence_ref="e1", quote="税务政策正文", claim="第一点见原文。"),
    ))
    checked = CitedSummaryValidator().validate(output=output, query_mode=KnowledgeQueryMode.EXPLANATION,
                                               bundle=bundle, limits=KnowledgeEvidenceLimits.minimal_v1())
    assert checked.domain_result is not None
    plain = cast(dict[str, Any], json.loads(canonical_json_bytes(checked.domain_result)))
    assert plain["answerSummary"] == "1. 第二点见原文。\n2. 第一点见原文。"
    assert [point["quote"] for point in plain["points"]] == ["另一个直接原文", "税务政策正文"]


def test_claim_answer_must_fit_existing_result_byte_budget() -> None:
    quoted = ExtractiveSummaryValidator().validate(output=_output(), bundle=_bundle(),
                                                   limits=KnowledgeEvidenceLimits.minimal_v1())
    assert quoted.domain_result is not None
    limit = len(canonical_json_bytes(quoted.domain_result)) + 1
    with pytest.raises(InvalidCitedSummary) as raised:
        _validate(_output(claim="回答" * 70), KnowledgeQueryMode.EXPLANATION,
                  limits=replace(KnowledgeEvidenceLimits.minimal_v1(), max_domain_result_bytes=limit))
    assert raised.value.reason is CitedSummaryValidationFailureReason.RESULT_TOO_LARGE


def test_mode_and_output_type_are_request_owned() -> None:
    with pytest.raises(InvalidCitedSummary):
        CitedSummaryValidator().validate(output=_output(), query_mode=KnowledgeQueryMode.NONE,
                                         bundle=_bundle(), limits=KnowledgeEvidenceLimits.minimal_v1())
    with pytest.raises(InvalidCitedSummary):
        CitedSummaryValidator().validate(
            output=KnowledgeSummaryOutput(outcome=SummaryOutcome.INSUFFICIENT_EVIDENCE, points=()),  # type: ignore[arg-type]
            query_mode=KnowledgeQueryMode.LOOKUP, bundle=_bundle(), limits=KnowledgeEvidenceLimits.minimal_v1(),
        )


@pytest.mark.parametrize("unsupported_claim", [
    "该规定不适用。",  # Reversed negation.
    "该规定于2030年生效。",  # Invented date and effective period.
    "另一类纳税人适用该规定。",  # Wrong subject and classification.
    "适用税率为13%。",  # Invented number and rate.
])
def test_valid_shape_does_not_prove_semantic_entailment(unsupported_claim: str) -> None:
    # These claims have legal structure but no support in the fixture's quote.
    # This test only checks mechanical acceptance; it must never count them as
    # faithful or useful in the independent, source-based human answer rubric.
    checked = _validate(_output(claim=unsupported_claim), KnowledgeQueryMode.EXPLANATION)
    assert checked.domain_result is not None
    assert checked.domain_result["summaryType"] == "cited_limited_answer"
    assert checked.domain_result["answerSummary"] == f"1. {unsupported_claim}"
