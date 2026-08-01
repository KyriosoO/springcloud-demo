from __future__ import annotations

from agent_runtime.knowledge.contracts import (
    DomainSelection,
    RewriteCandidate,
    RewriteCandidateSource,
    RewriteMode,
    RewriteResult,
)
from agent_runtime.knowledge.planning import KnowledgeRetrievalPlanBuilder
from agent_runtime.knowledge.settings import KnowledgeSettings


def test_plan_has_keyword_and_vector_per_domain_without_physical_fields() -> None:
    rewrite = RewriteResult(
        original_question="税务政策和法律",
        selected_query="税务政策和法律",
        candidates=(RewriteCandidate(text="税务政策和法律", source=RewriteCandidateSource.ORIGINAL_FALLBACK, ordinal=1),),
        mode=RewriteMode.ORIGINAL_FALLBACK,
        question_policy_version="question-egress-v1",
        question_egress_denied=False,
    )
    settings = KnowledgeSettings.from_env(
        {"AGENT_KNOWLEDGE_ENABLED": "true", "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,tax.law"}
    )
    plan = KnowledgeRetrievalPlanBuilder().build(
        rewrite=rewrite,
        domains=DomainSelection(
            selected_domain_ids=("tax.policy", "tax.law"),
            catalog_version="tax-domain-catalog-v1",
            reason_codes=("both",),
        ),
        settings=settings,
    )

    assert tuple((item.logical_domain_id, item.path.value) for item in plan.items) == (
        ("tax.policy", "keyword"), ("tax.policy", "vector"),
        ("tax.law", "keyword"), ("tax.law", "vector"),
    )
    assert all(not hasattr(item, "index") and not hasattr(item, "url") for item in plan.items)
