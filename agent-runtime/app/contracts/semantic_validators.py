"""
Semantic validators for Agent plan models.
Hand-written rules that cannot be expressed in OpenAPI/JSON Schema:
intent shape, operator/value mutual exclusion, metric alias uniqueness, etc.

These validators are called EXPLICITLY in parse_plan(), runtime_api.py,
and model __init__ monkey-patches. Do NOT rely on Pydantic model_validator —
model_validate() bypasses __init__ and therefore bypasses monkey-patches.
"""

from app.contracts import generated_models as g


def validate_agent_plan_semantics(plan: g.AgentPlan) -> None:
    """Unified semantic validation for any AgentPlan regardless of intent.
    Called explicitly in parse_plan() so model_validate() paths are covered.
    Raises ValueError if any constraint is violated.
    """
    validate_agent_plan_intent_shape(plan)
    if plan.query is not None and plan.query.filters:
        for f in plan.query.filters:
            validate_agent_filter_shape(f)
    if plan.aggregate is not None:
        validate_metric_aliases_unique(plan.aggregate)
        for m in plan.aggregate.metrics:
            validate_aggregate_metric_function_field(m)
        if plan.aggregate.filters:
            for f in plan.aggregate.filters:
                validate_agent_filter_shape(f)


def validate_plan_generate_request_semantics(req: g.PlanGenerateRequest) -> None:
    """Check domainSchemas uniqueness and capability descriptors.
    Called at the FastAPI endpoint entry so invalid requests get 400."""
    # domainSchemas 域唯一性
    if req.domain_schemas:
        seen = set()
        for s in req.domain_schemas:
            if s.domain in seen:
                raise ValueError("Duplicate domain in domainSchemas: %s" % s.domain)
            seen.add(s.domain)
    # capabilities 校验
    validate_capability_descriptors(req)


def validate_agent_plan_intent_shape(plan: g.AgentPlan) -> None:
    """Validate QUERY/CLARIFY/AGGREGATE intent shape constraints.

    Raises ValueError if the constraint is violated.
    These checks cannot be expressed in static OpenAPI schema.
    """
    if plan.intent == g.AgentIntent.query:
        if plan.query is None or plan.clarify is not None or plan.aggregate is not None:
            raise ValueError("QUERY requires query and forbids clarify and aggregate")
        if plan.domain is None:
            raise ValueError("QUERY requires a non-null domain")
    elif plan.intent == g.AgentIntent.clarify:
        if plan.clarify is None or plan.query is not None or plan.aggregate is not None:
            raise ValueError("CLARIFY requires clarify and forbids query and aggregate")
    elif plan.intent == g.AgentIntent.aggregate:
        if plan.aggregate is None or plan.query is not None or plan.clarify is not None:
            raise ValueError("AGGREGATE requires aggregate and forbids query and clarify")
        if plan.domain is None:
            raise ValueError("AGGREGATE requires a non-null domain")


def validate_agent_filter_shape(af: g.AgentFilter) -> None:
    """Validate multi-value operators use values, single-value/range use value."""
    multi_value = {g.AgentOperator.in_, g.AgentOperator.contains_any, g.AgentOperator.starts_with_any}
    if af.operator in multi_value:
        if af.value is not None or not af.values:
            raise ValueError(f"{af.operator.value} requires non-empty values and no value")
        if any(not it.strip() or len(it.strip()) > 256 for it in af.values):
            raise ValueError(f"{af.operator.value} values must contain 1 to 256 non-blank characters")
    else:
        if af.values is not None or af.value is None or not af.value.strip():
            raise ValueError(f"{af.operator.value} requires a non-empty value and no values")


def validate_aggregate_metric_function_field(m: g.AggregateMetricSpec) -> None:
    """COUNT must not specify field; SUM/AVG/MIN/MAX requires a field."""
    if m.function == g.AggregateFunction.count and m.field is not None:
        raise ValueError("COUNT must not specify a field")
    if m.function != g.AggregateFunction.count and m.field is None:
        raise ValueError(f"{m.function.value} requires a field")


def validate_metric_aliases_unique(agg_spec: g.AgentAggregateSpec) -> None:
    """All metric aliases must be unique."""
    aliases = [m.alias for m in agg_spec.metrics]
    if len(set(aliases)) != len(aliases):
        raise ValueError("metric alias must be unique")


def validate_capability_descriptors(req: g.PlanGenerateRequest) -> None:
    """校验 capabilities 字段的结构和契约规则。

    首期强契约（未投产阶段，无 nullable 兼容窗口）：
    - capabilities 必须非 None（Pydantic 已由 @NotNull + required 强制）
    - capabilityId 唯一
    - domainScopes 非 null
    - query.search 至少有一个 enabled=true scope
    - aggregate.compute 出现时至少有一个 enabled=true scope
    - clarify.ask 的 domainScopes 为空或全部 disabled
    - 同一 capability 内 domainScopes[*].domain 不重复
    - enabled=true 的 domain 必须存在于 request.domainSchemas[*].domain 中
    """
    caps = req.capabilities
    if not caps:
        # capabilities == []：Java 声明当前无可用 capability，禁止推断额外能力
        return

    cap_ids: set[str] = set()
    config_domains = {s.domain for s in req.domain_schemas}

    for c in caps:
        # capabilityId 唯一
        if c.capability_id in cap_ids:
            raise ValueError("Duplicate capabilityId: %s" % c.capability_id)
        cap_ids.add(c.capability_id)

        # domainScopes 必须非 null（Pydantic 已强制，此处兜底）
        scopes = c.domain_scopes or []
        scope_domains: set[str] = set()
        for ds in scopes:
            # domain 唯一性检查覆盖全部条目（含 disabled），避免同一 domain 出现多条记录
            if ds.domain in scope_domains:
                raise ValueError(
                    "Duplicate domain '%s' in capability %s domainScopes" % (ds.domain, c.capability_id))
            scope_domains.add(ds.domain)
            if ds.enabled:
                if ds.domain not in config_domains:
                    raise ValueError(
                        "Capability %s domain '%s' not found in domainSchemas" % (c.capability_id, ds.domain))

    # query.search: QUERY capability 至少有一个 enabled scope
    _require_query_scope(caps)

    # aggregate.compute: 出现时必须至少有一个 enabled scope
    _require_aggregate_scope(caps)

    # clarify.ask: domainScopes 必须为空
    for c in caps:
        if c.capability_id == "clarify.ask":
            if any(ds.enabled for ds in (c.domain_scopes or [])):
                raise ValueError("clarify.ask must not have enabled domainScopes")


def _require_query_scope(caps: list) -> None:
    """query.search 必须存在且至少有一个 enabled domain scope。"""
    for c in caps:
        if c.capability_id == "query.search":
            if not any(ds.enabled for ds in (c.domain_scopes or [])):
                raise ValueError("query.search requires at least one enabled domain scope")
            return
    raise ValueError("query.search capability is required")


def _require_aggregate_scope(caps: list) -> None:
    """aggregate.compute 如果存在，必须至少有一个 enabled domain scope。"""
    for c in caps:
        if c.capability_id == "aggregate.compute":
            if not any(ds.enabled for ds in (c.domain_scopes or [])):
                raise ValueError("aggregate.compute requires at least one enabled domain scope")
            return
