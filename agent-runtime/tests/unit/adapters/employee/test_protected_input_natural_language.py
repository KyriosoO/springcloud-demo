from __future__ import annotations

import pytest

from agent_runtime.adapters.employee.protected_input import EmployeeProtectedValueExtractor
from agent_runtime.business.query_plan import InvalidProtectedValue
from agent_runtime.model.contracts import QuestionEgressDisposition
from agent_runtime.model.input_guard import QuestionEgressGuard


@pytest.mark.parametrize(
    "question,values",
    (
        ("姓杨的员工", ("杨",)),
        ("杨姓员工", ("杨",)),
        ("姓氏为杨的员工", ("杨",)),
        ("是否有姓欧阳的", ("欧阳",)),
        ("查询姓杨或姓王的员工", ("杨", "王")),
        ("帮我找杨姓、王姓员工", ("杨", "王")),
        ("查询姓名为杨明或王芳的员工", ("杨明", "王芳")),
        ("查找杨明、王芳这几名员工", ("杨明", "王芳")),
        ("查询姓杨且姓名中包含明的员工", ("杨", "明")),
        ("查找杨姓、名字包含华的员工", ("杨", "华")),
        ("查一下姓名为杨明的。", ("杨明",)),
    ),
)
def test_employee_name_variants_create_ordered_typed_slots(
    question: str,
    values: tuple[str, ...],
) -> None:
    slots = EmployeeProtectedValueExtractor().extract(question, request_id="request-1")
    assert tuple(slots.values.values()) == values
    assert tuple(slots.logical_fields.values()) == ("chinese_name",) * len(values)

    decision = QuestionEgressGuard().evaluate_business(
        question,
        protected_values=slots.values,
    )
    assert decision.disposition is QuestionEgressDisposition.ALLOWED
    assert decision.minimized_question is not None
    assert all(value not in decision.minimized_question for value in values)
    assert decision.minimized_question.count("protected-ref(") == len(values)


def test_extractor_preserves_connectors_for_model_semantics() -> None:
    question = "查询姓杨且姓名中包含明的员工"
    slots = EmployeeProtectedValueExtractor().extract(question, request_id="request-1")
    decision = QuestionEgressGuard().evaluate_business(
        question,
        protected_values=slots.values,
    )
    assert decision.minimized_question == (
        "查询姓protected-ref(slot-1)且姓名中包含protected-ref(slot-2)的员工"
    )


@pytest.mark.parametrize(
    "question",
    (
        "查询姓杨或姓杨的员工",
        "查询姓名为杨明或杨明的员工",
        "查询姓名中包含姓名的员工",
    ),
)
def test_ambiguous_or_duplicate_name_extraction_fails_closed(question: str) -> None:
    with pytest.raises(InvalidProtectedValue):
        EmployeeProtectedValueExtractor().extract(question, request_id="request-1")
