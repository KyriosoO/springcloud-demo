from __future__ import annotations

from agent_runtime.model.contracts import BusinessQueryPlanTaskInput
from agent_runtime.model.deepseek.business_query_plan_v6 import (
    BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION,
    BUSINESS_QUERY_PLAN_TASK_VERSION,
    build_business_query_plan_task_definition,
)


def test_v6_prompt_defines_bare_slot_serialization_without_changing_catalog() -> None:
    definition = build_business_query_plan_task_definition(timeout_ms=8000)
    request = definition.build_request(
        BusinessQueryPlanTaskInput(
            minimized_question=(
                "查询姓protected-ref(slot-1)或姓protected-ref(slot-2)的员工"
            ),
            catalog={"schema_version": 3, "snapshot_id": "a" * 64},
            catalog_snapshot_id="a" * 64,
        )
    )

    assert definition.task_version == BUSINESS_QUERY_PLAN_TASK_VERSION == "business-query-plan-v6"
    assert request.task_version == "business-query-plan-v6"
    assert '{"value_ref":"slot-1"}' in BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION
    assert (
        '{"value_refs":["slot-1","slot-2"]}'
        in BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION
    )
    for required in (
        "only a wrapper in the question",
        "bare slot ID",
        "every semantically corresponding slot exactly once",
        "never omit, duplicate, rename, invent",
    ):
        assert required in BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION


def test_v5_remains_a_distinct_historical_task() -> None:
    from agent_runtime.model.deepseek.business_query_plan_v5 import (
        BUSINESS_QUERY_PLAN_TASK_VERSION as V5_TASK_VERSION,
    )

    assert V5_TASK_VERSION == "business-query-plan-v5"
    assert V5_TASK_VERSION != BUSINESS_QUERY_PLAN_TASK_VERSION
