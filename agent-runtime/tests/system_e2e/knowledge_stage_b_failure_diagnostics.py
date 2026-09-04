"""KB-DIAG-001: test-process-only observation AFTER production rejection."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace
from unittest.mock import patch

from agent_runtime.knowledge.rewrite_v4 import KnowledgeRewriteTaskV4
from agent_runtime.model.contracts import InvalidModelOutput, ModelTransportError, StructuredFinishKind
from agent_runtime.model.deepseek.json_codec import parse_unique_json_object
from agent_runtime.model.deepseek.transport import DeepSeekChatTransport

VERSION = "stage-b-failure-diagnostics-v1"
TASKS = {"action_selection": "action-selection-v4", "knowledge_rewrite": "4", "knowledge_summary": "4"}
PROVIDER_CODES = frozenset("model." + item for item in (
    "provider_response_mismatch", "provider_choices_invalid", "provider_choice_invalid",
    "provider_finish_reason_invalid", "provider_message_invalid", "provider_content_invalid",
    "provider_tool_calls_invalid", "provider_tool_call_invalid", "provider_usage_invalid",
    "provider_content_type_invalid", "provider_content_encoding_invalid", "provider_response_too_large",
    "json_non_finite_number", "json_duplicate_key", "json_invalid_unicode", "json_bytes_exceeded",
    "json_invalid_utf8", "json_type_invalid", "json_invalid", "json_object_required",
))
JSON_CODES = frozenset(code for code in PROVIDER_CODES if code.startswith("model.json_"))
TASK_CODES = JSON_CODES | frozenset({"response_shape_invalid", "top_level_contract_invalid",
    "outcome_invalid", "queries_contract_invalid", "missing_conditions_invalid", "task_contract_invalid"})
GATEWAY_CODES = frozenset({"input_denied", "provider_timeout", "provider_failure", "invalid_output",
                           "cancelled", "unknown_failure"})
REASONS = {"provider": PROVIDER_CODES | {"provider_invalid_output", "provider_timeout", "provider_failure", "cancelled"},
           "task_decoder": TASK_CODES, "gateway": GATEWAY_CODES}
_active = ContextVar("stage_b_diagnostics", default=None)


def validate_rows(rows):
    if type(rows) is not list or len(rows) > 3:
        raise ValueError("stage_b.diagnostic_schema_invalid")
    seen = set()
    for row in rows:
        if (type(row) is not dict or set(row) != {"taskId", "taskVersion", "stage", "reason"}
                or any(type(value) is not str for value in row.values())
                or TASKS.get(row["taskId"]) != row["taskVersion"]
                or row["stage"] not in REASONS or row["reason"] not in REASONS[row["stage"]]
                or row["taskId"] in seen):
            raise ValueError("stage_b.diagnostic_schema_invalid")
        seen.add(row["taskId"])
    return [dict(row) for row in rows]


def _record(task_id, version, stage, reason):
    budget = _active.get()
    if budget is None or TASKS.get(task_id) != version:
        return
    if any(row["taskId"] == task_id for row in budget.model_failures):
        return
    # Every caller supplies an enum; never persist exception text or response data.
    budget.model_failures.append({"taskId": str(task_id), "taskVersion": version, "stage": stage, "reason": reason})


def rewrite_failure(response):
    """Classify a rejected response in memory; this never accepts a plan."""
    if response.finish_kind is not StructuredFinishKind.STOP or response.content is None or response.tool_calls:
        return "response_shape_invalid"
    try:
        value = parse_unique_json_object(response.content, max_bytes=262144, max_depth=20, max_items=4096)
    except InvalidModelOutput as exc:
        return str(exc) if str(exc) in JSON_CODES else "task_contract_invalid"
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return "task_contract_invalid"
    if set(value) != {"outcome", "queries", "missing_conditions"}:
        return "top_level_contract_invalid"
    outcome, queries, missing = value["outcome"], value["queries"], value["missing_conditions"]
    if type(outcome) is not str or outcome not in {"search", "clarification_required", "unsupported"}:
        return "outcome_invalid"
    if not isinstance(missing, tuple) or any(type(x) is not str or x not in {
            "subject", "taxpayer_type", "calculation_method", "applicable_period"} for x in missing):
        return "missing_conditions_invalid"
    if (len(set(missing)) != len(missing) or (outcome != "clarification_required" and missing)
            or (outcome == "clarification_required" and not 1 <= len(missing) <= 3)):
        return "missing_conditions_invalid"
    if not isinstance(queries, tuple) or (outcome != "search" and queries):
        return "queries_contract_invalid"
    if outcome == "search" and (not 1 <= len(queries) <= 2 or any(
            not isinstance(item, Mapping) or set(item) != {"domain_id", "query"} for item in queries)):
        return "queries_contract_invalid"
    return "task_contract_invalid"


def failure_rows(observation):
    budget = _active.get()
    rows = [] if budget is None else list(budget.model_failures)
    for item in observation.model_calls:
        if item["status"] == "succeeded" or any(row["taskId"] == item["taskId"] for row in rows):
            continue
        reason = item.get("failureKind")
        rows.append({"taskId": item["taskId"], "taskVersion": item["taskVersion"], "stage": "gateway",
                     "reason": reason if reason in GATEWAY_CODES else "unknown_failure"})
    return validate_rows(rows)


@contextmanager
def diagnostic_scope(budget):
    complete = DeepSeekChatTransport.complete
    definition = KnowledgeRewriteTaskV4.definition

    async def observed_complete(self, request, *, call_deadline):
        try:
            return await complete(self, request, call_deadline=call_deadline)
        except InvalidModelOutput as exc:
            reason = str(exc) if str(exc) in PROVIDER_CODES else "provider_invalid_output"
            _record(request.task_id, request.task_version, "provider", reason)
            raise
        except ModelTransportError as exc:
            reason = "provider_timeout" if exc.kind.value == "provider_timeout" else "provider_failure"
            _record(request.task_id, request.task_version, "provider", reason)
            raise
        except asyncio.CancelledError:
            _record(request.task_id, request.task_version, "provider", "cancelled")
            raise

    def observed_definition():
        original = definition()

        def parse(response):
            try:
                return original.parse_response(response)
            except InvalidModelOutput:
                _record(original.task_id, original.task_version, "task_decoder", rewrite_failure(response))
                raise

        return replace(original, parse_response=parse)

    token = _active.set(budget)
    try:
        with patch.object(DeepSeekChatTransport, "complete", observed_complete), patch.object(
                KnowledgeRewriteTaskV4, "definition", staticmethod(observed_definition)):
            yield
    finally:
        _active.reset(token)
