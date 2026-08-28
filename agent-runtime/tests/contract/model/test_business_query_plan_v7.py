from __future__ import annotations

from agent_runtime.model.contracts import BusinessQueryPlanTaskInput
from agent_runtime.model.deepseek.business_query_plan_v7 import (
    BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION,
    BUSINESS_QUERY_PLAN_TASK_VERSION,
    build_business_query_plan_task_definition,
)


def test_v7_prompt_rejects_unknown_explicit_field_substitution() -> None:
    definition = build_business_query_plan_task_definition(timeout_ms=8000)
    request = definition.build_request(
        BusinessQueryPlanTaskInput(
            minimized_question="查询员工的unknownField等于上海",
            catalog={"schema_version": 3, "snapshot_id": "a" * 64},
            catalog_snapshot_id="a" * 64,
        )
    )

    assert definition.task_version == BUSINESS_QUERY_PLAN_TASK_VERSION == (
        "business-query-plan-v7"
    )
    assert request.task_version == "business-query-plan-v7"
    for required in (
        "explicitly requested attribute or field label is a binding condition",
        "not represented by a catalog logical field",
        "Never translate an unknown attribute to the nearest known field",
        "silently drop it",
        "camelCase and snake_case labels",
    ):
        assert required in BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION


def test_v6_remains_a_distinct_historical_task() -> None:
    from agent_runtime.model.deepseek.business_query_plan_v6 import (
        BUSINESS_QUERY_PLAN_TASK_VERSION as V6_TASK_VERSION,
    )

    assert V6_TASK_VERSION == "business-query-plan-v6"
    assert V6_TASK_VERSION != BUSINESS_QUERY_PLAN_TASK_VERSION
