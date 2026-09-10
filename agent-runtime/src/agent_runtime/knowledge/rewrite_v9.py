"""Scope query constraints through existing requirements; keep the exact V7 wire contract."""
from __future__ import annotations

from dataclasses import replace

from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput, KnowledgeSemanticPlanOutput
from agent_runtime.knowledge.rewrite_v8 import KnowledgeRewriteTaskV8
from agent_runtime.model.contracts import ModelTaskDefinition, StructuredModelRequest

_PREVIOUS_CONSTRAINTS = (
    "每个query保留原问题显式主体、服务、日期、数字、比例及单位、否定、文号、法条、纳税人类型及计税方法，原样保留受保护约束，不补造或改值。"
)
_SCOPED_CONSTRAINTS = (
    "先在requirements的focus中表达各子问题及其所属原问条件，再形成对应域query；不输出额外作用域字段。"
    "focus保留该需求相关的主体、服务、日期、数字、完整比例及单位、否定、文号、法条、纳税人类型和计税方法；"
    "适用于多个域的全局条件必须在每个受影响域至少一个focus中明确，不把全局条件错误归为局部。"
    "每域query保留本域所有focus中的受保护条件，以及原问题中未分配给任何focus的条件；"
    "不复制仅属于其他域的约束，不新增、换值或重复增加，受保护值保持原问顺序。"
    "同域多个focus重复同一条件不要求query重复；原问多次出现相同受保护值时保留其各子问题所属次数，不能用去重掩盖遗漏。"
    "单域query仍保留全部原问约束。无法可靠判断条件归属时按既有可表达缺失条件澄清，否则unsupported，不猜测、不补条件。"
)
_PREVIOUS_RATIO = "有%/％/‰/‱或百分之/千分之/万分之时，每个query保留完整比例及税率主题。"
_SCOPED_RATIO = (
    "有%/％/‰/‱或百分之/千分之/万分之时，完整比例、单位及税率/征收率主题按focus所属域保留，"
    "未分配条件保守保留在全部域，不改比例所对应的主题含义。focus不能新增原问没有的税率/征收率主题。"
)


def _request(value: KnowledgeSemanticPlanInput) -> StructuredModelRequest:
    request = KnowledgeRewriteTaskV8.definition().build_request(value)
    instruction = request.system_instruction
    for old, new in ((_PREVIOUS_CONSTRAINTS, _SCOPED_CONSTRAINTS), (_PREVIOUS_RATIO, _SCOPED_RATIO)):
        if instruction.count(old) != 1:
            raise ValueError("knowledge.rewrite_instruction_baseline_invalid")
        instruction = instruction.replace(old, new)
    return replace(request, task_version="9", system_instruction=instruction)


class KnowledgeRewriteTaskV9:
    @staticmethod
    def definition() -> ModelTaskDefinition[KnowledgeSemanticPlanInput, KnowledgeSemanticPlanOutput]:
        return replace(KnowledgeRewriteTaskV8.definition(), task_version="9", build_request=_request)
