"""Explicit premises need quoted support; the V6 wire contract is unchanged."""
from __future__ import annotations

from dataclasses import replace

from agent_runtime.knowledge.evidence.contracts import KnowledgeSummaryInput, KnowledgeSummaryOutput
from agent_runtime.knowledge.evidence.summary_task_v6 import KnowledgeSummaryTaskV6, SUMMARY_PROMPT_V6
from agent_runtime.model.contracts import ModelTaskDefinition, StructuredModelRequest


SUMMARY_PROMPT_V7 = SUMMARY_PROMPT_V6 + (
    "完整性优先于引用数量最少。先逐一检查原问题的显式限定，再决定保留哪些point。"
    "特别是原问题同时给出上位类别和下位对象并询问定义时，"
    "定义是什么、该对象是否属于这个类别，都是必须用quote支持的要点。"
    "不得因为用户把对象放在某类别下提问就省略归属证明；也不得因为requirements只有一个条目就只引用一段。"
    "定义与分类关系分别位于不同evidence时，将两个直接片段分别输出为不同point，"
    "并在同一个requirement的evidence_refs中列出它们，联合证明该需求。"
    "若一段连续原文已经同时完整证明定义及归属，只用这一段，不机械增加第二个引用。"
    "输出前仅用实际points中的quote核对每个显式要点；不得借用未引用正文、推测标题或常识补全关系。"
    "仅找到定义而没有归属的直接证据时返回insufficient_evidence；"
    "在全部要点已被证明后，才删除不会损失任何要点的冗余point。"
)


def _build_request(value: KnowledgeSummaryInput) -> StructuredModelRequest:
    return replace(KnowledgeSummaryTaskV6.definition().build_request(value),
                   task_version="7", system_instruction=SUMMARY_PROMPT_V7)


class KnowledgeSummaryTaskV7:
    @staticmethod
    def definition() -> ModelTaskDefinition[KnowledgeSummaryInput, KnowledgeSummaryOutput]:
        return replace(KnowledgeSummaryTaskV6.definition(), task_version="7", build_request=_build_request)
