from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import TypeAdapter


CLARIFICATION_BINDINGS = {
    "CAPABILITY_AMBIGUOUS": ("CAPABILITY_CHOICES", "ROUTE"),
    "DOMAIN_REQUIRED": ("DOMAIN_CHOICES", "ROUTE"),
    "DOMAIN_AMBIGUOUS": ("DOMAIN_CHOICES", "ROUTE"),
    "FIELD_REQUIRED": ("FIELD_CHOICES", "PLAN"),
    "VALUE_REQUIRED": ("VALUE_CHOICES", "PLAN"),
    "VALUE_AMBIGUOUS": ("VALUE_CHOICES", "PLAN"),
}
CHOICE_FIELDS = {
    "CAPABILITY_CHOICES": "capability_ids",
    "DOMAIN_CHOICES": "domains",
    "FIELD_CHOICES": "fields",
    "VALUE_CHOICES": "values",
}
MIN_CHOICES = {
    "CAPABILITY_AMBIGUOUS": 2,
    "DOMAIN_REQUIRED": 1,
    "DOMAIN_AMBIGUOUS": 2,
    "FIELD_REQUIRED": 1,
    "VALUE_REQUIRED": 0,
    "VALUE_AMBIGUOUS": 2,
}
WRONG_REASON_BY_ARG_TYPE = {
    "CAPABILITY_CHOICES": "DOMAIN_REQUIRED",
    "DOMAIN_CHOICES": "CAPABILITY_AMBIGUOUS",
    "FIELD_CHOICES": "VALUE_REQUIRED",
    "VALUE_CHOICES": "FIELD_REQUIRED",
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
    actual = (
        clarification.args.arg_type,
        clarification.metadata.operation.value,
    )
    arg_type = actual[0] if isinstance(actual[0], str) else actual[0].value
    expected = CLARIFICATION_BINDINGS[reason]
    if (arg_type, actual[1]) != expected:
        raise ValueError(f"invalid clarification binding: {reason} -> {actual}")
    choices = getattr(clarification.args, CHOICE_FIELDS[arg_type])
    if len(set(choices)) != len(choices):
        raise ValueError(f"duplicate clarification choices: {reason}")
    if len(set(choices)) < MIN_CHOICES[reason]:
        raise ValueError(f"invalid clarification choice count: {reason}")


def _assert_runtime_error_binding(error: object) -> None:
    expected = ERROR_BINDINGS[error.code.value]
    actual = error.metadata.termination_reason.value
    if actual != expected:
        raise ValueError(f"invalid Runtime error binding: {error.code.value} -> {actual}")


def test_plan_kind_has_no_clarify(candidate_models: ModuleType) -> None:
    assert {item.value for item in candidate_models.AgentPlanKind} == {"QUERY", "AGGREGATE"}


def test_clarification_has_no_question(candidate_models: ModuleType) -> None:
    assert "question" not in candidate_models.ClarificationRequired.model_fields


def test_executable_plan_has_no_identity_echo(candidate_models: ModuleType) -> None:
    fields = set(candidate_models.ExecutablePlan.model_fields)
    assert fields.isdisjoint({"capability_id", "capabilityId", "plan_kind", "domain"})


def test_no_parallel_version_axis(candidate_models: ModuleType) -> None:
    assert not hasattr(candidate_models, "PlanVersion")
    for name in dir(candidate_models):
        model = getattr(candidate_models, name)
        fields = getattr(model, "model_fields", {})
        assert "plan_version" not in fields and "strategy_version" not in fields


def test_route_request_has_no_context(candidate_models: ModuleType) -> None:
    fields = set(candidate_models.RouteRequest.model_fields)
    assert fields.isdisjoint({"context", "context_view", "context_views", "domain_schema"})


def test_requests_share_single_contract_generation(
    candidate_models: ModuleType, candidate_fixture_dir: Path
) -> None:
    route_payload = json.loads(
        (candidate_fixture_dir / "route-request.json").read_text(encoding="utf-8")
    )
    plan_payload = json.loads(
        (candidate_fixture_dir / "plan-request.json").read_text(encoding="utf-8")
    )
    route = candidate_models.RouteRequest.model_validate(route_payload)
    plan = candidate_models.PlanRequest.model_validate(plan_payload)
    assert route.contract_version == plan.contract_version
    assert route.contract_version
    plan_payload["contractVersion"] = "9.9.9"
    with pytest.raises(ValueError):
        candidate_models.PlanRequest.model_validate(plan_payload)


@pytest.mark.parametrize(
    ("reason", "args_payload", "operation", "root_model"),
    [
        (
            "CAPABILITY_AMBIGUOUS",
            {"argType": "CAPABILITY_CHOICES", "capabilityIds": ["query", "aggregate"]},
            "ROUTE",
            "RouteOutcome",
        ),
        (
            "DOMAIN_REQUIRED",
            {"argType": "DOMAIN_CHOICES", "domains": ["employee"]},
            "ROUTE",
            "RouteOutcome",
        ),
        (
            "DOMAIN_AMBIGUOUS",
            {"argType": "DOMAIN_CHOICES", "domains": ["employee", "transaction"]},
            "ROUTE",
            "RouteOutcome",
        ),
        (
            "FIELD_REQUIRED",
            {"argType": "FIELD_CHOICES", "fields": ["name"]},
            "PLAN",
            "PlanOutcome",
        ),
        (
            "VALUE_REQUIRED",
            {"argType": "VALUE_CHOICES", "field": "name", "values": []},
            "PLAN",
            "PlanOutcome",
        ),
        (
            "VALUE_AMBIGUOUS",
            {"argType": "VALUE_CHOICES", "field": "name", "values": ["张", "章"]},
            "PLAN",
            "PlanOutcome",
        ),
    ],
)
def test_clarification_reason_arg_operation_binding(
    candidate_models: ModuleType,
    reason: str,
    args_payload: dict[str, object],
    operation: str,
    root_model: str,
) -> None:
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
    parsed = TypeAdapter(getattr(candidate_models, root_model)).validate_python(payload)
    root = getattr(parsed, "root", parsed)
    _assert_clarification_binding(root)

    original_operation = root.metadata.operation
    opposite = "PLAN" if root.metadata.operation.value == "ROUTE" else "ROUTE"
    root.metadata.operation = next(
        item for item in candidate_models.RuntimeOperationType if item.value == opposite
    )
    with pytest.raises(ValueError, match="invalid clarification binding"):
        _assert_clarification_binding(root)

    root.metadata.operation = original_operation
    original_reason = root.reason_code
    arg_type = root.args.arg_type
    arg_type_value = arg_type if isinstance(arg_type, str) else arg_type.value
    wrong_reason = WRONG_REASON_BY_ARG_TYPE[arg_type_value]
    root.reason_code = next(
        item for item in candidate_models.ClarificationReasonCode
        if item.value == wrong_reason
    )
    with pytest.raises(ValueError, match="invalid clarification binding"):
        _assert_clarification_binding(root)

    root.reason_code = original_reason
    choice_field = CHOICE_FIELDS[arg_type_value]
    original_choices = list(getattr(root.args, choice_field))
    if original_choices:
        setattr(root.args, choice_field, [original_choices[0], original_choices[0]])
        with pytest.raises(ValueError, match="duplicate clarification choices"):
            _assert_clarification_binding(root)
        setattr(root.args, choice_field, original_choices)
    if MIN_CHOICES[reason] >= 2:
        setattr(root.args, choice_field, getattr(root.args, choice_field)[:1])
        with pytest.raises(ValueError, match="invalid clarification choice count"):
            _assert_clarification_binding(root)


def test_runtime_error_code_termination_binding(
    candidate_models: ModuleType, candidate_fixture_dir: Path
) -> None:
    payload = json.loads(
        (candidate_fixture_dir / "runtime-error.json").read_text(encoding="utf-8")
    )
    for code, termination in ERROR_BINDINGS.items():
        candidate = json.loads(json.dumps(payload, ensure_ascii=False))
        candidate["code"] = code
        candidate["metadata"]["terminationReason"] = termination
        error = candidate_models.RuntimeErrorResponse.model_validate(candidate)
        _assert_runtime_error_binding(error)

    error = candidate_models.RuntimeErrorResponse.model_validate(payload)
    error.metadata.termination_reason = next(
        item
        for item in candidate_models.RuntimeTerminationReason
        if item.value == "INTERNAL_ERROR"
    )
    with pytest.raises(ValueError, match="invalid Runtime error binding"):
        _assert_runtime_error_binding(error)
