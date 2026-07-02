"""当前 D03 契约的路由/计划运行时操作。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.contracts.models import (
    AggregateAgentPlan,
    ClarificationRequired,
    DomainChoiceArgs,
    ExecutablePlan,
    PlanOutcome,
    PlanRequest,
    QueryAgentPlan,
    RouteDecision,
    RouteOutcome,
    RouteRequest,
    RuntimeOperationMetadata,
    RuntimeOperationType,
    RuntimeTerminationReason,
    validate_plan_outcome,
    validate_route_outcome,
)
from app.core.errors import RuntimePlanError
from app.core.llm_client import LlmClient, get_llm_client

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


def _prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


class RuntimeRoutePlanner:
    def __init__(self, llm_client: LlmClient):
        self._llm_client = llm_client

    async def route(self, request: RouteRequest) -> RouteDecision | ClarificationRequired:
        raw = await self._llm_client.generate_plan_json(
            _prompt("route_system.md"),
            request.model_dump(by_alias=True, mode="json", exclude_none=False),
        )
        try:
            return _parse_route(raw, request)
        except (ValueError, ValidationError) as exc:
            raise RuntimePlanError(
                "CONTRACT_INVALID",
                "Route output does not match Runtime contract",
                request_id=request.request_id,
            ) from exc


class RuntimePlanPlanner:
    def __init__(self, llm_client: LlmClient):
        self._llm_client = llm_client

    async def plan(self, request: PlanRequest) -> ExecutablePlan | ClarificationRequired:
        prompt = "aggregate_system.md" if request.plan_kind.value == "AGGREGATE" else "query_system.md"
        raw = await self._llm_client.generate_plan_json(
            _prompt(prompt),
            request.model_dump(by_alias=True, mode="json", exclude_none=False),
        )
        try:
            return _parse_plan(raw, request)
        except (ValueError, ValidationError) as exc:
            raise RuntimePlanError(
                "CONTRACT_INVALID",
                "Plan output does not match Runtime contract",
                request_id=request.request_id,
            ) from exc


def _parse_route(raw: str, request: RouteRequest) -> RouteDecision | ClarificationRequired:
    payload = _json_object(raw)
    if "outcomeType" in payload:
        outcome = validate_route_outcome(payload)
    else:
        outcome = _legacy_route_to_outcome(payload, request)
    _assert_request_id(outcome.request_id, request.request_id)
    return outcome


def _parse_plan(raw: str, request: PlanRequest) -> ExecutablePlan | ClarificationRequired:
    payload = _json_object(raw)
    if "outcomeType" in payload:
        outcome = validate_plan_outcome(payload)
    else:
        outcome = _legacy_plan_to_outcome(payload, request)
    _assert_request_id(outcome.request_id, request.request_id)
    return outcome


def _legacy_route_to_outcome(payload: dict[str, Any], request: RouteRequest) -> RouteDecision | ClarificationRequired:
    intent = str(payload.get("intent", "")).upper()
    if intent == "CLARIFY":
        domains = [item.domain for item in request.domains]
        args = DomainChoiceArgs(argType="DOMAIN_CHOICES", domains=domains[:20] or ["unknown"])
        return ClarificationRequired(
            outcomeType="CLARIFICATION",
            requestId=request.request_id,
            reasonCode="DOMAIN_AMBIGUOUS" if len(domains) > 1 else "DOMAIN_REQUIRED",
            args=args,
            metadata=_metadata("ROUTE", "CLARIFICATION"),
        )
    plan_kind = "AGGREGATE" if intent == "AGGREGATE" else "QUERY"
    capability = next(
        (item for item in request.capabilities if item.plan_kind.value == plan_kind),
        None,
    )
    if capability is None:
        raise ValueError(f"no capability for plan kind: {plan_kind}")
    domain = payload.get("domain")
    return RouteDecision(
        outcomeType="DECISION",
        requestId=request.request_id,
        capabilityId=capability.capability_id,
        domain=domain,
        metadata=_metadata("ROUTE", "COMPLETED"),
    )


def _legacy_plan_to_outcome(payload: dict[str, Any], request: PlanRequest) -> ExecutablePlan | ClarificationRequired:
    if str(payload.get("intent", "")).upper() == "CLARIFY":
        domain = request.domain or (request.domain_schema.domain if request.domain_schema else "unknown")
        args = DomainChoiceArgs(argType="DOMAIN_CHOICES", domains=[domain])
        return ClarificationRequired(
            outcomeType="CLARIFICATION",
            requestId=request.request_id,
            reasonCode="DOMAIN_REQUIRED",
            args=args,
            metadata=_metadata("PLAN", "CLARIFICATION"),
        )
    if request.plan_kind.value == "AGGREGATE":
        plan = AggregateAgentPlan(planKind="AGGREGATE", aggregate=payload["aggregate"])
    else:
        plan = QueryAgentPlan(planKind="QUERY", query=payload["query"])
    return ExecutablePlan(
        outcomeType="EXECUTABLE",
        requestId=request.request_id,
        plan=plan,
        metadata=_metadata("PLAN", "COMPLETED"),
    )


def _json_object(raw: str) -> dict[str, Any]:
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("LLM output must be a JSON object")
    return parsed


def _assert_request_id(actual: str, expected: str) -> None:
    if actual != expected:
        raise ValueError("requestId mismatch")


def _metadata(operation: str, termination: str) -> RuntimeOperationMetadata:
    return RuntimeOperationMetadata(
        operation=operation,
        providerAttempts=1,
        repairAttempts=0,
        repairDurationMs=0,
        totalDurationMs=1,
        terminationReason=termination,
        deadlineReached=False,
        repairLimitReached=False,
    )


@lru_cache
def get_route_planner() -> RuntimeRoutePlanner:
    return RuntimeRoutePlanner(get_llm_client())


@lru_cache
def get_plan_planner() -> RuntimePlanPlanner:
    return RuntimePlanPlanner(get_llm_client())
