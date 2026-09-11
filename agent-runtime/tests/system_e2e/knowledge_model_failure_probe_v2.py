"""Test-only rejected-structure facts. Never admit, repair or re-parse a plan."""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator
from unittest.mock import patch

from agent_runtime.knowledge import rewrite_v7
from agent_runtime.knowledge.contracts import (
    KnowledgeEvidenceRequirement, KnowledgeQuestionKind, KnowledgeRequirementKind, PlannedDomainQuery,
)
from agent_runtime.knowledge.errors import KnowledgeInputError
from agent_runtime.knowledge.evidence_requirements import valid_plan_text
from agent_runtime.model.contracts import InvalidModelOutput
from tests.system_e2e import knowledge_model_failure_probe_v1 as legacy

DETAILS = (
    "unknown", "query_count", "query_text", "search_missing_conditions", "missing_conditions",
    "terminal_state", "domains", "requirement_count", "requirement_id", "requirement_domain",
    "focus_text", "domain_coverage", "applicability_roles",
)
_PROJECT = legacy.project_failure
_VALIDATE = rewrite_v7.validate_requirement_plan_output
_REJECTED: ContextVar[tuple[KnowledgeInputError, str] | None] = ContextVar("rejected_structure_v2", default=None)


@dataclass(frozen=True, slots=True)
class FailureDiagnostic(legacy.FailureDiagnostic):
    detail: str


def rejected_detail(output: object) -> str:
    """One bounded observed violation; deliberately not an admission predicate."""
    if type(output) is not rewrite_v7.KnowledgeRequirementPlanOutput:
        return "unknown"
    missing = output.missing_conditions
    if type(missing) is not tuple or len(missing) > 3 or any(
        type(item) is not str or item not in {"subject", "taxpayer_type", "calculation_method", "applicable_period"}
        for item in missing
    ) or len(set(missing)) != len(missing):
        return "missing_conditions"
    if type(output.outcome) is not str:
        return "terminal_state"
    if output.outcome != "search":
        return "terminal_state"
    if missing:
        return "search_missing_conditions"
    queries = output.queries
    if type(queries) is not tuple or not 1 <= len(queries) <= 2:
        return "query_count"
    if any(type(q) is not PlannedDomainQuery or type(q.domain_id) is not str for q in queries):
        return "domains"
    if any(not valid_plan_text(q.query, max_chars=1024) for q in queries):
        return "query_text"
    domains = tuple(q.domain_id for q in queries)
    if len(set(domains)) != len(domains) or any(d not in {"tax.policy", "tax.law"} for d in domains):
        return "domains"
    requirements = output.evidence_requirements
    if type(requirements) is not tuple or not 1 <= len(requirements) <= 4:
        return "requirement_count"
    for ordinal, item in enumerate(requirements, 1):
        if type(item) is not KnowledgeEvidenceRequirement:
            return "unknown"
        if type(item.requirement_id) is not str or item.requirement_id != f"r{ordinal}":
            return "requirement_id"
        if type(item.domain_id) is not str or item.domain_id not in domains:
            return "requirement_domain"
        if type(item.kind) is not KnowledgeRequirementKind:
            return "unknown"
        if not valid_plan_text(item.focus, max_chars=192):
            return "focus_text"
    if {item.domain_id for item in requirements} != set(domains):
        return "domain_coverage"
    if output.question_kind is KnowledgeQuestionKind.APPLICABILITY:
        counts = Counter(item.kind for item in requirements)
        if any(counts[kind] != 1 for kind in (
            KnowledgeRequirementKind.SUBJECT_SCOPE, KnowledgeRequirementKind.RULE, KnowledgeRequirementKind.TEMPORAL_SCOPE,
        )):
            return "applicability_roles"
    return "unknown"


def _validated(output: rewrite_v7.KnowledgeRequirementPlanOutput, *, enabled_domain_ids: tuple[str, ...]) -> None:
    _REJECTED.set(None)
    try:
        _VALIDATE(output, enabled_domain_ids=enabled_domain_ids)
    except KnowledgeInputError as error:
        detail = "unknown"
        if type(error) is KnowledgeInputError:
            # Diagnosis cannot replace the original failure, even if its helper breaks.
            try:
                detail = rejected_detail(output)
                if type(detail) is not str or detail not in DETAILS:
                    detail = "unknown"
            except Exception:
                detail = "unknown"
            _REJECTED.set((error, detail))
        raise


def project_failure(error: BaseException | None) -> FailureDiagnostic:
    original = _PROJECT(error)
    recorded = _REJECTED.get()
    _REJECTED.set(None)
    detail = "unknown"
    current = error
    # Only the same rejected exception in the existing finite cause chain qualifies.
    for _ in range(8):
        if recorded is not None and current is recorded[0]:
            detail = recorded[1]
            break
        if type(current) is not InvalidModelOutput:
            break
        current = current.__cause__
    return FailureDiagnostic(original.phase, original.code, original.cause, detail)


@contextmanager
def observe_failures() -> Iterator[legacy.FailureCollector]:
    # Acquire the legacy installation lock BEFORE changing its projection function.
    with legacy.observe_failures() as collector:
        token = _REJECTED.set(None)
        try:
            with patch.object(legacy, "project_failure", project_failure), \
                    patch.object(rewrite_v7, "validate_requirement_plan_output", _validated):
                yield collector
        finally:
            _REJECTED.reset(token)
