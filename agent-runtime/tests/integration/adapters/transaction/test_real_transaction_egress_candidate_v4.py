from __future__ import annotations

import asyncio
import os
from pathlib import Path

import httpx
import pytest

from agent_runtime.adapters.transaction.definition import transaction_search_definition
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
from agent_runtime.model.deepseek.transport import (
    DeepSeekChatTransport,
    build_deepseek_http_client,
)
from agent_runtime.model.settings import ModelProvider, ModelSettings
from tests.helpers import ManualCancellationSignal
from tests.integration.adapters.transaction.egress_candidate_v4 import (
    MAXIMUM_PAID_ANSWER_CALLS,
    MINIMUM_VALID_ANSWER_CALLS,
    RUN_ID,
    SAFE_QUESTION,
    BudgetedTransactionAnswerTransport,
    JournaledTransactionSearchTransport,
    ModelTerminalStatus,
    TransactionEgressFailurePhase,
    TransactionEgressFailureReason,
    TransactionEgressLifecycleJournal,
    TransactionEgressSafetySnapshot,
    build_transaction_egress_snapshot,
    build_live_forbidden_literals,
    consumed_path_for,
    count_forbidden_log_literals,
    finalize_result,
    load_strict_json,
    sha256_file,
    validate_authorization,
    validate_manifest,
)
from tests.model_helpers import call_with_model_context


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_TRANSACTION_EGRESS_CANDIDATE_04") != "1",
    reason="requires exact GATE-026 candidate-04 opt-in",
)


def _required(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError("transaction.egress_candidate_environment_missing")
    return value


def _context(token: str) -> CapabilityExecutionContext:
    return CapabilityExecutionContext(
        request_id="transaction-egress-candidate-04",
        correlation_id="transaction-egress-candidate-04",
        original_question=SAFE_QUESTION,
        subject_id="transaction-egress-live-principal",
        subject_type=SubjectType.USER,
        user_token=OpaqueUserToken.from_raw(token),
        deadline_monotonic=asyncio.get_running_loop().time() + 20.0,
        cancellation=ManualCancellationSignal(),
    )


class LiveTransactionSearchServer:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self.calls = 0

    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        if self.calls:
            raise RuntimeError("transaction.egress_candidate_search_budget_exhausted")
        self.calls = 1
        response = await self._client.post(
            request.request.relative_path,
            headers={
                "Authorization": request.authorization,
                "Content-Type": "application/json",
                "Accept-Encoding": "identity",
            },
            content=request.request.json_body.content if request.request.json_body else None,
        )
        content_type = response.headers.get("Content-Type")
        return FakeDomainHttpResponse(
            status_code=response.status_code,
            content_type=None if content_type is None else content_type.split(";", 1)[0].strip().lower(),
            body=response.content,
        )

    async def aclose(self) -> None:
        await self._client.aclose()


def _terminal_status(
    kind: AnswerGenerationDecisionKind,
    failure: ModelNodeFailureKind | None,
) -> ModelTerminalStatus:
    if kind is AnswerGenerationDecisionKind.ANSWER:
        return "answer"
    if failure is ModelNodeFailureKind.INPUT_DENIED:
        return "input_denied"
    if failure is ModelNodeFailureKind.PROVIDER_TIMEOUT:
        return "provider_timeout"
    if failure is ModelNodeFailureKind.PROVIDER_FAILURE:
        return "provider_failure"
    return "invalid_output"


@pytest.mark.asyncio
async def test_gate026_candidate04_one_search_and_thirty_bounded_answers(
    capfd: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    repository_root = Path(__file__).resolve().parents[5]
    evidence_directory = Path(__file__).resolve().parent / "evidence"
    manifest_sha256 = _required("TRANSACTION_EGRESS_MANIFEST_SHA256")
    manifest_path = evidence_directory / f"{RUN_ID}.manifest.json"
    authorization_path = evidence_directory / f"{RUN_ID}.authorization.json"
    if sha256_file(manifest_path) != manifest_sha256:
        raise RuntimeError("transaction.egress_candidate_authorization_binding_invalid")
    validate_manifest(load_strict_json(manifest_path), repository_root=repository_root)
    validate_authorization(load_strict_json(authorization_path), manifest_sha256=manifest_sha256)

    transaction_type = _required("TRANSACTION_EGRESS_LIVE_TEST_TYPE")
    user_jwt = _required("TRANSACTION_EGRESS_LIVE_USER_JWT")
    base_url = _required("TRANSACTION_EGRESS_LIVE_BASE_URL")
    lifecycle_path = Path(_required("TRANSACTION_EGRESS_LIFECYCLE_OUTPUT"))
    result_path = Path(_required("TRANSACTION_EGRESS_RESULT_OUTPUT"))
    if (
        lifecycle_path != evidence_directory / f"{RUN_ID}.lifecycle.jsonl"
        or consumed_path_for(evidence_directory).exists()
        or result_path != evidence_directory / f"{RUN_ID}.result.json"
    ):
        raise RuntimeError("transaction.egress_candidate_output_binding_invalid")

    snapshot = build_transaction_egress_snapshot()
    definition = transaction_search_definition()
    journal = TransactionEgressLifecycleJournal(
        lifecycle_path,
        manifest_sha256=manifest_sha256,
    )
    failure_phase: TransactionEgressFailurePhase | None = None
    failure_reason: TransactionEgressFailureReason | None = None
    search_transport: JournaledTransactionSearchTransport | None = None
    model_transport: BudgetedTransactionAnswerTransport | None = None
    model_components: LocalModelComponents | None = None
    model_client: httpx.AsyncClient | None = None
    valid_answers = 0
    forbidden_literals: tuple[str, ...] = (user_jwt,)
    current_phase = TransactionEgressFailurePhase.TRANSACTION_SEARCH

    try:
        domain_client = httpx.AsyncClient(
            base_url=base_url,
            follow_redirects=False,
            trust_env=False,
            timeout=httpx.Timeout(8.0),
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        )
        search_transport = JournaledTransactionSearchTransport(
            delegate=LiveTransactionSearchServer(domain_client),
            journal=journal,
            expected_transaction_type=transaction_type,
        )
        handler = BoundBusinessActionHandler(
            definition=definition,
            settings=dict(snapshot.actions)[definition.descriptor.capability_id],
            client=UserJwtBusinessHttpClient(
                transport=search_transport,
                max_response_bytes=1_048_576,
            ),
            user_projector=BusinessUserResultProjector(),
            egress_projector=BusinessEgressProjector(),
            egress_policy=GlobalBusinessEgressPolicy.from_settings(snapshot.global_settings),
            config_snapshot_id=snapshot.snapshot_id,
            max_user_result_bytes=262_144,
        )
        result = await handler.handle(
            definition.argument_validator.validate({"trans_type": transaction_type, "size": 1}),
            _context(user_jwt),
        )
        current_phase = TransactionEgressFailurePhase.TRANSACTION_RESULT
        if result.status is not CapabilityStatus.SUCCESS or result.domain_result is None:
            failure_phase = current_phase
            failure_reason = TransactionEgressFailureReason.TRANSACTION_RESULT_INVALID
        elif result.egress.disposition is not EgressDisposition.ALLOWED or result.egress.safe_payload is None:
            failure_phase = TransactionEgressFailurePhase.EGRESS_PROJECTION
            failure_reason = TransactionEgressFailureReason.EGRESS_PROJECTION_INVALID
        else:
            safe_payload = result.egress.safe_payload
            current_phase = TransactionEgressFailurePhase.MODEL_SETUP
            api_key = _required("LLM_API_KEY")
            forbidden_literals = build_live_forbidden_literals(
                user_jwt=user_jwt,
                api_key=api_key,
                domain_result=result.domain_result,
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
                raise RuntimeError("transaction.egress_candidate_provider_invalid")
            model_client = build_deepseek_http_client(model_settings)
            model_transport = BudgetedTransactionAnswerTransport(
                delegate=DeepSeekChatTransport(settings=model_settings, client=model_client),
                journal=journal,
                forbidden_literals=forbidden_literals,
            )
            model_components = LocalModelCompositionRoot.build(
                settings=ModelSettings(),
                transport=model_transport,
                grounding_policies={"transaction.search": BusinessAnswerGroundingPolicy()},
            )
            current_phase = TransactionEgressFailurePhase.MODEL_CALL
            for _ in range(MAXIMUM_PAID_ANSWER_CALLS):
                decision = await call_with_model_context(
                    lambda: model_components.answer_generator(
                        AnswerGenerationInput(
                            question=SAFE_QUESTION,
                            capability_id="transaction.search",
                            safe_payload=safe_payload,
                        )
                    ),
                    question=SAFE_QUESTION,
                )
                model_transport.record_terminal(
                    _terminal_status(
                        decision.kind,
                        None if decision.failure is None else decision.failure.kind,
                    )
                )
                valid_answers += int(decision.kind is AnswerGenerationDecisionKind.ANSWER)
            if valid_answers < MINIMUM_VALID_ANSWER_CALLS:
                failure_phase = TransactionEgressFailurePhase.THRESHOLD
                failure_reason = TransactionEgressFailureReason.THRESHOLD_NOT_MET
    except BaseException:
        if model_transport is not None and model_transport.terminal_calls < model_transport.calls:
            model_transport.record_terminal("provider_failure")
        if failure_phase is None:
            failure_phase = current_phase
            failure_reason = {
                TransactionEgressFailurePhase.TRANSACTION_SEARCH: TransactionEgressFailureReason.TRANSACTION_SEARCH_FAILED,
                TransactionEgressFailurePhase.TRANSACTION_RESULT: TransactionEgressFailureReason.TRANSACTION_RESULT_INVALID,
                TransactionEgressFailurePhase.EGRESS_PROJECTION: TransactionEgressFailureReason.EGRESS_PROJECTION_INVALID,
                TransactionEgressFailurePhase.MODEL_SETUP: TransactionEgressFailureReason.MODEL_REQUEST_INVALID,
                TransactionEgressFailurePhase.MODEL_CALL: TransactionEgressFailureReason.MODEL_CALL_FAILED,
                TransactionEgressFailurePhase.THRESHOLD: TransactionEgressFailureReason.THRESHOLD_NOT_MET,
                TransactionEgressFailurePhase.CLEANUP: TransactionEgressFailureReason.CLEANUP_FAILED,
                TransactionEgressFailurePhase.INTERNAL: TransactionEgressFailureReason.INTERNAL_FAILURE,
            }[current_phase]
    finally:
        cleanup_failed = False
        for component in (model_components, model_client, search_transport):
            if component is not None:
                try:
                    await component.aclose()
                except BaseException:
                    cleanup_failed = True
        if cleanup_failed and failure_phase is None:
            failure_phase = TransactionEgressFailurePhase.CLEANUP
            failure_reason = TransactionEgressFailureReason.CLEANUP_FAILED

    captured = capfd.readouterr()
    captured_logs = "\n".join(record.getMessage() for record in caplog.records)
    log_leak_count = count_forbidden_log_literals(
        captured.out + captured.err + captured_logs,
        forbidden_literals,
    )
    if log_leak_count and failure_phase is None:
        failure_phase = TransactionEgressFailurePhase.CLEANUP
        failure_reason = TransactionEgressFailureReason.LOG_LEAK_DETECTED
    if failure_phase is None:
        journal.record_run_terminal(status="passed", failure_phase=None, failure_reason=None)
    else:
        assert failure_reason is not None
        journal.record_run_terminal(
            status="failed_consumed" if journal.consumed_marker_path.exists() else "failed_unconsumed",
            failure_phase=failure_phase,
            failure_reason=failure_reason,
        )
    evidence = finalize_result(
        journal=journal,
        result_path=result_path,
        config_snapshot_id=snapshot.snapshot_id,
        safety=TransactionEgressSafetySnapshot(
            forbidden_payload_field_count=0 if model_transport is None else model_transport.forbidden_payload_field_count,
            forbidden_literal_count=0 if model_transport is None else model_transport.forbidden_literal_count,
            log_leak_count=log_leak_count,
        ),
    )
    if evidence["status"] != "passed":
        raise AssertionError("transaction.egress_candidate_failed")
