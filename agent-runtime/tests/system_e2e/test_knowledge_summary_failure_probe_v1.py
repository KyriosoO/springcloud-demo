"""Synthetic non-live counterexamples; these do not diagnose a discarded live output."""
from dataclasses import FrozenInstanceError, asdict, replace
import json

import pytest

from agent_runtime.knowledge.evidence.contracts import KnowledgeEvidenceLimits, SummaryOutcome
from agent_runtime.knowledge.evidence.requirement_validation import (
    CoverageValidationFailureReason, InvalidRequirementCoverage, RequirementCoverageValidator,
)
from agent_runtime.knowledge.evidence.summary_validation import (
    ExtractiveSummaryValidator, InvalidSummary, SummaryValidationFailureReason,
)
from tests.requirement_evidence_helpers import bound_input, output_for
from tests.system_e2e.knowledge_summary_failure_probe_v1 import (
    COVERAGE_REASONS, EXTRACTIVE_REASONS, SummaryFailureDiagnostic, project_summary_failure,
)


FAULTS = (
    ("input_types", "coverage_input_invalid", "input_contract"),
    ("input_contract", "coverage_input_invalid", "input_contract"),
    ("bundle_binding", "coverage_bundle_invalid", "bundle_binding"),
    ("source_binding", "coverage_source_invalid", "source_binding"),
    ("insufficient_payload", "coverage_outcome_invalid", "outcome_points"),
    ("outcome_points", "coverage_outcome_invalid", "outcome_points"),
    ("coverage_ids", "coverage_ids_invalid", "coverage_ids"),
    ("point_refs", "coverage_refs_invalid", "coverage_refs"),
    ("coverage_refs", "coverage_refs_invalid", "coverage_refs"),
    ("coverage_domain", "coverage_domain_mismatch", "coverage_domain"),
    ("unused_points", "coverage_unused_points", "unused_points"),
)


def coverage_error(fault):
    _, bundle, value = bound_input()
    output = output_for(value)
    if fault == "input_types": output = None
    elif fault == "input_contract": value = replace(value, schema_version=1)
    elif fault == "bundle_binding":
        bundle = replace(bundle, question_trace=replace(bundle.question_trace, minimized_question="different"))
    elif fault == "source_binding":
        value = replace(value, evidence=(replace(value.evidence[0], content="different"), *value.evidence[1:]))
    elif fault == "insufficient_payload": output = replace(output, outcome=SummaryOutcome.INSUFFICIENT_EVIDENCE)
    elif fault == "outcome_points": output = replace(output, points=())
    elif fault == "coverage_ids": output = replace(output, coverage=tuple(reversed(output.coverage)))
    elif fault == "point_refs": output = replace(output, points=(*output.points, output.points[0]))
    elif fault == "coverage_refs":
        output = replace(output, coverage=(replace(output.coverage[0], evidence_refs=("e8",)), *output.coverage[1:]))
    elif fault == "coverage_domain":
        value = replace(value, requirements=(replace(value.requirements[0], domain_id="tax.law"), *value.requirements[1:]))
    elif fault == "unused_points":
        output = replace(output, coverage=tuple(replace(item, evidence_refs=("e1",)) for item in output.coverage))
    else: raise AssertionError(fault)
    with pytest.raises(InvalidSummary) as raised:
        RequirementCoverageValidator().validate(output=output, requirements=value.requirements, summary_input=value, bundle=bundle)
    return raised.value


@pytest.mark.parametrize("fault,expected_reason,branch", FAULTS)
def test_each_existing_coverage_rejection_classified_without_reentry(fault, expected_reason, branch):
    error = coverage_error(fault)
    trace, reason = error.__traceback__, error.reason
    assert type(error) is InvalidRequirementCoverage
    assert error.coverage_reason.value == expected_reason
    assert reason is SummaryValidationFailureReason.UNKNOWN_EVIDENCE_REF
    assert str(error) == "knowledge.invalid_summary"
    expected = SummaryFailureDiagnostic("requirement_coverage", expected_reason, branch)
    assert project_summary_failure(error) == expected
    assert project_summary_failure(error) == expected
    assert error.__traceback__ is trace and error.reason is reason
    assert set(asdict(expected)) == {"phase", "reason", "branch"}


@pytest.mark.parametrize("quote,reason", [
    ("", "quote_empty"), ("x" * 513, "quote_too_long"),
    ("synthetic\ntext", "quote_control_character"), ("synthetic non-substring", "quote_not_substring"),
])
def test_extractive_reason_distinct_and_raw_value_not_projected(quote, reason):
    _, bundle, value = bound_input()
    output = output_for(value)
    output = replace(output, points=(replace(output.points[0], quote=quote),))
    with pytest.raises(InvalidSummary) as raised:
        ExtractiveSummaryValidator().validate(output=output, bundle=bundle, limits=KnowledgeEvidenceLimits.quality_v3())
    record = project_summary_failure(raised.value)
    assert record == SummaryFailureDiagnostic("extractive_summary", reason, "quote_and_result_contract")
    encoded = json.dumps(asdict(record))
    assert "synthetic" not in encoded and "content" not in encoded


def test_domain_mismatch_is_rejected_and_not_repaired():
    _, bundle, value = bound_input()
    requirements = (replace(value.requirements[0], domain_id="tax.law"), *value.requirements[1:])
    value = replace(value, requirements=requirements)
    with pytest.raises(InvalidSummary) as raised:
        RequirementCoverageValidator().validate(output=output_for(value), requirements=requirements, summary_input=value, bundle=bundle)
    assert project_summary_failure(raised.value).branch == "coverage_domain"


def test_success_is_unchanged_and_does_not_generate_failure_record():
    _, bundle, value = bound_input()
    output = RequirementCoverageValidator().validate(output=output_for(value), requirements=value.requirements, summary_input=value, bundle=bundle)
    assert ExtractiveSummaryValidator().validate(output=output, bundle=bundle, limits=KnowledgeEvidenceLimits.quality_v3()).domain_result is not None
    assert project_summary_failure(None) == SummaryFailureDiagnostic()


def test_unknown_types_and_malicious_exception_properties_are_not_accessed():
    class Hostile(InvalidSummary):
        def __getattribute__(self, name):
            raise AssertionError("must not inspect unknown exception")
    hostile = Hostile(SummaryValidationFailureReason.QUOTE_EMPTY)
    assert project_summary_failure(hostile) == SummaryFailureDiagnostic()
    assert project_summary_failure(ValueError("synthetic secret")) == SummaryFailureDiagnostic()
    error = InvalidSummary(SummaryValidationFailureReason.QUOTE_EMPTY)
    error.reason = "synthetic secret"
    assert project_summary_failure(error) == SummaryFailureDiagnostic()


def test_reason_category_is_not_a_claim_about_actual_production_execution():
    try:
        raise InvalidSummary(SummaryValidationFailureReason.QUOTE_EMPTY)
    except InvalidSummary as error:
        assert project_summary_failure(error) == SummaryFailureDiagnostic("extractive_summary", "quote_empty", "quote_and_result_contract")
    with pytest.raises(FrozenInstanceError):
        SummaryFailureDiagnostic().phase = "changed"


def test_fixtures_cover_all_coverage_reasons_and_categories_are_exhaustive():
    assert {reason for _, reason, _ in FAULTS} == {reason.value for reason in COVERAGE_REASONS}
    assert not EXTRACTIVE_REASONS.intersection(COVERAGE_REASONS)
    assert set(SummaryValidationFailureReason) == EXTRACTIVE_REASONS
    assert set(CoverageValidationFailureReason) == set(COVERAGE_REASONS)


def test_unknown_coverage_reason_and_subclass_are_not_read_or_exposed():
    error = InvalidRequirementCoverage(CoverageValidationFailureReason.INPUT_INVALID)
    error.coverage_reason = "synthetic secret"
    assert project_summary_failure(error) == SummaryFailureDiagnostic()
    class HostileCoverage(InvalidRequirementCoverage):
        def __getattribute__(self, name):
            raise AssertionError("must not read unknown coverage exception")
    assert project_summary_failure(HostileCoverage(CoverageValidationFailureReason.INPUT_INVALID)) == SummaryFailureDiagnostic()


def test_projection_never_reenters_either_validator(monkeypatch):
    error = coverage_error("coverage_ids")
    def forbidden(*args, **kwargs):
        raise AssertionError("must not invoke validation again")
    monkeypatch.setattr(RequirementCoverageValidator, "validate", forbidden)
    monkeypatch.setattr(ExtractiveSummaryValidator, "validate", forbidden)
    assert project_summary_failure(error).branch == "coverage_ids"


def test_depth_does_not_change_typed_reason_projection():
    def nested(depth):
        if depth:
            return nested(depth - 1)
        _, bundle, value = bound_input()
        return RequirementCoverageValidator().validate(output=None, requirements=value.requirements, summary_input=value, bundle=bundle)
    with pytest.raises(InvalidSummary) as raised:
        nested(40)
    assert project_summary_failure(raised.value) == SummaryFailureDiagnostic("requirement_coverage", "coverage_input_invalid", "input_contract")


def test_decoder_success_does_not_imply_quote_validation_success():
    from agent_runtime.knowledge.evidence.summary_task_v7 import KnowledgeSummaryTaskV7
    from tests.contract.knowledge.test_summary_task_v5 import _response
    _, bundle, value = bound_input()
    raw = asdict(output_for(value))
    raw["points"][0]["quote"] = "synthetic\ntext"
    decoded = KnowledgeSummaryTaskV7.definition().parse_response(_response(json.dumps(raw)))
    validated_coverage = RequirementCoverageValidator().validate(output=decoded, requirements=value.requirements, summary_input=value, bundle=bundle)
    with pytest.raises(InvalidSummary) as raised:
        ExtractiveSummaryValidator().validate(output=validated_coverage, bundle=bundle, limits=KnowledgeEvidenceLimits.quality_v3())
    assert project_summary_failure(raised.value).reason == "quote_control_character"
