from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

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
from agent_runtime.model.contracts import (
    ModelTaskId,
    StructuredModelRequest,
    StructuredModelResponse,
    StructuredModelTransport,
    StructuredOutputMode,
    StructuredToolMode,
)
from agent_runtime.model.deepseek.transport import (
    DeepSeekChatTransport,
    build_deepseek_http_client,
)
from agent_runtime.model.settings import ModelProvider, ModelSettings
from tests.helpers import ManualCancellationSignal
from tests.integration.adapters.employee.egress_candidate_v2 import (
    build_employee_egress_snapshot,
    count_forbidden_log_literals,
    safe_question,
)
from tests.integration.adapters.employee.egress_candidate_v4 import (
    AUTHORIZATION_REFERENCE,
    MAXIMUM_PAID_ANSWER_CALLS,
    MINIMUM_VALID_ANSWER_CALLS,
    MODEL_VISIBLE_FIELD_IDS,
    RUN_ID,
    SCHEMA_VERSION,
    LifecycleJournal,
    load_strict_json,
    sha256_file,
    validate_authorization,
    validate_manifest,
    write_consumed_marker,
)
from tests.model_helpers import call_with_model_context


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_EMPLOYEE_EGRESS_CANDIDATE_V4") != "1",
    reason="requires explicit one-shot GATE-024 candidate-04 opt-in",
)


def _required(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"employee.egress_candidate_v4_env_missing:{name}")
    return value.strip()


def _context(token: str) -> CapabilityExecutionContext:
    return CapabilityExecutionContext(
        request_id="employee-egress-candidate-v4",
        correlation_id="employee-egress-candidate-v4",
        original_question=safe_question(),
        subject_id="employee-egress-authorized-reader",
        subject_type=SubjectType.USER,
        user_token=OpaqueUserToken.from_raw(token),
        deadline_monotonic=asyncio.get_running_loop().time() + 20.0,
        cancellation=ManualCancellationSignal(),
    )


def _count_keys(value: object, forbidden: frozenset[str]) -> int:
    if isinstance(value, dict):
        return sum(key in forbidden for key in value) + sum(
            _count_keys(item, forbidden) for item in value.values()
        )
    if isinstance(value, list):
        return sum(_count_keys(item, forbidden) for item in value)
    return 0


def _domain_literals(domain_result: Mapping[str, object], identifier: str) -> tuple[str, ...]:
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


class _LiveEmployeeTransport:
    def __init__(self, client: httpx.AsyncClient, journal: LifecycleJournal) -> None:
        self._client = client
        self._journal = journal
        self.calls = 0

    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        if self.calls != 0:
            raise RuntimeError("employee.egress_candidate_v4_employee_budget_exhausted")
        self.calls = 1
        self._journal.started("employee_detail")
        try:
            response = await self._client.get(
                request.request.relative_path,
                headers={"Authorization": request.authorization, "Accept-Encoding": "identity"},
            )
        except BaseException:
            self._journal.finished(
                "employee_detail", terminal="failed", reason="employee_request_failed"
            )
            raise
        self._journal.finished("employee_detail", terminal="succeeded")
        content_type = response.headers.get("Content-Type")
        return FakeDomainHttpResponse(
            status_code=response.status_code,
            content_type=(
                None
                if content_type is None
                else content_type.split(";", 1)[0].strip().lower()
            ),
            body=response.content,
        )

    async def aclose(self) -> None:
        await self._client.aclose()


class _BudgetedAnswerTransport:
    def __init__(
        self,
        *,
        delegate: StructuredModelTransport,
        journal: LifecycleJournal,
        consumed_path: Path,
        manifest_sha256: str,
        forbidden_literals: Sequence[str],
    ) -> None:
        self._delegate = delegate
        self._journal = journal
        self._consumed_path = consumed_path
        self._manifest_sha256 = manifest_sha256
        self._forbidden_literals = tuple(value for value in forbidden_literals if value)
        self.calls = 0
        self.terminals = 0
        self.valid_answers = 0
        self.forbidden_payload_field_count = 0
        self.forbidden_literal_count = 0

    async def complete(
        self, request: StructuredModelRequest, *, call_deadline: float
    ) -> StructuredModelResponse:
        if self.calls >= MAXIMUM_PAID_ANSWER_CALLS:
            raise RuntimeError("employee.egress_candidate_v4_model_budget_exhausted")
        self._validate_request(request)
        ordinal = self.calls + 1
        self._journal.started("model_answer", ordinal=ordinal)
        self.calls = ordinal
        if ordinal == 1:
            write_consumed_marker(
                self._consumed_path, manifest_sha256=self._manifest_sha256
            )
        return await self._delegate.complete(request, call_deadline=call_deadline)

    def terminal(self, state: str) -> None:
        ordinal = self.terminals + 1
        if ordinal > self.calls or state not in {
            "answer",
            "invalid_output",
            "input_denied",
            "timeout",
            "provider_failure",
        }:
            raise RuntimeError("employee.egress_candidate_v4_model_terminal_invalid")
        self._journal.finished("model_answer", terminal=state, ordinal=ordinal)
        self.terminals = ordinal
        if state == "answer":
            self.valid_answers += 1

    def _validate_request(self, request: StructuredModelRequest) -> None:
        if (
            request.task_id is not ModelTaskId.ANSWER_GENERATION
            or request.task_version != "answer-generation-v2"
            or request.tools
            or request.tool_mode is not StructuredToolMode.NONE
            or request.output_mode is not StructuredOutputMode.JSON_OBJECT
        ):
            raise RuntimeError("employee.egress_candidate_v4_request_invalid")
        payload = json.loads(request.user_payload_json)
        if type(payload) is not dict or set(payload) != {"question", "safe_payload"}:
            raise RuntimeError("employee.egress_candidate_v4_request_invalid")
        if payload["question"] != safe_question():
            raise RuntimeError("employee.egress_candidate_v4_question_invalid")
        safe_payload = payload["safe_payload"]
        if type(safe_payload) is not dict:
            raise RuntimeError("employee.egress_candidate_v4_request_invalid")
        facts = safe_payload.get("facts")
        if type(facts) is not list or len(facts) != len(MODEL_VISIBLE_FIELD_IDS):
            raise RuntimeError("employee.egress_candidate_v4_field_boundary_invalid")
        field_ids: list[str] = []
        for fact in facts:
            if type(fact) is not dict or type(fact.get("source")) is not dict:
                raise RuntimeError("employee.egress_candidate_v4_field_boundary_invalid")
            source = cast(dict[str, object], fact["source"])
            if type(source.get("field_id")) is not str:
                raise RuntimeError("employee.egress_candidate_v4_field_boundary_invalid")
            field_ids.append(cast(str, source["field_id"]))
        if tuple(field_ids) != MODEL_VISIBLE_FIELD_IDS:
            raise RuntimeError("employee.egress_candidate_v4_field_boundary_invalid")
        forbidden = frozenset(
            {
                "employee_id_masked",
                "member_no_masked",
                "chinese_name",
                "public_email",
                "financial_account",
                "credential",
                "jwt",
                "user_token",
                "idCardNo",
                "memberNo",
                "chineseName",
                "publicEmail",
            }
        )
        self.forbidden_payload_field_count += _count_keys(payload, forbidden)
        self.forbidden_literal_count += sum(
            value in request.user_payload_json for value in self._forbidden_literals
        )
        if self.forbidden_payload_field_count or self.forbidden_literal_count:
            raise RuntimeError("employee.egress_candidate_v4_payload_forbidden")


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


def _write_staging(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


@pytest.mark.asyncio
async def test_gate024_candidate04_one_employee_result_and_thirty_bounded_answers(
    capfd: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    repository_root = Path(_required("EMPLOYEE_EGRESS_V4_REPOSITORY"))
    evidence_directory = repository_root / "agent-runtime/tests/integration/adapters/employee/evidence"
    manifest_sha256 = _required("EMPLOYEE_EGRESS_V4_MANIFEST_SHA256")
    manifest_path = evidence_directory / f"{RUN_ID}.manifest.json"
    authorization_path = evidence_directory / f"{RUN_ID}.authorization.json"
    if sha256_file(manifest_path) != manifest_sha256:
        raise RuntimeError("employee.egress_candidate_v4_manifest_binding_invalid")
    validate_manifest(load_strict_json(manifest_path), repository_root=repository_root)
    validate_authorization(
        load_strict_json(authorization_path), manifest_sha256=manifest_sha256
    )

    identifier = _required("EMPLOYEE_EGRESS_V4_IDENTIFIER")
    token = _required("EMPLOYEE_EGRESS_V4_ADMIN_JWT")
    base_url = _required("EMPLOYEE_EGRESS_V4_BASE_URL")
    if not base_url.startswith("http://127.0.0.1:"):
        raise RuntimeError("employee.egress_candidate_v4_endpoint_invalid")
    lifecycle_path = Path(_required("EMPLOYEE_EGRESS_V4_LIFECYCLE"))
    consumed_path = Path(_required("EMPLOYEE_EGRESS_V4_CONSUMED"))
    staging_path = Path(_required("EMPLOYEE_EGRESS_V4_STAGING"))
    if consumed_path.exists() or staging_path.exists():
        raise RuntimeError("employee.egress_candidate_v4_output_exists")

    journal = LifecycleJournal(lifecycle_path, manifest_sha256=manifest_sha256, create=False)
    snapshot = build_employee_egress_snapshot()
    definition = employee_detail_definition()
    settings = dict(snapshot.actions)[definition.descriptor.capability_id]
    employee_transport: _LiveEmployeeTransport | None = None
    answer_transport: _BudgetedAnswerTransport | None = None
    model_components: LocalModelComponents | None = None
    model_client: httpx.AsyncClient | None = None
    failure_phase = "none"
    failure_reason = "none"
    current_phase = "employee_detail"
    log_forbidden_literals: tuple[str, ...] = (identifier, token)
    try:
        employee_transport = _LiveEmployeeTransport(
            httpx.AsyncClient(
                base_url=base_url,
                follow_redirects=False,
                trust_env=False,
                timeout=httpx.Timeout(8.0),
                limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
            ),
            journal,
        )
        handler = BoundBusinessActionHandler(
            definition=definition,
            settings=settings,
            client=UserJwtBusinessHttpClient(
                transport=employee_transport, max_response_bytes=1_048_576
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
        if result.status is not CapabilityStatus.SUCCESS or result.domain_result is None:
            failure_phase, failure_reason = "employee_detail", "employee_result_invalid"
        elif (
            result.egress.disposition is not EgressDisposition.ALLOWED
            or result.egress.safe_payload is None
        ):
            failure_phase, failure_reason = "model_setup", "egress_projection_invalid"
        else:
            safe_payload = result.egress.safe_payload
            assert safe_payload is not None
            current_phase = "model_setup"
            api_key = _required("LLM_API_KEY")
            log_forbidden_literals = tuple(
                sorted(
                    set(_domain_literals(result.domain_result, identifier))
                    | {token, api_key}
                )
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
                raise RuntimeError("employee.egress_candidate_v4_provider_invalid")
            model_client = build_deepseek_http_client(model_settings)
            answer_transport = _BudgetedAnswerTransport(
                delegate=DeepSeekChatTransport(settings=model_settings, client=model_client),
                journal=journal,
                consumed_path=consumed_path,
                manifest_sha256=manifest_sha256,
                forbidden_literals=_domain_literals(result.domain_result, identifier),
            )
            model_components = LocalModelCompositionRoot.build(
                settings=ModelSettings(),
                transport=answer_transport,
                grounding_policies={"employee.detail": BusinessAnswerGroundingPolicy()},
            )
            current_phase = "model_answer"
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
                answer_transport.terminal(
                    _outcome(
                        decision.kind,
                        None if decision.failure is None else decision.failure.kind,
                    )
                )
            if answer_transport.valid_answers < MINIMUM_VALID_ANSWER_CALLS:
                failure_phase, failure_reason = "threshold", "threshold_not_met"
    except BaseException:
        if answer_transport is not None and answer_transport.terminals < answer_transport.calls:
            answer_transport.terminal("provider_failure")
        if failure_reason == "none":
            failure_phase = current_phase
            failure_reason = {
                "employee_detail": "employee_request_failed",
                "model_setup": "model_setup_failed",
                "model_answer": "model_call_failed",
            }[current_phase]
    finally:
        for closeable in (model_components, model_client, employee_transport):
            if closeable is not None:
                try:
                    await closeable.aclose()
                except BaseException:
                    if failure_reason == "none":
                        failure_phase, failure_reason = "model_setup", "model_setup_failed"

    captured = capfd.readouterr()
    log_text = captured.out + captured.err + "\n".join(
        record.getMessage() for record in caplog.records
    )
    log_leak_count = count_forbidden_log_literals(log_text, log_forbidden_literals)
    if log_leak_count:
        failure_phase, failure_reason = "host_validation", "log_leak_detected"
    _write_staging(
        staging_path,
        {
            "schemaVersion": SCHEMA_VERSION,
            "runId": RUN_ID,
            "manifestSha256": manifest_sha256,
            "authorizationReference": AUTHORIZATION_REFERENCE,
            "failure": {"phase": failure_phase, "reason": failure_reason},
            "counts": {
                "employeeDetailStarted": 0 if employee_transport is None else employee_transport.calls,
                "employeeDetailTerminal": 0 if employee_transport is None else employee_transport.calls,
                "modelAnswerStarted": 0 if answer_transport is None else answer_transport.calls,
                "modelAnswerTerminal": 0 if answer_transport is None else answer_transport.terminals,
                "validAnswers": 0 if answer_transport is None else answer_transport.valid_answers,
            },
            "safety": {
                "retryCount": 0,
                "resumeCount": 0,
                "otherEndpointCalls": 0,
                "forbiddenPayloadFieldCount": (
                    0 if answer_transport is None else answer_transport.forbidden_payload_field_count
                ),
                "forbiddenLiteralCount": (
                    0 if answer_transport is None else answer_transport.forbidden_literal_count
                ),
                "logLeakCount": log_leak_count,
            },
        },
    )
    if failure_reason != "none":
        raise AssertionError("employee.egress_candidate_v4_failed")
