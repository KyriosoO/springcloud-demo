from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import TypeAdapter


@pytest.mark.parametrize(
    ("fixture", "root_model"),
    [
        ("route-request.json", "RouteRequest"),
        ("route-decision.json", "RouteOutcome"),
        ("route-clarification.json", "RouteOutcome"),
        ("plan-request.json", "PlanRequest"),
        ("query-plan.json", "PlanOutcome"),
        ("aggregate-plan.json", "PlanOutcome"),
        ("plan-clarification.json", "PlanOutcome"),
        ("runtime-error.json", "RuntimeErrorResponse"),
    ],
)
def test_positive_fixture_round_trip(
    candidate_models: ModuleType,
    candidate_fixture_dir: Path,
    fixture: str,
    root_model: str,
) -> None:
    payload = json.loads((candidate_fixture_dir / fixture).read_text(encoding="utf-8"))
    model_type = getattr(candidate_models, root_model)
    adapter = TypeAdapter(model_type)
    parsed = adapter.validate_python(payload)
    dumped = adapter.dump_python(
        parsed, by_alias=True, mode="json", exclude_none=False, exclude_unset=True
    )
    assert dumped == payload


def test_route_to_plan_fixture_chain(
    candidate_models: ModuleType, candidate_fixture_dir: Path
) -> None:
    def load(name: str) -> dict:
        return json.loads((candidate_fixture_dir / name).read_text(encoding="utf-8"))

    route_request = candidate_models.RouteRequest.model_validate(load("route-request.json"))
    route_outcome = TypeAdapter(candidate_models.RouteOutcome).validate_python(
        load("route-decision.json")
    )
    route_decision = getattr(route_outcome, "root", route_outcome)
    plan_request = candidate_models.PlanRequest.model_validate(load("plan-request.json"))
    plan_outcome = TypeAdapter(candidate_models.PlanOutcome).validate_python(
        load("query-plan.json")
    )
    executable = getattr(plan_outcome, "root", plan_outcome)

    assert {
        route_request.request_id,
        route_decision.request_id,
        plan_request.request_id,
        executable.request_id,
    } == {"flow-001"}
    assert route_request.contract_version == plan_request.contract_version
    assert route_request.contract_version
    assert route_request.absolute_deadline == plan_request.absolute_deadline
    assert route_decision.capability_id == plan_request.capability_id
    assert plan_request.capability.capability_id == plan_request.capability_id
    assert plan_request.plan_kind.value == executable.plan.plan_kind == "QUERY"
    assert route_decision.domain == plan_request.domain == plan_request.domain_schema.domain
