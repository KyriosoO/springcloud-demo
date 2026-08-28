from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from agent_runtime.adapters.employee.protected_input import EmployeeProtectedValueExtractor
from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.model.input_guard import QuestionEgressGuard
from tests.system_e2e.test_business_list_query_nonlive import (
    _ADMIN_TOKEN,
    _runtime,
    _scope,
)


@dataclass(frozen=True, slots=True)
class _NaturalLanguageCase:
    question: str
    filters: tuple[dict[str, object], ...]
    wire_operators: tuple[str, ...]
    wire_values: tuple[object, ...]
    protected_values: tuple[str, ...] = ()


_CASES = (
    _NaturalLanguageCase(
        "姓杨的员工",
        ({"field": "chinese_name", "operator": "prefix", "value": {"value_ref": "slot-1"}},),
        ("prefix",),
        ("杨",),
        ("杨",),
    ),
    _NaturalLanguageCase(
        "查询欧阳姓员工",
        ({"field": "chinese_name", "operator": "prefix", "value": {"value_ref": "slot-1"}},),
        ("prefix",),
        ("欧阳",),
        ("欧阳",),
    ),
    _NaturalLanguageCase(
        "查询姓杨或姓王的员工",
        ({"field": "chinese_name", "operator": "prefix_any", "value": {"value_refs": ("slot-1", "slot-2")}},),
        ("prefixAny",),
        (("杨", "王"),),
        ("杨", "王"),
    ),
    _NaturalLanguageCase(
        "查询姓名为杨明或王芳的员工",
        ({"field": "chinese_name", "operator": "in", "value": {"value_refs": ("slot-1", "slot-2")}},),
        ("in",),
        (("杨明", "王芳"),),
        ("杨明", "王芳"),
    ),
    _NaturalLanguageCase(
        "查询姓杨且姓名中包含“明”的员工",
        (
            {"field": "chinese_name", "operator": "prefix", "value": {"value_ref": "slot-1"}},
            {"field": "chinese_name", "operator": "contains", "value": {"value_ref": "slot-2"}},
        ),
        ("prefix", "contains"),
        ("杨", "明"),
        ("杨", "明"),
    ),
    _NaturalLanguageCase(
        "请查一下上海市的员工",
        ({"field": "contact_address", "operator": "contains", "value": {"literal": "上海市"}},),
        ("contains",),
        ("上海",),
    ),
    _NaturalLanguageCase(
        "查询江苏、浙江或上海的员工",
        ({"field": "contact_address", "operator": "contains_any", "value": {"literal": ("江苏", "浙江", "上海")}},),
        ("containsAny",),
        (("江苏", "浙江", "上海"),),
    ),
    _NaturalLanguageCase(
        "是否有姓杨的",
        ({"field": "chinese_name", "operator": "prefix", "value": {"value_ref": "slot-1"}},),
        ("prefix",),
        ("杨",),
        ("杨",),
    ),
)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _CASES, ids=lambda item: item.question)
async def test_natural_language_variants_use_one_llm_plan_and_one_employee_search(
    case: _NaturalLanguageCase,
) -> None:
    slots = EmployeeProtectedValueExtractor().extract(case.question, request_id="preview")
    decision = QuestionEgressGuard().evaluate_business(
        case.question,
        protected_values=slots.values,
    )
    assert decision.minimized_question is not None
    plan = {
        "domain": "employee",
        "action": "employee.search",
        "arguments": {
            "filters": case.filters,
            "page": 1,
            "size": 20,
            "sorts": (),
        },
    }
    runtime, model, employee, transaction, knowledge = _runtime(
        {decision.minimized_question: plan}
    )

    result = await runtime.ainvoke(
        question=case.question,
        scope=_scope(case.question, token=_ADMIN_TOKEN, case_id="employee-nl"),
    )
    await runtime.aclose()

    assert result.status is CapabilityStatus.SUCCESS
    assert result.capability_id == "employee.search"
    assert len(model.requests) == 1
    assert len(employee.requests) == 1
    assert transaction.requests == []
    assert knowledge.calls == 0
    assert employee.requests[0].request.relative_path == "/employees/es/search"
    model_payload = json.loads(model.requests[0].user_payload_json)
    assert all(value not in model_payload["question"] for value in case.protected_values)

    body = employee.requests[0].request.json_body
    assert body is not None
    raw = json.loads(body.content.decode("utf-8"))
    assert tuple(item["operator"] for item in raw["filters"]) == case.wire_operators
    actual_values = tuple(
        tuple(item["values"]) if "values" in item else item["value"]
        for item in raw["filters"]
    )
    assert actual_values == case.wire_values


@pytest.mark.asyncio
async def test_invalid_multivalue_plan_fails_before_employee_search() -> None:
    question = "查询姓杨或姓王的员工"
    slots = EmployeeProtectedValueExtractor().extract(question, request_id="preview")
    decision = QuestionEgressGuard().evaluate_business(question, protected_values=slots.values)
    assert decision.minimized_question is not None
    runtime, model, employee, transaction, knowledge = _runtime(
        {
            decision.minimized_question: {
                "domain": "employee",
                "action": "employee.search",
                "arguments": {
                    "filters": ({
                        "field": "chinese_name",
                        "operator": "in",
                        "value": {"value_refs": ("slot-1", "slot-1")},
                    },),
                    "page": 1,
                    "size": 20,
                    "sorts": (),
                },
            }
        }
    )

    result = await runtime.ainvoke(
        question=question,
        scope=_scope(question, token=_ADMIN_TOKEN, case_id="employee-nl-invalid"),
    )
    await runtime.aclose()

    assert result.status is CapabilityStatus.INVALID_ARGUMENT
    assert len(model.requests) == 1
    assert employee.requests == []
    assert transaction.requests == []
    assert knowledge.calls == 0
