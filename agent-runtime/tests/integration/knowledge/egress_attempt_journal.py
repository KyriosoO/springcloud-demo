from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final


_SAFE_ID: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
_CASE_IDS: Final = ("tax-policy", "tax-law", "tax-mixed")
_REPEAT_COUNT: Final = 10
_AUTHORIZED_SUMMARY_CALLS: Final = len(_CASE_IDS) * _REPEAT_COUNT
_CASE_SEQUENCE: Final = tuple(case_id for _ in range(_REPEAT_COUNT) for case_id in _CASE_IDS)
_TERMINAL_STATUSES: Final = frozenset(
    {
        "success",
        "http_failure",
        "timeout",
        "schema_invalid",
        "insufficient_evidence",
        "quote_invalid",
    }
)
_HEADER_KEYS: Final = {
    "schemaVersion",
    "event",
    "runId",
    "gateId",
    "workPackageId",
    "authorizationReference",
    "authorizedSummaryCalls",
    "retryAllowed",
    "recordedAt",
}
_CALL_KEYS: Final = {
    "schemaVersion",
    "event",
    "runId",
    "callOrdinal",
    "caseId",
    "recordedAt",
}
_TERMINAL_KEYS: Final = _CALL_KEYS | {"status"}


class KnowledgeEgressAttemptJournalError(ValueError):
    pass


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _safe_id(value: object) -> bool:
    return isinstance(value, str) and _SAFE_ID.fullmatch(value) is not None


def _write_line(path: Path, value: dict[str, object], *, exclusive: bool) -> None:
    mode = "x" if exclusive else "a"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open(mode, encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def validate_attempt_journal(path: Path) -> tuple[dict[str, Any], ...]:
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise KnowledgeEgressAttemptJournalError("knowledge.egress_journal_invalid") from exc
    if not raw_lines or any(not line or len(line.encode("utf-8")) > 2048 for line in raw_lines):
        raise KnowledgeEgressAttemptJournalError("knowledge.egress_journal_invalid")
    try:
        records = tuple(json.loads(line) for line in raw_lines)
    except json.JSONDecodeError as exc:
        raise KnowledgeEgressAttemptJournalError("knowledge.egress_journal_invalid") from exc
    if any(type(record) is not dict for record in records):
        raise KnowledgeEgressAttemptJournalError("knowledge.egress_journal_invalid")

    header = records[0]
    if (
        set(header) != _HEADER_KEYS
        or header["schemaVersion"] != 1
        or header["event"] != "attempt_started"
        or not _safe_id(header["runId"])
        or header["gateId"] != "GATE-022"
        or header["workPackageId"] != "WP-K-EGRESS-01"
        or not _safe_id(header["authorizationReference"])
        or header["authorizedSummaryCalls"] != _AUTHORIZED_SUMMARY_CALLS
        or header["retryAllowed"] is not False
        or not isinstance(header["recordedAt"], str)
    ):
        raise KnowledgeEgressAttemptJournalError("knowledge.egress_journal_invalid")

    run_id = header["runId"]
    started: dict[int, str] = {}
    terminal: set[int] = set()
    for record in records[1:]:
        event = record.get("event")
        expected_keys = _CALL_KEYS if event == "outbound_started" else _TERMINAL_KEYS
        if (
            set(record) != expected_keys
            or record.get("schemaVersion") != 1
            or record.get("runId") != run_id
            or type(record.get("callOrdinal")) is not int
            or not 1 <= record["callOrdinal"] <= _AUTHORIZED_SUMMARY_CALLS
            or record.get("caseId") not in _CASE_IDS
            or not isinstance(record.get("recordedAt"), str)
        ):
            raise KnowledgeEgressAttemptJournalError("knowledge.egress_journal_invalid")
        ordinal = record["callOrdinal"]
        case_id = record["caseId"]
        if event == "outbound_started":
            if ordinal in started or ordinal != len(started) + 1 or case_id != _CASE_SEQUENCE[ordinal - 1]:
                raise KnowledgeEgressAttemptJournalError("knowledge.egress_journal_invalid")
            started[ordinal] = case_id
        elif event == "call_terminal":
            if (
                ordinal not in started
                or ordinal in terminal
                or started[ordinal] != case_id
                or record.get("status") not in _TERMINAL_STATUSES
            ):
                raise KnowledgeEgressAttemptJournalError("knowledge.egress_journal_invalid")
            terminal.add(ordinal)
        else:
            raise KnowledgeEgressAttemptJournalError("knowledge.egress_journal_invalid")
    return records


def write_failure_attempt_from_journal(*, journal_path: Path, output_path: Path) -> None:
    records = validate_attempt_journal(journal_path)
    header = records[0]
    terminals = {
        record["callOrdinal"]: record["status"]
        for record in records[1:]
        if record["event"] == "call_terminal"
    }
    started = [record for record in records[1:] if record["event"] == "outbound_started"]
    value = {
        "schemaVersion": 1,
        "workPackageId": "WP-K-EGRESS-01",
        "gateId": "GATE-022",
        "runId": header["runId"],
        "recordedAt": _timestamp(),
        "authorizationReference": header["authorizationReference"],
        "status": "failed_incomplete",
        "actualSummaryCalls": len(started),
        "retryCount": 0,
        "terminalRecordCount": len(terminals),
        "incompleteCallCount": len(started) - len(terminals),
        "caseResults": [
            {
                "callOrdinal": record["callOrdinal"],
                "caseId": record["caseId"],
                "status": terminals.get(record["callOrdinal"], "started_without_terminal"),
            }
            for record in started
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def _main(arguments: list[str]) -> int:
    if len(arguments) != 2:
        return 2
    try:
        write_failure_attempt_from_journal(
            journal_path=Path(arguments[0]),
            output_path=Path(arguments[1]),
        )
    except (KnowledgeEgressAttemptJournalError, OSError):
        return 2
    return 0


class KnowledgeEgressAttemptJournal:
    __slots__ = ("_path", "_run_id", "_started", "_terminal")

    def __init__(
        self,
        path: Path,
        *,
        run_id: str,
        authorization_reference: str,
    ) -> None:
        if not _safe_id(run_id) or not _safe_id(authorization_reference):
            raise KnowledgeEgressAttemptJournalError("knowledge.egress_journal_invalid")
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
                "gateId": "GATE-022",
                "workPackageId": "WP-K-EGRESS-01",
                "authorizationReference": authorization_reference,
                "authorizedSummaryCalls": _AUTHORIZED_SUMMARY_CALLS,
                "retryAllowed": False,
                "recordedAt": _timestamp(),
            },
            exclusive=True,
        )

    def record_outbound_started(self, *, call_ordinal: int, case_id: str) -> None:
        if (
            not 1 <= call_ordinal <= _AUTHORIZED_SUMMARY_CALLS
            or case_id != _CASE_SEQUENCE[call_ordinal - 1]
            or call_ordinal != len(self._started) + 1
            or call_ordinal in self._started
        ):
            raise KnowledgeEgressAttemptJournalError("knowledge.egress_journal_invalid")
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

    def record_terminal(self, *, call_ordinal: int, case_id: str, status: str) -> None:
        if (
            self._started.get(call_ordinal) != case_id
            or call_ordinal in self._terminal
            or status not in _TERMINAL_STATUSES
        ):
            raise KnowledgeEgressAttemptJournalError("knowledge.egress_journal_invalid")
        _write_line(
            self._path,
            {
                "schemaVersion": 1,
                "event": "call_terminal",
                "runId": self._run_id,
                "callOrdinal": call_ordinal,
                "caseId": case_id,
                "status": status,
                "recordedAt": _timestamp(),
            },
            exclusive=False,
        )
        self._terminal.add(call_ordinal)

    def is_terminal(self, call_ordinal: int) -> bool:
        return call_ordinal in self._terminal


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
