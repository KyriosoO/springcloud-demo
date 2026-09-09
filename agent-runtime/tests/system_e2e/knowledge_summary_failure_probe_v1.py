"""Pure, test-only projection AFTER summary rejection; never parse or repair output."""
from dataclasses import dataclass

from agent_runtime.knowledge.evidence.requirement_validation import (
    CoverageValidationFailureReason, InvalidRequirementCoverage,
)
from agent_runtime.knowledge.evidence.summary_validation import (
    InvalidSummary, SummaryValidationFailureReason,
)

# Rule categories, not proof of a production throw site. No stack inspection.
COVERAGE_REASONS = {
    CoverageValidationFailureReason.INPUT_INVALID: "input_contract",
    CoverageValidationFailureReason.BUNDLE_INVALID: "bundle_binding",
    CoverageValidationFailureReason.SOURCE_INVALID: "source_binding",
    CoverageValidationFailureReason.OUTCOME_INVALID: "outcome_points",
    CoverageValidationFailureReason.IDS_INVALID: "coverage_ids",
    CoverageValidationFailureReason.REFS_INVALID: "coverage_refs",
    CoverageValidationFailureReason.DOMAIN_MISMATCH: "coverage_domain",
    CoverageValidationFailureReason.UNUSED_POINTS: "unused_points",
}
EXTRACTIVE_REASONS = frozenset({
    SummaryValidationFailureReason.OUTCOME_POINTS_MISMATCH,
    SummaryValidationFailureReason.POINT_COUNT_INVALID,
    SummaryValidationFailureReason.UNKNOWN_EVIDENCE_REF,
    SummaryValidationFailureReason.DUPLICATE_EVIDENCE_REF,
    SummaryValidationFailureReason.QUOTE_EMPTY,
    SummaryValidationFailureReason.QUOTE_TOO_LONG,
    SummaryValidationFailureReason.QUOTE_CONTROL_CHARACTER,
    SummaryValidationFailureReason.QUOTE_NOT_SUBSTRING,
    SummaryValidationFailureReason.ANSWER_TOO_LARGE,
    SummaryValidationFailureReason.RESULT_TOO_LARGE,
})


@dataclass(frozen=True, slots=True)
class SummaryFailureDiagnostic:
    phase: str = "unknown"
    reason: str = "unknown"
    branch: str = "unknown"


def project_summary_failure(error: BaseException | None) -> SummaryFailureDiagnostic:
    """Classify typed reasons only; never inspect payloads or re-enter validators."""
    if type(error) is InvalidRequirementCoverage:
        reason = error.coverage_reason
        if type(reason) is CoverageValidationFailureReason and reason in COVERAGE_REASONS:
            return SummaryFailureDiagnostic("requirement_coverage", reason.value, COVERAGE_REASONS[reason])
        return SummaryFailureDiagnostic()
    if type(error) is not InvalidSummary or type(error.reason) is not SummaryValidationFailureReason:
        return SummaryFailureDiagnostic()
    if error.reason in EXTRACTIVE_REASONS:
        return SummaryFailureDiagnostic("extractive_summary", error.reason.value, "quote_and_result_contract")
    return SummaryFailureDiagnostic()
