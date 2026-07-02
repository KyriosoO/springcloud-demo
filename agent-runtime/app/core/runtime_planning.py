"""当前 D03 契约的路由/计划运行时操作。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.contracts.models import (
    ClarificationRequired,
    ExecutablePlan,
    PlanOutcome,
    PlanRequest,
    RouteDecision,
    RouteOutcome,
    RouteRequest,
    RuntimeOperationMetadata,
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
    outcome = validate_route_outcome(payload)
    _assert_request_id(outcome.request_id, request.request_id)
    return outcome


def _parse_plan(raw: str, request: PlanRequest) -> ExecutablePlan | ClarificationRequired:
    payload = _json_object(raw)
    outcome = validate_plan_outcome(payload)
    _assert_request_id(outcome.request_id, request.request_id)
    return outcome


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
