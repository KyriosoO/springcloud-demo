"""Current-only reference boundaries; never rewrite questions or build queries."""
from __future__ import annotations

from dataclasses import replace
import re

from agent_runtime.knowledge.contracts import ProtectedConstraintSet
from agent_runtime.knowledge.tax_question_semantics import TaxQuestionSemanticGuard


_REFERENCE_WITH_REQUEST_PREFIX = re.compile(
    r"(?:请(?:帮我)?|帮我|麻烦(?:帮我)?)?(?:分别|同时)?"
    r"(?:查找|查询|检索|查阅|查看|对比|比较)"
    r"(?P<reference>[\u4e00-\u9fffA-Za-z]{1,24}"
    r"(?:〔[0-9]{4}〕|\[[0-9]{4}\])[0-9]{1,12}号)"
)


def _reference_body(token: str) -> str:
    match = _REFERENCE_WITH_REQUEST_PREFIX.fullmatch(token)
    # Strip once only. In particular, retain regional/issuer prefixes verbatim.
    return token if match is None else match.group("reference")


class DocumentReferenceSemanticGuard(TaxQuestionSemanticGuard):
    """Keep frozen guards intact while separating explicit lookup syntax."""

    def extract(self, original_question: str) -> ProtectedConstraintSet:
        # Validate raw types, controls, token sizes/counts before normalization.
        constraints = super().extract(original_question)
        return replace(
            constraints,
            document_numbers=tuple(_reference_body(token) for token in constraints.document_numbers),
        )
