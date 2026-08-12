from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict, cast

import pytest

from agent_runtime.bootstrap import LocalModelCompositionRoot
from agent_runtime.capability_api.contracts import JsonObject
from agent_runtime.graph.action_resolution import (
    CapabilitySelectionDecisionKind,
    CapabilitySelectionInput,
)
from agent_runtime.graph.state import (
    AnswerGenerationDecisionKind,
    AnswerGenerationInput,
    ModelNodeFailureKind,
)
from agent_runtime.model.contracts import (
    QuestionDataClass,
    QuestionEgressDisposition,
)
from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.model.question_policy import classify_question
from agent_runtime.model.settings import ModelSettings
from tests.helpers import descriptor
from tests.model_helpers import AcceptGroundingPolicy, FakeStructuredModelTransport


class SensitiveQuestionCase(TypedDict):
    category: str
    question: str


_FIXTURE_PATH = Path(__file__).parents[2] / "fixtures" / "business_sensitive_questions.json"
_CATEGORY_CLASS = {
    "personal_identifier": QuestionDataClass.PERSONAL_IDENTIFIER,
    "employee_identifier": QuestionDataClass.EMPLOYEE_IDENTIFIER,
    "transaction_identifier": QuestionDataClass.TRANSACTION_IDENTIFIER,
    "financial_account": QuestionDataClass.FINANCIAL_ACCOUNT,
    "contact": QuestionDataClass.CONTACT,
    "credential_or_secret": QuestionDataClass.CREDENTIAL_OR_SECRET,
    "free_text_sensitive": QuestionDataClass.FREE_TEXT_SENSITIVE,
    "generic_business": QuestionDataClass.GENERIC_BUSINESS,
}


def _load_cases() -> tuple[SensitiveQuestionCase, ...]:
    raw = cast(object, json.loads(_FIXTURE_PATH.read_text(encoding="utf-8")))
    assert type(raw) is dict
    document = cast(dict[str, object], raw)
    assert set(document) == {"schemaVersion", "cases"}
    assert type(document["schemaVersion"]) is int and document["schemaVersion"] == 1
    raw_cases = document["cases"]
    assert type(raw_cases) is list
    cases: list[SensitiveQuestionCase] = []
    for raw_case in raw_cases:
        assert type(raw_case) is dict
        case = cast(dict[str, object], raw_case)
        assert set(case) == {"category", "question"}
        assert type(case["category"]) is str
        assert type(case["question"]) is str
        cases.append(
            SensitiveQuestionCase(
                category=case["category"],
                question=case["question"],
            )
        )
    assert tuple(case["category"] for case in cases) == tuple(_CATEGORY_CLASS)
    return tuple(cases)


def _safe_payload() -> JsonObject:
    return {
        "schema_version": 1,
        "facts": (
            {"fact_id": "fact-0001", "value": "SYNTHETIC", "source": {"field_id": "status"}},
        ),
    }


def test_business_sensitive_fixture_has_exact_schema_and_policy_categories() -> None:
    for case in _load_cases():
        assert classify_question(case["question"]) == frozenset({_CATEGORY_CLASS[case["category"]]})


@pytest.mark.asyncio
async def test_sensitive_business_questions_are_zero_call_for_selection_and_answer() -> None:
    transport = FakeStructuredModelTransport()
    grounding = AcceptGroundingPolicy()
    components = LocalModelCompositionRoot.build(
        settings=ModelSettings(),
        transport=transport,
        grounding_policies={"test.query": grounding},
    )
    try:
        for case in _load_cases():
            if case["category"] == "generic_business":
                continue
            question = case["question"]
            selection = await components.action_selector(
                CapabilitySelectionInput(question=question, descriptors=(descriptor(),))
            )
            answer = await components.answer_generator(
                AnswerGenerationInput(
                    question=question,
                    capability_id="test.query",
                    safe_payload=_safe_payload(),
                )
            )

            assert selection.kind is CapabilitySelectionDecisionKind.FAILURE
            assert selection.failure is not None
            assert selection.failure.kind is ModelNodeFailureKind.INPUT_DENIED
            assert answer.kind is AnswerGenerationDecisionKind.FAILURE
            assert answer.failure is not None
            assert answer.failure.kind is ModelNodeFailureKind.INPUT_DENIED
            assert transport.calls == 0
            assert grounding.calls == 0
    finally:
        await components.aclose()


@pytest.mark.parametrize(
    "question",
    (
        "查询员工张三的详情",
        "查询金额为 100.00 元的交易",
    ),
)
@pytest.mark.asyncio
async def test_domain_specific_unclassified_details_fail_closed_with_zero_transport(question: str) -> None:
    transport = FakeStructuredModelTransport()
    grounding = AcceptGroundingPolicy()
    components = LocalModelCompositionRoot.build(
        settings=ModelSettings(),
        transport=transport,
        grounding_policies={"test.query": grounding},
    )
    try:
        selection = await components.action_selector(
            CapabilitySelectionInput(question=question, descriptors=(descriptor(),))
        )
        answer = await components.answer_generator(
            AnswerGenerationInput(
                question=question,
                capability_id="test.query",
                safe_payload=_safe_payload(),
            )
        )

        assert selection.kind is CapabilitySelectionDecisionKind.FAILURE
        assert selection.failure is not None
        assert selection.failure.kind is ModelNodeFailureKind.INPUT_DENIED
        assert answer.kind is AnswerGenerationDecisionKind.FAILURE
        assert answer.failure is not None
        assert answer.failure.kind is ModelNodeFailureKind.INPUT_DENIED
        assert transport.calls == 0
        assert grounding.calls == 0
    finally:
        await components.aclose()


def test_generic_business_case_only_passes_question_egress_guard() -> None:
    generic = next(case for case in _load_cases() if case["category"] == "generic_business")

    decision = QuestionEgressGuard().evaluate(generic["question"])

    assert decision.disposition is QuestionEgressDisposition.ALLOWED
    assert decision.minimized_question == generic["question"]
