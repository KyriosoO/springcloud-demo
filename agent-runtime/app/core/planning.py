"""
Plan 解析、校验和 prompt 辅助 — 多域感知。
支持 route/query 分离 prompt。
"""

import importlib.resources
import json
from typing import Any

from app.contracts.models import (
    AgentFieldType,
    AgentIntent,
    AgentPlan,
    AgentQuerySpec,
    AggregateFunction,
    ClarifySpec,
    PlanGenerateRequest,
    QueryContextMode,
    RuntimeDomainSchema,
    validate_agent_plan_semantics,
)
from app.core.route_models import RouteDecision


def _strip_markdown_fence(text: str) -> str:
    """去除 LLM 输出的 markdown 代码围栏，返回纯 JSON 文本。"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _build_base_payload(request: PlanGenerateRequest) -> dict[str, Any]:
    """构建公共 JSON 载荷（message/recentTurns/previousQuery/domainSchemas/capabilities）。"""
    return {
        "message": request.message,
        "recentTurns": [
            t.model_dump(by_alias=True)
            for t in (request.recent_turns or ())
        ],
        "previousQuery": (
            request.previous_query.model_dump(by_alias=True)
            if request.previous_query is not None
            else None
        ),
        "domainSchemas": [
            s.model_dump(by_alias=True)
            for s in (request.domain_schemas or ())
        ],
        "capabilities": [
            c.model_dump(by_alias=True)
            for c in request.capabilities
        ],
        "planVersion": "1.0",
    }


def _field_type(schema: RuntimeDomainSchema | None, field: str) -> AgentFieldType | None:
    """从 schema 中查找字段类型。"""
    if schema is None:
        return None
    for f in schema.fields:
        if f.name == field:
            return f.type
    return None


def load_route_prompt() -> str:
    """加载路由系统 prompt，从 app/prompts/route_system.md。"""
    ref = importlib.resources.files("app") / "prompts" / "route_system.md"
    return ref.read_text(encoding="utf-8")


def load_query_prompt() -> str:
    """加载查询系统 prompt，从 app/prompts/query_system.md。"""
    ref = importlib.resources.files("app") / "prompts" / "query_system.md"
    return ref.read_text(encoding="utf-8")


def build_user_payload(request: PlanGenerateRequest) -> dict[str, Any]:
    """构建发送给 LLM 的 JSON 载荷（用户消息）。"""
    return _build_base_payload(request)


def schema_by_domain(
    request: PlanGenerateRequest,
    domain: str,
) -> RuntimeDomainSchema | None:
    """按 domain 名称查找对应的 RuntimeDomainSchema。"""
    return next(
        (s for s in request.domain_schemas if s.domain == domain),
        None,
    )


def parse_plan(raw_json: str) -> AgentPlan:
    """解析 LLM 输出为 AgentPlan，自动去除 markdown 代码围栏。"""
    data = json.loads(_strip_markdown_fence(raw_json))
    plan = AgentPlan.model_validate(data)
    validate_agent_plan_semantics(plan)
    return plan


def parse_route_decision(raw_json: str) -> RouteDecision:
    """解析 LLM 路由输出为 RouteDecision，自动去除 markdown 代码围栏。"""
    data = json.loads(_strip_markdown_fence(raw_json))
    return RouteDecision.model_validate(data)


def validate_route_decision(
    route: RouteDecision,
    request: PlanGenerateRequest,
) -> list[str]:
    """对路由决策做语义校验（domain 是否存在于 domainSchemas、capability 是否可用）。"""
    errors: list[str] = []

    # capability 校验：intent 对应的 capability 必须存在且 enabled=true；
    # QUERY/AGGREGATE 带 domain 时，domain 必须在 capability 的 enabled scope 中。
    _intent_to_capability = {
        AgentIntent.QUERY: "query.search",
        AgentIntent.AGGREGATE: "aggregate.compute",
        AgentIntent.CLARIFY: "clarify.ask",
    }
    cap_id = _intent_to_capability.get(route.intent)
    if cap_id is not None and not _has_capability(request.capabilities, cap_id):
        errors.append(
            f"Capability '{cap_id}' is not available for intent '{route.intent.value}'"
        )

    if route.intent in (AgentIntent.QUERY, AgentIntent.AGGREGATE) and route.domain is not None:
        _require_capability_domain(request.capabilities, cap_id, route.domain, errors)

    if route.domain is not None:
        schema = schema_by_domain(request, route.domain)
        if schema is None:
            errors.append(f"Unknown route domain '{route.domain}'")

    return errors


def build_clarify_plan(request_id: str, route: RouteDecision) -> AgentPlan:
    """从路由决策直接构造 CLARIFY AgentPlan。"""
    return AgentPlan(
        plan_version="1.0",
        intent=AgentIntent.CLARIFY,
        domain=route.domain,
        query=None,
        clarify=ClarifySpec(question=route.question),
    )


def build_query_payload(request: PlanGenerateRequest, route: RouteDecision) -> dict[str, Any]:
    """构建 QUERY 生成阶段的 JSON 载荷，在基础载荷上附加 route 决策对象。"""
    payload = _build_base_payload(request)
    payload["route"] = route.model_dump(by_alias=True)
    return payload


def validate_query_plan_against_route(
    plan: AgentPlan,
    route: RouteDecision,
) -> list[str]:
    """校验 QUERY plan 与路由决策的一致性：intent 必须为 QUERY、domain 必须匹配、clarify 必须为空。"""
    errors: list[str] = []

    if plan.intent != AgentIntent.QUERY:
        errors.append("Query plan must have intent=QUERY")

    if route.domain is not None and plan.domain != route.domain:
        errors.append(
            f"Query plan domain '{plan.domain}' does not match route domain '{route.domain}'"
        )

    if plan.clarify is not None:
        errors.append("QUERY plan must not contain clarify")

    if plan.aggregate is not None:
        errors.append("QUERY plan must not contain aggregate")

    return errors


def load_aggregate_prompt() -> str:
    """加载聚合系统 prompt，从 app/prompts/aggregate_system.md。"""
    ref = importlib.resources.files("app") / "prompts" / "aggregate_system.md"
    return ref.read_text(encoding="utf-8")


def build_aggregate_payload(request: PlanGenerateRequest, route: RouteDecision) -> dict[str, Any]:
    """构建 AGGREGATE 生成阶段的 JSON 载荷，在基础载荷上附加 route 决策对象。"""
    payload = _build_base_payload(request)
    payload["route"] = route.model_dump(by_alias=True)
    return payload


def validate_aggregate_plan_against_route(
    plan: AgentPlan,
    route: RouteDecision,
) -> list[str]:
    """校验 AGGREGATE plan 与路由决策的契约一致性。仅检查 intent/domain/互斥字段；字段级白名单/类型约束由 validate_plan_against_request 负责。"""
    errors: list[str] = []

    if plan.intent != AgentIntent.AGGREGATE:
        errors.append("Aggregate plan must have intent=AGGREGATE")

    if route.domain is not None and plan.domain != route.domain:
        errors.append(
            f"Aggregate plan domain '{plan.domain}' does not match route domain '{route.domain}'"
        )

    if plan.aggregate is None:
        errors.append("AGGREGATE plan requires an aggregate spec")
        return errors

    if plan.query is not None:
        errors.append("AGGREGATE plan must not contain query")
    if plan.clarify is not None:
        errors.append("AGGREGATE plan must not contain clarify")

    return errors


def validate_plan_against_request(
    plan: AgentPlan,
    request: PlanGenerateRequest,
) -> list[str]:
    """Pydantic 基础校验之外的语义层校验。"""
    errors: list[str] = []

    if plan.intent == AgentIntent.QUERY:
        if plan.domain is None:
            errors.append("QUERY plan requires a non-null domain")
            return errors

        # capability scope 校验：domain 必须在 query.search enabled 中
        caps = request.capabilities
        _require_capability_domain(caps, "query.search", plan.domain, errors)

        schema = schema_by_domain(request, plan.domain)
        if schema is None:
            errors.append(f"Unknown QUERY domain '{plan.domain}'")
            return errors

        if plan.query.context_mode == QueryContextMode.merge:
            if request.previous_query is None:
                errors.append("MERGE query requires previousQuery")
            elif request.previous_query.domain != plan.domain:
                errors.append(
                    "MERGE domain must match previousQuery domain"
                )

        allowed_fields = {f.name for f in schema.fields}
        allowed_operators_by_field = {
            f.name: {op.value for op in f.operators}
            for f in schema.fields
        }
        _validate_query(
            plan.query, allowed_fields, allowed_operators_by_field,
            schema.max_filters, schema.max_size, schema.max_result_window, errors,
        )

    elif plan.intent == AgentIntent.CLARIFY:
        # capability 校验：确保 clarify.ask 存在于 request capabilities 中
        caps = request.capabilities
        if not _has_capability(caps, "clarify.ask"):
            errors.append("Capability 'clarify.ask' not available")
        if plan.domain is not None and schema_by_domain(request, plan.domain) is None:
            errors.append(f"Unknown CLARIFY domain '{plan.domain}'")

    elif plan.intent == AgentIntent.AGGREGATE:
        if plan.domain is None:
            errors.append("AGGREGATE plan requires a non-null domain")
            return errors

        # capability scope 校验：domain 必须在 aggregate.compute enabled 中
        caps = request.capabilities
        _require_capability_domain(caps, "aggregate.compute", plan.domain, errors)

        schema = schema_by_domain(request, plan.domain)
        if schema is None:
            errors.append(f"Unknown AGGREGATE domain '{plan.domain}'")
            return errors

        if plan.aggregate is None:
            errors.append("AGGREGATE plan requires an aggregate spec")
            return errors

        allowed_fields = {f.name for f in schema.fields}
        allowed_operators_by_field = {
            f.name: {op.value for op in f.operators}
            for f in schema.fields
        }
        allowed_agg_functions_by_field = {
            f.name: f.supported_aggregate_functions
            for f in schema.fields
        }

        for f in (plan.aggregate.filters or ()):
            if f.field not in allowed_fields:
                errors.append(f"Aggregate filter field '{f.field}' not allowed")
            elif f.operator.value not in allowed_operators_by_field.get(f.field, set()):
                errors.append(f"Operator '{f.operator.value}' not allowed for field '{f.field}'")

        for gb in (plan.aggregate.group_by_fields or ()):
            if not gb or not gb.strip():
                errors.append("groupBy field must not be blank")
            elif gb not in allowed_fields:
                errors.append(f"groupBy field '{gb}' not allowed in domain")

        metric_aliases: set[str] = set()
        for metric in plan.aggregate.metrics:
            if metric.alias in metric_aliases:
                errors.append(f"Metric alias '{metric.alias}' is duplicated")
            metric_aliases.add(metric.alias)
            if metric.function == AggregateFunction.COUNT:
                if metric.field is not None:
                    errors.append("COUNT must not specify a field")
                continue
            if metric.field is None:
                errors.append(f"{metric.function.value} requires a field")
                continue
            if metric.field not in allowed_fields:
                errors.append(f"Metric field '{metric.field}' not allowed")
                continue
            allowed_fns = allowed_agg_functions_by_field.get(metric.field)
            if allowed_fns is not None and metric.function not in allowed_fns:
                errors.append(
                    f"Aggregate function '{metric.function.value}' not allowed for field "
                    f"'{metric.field}'. Allowed: {sorted(f.value for f in allowed_fns)}"
                )
            if metric.function in (AggregateFunction.SUM, AggregateFunction.AVG):
                ft = _field_type(schema, metric.field)
                if ft is not None and ft != AgentFieldType.DECIMAL:
                    errors.append(f"{metric.function.value} requires DECIMAL field, got {ft.value}")
            if metric.function in (AggregateFunction.MIN, AggregateFunction.MAX):
                ft = _field_type(schema, metric.field)
                if ft is not None and ft not in (AgentFieldType.DECIMAL, AgentFieldType.INSTANT):
                    errors.append(f"{metric.function.value} requires DECIMAL or INSTANT field, got {ft.value}")

        if plan.aggregate.order_by:
            valid_order_fields = set(plan.aggregate.group_by_fields or []) | metric_aliases
            for order in plan.aggregate.order_by:
                if order.field not in valid_order_fields:
                    errors.append(
                        f"orderBy field '{order.field}' not in groupByFields or metric aliases"
                    )

    return errors


def _has_capability(caps: list, capability_id: str) -> bool:
    """检查 request capabilities 中是否包含指定 capabilityId 且 enabled=true。"""
    for c in caps:
        if c.capability_id == capability_id and c.enabled:
            return True
    return False


def _require_capability_domain(
    caps: list,
    capability_id: str,
    plan_domain: str | None,
    errors: list[str],
) -> None:
    """校验 plan domain 是否存在于指定 capability 的 enabled scope 中。

    设计原则（来源：Agent能力注册与Metadata收敛实施设计 v1.0 Section 8.3/8.4）：
    - capabilities == [] 表示 Java 声明当前无可用能力，QUERY/AGGREGATE 全部拒绝。
    - 缺失对应 capability 或 domain 不在 enabled scope 中，均追加错误。
    - CLARIFY 不调用本函数（只要求 capability 存在，不要求 domain scope，见 Section 8.3 line 503）。
    """
    if not caps:
        # 无 capability 声明：禁止任何 QUERY/AGGREGATE
        errors.append(f"Capability '{capability_id}' not available (capabilities is empty)")
        return
    for c in caps:
        if c.capability_id == capability_id:
            # 顶层 enabled=false 视为 capability 整体不可用
            if not c.enabled:
                errors.append(f"Capability '{capability_id}' is disabled")
                return
            enabled_domains = {ds.domain for ds in (c.domain_scopes or []) if ds.enabled}
            if not enabled_domains:
                errors.append(
                    f"Capability '{capability_id}' has no enabled domain scopes"
                )
                return
            if plan_domain is None or plan_domain not in enabled_domains:
                errors.append(
                    f"Domain '{plan_domain}' not in enabled scope of capability "
                    f"'{capability_id}'. Enabled: {sorted(enabled_domains)}"
                )
            return
    # 未找到 capability
    errors.append(f"Capability '{capability_id}' not found in request capabilities")


def _validate_query(
    query: AgentQuerySpec,
    allowed_fields: set[str],
    allowed_operators_by_field: dict[str, set[str]],
    max_filters: int,
    max_size: int,
    max_result_window: int,
    errors: list[str],
) -> None:
    """对 QUERY plan 做结构校验。校验 filter 数量上限、字段白名单、操作符白名单、remove_fields 域成员、page >= 1、size 上下界、分页范围不超过 max_result_window。错误追加写入 errors 列表。"""
    filters = query.filters or []
    remove_fields = query.remove_fields or []
    select_fields = query.select_fields or []

    if len(filters) > max_filters:
        errors.append(f"Filters count {len(filters)} exceeds max {max_filters}")

    context_mode = query.context_mode or QueryContextMode.replace
    if context_mode == QueryContextMode.replace:
        if not filters:
            errors.append("QUERY Plan requires at least one filter")
        if remove_fields:
            errors.append("REPLACE QUERY must not contain removeFields")

    for f in filters:
        if f.field not in allowed_fields:
            errors.append(f"Field '{f.field}' not allowed")
            continue
        if f.operator.value not in allowed_operators_by_field.get(f.field, set()):
            errors.append(f"Operator '{f.operator.value}' not allowed for field '{f.field}'")

    for field in remove_fields:
        if field not in allowed_fields:
            errors.append(f"removeFields contains unknown field '{field}'")

    for field in select_fields:
        if field not in allowed_fields:
            errors.append(f"Unknown selectField '{field}'")
    if len(select_fields) > 10:
        errors.append(f"selectFields count {len(select_fields)} exceeds max 10")

    if query.page is not None and query.page < 1:
        errors.append("page must be >= 1")
    if query.size is not None and (query.size < 1 or query.size > max_size):
        errors.append(f"size must be >= 1 and <= {max_size}")

    if query.page is not None and query.size is not None:
        frm = (query.page - 1) * query.size
        if frm + query.size > max_result_window:
            errors.append(f"Pagination range exceeds max_result_window {max_result_window}")
