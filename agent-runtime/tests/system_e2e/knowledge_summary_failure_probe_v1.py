"""Pure, test-only projection AFTER summary rejection; never parse or repair output."""
from dataclasses import dataclass

from agent_runtime.knowledge.evidence.requirement_validation import RequirementCoverageValidator
from agent_runtime.knowledge.evidence.summary_validation import (
    ExtractiveSummaryValidator, InvalidSummary, SummaryValidationFailureReason,
)

# Identities and static sites only. Future live use must freeze these source files.
# Never read frame locals/globals, messages, exception args, paths or model text.
_COVERAGE = RequirementCoverageValidator.validate.__code__
_EXTRACTIVE = ExtractiveSummaryValidator.validate.__code__
COVERAGE_SITES = {
    27: "input_types", 31: "input_contract", 41: "bundle_binding",
    52: "source_binding", 55: "insufficient_payload", 58: "outcome_points",
    60: "coverage_ids", 63: "point_refs", 71: "coverage_refs_or_domain",
    74: "unused_points",
}


@dataclass(frozen=True, slots=True)
class SummaryFailureDiagnostic:
    phase: str = "unknown"
    reason: str = "unknown"
    branch: str = "unknown"


def project_summary_failure(error: BaseException | None) -> SummaryFailureDiagnostic:
    """No IO/hooks, cause traversal or validator re-entry; unknown data stays unknown."""
    if type(error) is not InvalidSummary or type(error.reason) is not SummaryValidationFailureReason:
        return SummaryFailureDiagnostic()
    phase, branch = "unknown", "unknown"
    trace = error.__traceback__
    for _ in range(32):
        if trace is None:
            break
        code = trace.tb_frame.f_code
        if code is _COVERAGE and trace.tb_lineno in COVERAGE_SITES:
            phase, branch = "requirement_coverage", COVERAGE_SITES[trace.tb_lineno]
        elif code is _EXTRACTIVE:
            phase, branch = "extractive_summary", "quote_and_result_contract"
        trace = trace.tb_next
    return SummaryFailureDiagnostic(phase, error.reason.value, branch)
