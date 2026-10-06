"""Summary9 claim checks after the existing exact Evidence/quote validation."""
from __future__ import annotations

import re
import unicodedata
from enum import StrEnum

from agent_runtime.capability_api.contracts import canonical_json_bytes, freeze_json_object
from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeCitedSummaryOutput,
    KnowledgeCitedSummaryPoint,
    KnowledgeEvidenceBundle,
    KnowledgeEvidenceLimits,
    SummaryOutcome,
    SummaryValidationResult,
)
from agent_runtime.knowledge.evidence.summary_validation import (
    ExtractiveSummaryValidator,
)
from agent_runtime.knowledge.intent_contracts import KnowledgeQueryMode


_PSEUDO_REF = re.compile(r"(?<![A-Za-z0-9_])e[1-8](?![A-Za-z0-9_])", re.IGNORECASE)
_REFERENCE_FIELD_NAMES = ("evidence_ref", "evidenceid", "sourceurl", "source_url", "citation")
_URL_MARKERS = ("http://", "https://", "www.")


class CitedSummaryValidationFailureReason(StrEnum):
    CLAIM_INVALID = "claim_invalid"
    CLAIM_TOO_LONG = "claim_too_long"
    CLAIM_CONTROL_CHARACTER = "claim_control_character"
    CLAIM_UNSAFE_REFERENCE = "claim_unsafe_reference"
    ANSWER_TOO_LARGE = "answer_too_large"
    RESULT_TOO_LARGE = "result_too_large"


class InvalidCitedSummary(ValueError):
    def __init__(self, reason: CitedSummaryValidationFailureReason) -> None:
        super().__init__("knowledge.invalid_summary")
        self.reason = reason


class CitedSummaryValidator:
    def __init__(self, quote_validator: ExtractiveSummaryValidator | None = None) -> None:
        self._quote_validator = quote_validator or ExtractiveSummaryValidator()

    def validate(
        self,
        *,
        output: KnowledgeCitedSummaryOutput,
        query_mode: KnowledgeQueryMode,
        bundle: KnowledgeEvidenceBundle,
        limits: KnowledgeEvidenceLimits,
    ) -> SummaryValidationResult:
        if (
            type(output) is not KnowledgeCitedSummaryOutput
            or type(output.outcome) is not SummaryOutcome
            or type(output.points) is not tuple
            or any(type(point) is not KnowledgeCitedSummaryPoint
                   or type(point.evidence_ref) is not str
                   or type(point.quote) is not str
                   or type(point.claim) is not str for point in output.points)
            or type(query_mode) is not KnowledgeQueryMode
            or query_mode is KnowledgeQueryMode.NONE
        ):
            raise InvalidCitedSummary(CitedSummaryValidationFailureReason.CLAIM_INVALID)

        # Keep the original ref/quote/bytes checks in front of every claim check.
        checked = self._quote_validator.validate(output=output, bundle=bundle, limits=limits)
        if checked.insufficient:
            return checked
        if checked.domain_result is None:
            raise InvalidCitedSummary(CitedSummaryValidationFailureReason.CLAIM_INVALID)

        lines: list[str] = []
        for ordinal, point in enumerate(output.points, 1):
            claim = point.claim
            if query_mode is KnowledgeQueryMode.LOOKUP:
                if claim != "":
                    raise InvalidCitedSummary(CitedSummaryValidationFailureReason.CLAIM_INVALID)
                # The original validator has already normalized the quote.
                lines.append(f"{ordinal}. {unicodedata.normalize('NFC', point.quote)}")
                continue
            if not claim or not claim.strip():
                raise InvalidCitedSummary(CitedSummaryValidationFailureReason.CLAIM_INVALID)
            if len(claim) > 160:
                raise InvalidCitedSummary(CitedSummaryValidationFailureReason.CLAIM_TOO_LONG)
            if unicodedata.normalize("NFC", claim) != claim:
                raise InvalidCitedSummary(CitedSummaryValidationFailureReason.CLAIM_INVALID)
            if any(unicodedata.category(character).startswith("C")
                   or unicodedata.category(character) in {"Zl", "Zp"} for character in claim):
                raise InvalidCitedSummary(CitedSummaryValidationFailureReason.CLAIM_CONTROL_CHARACTER)
            folded = claim.casefold()
            if (any(marker in folded for marker in _URL_MARKERS + _REFERENCE_FIELD_NAMES)
                    or _PSEUDO_REF.search(claim) is not None):
                raise InvalidCitedSummary(CitedSummaryValidationFailureReason.CLAIM_UNSAFE_REFERENCE)
            lines.append(f"{ordinal}. {claim}")

        answer = "\n".join(lines)
        if len(answer) > 3072:
            raise InvalidCitedSummary(CitedSummaryValidationFailureReason.ANSWER_TOO_LARGE)
        result = dict(checked.domain_result)
        result["answerSummary"] = answer
        result["summaryType"] = (
            "extractive_evidence" if query_mode is KnowledgeQueryMode.LOOKUP
            else "cited_limited_answer"
        )
        if len(canonical_json_bytes(result)) > limits.max_domain_result_bytes:
            raise InvalidCitedSummary(CitedSummaryValidationFailureReason.RESULT_TOO_LARGE)
        return SummaryValidationResult(
            domain_result=freeze_json_object(result, max_bytes=limits.max_domain_result_bytes,
                                             max_depth=6, max_collection_items=256),
            insufficient=False,
        )
