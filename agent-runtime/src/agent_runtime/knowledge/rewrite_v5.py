"""Minimal source-domain planning with the unchanged V3/V4 contract."""
from __future__ import annotations

from dataclasses import replace

from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput, KnowledgeSemanticPlanOutput
from agent_runtime.knowledge.rewrite_v4 import INSTRUCTION as V4_INSTRUCTION, KnowledgeRewriteTaskV4
from agent_runtime.model.contracts import ModelTaskDefinition, StructuredModelRequest

DOMAIN_INSTRUCTION = (
    "选域时必须区分原文类别与税务背景：域不是税种标签，问题属于税务不代表需要所有域。"
    "只查政策文件或实施细则中的定义、分类、办理条件，且未提出独立法律规则问题时，只选tax.policy；"
    "只查指定法律或行政法规的法条、基本规则，且不要求政策分类或实施依据时，只选tax.law。"
    "结合完整语义判断，不能按某个词是否出现机械选域。"
    "只有原问题确实需要政策分类/实施依据与法律规则分别提供不可替代的依据时，才一次选择两域。"
    "不得为补充背景、保险召回或在第二域重复同一个问题而扩域。"
    "不得补出用户未问的税率、期间、法条或第二个问题；单独出现税率不等于需要法律域，"
    "不得假设历史期间适用当前法律。必要原文域不在已启用目录时返回unsupported，不静默替换域。"
    "上述规则只细化search的最小必要域，不改变适用判断优先澄清、禁止补造、条件保持及所有输出合同。"
)
INSTRUCTION = V4_INSTRUCTION + DOMAIN_INSTRUCTION


def _request(value: KnowledgeSemanticPlanInput) -> StructuredModelRequest:
    request = KnowledgeRewriteTaskV4.definition().build_request(value)
    return replace(request, task_version="5", system_instruction=INSTRUCTION)


class KnowledgeRewriteTaskV5:
    @staticmethod
    def definition() -> ModelTaskDefinition[KnowledgeSemanticPlanInput, KnowledgeSemanticPlanOutput]:
        return replace(KnowledgeRewriteTaskV4.definition(), task_version="5", build_request=_request)
