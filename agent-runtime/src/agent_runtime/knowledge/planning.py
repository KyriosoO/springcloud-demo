from __future__ import annotations

from agent_runtime.knowledge.contracts import (
    DomainSelection,
    KnowledgeRetrievalPlan,
    RetrievalPath,
    RetrievalPlanItem,
    RewriteResult,
)
from agent_runtime.knowledge.errors import KnowledgeInputError
from agent_runtime.knowledge.settings import KnowledgeSettings


class KnowledgeRetrievalPlanBuilder:
    def build(
        self,
        *,
        rewrite: RewriteResult,
        domains: DomainSelection,
        settings: KnowledgeSettings,
    ) -> KnowledgeRetrievalPlan:
        if not domains.selected_domain_ids:
            raise KnowledgeInputError("knowledge.plan_domains_required")
        items: list[RetrievalPlanItem] = []
        ordinal = 1
        for domain_id in domains.selected_domain_ids:
            for path in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR):
                items.append(
                    RetrievalPlanItem(
                        logical_domain_id=domain_id,
                        path=path,
                        query_text=rewrite.selected_query,
                        candidate_limit=settings.per_path_candidate_limit,
                        ordinal=ordinal,
                    )
                )
                ordinal += 1
        return KnowledgeRetrievalPlan(
            items=tuple(items),
            selected_domain_ids=domains.selected_domain_ids,
            config_version=settings.config_version,
        )

