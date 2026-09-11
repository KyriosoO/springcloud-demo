"""Observe the original decoder's single JSON load; never change admission."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import json
from typing import Any, Iterator
from unittest.mock import patch

from agent_runtime.knowledge import rewrite_v7
from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanOutput
from agent_runtime.model.contracts import InvalidModelOutput, StructuredModelResponse
from tests.system_e2e import knowledge_model_failure_probe_v1 as legacy
from tests.system_e2e import knowledge_model_failure_probe_v2 as semantic

SHAPES = (
    "root_shape", "root_fields", "question_kind_type", "collection_type", "collection_limit",
    "query_shape", "requirement_shape", "requirement_kind_enum", "question_kind_enum",
)
DETAILS = semantic.DETAILS + SHAPES
_JSON = json
_PARSE = rewrite_v7._parse
_PROJECT = semantic.project_failure
_PARSING: ContextVar[bool] = ContextVar("rewrite_shape_parsing_v3", default=False)
_FACT: ContextVar[str] = ContextVar("rewrite_shape_fact_v3", default="unknown")
_REJECTED: ContextVar[tuple[InvalidModelOutput, str] | None] = ContextVar("rewrite_shape_rejected_v3", default=None)


@dataclass(slots=True)
class _Scope:
    active: bool = True


_SCOPE: ContextVar[_Scope | None] = ContextVar("rewrite_shape_scope_v3", default=None)


def _enabled() -> bool:
    scope = _SCOPE.get()
    return scope is not None and scope.active


def _keys(value: object, expected: frozenset[str]) -> bool:
    return (type(value) is dict and len(value) == len(expected)
            and all(type(key) is str and key in expected for key in value))


def shape_detail(value: object) -> str:
    """Bounded structural fact, not a decoder, validator, or raw-response parser."""
    if type(value) is not dict:
        return "root_shape" if type(value) in (list, str, int, float, bool, type(None)) else "unknown"
    if not _keys(value, frozenset(("outcome", "question_kind", "queries", "requirements", "missing_conditions"))):
        return "root_fields"
    if type(value["question_kind"]) is not str:
        return "question_kind_type"
    if any(type(value[key]) is not list for key in ("queries", "requirements", "missing_conditions")):
        return "collection_type"
    if len(value["queries"]) > 2 or len(value["requirements"]) > 4 or len(value["missing_conditions"]) > 3:
        return "collection_limit"
    for item in value["queries"]:
        if not _keys(item, frozenset(("domain_id", "query"))):
            return "query_shape"
    for item in value["requirements"]:
        if not _keys(item, frozenset(("requirement_id", "domain_id", "kind", "focus"))) or type(item["kind"]) is not str:
            return "requirement_shape"
        if item["kind"] not in {"subject_scope", "rule", "temporal_scope", "constraint"}:
            return "requirement_kind_enum"
    if value["question_kind"] not in {"none", "lookup", "applicability"}:
        return "question_kind_enum"
    return "unknown"


class _JsonView:
    @staticmethod
    def loads(*args: Any, **kwargs: Any) -> Any:
        # Original hooks and exact returned tree are preserved. No second parse.
        value = _JSON.loads(*args, **kwargs)
        if _enabled() and _PARSING.get():
            try:
                detail = shape_detail(value)
                _FACT.set(detail if type(detail) is str and detail in SHAPES else "unknown")
            except Exception:
                # This is only an observation fault; never hide a decoder fault.
                _FACT.set("unknown")
        return value


def _parse(response: StructuredModelResponse) -> KnowledgeSemanticPlanOutput:
    if not _enabled():
        return _PARSE(response)
    _REJECTED.set(None)
    semantic._REJECTED.set(None)
    parsing_token = _PARSING.set(True)
    fact_token = _FACT.set("unknown")
    rejected = None
    try:
        return _PARSE(response)
    except InvalidModelOutput as error:
        if type(error) is InvalidModelOutput:
            rejected = (error, _FACT.get())
        raise
    finally:
        _REJECTED.set(rejected)
        _FACT.reset(fact_token)
        _PARSING.reset(parsing_token)


def project_failure(error: BaseException | None) -> semantic.FailureDiagnostic:
    recorded = _REJECTED.get()
    _REJECTED.set(None)
    original = _PROJECT(error)
    if (not _enabled() or recorded is None or error is not recorded[0]
            or original.phase != "rewrite_decoder" or original.cause != "shape_or_enum"):
        return original
    return semantic.FailureDiagnostic(original.phase, original.code, original.cause, recorded[1])


@contextmanager
def observe_failures() -> Iterator[legacy.FailureCollector]:
    # V2 acquires the shared V1 lock before we change any process-local hooks.
    with semantic.observe_failures() as collector:
        scope = _Scope()
        scope_token = _SCOPE.set(scope)
        rejected_token = _REJECTED.set(None)
        parsing_token = _PARSING.set(False)
        fact_token = _FACT.set("unknown")
        try:
            with patch.object(legacy, "project_failure", project_failure), \
                    patch.object(rewrite_v7, "json", _JsonView), \
                    patch.object(rewrite_v7, "_parse", _parse):
                yield collector
        finally:
            scope.active = False
            _FACT.reset(fact_token)
            _PARSING.reset(parsing_token)
            _REJECTED.reset(rejected_token)
            _SCOPE.reset(scope_token)
