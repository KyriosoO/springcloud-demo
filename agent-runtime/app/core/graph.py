"""
route/query/aggregate 分层 plan 生成 LangGraph 图。
route -> validate_route -> (repair x1 | clarify_end | intent_stage)
intent_stage -> (generate -> validate -> repair x1 | end | error)

QUERY 和 AGGREGATE 两个 intent stage 的模式相同（生成→校验→修复），
由 _make_intent_stage 工厂统一构造，消除重复代码。
"""

from functools import lru_cache
from typing import Callable, Literal

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.contracts.models import AgentIntent, AgentPlan, PlanGenerateRequest
from app.core.llm_client import get_llm_client
from app.core.planning import (
    build_user_payload,
    build_query_payload,
    build_aggregate_payload,
    load_route_prompt,
    load_query_prompt,
    load_aggregate_prompt,
    parse_plan,
    parse_route_decision,
    validate_plan_against_request,
    validate_route_decision,
    validate_query_plan_against_route,
    validate_aggregate_plan_against_route,
    build_clarify_plan,
    _has_capability,
)
from app.core.route_models import RouteDecision
from app.core.settings import get_settings


# ── State ───────────────────────────────────────────────────────────────────

class PlanGraphState(TypedDict, total=False):
    """route/query/aggregate 分层图中所有节点共享的状态字典。"""

    request: PlanGenerateRequest

    # Route stage
    route_raw_output: str
    route_decision: RouteDecision
    route_validation_errors: list[str]
    route_repair_attempted: bool

    # Query stage
    query_raw_output: str
    query_plan: AgentPlan
    query_validation_errors: list[str]
    query_repair_attempted: bool

    # Aggregate stage
    aggregate_raw_output: str
    aggregate_plan: AgentPlan
    aggregate_validation_errors: list[str]
    aggregate_repair_attempted: bool

    # Output
    plan: AgentPlan


# ── Intent stage factory ────────────────────────────────────────────────────

# 每个 intent 的配置：prompt loader、payload builder、route validator。
# 由 _make_intent_stage 消费，避免 query/aggregate 两套节点各自手写相同的模式。

class _IntentStageConfig:
    intent: AgentIntent
    prompt_loader: Callable[[], str]
    payload_builder: Callable[[PlanGenerateRequest, RouteDecision], dict]
    route_validator: Callable[[AgentPlan, RouteDecision], list[str]]
    raw_output_key: str
    plan_key: str
    validation_errors_key: str
    repair_attempted_key: str
    repair_label: str


def _make_intent_stage(cfg: _IntentStageConfig):
    """从配置创建一組 (generate, validate, repair, route) 节点函数。"""

    async def generate_node(state: PlanGraphState) -> PlanGraphState:
        system_prompt = cfg.prompt_loader()
        user_payload = cfg.payload_builder(state["request"], state["route_decision"])
        client = get_llm_client()
        raw = await client.generate_plan_json(system_prompt, user_payload)
        state[cfg.raw_output_key] = raw
        return state

    async def validate_node(state: PlanGraphState) -> PlanGraphState:
        errors: list[str] = []
        try:
            plan = parse_plan(state[cfg.raw_output_key])
            state[cfg.plan_key] = plan
        except Exception as e:
            errors.append(str(e))
            state[cfg.validation_errors_key] = errors
            return state

        route = state["route_decision"]
        route_errors = cfg.route_validator(plan, route)
        if route_errors:
            errors.extend(route_errors)

        req_errors = validate_plan_against_request(plan, state["request"])
        if req_errors:
            errors.extend(req_errors)

        state[cfg.validation_errors_key] = errors
        if not errors:
            state["plan"] = state.get(cfg.plan_key)
        return state

    async def repair_node(state: PlanGraphState) -> PlanGraphState:
        system_prompt = cfg.prompt_loader()
        user_payload = cfg.payload_builder(state["request"], state["route_decision"])
        client = get_llm_client()
        raw = await client.repair_json(
            system_prompt,
            state[cfg.raw_output_key],
            state.get(cfg.validation_errors_key, []),
            user_payload,
        )
        state[cfg.raw_output_key] = raw
        state[cfg.repair_attempted_key] = True
        try:
            plan = parse_plan(raw)
            state[cfg.plan_key] = plan
            route_errors = cfg.route_validator(plan, state["route_decision"])
            req_errors = validate_plan_against_request(plan, state["request"])
            all_errors = route_errors + req_errors
            state[cfg.validation_errors_key] = [] if not all_errors else all_errors
        except Exception as e:
            state[cfg.validation_errors_key] = [str(e)]
        return state

    def route_after_validate(
        state: PlanGraphState,
    ) -> Literal["repair", "end", "error"]:
        has_errors = bool(state.get(cfg.validation_errors_key))
        if not has_errors:
            plan = state.get(cfg.plan_key)
            if plan is not None:
                state["plan"] = plan
            return "end"
        if not state.get(cfg.repair_attempted_key, False):
            return "repair"
        return "error"

    # Return the concrete label so the caller can assign it to a name.
    return generate_node, validate_node, repair_node, route_after_validate, cfg.repair_label


# ── Stage instances ─────────────────────────────────────────────────────────

_query_cfg = _IntentStageConfig()
_query_cfg.intent = AgentIntent.QUERY
_query_cfg.prompt_loader = load_query_prompt
_query_cfg.payload_builder = build_query_payload
_query_cfg.route_validator = validate_query_plan_against_route
_query_cfg.raw_output_key = "query_raw_output"
_query_cfg.plan_key = "query_plan"
_query_cfg.validation_errors_key = "query_validation_errors"
_query_cfg.repair_attempted_key = "query_repair_attempted"
_query_cfg.repair_label = "query_repair"

_query_generate, _query_validate, _query_repair, _query_route, _query_repair_label = \
    _make_intent_stage(_query_cfg)

_aggregate_cfg = _IntentStageConfig()
_aggregate_cfg.intent = AgentIntent.AGGREGATE
_aggregate_cfg.prompt_loader = load_aggregate_prompt
_aggregate_cfg.payload_builder = build_aggregate_payload
_aggregate_cfg.route_validator = validate_aggregate_plan_against_route
_aggregate_cfg.raw_output_key = "aggregate_raw_output"
_aggregate_cfg.plan_key = "aggregate_plan"
_aggregate_cfg.validation_errors_key = "aggregate_validation_errors"
_aggregate_cfg.repair_attempted_key = "aggregate_repair_attempted"
_aggregate_cfg.repair_label = "aggregate_repair"

_agg_generate, _agg_validate, _agg_repair, _agg_route, _ = \
    _make_intent_stage(_aggregate_cfg)


# ── Route stage (cannot be unified — unique routing logic) ───────────────────

async def route_node(state: PlanGraphState) -> PlanGraphState:
    """调用 LLM 生成路由决策。"""
    system_prompt = load_route_prompt()
    user_payload = build_user_payload(state["request"])
    client = get_llm_client()
    raw = await client.generate_plan_json(system_prompt, user_payload)
    state["route_raw_output"] = raw
    return state


async def validate_route_node(state: PlanGraphState) -> PlanGraphState:
    """解析并校验路由决策。低置信度 QUERY/AGGREGATE 降级为 CLARIFY。"""
    errors: list[str] = []
    settings = get_settings()

    try:
        route = parse_route_decision(state["route_raw_output"])
        state["route_decision"] = route
    except Exception as e:
        errors.append(str(e))
        state["route_validation_errors"] = errors
        return state

    req_errors = validate_route_decision(route, state["request"])
    if req_errors:
        errors.extend(req_errors)

    if (
        not errors
        and route.intent in (AgentIntent.QUERY, AgentIntent.AGGREGATE)
        and route.confidence < settings.route_confidence_threshold
    ):
        # 降级为 CLARIFY 前校验 clarify.ask capability 是否可用；
        # 若不可用则不降级，保留原校验错误避免假性通过。
        from app.core.planning import _has_capability
        if not _has_capability(state["request"].capabilities, "clarify.ask"):
            errors.append(
                "Low confidence downgrade to CLARIFY is not available: "
                "capability 'clarify.ask' is missing or disabled"
            )
        else:
            state["route_decision"] = RouteDecision(
                intent=AgentIntent.CLARIFY,
                domain=route.domain,
                question="请补充更明确的查询条件，例如具体字段、取值或范围。",
                confidence=route.confidence,
                reason=(
                f"Route confidence {route.confidence} below threshold "
                f"{settings.route_confidence_threshold}"
            ),
        )

    state["route_validation_errors"] = errors
    return state


async def route_repair_node(state: PlanGraphState) -> PlanGraphState:
    """尝试修复无效路由输出，最多一次。"""
    system_prompt = load_route_prompt()
    user_payload = build_user_payload(state["request"])
    client = get_llm_client()
    raw = await client.repair_json(
        system_prompt,
        state["route_raw_output"],
        state.get("route_validation_errors", []),
        user_payload,
    )
    state["route_raw_output"] = raw
    state["route_repair_attempted"] = True
    try:
        route = parse_route_decision(raw)
        state["route_decision"] = route
        req_errors = validate_route_decision(route, state["request"])
        state["route_validation_errors"] = [] if not req_errors else req_errors
    except Exception as e:
        state["route_validation_errors"] = [str(e)]
    return state


def route_after_validate_route(
    state: PlanGraphState,
) -> Literal["route_repair", "clarify_end", "query", "aggregate", "error"]:
    """路由校验后的分支决策。"""
    has_errors = bool(state.get("route_validation_errors"))
    if has_errors:
        if not state.get("route_repair_attempted", False):
            return "route_repair"
        return "error"

    route = state.get("route_decision")
    if route is not None and route.intent == AgentIntent.CLARIFY:
        return "clarify_end"
    if route is not None and route.intent == AgentIntent.QUERY:
        return "query"
    if route is not None and route.intent == AgentIntent.AGGREGATE:
        return "aggregate"
    return "error"


async def clarify_end_node(state: PlanGraphState) -> PlanGraphState:
    """从路由决策直接构造 CLARIFY AgentPlan。"""
    route = state["route_decision"]
    plan = build_clarify_plan(state["request"].request_id, route)
    state["plan"] = plan
    return state


# ── Re-exports for test backward compat ─────────────────────────────────────
# test_graph.py imports these names directly. Export the factory-generated
# functions so existing test code compiles without change.
validate_query_node = _query_validate

# Map factory's generic "repair" label back to legacy "query_repair"/"aggregate_repair"
# for graph edge routing and test backward compat. The LangGraph conditional
# edges use these literal strings.
def _query_route_with_label(state):
    r = _query_route(state)
    return _query_repair_label if r == "repair" else r

route_after_validate_query = _query_route_with_label

def _agg_route_with_label(state):
    r = _agg_route(state)
    return "aggregate_repair" if r == "repair" else r

def build_plan_graph() -> "CompiledStateGraph":
    """构建 route/query/aggregate 分层的 LangGraph 图并编译。"""
    builder = StateGraph(PlanGraphState)

    # Route stage
    builder.add_node("route", route_node)
    builder.add_node("validate_route", validate_route_node)
    builder.add_node("route_repair", route_repair_node)
    builder.add_node("clarify_end", clarify_end_node)

    # Query stage (factory-generated)
    builder.add_node("query", _query_generate)
    builder.add_node("validate_query", _query_validate)
    builder.add_node("query_repair", _query_repair)

    # Aggregate stage (factory-generated)
    builder.add_node("aggregate", _agg_generate)
    builder.add_node("validate_aggregate", _agg_validate)
    builder.add_node("aggregate_repair", _agg_repair)

    # Edges
    builder.add_edge(START, "route")
    builder.add_edge("route", "validate_route")
    builder.add_conditional_edges(
        "validate_route",
        route_after_validate_route,
        {
            "route_repair": "route_repair",
            "clarify_end": "clarify_end",
            "query": "query",
            "aggregate": "aggregate",
            "error": END,
        },
    )
    builder.add_edge("route_repair", "validate_route")
    builder.add_edge("clarify_end", END)

    # Query loop: generate → validate → repair → validate
    builder.add_edge("query", "validate_query")
    builder.add_conditional_edges(
        "validate_query",
        _query_route_with_label,
        {"query_repair": "query_repair", "end": END, "error": END},
    )
    builder.add_edge("query_repair", "validate_query")

    # Aggregate loop: generate → validate → repair → validate
    builder.add_edge("aggregate", "validate_aggregate")
    builder.add_conditional_edges(
        "validate_aggregate",
        _agg_route_with_label,
        {"aggregate_repair": "aggregate_repair", "end": END, "error": END},
    )
    builder.add_edge("aggregate_repair", "validate_aggregate")

    return builder.compile()


@lru_cache
def get_plan_graph() -> "CompiledStateGraph":
    """缓存单例的 plan graph 工厂函数。"""
    return build_plan_graph()
