"""Evidence-backed classification context without changing the extractive contract."""
from __future__ import annotations

from dataclasses import replace

from agent_runtime.knowledge.evidence.contracts import KnowledgeSummaryInput, KnowledgeSummaryOutput
from agent_runtime.knowledge.evidence.summary_task_v4 import SUMMARY_PROMPT_V4, KnowledgeSummaryTaskV4
from agent_runtime.model.contracts import ModelTaskDefinition, StructuredModelRequest


CLASSIFICATION_INSTRUCTION = (
    "\n分类上下文证明规则：与答案相关的显式分类上下文也是必须有原文支持的要点。"
    "问题在某分类下询问对象定义时，须同时引用直接证明定义及该分类归属的原文，"
    "不能把用户给定的类别归属直接当作已证事实。"
    "分类清单的quote必须保留足以识别类别与成员关系的连续上下文，不能只摘孤立关键词。"
    "不展开与答案无关的分类或行业背景，不推导用户未提出的上位分类，不用模型常识补链。"
    "一段连续原文同时证明全部要点时，只使用一个point；证据分散时使用不同evidence_ref，"
    "不得为了凑双引用增加冗余点。"
    "任一必要要点缺少直接证据、证据冲突无法据原文消解，或无法在最多5点、"
    "每点最多512字符及evidence_ref唯一约束内完整证明时，必须输出insufficient_evidence。"
    "同一ref内不连续的片段不得拼接或重复引用，也不得扩大quote长度绕过限制。"
    "检索coverage完整不表示答案已完整证明；上述判断仅依据原问题和本次允许的evidence，"
    "不得补造事实、加入额外字段或执行额外任务。"
)
SUMMARY_PROMPT_V5 = SUMMARY_PROMPT_V4 + CLASSIFICATION_INSTRUCTION


def _build_request(value: KnowledgeSummaryInput) -> StructuredModelRequest:
    request = KnowledgeSummaryTaskV4.definition().build_request(value)
    return replace(request, task_version="5", system_instruction=SUMMARY_PROMPT_V5)


class KnowledgeSummaryTaskV5:
    @staticmethod
    def definition() -> ModelTaskDefinition[KnowledgeSummaryInput, KnowledgeSummaryOutput]:
        return replace(KnowledgeSummaryTaskV4.definition(), task_version="5", build_request=_build_request)
