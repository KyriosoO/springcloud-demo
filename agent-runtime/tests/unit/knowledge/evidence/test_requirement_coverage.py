from dataclasses import replace
import json

import pytest

from agent_runtime.knowledge.contracts import KnowledgeRequirementKind
from agent_runtime.knowledge.evidence.builder import EvidenceIntegrityError, EvidenceIntegrityVerifier
from agent_runtime.knowledge.evidence.contracts import KnowledgeEvidenceLimits, KnowledgeSummaryOutput, SummaryOutcome, SummaryRequirementCoverage
from agent_runtime.knowledge.evidence.requirement_validation import RequirementCoverageValidator
from agent_runtime.knowledge.evidence.summary_task_v6 import requirement_summary_input_json
from agent_runtime.knowledge.evidence.summary_validation import ExtractiveSummaryValidator, InvalidSummary
from tests.requirement_evidence_helpers import bound_input, output_for, requirement_input, select


def validate(output, source, bundle, value):
    return RequirementCoverageValidator().validate(output=output, requirements=source.evidence_requirements, summary_input=value, bundle=bundle)


def test_valid_full_coverage_reuses_unchanged_extractive_and_public_result():
    source, bundle, value = bound_input()
    checked = validate(output_for(value), source, bundle, value)
    assert type(checked) is KnowledgeSummaryOutput
    result = ExtractiveSummaryValidator().validate(output=checked, bundle=bundle, limits=KnowledgeEvidenceLimits.quality_v3())
    assert not result.insufficient and result.domain_result["schemaVersion"] == 1
    assert "requirements" not in result.domain_result and len(result.domain_result["points"]) == 3


def test_one_quote_can_cover_multiple_requirements_without_repeating_point():
    source, bundle, value = bound_input(requirement_input(count=1, merged=True))
    assert len(bundle.evidence) == 1
    assert len(validate(output_for(value, merged=True), source, bundle, value).points) == 1


def test_multiple_quotes_can_jointly_declare_requirement_and_none_unused():
    source, bundle, value = bound_input()
    output = output_for(value)
    output = replace(output, coverage=tuple(replace(item, evidence_refs=("e1", "e2", "e3")) for item in output.coverage))
    assert validate(output, source, bundle, value).points == output.points


@pytest.mark.parametrize("fault", ["old_output", "missing", "extra", "reorder", "duplicate", "unknown_ref", "unused_point", "undeclared_point", "duplicate_refs", "refs_list", "point_duplicate", "quote_type", "wrong_domain", "input_requirement", "schema_bool", "input_order", "body", "hash", "source_id", "chunk", "metadata", "insufficient_nonempty"])
def test_wrong_binding_or_coverage_never_becomes_insufficient(fault):
    source, bundle, value = bound_input()
    output = output_for(value)
    if fault == "old_output": output = KnowledgeSummaryOutput(outcome=output.outcome, points=output.points)
    elif fault == "missing": output = replace(output, coverage=output.coverage[:-1])
    elif fault == "extra": output = replace(output, coverage=output.coverage + (SummaryRequirementCoverage(requirement_id="r4", evidence_refs=("e1",)),))
    elif fault == "reorder": output = replace(output, coverage=tuple(reversed(output.coverage)))
    elif fault == "duplicate": output = replace(output, coverage=(output.coverage[0],) * 3)
    elif fault in {"unknown_ref", "duplicate_refs", "refs_list", "unused_point"}:
        refs = ("e8",) if fault == "unknown_ref" else ("e1", "e1") if fault == "duplicate_refs" else ["e1"] if fault == "refs_list" else ("e1",)
        output = replace(output, coverage=tuple(replace(item, evidence_refs=refs) for item in output.coverage))
    elif fault == "undeclared_point": output = replace(output, points=output.points[:-1])
    elif fault == "point_duplicate": output = replace(output, points=(output.points[0],) * 3)
    elif fault == "quote_type": output = replace(output, points=(replace(output.points[0], quote=None),) + output.points[1:])
    elif fault == "wrong_domain":
        reqs = (replace(source.evidence_requirements[0], domain_id="tax.law"),) + source.evidence_requirements[1:]
        source, value = replace(source, evidence_requirements=reqs), replace(value, requirements=reqs)
    elif fault == "input_requirement": value = replace(value, requirements=(replace(value.requirements[0], focus="不同需求"),) + value.requirements[1:])
    elif fault == "schema_bool": value = replace(value, schema_version=True)
    elif fault == "input_order": value = replace(value, evidence=tuple(reversed(value.evidence)))
    elif fault == "body": value = replace(value, evidence=(replace(value.evidence[0], content="另一原文"),) + value.evidence[1:])
    elif fault in {"hash", "source_id", "chunk"}:
        changes = {"content_sha256": "b" * 64} if fault == "hash" else {"evidence_id": "ev-wrong"} if fault == "source_id" else {"chunk_id": "other"}
        bundle = replace(bundle, evidence=(replace(bundle.evidence[0], **changes),) + bundle.evidence[1:])
    elif fault == "metadata": value = replace(value, evidence=(replace(value.evidence[0], title="另一个标题"),) + value.evidence[1:])
    elif fault == "insufficient_nonempty": output = replace(output, outcome=SummaryOutcome.INSUFFICIENT_EVIDENCE)
    with pytest.raises(InvalidSummary): validate(output, source, bundle, value)


def test_policy_omitted_document_metadata_is_not_restored_or_required():
    source, bundle, value = bound_input()
    value = replace(value, evidence=tuple(replace(item, domain_ids=None, title=None, document_number=None, written_date=None, material_type=None) for item in value.evidence))
    assert all(set(item) == {"evidence_ref", "content"} for item in json.loads(requirement_summary_input_json(value))["evidence"])
    validate(output_for(value), source, bundle, value)


@pytest.mark.parametrize("quote", ["", "不存在的原文", "字" * 513, "合成\n正文"])
def test_coverage_does_not_replace_original_substring_and_length_validator(quote):
    source, bundle, value = bound_input()
    output = output_for(value)
    checked = validate(replace(output, points=(replace(output.points[0], quote=quote),) + output.points[1:]), source, bundle, value)
    with pytest.raises(InvalidSummary):
        ExtractiveSummaryValidator().validate(output=checked, bundle=bundle, limits=KnowledgeEvidenceLimits.quality_v3())


def test_semantic_counterexample_is_not_falsely_claimed_detectable_by_local_coverage():
    source, bundle, value = bound_input(requirement_input(count=1, merged=True))
    # The synthetic text states no category, applicable rule or effective date.
    # It passes structural source checks, but a human semantic rubric must fail.
    checked = validate(output_for(value, merged=True), source, bundle, value)
    assert not ExtractiveSummaryValidator().validate(output=checked, bundle=bundle, limits=KnowledgeEvidenceLimits.quality_v3()).insufficient
    assert "生效" not in checked.points[0].quote


@pytest.mark.parametrize("fault", ["unknown", "duplicate_label", "wrong_domain", "duplicate_assignment", "unmarked", "false_anchor", "list", "order"])
def test_invalid_ranking_labels_fail_integrity(fault):
    source = requirement_input()
    items = list(source.batch.candidates)
    if fault == "unknown": items[0] = replace(items[0], requirement_ids=("r4",))
    elif fault == "duplicate_label": items[0] = replace(items[0], requirement_ids=("r1", "r1"))
    elif fault == "duplicate_assignment": items[1] = replace(items[1], requirement_ids=("r1",))
    elif fault == "wrong_domain": items[0] = replace(items[0], domain_ids=("tax.law",))
    elif fault == "unmarked": items[0] = replace(items[0], coverage_anchor=False)
    elif fault == "false_anchor": items[0] = replace(items[0], requirement_ids=())
    elif fault == "list": items[0] = replace(items[0], requirement_ids=["r1"])
    elif fault == "order": items[0] = replace(items[0], requirement_ids=("r2", "r1"))
    with pytest.raises(EvidenceIntegrityError):
        select(replace(source, batch=replace(source.batch, candidates=tuple(items))))


def test_missing_requirement_anchor_is_insufficient_not_invalid():
    source = requirement_input(count=2)
    assert len(EvidenceIntegrityVerifier().verify(input=source)) == 2
    assert not select(source).sufficient


def test_four_anchors_and_eight_same_parent_limit_preserve_new_budget():
    source = requirement_input(count=9)
    reqs = source.evidence_requirements + (replace(source.evidence_requirements[0], requirement_id="r4", kind=KnowledgeRequirementKind.CONSTRAINT),)
    items = tuple(replace(item, requirement_ids=("r4",), coverage_anchor=True) if item.rank == 4 else item for item in source.batch.candidates)
    result = select(replace(source, evidence_requirements=reqs, batch=replace(source.batch, candidates=items)))
    assert len(result.bundle.evidence) == 8 and [item.rank for item in result.bundle.evidence] == list(range(1, 9))
    assert KnowledgeEvidenceLimits.quality_v3() == KnowledgeEvidenceLimits.quality_v2()


def test_maximal_payload_includes_requirements_and_exact_boundary_for_mandatory_anchor():
    from tests.retrieval_helpers import candidate
    source = requirement_input(count=4)
    reqs = source.evidence_requirements + (replace(source.evidence_requirements[0], requirement_id="r4", kind=KnowledgeRequirementKind.CONSTRAINT),)
    items = tuple(replace(item, candidate=candidate(chunk=f"c{item.rank}", content="字" * 3000)) if item.rank < 4
                  else replace(item, requirement_ids=("r4",), coverage_anchor=True) for item in source.batch.candidates)
    source = replace(source, evidence_requirements=reqs, batch=replace(source.batch, candidates=items))
    _, bundle, value = bound_input(source)
    assert bundle.maximal_summary_input_bytes == len(requirement_summary_input_json(value).encode())
    # Four legal <=4096-character sources jointly approach the unchanged limit.
    padding = 32768 - bundle.maximal_summary_input_bytes
    item = source.batch.candidates[-1]
    large = replace(item, candidate=candidate(chunk="c4", content=item.candidate.content + "字" * (padding // 3) + "x" * (padding % 3)))
    source = replace(source, batch=replace(source.batch, candidates=items[:3] + (large,)))
    assert select(source).bundle.maximal_summary_input_bytes == 32768
    large = replace(large, candidate=candidate(chunk="c4", content=large.candidate.content + "x"))
    assert not select(replace(source, batch=replace(source.batch, candidates=items[:3] + (large,)))).sufficient


def test_wrong_limits_fail_closed_without_factory_identity_requirement():
    with pytest.raises(EvidenceIntegrityError): select(requirement_input(), limits=KnowledgeEvidenceLimits.v1())
    assert select(requirement_input(), limits=replace(KnowledgeEvidenceLimits.quality_v3())).sufficient
