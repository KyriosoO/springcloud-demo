"""当前运行时契约模型再导出层。

生成模型是规范结构契约。本模块只暴露运行时代码消费的当前路由/计划传输对象。
"""

from pydantic import BaseModel as StrictModel
from pydantic import TypeAdapter, ValidationError

from app.contracts.generated_models import (  # noqa: F401
    AgentAggregateSpec as AgentAggregateSpec,
    AgentDomainMode as AgentDomainMode,
    AgentFieldType as AgentFieldType,
    AgentFilter as AgentFilter,
    AgentOperator as AgentOperator,
    AgentPlanKind as AgentPlanKind,
    AgentQuerySpec as AgentQuerySpec,
    AggregateAgentPlan as AggregateAgentPlan,
    AggregateFunction as AggregateFunction,
    AggregateMetricSpec as AggregateMetricSpec,
    AggregateOrderSpec as AggregateOrderSpec,
    CapabilityChoiceArgs as CapabilityChoiceArgs,
    ClarificationArgType as ClarificationArgType,
    ClarificationReasonCode as ClarificationReasonCode,
    ClarificationRequired as ClarificationRequired,
    Direction as Direction,
    DomainChoiceArgs as DomainChoiceArgs,
    ExecutablePlan as ExecutablePlan,
    FieldForbiddenArgs as FieldForbiddenArgs,
    FieldChoiceArgs as FieldChoiceArgs,
    PlanOutcome as PlanOutcome,
    PlanRequest as PlanRequest,
    QueryAgentPlan as QueryAgentPlan,
    QueryContextMode as QueryContextMode,
    RouteDecision as RouteDecision,
    RouteOutcome as RouteOutcome,
    RouteRequest as RouteRequest,
    RuntimeAggregateContextView as RuntimeAggregateContextView,
    RuntimeCapabilityRoutingDescriptor as RuntimeCapabilityRoutingDescriptor,
    RuntimeContextType as RuntimeContextType,
    RuntimeDomainFieldSchema as RuntimeDomainFieldSchema,
    RuntimeDomainRoutingProjection as RuntimeDomainRoutingProjection,
    RuntimeDomainSchema as RuntimeDomainSchema,
    RuntimeErrorCode as RuntimeErrorCode,
    RuntimeErrorResponse as RuntimeErrorResponse,
    RuntimeOperationMetadata as RuntimeOperationMetadata,
    RuntimeOperationType as RuntimeOperationType,
    RuntimeOutcomeType as RuntimeOutcomeType,
    RuntimeProfileBehaviorProjection as RuntimeProfileBehaviorProjection,
    RuntimeQueryContextView as RuntimeQueryContextView,
    RuntimeTerminationReason as RuntimeTerminationReason,
    RuntimeTurnProjection as RuntimeTurnProjection,
    RuntimeTurnRole as RuntimeTurnRole,
    ValueChoiceArgs as ValueChoiceArgs,
)


def unwrap_root(value):
    """返回生成根模型包装结构中的具体联合成员。"""
    return getattr(value, "root", value)


def validate_route_outcome(payload: object):
    return unwrap_root(TypeAdapter(RouteOutcome).validate_python(payload))


def validate_plan_outcome(payload: object):
    return unwrap_root(TypeAdapter(PlanOutcome).validate_python(payload))
