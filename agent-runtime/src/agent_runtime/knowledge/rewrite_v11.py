"""Fixed enabled-domain slots; unchanged necessary-evidence plan semantics."""
from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, cast

from agent_runtime.capability_api.contracts import JsonObject
from agent_runtime.knowledge.catalog import build_tax_domain_catalog
from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput, KnowledgeSemanticPlanOutput
from agent_runtime.knowledge.rewrite_v9 import KnowledgeRewriteTaskV9
from agent_runtime.knowledge.rewrite_v10 import KnowledgeRewriteTaskV10, OUTPUT_NAME
from agent_runtime.model.contracts import (
    InvalidModelOutput, ModelTaskDefinition, StructuredFinishKind, StructuredModelRequest,
    StructuredModelResponse, canonical_object_json,
)

_FIELDS = frozenset(("outcome", "question_kind", "queries", "requirements", "missing_conditions"))
_OLD_EXAMPLES = (
    '检索结构：{"outcome":"search","question_kind":"lookup","queries":[{"domain_id":"目录内ID","query":"税务检索表达"}],'
    '"requirements":[{"requirement_id":"r1","domain_id":"同组query的域ID","kind":"rule","focus":"待查证的税务规则"}],"missing_conditions":[]}。'
    '澄清结构：{"outcome":"clarification_required","question_kind":"none","queries":[],"requirements":[],"missing_conditions":["taxpayer_type"]}。'
    '不支持结构：{"outcome":"unsupported","question_kind":"none","queries":[],"requirements":[],"missing_conditions":[]}。'
)
_OLD_QUERY_RULE = "queries含1至2个唯一启用域，每域一个非空NFC query，最多1024字符。"
_SLOT_RULE = (
    "queries是固定槽位对象，键必须精确覆盖所有启用域；每个值只能是字符串。"
    "未选中域填精确空串，不是空白、null或缺失键；澄清与不支持时所有槽位填空串。"
    "search选中1至2个域，每个非空槽位为该域唯一NFC query，最多1024字符。"
    "只选择原问题真正需要的域，不为填满槽位广播全部域。"
    "同域多个需求共用一个query，不能重复键，也不输出旧queries数组。"
)
_OLD_ASSOCIATION = "每项domain_id必须在queries内，每个查询域至少一项需求。"
_SLOT_ASSOCIATION = "每项domain_id必须对应queries内非空槽位，每个非空槽位至少一项需求，空槽位不得关联需求。"


def _validated_domains(domains: tuple[str, ...]) -> tuple[str, ...]:
    known = tuple(item.domain_id for item in build_tax_domain_catalog().domains)
    if (type(domains) is not tuple or not 1 <= len(domains) <= 2
            or any(type(item) is not str or item not in known for item in domains)
            or domains != tuple(item for item in known if item in domains)):
        raise ValueError("knowledge.enabled_domains_invalid")
    return domains


def _examples(domains: tuple[str, ...]) -> str:
    empty: JsonObject = {domain: "" for domain in domains}
    search: JsonObject = {
        "outcome": "search", "question_kind": "lookup",
        "queries": {**empty, domains[0]: "税务检索表达"},
        "requirements": ({"requirement_id": "r1", "domain_id": domains[0], "kind": "rule",
                          "focus": "待查证的税务规则"},),
        "missing_conditions": (),
    }
    terminal: JsonObject = {
        "outcome": "unsupported", "question_kind": "none", "queries": empty,
        "requirements": (), "missing_conditions": (),
    }
    clarification: JsonObject = {**terminal, "outcome": "clarification_required", "missing_conditions": ("taxpayer_type",)}
    return ("检索结构：" + canonical_object_json(search) + "。澄清结构："
            + canonical_object_json(clarification) + "。不支持结构：" + canonical_object_json(terminal) + "。")


def _request(value: KnowledgeSemanticPlanInput, domains: tuple[str, ...]) -> StructuredModelRequest:
    if (type(value) is not KnowledgeSemanticPlanInput or type(value.enabled_domain_ids) is not tuple
            or value.enabled_domain_ids != domains):
        raise ValueError("knowledge.enabled_domains_mismatch")
    request = KnowledgeRewriteTaskV10.definition().build_request(value)
    instruction = request.system_instruction
    for old, new in ((_OLD_EXAMPLES, _examples(domains)), (_OLD_QUERY_RULE, _SLOT_RULE),
                     (_OLD_ASSOCIATION, _SLOT_ASSOCIATION)):
        if instruction.count(old) != 1:
            raise ValueError("knowledge.rewrite_instruction_baseline_invalid")
        instruction = instruction.replace(old, new)
    tool = request.tools[0]
    properties = dict(cast(JsonObject, tool.arguments_schema["properties"]))
    properties["queries"] = {
        "type": "object", "properties": {domain: {"type": "string"} for domain in domains},
        "required": domains, "additionalProperties": False,
    }
    return replace(
        request, task_version="11", system_instruction=instruction,
        tools=(replace(tool, arguments_schema={**tool.arguments_schema, "properties": properties}),),
    )


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise InvalidModelOutput("knowledge.invalid_requirement_plan")
        value[key] = item
    return value


def _constant(_: str) -> None:
    raise InvalidModelOutput("knowledge.invalid_requirement_plan")


def _parse(response: StructuredModelResponse, domains: tuple[str, ...]) -> KnowledgeSemanticPlanOutput:
    if (response.finish_kind is not StructuredFinishKind.TOOL_CALLS or response.content not in (None, "")
            or len(response.tool_calls) != 1 or response.tool_calls[0].name != OUTPUT_NAME):
        raise InvalidModelOutput("knowledge.invalid_requirement_plan")
    try:
        value = json.loads(response.tool_calls[0].arguments_json, object_pairs_hook=_unique, parse_constant=_constant)
        if type(value) is not dict or set(value) != _FIELDS:
            raise ValueError
        slots = value["queries"]
        if (type(slots) is not dict or set(slots) != set(domains)
                or any(type(item) is not str for item in slots.values())):
            raise ValueError
        # 空串是协议内的未选中标记；非空值原样转接，不能修复、去重或补造计划。
        value["queries"] = [{"domain_id": domain, "query": slots[domain]}
                            for domain in domains if slots[domain] != ""]
        mapped = canonical_object_json(value)
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise InvalidModelOutput("knowledge.invalid_requirement_plan") from exc
    return KnowledgeRewriteTaskV9.definition().parse_response(StructuredModelResponse(
        finish_kind=StructuredFinishKind.STOP, content=mapped, tool_calls=(),
        usage_total_tokens=response.usage_total_tokens,
    ))


class KnowledgeRewriteTaskV11:
    @staticmethod
    def definition(*, enabled_domain_ids: tuple[str, ...]) -> ModelTaskDefinition[KnowledgeSemanticPlanInput, KnowledgeSemanticPlanOutput]:
        domains = _validated_domains(enabled_domain_ids)

        def build_request(value: KnowledgeSemanticPlanInput) -> StructuredModelRequest:
            return _request(value, domains)

        def parse_response(response: StructuredModelResponse) -> KnowledgeSemanticPlanOutput:
            return _parse(response, domains)

        return replace(KnowledgeRewriteTaskV10.definition(), task_version="11",
                       build_request=build_request, parse_response=parse_response)
