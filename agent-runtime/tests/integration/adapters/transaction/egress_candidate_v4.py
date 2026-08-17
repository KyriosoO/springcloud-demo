from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, Literal, NoReturn, cast

from agent_runtime.adapters.transaction.definition import transaction_search_definition
from agent_runtime.adapters.transaction.settings import TransactionAdapterSettings
from agent_runtime.business.http_client import (
    FakeDomainHttpRequest,
    FakeDomainHttpResponse,
    FakeDomainTransport,
)
from agent_runtime.business.settings import (
    BusinessConfigurationSnapshot,
    BusinessConfigurationSource,
    BusinessGlobalSettings,
    BusinessServiceBinding,
    BusinessSettingsValidator,
)
from agent_runtime.model.contracts import (
    ModelTaskId,
    StructuredModelRequest,
    StructuredModelResponse,
    StructuredModelTransport,
    StructuredOutputMode,
    StructuredToolMode,
)


RUN_ID: Final = "transaction-egress-v4-20260817-candidate-04"
PREPARATION_WORK_PACKAGE_ID: Final = "WP-TXN-EGRESS-CANDIDATE-04-PREP"
WORK_PACKAGE_ID: Final = "WP-TXN-EGRESS-01"
GATE_ID: Final = "GATE-026"
AUTHORIZATION_REFERENCE: Final = "P3_00:GATE-026"
SCHEMA_VERSION: Final = 4
QUESTION_POLICY_VERSION: Final = "question-egress-v2"
BUSINESS_POLICY_VERSION: Final = "business-egress-v1"
INPUT_CONTRACT_VERSION: Final = "transaction-search-type-equality-v1"
SAFE_QUESTION: Final = "概述这一条交易结果的交易类型和金额"
MODEL_VISIBLE_FIELD_IDS: Final = ("transaction_type", "amount")
MAXIMUM_TRANSACTION_SEARCHES: Final = 1
MAXIMUM_PAID_ANSWER_CALLS: Final = 30
MINIMUM_VALID_ANSWER_CALLS: Final = 27

REQUIRED_HISTORY_PATHS: Final = frozenset(
    {
        "agent-runtime/tests/integration/adapters/transaction/evidence/"
        "wp-txn-real-01-20260806T134518Z.json",
        "agent-runtime/tests/integration/adapters/transaction/evidence/"
        "transaction-egress-v1-20260814-candidate-01.manifest.json",
        "agent-runtime/tests/integration/adapters/transaction/evidence/"
        "transaction-egress-v1-20260814-candidate-01.authorization.json",
        "agent-runtime/tests/integration/adapters/transaction/"
        "test_transaction_egress_candidate_history.py",
        "agent-runtime/tests/integration/adapters/transaction/evidence/"
        "transaction-egress-v2-20260817-candidate-02.manifest.json",
        "agent-runtime/tests/integration/adapters/transaction/evidence/"
        "transaction-egress-v2-20260817-candidate-02.authorization.json",
        "agent-runtime/tests/integration/adapters/transaction/evidence/"
        "transaction-egress-v2-20260817-candidate-02.initialization-failure.json",
        "agent-runtime/tests/integration/adapters/transaction/"
        "test_transaction_egress_candidate_v2_failed_history.py",
        "agent-runtime/tests/integration/adapters/transaction/evidence/"
        "transaction-egress-v3-20260817-candidate-03.manifest.json",
        "agent-runtime/tests/integration/adapters/transaction/evidence/"
        "transaction-egress-v3-20260817-candidate-03.authorization.json",
        "agent-runtime/tests/integration/adapters/transaction/evidence/"
        "transaction-egress-v3-20260817-candidate-03.host-preflight.jsonl",
        "agent-runtime/tests/integration/adapters/transaction/evidence/"
        "transaction-egress-v3-20260817-candidate-03.host-result.json",
        "agent-runtime/tests/integration/adapters/transaction/evidence/"
        "transaction-egress-v3-20260817-candidate-03.lifecycle.jsonl",
        "agent-runtime/tests/integration/adapters/transaction/evidence/"
        "transaction-egress-v3-20260817-candidate-03.result.json",
        "agent-runtime/tests/integration/adapters/transaction/"
        "test_transaction_egress_candidate_v3_failed_history.py",
    }
)

REQUIRED_ASSET_PATHS: Final = frozenset(
    {
        "agent-runtime/scripts/run-transaction-egress-live-candidate-04.ps1",
        "agent-runtime/src/agent_runtime/bootstrap.py",
        "agent-runtime/src/agent_runtime/business/egress.py",
        "agent-runtime/src/agent_runtime/business/grounding.py",
        "agent-runtime/src/agent_runtime/business/handler.py",
        "agent-runtime/src/agent_runtime/business/http_client.py",
        "agent-runtime/src/agent_runtime/business/settings.py",
        "agent-runtime/src/agent_runtime/business/user_projection.py",
        "agent-runtime/src/agent_runtime/model/deepseek/answer_generator_v2.py",
        "agent-runtime/src/agent_runtime/model/deepseek/transport.py",
        "agent-runtime/src/agent_runtime/model/input_guard.py",
        "agent-runtime/src/agent_runtime/model/question_policy.py",
        "agent-runtime/src/agent_runtime/model/settings.py",
        "agent-runtime/src/agent_runtime/adapters/transaction/codec.py",
        "agent-runtime/src/agent_runtime/adapters/transaction/definition.py",
        "agent-runtime/src/agent_runtime/adapters/transaction/fields.py",
        "agent-runtime/src/agent_runtime/adapters/transaction/normalizer.py",
        "agent-runtime/src/agent_runtime/adapters/transaction/settings.py",
        "agent-runtime/tests/helpers.py",
        "agent-runtime/tests/model_helpers.py",
        "agent-runtime/tests/unit/business/test_grounding.py",
        "agent-runtime/tests/unit/model/test_input_guard.py",
        "agent-runtime/tests/integration/adapters/transaction/egress_candidate_v4.py",
        "agent-runtime/tests/integration/adapters/transaction/egress_candidate_v4_host.py",
        "agent-runtime/tests/integration/adapters/transaction/"
        "test_real_transaction_egress_candidate_v4.py",
        "agent-runtime/tests/integration/adapters/transaction/"
        "test_transaction_egress_candidate_v4_harness.py",
        "agent-runtime/tests/integration/adapters/transaction/"
        "test_transaction_egress_candidate_v4_host.py",
        "agent-runtime/tests/integration/adapters/transaction/"
        "test_transaction_egress_candidate_v4_history.py",
        "agent-runtime/tests/integration/adapters/transaction/"
        "test_transaction_egress_candidate_v4_preparation.py",
        "agent-runtime/tests/integration/adapters/transaction/evidence/"
        "transaction-egress-candidate-v4-lifecycle.schema.json",
        "agent-runtime/tests/integration/adapters/transaction/evidence/"
        "transaction-egress-candidate-v4-result.schema.json",
        "agent-runtime/tests/integration/adapters/transaction/evidence/"
        "transaction-egress-candidate-v4-host-preflight.schema.json",
        "agent-runtime/tests/integration/adapters/transaction/evidence/"
        "transaction-egress-candidate-v4-host-result.schema.json",
    }
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_RUN_STATUSES = {"passed", "failed_unconsumed", "failed_consumed"}
_MODEL_TERMINALS = {
    "answer",
    "input_denied",
    "invalid_output",
    "provider_timeout",
    "provider_failure",
}
_FAILURE_REASONS = {
    "none",
    "transaction_search_failed",
    "transaction_result_invalid",
    "egress_projection_invalid",
    "model_request_invalid",
    "model_call_failed",
    "threshold_not_met",
    "log_leak_detected",
    "cleanup_failed",
    "internal_failure",
}
_LIFECYCLE_KEYS = {
    "schemaVersion",
    "runId",
    "manifestSha256",
    "authorizationReference",
    "sequence",
    "event",
    "phase",
    "ordinal",
    "status",
    "reason",
    "retryCount",
    "resumeCount",
}
_RESULT_KEYS = {
    "schemaVersion",
    "status",
    "runId",
    "manifestSha256",
    "authorizationReference",
    "policyVersions",
    "counts",
    "threshold",
    "safety",
    "failure",
}

ModelTerminalStatus = Literal[
    "answer",
    "input_denied",
    "invalid_output",
    "provider_timeout",
    "provider_failure",
]


class TransactionEgressCandidateError(ValueError):
    pass


class TransactionEgressEvidenceWriteError(RuntimeError):
    pass


def build_live_forbidden_literals(
    *,
    user_jwt: str,
    api_key: str,
    domain_result: Mapping[str, object],
) -> tuple[str, ...]:
    """Build the live-only deny list without rejecting approved model facts."""
    if not user_jwt or not api_key:
        raise TransactionEgressCandidateError("transaction.egress_candidate_secret_invalid")
    records = domain_result.get("records")
    if not isinstance(records, tuple):
        raise TransactionEgressCandidateError("transaction.egress_candidate_domain_result_invalid")
    literals: list[str] = [user_jwt, api_key]
    for record in records:
        if not isinstance(record, Mapping):
            raise TransactionEgressCandidateError("transaction.egress_candidate_domain_result_invalid")
        fields = record.get("fields")
        if not isinstance(fields, Mapping):
            raise TransactionEgressCandidateError("transaction.egress_candidate_domain_result_invalid")
        for field_id, value in fields.items():
            if (
                field_id not in MODEL_VISIBLE_FIELD_IDS
                and isinstance(value, str)
                and value
            ):
                literals.append(value)
    return tuple(dict.fromkeys(literals))


class TransactionEgressFailurePhase(StrEnum):
    TRANSACTION_SEARCH = "transaction_search"
    TRANSACTION_RESULT = "transaction_result"
    EGRESS_PROJECTION = "egress_projection"
    MODEL_SETUP = "model_setup"
    MODEL_CALL = "model_call"
    THRESHOLD = "threshold"
    CLEANUP = "cleanup"
    INTERNAL = "internal"


class TransactionEgressFailureReason(StrEnum):
    TRANSACTION_SEARCH_FAILED = "transaction_search_failed"
    TRANSACTION_RESULT_INVALID = "transaction_result_invalid"
    EGRESS_PROJECTION_INVALID = "egress_projection_invalid"
    MODEL_REQUEST_INVALID = "model_request_invalid"
    MODEL_CALL_FAILED = "model_call_failed"
    THRESHOLD_NOT_MET = "threshold_not_met"
    LOG_LEAK_DETECTED = "log_leak_detected"
    CLEANUP_FAILED = "cleanup_failed"
    INTERNAL_FAILURE = "internal_failure"


@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionEgressLifecycleSnapshot:
    status: str
    failure_phase: str | None
    failure_reason: str | None
    transaction_search_started: int
    transaction_search_terminal: int
    answer_started: int
    answer_terminal: int
    valid_answers: int
    consumed: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionEgressSafetySnapshot:
    forbidden_payload_field_count: int = 0
    forbidden_literal_count: int = 0
    log_leak_count: int = 0


def _invalid() -> NoReturn:
    raise TransactionEgressCandidateError("transaction.egress_candidate_invalid")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _invalid()
        value[key] = item
    return value


def load_strict_json(path: Path, *, max_bytes: int = 262_144) -> dict[str, Any]:
    raw = path.read_bytes()
    if not raw or len(raw) > max_bytes or raw.startswith(b"\xef\xbb\xbf"):
        _invalid()
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise TransactionEgressCandidateError("transaction.egress_candidate_invalid") from exc
    if type(value) is not dict:
        _invalid()
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lifecycle_path_for(directory: Path) -> Path:
    return directory / f"{RUN_ID}.lifecycle.jsonl"


def consumed_path_for(directory: Path) -> Path:
    return directory / f"{RUN_ID}.authorization.consumed.json"


def result_path_for(directory: Path) -> Path:
    return directory / f"{RUN_ID}.result.json"


def build_transaction_egress_snapshot() -> BusinessConfigurationSnapshot:
    definition = transaction_search_definition()
    action = TransactionAdapterSettings.from_env(
        {
            "AGENT_TRANSACTION_SEARCH_ENABLED": "true",
            "AGENT_TRANSACTION_SEARCH_MAX_PAGE_SIZE": "1",
            "AGENT_TRANSACTION_SEARCH_MAX_RESULT_COUNT": "1",
            "AGENT_TRANSACTION_SEARCH_FILTER_FIELDS": "trans_type",
            "AGENT_TRANSACTION_SEARCH_SORT_FIELDS": "",
            "AGENT_TRANSACTION_SEARCH_USER_FIELDS": "transaction_type,amount",
            "AGENT_TRANSACTION_SEARCH_MODEL_FIELDS": "transaction_type,amount",
        }
    ).action
    return BusinessSettingsValidator().validate(
        (definition,),
        BusinessConfigurationSource(
            global_settings=BusinessGlobalSettings(egress_enabled=True),
            actions=((definition.descriptor.capability_id, action),),
            service_bindings=(
                BusinessServiceBinding(
                    service_key=definition.service_key,
                    base_endpoint="http://127.0.0.1:9202",
                ),
            ),
        ),
        core_max_domain_result_bytes=262_144,
    )


def _write_exclusive_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except (FileExistsError, OSError) as exc:
        raise TransactionEgressEvidenceWriteError(
            "transaction.egress_candidate_evidence_write_failed"
        ) from exc


def write_exclusive_json(path: Path, value: Mapping[str, object]) -> None:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    _write_exclusive_bytes(path, payload)


def write_consumed_marker(path: Path, *, manifest_sha256: str) -> None:
    if _SHA256.fullmatch(manifest_sha256) is None:
        _invalid()
    write_exclusive_json(
        path,
        {
            "schemaVersion": SCHEMA_VERSION,
            "state": "consumed",
            "runId": RUN_ID,
            "manifestSha256": manifest_sha256,
            "authorizationReference": AUTHORIZATION_REFERENCE,
        },
    )


def validate_consumed_marker(value: object, *, manifest_sha256: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != {
        "schemaVersion",
        "state",
        "runId",
        "manifestSha256",
        "authorizationReference",
    }:
        _invalid()
    marker = cast(dict[str, Any], value)
    if marker != {
        "schemaVersion": SCHEMA_VERSION,
        "state": "consumed",
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
    }:
        _invalid()
    return marker


class TransactionEgressLifecycleJournal:
    def __init__(self, path: Path, *, manifest_sha256: str) -> None:
        if _SHA256.fullmatch(manifest_sha256) is None:
            _invalid()
        self._path = path
        self._manifest_sha256 = manifest_sha256
        self._sequence = 0
        self._search_started = False
        self._search_terminal = False
        self._answer_started = 0
        self._answer_terminal = 0
        self._run_terminal = False
        self._create()
        self._append(
            event="run_started",
            phase="run",
            ordinal=0,
            status="started",
            reason="none",
        )

    @property
    def path(self) -> Path:
        return self._path

    @property
    def manifest_sha256(self) -> str:
        return self._manifest_sha256

    @property
    def consumed_marker_path(self) -> Path:
        return consumed_path_for(self._path.parent)

    def record_search_started(self) -> None:
        if self._run_terminal or self._search_started:
            _invalid()
        self._search_started = True
        self._append(
            event="transaction_search_started",
            phase="transaction_search",
            ordinal=1,
            status="started",
            reason="none",
        )

    def record_search_terminal(self, *, status: Literal["completed", "failed"]) -> None:
        if self._run_terminal or not self._search_started or self._search_terminal:
            _invalid()
        self._search_terminal = True
        self._append(
            event="transaction_search_terminal",
            phase="transaction_search",
            ordinal=1,
            status=status,
            reason="none" if status == "completed" else "transaction_search_failed",
        )

    def record_model_started(self, *, ordinal: int) -> None:
        if (
            self._run_terminal
            or not self._search_terminal
            or ordinal != self._answer_started + 1
            or ordinal > MAXIMUM_PAID_ANSWER_CALLS
        ):
            _invalid()
        self._answer_started = ordinal
        self._append(
            event="model_answer_started",
            phase="model_answer",
            ordinal=ordinal,
            status="started",
            reason="none",
        )

    def record_model_terminal(self, *, ordinal: int, status: ModelTerminalStatus) -> None:
        if (
            self._run_terminal
            or ordinal != self._answer_terminal + 1
            or ordinal > self._answer_started
            or status not in _MODEL_TERMINALS
        ):
            _invalid()
        self._answer_terminal = ordinal
        self._append(
            event="model_answer_terminal",
            phase="model_answer",
            ordinal=ordinal,
            status=status,
            reason="none",
        )

    def record_run_terminal(
        self,
        *,
        status: Literal["passed", "failed_unconsumed", "failed_consumed"],
        failure_phase: TransactionEgressFailurePhase | None,
        failure_reason: TransactionEgressFailureReason | None,
    ) -> None:
        if self._run_terminal or self._answer_started != self._answer_terminal:
            _invalid()
        if status == "passed":
            if failure_phase is not None or failure_reason is not None:
                _invalid()
            reason = "none"
            phase = "run"
        else:
            if failure_phase is None or failure_reason is None:
                _invalid()
            reason = failure_reason.value
            phase = failure_phase.value
        self._run_terminal = True
        self._append(
            event="run_terminal",
            phase=phase,
            ordinal=0,
            status=status,
            reason=reason,
        )

    def _create(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._path.open("xb") as stream:
                stream.flush()
                os.fsync(stream.fileno())
        except (FileExistsError, OSError) as exc:
            raise TransactionEgressEvidenceWriteError(
                "transaction.egress_candidate_lifecycle_create_failed"
            ) from exc

    def _append(
        self,
        *,
        event: str,
        phase: str,
        ordinal: int,
        status: str,
        reason: str,
    ) -> None:
        self._sequence += 1
        record = {
            "schemaVersion": SCHEMA_VERSION,
            "runId": RUN_ID,
            "manifestSha256": self._manifest_sha256,
            "authorizationReference": AUTHORIZATION_REFERENCE,
            "sequence": self._sequence,
            "event": event,
            "phase": phase,
            "ordinal": ordinal,
            "status": status,
            "reason": reason,
            "retryCount": 0,
            "resumeCount": 0,
        }
        try:
            with self._path.open("a", encoding="utf-8", newline="\n") as stream:
                json.dump(record, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise TransactionEgressEvidenceWriteError(
                "transaction.egress_candidate_lifecycle_write_failed"
            ) from exc


class JournaledTransactionSearchTransport:
    def __init__(
        self,
        *,
        delegate: FakeDomainTransport,
        journal: TransactionEgressLifecycleJournal,
        expected_transaction_type: str,
    ) -> None:
        if not expected_transaction_type:
            raise ValueError("transaction.egress_candidate_search_type_invalid")
        self._delegate = delegate
        self._journal = journal
        self._expected_transaction_type = expected_transaction_type
        self.calls = 0

    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        if self.calls >= MAXIMUM_TRANSACTION_SEARCHES:
            raise RuntimeError("transaction.egress_candidate_search_budget_exhausted")
        self._validate_request(request)
        self._journal.record_search_started()
        self.calls = 1
        try:
            response = await self._delegate.send(request)
        except BaseException:
            self._journal.record_search_terminal(status="failed")
            raise
        self._journal.record_search_terminal(status="completed")
        return response

    async def aclose(self) -> None:
        await self._delegate.aclose()

    def _validate_request(self, request: FakeDomainHttpRequest) -> None:
        outbound = request.request
        if (
            outbound.method != "POST"
            or outbound.relative_path != "/txn/search"
            or outbound.query
            or outbound.json_body is None
        ):
            raise RuntimeError("transaction.egress_candidate_search_request_invalid")
        try:
            body = json.loads(outbound.json_body.content.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("transaction.egress_candidate_search_request_invalid") from exc
        if body != {
            "condition": {"transType": self._expected_transaction_type},
            "page": 1,
            "size": 1,
            "sorts": [],
        }:
            raise RuntimeError("transaction.egress_candidate_search_request_invalid")


def _count_keys(value: object, forbidden: frozenset[str]) -> int:
    if isinstance(value, dict):
        return sum(key in forbidden for key in value) + sum(
            _count_keys(item, forbidden) for item in value.values()
        )
    if isinstance(value, list):
        return sum(_count_keys(item, forbidden) for item in value)
    return 0


def count_forbidden_log_literals(text: str, literals: Sequence[str]) -> int:
    return min(1_000, sum(text.count(value) for value in frozenset(literals) if value))


class BudgetedTransactionAnswerTransport:
    def __init__(
        self,
        *,
        delegate: StructuredModelTransport,
        journal: TransactionEgressLifecycleJournal,
        forbidden_literals: Sequence[str] = (),
    ) -> None:
        self._delegate = delegate
        self._journal = journal
        self._forbidden_literals = tuple(value for value in forbidden_literals if value)
        self.calls = 0
        self.terminal_calls = 0
        self.retry_count = 0
        self.forbidden_payload_field_count = 0
        self.forbidden_literal_count = 0
        self.requests: list[StructuredModelRequest] = []

    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        if self.calls >= MAXIMUM_PAID_ANSWER_CALLS:
            raise RuntimeError("transaction.egress_candidate_budget_exhausted")
        self._validate_request(request)
        ordinal = self.calls + 1
        if ordinal == 1:
            write_consumed_marker(
                self._journal.consumed_marker_path,
                manifest_sha256=self._journal.manifest_sha256,
            )
        self._journal.record_model_started(ordinal=ordinal)
        self.calls = ordinal
        self.requests.append(request)
        return await self._delegate.complete(request, call_deadline=call_deadline)

    def record_terminal(self, status: ModelTerminalStatus) -> None:
        ordinal = self.terminal_calls + 1
        if ordinal > self.calls:
            _invalid()
        self._journal.record_model_terminal(ordinal=ordinal, status=status)
        self.terminal_calls = ordinal

    def _validate_request(self, request: StructuredModelRequest) -> None:
        if (
            request.task_id is not ModelTaskId.ANSWER_GENERATION
            or request.task_version != "answer-generation-v2"
            or request.tools
            or request.tool_mode is not StructuredToolMode.NONE
            or request.output_mode is not StructuredOutputMode.JSON_OBJECT
        ):
            raise RuntimeError("transaction.egress_candidate_request_invalid")
        try:
            payload = json.loads(request.user_payload_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("transaction.egress_candidate_request_invalid") from exc
        if type(payload) is not dict or set(payload) != {"question", "safe_payload"}:
            raise RuntimeError("transaction.egress_candidate_request_invalid")
        if payload["question"] != SAFE_QUESTION:
            raise RuntimeError("transaction.egress_candidate_question_invalid")
        safe_payload = payload["safe_payload"]
        if type(safe_payload) is not dict or set(safe_payload) != {
            "schema_version",
            "policy_version",
            "config_snapshot_id",
            "facts",
            "presentation",
            "coverage",
        }:
            raise RuntimeError("transaction.egress_candidate_payload_invalid")
        facts = safe_payload.get("facts")
        if type(facts) is not list or len(facts) != 2:
            raise RuntimeError("transaction.egress_candidate_field_boundary_invalid")
        field_ids: list[str] = []
        for fact in facts:
            if type(fact) is not dict:
                raise RuntimeError("transaction.egress_candidate_field_boundary_invalid")
            source = fact.get("source")
            if type(source) is not dict or type(source.get("field_id")) is not str:
                raise RuntimeError("transaction.egress_candidate_field_boundary_invalid")
            field_ids.append(cast(str, source["field_id"]))
        if tuple(field_ids) != MODEL_VISIBLE_FIELD_IDS:
            raise RuntimeError("transaction.egress_candidate_field_boundary_invalid")
        amount_fact = facts[1]
        if (
            amount_fact.get("value_type") != "decimal"
            or amount_fact.get("transform_id") != "decimal_2"
            or type(amount_fact.get("value")) is not str
            or re.fullmatch(r"-?(?:0|[1-9][0-9]*)\.[0-9]{2}", cast(str, amount_fact["value"])) is None
        ):
            raise RuntimeError("transaction.egress_candidate_decimal_invalid")
        forbidden_keys = frozenset(
            {
                "transaction_id",
                "transaction_id_masked",
                "trans_id",
                "transId",
                "date",
                "trans_date",
                "transDate",
                "total",
                "total_count",
                "raw_response",
                "query",
                "condition",
                "jwt",
                "user_token",
            }
        )
        self.forbidden_payload_field_count += _count_keys(payload, forbidden_keys)
        self.forbidden_literal_count += sum(
            value in request.user_payload_json for value in self._forbidden_literals
        )
        if self.forbidden_payload_field_count or self.forbidden_literal_count:
            raise RuntimeError("transaction.egress_candidate_payload_forbidden")


def _parse_jsonl(path: Path) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    if not raw or len(raw) > 262_144 or raw.startswith(b"\xef\xbb\xbf"):
        _invalid()
    records: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line:
            _invalid()
        try:
            value = json.loads(line.decode("utf-8"), object_pairs_hook=_unique_object)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise TransactionEgressCandidateError("transaction.egress_candidate_invalid") from exc
        if type(value) is not dict:
            _invalid()
        records.append(value)
    return records


def validate_lifecycle(
    path: Path,
    *,
    consumed_path: Path,
    manifest_sha256: str,
) -> TransactionEgressLifecycleSnapshot:
    records = _parse_jsonl(path)
    if len(records) < 2:
        _invalid()
    for sequence, record in enumerate(records, 1):
        if set(record) != _LIFECYCLE_KEYS:
            _invalid()
        if (
            record["schemaVersion"] != SCHEMA_VERSION
            or record["runId"] != RUN_ID
            or record["manifestSha256"] != manifest_sha256
            or record["authorizationReference"] != AUTHORIZATION_REFERENCE
            or record["sequence"] != sequence
            or record["retryCount"] != 0
            or record["resumeCount"] != 0
            or type(record["ordinal"]) is not int
        ):
            _invalid()
    if records[0] != {
        "schemaVersion": SCHEMA_VERSION,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "sequence": 1,
        "event": "run_started",
        "phase": "run",
        "ordinal": 0,
        "status": "started",
        "reason": "none",
        "retryCount": 0,
        "resumeCount": 0,
    }:
        _invalid()
    final = records[-1]
    if final["event"] != "run_terminal" or final["status"] not in _RUN_STATUSES:
        _invalid()
    search_started = 0
    search_terminal = 0
    answer_started = 0
    answer_terminal = 0
    valid_answers = 0
    open_model_ordinal: int | None = None
    for record in records[1:-1]:
        event = record["event"]
        ordinal = cast(int, record["ordinal"])
        if event == "transaction_search_started":
            if search_started or search_terminal or ordinal != 1 or record["status"] != "started":
                _invalid()
            search_started = 1
        elif event == "transaction_search_terminal":
            if search_started != 1 or search_terminal or ordinal != 1 or record["status"] not in {"completed", "failed"}:
                _invalid()
            search_terminal = 1
        elif event == "model_answer_started":
            if search_terminal != 1 or open_model_ordinal is not None or ordinal != answer_started + 1 or record["status"] != "started":
                _invalid()
            answer_started += 1
            open_model_ordinal = ordinal
        elif event == "model_answer_terminal":
            if open_model_ordinal != ordinal or ordinal != answer_terminal + 1 or record["status"] not in _MODEL_TERMINALS:
                _invalid()
            answer_terminal += 1
            valid_answers += int(record["status"] == "answer")
            open_model_ordinal = None
        else:
            _invalid()
    if (
        search_started > MAXIMUM_TRANSACTION_SEARCHES
        or search_terminal != search_started
        or answer_started > MAXIMUM_PAID_ANSWER_CALLS
        or answer_terminal != answer_started
        or open_model_ordinal is not None
    ):
        _invalid()
    consumed = consumed_path.is_file()
    if consumed:
        validate_consumed_marker(load_strict_json(consumed_path), manifest_sha256=manifest_sha256)
    status = cast(str, final["status"])
    failure_phase = None if status == "passed" else cast(str, final["phase"])
    failure_reason = None if status == "passed" else cast(str, final["reason"])
    if status == "passed":
        if (
            not consumed
            or search_started != 1
            or answer_started != MAXIMUM_PAID_ANSWER_CALLS
            or valid_answers < MINIMUM_VALID_ANSWER_CALLS
            or final["phase"] != "run"
            or final["reason"] != "none"
        ):
            _invalid()
    elif status == "failed_unconsumed":
        if consumed or answer_started != 0 or failure_reason not in _FAILURE_REASONS - {"none"}:
            _invalid()
    elif status == "failed_consumed":
        if not consumed or failure_reason not in _FAILURE_REASONS - {"none"}:
            _invalid()
    return TransactionEgressLifecycleSnapshot(
        status=status,
        failure_phase=failure_phase,
        failure_reason=failure_reason,
        transaction_search_started=search_started,
        transaction_search_terminal=search_terminal,
        answer_started=answer_started,
        answer_terminal=answer_terminal,
        valid_answers=valid_answers,
        consumed=consumed,
    )


def finalize_result(
    *,
    journal: TransactionEgressLifecycleJournal,
    result_path: Path,
    config_snapshot_id: str,
    safety: TransactionEgressSafetySnapshot = TransactionEgressSafetySnapshot(),
) -> dict[str, object]:
    snapshot = validate_lifecycle(
        journal.path,
        consumed_path=journal.consumed_marker_path,
        manifest_sha256=journal.manifest_sha256,
    )
    result: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "status": snapshot.status,
        "runId": RUN_ID,
        "manifestSha256": journal.manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "policyVersions": {
            "question": QUESTION_POLICY_VERSION,
            "business": BUSINESS_POLICY_VERSION,
            "inputContract": INPUT_CONTRACT_VERSION,
            "configSnapshotSha256": config_snapshot_id,
        },
        "counts": {
            "transactionSearchStarted": snapshot.transaction_search_started,
            "transactionSearchTerminal": snapshot.transaction_search_terminal,
            "answerStarted": snapshot.answer_started,
            "answerTerminal": snapshot.answer_terminal,
            "validAnswers": snapshot.valid_answers,
            "otherTransactionEndpoints": 0,
            "retryCount": 0,
            "resumeCount": 0,
        },
        "threshold": {
            "maximumAnswerCalls": MAXIMUM_PAID_ANSWER_CALLS,
            "minimumValidAnswers": MINIMUM_VALID_ANSWER_CALLS,
        },
        "safety": {
            "forbiddenPayloadFieldCount": safety.forbidden_payload_field_count,
            "forbiddenLiteralCount": safety.forbidden_literal_count,
            "logLeakCount": safety.log_leak_count,
            "queryValuePersisted": False,
            "transactionValuePersisted": False,
            "jwtPersisted": False,
            "factsPersisted": False,
            "promptPersisted": False,
            "rawResponsePersisted": False,
        },
        "failure": {
            "phase": snapshot.failure_phase,
            "reason": snapshot.failure_reason,
        },
    }
    validate_result(result)
    write_exclusive_json(result_path, result)
    return result


def validate_result(value: object) -> dict[str, Any]:
    if type(value) is not dict or set(value) != _RESULT_KEYS:
        _invalid()
    result = cast(dict[str, Any], value)
    if (
        result["schemaVersion"] != SCHEMA_VERSION
        or result["status"] not in _RUN_STATUSES
        or result["runId"] != RUN_ID
        or result["authorizationReference"] != AUTHORIZATION_REFERENCE
        or _SHA256.fullmatch(str(result["manifestSha256"])) is None
    ):
        _invalid()
    policies = result["policyVersions"]
    if type(policies) is not dict or set(policies) != {
        "question",
        "business",
        "inputContract",
        "configSnapshotSha256",
    }:
        _invalid()
    if (
        policies["question"] != QUESTION_POLICY_VERSION
        or policies["business"] != BUSINESS_POLICY_VERSION
        or policies["inputContract"] != INPUT_CONTRACT_VERSION
        or _SHA256.fullmatch(str(policies["configSnapshotSha256"])) is None
    ):
        _invalid()
    counts = result["counts"]
    if type(counts) is not dict or set(counts) != {
        "transactionSearchStarted",
        "transactionSearchTerminal",
        "answerStarted",
        "answerTerminal",
        "validAnswers",
        "otherTransactionEndpoints",
        "retryCount",
        "resumeCount",
    }:
        _invalid()
    if any(type(counts[key]) is not int for key in counts):
        _invalid()
    if (
        not 0 <= counts["transactionSearchStarted"] <= 1
        or counts["transactionSearchTerminal"] != counts["transactionSearchStarted"]
        or not 0 <= counts["answerStarted"] <= MAXIMUM_PAID_ANSWER_CALLS
        or counts["answerTerminal"] != counts["answerStarted"]
        or not 0 <= counts["validAnswers"] <= counts["answerTerminal"]
        or counts["otherTransactionEndpoints"] != 0
        or counts["retryCount"] != 0
        or counts["resumeCount"] != 0
    ):
        _invalid()
    if result["threshold"] != {
        "maximumAnswerCalls": MAXIMUM_PAID_ANSWER_CALLS,
        "minimumValidAnswers": MINIMUM_VALID_ANSWER_CALLS,
    }:
        _invalid()
    safety = result["safety"]
    if type(safety) is not dict or set(safety) != {
        "forbiddenPayloadFieldCount",
        "forbiddenLiteralCount",
        "logLeakCount",
        "queryValuePersisted",
        "transactionValuePersisted",
        "jwtPersisted",
        "factsPersisted",
        "promptPersisted",
        "rawResponsePersisted",
    }:
        _invalid()
    if any(
        type(safety[key]) is not int or not 0 <= safety[key] <= 1_000
        for key in ("forbiddenPayloadFieldCount", "forbiddenLiteralCount", "logLeakCount")
    ):
        _invalid()
    if any(
        safety[key] is not False
        for key in (
            "queryValuePersisted",
            "transactionValuePersisted",
            "jwtPersisted",
            "factsPersisted",
            "promptPersisted",
            "rawResponsePersisted",
        )
    ):
        _invalid()
    failure = result["failure"]
    if type(failure) is not dict or set(failure) != {"phase", "reason"}:
        _invalid()
    status = result["status"]
    if status == "passed":
        if (
            failure != {"phase": None, "reason": None}
            or counts["transactionSearchStarted"] != 1
            or counts["answerStarted"] != MAXIMUM_PAID_ANSWER_CALLS
            or counts["validAnswers"] < MINIMUM_VALID_ANSWER_CALLS
            or any(safety[key] != 0 for key in ("forbiddenPayloadFieldCount", "forbiddenLiteralCount", "logLeakCount"))
        ):
            _invalid()
    else:
        if (
            type(failure["phase"]) is not str
            or failure["phase"] not in {item.value for item in TransactionEgressFailurePhase}
            or type(failure["reason"]) is not str
            or failure["reason"] not in _FAILURE_REASONS - {"none"}
        ):
            _invalid()
    return result


def validate_manifest(
    value: object,
    *,
    repository_root: Path,
    expected_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    if type(value) is not dict or set(value) != {
        "schemaVersion",
        "status",
        "preparationWorkPackageId",
        "workPackageId",
        "gateId",
        "runId",
        "authorizationReference",
        "preparedAt",
        "inputContractVersion",
        "executionBoundary",
        "history",
        "assetHashes",
    }:
        _invalid()
    manifest = cast(dict[str, Any], value)
    if (
        manifest["schemaVersion"] != SCHEMA_VERSION
        or manifest["status"] != "prepared_unconsumed"
        or manifest["preparationWorkPackageId"] != PREPARATION_WORK_PACKAGE_ID
        or manifest["workPackageId"] != WORK_PACKAGE_ID
        or manifest["gateId"] != GATE_ID
        or manifest["runId"] != RUN_ID
        or manifest["authorizationReference"] != AUTHORIZATION_REFERENCE
        or manifest["inputContractVersion"] != INPUT_CONTRACT_VERSION
    ):
        _invalid()
    boundary = manifest["executionBoundary"]
    if boundary != {
        "transactionSearchMaximum": 1,
        "paidAnswerMaximum": 30,
        "minimumValidAnswers": 27,
        "modelVisibleFieldIds": ["transaction_type", "amount"],
        "liveExecutionAuthorized": False,
        "transactionAccessAuthorized": False,
        "modelAccessAuthorized": False,
        "retryAllowed": False,
        "resumeAllowed": False,
    }:
        _invalid()
    history = manifest["history"]
    assets = manifest["assetHashes"]
    if type(history) is not list or not history or type(assets) is not list or not assets:
        _invalid()
    for collection in (history, assets):
        seen: set[str] = set()
        for item in collection:
            if type(item) is not dict or set(item) != {"path", "sha256"}:
                _invalid()
            relative = item["path"]
            digest = item["sha256"]
            if type(relative) is not str or relative in seen or _SHA256.fullmatch(str(digest)) is None:
                _invalid()
            seen.add(relative)
            path = (repository_root / relative).resolve()
            if repository_root.resolve() not in path.parents or not path.is_file() or sha256_file(path) != digest:
                _invalid()
    if {item["path"] for item in history} != REQUIRED_HISTORY_PATHS:
        _invalid()
    if {item["path"] for item in assets} != REQUIRED_ASSET_PATHS:
        _invalid()
    if expected_manifest_sha256 is not None and _SHA256.fullmatch(expected_manifest_sha256) is None:
        _invalid()
    return manifest


def validate_authorization(value: object, *, manifest_sha256: str) -> dict[str, Any]:
    expected = {
        "schemaVersion": SCHEMA_VERSION,
        "status": "prepared_unconsumed",
        "preparationWorkPackageId": PREPARATION_WORK_PACKAGE_ID,
        "workPackageId": WORK_PACKAGE_ID,
        "gateId": GATE_ID,
        "runId": RUN_ID,
        "manifestSha256": manifest_sha256,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "transactionSearchMaximum": 1,
        "paidAnswerMaximum": 30,
        "minimumValidAnswers": 27,
        "liveExecutionAuthorized": False,
        "transactionAccessAuthorized": False,
        "modelAccessAuthorized": False,
        "retryAllowed": False,
        "resumeAllowed": False,
        "confirmedBy": "project-maintainer-pending-gate-026-live-authorization",
        "preparedAt": "2026-08-17T00:00:00Z",
    }
    if value != expected:
        _invalid()
    return cast(dict[str, Any], value)
