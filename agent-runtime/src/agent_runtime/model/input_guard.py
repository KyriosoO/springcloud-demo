from __future__ import annotations

from agent_runtime.model.contracts import (
    QuestionDataClass,
    QuestionEgressDecision,
    QuestionEgressDisposition,
    QuestionEgressReasonCode,
)
from agent_runtime.model.question_policy import (
    DENY_CLASSES,
    QUESTION_EGRESS_POLICY_VERSION,
    classify_question,
    contains_forbidden_control,
    normalize_question,
)


class QuestionEgressGuard:
    __slots__ = ("_max_question_chars",)

    def __init__(self, *, max_question_chars: int = 4096) -> None:
        if not isinstance(max_question_chars, int) or isinstance(max_question_chars, bool) or max_question_chars <= 0:
            raise ValueError("model.invalid_question_limit")
        self._max_question_chars = max_question_chars

    def evaluate(self, question: str) -> QuestionEgressDecision:
        if (
            not isinstance(question, str)
            or not question
            or len(question) > self._max_question_chars
            or contains_forbidden_control(question)
        ):
            return self._denied(QuestionEgressReasonCode.INVALID_QUESTION)

        minimized = normalize_question(question)
        if not minimized:
            return self._denied(QuestionEgressReasonCode.INVALID_QUESTION)
        classes = classify_question(minimized)
        if classes & (DENY_CLASSES - {QuestionDataClass.UNKNOWN}):
            return self._denied(QuestionEgressReasonCode.SENSITIVE_INPUT)
        if QuestionDataClass.UNKNOWN in classes:
            return self._denied(QuestionEgressReasonCode.UNKNOWN_INPUT)
        if not classes.issubset({QuestionDataClass.PUBLIC_KNOWLEDGE, QuestionDataClass.GENERIC_BUSINESS}):
            return self._denied(QuestionEgressReasonCode.UNKNOWN_INPUT)
        return QuestionEgressDecision(
            disposition=QuestionEgressDisposition.ALLOWED,
            policy_version=QUESTION_EGRESS_POLICY_VERSION,
            minimized_question=minimized,
        )

    @staticmethod
    def _denied(reason: QuestionEgressReasonCode) -> QuestionEgressDecision:
        return QuestionEgressDecision(
            disposition=QuestionEgressDisposition.DENIED,
            policy_version=QUESTION_EGRESS_POLICY_VERSION,
            reason_code=reason,
        )

