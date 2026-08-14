from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import httpx
import pytest

from agent_runtime.adapters.employee.definition import employee_detail_definition
from agent_runtime.bootstrap import LocalModelCompositionRoot
from agent_runtime.business.egress import BusinessEgressProjector
from agent_runtime.business.grounding import BusinessAnswerGroundingPolicy
from agent_runtime.business.handler import BoundBusinessActionHandler
from agent_runtime.business.http_client import UserJwtBusinessHttpClient
from agent_runtime.business.settings import GlobalBusinessEgressPolicy
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
from tests.integration.adapters.employee.egress_candidate_v2 import (
    MAXIMUM_PAID_ANSWER_CALLS,
    RUN_ID,
    BudgetedEmployeeAnswerTransportV2,
    EmployeeEgressEvidenceWriteV2Error,
    EmployeeEgressFailurePhase,
    EmployeeEgressFailureReason,
    EmployeeEgressLifecycleJournalV2,
    EmployeeEgressSafetySnapshotV2,
    LiveEmployeeTransportV2,
    ModelTerminalStatus,
    build_employee_egress_snapshot,
    count_forbidden_log_literals,
    finalize_employee_egress_evidence_v2,
    record_failure_terminal,
    safe_question,
    validate_employee_egress_lifecycle_v2,
)
from tests.model_helpers import FakeStructuredModelTransport, call_with_model_context


_SYNTHETIC_IDENTIFIER = "SYNTH-CANDIDATE-V2-0001"


def _model_response(*, valid: bool = True) -> StructuredModelResponse:
    value = (
        {
            "answer": "职位为工程师 [fact-0001]；工作地为上海 [fact-0002]。",
            "used_fact_ids": ["fact-0001", "fact-0002"],
            "unsupported_claims": [],
        }
        if valid
        else {
            "answer": "未经事实支持的回答。",
            "used_fact_ids": [],
            "unsupported_claims": [],
        }
    )
    return StructuredModelResponse(
        finish_kind=StructuredFinishKind.STOP,
        content=json.dumps(value, ensure_ascii=False, separators=(",", ":")),
        tool_calls=(),
        usage_total_tokens=18,
    )


def _employee_body(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "idCardNo": _SYNTHETIC_IDENTIFIER,
        "memberNo": "SYNTH-M-V2-0001",
        "chineseName": "合成员工",
        "publicEmail": "synthetic-v2@example.invalid",
        "position": "工程师",
        "workBaseSi": "上海",
    }
    value.update(overrides)
    return value


def _journal(tmp_path: Path) -> EmployeeEgressLifecycleJournalV2:
    return EmployeeEgressLifecycleJournalV2(
        tmp_path / f"{RUN_ID}.lifecycle.jsonl",
        run_id=RUN_ID,
        manifest_sha256="a" * 64,
    )


async def _capability_result(
    journal: EmployeeEgressLifecycleJournalV2,
    *,
    body: dict[str, object] | None = None,
    failure: Exception | None = None,
) -> tuple[CapabilityResult, LiveEmployeeTransportV2]:
    async def respond(request: httpx.Request) -> httpx.Response:
        del request
        if failure is not None:
            raise failure
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            content=json.dumps(
                _employee_body() if body is None else body,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8"),
        )

    client = httpx.AsyncClient(
        base_url="http://employee.invalid",
        transport=httpx.MockTransport(respond),
        follow_redirects=False,
        trust_env=False,
    )
    transport = LiveEmployeeTransportV2(client, journal)
    definition = employee_detail_definition()
    snapshot = build_employee_egress_snapshot()
    handler = BoundBusinessActionHandler(
        definition=definition,
        settings=dict(snapshot.actions)[definition.descriptor.capability_id],
        client=UserJwtBusinessHttpClient(transport=transport, max_response_bytes=1_048_576),
        user_projector=BusinessUserResultProjector(),
        egress_projector=BusinessEgressProjector(),
        egress_policy=GlobalBusinessEgressPolicy.from_settings(snapshot.global_settings),
        config_snapshot_id=snapshot.snapshot_id,
        max_user_result_bytes=262_144,
    )
    result = await handler.handle(
        definition.argument_validator.validate({"employee_identifier": _SYNTHETIC_IDENTIFIER}),
        scope(safe_question()).context,
    )
    return result, transport


async def _answer_once(
    *,
    result: CapabilityResult,
    transport: BudgetedEmployeeAnswerTransportV2,
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


def _finalize_failure(
    journal: EmployeeEgressLifecycleJournalV2,
    tmp_path: Path,
    *,
    phase: EmployeeEgressFailurePhase,
    reason: EmployeeEgressFailureReason,
) -> dict[str, object]:
    record_failure_terminal(journal, phase=phase, reason=reason)
    return finalize_employee_egress_evidence_v2(
        journal=journal,
        evidence_path=tmp_path / "result.json",
        config_snapshot_id=build_employee_egress_snapshot().snapshot_id,
    )


@pytest.mark.asyncio
async def test_v2_real_handler_fake_transport_passes_with_exact_lifecycle(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    result, employee_transport = await _capability_result(journal)
    delegate = FakeStructuredModelTransport(_model_response())
    model_transport = BudgetedEmployeeAnswerTransportV2(
        delegate=delegate,
        journal=journal,
        forbidden_literals=(
            _SYNTHETIC_IDENTIFIER,
            "SYNTH-M-V2-0001",
            "合成员工",
            "synthetic-v2@example.invalid",
        ),
    )

    assert result.status is CapabilityStatus.SUCCESS
    assert result.egress.disposition is EgressDisposition.ALLOWED
    for _ in range(MAXIMUM_PAID_ANSWER_CALLS):
        assert await _answer_once(result=result, transport=model_transport) is (
            AnswerGenerationDecisionKind.ANSWER
        )
        model_transport.record_terminal("answer")
    journal.record_run_terminal(status="passed", failure_phase=None, failure_reason=None)
    evidence = finalize_employee_egress_evidence_v2(
        journal=journal,
        evidence_path=tmp_path / "result.json",
        config_snapshot_id=build_employee_egress_snapshot().snapshot_id,
    )
    snapshot = validate_employee_egress_lifecycle_v2(
        journal.path,
        consumed_path=journal.consumed_marker_path,
        manifest_sha256="a" * 64,
    )

    assert employee_transport.calls == 1
    assert model_transport.calls == model_transport.terminal_calls == delegate.calls == 30
    assert snapshot.employee_detail_requests == 1
    assert snapshot.employee_detail_terminal == "completed"
    assert snapshot.model_outbound_calls == snapshot.model_terminal_records == 30
    assert snapshot.valid_answers == 30
    assert evidence["status"] == "passed"
    assert evidence["counts"]["employeeDetailRequests"] == 1
    assert evidence["counts"]["retryCount"] == 0
    assert evidence["counts"]["resumeCount"] == 0
    raw = json.dumps(evidence, ensure_ascii=False)
    assert all(
        value not in raw
        for value in (
            _SYNTHETIC_IDENTIFIER,
            "SYNTH-M-V2-0001",
            "合成员工",
            "synthetic-v2@example.invalid",
        )
    )
    await employee_transport.aclose()


def test_v2_failure_before_employee_request_is_exact_and_unconsumed(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    evidence = _finalize_failure(
        journal,
        tmp_path,
        phase=EmployeeEgressFailurePhase.EMPLOYEE_REQUEST,
        reason=EmployeeEgressFailureReason.EMPLOYEE_REQUEST_FAILED,
    )

    assert evidence["status"] == "failed_unconsumed"
    assert evidence["counts"]["employeeDetailRequests"] == 0  # type: ignore[index]
    assert evidence["counts"]["actualAnswerCalls"] == 0  # type: ignore[index]
    assert not journal.consumed_marker_path.exists()


@pytest.mark.asyncio
async def test_v2_employee_transport_failure_has_started_and_failed_terminal(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    result, transport = await _capability_result(
        journal,
        failure=httpx.ConnectError("synthetic-connect-failure"),
    )
    evidence = _finalize_failure(
        journal,
        tmp_path,
        phase=EmployeeEgressFailurePhase.EMPLOYEE_REQUEST,
        reason=EmployeeEgressFailureReason.EMPLOYEE_REQUEST_FAILED,
    )

    assert result.status is CapabilityStatus.DOWNSTREAM_FAILURE
    assert evidence["status"] == "failed_unconsumed"
    assert evidence["counts"]["employeeDetailRequests"] == 1  # type: ignore[index]
    snapshot = validate_employee_egress_lifecycle_v2(
        journal.path,
        consumed_path=journal.consumed_marker_path,
        manifest_sha256="a" * 64,
    )
    assert snapshot.employee_detail_terminal == "failed"
    await transport.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "phase", "reason"),
    (
        (
            {"unexpected": "value"},
            EmployeeEgressFailurePhase.EMPLOYEE_RESULT,
            EmployeeEgressFailureReason.EMPLOYEE_RESULT_INVALID,
        ),
        (
            _employee_body(position=None, workBaseSi=None),
            EmployeeEgressFailurePhase.EGRESS_PROJECTION,
            EmployeeEgressFailureReason.EGRESS_PROJECTION_INVALID,
        ),
    ),
)
async def test_v2_response_and_projection_failures_remain_unconsumed(
    tmp_path: Path,
    body: dict[str, object],
    phase: EmployeeEgressFailurePhase,
    reason: EmployeeEgressFailureReason,
) -> None:
    journal = _journal(tmp_path)
    result, transport = await _capability_result(journal, body=body)
    evidence = _finalize_failure(journal, tmp_path, phase=phase, reason=reason)

    assert result.egress.disposition is not EgressDisposition.ALLOWED
    assert evidence["status"] == "failed_unconsumed"
    assert evidence["counts"]["employeeDetailRequests"] == 1  # type: ignore[index]
    assert evidence["counts"]["actualAnswerCalls"] == 0  # type: ignore[index]
    await transport.aclose()


@pytest.mark.asyncio
async def test_v2_model_setup_and_invalid_request_fail_before_consumption(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    result, employee_transport = await _capability_result(journal)
    delegate = FakeStructuredModelTransport(_model_response())
    model_transport = BudgetedEmployeeAnswerTransportV2(delegate=delegate, journal=journal)
    invalid_request = StructuredModelRequest(
        task_id=ModelTaskId.KNOWLEDGE_SUMMARY,
        task_version="answer-generation-v1",
        system_instruction="invalid",
        user_payload_json="{}",
        tools=(),
        tool_mode=StructuredToolMode.NONE,
        output_mode=StructuredOutputMode.JSON_OBJECT,
        max_output_tokens=1,
    )

    assert result.status is CapabilityStatus.SUCCESS
    with pytest.raises(RuntimeError, match="employee.egress_candidate_v2_request_invalid"):
        await model_transport.complete(invalid_request, call_deadline=100.0)
    evidence = _finalize_failure(
        journal,
        tmp_path,
        phase=EmployeeEgressFailurePhase.MODEL_CALL,
        reason=EmployeeEgressFailureReason.MODEL_REQUEST_INVALID,
    )

    assert delegate.calls == 0
    assert evidence["status"] == "failed_unconsumed"
    assert evidence["counts"]["actualAnswerCalls"] == 0  # type: ignore[index]
    await employee_transport.aclose()


@pytest.mark.asyncio
async def test_v2_failure_after_consumed_before_outbound_is_failed_consumed(tmp_path: Path) -> None:
    class FailAfterConsumedJournal(EmployeeEgressLifecycleJournalV2):
        def record_model_outbound_started(self, *, ordinal: int) -> None:
            del ordinal
            raise RuntimeError("synthetic-after-consumed")

    journal = FailAfterConsumedJournal(
        tmp_path / f"{RUN_ID}.lifecycle.jsonl",
        run_id=RUN_ID,
        manifest_sha256="a" * 64,
    )
    result, employee_transport = await _capability_result(journal)
    delegate = FakeStructuredModelTransport(_model_response())
    model_transport = BudgetedEmployeeAnswerTransportV2(delegate=delegate, journal=journal)

    assert await _answer_once(result=result, transport=model_transport) is (
        AnswerGenerationDecisionKind.FAILURE
    )
    evidence = _finalize_failure(
        journal,
        tmp_path,
        phase=EmployeeEgressFailurePhase.MODEL_CALL,
        reason=EmployeeEgressFailureReason.MODEL_CALL_FAILED,
    )

    assert journal.consumed_marker_path.is_file()
    assert delegate.calls == 0
    assert evidence["status"] == "failed_consumed"
    assert evidence["counts"]["actualAnswerCalls"] == 0  # type: ignore[index]
    await employee_transport.aclose()


@pytest.mark.asyncio
async def test_v2_model_terminal_and_threshold_failure_are_finite_and_consumed(
    tmp_path: Path,
) -> None:
    journal = _journal(tmp_path)
    result, employee_transport = await _capability_result(journal)
    delegate = FakeStructuredModelTransport(_model_response(valid=False))
    model_transport = BudgetedEmployeeAnswerTransportV2(delegate=delegate, journal=journal)

    for _ in range(MAXIMUM_PAID_ANSWER_CALLS):
        assert await _answer_once(result=result, transport=model_transport) is (
            AnswerGenerationDecisionKind.FAILURE
        )
        model_transport.record_terminal("invalid_output")
    evidence = _finalize_failure(
        journal,
        tmp_path,
        phase=EmployeeEgressFailurePhase.THRESHOLD,
        reason=EmployeeEgressFailureReason.THRESHOLD_NOT_MET,
    )

    assert evidence["status"] == "failed_consumed"
    assert evidence["counts"]["actualAnswerCalls"] == 30  # type: ignore[index]
    assert evidence["counts"]["terminalAnswerRecords"] == 30  # type: ignore[index]
    assert evidence["counts"]["validAnswers"] == 0  # type: ignore[index]
    assert delegate.calls == 30
    await employee_transport.aclose()


@pytest.mark.asyncio
async def test_v2_unexpected_model_delegate_failure_closes_open_terminal(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    result, employee_transport = await _capability_result(journal)
    delegate = FakeStructuredModelTransport(failure=RuntimeError("synthetic-provider-failure"))
    model_transport = BudgetedEmployeeAnswerTransportV2(delegate=delegate, journal=journal)

    assert await _answer_once(result=result, transport=model_transport) is (
        AnswerGenerationDecisionKind.FAILURE
    )
    assert model_transport.calls == 1
    assert model_transport.terminal_calls == 0
    model_transport.record_terminal("provider_failure")
    evidence = _finalize_failure(
        journal,
        tmp_path,
        phase=EmployeeEgressFailurePhase.MODEL_CALL,
        reason=EmployeeEgressFailureReason.MODEL_CALL_FAILED,
    )

    assert evidence["status"] == "failed_consumed"
    assert evidence["counts"]["actualAnswerCalls"] == 1  # type: ignore[index]
    assert evidence["counts"]["terminalAnswerRecords"] == 1  # type: ignore[index]
    assert evidence["outcomes"] == [{"attemptOrdinal": 1, "status": "provider_failure"}]
    await employee_transport.aclose()


def test_v2_cleanup_and_evidence_write_failures_are_fail_closed(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    record_failure_terminal(
        journal,
        phase=EmployeeEgressFailurePhase.CLEANUP,
        reason=EmployeeEgressFailureReason.CLEANUP_FAILED,
    )
    evidence_path = tmp_path / "result.json"
    evidence_path.write_text("reserved", encoding="utf-8")

    with pytest.raises(
        EmployeeEgressEvidenceWriteV2Error,
        match="employee.egress_candidate_v2_evidence_write_failed",
    ):
        finalize_employee_egress_evidence_v2(
            journal=journal,
            evidence_path=evidence_path,
            config_snapshot_id=build_employee_egress_snapshot().snapshot_id,
        )
    assert evidence_path.read_text(encoding="utf-8") == "reserved"
    assert not journal.consumed_marker_path.exists()


def test_v2_log_leak_is_finite_and_cannot_pass(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    leak_count = count_forbidden_log_literals(
        "prefix synthetic-secret suffix synthetic-secret",
        ("synthetic-secret", "synthetic-secret", ""),
    )
    assert leak_count == 2
    record_failure_terminal(
        journal,
        phase=EmployeeEgressFailurePhase.CLEANUP,
        reason=EmployeeEgressFailureReason.LOG_LEAK_DETECTED,
    )
    evidence = finalize_employee_egress_evidence_v2(
        journal=journal,
        evidence_path=tmp_path / "log-leak-result.json",
        config_snapshot_id=build_employee_egress_snapshot().snapshot_id,
        safety=EmployeeEgressSafetySnapshotV2(log_leak_count=leak_count),
    )

    assert evidence["status"] == "failed_unconsumed"
    assert evidence["failure"] == {
        "phase": "cleanup",
        "reason": "log_leak_detected",
    }
    assert evidence["safety"]["logLeakCount"] == 2
