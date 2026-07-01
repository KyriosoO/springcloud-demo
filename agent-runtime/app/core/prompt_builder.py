"""
Prompt builder: 从 generated models 和 runtime domain schema 动态构建 prompt。
避免在 prompt 文件中手写硬编码的 enum 值或字段规则。
"""

from __future__ import annotations

from app.contracts import generated_models as g
from app.contracts.models import RuntimeDomainSchema


def supported_intents_list() -> str:
    """列出当前 Java 契约中支持的全部 intent，避免 prompt 硬编码 enum。"""
    return ", ".join(f"{v.value}" for v in g.AgentIntent)


def aggregate_functions_list() -> str:
    """列出当前支持的聚合函数，避免 prompt 硬编码 enum。"""
    parts: list[str] = []
    for v in g.AggregateFunction:
        desc = _fn_desc(v)
        parts.append(f"{v.value} ({desc})")
    return ", ".join(parts)


def _fn_desc(v: g.AggregateFunction) -> str:
    if v == g.AggregateFunction.count:
        return "计数，不需要 field"
    if v == g.AggregateFunction.sum:
        return "求和，需要 DECIMAL field"
    if v == g.AggregateFunction.avg:
        return "平均，需要 DECIMAL field"
    if v == g.AggregateFunction.min:
        return "最小值，需要 DECIMAL 或 INSTANT field"
    if v == g.AggregateFunction.max:
        return "最大值，需要 DECIMAL 或 INSTANT field"
    return ""


def domain_has_aggregate_capability(s: RuntimeDomainSchema) -> bool:
    """某个 domain schema 是否包含可聚合字段（至少一个字段有非 null supported_aggregate_functions）。"""
    return any(
        f.supported_aggregate_functions is not None
        for f in s.fields
    )


def any_domain_supports_aggregate(schemas: list[RuntimeDomainSchema]) -> bool:
    """是否至少存在一个 domain 支持 AGGREGATE。"""
    return any(domain_has_aggregate_capability(s) for s in schemas)


def field_aggregate_functions_desc(field: g.RuntimeFieldSchema) -> str:
    """生成字段支持的聚合函数列表描述。"""
    if field.supported_aggregate_functions is None:
        return "(unknown capability)"
    if not field.supported_aggregate_functions:
        return "仅 COUNT"
    return ", ".join(f.value for f in field.supported_aggregate_functions)
