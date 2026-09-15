"""Request-local contracts for the minimal Knowledge flow; not a legacy plan."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from agent_runtime.knowledge.catalog import build_tax_domain_catalog
from agent_runtime.model.contracts import (
    InvalidModelOutput,
    ModelInputDenied,
    QuestionEgressDisposition,
    QuestionEgressReasonCode,
)
from agent_runtime.model.input_guard import QuestionEgressGuard


class KnowledgeQueryMode(StrEnum):
    LOOKUP = "lookup"
    EXPLANATION = "explanation"
    APPLICABILITY = "applicability"
    NONE = "none"


class KnowledgeIntentOutcome(StrEnum):
    SEARCH = "search"
    CLARIFICATION_REQUIRED = "clarification_required"
    UNSUPPORTED = "unsupported"


class KnowledgeMissingCondition(StrEnum):
    SUBJECT = "subject"
    PERIOD = "period"
    TAXPAYER_TYPE = "taxpayer_type"
    CALCULATION_METHOD = "calculation_method"


def validate_enabled_domain_ids(domains: tuple[str, ...]) -> tuple[str, ...]:
    """Bind to a code-owned, ordered catalog subset, never a model-owned list."""
    known = tuple(item.domain_id for item in build_tax_domain_catalog().domains)
    if (
        type(domains) is not tuple
        or not 1 <= len(domains) <= 2
        or any(type(item) is not str or item not in known for item in domains)
        or domains != tuple(item for item in known if item in domains)
    ):
        raise ValueError("knowledge.enabled_domains_invalid")
    return domains


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeQueryIntentInput:
    """Prepare safe NFC Q once; later stages must reuse this complete value."""

    minimized_question: str = field(repr=False)

    def __post_init__(self) -> None:
        decision = QuestionEgressGuard().evaluate(self.minimized_question)
        if decision.disposition is not QuestionEgressDisposition.ALLOWED:
            code = (
                "knowledge.invalid_question"
                if decision.reason_code is QuestionEgressReasonCode.INVALID_QUESTION
                else "knowledge.question_denied"
            )
            raise ModelInputDenied(code)
        question = decision.minimized_question
        if question is None or not 1 <= len(question) <= 1024:
            raise ModelInputDenied("knowledge.invalid_question")
        try:
            question.encode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise ModelInputDenied("knowledge.invalid_question") from exc
        object.__setattr__(self, "minimized_question", question)


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeQueryIntent:
    query_mode: KnowledgeQueryMode
    selected_domain_ids: tuple[str, ...]
    missing_conditions: tuple[KnowledgeMissingCondition, ...]
    outcome: KnowledgeIntentOutcome

    def __post_init__(self) -> None:
        if (
            not isinstance(self.query_mode, KnowledgeQueryMode)
            or not isinstance(self.outcome, KnowledgeIntentOutcome)
            or type(self.selected_domain_ids) is not tuple
            or type(self.missing_conditions) is not tuple
            or len(self.missing_conditions) > 4
            or any(not isinstance(item, KnowledgeMissingCondition) for item in self.missing_conditions)
            or len(set(self.missing_conditions)) != len(self.missing_conditions)
        ):
            raise InvalidModelOutput("knowledge.invalid_query_intent")
        if self.outcome is KnowledgeIntentOutcome.SEARCH:
            try:
                validate_enabled_domain_ids(self.selected_domain_ids)
            except ValueError as exc:
                raise InvalidModelOutput("knowledge.invalid_query_intent") from exc
            valid = self.query_mode is not KnowledgeQueryMode.NONE and not self.missing_conditions
        elif self.outcome is KnowledgeIntentOutcome.CLARIFICATION_REQUIRED:
            valid = (
                self.query_mode is not KnowledgeQueryMode.NONE
                and not self.selected_domain_ids
                and bool(self.missing_conditions)
            )
        else:
            valid = (
                self.query_mode is KnowledgeQueryMode.NONE
                and not self.selected_domain_ids
                and not self.missing_conditions
            )
        if not valid:
            raise InvalidModelOutput("knowledge.invalid_query_intent")
