from types import SimpleNamespace

import pytest

from agent_runtime.knowledge.contracts import PlannedDomainQuery, RewriteStageKind
from agent_runtime.knowledge.rewrite_v3 import KnowledgeRewriteTaskV3, KnowledgeSemanticPlanOutput
from agent_runtime.knowledge.semantic_planner import KnowledgeSemanticPlanner


@pytest.mark.parametrize("question, queries, accepted", [
    ("增值税住宿服务分类与税率", ("增值税住宿服务生活服务", "住宿服务税率"), True),
    ("增值税住宿服务分类与税率", ("增值税住宿服务生活服务",), False),
    ("增值税住宿服务分类与税率", ("增值税住宿服务生活服务", "增值税住宿服务规定"), False),
    ("增值税住宿服务分类", ("增值税住宿服务生活服务", "住宿服务税率"), False),
    ("增值税住宿服务征收率", ("增值税住宿服务生活服务", "住宿服务税率"), False),
    ("住宿服务6%税率", ("住宿服务6%分类", "住宿服务6%税率"), False),
    ("住宿服务百分之六税率", ("住宿服务百分之六分类", "住宿服务百分之六税率"), False),
    ("住宿服务6%税率", ("住宿服务6%税率分类", "住宿服务6%税率"), True),
    ("一般纳税人住宿服务分类与税率", ("住宿服务分类", "一般纳税人住宿服务税率"), False),
    ("2026年增值税住宿服务分类与税率", ("2026年增值税住宿服务分类", "2026年住宿服务税率"), True),
    ("住宿服务分类与税率", ("住宿服务生活服务", "住宿服务税率"), False),
    ("住宿服务6％税率", ("住宿服务6‰税率",), False),
    ("住宿服务6‰税率", ("住宿服务6‱税率",), False),
    ("住宿服务6％税率", ("住宿服务6税率",), False),
    ("住宿服务百分之六税率", ("住宿服务千分之六税率",), False),
    ("住宿服务6％税率", ("住宿服务6％税率政策",), True),
    ("住宿服务千分之六税率", ("住宿服务千分之六税率政策",), True),
])
@pytest.mark.asyncio
async def test_domain_focusing_preserves_topic_union_and_every_explicit_condition(question, queries, accepted):
    class Gateway:
        calls = 0

        async def generate(self, **kwargs):
            self.calls += 1
            return SimpleNamespace(output=KnowledgeSemanticPlanOutput(
                outcome="search", missing_conditions=(),
                queries=tuple(PlannedDomainQuery(domain_id=domain, query=query)
                              for domain, query in zip(("tax.policy", "tax.law"), queries)),
            ))

    gateway = Gateway()
    planner = KnowledgeSemanticPlanner(
        gateway=gateway, context=SimpleNamespace(require_current=lambda: object()),
        enabled_domain_ids=("tax.policy", "tax.law"), definition=KnowledgeRewriteTaskV3.definition(),
    )
    result = await planner.rewrite(original_question=question, timeout_s=1)
    assert (result.kind is RewriteStageKind.SUCCESS) is accepted
    assert gateway.calls == 1
