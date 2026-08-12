from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from agent_runtime.knowledge.evidence.summary_validation import SummaryValidationFailureReason


SAFE_ID: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
SHA256: Final = re.compile(r"[0-9a-f]{64}")
CASE_IDS: Final = ("tax-policy", "tax-law", "tax-mixed")
REPEAT_COUNT: Final = 3
AUTHORIZED_SUMMARY_CALLS: Final = len(CASE_IDS) * REPEAT_COUNT
CASE_SEQUENCE: Final = tuple(case_id for _ in range(REPEAT_COUNT) for case_id in CASE_IDS)
TERMINAL_STATUSES: Final = frozenset(
    {
        "success",
        "http_failure",
        "timeout",
        "schema_invalid",
        "insufficient_evidence",
        "quote_invalid",
    }
)
VALIDATION_REASONS: Final = frozenset(item.value for item in SummaryValidationFailureReason)
HEADER_KEYS: Final = {
    "schemaVersion",
    "event",
    "runId",
    "gateId",
    "workPackageId",
    "authorizationReference",
    "manifestSha256",
    "authorizedSummaryCalls",
    "retryAllowed",
    "diagnosticOnly",
    "recordedAt",
}
CALL_KEYS: Final = {
    "schemaVersion",
    "event",
    "runId",
    "callOrdinal",
    "caseId",
    "recordedAt",
}
TERMINAL_KEYS: Final = CALL_KEYS | {"status"}
DIAGNOSTIC_TERMINAL_KEYS: Final = TERMINAL_KEYS | {"validationReason"}
RESULT_KEYS: Final = {
    "schemaVersion",
    "workPackageId",
    "gateId",
    "runId",
    "authorizationReference",
    "manifestSha256",
    "recordedAt",
    "status",
    "diagnosticOnly",
    "authorizedSummaryCalls",
    "actualSummaryCalls",
    "terminalRecordCount",
    "retryCount",
    "statusCounts",
    "validationReasonCounts",
    "dataBoundary",
    "closureClaimed",
}
DATA_BOUNDARY_KEYS: Final = {
    "questionPersisted",
    "knowledgeContentPersisted",
    "quotePersisted",
    "rawModelResponsePersisted",
    "jwtPersisted",
    "businessCallCount",
}


class KnowledgeEgressDiagnosticJournalError(ValueError):
    pass


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _safe_id(value: object) -> bool:
    return isinstance(value, str) and SAFE_ID.fullmatch(value) is not None


def _write_line(path: Path, value: dict[str, object], *, exclusive: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x" if exclusive else "a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def validate_diagnostic_journal(path: Path) -> tuple[dict[str, Any], ...]:
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise KnowledgeEgressDiagnosticJournalError("knowledge.egress_diagnostic_journal_invalid") from exc
    if not raw_lines or any(not line or len(line.encode("utf-8")) > 2048 for line in raw_lines):
        raise KnowledgeEgressDiagnosticJournalError("knowledge.egress_diagnostic_journal_invalid")
    try:
        records = tuple(json.loads(line) for line in raw_lines)
    except json.JSONDecodeError as exc:
        raise KnowledgeEgressDiagnosticJournalError("knowledge.egress_diagnostic_journal_invalid") from exc
    if any(type(record) is not dict for record in records):
        raise KnowledgeEgressDiagnosticJournalError("knowledge.egress_diagnostic_journal_invalid")

    header = records[0]
    if (
        set(header) != HEADER_KEYS
        or header["schemaVersion"] != 1
        or header["event"] != "attempt_started"
        or not _safe_id(header["runId"])
        or header["gateId"] != "GATE-041"
        or header["workPackageId"] != "WP-K-EGRESS-DIAG-01"
        or not _safe_id(header["authorizationReference"])
        or not isinstance(header["manifestSha256"], str)
        or SHA256.fullmatch(header["manifestSha256"]) is None
        or header["authorizedSummaryCalls"] != AUTHORIZED_SUMMARY_CALLS
        or header["retryAllowed"] is not False
        or header["diagnosticOnly"] is not True
        or not isinstance(header["recordedAt"], str)
    ):
        raise KnowledgeEgressDiagnosticJournalError("knowledge.egress_diagnostic_journal_invalid")

    run_id = header["runId"]
    started: dict[int, str] = {}
    terminal: set[int] = set()
    for record in records[1:]:
        event = record.get("event")
        status = record.get("status")
        if event == "outbound_started":
            expected_keys = CALL_KEYS
        elif event == "call_terminal" and status == "quote_invalid":
            expected_keys = DIAGNOSTIC_TERMINAL_KEYS
        else:
            expected_keys = TERMINAL_KEYS
        if (
            set(record) != expected_keys
            or record.get("schemaVersion") != 1
            or record.get("runId") != run_id
            or type(record.get("callOrdinal")) is not int
            or not 1 <= record["callOrdinal"] <= AUTHORIZED_SUMMARY_CALLS
            or record.get("caseId") not in CASE_IDS
            or not isinstance(record.get("recordedAt"), str)
        ):
            raise KnowledgeEgressDiagnosticJournalError("knowledge.egress_diagnostic_journal_invalid")
        ordinal = record["callOrdinal"]
        case_id = record["caseId"]
        if event == "outbound_started":
            if ordinal in started or ordinal != len(started) + 1 or case_id != CASE_SEQUENCE[ordinal - 1]:
                raise KnowledgeEgressDiagnosticJournalError("knowledge.egress_diagnostic_journal_invalid")
            started[ordinal] = case_id
        elif event == "call_terminal":
            if (
                ordinal not in started
                or ordinal in terminal
                or started[ordinal] != case_id
                or status not in TERMINAL_STATUSES
                or (status == "quote_invalid" and record.get("validationReason") not in VALIDATION_REASONS)
            ):
                raise KnowledgeEgressDiagnosticJournalError("knowledge.egress_diagnostic_journal_invalid")
            terminal.add(ordinal)
        else:
            raise KnowledgeEgressDiagnosticJournalError("knowledge.egress_diagnostic_journal_invalid")
    return records


def diagnostic_result_from_records(records: tuple[dict[str, Any], ...]) -> dict[str, object]:
    header = records[0]
    started = tuple(record for record in records[1:] if record["event"] == "outbound_started")
    terminals = tuple(record for record in records[1:] if record["event"] == "call_terminal")
    status_counts = Counter(str(record["status"]) for record in terminals)
    reason_counts = Counter(
        str(record["validationReason"])
        for record in terminals
        if record["status"] == "quote_invalid"
    )
    complete = len(started) == AUTHORIZED_SUMMARY_CALLS and len(terminals) == AUTHORIZED_SUMMARY_CALLS
    return {
        "schemaVersion": 1,
        "workPackageId": "WP-K-EGRESS-DIAG-01",
        "gateId": "GATE-041",
        "runId": header["runId"],
        "authorizationReference": header["authorizationReference"],
        "manifestSha256": header["manifestSha256"],
        "recordedAt": _timestamp(),
        "status": "diagnostic_completed" if complete else "failed_incomplete",
        "diagnosticOnly": True,
        "authorizedSummaryCalls": AUTHORIZED_SUMMARY_CALLS,
        "actualSummaryCalls": len(started),
        "terminalRecordCount": len(terminals),
        "retryCount": 0,
        "statusCounts": dict(sorted(status_counts.items())),
        "validationReasonCounts": dict(sorted(reason_counts.items())),
        "dataBoundary": {
            "questionPersisted": False,
            "knowledgeContentPersisted": False,
            "quotePersisted": False,
            "rawModelResponsePersisted": False,
            "jwtPersisted": False,
            "businessCallCount": 0,
        },
        "closureClaimed": False,
    }


def validate_diagnostic_result(value: object) -> dict[str, Any]:
    if type(value) is not dict or set(value) != RESULT_KEYS:
        raise KnowledgeEgressDiagnosticJournalError("knowledge.egress_diagnostic_result_invalid")
    result: dict[str, Any] = value
    status_counts = result.get("statusCounts")
    reason_counts = result.get("validationReasonCounts")
    data_boundary = result.get("dataBoundary")
    if (
        result.get("schemaVersion") != 1
        or result.get("workPackageId") != "WP-K-EGRESS-DIAG-01"
        or result.get("gateId") != "GATE-041"
        or not _safe_id(result.get("runId"))
        or not _safe_id(result.get("authorizationReference"))
        or not isinstance(result.get("manifestSha256"), str)
        or SHA256.fullmatch(result["manifestSha256"]) is None
        or not isinstance(result.get("recordedAt"), str)
        or result.get("status") not in {"diagnostic_completed", "failed_incomplete"}
        or result.get("diagnosticOnly") is not True
        or result.get("authorizedSummaryCalls") != AUTHORIZED_SUMMARY_CALLS
        or type(result.get("actualSummaryCalls")) is not int
        or not 0 <= result["actualSummaryCalls"] <= AUTHORIZED_SUMMARY_CALLS
        or type(result.get("terminalRecordCount")) is not int
        or not 0 <= result["terminalRecordCount"] <= result["actualSummaryCalls"]
        or result.get("retryCount") != 0
        or type(status_counts) is not dict
        or any(status not in TERMINAL_STATUSES or type(count) is not int or count < 0 for status, count in status_counts.items())
        or sum(status_counts.values()) != result["terminalRecordCount"]
        or type(reason_counts) is not dict
        or any(reason not in VALIDATION_REASONS or type(count) is not int or count < 0 for reason, count in reason_counts.items())
        or sum(reason_counts.values()) != status_counts.get("quote_invalid", 0)
        or type(data_boundary) is not dict
        or set(data_boundary) != DATA_BOUNDARY_KEYS
        or any(data_boundary[key] is not False for key in DATA_BOUNDARY_KEYS - {"businessCallCount"})
        or data_boundary["businessCallCount"] != 0
        or result.get("closureClaimed") is not False
    ):
        raise KnowledgeEgressDiagnosticJournalError("knowledge.egress_diagnostic_result_invalid")
    if result["status"] == "diagnostic_completed" and (
        result["actualSummaryCalls"] != AUTHORIZED_SUMMARY_CALLS
        or result["terminalRecordCount"] != AUTHORIZED_SUMMARY_CALLS
    ):
        raise KnowledgeEgressDiagnosticJournalError("knowledge.egress_diagnostic_result_invalid")
    return result


def write_diagnostic_result_from_journal(*, journal_path: Path, output_path: Path) -> None:
    records = validate_diagnostic_journal(journal_path)
    value = validate_diagnostic_result(diagnostic_result_from_records(records))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


class KnowledgeEgressDiagnosticJournal:
    __slots__ = ("_path", "_run_id", "_started", "_terminal")

    def __init__(
        self,
        path: Path,
        *,
        run_id: str,
        authorization_reference: str,
        manifest_sha256: str,
    ) -> None:
        if (
            not _safe_id(run_id)
            or not _safe_id(authorization_reference)
            or SHA256.fullmatch(manifest_sha256) is None
        ):
            raise KnowledgeEgressDiagnosticJournalError("knowledge.egress_diagnostic_journal_invalid")
        self._path = path
        self._run_id = run_id
        self._started: dict[int, str] = {}
        self._terminal: set[int] = set()
        _write_line(
            path,
            {
                "schemaVersion": 1,
                "event": "attempt_started",
                "runId": run_id,
                "gateId": "GATE-041",
                "workPackageId": "WP-K-EGRESS-DIAG-01",
                "authorizationReference": authorization_reference,
                "manifestSha256": manifest_sha256,
                "authorizedSummaryCalls": AUTHORIZED_SUMMARY_CALLS,
                "retryAllowed": False,
                "diagnosticOnly": True,
                "recordedAt": _timestamp(),
            },
            exclusive=True,
        )

    def record_outbound_started(self, *, call_ordinal: int, case_id: str) -> None:
        if (
            not 1 <= call_ordinal <= AUTHORIZED_SUMMARY_CALLS
            or case_id != CASE_SEQUENCE[call_ordinal - 1]
            or call_ordinal != len(self._started) + 1
            or call_ordinal in self._started
        ):
            raise KnowledgeEgressDiagnosticJournalError("knowledge.egress_diagnostic_journal_invalid")
        _write_line(
            self._path,
            {
                "schemaVersion": 1,
                "event": "outbound_started",
                "runId": self._run_id,
                "callOrdinal": call_ordinal,
                "caseId": case_id,
                "recordedAt": _timestamp(),
            },
            exclusive=False,
        )
        self._started[call_ordinal] = case_id

    def record_terminal(
        self,
        *,
        call_ordinal: int,
        case_id: str,
        status: str,
        validation_reason: SummaryValidationFailureReason | None = None,
    ) -> None:
        if (
            self._started.get(call_ordinal) != case_id
            or call_ordinal in self._terminal
            or status not in TERMINAL_STATUSES
            or (status == "quote_invalid") != (validation_reason is not None)
        ):
            raise KnowledgeEgressDiagnosticJournalError("knowledge.egress_diagnostic_journal_invalid")
        value: dict[str, object] = {
            "schemaVersion": 1,
            "event": "call_terminal",
            "runId": self._run_id,
            "callOrdinal": call_ordinal,
            "caseId": case_id,
            "status": status,
            "recordedAt": _timestamp(),
        }
        if validation_reason is not None:
            value["validationReason"] = validation_reason.value
        _write_line(self._path, value, exclusive=False)
        self._terminal.add(call_ordinal)

    def is_terminal(self, call_ordinal: int) -> bool:
        return call_ordinal in self._terminal


def _main(arguments: list[str]) -> int:
    if len(arguments) != 2:
        return 2
    try:
        journal_path = Path(arguments[0])
        result_path = Path(arguments[1])
        records = validate_diagnostic_journal(journal_path)
        result = validate_diagnostic_result(json.loads(result_path.read_text(encoding="utf-8")))
        expected = diagnostic_result_from_records(records)
        for key in (
            "runId",
            "authorizationReference",
            "manifestSha256",
            "status",
            "actualSummaryCalls",
            "terminalRecordCount",
            "statusCounts",
            "validationReasonCounts",
        ):
            if result[key] != expected[key]:
                return 2
    except (KnowledgeEgressDiagnosticJournalError, OSError, json.JSONDecodeError):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
