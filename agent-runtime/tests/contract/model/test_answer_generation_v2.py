from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from agent_runtime.bootstrap import LocalModelCompositionRoot
from agent_runtime.business.grounding import BusinessAnswerGroundingPolicy
from agent_runtime.capability_api.contracts import JsonObject
from agent_runtime.graph.state import (
    AnswerGenerationDecision,
    AnswerGenerationDecisionKind,
    AnswerGenerationInput,
    ModelNodeFailureKind,
)
from agent_runtime.model.contracts import StructuredFinishKind, StructuredModelResponse
from agent_runtime.model.deepseek.answer_generator import (
    AnswerGenerationTaskInput,
    build_answer_generation_task_definition,
)
from agent_runtime.model.deepseek.answer_generator_v2 import (
    build_answer_generation_v2_task_definition,
)
from agent_runtime.model.settings import ModelSettings
from tests.model_helpers import FakeStructuredModelTransport, call_with_model_context


RUNTIME_ROOT = Path(__file__).resolve().parents[3]
ANSWER_V1 = RUNTIME_ROOT / "src/agent_runtime/model/deepseek/answer_generator.py"
ANSWER_V1_SHA256 = "9ad5bb89ebdb951fe0681a2bc07edd2b452d2ca495f3c100702eb2abfdc3271f"
QUESTION = "查询单个员工详情"
PAYLOAD: JsonObject = {
    "schema_version": 1,
    "policy_version": "business-egress-v1",
    "config_snapshot_id": "a" * 64,
    "facts": (
        {
            "fact_id": "fact-0001",
            "value_type": "text",
            "value": "工程师",
            "transform_id": "bounded_text",
            "source": {"record_ref": "record-0001", "field_id": "position"},
        },
        {
            "fact_id": "fact-0002",
            "value_type": "text",
            "value": "上海",
            "transform_id": "bounded_text",
            "source": {"record_ref": "record-0001", "field_id": "work_base_si"},
        },
    ),
    "presentation": {"mode": "business_facts", "action_id": "employee.detail"},
    "coverage": {"truncated": False},
}


def _response(*, answer: str) -> StructuredModelResponse:
    return StructuredModelResponse(
        finish_kind=StructuredFinishKind.STOP,
        content=json.dumps(
            {
                "answer": answer,
                "used_fact_ids": ["fact-0001", "fact-0002"],
                "unsupported_claims": [],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        tool_calls=(),
        usage_total_tokens=18,
    )


async def _generate(*, answer: str) -> tuple[AnswerGenerationDecision, FakeStructuredModelTransport]:
    transport = FakeStructuredModelTransport(_response(answer=answer))
    components = LocalModelCompositionRoot.build(
        settings=ModelSettings(),
        transport=transport,
        grounding_policies={"employee.detail": BusinessAnswerGroundingPolicy()},
    )
    try:
        decision = await call_with_model_context(
            lambda: components.answer_generator(
                AnswerGenerationInput(
                    question=QUESTION,
                    capability_id="employee.detail",
                    safe_payload=PAYLOAD,
                )
            ),
            question=QUESTION,
        )
    finally:
        await components.aclose()
    return decision, transport


def test_v2_changes_only_task_version_and_model_visible_instruction() -> None:
    v1 = build_answer_generation_task_definition(timeout_ms=1000)
    v2 = build_answer_generation_v2_task_definition(timeout_ms=1000)
    input = AnswerGenerationTaskInput(
        minimized_question=QUESTION,
        safe_payload=PAYLOAD,
    )
    v1_request = v1.build_request(input)
    v2_request = v2.build_request(input)

    assert v2.task_version == v2_request.task_version == "answer-generation-v2"
    assert v2.input_type is v1.input_type is AnswerGenerationTaskInput
    assert v2.task_id is v1.task_id
    assert v2.max_input_bytes == v1.max_input_bytes
    assert v2.timeout_ms == v1.timeout_ms
    assert v2.max_output_tokens == v1.max_output_tokens
    assert v2_request.user_payload_json == v1_request.user_payload_json
    assert v2_request.tools == v1_request.tools == ()
    response = _response(answer="职位为工程师 [fact-0001]；工作地为上海 [fact-0002]。")
    assert v2.parse_response(response) == v1.parse_response(response)
    assert "[fact-NNNN]" in v2_request.system_instruction
    assert "used_fact_ids" in v2_request.system_instruction
    assert "must exactly equal" in v2_request.system_instruction
    assert "[fact-0001]" in v2_request.system_instruction
    assert "[fact-0002]" in v2_request.system_instruction


def test_answer_v1_source_remains_byte_for_byte_immutable() -> None:
    assert hashlib.sha256(ANSWER_V1.read_bytes()).hexdigest() == ANSWER_V1_SHA256


@pytest.mark.asyncio
async def test_runtime_composition_uses_v2_and_accepts_fully_marked_answer() -> None:
    decision, transport = await _generate(
        answer="职位为工程师 [fact-0001]；工作地为上海 [fact-0002]。"
    )

    assert decision.kind is AnswerGenerationDecisionKind.ANSWER
    assert decision.answer_text == "职位为工程师 [fact-0001]；工作地为上海 [fact-0002]。"
    assert transport.calls == 1
    assert transport.requests[0].task_version == "answer-generation-v2"


@pytest.mark.asyncio
async def test_runtime_composition_keeps_strict_grounding_for_v1_style_unmarked_answer() -> None:
    decision, transport = await _generate(answer="职位为工程师；工作地为上海。")

    assert decision.kind is AnswerGenerationDecisionKind.FAILURE
    assert decision.failure is not None
    assert decision.failure.kind is ModelNodeFailureKind.INVALID_OUTPUT
    assert transport.calls == 1
    assert transport.requests[0].task_version == "answer-generation-v2"
