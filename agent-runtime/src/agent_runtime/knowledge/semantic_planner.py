"""The V3 implementation of the existing request-scoped rewrite stage."""
from __future__ import annotations

import re

from agent_runtime.knowledge.contracts import (
    KNOWLEDGE_QUALITY_VERSION, RewriteCandidate, RewriteCandidateSource, RewriteMode,
    RewriteResult, RewriteStageKind, RewriteStageResult,
)
from agent_runtime.knowledge.errors import KnowledgeInputError
from agent_runtime.knowledge.question_semantics import QuestionSemanticGuard
from agent_runtime.knowledge.rewrite_v3 import (
    KnowledgeSemanticPlanInput, KnowledgeSemanticPlanOutput,
)
from agent_runtime.model.context import ModelCallContextAccessor
from agent_runtime.model.contracts import ModelProviderFailureKind, ModelTaskDefinition, QuestionEgressDisposition, StructuredModelGateway
from agent_runtime.model.input_guard import QuestionEgressGuard

_EXPLICIT_CONDITIONS = (
    "一般纳税人", "小规模纳税人", "一般计税", "简易计税",
)
_RATE_TOPICS = ("征收率", "税率")
_RATIO_MARKERS = ("%", "％", "‰", "‱", "百分之", "千分之", "万分之")
_RATIO_VALUE = r"(?:[0-9]+(?:\.[0-9]+)?|[零〇一二三四五六七八九十百千万]+(?:点[零〇一二三四五六七八九]+)?)"
_RATIO = re.compile(rf"(?:百分之|千分之|万分之){_RATIO_VALUE}|{_RATIO_VALUE}[%％‰‱]")


class KnowledgeSemanticPlanner:
    def __init__(
        self, *, gateway: StructuredModelGateway, context: ModelCallContextAccessor,
        enabled_domain_ids: tuple[str, ...], max_query_chars: int = 1024,
        definition: ModelTaskDefinition[KnowledgeSemanticPlanInput, KnowledgeSemanticPlanOutput],
    ) -> None:
        self._gateway, self._context = gateway, context
        self._domains = enabled_domain_ids
        self._max_chars = max_query_chars
        self._guard, self._semantic = QuestionEgressGuard(), QuestionSemanticGuard()
        self._definition = definition

    async def rewrite(self, *, original_question: str, timeout_s: float) -> RewriteStageResult:
        del timeout_s  # Capability phase and ModelGateway enforce their bounded deadlines.
        try:
            constraints = self._semantic.extract(original_question)
        except KnowledgeInputError:
            return RewriteStageResult(kind=RewriteStageKind.INPUT_INVALID)
        decision = self._guard.evaluate(original_question)
        if decision.disposition is QuestionEgressDisposition.DENIED:
            return RewriteStageResult(
                kind=RewriteStageKind.QUESTION_DENIED, policy_version=decision.policy_version,
                reason_code=decision.reason_code.value if decision.reason_code else "unknown_input",
            )
        assert decision.minimized_question is not None
        try:
            result = await self._gateway.generate(
                definition=self._definition,
                input=KnowledgeSemanticPlanInput(
                    minimized_question=decision.minimized_question, enabled_domain_ids=self._domains,
                ),
                context=self._context.require_current(),
            )
        except TimeoutError:
            return RewriteStageResult(kind=RewriteStageKind.TIMEOUT)
        except Exception:
            return RewriteStageResult(kind=RewriteStageKind.FAILURE)
        output = result.output
        if output is None:
            return RewriteStageResult(
                kind=RewriteStageKind.TIMEOUT if result.failure_kind is ModelProviderFailureKind.PROVIDER_TIMEOUT
                else RewriteStageKind.FAILURE,
            )
        if output.outcome == "clarification_required":
            return RewriteStageResult(kind=RewriteStageKind.CLARIFICATION_REQUIRED)
        if any(item.domain_id not in self._domains for item in output.queries):
            return RewriteStageResult(kind=RewriteStageKind.FAILURE)
        plans = tuple(item for domain in self._domains for item in output.queries if item.domain_id == domain)
        if plans and any((term in original_question) != any(term in item.query for item in plans)
                         for term in _RATE_TOPICS):
            return RewriteStageResult(kind=RewriteStageKind.FAILURE)
        per_query = _EXPLICIT_CONDITIONS + (
            _RATE_TOPICS if any(marker in original_question for marker in _RATIO_MARKERS) else ()
        )
        for item in plans:
            if (
                not self._semantic.validate_candidate(
                    candidate=item.query, constraints=constraints, max_chars=self._max_chars,
                ).accepted
                or self._guard.evaluate(item.query).disposition is QuestionEgressDisposition.DENIED
                # The historical numeric guard does not bind Unicode ratio units.
                # Preserve the entire value/unit token, not just marker presence.
                or _RATIO.findall(item.query) != _RATIO.findall(original_question)
                or any((term in original_question) != (term in item.query) for term in per_query)
            ):
                return RewriteStageResult(kind=RewriteStageKind.FAILURE)
        return RewriteStageResult(
            kind=RewriteStageKind.SUCCESS,
            rewrite=RewriteResult(
                original_question=original_question,
                selected_query=plans[0].query if plans else decision.minimized_question,
                candidates=tuple(RewriteCandidate(text=item.query, source=RewriteCandidateSource.MODEL, ordinal=i)
                                 for i, item in enumerate(plans, 1)),
                mode=RewriteMode.MODEL, question_policy_version=decision.policy_version,
                question_egress_denied=False, domain_queries=plans, plan_version=KNOWLEDGE_QUALITY_VERSION,
            ),
        )
