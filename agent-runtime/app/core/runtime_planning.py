"""当前 D03 契约的路由/计划运行时操作。"""

from __future__ import annotations

import json
import time
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
REPAIR_SYSTEM_PROMPT = """You repair invalid Agent Runtime JSON output.

Return one JSON object only. Do not use Markdown.
The repaired object must match the Runtime contract for the requestData operation.
Echo requestData.requestId exactly. Use only fields, operators, domains, and capabilities present in requestData.
If the requested field is not available in requestData.domainSchema.fields, return a FIELD_FORBIDDEN clarification instead of inventing fields.
"""


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
        prompt = _plan_prompt(request.plan_kind.value)
        request_payload = request.model_dump(by_alias=True, mode="json", exclude_none=False)
        raw = await self._llm_client.generate_plan_json(
            _prompt(prompt),
            request_payload,
        )
        try:
            return _parse_plan(raw, request)
        except (ValueError, ValidationError) as exc:
            return await self._repair_plan(raw, exc, request, request_payload)

    async def _repair_plan(
        self,
        raw: str,
        original_error: Exception,
        request: PlanRequest,
        request_payload: dict[str, Any],
    ) -> ExecutablePlan | ClarificationRequired:
        if request.repair_limit <= 0:
            raise RuntimePlanError(
                "CONTRACT_INVALID",
                "Plan output does not match Runtime contract",
                request_id=request.request_id,
            ) from original_error
        started = time.perf_counter()
        repaired = await self._llm_client.repair_json(
            REPAIR_SYSTEM_PROMPT,
            raw,
            [_validation_error(original_error)],
            request_payload,
        )
        repair_ms = max(0, int((time.perf_counter() - started) * 1000))
        try:
            outcome = _parse_plan(repaired, request)
            _mark_repaired(outcome, "PLAN", repair_ms)
            return outcome
        except (ValueError, ValidationError) as exc:
            raise RuntimePlanError(
                "OUTPUT_REPAIR_EXHAUSTED",
                "Plan output repair attempts were exhausted",
                request_id=request.request_id,
            ) from exc


def _parse_route(raw: str, request: RouteRequest) -> RouteDecision | ClarificationRequired:
    payload = _json_object(raw)
    outcome = validate_route_outcome(payload)
    _assert_request_id(outcome.request_id, request.request_id)
    return outcome


def _parse_plan(raw: str, request: PlanRequest) -> ExecutablePlan | ClarificationRequired:
    payload = _json_object(raw)
    _normalize_present_request_id(payload, request.request_id)
    outcome = validate_plan_outcome(payload)
    _assert_request_id(outcome.request_id, request.request_id)
    return outcome


def _plan_prompt(plan_kind: str) -> str:
    return {
        "QUERY": "query_system.md",
        "AGGREGATE": "aggregate_system.md",
        "DOCUMENT": "document_system.md",
    }.get(plan_kind, "query_system.md")


def _json_object(raw: str) -> dict[str, Any]:
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("LLM output must be a JSON object")
    return parsed


def _assert_request_id(actual: str, expected: str) -> None:
    if actual != expected:
        raise ValueError("requestId mismatch")


def _normalize_present_request_id(payload: dict[str, Any], expected: str) -> None:
    actual = payload.get("requestId")
    if isinstance(actual, str) and actual != expected:
        payload["requestId"] = expected


def _mark_repaired(outcome: ExecutablePlan | ClarificationRequired, operation: str, repair_ms: int) -> None:
    metadata = outcome.metadata
    metadata.operation = operation
    metadata.provider_attempts = 2
    metadata.repair_attempts = 1
    metadata.repair_duration_ms = repair_ms
    metadata.total_duration_ms = max(metadata.total_duration_ms or 0, repair_ms)
    metadata.repair_limit_reached = False


def _validation_error(error: Exception) -> str:
    return str(error)[:1000]


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
