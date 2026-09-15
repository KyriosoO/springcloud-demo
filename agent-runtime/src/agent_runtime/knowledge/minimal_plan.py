"""DR-KFLOW-203: request-local original-question plan, not a legacy rewrite plan."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Mapping

from agent_runtime.knowledge.catalog import CATALOG_VERSION
from agent_runtime.knowledge.contracts import RetrievalPath, RetrievalPlanItem
from agent_runtime.knowledge.intent_contracts import (
    KnowledgeIntentOutcome, KnowledgeQueryIntent, KnowledgeQueryIntentInput,
    KnowledgeQueryMode, validate_enabled_domain_ids,
)
from agent_runtime.knowledge.retrieval.es_adapter import PROFILE_BY_DOMAIN


MINIMAL_VERSION = "knowledge-minimal-v1"


@dataclass(frozen=True, slots=True, kw_only=True)
class MinimalRetrievalSettings:
    """Only narrowing controls; no environment reads or production activation."""

    enabled_domain_ids: tuple[str, ...] = ("tax.policy", "tax.law")
    min_partial_candidates: int = 3
    retrieval_timeout_s: float = 20.0
    config_version: str = MINIMAL_VERSION

    def __post_init__(self) -> None:
        validate_enabled_domain_ids(self.enabled_domain_ids)
        if (
            self.config_version != MINIMAL_VERSION
            or type(self.min_partial_candidates) is not int
            or not 3 <= self.min_partial_candidates <= 20
            or type(self.retrieval_timeout_s) not in (int, float)
            or not math.isfinite(self.retrieval_timeout_s)
            or not 0 < self.retrieval_timeout_s <= 20
        ):
            raise ValueError("knowledge.minimal_config_invalid")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> MinimalRetrievalSettings:
        if set(raw) - {"enabled_domain_ids", "min_partial_candidates", "retrieval_timeout_s", "config_version"}:
            raise ValueError("knowledge.minimal_config_invalid")
        domains = raw.get("enabled_domain_ids", ("tax.policy", "tax.law"))
        minimum = raw.get("min_partial_candidates", 3)
        timeout = raw.get("retrieval_timeout_s", 20.0)
        version = raw.get("config_version", MINIMAL_VERSION)
        if (type(domains) not in (list, tuple) or not isinstance(minimum, int)
                or not isinstance(timeout, (int, float)) or not isinstance(version, str)):
            raise ValueError("knowledge.minimal_config_invalid")
        if not isinstance(domains, (list, tuple)) or any(type(item) is not str for item in domains):
            raise ValueError("knowledge.minimal_config_invalid")
        return cls(enabled_domain_ids=tuple(domains), min_partial_candidates=minimum,
                   retrieval_timeout_s=timeout, config_version=version)


def _items(question: str, domains: tuple[str, ...]) -> tuple[RetrievalPlanItem, ...]:
    return tuple(RetrievalPlanItem(logical_domain_id=domain, path=path, query_text=question,
        candidate_limit=20, ordinal=index * 2 + offset)
        for index, domain in enumerate(domains)
        for offset, path in enumerate((RetrievalPath.KEYWORD, RetrievalPath.VECTOR), start=1))


@dataclass(frozen=True, slots=True, kw_only=True)
class MinimalKnowledgeRetrievalPlan:
    original_question: str = field(repr=False)
    query_mode: KnowledgeQueryMode
    selected_domain_ids: tuple[str, ...]
    settings: MinimalRetrievalSettings
    items: tuple[RetrievalPlanItem, ...] = field(repr=False)
    profile_bindings: tuple[tuple[str, str], ...]
    catalog_version: str = CATALOG_VERSION
    schema_version: int = 3

    def __post_init__(self) -> None:
        self.validate(self.settings)

    def validate(self, settings: MinimalRetrievalSettings) -> None:
        validate_enabled_domain_ids(self.selected_domain_ids)
        if (
            type(self.settings) is not MinimalRetrievalSettings or self.settings != settings
            or type(self.schema_version) is not int or self.schema_version != 3
            or self.catalog_version != CATALOG_VERSION
            or not isinstance(self.query_mode, KnowledgeQueryMode) or self.query_mode is KnowledgeQueryMode.NONE
            or any(domain not in settings.enabled_domain_ids for domain in self.selected_domain_ids)
            or KnowledgeQueryIntentInput(minimized_question=self.original_question).minimized_question != self.original_question
            or type(self.items) is not tuple or self.items != _items(self.original_question, self.selected_domain_ids)
            or any(type(item.ordinal) is not int or type(item.candidate_limit) is not int
                   or not isinstance(item.path, RetrievalPath) for item in self.items)
            or self.profile_bindings != tuple((domain, PROFILE_BY_DOMAIN[domain]) for domain in self.selected_domain_ids)
        ):
            raise ValueError("knowledge.minimal_plan_invalid")


class MinimalKnowledgePlanBuilder:
    def build(self, *, question: KnowledgeQueryIntentInput, intent: KnowledgeQueryIntent,
              settings: MinimalRetrievalSettings) -> MinimalKnowledgeRetrievalPlan:
        if intent.outcome is not KnowledgeIntentOutcome.SEARCH:
            raise ValueError("knowledge.minimal_plan_requires_search")
        return MinimalKnowledgeRetrievalPlan(original_question=question.minimized_question,
            query_mode=intent.query_mode, selected_domain_ids=intent.selected_domain_ids, settings=settings,
            items=_items(question.minimized_question, intent.selected_domain_ids),
            profile_bindings=tuple((domain, PROFILE_BY_DOMAIN[domain]) for domain in intent.selected_domain_ids))
