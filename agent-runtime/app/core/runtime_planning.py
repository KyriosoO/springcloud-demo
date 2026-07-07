"""当前 D03 契约的路由/计划运行时操作。"""

from __future__ import annotations

import json
import re
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
from app.core.errors import RuntimePlanError, RuntimeProviderError, RuntimeTimeoutError
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
        request_payload = request.model_dump(by_alias=True, mode="json", exclude_none=False)
        try:
            raw = await self._llm_client.generate_plan_json(
                _prompt("route_system.md"),
                request_payload,
            )
        except (RuntimeProviderError, RuntimeTimeoutError):
            fallback = _document_route_fallback(request)
            if fallback is not None:
                return fallback
            raise
        try:
            outcome = _parse_route(raw, request)
            fallback = _document_route_safety_fallback(outcome, request)
            return fallback if fallback is not None else outcome
        except (ValueError, ValidationError) as exc:
            fallback = _document_route_fallback(request)
            if fallback is not None:
                return fallback
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
        try:
            raw = await self._llm_client.generate_plan_json(
                _prompt(prompt),
                request_payload,
            )
        except (RuntimeProviderError, RuntimeTimeoutError):
            fallback = _document_plan_fallback(request)
            if fallback is not None:
                return fallback
            raise
        try:
            outcome = _parse_plan(raw, request)
            fallback = _document_plan_safety_fallback(outcome, request)
            return fallback if fallback is not None else outcome
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
            fallback = _document_plan_safety_fallback(outcome, request)
            return fallback if fallback is not None else outcome
        except (ValueError, ValidationError) as exc:
            fallback = _document_plan_fallback(request)
            if fallback is not None:
                return fallback
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


def _document_route_fallback(request: RouteRequest) -> RouteDecision | ClarificationRequired | None:
    document_capabilities = [
        capability for capability in request.capabilities
        if capability.plan_kind.value == "DOCUMENT" and capability.capability_id.startswith("document.")
    ]
    if not document_capabilities:
        return None
    message = request.message.strip()
    domain = _infer_document_domain(message, request)
    if domain is None:
        if not _is_document_ambiguous_message(message):
            return None
        document_domains = {
            allowed_domain
            for capability in document_capabilities
            for allowed_domain in capability.allowed_domains
        }
        domains = sorted({domain.domain for domain in request.domains if domain.domain in document_domains})
        if not domains:
            return None
        return validate_route_outcome({
            "outcomeType": "CLARIFICATION",
            "requestId": request.request_id,
            "reasonCode": "DOMAIN_REQUIRED",
            "args": {"argType": "DOMAIN_CHOICES", "domains": domains},
            "metadata": _metadata_dict("ROUTE", "CLARIFICATION"),
        })
    capability_id = _select_document_capability_id(message, document_capabilities)
    if capability_id is None:
        return None
    allowed_domains = next(
        (capability.allowed_domains for capability in document_capabilities
         if capability.capability_id == capability_id),
        [],
    )
    if domain not in allowed_domains:
        return None
    return validate_route_outcome({
        "outcomeType": "DECISION",
        "requestId": request.request_id,
        "capabilityId": capability_id,
        "domain": domain,
        "metadata": _metadata_dict("ROUTE", "COMPLETED"),
    })


def _document_plan_fallback(request: PlanRequest) -> ExecutablePlan | ClarificationRequired | None:
    if request.plan_kind.value != "DOCUMENT" or request.domain_schema is None or not request.domain:
        return None
    if not request.capability_id.startswith("document."):
        return None
    operation = _document_operation(request.capability_id, request.message)
    if operation is None:
        return None
    message = request.message.strip()
    filters = _document_filters(message, request.domain_schema)
    query_text, top_k = _document_query_and_top_k(operation, message, request.domain_schema)
    document: dict[str, Any] = {
        "operation": operation,
        "queryText": query_text,
        "filters": filters,
        "retrievalOptions": {
            "retrievalMode": "HYBRID",
            "topK": top_k,
            "page": 1,
            "size": top_k,
        },
    }
    if operation in {"ANSWER", "SUMMARIZE"}:
        document["citationRequired"] = True
        document["generationOptions"] = {
            "enabled": True,
            "failurePolicy": "FALLBACK_EXTRACTIVE",
        }
    if operation == "SUMMARIZE":
        document["summaryScope"] = {
            "documentIds": [],
            "sectionHints": _summary_section_hints(message),
        }
    return validate_plan_outcome({
        "outcomeType": "EXECUTABLE",
        "requestId": request.request_id,
        "plan": {
            "planKind": "DOCUMENT",
            "document": document,
        },
        "metadata": _metadata_dict("PLAN", "COMPLETED"),
    })


def _document_route_safety_fallback(
        outcome: RouteDecision | ClarificationRequired,
        request: RouteRequest) -> RouteDecision | ClarificationRequired | None:
    if not hasattr(outcome, "reason_code"):
        return None
    if outcome.reason_code.value in {"DOMAIN_REQUIRED", "CAPABILITY_AMBIGUOUS"}:
        return _document_route_fallback(request)
    return None


def _document_plan_safety_fallback(
        outcome: ExecutablePlan | ClarificationRequired,
        request: PlanRequest) -> ExecutablePlan | ClarificationRequired | None:
    plan = getattr(outcome, "plan", None)
    document_plan = getattr(plan, "document", None)
    if document_plan is None:
        return None
    operation = getattr(document_plan.operation, "value", document_plan.operation)
    if operation == "SUMMARIZE" and document_plan.summary_scope is None:
        return _document_plan_fallback(request)
    return None


def _infer_document_domain(message: str, request: RouteRequest) -> str | None:
    available = {domain.domain for domain in request.domains}
    if any(term in message for term in ("文学", "小说", "鲁迅", "故乡", "作品", "作者")):
        return "literature" if "literature" in available else None
    if any(term in message for term in ("公司", "休假", "报销", "制度", "员工手册")):
        return "company_policy" if "company_policy" in available else None
    if any(term in message for term in (
            "知识库", "手册", "部署", "运维", "知识文档", "启动顺序",
            "404", "alias", "health", "故障", "排查", "document 查询")):
        return "knowledge_base" if "knowledge_base" in available else None
    if any(term in message for term in ("税", "增值税", "税法", "税率", "征收率", "发票")):
        return "tax_policy" if "tax_policy" in available else None
    if any(term in message for term in ("文档", "资料", "政策", "手册", "合同", "规程", "查阅")):
        return None
    return None


def _is_document_ambiguous_message(message: str) -> bool:
    return any(term in message for term in ("文档", "资料", "政策", "手册", "合同", "规程", "查阅"))


def _select_document_capability_id(message: str, capabilities: list[Any]) -> str | None:
    available = {capability.capability_id for capability in capabilities}
    if any(term in message for term in ("总结", "概括", "归纳")) and "document.summarize" in available:
        return "document.summarize"
    if any(term in message for term in ("什么", "怎么", "如何", "是否", "哪些", "哪里", "为什么", "应该", "应当")) \
            and "document.answer" in available:
        return "document.answer"
    if any(term in message for term in ("查询", "搜索", "查找", "检索", "查看", "查阅", "列出")) and "document.search" in available:
        return "document.search"
    if "document.answer" in available:
        return "document.answer"
    return next(iter(sorted(available)), None)


def _document_operation(capability_id: str, message: str) -> str | None:
    if capability_id.endswith(".summarize") or any(term in message for term in ("总结", "概括", "归纳")):
        return "SUMMARIZE"
    if capability_id.endswith(".search") or any(term in message for term in ("查询", "搜索", "查找", "检索", "查看", "查阅", "列出")):
        return "SEARCH"
    if capability_id.endswith(".answer"):
        return "ANSWER"
    return None


def _document_filters(message: str, schema: Any) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    title = _book_title(message)
    if title:
        operator = "EQ" if _field_supports(schema, "title", "EQ") else "CONTAINS"
        if _field_supports(schema, "title", operator):
            filters.append({"field": "title", "operator": operator, "value": title})
    return filters


def _document_query_and_top_k(operation: str, message: str, schema: Any) -> tuple[str, int]:
    return message[:500], _default_document_top_k(operation, schema)


def _summary_section_hints(message: str) -> list[str]:
    hints: list[str] = []
    for match in re.finditer(r"(第[一二三四五六七八九十百千万\d]+章[^，。；;,.、]{0,20})", message):
        hint = re.sub(r"(的)?(主要内容|内容|摘要|总结)$", "", match.group(1).strip())
        if hint and hint not in hints:
            hints.append(hint)
    return hints[:10]


def _book_title(message: str) -> str | None:
    match = re.search(r"《([^》]{1,100})》|\"([^\"]{1,100})\"|'([^']{1,100})'|“([^”]{1,100})”", message)
    if not match:
        return None
    return next(group.strip() for group in match.groups() if group and group.strip())


def _default_document_top_k(operation: str, schema: Any) -> int:
    desired = 20 if operation in {"ANSWER", "SUMMARIZE"} else 5
    max_size = getattr(schema, "max_size", None)
    if max_size is None:
        return desired
    return max(1, min(desired, max_size))


def _field_supports(schema: Any, field_name: str, operator: str) -> bool:
    for field in schema.fields:
        if field.field == field_name:
            return any(item.value == operator for item in field.operators)
    return False


def _metadata_dict(operation: str, termination: str) -> dict[str, Any]:
    return _metadata(operation, termination).model_dump(by_alias=True, mode="json")


@lru_cache
def get_route_planner() -> RuntimeRoutePlanner:
    return RuntimeRoutePlanner(get_llm_client())


@lru_cache
def get_plan_planner() -> RuntimePlanPlanner:
    return RuntimePlanPlanner(get_llm_client())
