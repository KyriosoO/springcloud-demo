from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_runtime.knowledge.evidence.summary_validation import SummaryValidationFailureReason
from tests.integration.knowledge.egress_diagnostic_journal import (
    AUTHORIZED_SUMMARY_CALLS,
    CASE_SEQUENCE,
    KnowledgeEgressDiagnosticJournal,
    KnowledgeEgressDiagnosticJournalError,
    diagnostic_result_from_records,
    validate_diagnostic_journal,
    validate_diagnostic_result,
    write_diagnostic_result_from_journal,
)


def _journal(path: Path) -> KnowledgeEgressDiagnosticJournal:
    return KnowledgeEgressDiagnosticJournal(
        path,
        run_id="knowledge-egress-diagnostic-v1-20260812-candidate-01",
        authorization_reference="P3_00:GATE-041",
        manifest_sha256="a" * 64,
    )


def test_complete_journal_records_only_finite_reasons_and_counts(tmp_path: Path) -> None:
    path = tmp_path / "attempt.jsonl"
    journal = _journal(path)
    for ordinal, case_id in enumerate(CASE_SEQUENCE, 1):
        journal.record_outbound_started(call_ordinal=ordinal, case_id=case_id)
        if ordinal % 2:
            journal.record_terminal(
                call_ordinal=ordinal,
                case_id=case_id,
                status="quote_invalid",
                validation_reason=SummaryValidationFailureReason.QUOTE_NOT_SUBSTRING,
            )
        else:
            journal.record_terminal(call_ordinal=ordinal, case_id=case_id, status="success")

    records = validate_diagnostic_journal(path)
    result = diagnostic_result_from_records(records)

    assert result["status"] == "diagnostic_completed"
    assert result["actualSummaryCalls"] == AUTHORIZED_SUMMARY_CALLS
    assert result["terminalRecordCount"] == AUTHORIZED_SUMMARY_CALLS
    assert result["statusCounts"] == {"quote_invalid": 5, "success": 4}
    assert result["validationReasonCounts"] == {"quote_not_substring": 5}
    assert validate_diagnostic_result(result) == result
    serialized = json.dumps(result, sort_keys=True)
    for forbidden in ("secret-sentinel", "税务政策正文", '"quote":', '"question":', '"jwt":', '"rawModelResponse":'):
        assert forbidden not in serialized


def test_quote_invalid_requires_reason_and_other_status_rejects_reason(tmp_path: Path) -> None:
    first = tmp_path / "missing.jsonl"
    missing = _journal(first)
    missing.record_outbound_started(call_ordinal=1, case_id=CASE_SEQUENCE[0])
    with pytest.raises(KnowledgeEgressDiagnosticJournalError, match="diagnostic_journal_invalid"):
        missing.record_terminal(call_ordinal=1, case_id=CASE_SEQUENCE[0], status="quote_invalid")

    second = tmp_path / "unexpected.jsonl"
    unexpected = _journal(second)
    unexpected.record_outbound_started(call_ordinal=1, case_id=CASE_SEQUENCE[0])
    with pytest.raises(KnowledgeEgressDiagnosticJournalError, match="diagnostic_journal_invalid"):
        unexpected.record_terminal(
            call_ordinal=1,
            case_id=CASE_SEQUENCE[0],
            status="success",
            validation_reason=SummaryValidationFailureReason.QUOTE_EMPTY,
        )


def test_validator_rejects_unknown_reason_and_out_of_order_case(tmp_path: Path) -> None:
    path = tmp_path / "attempt.jsonl"
    journal = _journal(path)
    journal.record_outbound_started(call_ordinal=1, case_id=CASE_SEQUENCE[0])
    journal.record_terminal(
        call_ordinal=1,
        case_id=CASE_SEQUENCE[0],
        status="quote_invalid",
        validation_reason=SummaryValidationFailureReason.QUOTE_EMPTY,
    )
    records = path.read_text(encoding="utf-8").splitlines()
    terminal = json.loads(records[-1])
    terminal["validationReason"] = "raw_quote_mismatch:secret"
    records[-1] = json.dumps(terminal, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(records) + "\n", encoding="utf-8")
    with pytest.raises(KnowledgeEgressDiagnosticJournalError, match="diagnostic_journal_invalid"):
        validate_diagnostic_journal(path)

    other = tmp_path / "order.jsonl"
    out_of_order = _journal(other)
    with pytest.raises(KnowledgeEgressDiagnosticJournalError, match="diagnostic_journal_invalid"):
        out_of_order.record_outbound_started(call_ordinal=1, case_id=CASE_SEQUENCE[1])


def test_incomplete_journal_writes_fail_closed_safe_result(tmp_path: Path) -> None:
    journal_path = tmp_path / "attempt.jsonl"
    output_path = tmp_path / "result.json"
    journal = _journal(journal_path)
    journal.record_outbound_started(call_ordinal=1, case_id=CASE_SEQUENCE[0])
    journal.record_terminal(call_ordinal=1, case_id=CASE_SEQUENCE[0], status="timeout")

    write_diagnostic_result_from_journal(journal_path=journal_path, output_path=output_path)
    result = json.loads(output_path.read_text(encoding="utf-8"))

    assert result["status"] == "failed_incomplete"
    assert result["actualSummaryCalls"] == 1
    assert result["terminalRecordCount"] == 1
    assert result["closureClaimed"] is False


def test_result_validator_rejects_closure_claim_or_reason_count_drift(tmp_path: Path) -> None:
    path = tmp_path / "attempt.jsonl"
    journal = _journal(path)
    journal.record_outbound_started(call_ordinal=1, case_id=CASE_SEQUENCE[0])
    journal.record_terminal(
        call_ordinal=1,
        case_id=CASE_SEQUENCE[0],
        status="quote_invalid",
        validation_reason=SummaryValidationFailureReason.QUOTE_EMPTY,
    )
    result = diagnostic_result_from_records(validate_diagnostic_journal(path))
    result["closureClaimed"] = True
    with pytest.raises(KnowledgeEgressDiagnosticJournalError, match="diagnostic_result_invalid"):
        validate_diagnostic_result(result)
    result["closureClaimed"] = False
    result["validationReasonCounts"] = {}
    with pytest.raises(KnowledgeEgressDiagnosticJournalError, match="diagnostic_result_invalid"):
        validate_diagnostic_result(result)
