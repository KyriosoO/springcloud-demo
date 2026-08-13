from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from agent_runtime.adapters.employee.definition import employee_detail_definition
from agent_runtime.adapters.employee.settings import EmployeeAdapterSettings
from agent_runtime.bootstrap import LocalModelCompositionRoot
from agent_runtime.business.egress import BusinessEgressProjector
from agent_runtime.business.grounding import BusinessAnswerGroundingPolicy
from agent_runtime.business.handler import BoundBusinessActionHandler
from agent_runtime.business.http_client import UserJwtBusinessHttpClient
from agent_runtime.business.settings import (
    BusinessGlobalSettings,
    GlobalBusinessEgressPolicy,
)
from agent_runtime.business.user_projection import BusinessUserResultProjector
from agent_runtime.capability_api.contracts import CapabilityResult, CapabilityStatus, EgressDisposition
from agent_runtime.graph.nodes import route_after_capability
from agent_runtime.graph.state import (
    AgentRequestState,
    AnswerGenerationDecisionKind,
    AnswerGenerationInput,
)
from agent_runtime.model.contracts import (
    ModelTaskId,
    StructuredFinishKind,
    StructuredModelRequest,
    StructuredModelResponse,
    StructuredOutputMode,
    StructuredToolMode,
)
from agent_runtime.model.settings import ModelSettings
from tests.helpers import scope
from tests.integration.adapters.employee.egress_candidate import (
    AUTHORIZATION_REFERENCE,
    MAXIMUM_PAID_ANSWER_CALLS,
    MODEL_VISIBLE_FIELD_IDS,
    RUN_ID,
    BudgetedEmployeeAnswerTransport,
    EmployeeEgressAttemptJournal,
    build_employee_egress_snapshot,
    safe_question,
    validate_attempt_journal,
)
from tests.integration.adapters.employee.test_sensitive_egress_zero_call import (
    FakeEmployeeServer,
    _employee_body,
)
from tests.model_helpers import FakeStructuredModelTransport, call_with_model_context


_SYNTHETIC_IDENTIFIER = "SYNTH-CANDIDATE-0001"


def _response() -> StructuredModelResponse:
    return StructuredModelResponse(
        finish_kind=StructuredFinishKind.STOP,
        content=json.dumps(
            {
                "answer": "职位为工程师 [fact-0001]；工作地为上海 [fact-0002]。",
                "used_fact_ids": ["fact-0001", "fact-0002"],
                "unsupported_claims": [],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        tool_calls=(),
        usage_total_tokens=18,
    )


async def _synthetic_capability_result() -> tuple[CapabilityResult, FakeEmployeeServer]:
    definition = employee_detail_definition()
    snapshot = build_employee_egress_snapshot()
    settings = dict(snapshot.actions)[definition.descriptor.capability_id]
    server = FakeEmployeeServer(_employee_body(idCardNo=_SYNTHETIC_IDENTIFIER))
    handler = BoundBusinessActionHandler(
        definition=definition,
        settings=settings,
        client=UserJwtBusinessHttpClient(transport=server, max_response_bytes=1_048_576),
        user_projector=BusinessUserResultProjector(),
        egress_projector=BusinessEgressProjector(),
        egress_policy=GlobalBusinessEgressPolicy.from_settings(snapshot.global_settings),
        config_snapshot_id=snapshot.snapshot_id,
        max_user_result_bytes=262_144,
    )
    input_value = definition.argument_validator.validate(
        {"employee_identifier": _SYNTHETIC_IDENTIFIER}
    )
    return await handler.handle(input_value, scope(safe_question()).context), server


async def _call_answer(
    *,
    result: CapabilityResult,
    transport: BudgetedEmployeeAnswerTransport,
) -> AnswerGenerationDecisionKind:
    assert route_after_capability(cast(AgentRequestState, {"capability_result": result})) == "answer"
    components = LocalModelCompositionRoot.build(
        settings=ModelSettings(),
        transport=transport,
        grounding_policies={"employee.detail": BusinessAnswerGroundingPolicy()},
    )
    try:
        safe_payload = result.egress.safe_payload
        assert safe_payload is not None
        decision = await call_with_model_context(
            lambda: components.answer_generator(
                AnswerGenerationInput(
                    question=safe_question(),
                    capability_id="employee.detail",
                    safe_payload=safe_payload,
                )
            ),
            question=safe_question(),
        )
        return decision.kind
    finally:
        await components.aclose()


@pytest.mark.asyncio
async def test_fake_candidate_runs_one_synthetic_employee_call_and_exact_thirty_answers(
    tmp_path: Path,
) -> None:
    result, server = await _synthetic_capability_result()
    delegate = FakeStructuredModelTransport(_response())
    consumed = tmp_path / "consumed.json"
    journal_path = tmp_path / "attempts.jsonl"
    transport = BudgetedEmployeeAnswerTransport(
        delegate=delegate,
        consumed_marker_path=consumed,
        journal=EmployeeEgressAttemptJournal(journal_path),
        manifest_sha256="a" * 64,
        forbidden_literals=(
            _SYNTHETIC_IDENTIFIER,
            "SYNTH-M001",
            "合成员工",
            "synthetic@example.invalid",
        ),
    )

    assert result.status is CapabilityStatus.SUCCESS
    assert result.egress.disposition is EgressDisposition.ALLOWED
    assert len(server.requests) == 1
    for _ in range(MAXIMUM_PAID_ANSWER_CALLS):
        assert await _call_answer(result=result, transport=transport) is AnswerGenerationDecisionKind.ANSWER
        transport.record_terminal("answer")

    assert transport.calls == delegate.calls == MAXIMUM_PAID_ANSWER_CALLS
    assert transport.retry_count == 0
    assert transport.forbidden_payload_field_count == 0
    assert transport.forbidden_literal_count == 0
    marker = json.loads(consumed.read_text(encoding="utf-8"))
    assert marker["runId"] == RUN_ID
    assert marker["authorizationReference"] == AUTHORIZATION_REFERENCE
    assert marker["maximumPaidAnswerCalls"] == MAXIMUM_PAID_ANSWER_CALLS
    assert marker["retryAllowed"] is False
    assert marker["resumeAllowed"] is False
    journal = validate_attempt_journal(journal_path)
    assert len(journal) == 61
    assert all(record["event"] == "outbound_started" for record in journal[1::2])
    assert all(record["event"] == "call_terminal" for record in journal[2::2])

    assert await _call_answer(
        result=result,
        transport=transport,
    ) is AnswerGenerationDecisionKind.FAILURE
    assert delegate.calls == MAXIMUM_PAID_ANSWER_CALLS


@pytest.mark.asyncio
async def test_invalid_request_fails_before_consumption_and_delegate_call(tmp_path: Path) -> None:
    delegate = FakeStructuredModelTransport(_response())
    consumed = tmp_path / "consumed.json"
    transport = BudgetedEmployeeAnswerTransport(
        delegate=delegate,
        consumed_marker_path=consumed,
        journal=EmployeeEgressAttemptJournal(tmp_path / "attempts.jsonl"),
        manifest_sha256="a" * 64,
    )
    request = StructuredModelRequest(
        task_id=ModelTaskId.KNOWLEDGE_SUMMARY,
        task_version="answer-generation-v1",
        system_instruction="invalid",
        user_payload_json="{}",
        tools=(),
        tool_mode=StructuredToolMode.NONE,
        output_mode=StructuredOutputMode.JSON_OBJECT,
        max_output_tokens=1,
    )

    with pytest.raises(RuntimeError, match="employee.egress_candidate_request_invalid"):
        await transport.complete(request, call_deadline=100.0)
    assert delegate.calls == 0
    assert not consumed.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model_fields", "global_enabled", "expected_reason"),
    (
        ("", True, "business.no_model_fields"),
        ("position,work_base_si", False, "business.egress_disabled"),
    ),
)
async def test_candidate_negative_configuration_is_zero_model_call(
    model_fields: str,
    global_enabled: bool,
    expected_reason: str,
) -> None:
    definition = employee_detail_definition()
    settings = EmployeeAdapterSettings.from_env(
        {
            "AGENT_EMPLOYEE_DETAIL_ENABLED": "true",
            "AGENT_EMPLOYEE_DETAIL_MODEL_FIELDS": model_fields,
        }
    ).action
    server = FakeEmployeeServer(_employee_body(idCardNo=_SYNTHETIC_IDENTIFIER))
    handler = BoundBusinessActionHandler(
        definition=definition,
        settings=settings,
        client=UserJwtBusinessHttpClient(transport=server, max_response_bytes=1_048_576),
        user_projector=BusinessUserResultProjector(),
        egress_projector=BusinessEgressProjector(),
        egress_policy=GlobalBusinessEgressPolicy.from_settings(
            build_employee_egress_snapshot().global_settings
            if global_enabled
            else BusinessGlobalSettings()
        ),
        config_snapshot_id=build_employee_egress_snapshot().snapshot_id,
        max_user_result_bytes=262_144,
    )
    result = await handler.handle(
        definition.argument_validator.validate({"employee_identifier": _SYNTHETIC_IDENTIFIER}),
        scope(safe_question()).context,
    )
    delegate = FakeStructuredModelTransport(_response())

    assert result.egress.disposition is EgressDisposition.DENIED
    assert result.egress.reason_code == expected_reason
    assert route_after_capability(cast(AgentRequestState, {"capability_result": result})) == "fixed"
    assert delegate.calls == 0


def test_candidate_snapshot_freezes_exact_two_model_fields_and_defaults_remain_denied() -> None:
    snapshot = build_employee_egress_snapshot()
    settings = dict(snapshot.actions)["employee.detail"]

    assert settings.model_field_ids == MODEL_VISIBLE_FIELD_IDS
    assert snapshot.global_settings.egress_enabled is True
    assert len(snapshot.snapshot_id) == 64
    assert EmployeeAdapterSettings.from_env({}).action.model_field_ids == ()
