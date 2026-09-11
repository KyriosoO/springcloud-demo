"""Schema-constrained output envelope, with the unchanged V9 plan semantics."""
from __future__ import annotations

from dataclasses import replace

from agent_runtime.capability_api.contracts import JsonObject
from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput, KnowledgeSemanticPlanOutput
from agent_runtime.knowledge.rewrite_v9 import KnowledgeRewriteTaskV9
from agent_runtime.model.contracts import (
    InvalidModelOutput, ModelTaskDefinition, StructuredFinishKind, StructuredModelRequest,
    StructuredModelResponse, StructuredOutputMode, StructuredToolDefinition, StructuredToolMode,
)

OUTPUT_NAME = "knowledge_requirement_plan"
_OLD_OUTPUT = "只输出一个JSON对象，精确五字段outcome、question_kind、queries、requirements、missing_conditions；禁止额外字段、Markdown或解释。"
_NEW_OUTPUT = (
    "只通过knowledge_requirement_plan输出一次参数JSON，精确五字段outcome、question_kind、queries、requirements、missing_conditions；"
    "这是结果结构，不执行函数。不输出正文、额外字段、Markdown或解释。"
)


def _object(properties: JsonObject) -> JsonObject:
    return {"type": "object", "properties": properties,
            "required": tuple(properties), "additionalProperties": False}


def _schema(domains: tuple[str, ...]) -> JsonObject:
    domain: JsonObject = {"type": "string", "enum": domains}
    return _object({
        "outcome": {"type": "string", "enum": ("search", "clarification_required", "unsupported")},
        "question_kind": {"type": "string", "enum": ("lookup", "applicability", "none")},
        "queries": {"type": "array", "items": _object({"domain_id": domain, "query": {"type": "string"}})},
        "requirements": {"type": "array", "items": _object({
            "requirement_id": {"type": "string", "enum": ("r1", "r2", "r3", "r4")},
            "domain_id": domain,
            "kind": {"type": "string", "enum": ("subject_scope", "rule", "temporal_scope", "constraint")},
            "focus": {"type": "string"},
        })},
        "missing_conditions": {"type": "array", "items": {
            "type": "string", "enum": ("subject", "taxpayer_type", "calculation_method", "applicable_period"),
        }},
    })


def _request(value: KnowledgeSemanticPlanInput) -> StructuredModelRequest:
    request = KnowledgeRewriteTaskV9.definition().build_request(value)
    instruction = request.system_instruction
    if instruction.count(_OLD_OUTPUT) != 1 or instruction.count("工具调用或代码") != 1:
        raise ValueError("knowledge.rewrite_instruction_baseline_invalid")
    instruction = instruction.replace(_OLD_OUTPUT, _NEW_OUTPUT).replace(
        "工具调用或代码", "可执行指令或代码",
    )
    return replace(
        request, task_version="10", system_instruction=instruction,
        tools=(StructuredToolDefinition(name=OUTPUT_NAME, description="Return the bounded knowledge retrieval plan; never execute a tool.",
                                       arguments_schema=_schema(value.enabled_domain_ids)),),
        tool_mode=StructuredToolMode.SCHEMA_ONLY, output_mode=StructuredOutputMode.TOOL_CALLS,
    )


def _parse(response: StructuredModelResponse) -> KnowledgeSemanticPlanOutput:
    if (response.finish_kind is not StructuredFinishKind.TOOL_CALLS or response.content not in (None, "")
            or len(response.tool_calls) != 1 or response.tool_calls[0].name != OUTPUT_NAME):
        raise InvalidModelOutput("knowledge.invalid_requirement_plan")
    # Change framing only: no repair, field coercion, dispatch or follow-up request.
    return KnowledgeRewriteTaskV9.definition().parse_response(StructuredModelResponse(
        finish_kind=StructuredFinishKind.STOP, content=response.tool_calls[0].arguments_json,
        tool_calls=(), usage_total_tokens=response.usage_total_tokens,
    ))


class KnowledgeRewriteTaskV10:
    @staticmethod
    def definition() -> ModelTaskDefinition[KnowledgeSemanticPlanInput, KnowledgeSemanticPlanOutput]:
        return replace(KnowledgeRewriteTaskV9.definition(), task_version="10", build_request=_request, parse_response=_parse)
