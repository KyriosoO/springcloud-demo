"""当前运行时路由/计划契约测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.contracts import generated_models as g
from app.contracts import models

FIXTURE_DIR = (
    Path(__file__).resolve().parents[2]
    / "agent-api" / "src" / "test" / "resources"
    / "contract" / "fixtures"
)


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


CLARIFICATION_BINDINGS = {
    "CAPABILITY_AMBIGUOUS": ("CAPABILITY_CHOICES", "ROUTE"),
    "DOMAIN_REQUIRED": ("DOMAIN_CHOICES", "ROUTE"),
    "DOMAIN_AMBIGUOUS": ("DOMAIN_CHOICES", "ROUTE"),
    "FIELD_REQUIRED": ("FIELD_CHOICES", "PLAN"),
    "FIELD_FORBIDDEN": ("FIELD_FORBIDDEN", "PLAN"),
    "VALUE_REQUIRED": ("VALUE_CHOICES", "PLAN"),
    "VALUE_AMBIGUOUS": ("VALUE_CHOICES", "PLAN"),
}

CHOICE_FIELDS = {
    "CAPABILITY_CHOICES": "capability_ids",
    "DOMAIN_CHOICES": "domains",
    "FIELD_CHOICES": "fields",
    "FIELD_FORBIDDEN": "field",
    "VALUE_CHOICES": "values",
}

MIN_CHOICES = {
    "CAPABILITY_AMBIGUOUS": 2,
    "DOMAIN_REQUIRED": 1,
    "DOMAIN_AMBIGUOUS": 2,
    "FIELD_REQUIRED": 1,
    "FIELD_FORBIDDEN": 1,
    "VALUE_REQUIRED": 0,
    "VALUE_AMBIGUOUS": 2,
}

ERROR_BINDINGS = {
    "CONTRACT_INVALID": "VALIDATION_REJECTED",
    "AUTHENTICATION_FAILED": "AUTHENTICATION_REJECTED",
    "PROVIDER_UNAVAILABLE": "PROVIDER_UNAVAILABLE",
    "DEADLINE_EXCEEDED": "DEADLINE_EXCEEDED",
    "OUTPUT_REPAIR_EXHAUSTED": "REPAIR_EXHAUSTED",
    "INTERNAL_ERROR": "INTERNAL_ERROR",
}


def _assert_clarification_binding(clarification: object) -> None:
    reason = clarification.reason_code.value
    arg_type = clarification.args.arg_type
    arg_type_value = arg_type if isinstance(arg_type, str) else arg_type.value
    actual = (arg_type_value, clarification.metadata.operation.value)
    assert actual == CLARIFICATION_BINDINGS[reason]
    choices = getattr(clarification.args, CHOICE_FIELDS[arg_type_value])
    if isinstance(choices, str):
        choices = [choices]
    assert len(set(choices)) == len(choices)
    assert len(set(choices)) >= MIN_CHOICES[reason]


def _assert_runtime_error_binding(error: object) -> None:
    assert error.metadata.termination_reason.value == ERROR_BINDINGS[error.code.value]


@pytest.mark.parametrize(
    ("fixture", "root_model"),
    [
        ("route-request.json", models.RouteRequest),
        ("route-decision.json", models.RouteOutcome),
        ("route-clarification.json", models.RouteOutcome),
        ("plan-request.json", models.PlanRequest),
        ("query-plan.json", models.PlanOutcome),
        ("aggregate-plan.json", models.PlanOutcome),
        ("plan-clarification.json", models.PlanOutcome),
        ("runtime-error.json", models.RuntimeErrorResponse),
    ],
)
def test_positive_fixture_round_trip(fixture, root_model):
    payload = _load(fixture)
    adapter = TypeAdapter(root_model)
    parsed = adapter.validate_python(payload)
    dumped = adapter.dump_python(
        parsed, by_alias=True, mode="json", exclude_none=False, exclude_unset=True
    )
    assert dumped == payload


def test_route_to_plan_fixture_chain():
    route_request = models.RouteRequest.model_validate(_load("route-request.json"))
    route_decision = models.unwrap_root(
        TypeAdapter(models.RouteOutcome).validate_python(_load("route-decision.json"))
    )
    plan_request = models.PlanRequest.model_validate(_load("plan-request.json"))
    executable = models.unwrap_root(
        TypeAdapter(models.PlanOutcome).validate_python(_load("query-plan.json"))
    )

    assert {
        route_request.request_id,
        route_decision.request_id,
        plan_request.request_id,
        executable.request_id,
    } == {"flow-001"}
    assert route_request.contract_version == plan_request.contract_version
    assert route_decision.capability_id == plan_request.capability_id
    assert plan_request.plan_kind.value == executable.plan.plan_kind == "QUERY"
    assert route_decision.domain == plan_request.domain == plan_request.domain_schema.domain


@pytest.mark.parametrize(
    ("fixture", "message"),
    [
        ("unknown-plan-kind.json", "planKind"),
        ("unknown-operator.json", "operator"),
        ("extra-field.json", "extraField"),
        ("missing-query.json", "query"),
        ("discriminator-mismatch.json", "aggregate"),
    ],
)
def test_negative_fixtures_rejected(fixture, message):
    payload = _load("negative/" + fixture)
    with pytest.raises(ValidationError, match=message):
        TypeAdapter(models.PlanOutcome).validate_python(payload)


def test_legacy_plan_generate_models_are_not_exported():
    assert not hasattr(models, "PlanGenerateRequest")
    assert not hasattr(models, "PlanGenerateResponse")
    assert not hasattr(models, "AgentIntent")


def test_plan_kind_has_no_clarify():
    assert {item.value for item in g.AgentPlanKind} == {"QUERY", "AGGREGATE"}


def test_clarification_has_no_question():
    assert "question" not in g.ClarificationRequired.model_fields


def test_executable_plan_has_no_identity_echo():
    fields = set(g.ExecutablePlan.model_fields)
    assert fields.isdisjoint({"capability_id", "capabilityId", "plan_kind", "domain"})


def test_no_parallel_version_axis():
    assert not hasattr(g, "PlanVersion")
    for name in dir(g):
        model = getattr(g, name)
        fields = getattr(model, "model_fields", {})
        assert "plan_version" not in fields
        assert "strategy_version" not in fields


def test_route_request_has_no_context():
    fields = set(g.RouteRequest.model_fields)
    assert fields.isdisjoint({"context", "context_view", "context_views", "domain_schema"})


def test_query_context_accepts_optional_pagination_totals():
    view = g.RuntimeQueryContextView.model_validate(
        {
            "contextType": "QUERY",
            "sourceInvocationId": "inv-prev-001",
            "filters": [],
            "selectFields": ["name"],
            "sorts": [],
            "page": 1,
            "size": 20,
            "total": 45,
            "totalExact": True,
            "totalPages": 3,
        }
    )

    assert view.total == 45
    assert view.total_exact is True
    assert view.total_pages == 3


def test_requests_share_single_contract_generation():
    route = g.RouteRequest.model_validate(_load("route-request.json"))
    plan_payload = _load("plan-request.json")
    plan = g.PlanRequest.model_validate(plan_payload)

    assert route.contract_version == plan.contract_version
    assert route.contract_version

    plan_payload["contractVersion"] = "9.9.9"
    with pytest.raises(ValueError):
        g.PlanRequest.model_validate(plan_payload)


@pytest.mark.parametrize(
    ("reason", "args_payload", "operation", "root_model"),
    [
        (
            "CAPABILITY_AMBIGUOUS",
            {"argType": "CAPABILITY_CHOICES", "capabilityIds": ["query", "aggregate"]},
            "ROUTE",
            g.RouteOutcome,
        ),
        (
            "DOMAIN_REQUIRED",
            {"argType": "DOMAIN_CHOICES", "domains": ["employee"]},
            "ROUTE",
            g.RouteOutcome,
        ),
        (
            "DOMAIN_AMBIGUOUS",
            {"argType": "DOMAIN_CHOICES", "domains": ["employee", "transaction"]},
            "ROUTE",
            g.RouteOutcome,
        ),
        (
            "FIELD_REQUIRED",
            {"argType": "FIELD_CHOICES", "fields": ["name"]},
            "PLAN",
            g.PlanOutcome,
        ),
        (
            "FIELD_FORBIDDEN",
            {"argType": "FIELD_FORBIDDEN", "field": "contactAddress"},
            "PLAN",
            g.PlanOutcome,
        ),
        (
            "VALUE_REQUIRED",
            {"argType": "VALUE_CHOICES", "field": "name", "values": []},
            "PLAN",
            g.PlanOutcome,
        ),
        (
            "VALUE_AMBIGUOUS",
            {"argType": "VALUE_CHOICES", "field": "name", "values": ["张", "章"]},
            "PLAN",
            g.PlanOutcome,
        ),
    ],
)
def test_clarification_reason_arg_operation_binding(
    reason,
    args_payload,
    operation,
    root_model,
):
    payload = {
        "outcomeType": "CLARIFICATION",
        "requestId": f"binding-{reason.lower()}",
        "reasonCode": reason,
        "args": args_payload,
        "metadata": {
            "operation": operation,
            "providerAttempts": 1,
            "repairAttempts": 0,
            "repairDurationMs": 0,
            "totalDurationMs": 1,
            "terminationReason": "CLARIFICATION",
            "deadlineReached": False,
            "repairLimitReached": False,
        },
    }
    parsed = TypeAdapter(root_model).validate_python(payload)
    _assert_clarification_binding(models.unwrap_root(parsed))


def test_runtime_error_code_termination_binding():
    payload = _load("runtime-error.json")
    for code, termination in ERROR_BINDINGS.items():
        candidate = json.loads(json.dumps(payload, ensure_ascii=False))
        candidate["code"] = code
        candidate["metadata"]["terminationReason"] = termination
        _assert_runtime_error_binding(g.RuntimeErrorResponse.model_validate(candidate))
