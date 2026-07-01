"""
Pydantic contract models — re-export layer.
Generated models are the canonical structural contract.
This file re-exports them under the original class names and
semantic validators that cannot be expressed in OpenAPI/JSON Schema.

Explicit semantic checks must be called at the appropriate entry points:
  - validate_agent_plan_semantics() → parse_plan() in planning.py
  - validate_plan_generate_request_semantics() → generate_plan() in runtime_api.py

model_validate() does NOT trigger __init__, so monkey-patching __init__ is
intentionally absent from this file. Do NOT re-add monkey-patches.
"""

# ── Generated structural contract (canonical) ──────────────────
from app.contracts.generated_models import (      # noqa: F401
    AgentAggregateSpec as AgentAggregateSpec,
    AgentCapabilityDescriptor as AgentCapabilityDescriptor,
    AgentCapabilityExecutionMode as AgentCapabilityExecutionMode,
    AgentCapabilityRiskLevel as AgentCapabilityRiskLevel,
    AgentErrorCode as AgentErrorCode,
    AgentFieldType as AgentFieldType,
    AgentFilter as AgentFilter,
    AgentIntent as AgentIntent,
    AgentOperator as AgentOperator,
    AgentPlan as AgentPlan,
    AgentQuerySpec as AgentQuerySpec,
    AgentResponseType as AgentResponseType,
    AggregateFunction as AggregateFunction,
    AggregateMetricSpec as AggregateMetricSpec,
    AggregateOrderSpec as AggregateOrderSpec,
    CapabilityContextSpec as CapabilityContextSpec,
    CapabilityContractRef as CapabilityContractRef,
    CapabilityDomainScope as CapabilityDomainScope,
    ClarifySpec as ClarifySpec,
    PlanGenerateRequest as PlanGenerateRequest,
    PlanGenerateResponse as PlanGenerateResponse,
    RuntimeAggregateContext as RuntimeAggregateContext,
    RuntimeDomainSchema as RuntimeDomainSchema,
    RuntimeErrorResponse as RuntimeErrorResponse,
    RuntimeFieldSchema as RuntimeFieldSchema,
    RuntimeQueryContext as RuntimeQueryContext,
    RuntimeRole as RuntimeRole,
    RuntimeTurn as RuntimeTurn,
    QueryContextMode as QueryContextMode,
)

# ── Compatibility aliases for legacy import names ─────────────
AggregateSpec = AgentAggregateSpec
from pydantic import BaseModel as StrictModel  # noqa: E402

# ── Re-export Pydantic's ValidationError for test backward compat ──
from pydantic import ValidationError as ValidationError  # noqa: E402

# ── Runtime semantic validators (hand-written) ─────────────────
from app.contracts.semantic_validators import (  # noqa: E402
    validate_agent_plan_intent_shape,
    validate_agent_filter_shape,
    validate_aggregate_metric_function_field,
    validate_metric_aliases_unique,
    validate_agent_plan_semantics,
    validate_plan_generate_request_semantics,
    validate_capability_descriptors,
)
