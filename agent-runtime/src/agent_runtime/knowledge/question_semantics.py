from __future__ import annotations

import re
import unicodedata

from agent_runtime.knowledge.catalog import ARTICLE_PATTERN
from agent_runtime.knowledge.contracts import (
    ProtectedConstraintSet,
    RewriteCandidateRejection,
    RewriteCandidateValidation,
)
from agent_runtime.knowledge.errors import KnowledgeInputError

_NUMBER = re.compile(r"(?:[0-9]+(?:\.[0-9]+)?|[零〇一二三四五六七八九十百千万]{1,24})(?:%|元|万元|亿元)?")
_DATE = re.compile(r"(?:[0-9]{4}(?:年[0-9]{1,2}月[0-9]{1,2}日|[-/.][0-9]{1,2}[-/.][0-9]{1,2}))(?:以前|以后|期间|起|止|截至)?")
_DOCUMENT = re.compile(r"[^\s，。；：！？]{1,24}(?:〔[0-9]{4}〕|\[[0-9]{4}\])[0-9]{1,12}号")
_ARTICLE = re.compile(ARTICLE_PATTERN)
_NEGATIONS = ("不得", "禁止", "免税", "除外", "至少", "至多", "超过", "低于", "不", "未", "仅")
_NEGATION = re.compile("|".join(re.escape(item) for item in _NEGATIONS))


def _has_forbidden_control(value: str) -> bool:
    return any(character == "\x00" or (unicodedata.category(character) in {"Cc", "Cf"} and not character.isspace()) for character in value)


def _matches(pattern: re.Pattern[str], value: str) -> tuple[str, ...]:
    return tuple(match.group(0) for match in pattern.finditer(value))


class QuestionSemanticGuard:
    def extract(self, original_question: str) -> ProtectedConstraintSet:
        if not isinstance(original_question, str) or not original_question or _has_forbidden_control(original_question):
            raise KnowledgeInputError("knowledge.invalid_question")
        normalized = unicodedata.normalize("NFC", original_question)
        groups = (
            _matches(_NUMBER, normalized),
            _matches(_DATE, normalized),
            _matches(_DOCUMENT, normalized),
            _matches(_ARTICLE, normalized),
            _matches(_NEGATION, normalized),
        )
        if any(len(group) > 32 for group in groups) or sum(map(len, groups)) > 64:
            raise KnowledgeInputError("knowledge.invalid_question")
        if any(len(item) > 128 for group in groups for item in group):
            raise KnowledgeInputError("knowledge.invalid_question")
        return ProtectedConstraintSet(
            numbers=groups[0], dates=groups[1], document_numbers=groups[2],
            article_refs=groups[3], negations=groups[4],
        )

    def validate_candidate(
        self,
        *,
        candidate: str,
        constraints: ProtectedConstraintSet,
        max_chars: int,
    ) -> RewriteCandidateValidation:
        if not isinstance(candidate, str) or not candidate.strip():
            return RewriteCandidateValidation(accepted=False, reason=RewriteCandidateRejection.EMPTY)
        normalized = unicodedata.normalize("NFC", candidate)
        if _has_forbidden_control(normalized):
            return RewriteCandidateValidation(accepted=False, reason=RewriteCandidateRejection.CONTROL)
        if len(normalized) > max_chars:
            return RewriteCandidateValidation(accepted=False, reason=RewriteCandidateRejection.TOO_LONG)
        try:
            observed = self.extract(normalized)
        except KnowledgeInputError:
            return RewriteCandidateValidation(accepted=False, reason=RewriteCandidateRejection.INTRODUCED_CONSTRAINT)
        expected_groups = (
            constraints.numbers, constraints.dates, constraints.document_numbers,
            constraints.article_refs, constraints.negations,
        )
        observed_groups = (
            observed.numbers, observed.dates, observed.document_numbers,
            observed.article_refs, observed.negations,
        )
        if observed_groups == expected_groups:
            return RewriteCandidateValidation(accepted=True)
        if all(len(observed_item) <= len(expected_item) for observed_item, expected_item in zip(observed_groups, expected_groups)):
            return RewriteCandidateValidation(accepted=False, reason=RewriteCandidateRejection.MISSING_CONSTRAINT)
        return RewriteCandidateValidation(accepted=False, reason=RewriteCandidateRejection.INTRODUCED_CONSTRAINT)

