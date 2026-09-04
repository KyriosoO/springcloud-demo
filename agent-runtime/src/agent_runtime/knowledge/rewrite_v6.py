"""Per-domain query focus without changing the shared planning contract."""
from __future__ import annotations

from dataclasses import replace

from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput, KnowledgeSemanticPlanOutput
from agent_runtime.knowledge.rewrite_v5 import INSTRUCTION as V5_INSTRUCTION, KnowledgeRewriteTaskV5
from agent_runtime.model.contracts import ModelTaskDefinition, StructuredModelRequest

_CONTEXT_INSTRUCTION_V5 = (
    "每个query保留原问题的税务或法律检索语境，不得把带税种的问题改成脱离税务语境的普通服务检索。"
)
FOCUS_INSTRUCTION = (
    "每域query聚焦本域待证明的子问题，不机械复制仅修饰另一子问题的税法名称、文种或背景词。"
    "原问题的税务意图及所选逻辑域共同约束检索范围，不得为普通问题伪造税务意图。"
    "若税种、法律名称或其他限定确实修饰本域所查分类或规则，它仍是必要条件，不能借聚焦删除或替换。"
    "单域不得省略原问题实质主题，多域整组不得遗漏任何子问题；结合完整语义判断条件归属。"
    "上述聚焦不改变每个query保留显式主体、服务、日期、数字、具体比例、否定、文号、法条、"
    "纳税人及计税方法的要求，也不改变税率主题整组保持和具体比例逐query保持规则。"
)
# Replace, rather than append a contradictory instruction to an immutable task.
if V5_INSTRUCTION.count(_CONTEXT_INSTRUCTION_V5) != 1:
    raise ValueError("knowledge.rewrite_v6_source_instruction_invalid")
INSTRUCTION = V5_INSTRUCTION.replace(_CONTEXT_INSTRUCTION_V5, FOCUS_INSTRUCTION, 1)


def _request(value: KnowledgeSemanticPlanInput) -> StructuredModelRequest:
    request = KnowledgeRewriteTaskV5.definition().build_request(value)
    return replace(request, task_version="6", system_instruction=INSTRUCTION)


class KnowledgeRewriteTaskV6:
    @staticmethod
    def definition() -> ModelTaskDefinition[KnowledgeSemanticPlanInput, KnowledgeSemanticPlanOutput]:
        return replace(KnowledgeRewriteTaskV5.definition(), task_version="6", build_request=_request)
