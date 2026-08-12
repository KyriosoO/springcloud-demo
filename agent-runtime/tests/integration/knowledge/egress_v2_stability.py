from __future__ import annotations

import asyncio
import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from agent_runtime.knowledge.contracts import EvidenceStageKind
from agent_runtime.knowledge.evidence.summary_task_v2 import SUMMARY_PROMPT_V2
from agent_runtime.model.contracts import (
    ModelProviderFailureKind,
    ModelTransportError,
    StructuredModelRequest,
    StructuredModelResponse,
    StructuredModelTransport,
    StructuredOutputMode,
    StructuredToolMode,
)
from tests.integration.knowledge.egress_attempt_journal import KnowledgeEgressAttemptJournal
from tests.integration.knowledge.egress_live_evidence import validate_live_evidence


RUN_ID: Final = "knowledge-egress-v2-20260812-candidate-01"
AUTHORIZATION_GATE_ID: Final = "GATE-043"
CLOSURE_GATE_ID: Final = "GATE-022"
AUTHORIZATION_REFERENCE: Final = "P3_00:GATE-043"
AUTHORIZED_SUMMARY_CALLS: Final = 30
PROMPT_VERSION: Final = "knowledge-summary-extractive-prompt-v2"
PROMPT_SHA256: Final = "b6cf5e9a2d49ef09ce441ee5547eb57429f4df37c9efa6cc0bf29feec06a4797"
FORBIDDEN_PAYLOAD_KEYS: Final = {
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
TASK_BINDING = {
    "taskId": "knowledge_summary",
    "taskVersion": "2",
    "promptVersion": PROMPT_VERSION,
    "instructionSha256": PROMPT_SHA256,
}


class KnowledgeEgressV2EvidenceError(ValueError):
    pass


def _required(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"knowledge.egress_v2_env_missing:{name}")
    return value


def _count_forbidden_keys(value: object) -> int:
    if isinstance(value, dict):
        return sum(key in FORBIDDEN_PAYLOAD_KEYS for key in value) + sum(
            _count_forbidden_keys(item) for item in value.values()
        )
    if isinstance(value, list):
        return sum(_count_forbidden_keys(item) for item in value)
    return 0


def _write_consumed_marker(path: Path) -> None:
    marker = {
        "schemaVersion": 1,
        "gateId": AUTHORIZATION_GATE_ID,
        "closureGateId": CLOSURE_GATE_ID,
        "workPackageId": "WP-K-EGRESS-01",
        "runId": _required("AGENT_KNOWLEDGE_EGRESS_RUN_ID"),
        "authorizationReference": _required("AGENT_KNOWLEDGE_EGRESS_AUTHORIZATION_REFERENCE"),
        "consumedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "authorizedSummaryCalls": AUTHORIZED_SUMMARY_CALLS,
        "retryAllowed": False,
    }
    if marker["runId"] != RUN_ID or marker["authorizationReference"] != AUTHORIZATION_REFERENCE:
        raise RuntimeError("knowledge.egress_v2_authorization_binding_invalid")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(marker, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


class Gate043BudgetedSummaryTransport:
    def __init__(self, delegate: StructuredModelTransport, journal: KnowledgeEgressAttemptJournal) -> None:
        self._delegate = delegate
        self._journal = journal
        self._active_case_id: str | None = None
        self.calls = 0
        self.retry_count = 0
        self.forbidden_field_count = 0

    def begin_case(self, case_id: str) -> None:
        if self._active_case_id is not None:
            raise RuntimeError("knowledge.egress_v2_case_overlap")
        self._active_case_id = case_id

    def end_case(self, case_id: str) -> None:
        if self._active_case_id != case_id:
            raise RuntimeError("knowledge.egress_v2_case_mismatch")
        self._active_case_id = None

    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        if self.calls >= AUTHORIZED_SUMMARY_CALLS:
            raise RuntimeError("knowledge.egress_v2_budget_exhausted")
        if self._active_case_id is None:
            raise RuntimeError("knowledge.egress_v2_case_missing")
        if (
            request.task_id.value != "knowledge_summary"
            or request.task_version != "2"
            or request.system_instruction != SUMMARY_PROMPT_V2
            or request.tools
            or request.tool_mode is not StructuredToolMode.NONE
            or request.output_mode is not StructuredOutputMode.JSON_OBJECT
        ):
            raise RuntimeError("knowledge.egress_v2_request_invalid")
        payload = json.loads(request.user_payload_json)
        self.forbidden_field_count += _count_forbidden_keys(payload)
        if self.forbidden_field_count:
            raise RuntimeError("knowledge.egress_v2_payload_forbidden")
        if self.calls == 0:
            _write_consumed_marker(Path(_required("AGENT_KNOWLEDGE_EGRESS_CONSUMED_OUTPUT")))
        call_ordinal = self.calls + 1
        case_id = self._active_case_id
        self._journal.record_outbound_started(call_ordinal=call_ordinal, case_id=case_id)
        self.calls = call_ordinal
        try:
            return await self._delegate.complete(request, call_deadline=call_deadline)
        except (asyncio.CancelledError, TimeoutError):
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
        if self._journal.is_terminal(call_ordinal):
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
        self._journal.record_terminal(call_ordinal=call_ordinal, case_id=case_id, status=status)


def validate_v2_live_evidence(value: object) -> dict[str, Any]:
    if type(value) is not dict:
        raise KnowledgeEgressV2EvidenceError("knowledge.egress_v2_evidence_invalid")
    expected_keys = {
        "schemaVersion",
        "workPackageId",
        "gateId",
        "authorizationGateId",
        "runId",
        "recordedAt",
        "authorizationReference",
        "taskBinding",
        "dataBoundary",
        "catalog",
        "retrievalSnapshot",
        "budget",
        "negativeMatrix",
        "cases",
        "validation",
    }
    evidence = value
    if (
        set(evidence) != expected_keys
        or evidence["authorizationGateId"] != AUTHORIZATION_GATE_ID
        or evidence["runId"] != RUN_ID
        or evidence["authorizationReference"] != AUTHORIZATION_REFERENCE
        or evidence["taskBinding"] != TASK_BINDING
    ):
        raise KnowledgeEgressV2EvidenceError("knowledge.egress_v2_evidence_invalid")
    legacy_shape = deepcopy(evidence)
    del legacy_shape["authorizationGateId"]
    del legacy_shape["taskBinding"]
    legacy_shape["runId"] = "knowledge-egress-v1-20260812-candidate-03"
    legacy_shape["authorizationReference"] = "P3_00:GATE-040"
    try:
        validate_live_evidence(legacy_shape)
    except ValueError as exc:
        raise KnowledgeEgressV2EvidenceError("knowledge.egress_v2_evidence_invalid") from exc
    return evidence


def write_v2_live_evidence(path: Path, value: object) -> None:
    if type(value) is not dict:
        raise KnowledgeEgressV2EvidenceError("knowledge.egress_v2_evidence_invalid")
    enriched = dict(value)
    enriched["authorizationGateId"] = AUTHORIZATION_GATE_ID
    enriched["taskBinding"] = dict(TASK_BINDING)
    evidence = validate_v2_live_evidence(enriched)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(evidence, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
