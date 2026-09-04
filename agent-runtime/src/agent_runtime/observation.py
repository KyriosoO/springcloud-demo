from __future__ import annotations

import json
import re
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, fields, is_dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Iterator, Mapping, cast

from agent_runtime.model.contracts import ModelTaskId, StructuredModelRequest


_MAX_MODEL_CALLS = 8
_MAX_PLANS = 4
_MAX_DOWNSTREAM_CALLS = 32
_MAX_VIEW_BYTES = 65_536
_MAX_SNAPSHOT_BYTES = 65_536
_SENSITIVE_KEYS = frozenset(
    {
        "account",
        "authorization",
        "chinese_name",
        "contact_address",
        "email",
        "employee_id",
        "id_card",
        "id_card_no",
        "idcard",
        "idcardno",
        "jwt",
        "member_no",
        "memberno",
        "mobile",
        "name",
        "phone",
        "phone_no",
        "record_ref",
        "token",
        "trans_id",
    }
)


@dataclass(frozen=True, slots=True)
class ObservationSnapshot:
    model_calls: tuple[dict[str, Any], ...]
    plans: tuple[dict[str, Any], ...]
    downstream_calls: tuple[dict[str, Any], ...]


class RunObservationCollector:
    __slots__ = ("_downstream_calls", "_model_calls", "_next_sequence", "_plans")

    def __init__(self) -> None:
        self._next_sequence = 1
        self._model_calls: list[dict[str, Any]] = []
        self._plans: list[dict[str, Any]] = []
        self._downstream_calls: list[dict[str, Any]] = []

    def start_model_call(self, request: StructuredModelRequest) -> int | None:
        if len(self._model_calls) >= _MAX_MODEL_CALLS:
            return None
        sequence = self._take_sequence()
        try:
            request_view = _model_request_view(request)
        except (TypeError, ValueError, UnicodeError):
            request_view = {"projectionStatus": "unavailable"}
        self._model_calls.append(
            {
                "sequence": sequence,
                "taskId": request.task_id.value,
                "taskVersion": request.task_version,
                "request": request_view,
                "status": "started",
                "failureKind": None,
            }
        )
        return sequence

    def finish_model_call(
        self,
        sequence: int | None,
        *,
        failure_kind: str | None = None,
    ) -> None:
        entry = self._find(self._model_calls, sequence)
        if entry is None:
            return
        entry["status"] = "failed" if failure_kind is not None else "succeeded"
        entry["failureKind"] = failure_kind

    def record_plan(
        self,
        *,
        plan_type: str,
        source: str,
        validation_status: str,
        plan: object,
    ) -> None:
        if len(self._plans) >= _MAX_PLANS:
            return
        try:
            plan_view = _bounded_mapping(_redact(_to_plain(plan)))
        except (TypeError, ValueError, UnicodeError):
            plan_view = {"projectionStatus": "unavailable"}
        self._plans.append(
            {
                "sequence": self._take_sequence(),
                "type": plan_type,
                "source": source,
                "validationStatus": validation_status,
                "plan": plan_view,
            }
        )

    def start_downstream_call(
        self,
        *,
        target: str,
        operation: str,
        method: str,
        relative_path: str,
        request: Mapping[str, object],
    ) -> int | None:
        if len(self._downstream_calls) >= _MAX_DOWNSTREAM_CALLS:
            return None
        sequence = self._take_sequence()
        try:
            request_view = _bounded_mapping(_redact(request))
        except (TypeError, ValueError, UnicodeError):
            request_view = {"projectionStatus": "unavailable"}
        self._downstream_calls.append(
            {
                "sequence": sequence,
                "target": target,
                "operation": operation,
                "method": method,
                "relativePath": relative_path,
                "request": request_view,
                "status": "started",
                "httpStatus": None,
                "durationMs": None,
            }
        )
        return sequence

    def finish_downstream_call(
        self,
        sequence: int | None,
        *,
        status: str,
        http_status: int | None,
        duration_ms: int,
    ) -> None:
        entry = self._find(self._downstream_calls, sequence)
        if entry is None:
            return
        entry["status"] = status
        entry["httpStatus"] = http_status
        entry["durationMs"] = max(0, duration_ms)

    def snapshot(self) -> ObservationSnapshot:
        model_calls = [_safe_snapshot_item(item, "request") for item in self._model_calls]
        plans = [_safe_snapshot_item(item, "plan") for item in self._plans]
        downstream_calls = [
            _safe_snapshot_item(item, "request") for item in self._downstream_calls
        ]
        _fit_snapshot_budget(model_calls, plans, downstream_calls)
        return ObservationSnapshot(
            model_calls=tuple(model_calls),
            plans=tuple(plans),
            downstream_calls=tuple(downstream_calls),
        )

    def _take_sequence(self) -> int:
        value = self._next_sequence
        self._next_sequence += 1
        return value

    @staticmethod
    def _find(entries: list[dict[str, Any]], sequence: int | None) -> dict[str, Any] | None:
        if sequence is None:
            return None
        return next((entry for entry in entries if entry["sequence"] == sequence), None)


_CURRENT: ContextVar[RunObservationCollector | None] = ContextVar(
    "agent_runtime_run_observation",
    default=None,
)


@contextmanager
def observation_scope() -> Iterator[RunObservationCollector]:
    collector = RunObservationCollector()
    token: Token[RunObservationCollector | None] = _CURRENT.set(collector)
    try:
        yield collector
    finally:
        _CURRENT.reset(token)


def current_observation() -> RunObservationCollector | None:
    return _CURRENT.get()


def model_call_started(request: StructuredModelRequest) -> int | None:
    collector = current_observation()
    return None if collector is None else collector.start_model_call(request)


def model_call_succeeded(sequence: int | None) -> None:
    collector = current_observation()
    if collector is not None:
        collector.finish_model_call(sequence)


def model_call_failed(sequence: int | None, failure_kind: str) -> None:
    collector = current_observation()
    if collector is not None:
        collector.finish_model_call(sequence, failure_kind=failure_kind)


def record_plan(*, plan_type: str, source: str, validation_status: str, plan: object) -> None:
    collector = current_observation()
    if collector is not None:
        collector.record_plan(
            plan_type=plan_type,
            source=source,
            validation_status=validation_status,
            plan=plan,
        )


def downstream_call_started(
    *,
    target: str,
    operation: str,
    method: str,
    relative_path: str,
    request: Mapping[str, object],
) -> int | None:
    collector = current_observation()
    if collector is None:
        return None
    return collector.start_downstream_call(
        target=target,
        operation=operation,
        method=method,
        relative_path=relative_path,
        request=request,
    )


def downstream_call_finished(
    sequence: int | None,
    *,
    status: str,
    http_status: int | None,
    duration_ms: int,
) -> None:
    collector = current_observation()
    if collector is not None:
        collector.finish_downstream_call(
            sequence,
            status=status,
            http_status=http_status,
            duration_ms=duration_ms,
        )


def business_http_request_view(relative_path: str, body: bytes | None, query: tuple[tuple[str, str], ...]) -> dict[str, Any]:
    parsed: object = None
    if body is not None:
        parsed = json.loads(body.decode("utf-8"), parse_float=str)
    if relative_path == "/employees/es/search" and isinstance(parsed, dict):
        filters = parsed.get("filters")
        if isinstance(filters, list):
            for item in filters:
                if not isinstance(item, dict):
                    continue
                field = item.get("field")
                if isinstance(field, str) and _employee_service_field_is_sensitive(field):
                    if "value" in item:
                        item["value"] = "<protected>"
                    if "values" in item:
                        item["values"] = ["<protected>"]
        if "keyword" in parsed:
            parsed["keyword"] = "<protected>"
    return {
        "query": _redact(dict(query)),
        "body": _redact(parsed),
        "exactDecimalJsonNumbers": relative_path == "/txn/search",
    }


def safe_business_relative_path(relative_path: str) -> str:
    if relative_path in {"/employees/es/search", "/employees/es/vector-search", "/txn/search"}:
        return relative_path
    if relative_path.startswith("/employees/"):
        return "/employees/<protected>"
    return "/unsupported"


def knowledge_http_request_view(relative_path: str, body: bytes) -> dict[str, Any]:
    parsed = json.loads(body.decode("utf-8"))
    if not isinstance(parsed, dict):
        return {"bodyType": type(parsed).__name__}
    if relative_path == "/rerank":
        documents = parsed.get("documents")
        return {
            "query": parsed.get("query"),
            "documentCount": len(documents) if isinstance(documents, list) else 0,
            "topN": parsed.get("top_n"),
            "normalize": parsed.get("normalize"),
            "documentContentDisplayed": False,
        }
    if relative_path == "/es/knowledge/search":
        vector = parsed.get("queryVector")
        parsed["queryVector"] = {
            "present": isinstance(vector, list),
            "dimensions": len(vector) if isinstance(vector, list) else 0,
            "valuesDisplayed": False,
        }
    return cast(dict[str, Any], _redact(parsed))


def _model_request_view(request: StructuredModelRequest) -> dict[str, Any]:
    payload = json.loads(request.user_payload_json)
    if request.task_id is ModelTaskId.KNOWLEDGE_SUMMARY and isinstance(payload, dict):
        evidence = payload.get("evidence")
        payload = {
            "question": payload.get("question"),
            "evidence": [
                {
                    "evidenceRef": item.get("evidence_ref"),
                    "domainIds": item.get("domain_ids"),
                    "contentDisplayed": False,
                }
                for item in evidence
                if isinstance(item, dict)
            ] if isinstance(evidence, list) else [],
        }
    return _bounded_mapping(
        {
            "systemInstruction": request.system_instruction,
            "input": _redact(payload),
            "toolMode": request.tool_mode.value,
            "outputMode": request.output_mode.value,
            "toolNames": [tool.name for tool in request.tools],
            "maxOutputTokens": request.max_output_tokens,
        }
    )


def _to_plain(value: object) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _to_plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_to_plain(item) for item in value]
    if is_dataclass(value):
        return {field.name: _to_plain(getattr(value, field.name)) for field in fields(value)}
    return {"type": type(value).__name__}


def _redact(value: object, key: str | None = None) -> Any:
    normalized = "" if key is None else re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower().replace("-", "_")
    if normalized in _SENSITIVE_KEYS:
        return "<protected>"
    if isinstance(value, Mapping):
        result = {str(item_key): _redact(item, str(item_key)) for item_key, item in value.items()}
        field = value.get("field")
        if isinstance(field, str) and _field_value_is_sensitive(field):
            for item_key in value:
                normalized_key = str(item_key).lower().replace("-", "_")
                if normalized_key in {"value", "values"}:
                    result[str(item_key)] = "<protected>"
        return result
    if isinstance(value, (tuple, list)):
        return [_redact(item) for item in value]
    return value


def _bounded_view(value: Any) -> Any:
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > _MAX_VIEW_BYTES:
        raise ValueError("runtime.observation_view_too_large")
    return json.loads(encoded)


def _bounded_mapping(value: object) -> dict[str, Any]:
    result = _bounded_view(value)
    if not isinstance(result, dict):
        raise ValueError("runtime.observation_object_required")
    return cast(dict[str, Any], result)


def _safe_snapshot_item(item: Mapping[str, Any], projected_field: str) -> dict[str, Any]:
    try:
        return cast(dict[str, Any], _bounded_view(dict(item)))
    except (TypeError, ValueError, UnicodeError):
        fallback = dict(item)
        fallback[projected_field] = {"projectionStatus": "unavailable"}
        return cast(dict[str, Any], _bounded_view(fallback))


def _fit_snapshot_budget(
    model_calls: list[dict[str, Any]],
    plans: list[dict[str, Any]],
    downstream_calls: list[dict[str, Any]],
) -> None:
    groups = (
        (downstream_calls, "request"),
        (plans, "plan"),
        (model_calls, "request"),
    )
    while _snapshot_size(model_calls, plans, downstream_calls) > _MAX_SNAPSHOT_BYTES:
        candidates = [
            (len(_encode(item.get(field))), item, field)
            for items, field in groups
            for item in items
            if item.get(field) != {"projectionStatus": "unavailable"}
        ]
        if not candidates:
            raise ValueError("runtime.observation_snapshot_too_large")
        _, item, field = max(candidates, key=lambda candidate: candidate[0])
        item[field] = {"projectionStatus": "unavailable"}


def _snapshot_size(
    model_calls: list[dict[str, Any]],
    plans: list[dict[str, Any]],
    downstream_calls: list[dict[str, Any]],
) -> int:
    return len(
        _encode(
            {
                "modelCalls": model_calls,
                "plans": plans,
                "downstreamCalls": downstream_calls,
            }
        )
    )


def _encode(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _employee_service_field_is_sensitive(field: str) -> bool:
    normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", field).lower().replace("-", "_")
    return normalized in {
        "account",
        "chinese_name",
        "email",
        "id_card_no",
        "member_no",
        "mobile",
        "phone",
        "telephone",
        "contact_address",
    }


def _field_value_is_sensitive(field: str) -> bool:
    normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", field).lower().replace("-", "_")
    return normalized in _SENSITIVE_KEYS or _employee_service_field_is_sensitive(field)
