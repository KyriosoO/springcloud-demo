from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
from pathlib import Path

import httpx
import pytest

from agent_runtime.adapters.employee.definition import employee_detail_definition
from agent_runtime.bootstrap import LocalModelComponents, LocalModelCompositionRoot
from agent_runtime.business.egress import BusinessEgressProjector
from agent_runtime.business.grounding import BusinessAnswerGroundingPolicy
from agent_runtime.business.handler import BoundBusinessActionHandler
from agent_runtime.business.http_client import UserJwtBusinessHttpClient
from agent_runtime.business.settings import GlobalBusinessEgressPolicy
from agent_runtime.business.user_projection import BusinessUserResultProjector
from agent_runtime.capability_api.contracts import (
    CapabilityExecutionContext,
    CapabilityStatus,
    EgressDisposition,
    OpaqueUserToken,
    SubjectType,
)
from agent_runtime.graph.state import (
    AnswerGenerationDecisionKind,
    AnswerGenerationInput,
    ModelNodeFailureKind,
)
from agent_runtime.model.deepseek.transport import DeepSeekChatTransport, build_deepseek_http_client
from agent_runtime.model.settings import ModelProvider, ModelSettings
from tests.helpers import ManualCancellationSignal
from tests.integration.adapters.employee.egress_candidate_v2 import (
    MAXIMUM_PAID_ANSWER_CALLS,
    MINIMUM_VALID_ANSWER_CALLS,
    MODEL_VISIBLE_FIELD_IDS,
    RUN_ID,
    BudgetedEmployeeAnswerTransportV2,
    EmployeeEgressFailurePhase,
    EmployeeEgressFailureReason,
    EmployeeEgressLifecycleJournalV2,
    EmployeeEgressSafetySnapshotV2,
    LiveEmployeeTransportV2,
    ModelTerminalStatus,
    build_employee_egress_snapshot,
    consumed_path_for,
    count_forbidden_log_literals,
    finalize_employee_egress_evidence_v2,
    load_strict_json,
    record_failure_terminal,
    safe_question,
    sha256_file,
    validate_authorization,
    validate_manifest,
)
from tests.model_helpers import call_with_model_context


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_EMPLOYEE_EGRESS_CANDIDATE_V2") != "1",
    reason="requires explicit one-shot GATE-024 candidate-02 opt-in",
)


def _required(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"employee.egress_candidate_v2_env_missing:{name}")
    return value.strip()


def _context(token: str) -> CapabilityExecutionContext:
    return CapabilityExecutionContext(
        request_id="employee-egress-candidate-v2",
        correlation_id="employee-egress-candidate-v2",
        original_question=safe_question(),
        subject_id="employee-egress-authorized-reader",
        subject_type=SubjectType.USER,
        user_token=OpaqueUserToken.from_raw(token),
        deadline_monotonic=asyncio.get_running_loop().time() + 20.0,
        cancellation=ManualCancellationSignal(),
    )


def _forbidden_literals(domain_result: Mapping[str, object], identifier: str) -> tuple[str, ...]:
    values = {identifier}
    records = domain_result.get("records")
    if isinstance(records, tuple):
        for record in records:
            if not isinstance(record, Mapping):
                continue
            fields = record.get("fields")
            if not isinstance(fields, Mapping):
                continue
            for field_id, value in fields.items():
                if field_id not in MODEL_VISIBLE_FIELD_IDS and isinstance(value, str) and value:
                    values.add(value)
    return tuple(sorted(values))


def _log_forbidden_literals(
    domain_result: Mapping[str, object],
    *,
    identifier: str,
    token: str,
    api_key: str,
) -> tuple[str, ...]:
    values = {identifier, token, api_key}
    records = domain_result.get("records")
    if isinstance(records, tuple):
        for record in records:
            if not isinstance(record, Mapping):
                continue
            fields = record.get("fields")
            if isinstance(fields, Mapping):
                values.update(value for value in fields.values() if isinstance(value, str) and value)
    return tuple(sorted(values))


def _outcome(
    decision_kind: AnswerGenerationDecisionKind,
    failure_kind: object,
) -> ModelTerminalStatus:
    if decision_kind is AnswerGenerationDecisionKind.ANSWER:
        return "answer"
    if failure_kind is ModelNodeFailureKind.INPUT_DENIED:
        return "input_denied"
    if failure_kind is ModelNodeFailureKind.PROVIDER_TIMEOUT:
        return "timeout"
    if failure_kind is ModelNodeFailureKind.PROVIDER_FAILURE:
        return "provider_failure"
    return "invalid_output"


@pytest.mark.asyncio
async def test_gate024_candidate02_one_employee_result_and_thirty_bounded_answers(
    capfd: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    manifest_sha256 = _required("EMPLOYEE_EGRESS_V2_MANIFEST_SHA256")
    repository_root = Path(__file__).resolve().parents[5]
    evidence_directory = Path(__file__).parent / "evidence"
    manifest_path = evidence_directory / f"{RUN_ID}.manifest.json"
    authorization_path = evidence_directory / f"{RUN_ID}.authorization.json"
    if sha256_file(manifest_path) != manifest_sha256:
        raise RuntimeError("employee.egress_candidate_v2_authorization_binding_invalid")
    validate_manifest(load_strict_json(manifest_path), repository_root=repository_root)
    validate_authorization(load_strict_json(authorization_path), manifest_sha256=manifest_sha256)

    identifier = _required("EMPLOYEE_EGRESS_LIVE_TEST_IDENTIFIER")
    token = _required("EMPLOYEE_EGRESS_LIVE_USER_JWT")
    employee_base_url = _required("EMPLOYEE_EGRESS_LIVE_BASE_URL")
    if employee_base_url != "http://127.0.0.1:9210":
        raise RuntimeError("employee.egress_candidate_v2_endpoint_invalid")
    lifecycle_path = Path(_required("EMPLOYEE_EGRESS_V2_LIFECYCLE_OUTPUT"))
    consumed_path = Path(_required("EMPLOYEE_EGRESS_V2_CONSUMED_OUTPUT"))
    evidence_path = Path(_required("EMPLOYEE_EGRESS_V2_EVIDENCE_OUTPUT"))
    if (
        lifecycle_path != evidence_directory / f"{RUN_ID}.lifecycle.jsonl"
        or consumed_path != consumed_path_for(evidence_directory)
        or evidence_path != evidence_directory / f"{RUN_ID}.result.json"
    ):
        raise RuntimeError("employee.egress_candidate_v2_output_binding_invalid")

    snapshot = build_employee_egress_snapshot()
    definition = employee_detail_definition()
    settings = dict(snapshot.actions)[definition.descriptor.capability_id]
    journal = EmployeeEgressLifecycleJournalV2(
        lifecycle_path,
        run_id=RUN_ID,
        manifest_sha256=manifest_sha256,
    )
    failure_phase: EmployeeEgressFailurePhase | None = None
    failure_reason: EmployeeEgressFailureReason | None = None
    employee_transport: LiveEmployeeTransportV2 | None = None
    model_transport: BudgetedEmployeeAnswerTransportV2 | None = None
    model_components: LocalModelComponents | None = None
    model_client: httpx.AsyncClient | None = None
    valid_answers = 0
    log_forbidden_literals: tuple[str, ...] = (identifier, token)
    current_phase = EmployeeEgressFailurePhase.EMPLOYEE_REQUEST

    try:
        employee_client = httpx.AsyncClient(
            base_url=employee_base_url,
            follow_redirects=False,
            trust_env=False,
            timeout=httpx.Timeout(8.0),
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        )
        employee_transport = LiveEmployeeTransportV2(employee_client, journal)
        handler = BoundBusinessActionHandler(
            definition=definition,
            settings=settings,
            client=UserJwtBusinessHttpClient(
                transport=employee_transport,
                max_response_bytes=1_048_576,
            ),
            user_projector=BusinessUserResultProjector(),
            egress_projector=BusinessEgressProjector(),
            egress_policy=GlobalBusinessEgressPolicy.from_settings(snapshot.global_settings),
            config_snapshot_id=snapshot.snapshot_id,
            max_user_result_bytes=262_144,
        )
        result = await handler.handle(
            definition.argument_validator.validate({"employee_identifier": identifier}),
            _context(token),
        )
        current_phase = EmployeeEgressFailurePhase.EMPLOYEE_RESULT
        if result.status is not CapabilityStatus.SUCCESS or result.domain_result is None:
            failure_phase = current_phase
            failure_reason = EmployeeEgressFailureReason.EMPLOYEE_RESULT_INVALID
        else:
            current_phase = EmployeeEgressFailurePhase.EGRESS_PROJECTION
            if (
                result.egress.disposition is not EgressDisposition.ALLOWED
                or result.egress.safe_payload is None
            ):
                failure_phase = current_phase
                failure_reason = EmployeeEgressFailureReason.EGRESS_PROJECTION_INVALID
            else:
                safe_payload = result.egress.safe_payload
                current_phase = EmployeeEgressFailurePhase.MODEL_SETUP
                api_key = _required("LLM_API_KEY")
                log_forbidden_literals = _log_forbidden_literals(
                    result.domain_result,
                    identifier=identifier,
                    token=token,
                    api_key=api_key,
                )
                model_settings = ModelSettings.from_env(
                    {
                        "AGENT_MODEL_PROVIDER": "deepseek",
                        "AGENT_MODEL_MAX_CONCURRENCY": "1",
                        "AGENT_MODEL_ANSWER_TIMEOUT_MS": "15000",
                        "LLM_API_KEY": api_key,
                    }
                )
                if model_settings.provider is not ModelProvider.DEEPSEEK:
                    raise RuntimeError("employee.egress_candidate_v2_provider_invalid")
                model_client = build_deepseek_http_client(model_settings)
                model_transport = BudgetedEmployeeAnswerTransportV2(
                    delegate=DeepSeekChatTransport(settings=model_settings, client=model_client),
                    journal=journal,
                    forbidden_literals=_forbidden_literals(result.domain_result, identifier),
                )
                model_components = LocalModelCompositionRoot.build(
                    settings=ModelSettings(),
                    transport=model_transport,
                    grounding_policies={"employee.detail": BusinessAnswerGroundingPolicy()},
                )
                current_phase = EmployeeEgressFailurePhase.MODEL_CALL
                for _ in range(MAXIMUM_PAID_ANSWER_CALLS):
                    decision = await call_with_model_context(
                        lambda: model_components.answer_generator(
                            AnswerGenerationInput(
                                question=safe_question(),
                                capability_id="employee.detail",
                                safe_payload=safe_payload,
                            )
                        ),
                        question=safe_question(),
                    )
                    model_transport.record_terminal(
                        _outcome(
                            decision.kind,
                            None if decision.failure is None else decision.failure.kind,
                        )
                    )
                    if decision.kind is AnswerGenerationDecisionKind.ANSWER:
                        valid_answers += 1
                if model_transport.terminal_calls != MAXIMUM_PAID_ANSWER_CALLS:
                    raise RuntimeError("employee.egress_candidate_v2_model_terminal_incomplete")
                current_phase = EmployeeEgressFailurePhase.THRESHOLD
                if valid_answers < MINIMUM_VALID_ANSWER_CALLS:
                    failure_phase = current_phase
                    failure_reason = EmployeeEgressFailureReason.THRESHOLD_NOT_MET
    except BaseException:
        if model_transport is not None and model_transport.terminal_calls < model_transport.calls:
            model_transport.record_terminal("provider_failure")
        if failure_phase is None:
            failure_phase = current_phase
            failure_reason = {
                EmployeeEgressFailurePhase.EMPLOYEE_REQUEST: (
                    EmployeeEgressFailureReason.EMPLOYEE_REQUEST_FAILED
                ),
                EmployeeEgressFailurePhase.EMPLOYEE_RESULT: (
                    EmployeeEgressFailureReason.EMPLOYEE_RESULT_INVALID
                ),
                EmployeeEgressFailurePhase.EGRESS_PROJECTION: (
                    EmployeeEgressFailureReason.EGRESS_PROJECTION_INVALID
                ),
                EmployeeEgressFailurePhase.MODEL_SETUP: (
                    EmployeeEgressFailureReason.MODEL_SETUP_FAILED
                ),
                EmployeeEgressFailurePhase.MODEL_CALL: (
                    EmployeeEgressFailureReason.MODEL_CALL_FAILED
                ),
                EmployeeEgressFailurePhase.THRESHOLD: (
                    EmployeeEgressFailureReason.THRESHOLD_NOT_MET
                ),
                EmployeeEgressFailurePhase.CLEANUP: (
                    EmployeeEgressFailureReason.CLEANUP_FAILED
                ),
                EmployeeEgressFailurePhase.INTERNAL: (
                    EmployeeEgressFailureReason.INTERNAL_FAILURE
                ),
            }[current_phase]
    finally:
        cleanup_failed = False
        if model_components is not None:
            try:
                await model_components.aclose()
            except BaseException:
                cleanup_failed = True
        if model_client is not None:
            try:
                await model_client.aclose()
            except BaseException:
                cleanup_failed = True
        if employee_transport is not None:
            try:
                await employee_transport.aclose()
            except BaseException:
                cleanup_failed = True
        if cleanup_failed and failure_phase is None:
            failure_phase = EmployeeEgressFailurePhase.CLEANUP
            failure_reason = EmployeeEgressFailureReason.CLEANUP_FAILED

    captured = capfd.readouterr()
    captured_logs = "\n".join(record.getMessage() for record in caplog.records)
    log_leak_count = count_forbidden_log_literals(
        captured.out + captured.err + captured_logs,
        log_forbidden_literals,
    )
    if log_leak_count and failure_phase is None:
        failure_phase = EmployeeEgressFailurePhase.CLEANUP
        failure_reason = EmployeeEgressFailureReason.LOG_LEAK_DETECTED

    if failure_phase is None:
        journal.record_run_terminal(status="passed", failure_phase=None, failure_reason=None)
    else:
        assert failure_reason is not None
        record_failure_terminal(journal, phase=failure_phase, reason=failure_reason)
    safety = EmployeeEgressSafetySnapshotV2(
        forbidden_payload_field_count=0
        if model_transport is None
        else model_transport.forbidden_payload_field_count,
        forbidden_literal_count=0
        if model_transport is None
        else model_transport.forbidden_literal_count,
        log_leak_count=log_leak_count,
    )
    evidence = finalize_employee_egress_evidence_v2(
        journal=journal,
        evidence_path=evidence_path,
        config_snapshot_id=snapshot.snapshot_id,
        safety=safety,
    )
    if evidence["status"] != "passed":
        raise AssertionError("employee.egress_candidate_v2_failed")
