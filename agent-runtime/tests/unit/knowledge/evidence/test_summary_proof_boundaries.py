"""Characterize integrity guarantees, not semantic quality or live UAT success."""
from __future__ import annotations

from dataclasses import replace
import hashlib

import pytest

from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeEvidenceBundle,
    KnowledgeEvidenceLimits,
    KnowledgeSummaryOutput,
    KnowledgeSummaryPoint,
    SummaryOutcome,
)
from agent_runtime.knowledge.evidence.summary_validation import ExtractiveSummaryValidator
from tests.unit.knowledge.evidence.test_summary_validation_reasons import _bundle


def _synthetic_bundle(question: str) -> KnowledgeEvidenceBundle:
    base = _bundle()
    contents = ("测试服务甲是提供甲类设施的活动。", "测试服务甲属于测试类别乙。")
    evidence = tuple(
        replace(base.evidence[0], evidence_id=f"synthetic-ev-{ordinal}",
                rank=ordinal, chunk_id=f"synthetic-chunk-{ordinal}", content=content,
                content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest())
        for ordinal, content in enumerate(contents, 1)
    )
    return replace(base, evidence=evidence, question_trace=replace(
        base.question_trace, original_question=question, selected_query=question,
        minimized_question=question))


def _validate(bundle: KnowledgeEvidenceBundle, refs: tuple[int, ...]):
    output = KnowledgeSummaryOutput(outcome=SummaryOutcome.ANSWER, points=tuple(
        KnowledgeSummaryPoint(evidence_ref=f"e{ref}", quote=bundle.evidence[ref - 1].content)
        for ref in refs))
    return ExtractiveSummaryValidator().validate(
        output=output, bundle=bundle, limits=KnowledgeEvidenceLimits.v1())


@pytest.mark.parametrize("question", [
    "测试类别乙中的服务甲如何定义？",
    "请分别说明测试服务甲的定义和所属分类依据。",
])
@pytest.mark.parametrize("refs", [(1,), (1, 2)])
def test_valid_quotes_do_not_prove_explicit_question_coverage(question, refs):
    # The existing validator guarantees grounding/shape, not question semantics.
    # One quote passes integrity even for the explicit two-part question.
    validated = _validate(_synthetic_bundle(question), refs)
    assert not validated.insufficient and validated.domain_result is not None
    assert len(validated.domain_result["points"]) == len(refs)


def test_retrieval_coverage_is_not_coverage_of_final_citations():
    bundle = _synthetic_bundle("测试政策分类与法律依据分别是什么？")
    bundle = replace(bundle, evidence=(bundle.evidence[0], replace(
        bundle.evidence[1], domain_ids=("tax.law",))), coverage=replace(
            bundle.coverage, selected_domain_ids=("tax.policy", "tax.law"),
            represented_domain_ids=("tax.policy", "tax.law"), missing_domain_ids=()))
    validated = _validate(bundle, (1,))
    assert validated.domain_result is not None
    coverage = validated.domain_result["coverage"]
    assert coverage["retrievalComplete"] is True
    assert coverage["domainCoverageComplete"] is True
    assert tuple(coverage["representedDomainIds"]) == ("tax.policy", "tax.law")
    assert {domain for point in validated.domain_result["points"]
            for domain in point["citation"]["domainIds"]} == {"tax.policy"}


def test_model_insufficient_remains_no_result_despite_complete_retrieval():
    bundle = _synthetic_bundle("请说明测试服务甲的全部必要条件。")
    validated = ExtractiveSummaryValidator().validate(
        output=KnowledgeSummaryOutput(outcome=SummaryOutcome.INSUFFICIENT_EVIDENCE, points=()),
        bundle=bundle, limits=KnowledgeEvidenceLimits.v1())
    assert validated.insufficient and validated.domain_result is None
