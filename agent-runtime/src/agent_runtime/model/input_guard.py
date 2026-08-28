from __future__ import annotations

import re
from collections.abc import Mapping

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


BUSINESS_QUESTION_EGRESS_POLICY_VERSION = "business-question-egress-v2"
_SLOT_ID = re.compile(r"slot-[1-9][0-9]{0,5}")
_BUSINESS_ANCHOR = re.compile(r"(?:员工|交易|employee|transaction)", re.IGNORECASE)
_EMPLOYEE_NAME_CUE = re.compile(
    r"(?:"
    r"姓(?:氏)?(?:为|是)?\s*(?:[\u4e00-\u9fff]{1,2}|protected-ref\(slot-[1-9][0-9]{0,5}\))"
    r"|(?:[\u4e00-\u9fff]{1,2}|protected-ref\(slot-[1-9][0-9]{0,5}\))姓"
    r"|(?:员工姓名|姓名|名叫)\s*(?:为|是|中?包含|含有)?\s*"
    r"(?:[\u4e00-\u9fff]{1,4}|protected-ref\(slot-[1-9][0-9]{0,5}\))"
    r")"
)
_EXPLICIT_SENSITIVE_CLASSES = DENY_CLASSES - {QuestionDataClass.UNKNOWN}


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

    def is_business_question(self, question: str) -> bool:
        return (
            isinstance(question, str)
            and bool(question)
            and _has_business_admission_cue(question)
        )

    def evaluate_business(
        self,
        question: str,
        *,
        protected_values: Mapping[str, object] | None = None,
    ) -> QuestionEgressDecision:
        if (
            not isinstance(question, str)
            or not question
            or len(question) > self._max_question_chars
            or contains_forbidden_control(question)
        ):
            return self._business_denied(QuestionEgressReasonCode.INVALID_QUESTION)
        minimized = normalize_question(question)
        values = dict(protected_values or {})
        if len(values) > 16 or any(_SLOT_ID.fullmatch(slot_id) is None for slot_id in values):
            return self._business_denied(QuestionEgressReasonCode.INVALID_QUESTION)
        redacted = minimized
        for slot_id, raw_value in sorted(values.items()):
            if (
                not isinstance(raw_value, str)
                or not raw_value
                or len(raw_value) > 128
                or redacted.count(raw_value) != 1
                or contains_forbidden_control(raw_value)
            ):
                return self._business_denied(QuestionEgressReasonCode.INVALID_QUESTION)
            value_classes = classify_question(raw_value)
            if value_classes & (
                _EXPLICIT_SENSITIVE_CLASSES
                - {
                    QuestionDataClass.PERSONAL_IDENTIFIER,
                    QuestionDataClass.EMPLOYEE_IDENTIFIER,
                    QuestionDataClass.TRANSACTION_IDENTIFIER,
                    QuestionDataClass.CONTACT,
                }
            ):
                return self._business_denied(QuestionEgressReasonCode.SENSITIVE_INPUT)
            redacted = redacted.replace(raw_value, f"protected-ref({slot_id})", 1)
        classification_input = redacted
        for slot_id in values:
            classification_input = classification_input.replace(
                f"protected-ref({slot_id})",
                "",
            )
        classes = classify_question(classification_input)
        if classes & _EXPLICIT_SENSITIVE_CLASSES:
            return self._business_denied(QuestionEgressReasonCode.SENSITIVE_INPUT)
        if not _has_business_admission_cue(redacted):
            return self._business_denied(QuestionEgressReasonCode.UNKNOWN_INPUT)
        return QuestionEgressDecision(
            disposition=QuestionEgressDisposition.ALLOWED,
            policy_version=BUSINESS_QUESTION_EGRESS_POLICY_VERSION,
            minimized_question=redacted,
        )

    @staticmethod
    def _denied(reason: QuestionEgressReasonCode) -> QuestionEgressDecision:
        return QuestionEgressDecision(
            disposition=QuestionEgressDisposition.DENIED,
            policy_version=QUESTION_EGRESS_POLICY_VERSION,
            reason_code=reason,
        )

    @staticmethod
    def _business_denied(reason: QuestionEgressReasonCode) -> QuestionEgressDecision:
        return QuestionEgressDecision(
            disposition=QuestionEgressDisposition.DENIED,
            policy_version=BUSINESS_QUESTION_EGRESS_POLICY_VERSION,
            reason_code=reason,
        )


def _has_business_admission_cue(question: str) -> bool:
    return bool(_BUSINESS_ANCHOR.search(question) or _EMPLOYEE_NAME_CUE.search(question))
