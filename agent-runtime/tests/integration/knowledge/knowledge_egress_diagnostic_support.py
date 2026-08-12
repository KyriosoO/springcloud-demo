from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

from agent_runtime.capability_api.contracts import CapabilityStatus, OpaqueUserToken
from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.graph.state import AgentSemanticOutcome
from agent_runtime.knowledge.contracts import (
    EvidenceStageKind,
    KnowledgeEvidenceContext,
    KnowledgeEvidenceInput,
    KnowledgeRetrievalContext,
    KnowledgeRetrievalPlan,
    RetrievalPath,
    RetrievalPlanItem,
    RetrievalStageResult,
)
from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeEvidenceBundle,
    KnowledgeEvidenceLimits,
    KnowledgeSummaryOutput,
    SummaryValidationResult,
)
from agent_runtime.knowledge.evidence.summary_validation import (
    ExtractiveSummaryValidator,
    InvalidSummary,
    SummaryValidationFailureReason,
)
from agent_runtime.knowledge.retrieval.contracts import RankedKnowledgeBatch
from agent_runtime.model.contracts import (
    ModelProviderFailureKind,
    ModelTransportError,
    StructuredModelRequest,
    StructuredModelResponse,
    StructuredModelTransport,
)
from agent_runtime.model.input_guard import QuestionEgressGuard
from tests.helpers import ManualCancellationSignal, scope
from tests.integration.knowledge.egress_diagnostic_journal import (
    AUTHORIZED_SUMMARY_CALLS,
    KnowledgeEgressDiagnosticJournal,
)


FORBIDDEN_PAYLOAD_KEYS = {
    "evidence_id",
    "document_id",
    "chunk_id",
    "source_url",
    "policy_ref",
    "policy_version",
    "index_snapshot_id",
    "read_policy_version",
    "subject",
    "jwt",
    "user_token",
}
T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class DiagnosticCase:
    case_id: str
    question: str
    domains: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PreparedDiagnosticCase:
    case: DiagnosticCase
    retrieval: RetrievalStageResult[RankedKnowledgeBatch]
    evidence_input: KnowledgeEvidenceInput[RankedKnowledgeBatch]


CASES = (
    DiagnosticCase("tax-policy", "增值税小规模纳税人的现行税收政策有哪些", ("tax.policy",)),
    DiagnosticCase("tax-law", "个人所得税法关于居民个人有哪些规定", ("tax.law",)),
    DiagnosticCase("tax-mixed", "税收征收管理法律与现行税务政策如何衔接", ("tax.policy", "tax.law")),
)


def required_environment(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"knowledge.egress_diagnostic_env_missing:{name}")
    return value


def count_forbidden_keys(value: object) -> int:
    if isinstance(value, dict):
        return sum(key in FORBIDDEN_PAYLOAD_KEYS for key in value) + sum(
            count_forbidden_keys(item) for item in value.values()
        )
    if isinstance(value, list):
        return sum(count_forbidden_keys(item) for item in value)
    return 0


def retrieval_plan(case: DiagnosticCase) -> KnowledgeRetrievalPlan:
    items: list[RetrievalPlanItem] = []
    for domain in case.domains:
        for path in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR):
            items.append(
                RetrievalPlanItem(
                    logical_domain_id=domain,
                    path=path,
                    query_text=case.question,
                    candidate_limit=5,
                    ordinal=len(items) + 1,
                )
            )
    return KnowledgeRetrievalPlan(
        items=tuple(items),
        selected_domain_ids=case.domains,
        config_version="knowledge-flow-config-v1",
    )


def retrieval_context(token: str, deadline: float) -> KnowledgeRetrievalContext:
    return KnowledgeRetrievalContext(
        request_id="req-diagnostic-retrieval",
        correlation_id="corr-diagnostic-retrieval",
        subject="diagnostic-user",
        user_token=OpaqueUserToken.from_raw(token),
        deadline_monotonic=deadline,
        cancellation=ManualCancellationSignal(),
    )


def evidence_context(deadline: float, call_ordinal: int) -> KnowledgeEvidenceContext:
    return KnowledgeEvidenceContext(
        request_id=f"req-gate041-{call_ordinal}",
        correlation_id=f"corr-gate041-{call_ordinal}",
        subject="diagnostic-user",
        deadline_monotonic=deadline,
        cancellation=ManualCancellationSignal(),
    )


def evidence_input(
    case: DiagnosticCase,
    retrieval: RetrievalStageResult[RankedKnowledgeBatch],
) -> KnowledgeEvidenceInput[RankedKnowledgeBatch]:
    if retrieval.batch is None or retrieval.coverage is None:
        raise RuntimeError("knowledge.egress_diagnostic_retrieval_invalid")
    guard = QuestionEgressGuard().evaluate(case.question)
    if guard.minimized_question != case.question:
        raise RuntimeError("knowledge.egress_diagnostic_question_not_fixed")
    return KnowledgeEvidenceInput(
        original_question=case.question,
        selected_query=case.question,
        selected_domain_ids=case.domains,
        coverage=retrieval.coverage,
        question_policy_version=guard.policy_version,
        question_egress_denied=False,
        batch=retrieval.batch,
    )


async def with_model_context(
    operation: Callable[[], Awaitable[T]],
    *,
    question: str,
    deadline: float,
    call_ordinal: int,
) -> T:
    from agent_runtime.model.context import ModelContextBindingRuntimeInvoker

    result: list[T] = []

    class Delegate:
        async def ainvoke(self, *, question: str, scope: RequestExecutionScope) -> AgentSemanticOutcome:
            del question, scope
            result.append(await operation())
            return AgentSemanticOutcome(
                status=CapabilityStatus.SUCCESS,
                capability_id=None,
                answer_text="diagnostic",
                user_result=None,
                failure=None,
            )

    execution_scope = scope(question, deadline_monotonic=deadline)
    execution_scope = replace(
        execution_scope,
        context=replace(
            execution_scope.context,
            request_id=f"req-gate041-{call_ordinal}",
            correlation_id=f"corr-gate041-{call_ordinal}",
        ),
    )
    await ModelContextBindingRuntimeInvoker(Delegate()).ainvoke(question=question, scope=execution_scope)
    return result[0]


class RecordingExtractiveSummaryValidator(ExtractiveSummaryValidator):
    def __init__(self) -> None:
        self._last_reason: SummaryValidationFailureReason | None = None

    def validate(
        self,
        *,
        output: KnowledgeSummaryOutput,
        bundle: KnowledgeEvidenceBundle,
        limits: KnowledgeEvidenceLimits,
    ) -> SummaryValidationResult:
        if self._last_reason is not None:
            raise RuntimeError("knowledge.egress_diagnostic_reason_not_consumed")
        try:
            return super().validate(output=output, bundle=bundle, limits=limits)
        except InvalidSummary as exc:
            self._last_reason = exc.reason
            raise

    def take_reason(self) -> SummaryValidationFailureReason | None:
        reason = self._last_reason
        self._last_reason = None
        return reason


class DiagnosticBudgetedSummaryTransport:
    def __init__(
        self,
        delegate: StructuredModelTransport,
        journal: KnowledgeEgressDiagnosticJournal,
        validator: RecordingExtractiveSummaryValidator,
    ) -> None:
        self._delegate = delegate
        self._journal = journal
        self._validator = validator
        self._active_case_id: str | None = None
        self.calls = 0
        self.retry_count = 0
        self.forbidden_field_count = 0

    def begin_case(self, case_id: str) -> None:
        if self._active_case_id is not None:
            raise RuntimeError("knowledge.egress_diagnostic_case_overlap")
        self._active_case_id = case_id

    def end_case(self, case_id: str) -> None:
        if self._active_case_id != case_id:
            raise RuntimeError("knowledge.egress_diagnostic_case_mismatch")
        self._active_case_id = None

    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        if self.calls >= AUTHORIZED_SUMMARY_CALLS:
            raise RuntimeError("knowledge.egress_diagnostic_budget_exhausted")
        if self._active_case_id is None:
            raise RuntimeError("knowledge.egress_diagnostic_case_missing")
        if request.task_id.value != "knowledge_summary" or request.tools:
            raise RuntimeError("knowledge.egress_diagnostic_request_invalid")
        self.forbidden_field_count += count_forbidden_keys(json.loads(request.user_payload_json))
        if self.forbidden_field_count:
            raise RuntimeError("knowledge.egress_diagnostic_payload_forbidden")
        if self.calls == 0:
            _write_consumed_marker(Path(required_environment("AGENT_KNOWLEDGE_DIAGNOSTIC_CONSUMED_OUTPUT")))
        call_ordinal = self.calls + 1
        case_id = self._active_case_id
        self._journal.record_outbound_started(call_ordinal=call_ordinal, case_id=case_id)
        self.calls = call_ordinal
        try:
            return await self._delegate.complete(request, call_deadline=call_deadline)
        except asyncio.CancelledError:
            self._journal.record_terminal(call_ordinal=call_ordinal, case_id=case_id, status="timeout")
            raise
        except TimeoutError:
            self._journal.record_terminal(call_ordinal=call_ordinal, case_id=case_id, status="timeout")
            raise
        except ModelTransportError as exc:
            status = {
                ModelProviderFailureKind.PROVIDER_TIMEOUT: "timeout",
                ModelProviderFailureKind.INVALID_OUTPUT: "schema_invalid",
            }.get(exc.kind, "http_failure")
            self._journal.record_terminal(call_ordinal=call_ordinal, case_id=case_id, status=status)
            raise
        except Exception:
            self._journal.record_terminal(call_ordinal=call_ordinal, case_id=case_id, status="http_failure")
            raise

    def record_result(self, *, case_id: str, kind: EvidenceStageKind, stage_code: object) -> None:
        call_ordinal = self.calls
        validation_reason = self._validator.take_reason()
        if self._journal.is_terminal(call_ordinal):
            if validation_reason is not None:
                raise RuntimeError("knowledge.egress_diagnostic_unexpected_validation_reason")
            return
        if kind is EvidenceStageKind.SUCCESS:
            status = "success"
        elif kind is EvidenceStageKind.NO_RESULT:
            status = "insufficient_evidence"
        elif kind is EvidenceStageKind.TIMEOUT:
            status = "timeout"
        elif getattr(stage_code, "value", None) == "invalid_summary":
            status = "quote_invalid"
        else:
            status = "schema_invalid"
        if status == "quote_invalid" and validation_reason is None:
            raise RuntimeError("knowledge.egress_diagnostic_validation_reason_missing")
        if status != "quote_invalid" and validation_reason is not None:
            raise RuntimeError("knowledge.egress_diagnostic_validation_reason_unexpected")
        self._journal.record_terminal(
            call_ordinal=call_ordinal,
            case_id=case_id,
            status=status,
            validation_reason=validation_reason,
        )


def _write_consumed_marker(path: Path) -> None:
    value = {
        "schemaVersion": 1,
        "gateId": "GATE-041",
        "workPackageId": "WP-K-EGRESS-DIAG-01",
        "runId": required_environment("AGENT_KNOWLEDGE_DIAGNOSTIC_RUN_ID"),
        "authorizationReference": required_environment("AGENT_KNOWLEDGE_DIAGNOSTIC_AUTHORIZATION_REFERENCE"),
        "manifestSha256": required_environment("AGENT_KNOWLEDGE_DIAGNOSTIC_MANIFEST_SHA256"),
        "consumedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "authorizedSummaryCalls": AUTHORIZED_SUMMARY_CALLS,
        "retryAllowed": False,
        "diagnosticOnly": True,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
