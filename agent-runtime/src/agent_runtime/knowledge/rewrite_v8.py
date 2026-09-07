"""Restore clarification-first intent rules without changing the V7 wire contract."""
from __future__ import annotations

from dataclasses import replace

from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput, KnowledgeSemanticPlanOutput
from agent_runtime.knowledge.rewrite_v7 import KnowledgeRewriteTaskV7
from agent_runtime.model.contracts import ModelTaskDefinition, StructuredModelRequest

_PREVIOUS_INTENT = (
    "search的question_kind只有lookup或applicability；查阅、分类、比较或规则列举为lookup，确定条件下的具体适用判断为applicability。"
)
_CLARIFICATION_FIRST = (
    "先判断用户是在要求适用结论，还是查阅资料，再判断必要用户条件，最后才决定域、queries和requirements；不要输出推理过程。"
    "适用判断：用户要求为某服务、交易或经营活动选择一个适用税率、征收率、优惠或处理结果，不要求出现具体企业或个人名称。"
    "若结果会因未提供的纳税人类型、计税方法、适用期间或主体而不同，必须输出clarification_required，"
    "只列真正缺失的必要条件，question_kind为none，queries和requirements为空。"
    "不得默认一般纳税人、一般计税、当前期间或通常情形；不得把条件不完整的适用判断改成lookup规则查阅后直接给结论。"
    "资料查阅：用户明确要求定义、分类、指定法条、一般规则列举或比较，且无需为某交易选择单一结果时，可以search并标为lookup。"
    "不得机械要求全部四类条件；单独出现适用等词不决定意图，列举适用范围也可以是资料查阅。"
    "目的有歧义、直接回答可能被理解为单一适用结论时，只能为可表达的必要缺失条件请求澄清；"
    "若不存在可表达的缺失条件又无法形成可靠知识计划，输出unsupported，不伪造缺失条件。"
    "只有允许search后才生成查询和证据需求；search的question_kind只有lookup或applicability，条件充分的适用判断标为applicability。"
)


def _request(value: KnowledgeSemanticPlanInput) -> StructuredModelRequest:
    request = KnowledgeRewriteTaskV7.definition().build_request(value)
    if request.system_instruction.count(_PREVIOUS_INTENT) != 1:
        raise ValueError("knowledge.rewrite_instruction_baseline_invalid")
    instruction = request.system_instruction.replace(_PREVIOUS_INTENT, _CLARIFICATION_FIRST)
    return replace(request, task_version="8", system_instruction=instruction)


class KnowledgeRewriteTaskV8:
    @staticmethod
    def definition() -> ModelTaskDefinition[KnowledgeSemanticPlanInput, KnowledgeSemanticPlanOutput]:
        return replace(KnowledgeRewriteTaskV7.definition(), task_version="8", build_request=_request)
