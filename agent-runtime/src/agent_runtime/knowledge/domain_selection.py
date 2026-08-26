from __future__ import annotations

import re
import unicodedata

from agent_runtime.knowledge.catalog import (
    ARTICLE_PATTERN,
    CATALOG_VERSION,
    INDEPENDENT_POLICY_TERMS,
    LAW_TERMS,
    TAX_ANCHORS,
)
from agent_runtime.knowledge.contracts import DomainSelection, LogicalKnowledgeDomain

_ARTICLE = re.compile(ARTICLE_PATTERN)


class DeterministicDomainSelector:
    def select(
        self,
        *,
        original_question: str,
        enabled_domains: tuple[LogicalKnowledgeDomain, ...],
    ) -> DomainSelection:
        question = unicodedata.normalize("NFC", original_question)
        if not any(term in question for term in TAX_ANCHORS):
            return DomainSelection(
                selected_domain_ids=(),
                catalog_version=CATALOG_VERSION,
                reason_codes=("no_tax_anchor",),
            )
        law = any(term in question for term in LAW_TERMS) or _ARTICLE.search(question) is not None
        independent_policy = any(term in question for term in INDEPENDENT_POLICY_TERMS)
        policy = independent_policy if law else True
        wanted = ({"tax.policy"} if policy else set()) | ({"tax.law"} if law else set())
        if policy and law:
            reason = "policy_and_law"
        elif policy:
            reason = "policy"
        else:
            reason = "law"
        selected = tuple(item.domain_id for item in enabled_domains if item.domain_id in wanted)
        return DomainSelection(
            selected_domain_ids=selected,
            catalog_version=CATALOG_VERSION,
            reason_codes=(reason,),
        )
