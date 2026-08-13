from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from agent_runtime.adapters.employee.definition import employee_detail_definition
from agent_runtime.bootstrap import LocalModelComponents, LocalModelCompositionRoot
from agent_runtime.business.egress import BusinessEgressProjector
from agent_runtime.business.grounding import BusinessAnswerGroundingPolicy
from agent_runtime.business.handler import BoundBusinessActionHandler
from agent_runtime.business.http_client import (
    FakeDomainHttpRequest,
    FakeDomainHttpResponse,
    UserJwtBusinessHttpClient,
)
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
from tests.integration.adapters.employee.egress_candidate import (
    AUTHORIZATION_EVIDENCE_REFS,
    AUTHORIZATION_REFERENCE,
    GATE_ID,
    MAXIMUM_PAID_ANSWER_CALLS,
    MINIMUM_VALID_ANSWER_CALLS,
    MODEL_TASK_BINDING,
    MODEL_VISIBLE_FIELD_IDS,
    RUN_ID,
    WORK_PACKAGE_ID,
    BudgetedEmployeeAnswerTransport,
    EmployeeEgressAttemptJournal,
    build_employee_egress_snapshot,
    load_strict_json,
    safe_question,
    sha256_file,
    validate_authorization,
    validate_attempt_journal,
    validate_live_evidence,
    validate_manifest,
    write_exclusive_json,
)
from tests.model_helpers import call_with_model_context


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_EMPLOYEE_EGRESS_CANDIDATE") != "1",
    reason="requires explicit one-shot GATE-024 opt-in",
)


def _required(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"employee.egress_candidate_env_missing:{name}")
    return value.strip()


class LiveEmployeeTransport:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self.calls = 0

    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        if self.calls:
            raise RuntimeError("employee.egress_candidate_employee_budget_exhausted")
        self.calls += 1
        response = await self._client.get(
            request.request.relative_path,
            headers={"Authorization": request.authorization, "Accept-Encoding": "identity"},
        )
        content_type = response.headers.get("Content-Type")
        return FakeDomainHttpResponse(
            status_code=response.status_code,
            content_type=None
            if content_type is None
            else content_type.split(";", 1)[0].strip().lower(),
            body=response.content,
        )

    async def aclose(self) -> None:
        await self._client.aclose()


def _context(token: str) -> CapabilityExecutionContext:
    return CapabilityExecutionContext(
        request_id="employee-egress-candidate",
        correlation_id="employee-egress-candidate",
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


def _outcome(decision_kind: AnswerGenerationDecisionKind, failure_kind: object) -> str:
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
async def test_gate024_one_employee_result_and_thirty_bounded_answers() -> None:
    manifest_sha256 = _required("EMPLOYEE_EGRESS_MANIFEST_SHA256")
    repository_root = Path(__file__).resolve().parents[5]
    evidence_directory = Path(__file__).parent / "evidence"
    manifest_path = evidence_directory / f"{RUN_ID}.manifest.json"
    authorization_path = evidence_directory / f"{RUN_ID}.authorization.json"
    if sha256_file(manifest_path) != manifest_sha256:
        raise RuntimeError("employee.egress_candidate_authorization_binding_invalid")
    validate_manifest(load_strict_json(manifest_path), repository_root=repository_root)
    validate_authorization(
        load_strict_json(authorization_path),
        manifest_sha256=manifest_sha256,
    )
    identifier = _required("EMPLOYEE_EGRESS_LIVE_TEST_IDENTIFIER")
    token = _required("EMPLOYEE_EGRESS_LIVE_USER_JWT")
    employee_base_url = _required("EMPLOYEE_EGRESS_LIVE_BASE_URL")
    if employee_base_url != "http://127.0.0.1:9210":
        raise RuntimeError("employee.egress_candidate_endpoint_invalid")
    consumed_path = Path(_required("EMPLOYEE_EGRESS_CONSUMED_OUTPUT"))
    evidence_path = Path(_required("EMPLOYEE_EGRESS_EVIDENCE_OUTPUT"))
    journal_path = Path(_required("EMPLOYEE_EGRESS_ATTEMPT_JOURNAL_OUTPUT"))
    started = datetime.now(timezone.utc)
    snapshot = build_employee_egress_snapshot()
    definition = employee_detail_definition()
    settings = dict(snapshot.actions)[definition.descriptor.capability_id]
    employee_client = httpx.AsyncClient(
        base_url=employee_base_url,
        follow_redirects=False,
        trust_env=False,
        timeout=httpx.Timeout(8.0),
        limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
    )
    employee_transport = LiveEmployeeTransport(employee_client)
    handler = BoundBusinessActionHandler(
        definition=definition,
        settings=settings,
        client=UserJwtBusinessHttpClient(transport=employee_transport, max_response_bytes=1_048_576),
        user_projector=BusinessUserResultProjector(),
        egress_projector=BusinessEgressProjector(),
        egress_policy=GlobalBusinessEgressPolicy.from_settings(snapshot.global_settings),
        config_snapshot_id=snapshot.snapshot_id,
        max_user_result_bytes=262_144,
    )
    outcomes: list[dict[str, object]] = []
    actual_answer_calls = 0
    valid_answers = 0
    budgeted_transport: BudgetedEmployeeAnswerTransport | None = None
    model_components: LocalModelComponents | None = None
    model_client: httpx.AsyncClient | None = None
    status = "failed"
    try:
        result = await handler.handle(
            definition.argument_validator.validate({"employee_identifier": identifier}),
            _context(token),
        )
        if (
            result.status is not CapabilityStatus.SUCCESS
            or result.domain_result is None
            or result.egress.disposition is not EgressDisposition.ALLOWED
            or result.egress.safe_payload is None
        ):
            raise AssertionError("employee.egress_candidate_projection_failed")
        safe_payload = result.egress.safe_payload
        model_settings = ModelSettings.from_env(
            {
                "AGENT_MODEL_PROVIDER": "deepseek",
                "AGENT_MODEL_MAX_CONCURRENCY": "1",
                "AGENT_MODEL_ANSWER_TIMEOUT_MS": "15000",
                "LLM_API_KEY": _required("LLM_API_KEY"),
            }
        )
        if model_settings.provider is not ModelProvider.DEEPSEEK:
            raise AssertionError("employee.egress_candidate_provider_invalid")
        model_client = build_deepseek_http_client(model_settings)
        budgeted_transport = BudgetedEmployeeAnswerTransport(
            delegate=DeepSeekChatTransport(settings=model_settings, client=model_client),
            consumed_marker_path=consumed_path,
            journal=EmployeeEgressAttemptJournal(journal_path),
            manifest_sha256=manifest_sha256,
            forbidden_literals=_forbidden_literals(result.domain_result, identifier),
        )
        model_components = LocalModelCompositionRoot.build(
            settings=ModelSettings(),
            transport=budgeted_transport,
            grounding_policies={"employee.detail": BusinessAnswerGroundingPolicy()},
        )
        for ordinal in range(1, MAXIMUM_PAID_ANSWER_CALLS + 1):
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
            actual_answer_calls = budgeted_transport.calls
            if decision.kind is AnswerGenerationDecisionKind.ANSWER:
                valid_answers += 1
            outcomes.append(
                {
                    "attemptOrdinal": ordinal,
                    "status": _outcome(
                        decision.kind,
                        None if decision.failure is None else decision.failure.kind,
                    ),
                }
            )
            budgeted_transport.record_terminal(str(outcomes[-1]["status"]))
        status = "passed" if valid_answers >= MINIMUM_VALID_ANSWER_CALLS else "failed"
    finally:
        if model_components is not None:
            await model_components.aclose()
        if model_client is not None:
            await model_client.aclose()
        await employee_transport.aclose()
        journal_records = validate_attempt_journal(journal_path)
        evidence = {
            "schemaVersion": 1,
            "status": status,
            "workPackageId": WORK_PACKAGE_ID,
            "gateId": GATE_ID,
            "runId": RUN_ID,
            "manifestSha256": manifest_sha256,
            "authorizationReference": AUTHORIZATION_REFERENCE,
            "recordedAt": started.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "modelBinding": dict(MODEL_TASK_BINDING),
            "fieldBoundary": {"modelVisibleFieldIds": list(MODEL_VISIBLE_FIELD_IDS)},
            "businessSnapshot": {
                "policyVersion": "business-egress-v1",
                "configSnapshotId": snapshot.snapshot_id,
            },
            "authorizationEvidenceRefs": list(AUTHORIZATION_EVIDENCE_REFS),
            "attemptJournal": {
                "recordCount": len(journal_records),
                "sha256": sha256_file(journal_path),
            },
            "counts": {
                "employeeDetailRequests": employee_transport.calls,
                "otherEmployeeEndpoints": 0,
                "plannedAnswerCalls": MAXIMUM_PAID_ANSWER_CALLS,
                "maximumPaidAnswerCalls": MAXIMUM_PAID_ANSWER_CALLS,
                "actualAnswerCalls": actual_answer_calls,
                "terminalAnswerRecords": len(outcomes),
                "validAnswers": valid_answers,
                "retryCount": 0,
                "resumeCount": 0,
            },
            "safety": {
                "forbiddenPayloadFieldCount": 0
                if budgeted_transport is None
                else budgeted_transport.forbidden_payload_field_count,
                "forbiddenLiteralCount": 0
                if budgeted_transport is None
                else budgeted_transport.forbidden_literal_count,
                "logLeakCount": 0,
                "jwtPersisted": False,
                "identifierPersisted": False,
                "employeeDataPersisted": False,
                "rawModelResponsePersisted": False,
            },
            "outcomes": outcomes,
        }
        validate_live_evidence(evidence)
        write_exclusive_json(evidence_path, evidence)
    if status != "passed":
        raise AssertionError("employee.egress_candidate_threshold_not_met")
