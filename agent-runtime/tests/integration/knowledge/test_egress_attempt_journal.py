from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.integration.knowledge.egress_attempt_journal import (
    KnowledgeEgressAttemptJournal,
    KnowledgeEgressAttemptJournalError,
    validate_attempt_journal,
    write_failure_attempt_from_journal,
)


CASE_IDS = ("tax-policy", "tax-law", "tax-mixed")
CASE_SEQUENCE = tuple(case_id for _ in range(10) for case_id in CASE_IDS)


@pytest.mark.parametrize("failure_ordinal", (1, 10, 30))
def test_failure_at_each_call_retains_exact_safe_journal(tmp_path: Path, failure_ordinal: int) -> None:
    path = tmp_path / "attempt.jsonl"
    journal = KnowledgeEgressAttemptJournal(
        path,
        run_id="knowledge-egress-v1-test",
        authorization_reference="P3_00:GATE-040",
    )
    for ordinal, case_id in enumerate(CASE_SEQUENCE[:failure_ordinal], 1):
        journal.record_outbound_started(call_ordinal=ordinal, case_id=case_id)
        journal.record_terminal(
            call_ordinal=ordinal,
            case_id=case_id,
            status="http_failure" if ordinal == failure_ordinal else "success",
        )

    records = validate_attempt_journal(path)

    assert [record["event"] for record in records] == [
        "attempt_started",
        *(event for _ in range(failure_ordinal) for event in ("outbound_started", "call_terminal")),
    ]
    terminals = [record for record in records if record["event"] == "call_terminal"]
    assert terminals[-1]["callOrdinal"] == failure_ordinal
    assert terminals[-1]["status"] == "http_failure"
    raw = path.read_text(encoding="utf-8")
    assert all(forbidden not in raw for forbidden in ("question", "content", "jwt", "payload", "11010519491231002X"))


def test_interruption_after_outbound_start_is_valid_and_preserved(tmp_path: Path) -> None:
    path = tmp_path / "attempt.jsonl"
    journal = KnowledgeEgressAttemptJournal(
        path,
        run_id="knowledge-egress-v1-interrupted",
        authorization_reference="P3_00:GATE-040",
    )
    journal.record_outbound_started(call_ordinal=1, case_id="tax-policy")

    records = validate_attempt_journal(path)

    assert len(records) == 2
    assert records[-1]["event"] == "outbound_started"

    output = tmp_path / "failure-attempt.json"
    write_failure_attempt_from_journal(journal_path=path, output_path=output)
    value = json.loads(output.read_text(encoding="utf-8"))
    assert value == {
        "schemaVersion": 1,
        "workPackageId": "WP-K-EGRESS-01",
        "gateId": "GATE-022",
        "runId": "knowledge-egress-v1-interrupted",
        "recordedAt": value["recordedAt"],
        "authorizationReference": "P3_00:GATE-040",
        "status": "failed_incomplete",
        "actualSummaryCalls": 1,
        "retryCount": 0,
        "terminalRecordCount": 0,
        "incompleteCallCount": 1,
        "caseResults": [
            {"callOrdinal": 1, "caseId": "tax-policy", "status": "started_without_terminal"}
        ],
    }
    assert all(forbidden not in output.read_text(encoding="utf-8") for forbidden in ("question", "content", "jwt"))


@pytest.mark.parametrize(
    "operation",
    (
        lambda journal: journal.record_outbound_started(call_ordinal=2, case_id="tax-law"),
        lambda journal: journal.record_outbound_started(call_ordinal=31, case_id="tax-policy"),
        lambda journal: journal.record_terminal(call_ordinal=1, case_id="tax-policy", status="provider body"),
    ),
)
def test_journal_rejects_out_of_order_or_unbounded_values(
    tmp_path: Path,
    operation: object,
) -> None:
    path = tmp_path / "attempt.jsonl"
    journal = KnowledgeEgressAttemptJournal(
        path,
        run_id="knowledge-egress-v1-invalid",
        authorization_reference="P3_00:GATE-040",
    )

    with pytest.raises(KnowledgeEgressAttemptJournalError):
        operation(journal)  # type: ignore[operator]


def test_validator_rejects_unknown_fields(tmp_path: Path) -> None:
    path = tmp_path / "attempt.jsonl"
    journal = KnowledgeEgressAttemptJournal(
        path,
        run_id="knowledge-egress-v1-tamper",
        authorization_reference="P3_00:GATE-040",
    )
    journal.record_outbound_started(call_ordinal=1, case_id="tax-policy")
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    records[-1]["rawResponse"] = "secret"
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")

    with pytest.raises(KnowledgeEgressAttemptJournalError):
        validate_attempt_journal(path)
