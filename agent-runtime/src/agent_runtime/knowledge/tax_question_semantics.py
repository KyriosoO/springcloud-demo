"""Separate protected tax categories from quantities; not an intent resolver."""
from __future__ import annotations

from dataclasses import replace
from typing import Final
import unicodedata

from agent_runtime.knowledge.contracts import ProtectedConstraintSet
from agent_runtime.knowledge.question_semantics import QuestionSemanticGuard

TAX_CATEGORY_CONDITIONS: Final = (
    "一般纳税人", "小规模纳税人", "一般计税", "简易计税",
)


class TaxQuestionSemanticGuard(QuestionSemanticGuard):
    """Current planner only: category preservation remains a separate check."""

    def extract(self, original_question: str) -> ProtectedConstraintSet:
        constraints = super().extract(original_question)
        numeric_text = unicodedata.normalize("NFC", original_question)
        for condition in TAX_CATEGORY_CONDITIONS:
            # Keep separators: removing a phrase could join adjacent quantities.
            numeric_text = numeric_text.replace(condition, " " * len(condition))
        numbers = super().extract(numeric_text).numbers
        # Dates, references and negations always come from the untouched input.
        return replace(constraints, numbers=numbers)
