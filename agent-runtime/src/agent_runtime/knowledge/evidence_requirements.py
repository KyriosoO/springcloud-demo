"""Request-local proof obligations: structural checks, never intent inference."""
from __future__ import annotations

from collections import Counter
import re
import unicodedata

from agent_runtime.knowledge.catalog import build_tax_domain_catalog
from agent_runtime.knowledge.contracts import (
    KNOWLEDGE_QUALITY_VERSION_V3, KnowledgeEvidenceRequirement,
    KnowledgeQuestionKind, KnowledgeRequirementKind,
)
from agent_runtime.knowledge.errors import KnowledgeInputError
from agent_runtime.knowledge.question_semantics import QuestionSemanticGuard
from agent_runtime.knowledge.tax_question_semantics import TAX_CATEGORY_CONDITIONS
from agent_runtime.model.contracts import QuestionEgressDisposition
from agent_runtime.model.input_guard import QuestionEgressGuard

_DOMAINS = frozenset(domain.domain_id for domain in build_tax_domain_catalog().domains)
_RATIO_VALUE = r"(?:[0-9]+(?:\.[0-9]+)?|[零〇一二三四五六七八九十百千万]+(?:点[零〇一二三四五六七八九]+)?)"
_RATIO = re.compile(rf"(?:百分之|千分之|万分之){_RATIO_VALUE}|{_RATIO_VALUE}[%％‰‱]")


def protected_ratio_tokens(text: str) -> tuple[str, ...]:
    return tuple(_RATIO.findall(text))


def valid_plan_text(value: object, *, max_chars: int) -> bool:
    return (
        type(value) is str and bool(value.strip()) and len(value) <= max_chars
        and unicodedata.normalize("NFC", value) == value
        and not any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in value)
    )


def validate_evidence_requirements(
    *, question_kind: KnowledgeQuestionKind | None,
    requirements: tuple[KnowledgeEvidenceRequirement, ...], domain_ids: tuple[str, ...],
) -> None:
    """Validate search requirements identically at planning/ranking/Evidence boundaries."""
    if (
        type(question_kind) is not KnowledgeQuestionKind
        or type(domain_ids) is not tuple or not 1 <= len(domain_ids) <= 2
        or any(type(domain) is not str or domain not in _DOMAINS for domain in domain_ids)
        or len(set(domain_ids)) != len(domain_ids)
        or type(requirements) is not tuple or not 1 <= len(requirements) <= 4
    ):
        raise KnowledgeInputError("knowledge.invalid_evidence_requirements")
    for ordinal, item in enumerate(requirements, 1):
        if (
            type(item) is not KnowledgeEvidenceRequirement
            or type(item.requirement_id) is not str or item.requirement_id != f"r{ordinal}"
            or type(item.domain_id) is not str or item.domain_id not in domain_ids
            or type(item.kind) is not KnowledgeRequirementKind
            or not valid_plan_text(item.focus, max_chars=192)
        ):
            raise KnowledgeInputError("knowledge.invalid_evidence_requirements")
    if {item.domain_id for item in requirements} != set(domain_ids):
        raise KnowledgeInputError("knowledge.invalid_evidence_requirements")
    if question_kind is KnowledgeQuestionKind.APPLICABILITY:
        counts = Counter(item.kind for item in requirements)
        if any(counts[kind] != 1 for kind in (
            KnowledgeRequirementKind.SUBJECT_SCOPE, KnowledgeRequirementKind.RULE,
            KnowledgeRequirementKind.TEMPORAL_SCOPE,
        )):
            raise KnowledgeInputError("knowledge.invalid_evidence_requirements")


def validate_plan_requirements(
    *, quality_version: str | None, question_kind: KnowledgeQuestionKind | None,
    requirements: tuple[KnowledgeEvidenceRequirement, ...], domain_ids: tuple[str, ...],
) -> None:
    if quality_version == KNOWLEDGE_QUALITY_VERSION_V3:
        validate_evidence_requirements(
            question_kind=question_kind, requirements=requirements, domain_ids=domain_ids,
        )
    elif question_kind is not None or type(requirements) is not tuple or requirements:
        raise KnowledgeInputError("knowledge.requirement_version_mismatch")


def validate_requirement_focuses(
    *, original_question: str, requirements: tuple[KnowledgeEvidenceRequirement, ...],
    semantic_guard: QuestionSemanticGuard,
) -> None:
    """A focus may omit constraints, but cannot invent or multiply protected tokens."""
    original = semantic_guard.extract(original_question)
    guard = QuestionEgressGuard()
    for item in requirements:
        if guard.evaluate(item.focus).disposition is QuestionEgressDisposition.DENIED:
            raise KnowledgeInputError("knowledge.requirement_focus_denied")
        focus = semantic_guard.extract(item.focus)
        groups = (
            (focus.numbers, original.numbers), (focus.dates, original.dates),
            (focus.document_numbers, original.document_numbers),
            (focus.article_refs, original.article_refs), (focus.negations, original.negations),
            (protected_ratio_tokens(item.focus), protected_ratio_tokens(original_question)),
        )
        if any(Counter(found) - Counter(allowed) for found, allowed in groups) or any(
            item.focus.count(term) > original_question.count(term) for term in TAX_CATEGORY_CONDITIONS
        ):
            raise KnowledgeInputError("knowledge.requirement_focus_introduced_constraint")
