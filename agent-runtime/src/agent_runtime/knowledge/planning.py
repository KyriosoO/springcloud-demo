from __future__ import annotations

from agent_runtime.knowledge.contracts import (
    DomainSelection,
    KNOWLEDGE_QUALITY_VERSIONS,
    KNOWLEDGE_QUALITY_VERSION_V3,
    KnowledgeRetrievalPlan,
    RetrievalPath,
    RetrievalPlanItem,
    RewriteMode,
    RewriteResult,
)
from agent_runtime.knowledge.errors import KnowledgeInputError
from agent_runtime.knowledge.evidence_requirements import valid_plan_text, validate_plan_requirements
from agent_runtime.knowledge.settings import KnowledgeSettings
from agent_runtime.model.contracts import QuestionEgressDisposition
from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.observation import record_plan


class KnowledgeRetrievalPlanBuilder:
    def __init__(self, *, preserve_original_keyword: bool = False) -> None:
        if type(preserve_original_keyword) is not bool:
            raise ValueError("knowledge.invalid_query_representation")
        self._preserve_original_keyword = preserve_original_keyword

    def _original_keyword_query(self, rewrite: RewriteResult, maximum: int) -> str | None:
        if not self._preserve_original_keyword:
            return None
        if (
            rewrite.plan_version != KNOWLEDGE_QUALITY_VERSION_V3
            or rewrite.mode is not RewriteMode.MODEL
            or rewrite.question_egress_denied is not False
        ):
            raise KnowledgeInputError("knowledge.invalid_query_representation")
        decision = QuestionEgressGuard().evaluate(rewrite.original_question)
        question = decision.minimized_question
        if (decision.disposition is not QuestionEgressDisposition.ALLOWED
            or question is None or not valid_plan_text(question, max_chars=4096)):
            raise KnowledgeInputError("knowledge.invalid_query_representation")
        # Choose before retrieval; never truncate or retry a long original question.
        return question if len(question) <= maximum else None

    def build(
        self,
        *,
        rewrite: RewriteResult,
        domains: DomainSelection,
        settings: KnowledgeSettings,
    ) -> KnowledgeRetrievalPlan:
        if not domains.selected_domain_ids:
            raise KnowledgeInputError("knowledge.plan_domains_required")
        validate_plan_requirements(
            quality_version=rewrite.plan_version, question_kind=rewrite.question_kind,
            requirements=rewrite.evidence_requirements, domain_ids=domains.selected_domain_ids,
        )
        queries = {item.domain_id: item.query for item in rewrite.domain_queries}
        if rewrite.plan_version is not None and (
            (rewrite.plan_version not in KNOWLEDGE_QUALITY_VERSIONS and rewrite.plan_version != KNOWLEDGE_QUALITY_VERSION_V3)
            or len(queries) != len(rewrite.domain_queries)
            or tuple(queries) != domains.selected_domain_ids
            or not set(queries).issubset(settings.enabled_domain_ids)
        ):
            raise KnowledgeInputError("knowledge.invalid_semantic_plan")
        original_keyword_query = self._original_keyword_query(rewrite, settings.max_retrieval_query_chars)
        items: list[RetrievalPlanItem] = []
        ordinal = 1
        for domain_id in domains.selected_domain_ids:
            for path in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR):
                items.append(
                    RetrievalPlanItem(
                        logical_domain_id=domain_id,
                        path=path,
                        query_text=(original_keyword_query if path is RetrievalPath.KEYWORD and original_keyword_query is not None
                                    else queries[domain_id] if rewrite.plan_version else rewrite.selected_query),
                        candidate_limit=settings.per_path_candidate_limit,
                        ordinal=ordinal,
                    )
                )
                ordinal += 1
        plan = KnowledgeRetrievalPlan(
            items=tuple(items),
            selected_domain_ids=domains.selected_domain_ids,
            config_version=settings.config_version,
            quality_version=rewrite.plan_version,
            question_kind=rewrite.question_kind,
            evidence_requirements=rewrite.evidence_requirements,
            original_keyword_query=original_keyword_query,
        )
        record_plan(
            plan_type="knowledge_retrieval_plan",
            source="runtime_after_rewrite",
            validation_status="accepted",
            # Preserve the original observation contract, not every internal field.
            plan={
                "items": plan.items, "selected_domain_ids": plan.selected_domain_ids,
                "config_version": plan.config_version, "quality_version": plan.quality_version,
            },
        )
        return plan
