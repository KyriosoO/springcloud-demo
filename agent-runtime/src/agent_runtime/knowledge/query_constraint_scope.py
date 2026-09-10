"""Check domain queries against declared requirements, not inferred user intent."""
from __future__ import annotations

from collections import Counter

from agent_runtime.knowledge.contracts import (
    KnowledgeEvidenceRequirement, PlannedDomainQuery, ProtectedConstraintSet,
)
from agent_runtime.knowledge.errors import KnowledgeInputError
from agent_runtime.knowledge.evidence_requirements import (
    protected_ratio_tokens, validate_requirement_focuses,
)
from agent_runtime.knowledge.question_semantics import QuestionSemanticGuard
from agent_runtime.knowledge.tax_question_semantics import TAX_CATEGORY_CONDITIONS
from agent_runtime.model.contracts import QuestionEgressDisposition
from agent_runtime.model.input_guard import QuestionEgressGuard

_RATE_TOPICS = ("征收率", "税率")
_RATIO_MARKERS = ("%", "％", "‰", "‱", "百分之", "千分之", "万分之")


def _groups(value: ProtectedConstraintSet, text: str) -> tuple[tuple[str, ...], ...]:
    return (
        value.numbers, value.dates, value.document_numbers,
        value.article_refs, value.negations, protected_ratio_tokens(text),
    )


def _expected_tokens(
    original: tuple[str, ...], declarations: tuple[tuple[tuple[str, ...], ...], ...],
) -> tuple[tuple[str, ...], ...]:
    per_domain: list[Counter[str]] = []
    for focuses in declarations:
        maximum: Counter[str] = Counter()
        for tokens in focuses:
            maximum |= Counter(tokens)
        per_domain.append(maximum)
    assigned: Counter[str] = Counter()
    for maximum in per_domain:
        assigned += maximum
    unassigned = Counter(original) - assigned
    expected: list[tuple[str, ...]] = []
    for maximum in per_domain:
        remaining = maximum + unassigned
        ordered: list[str] = []
        for token in original:
            if remaining[token] > 0:
                ordered.append(token)
                remaining[token] -= 1
        expected.append(tuple(ordered))
    return tuple(expected)


def _expected_terms(
    original: str, focuses: tuple[tuple[str, ...], ...], terms: tuple[str, ...],
) -> tuple[frozenset[str], ...]:
    allowed = frozenset(term for term in terms if term in original)
    per_domain = tuple(frozenset(term for term in terms if any(term in text for text in group))
                       for group in focuses)
    assigned = frozenset().union(*per_domain)
    if assigned - allowed:
        raise KnowledgeInputError("knowledge.query_scope_mismatch")
    return tuple(group | (allowed - assigned) for group in per_domain)


def validate_scoped_queries(
    *, original_question: str, queries: tuple[PlannedDomainQuery, ...],
    requirements: tuple[KnowledgeEvidenceRequirement, ...],
    semantic_guard: QuestionSemanticGuard, max_chars: int,
) -> None:
    """Called only after the exact V7 plan/requirement shape has been validated."""
    # 不信任模型声明：先核对原问子集与敏感值，再计算本域及未分配条件。
    validate_requirement_focuses(
        original_question=original_question, requirements=requirements, semantic_guard=semantic_guard,
    )
    original = _groups(semantic_guard.extract(original_question), original_question)
    focuses = tuple(tuple(item.focus for item in requirements if item.domain_id == query.domain_id)
                    for query in queries)
    declarations = tuple(tuple(_groups(semantic_guard.extract(text), text) for text in group)
                         for group in focuses)
    expected = tuple(_expected_tokens(tokens, tuple(tuple(focus[i] for focus in group)
                                                    for group in declarations))
                     for i, tokens in enumerate(original))
    categories = _expected_terms(original_question, focuses, TAX_CATEGORY_CONDITIONS)
    topics = _expected_terms(original_question, focuses, _RATE_TOPICS)
    ratio_present = any(marker in original_question for marker in _RATIO_MARKERS)
    guard = QuestionEgressGuard()
    for index, query in enumerate(queries):
        constraints = ProtectedConstraintSet(
            numbers=expected[0][index], dates=expected[1][index],
            document_numbers=expected[2][index], article_refs=expected[3][index],
            negations=expected[4][index],
        )
        if (
            guard.evaluate(query.query).disposition is QuestionEgressDisposition.DENIED
            or not semantic_guard.validate_candidate(
                candidate=query.query, constraints=constraints, max_chars=max_chars,
            ).accepted
            or protected_ratio_tokens(query.query) != expected[5][index]
            or frozenset(term for term in TAX_CATEGORY_CONDITIONS if term in query.query) != categories[index]
            or (ratio_present and frozenset(term for term in _RATE_TOPICS if term in query.query) != topics[index])
        ):
            raise KnowledgeInputError("knowledge.query_scope_mismatch")
    if any((term in original_question) != any(term in item.query for item in queries) for term in _RATE_TOPICS):
        raise KnowledgeInputError("knowledge.query_scope_mismatch")
