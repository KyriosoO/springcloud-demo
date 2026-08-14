from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from agent_runtime.capability_api.contracts import (
    CapabilityResult,
    CapabilityStatus,
    EgressDisposition,
    JsonValue,
    ModelEgressResult,
)
from tests.integration.adapters.employee.egress_input_qualification_v2 import (
    AUTHORIZATION_REFERENCE,
    EMPLOYEE_EGRESS_HISTORY,
    GATE_ID,
    RETIRED_RUN_ID,
    RUN_ID,
    QualificationFailurePhase,
    QualificationLifecycleJournalV2,
    QualificationReason,
    QualificationRunStatus,
    QualificationV2Error,
    build_result,
    load_strict_json,
    sha256_file,
    validate_authorization,
    validate_lifecycle,
    validate_manifest,
    validate_result,
)


_MANIFEST_SHA = "a" * 64
_FROZEN_PREPARATION_COMMIT = "7eef0e2cd533aa071e89cdcb78c747d8c4722a30"
_CONSUMED_LIFECYCLE_SHA256 = (
    "570295951f8bf1a109156c017c30609ca548bfba3f021bff4cd2825f978ac231"
)
_CONSUMED_RESULT_SHA256 = (
    "7534b1d04a1512720dcbee1fe630114fb1f08bf9c3615dec1d2cb18bec4d5054"
)


def _success(*, position: str | None = "synthetic-position") -> CapabilityResult:
    fields: dict[str, JsonValue] = {
        "employee_id_masked": "********0000",
        "chinese_name": "synthetic-name",
        "work_base_si": "synthetic-work-base",
    }
    if position is not None:
        fields["position"] = position
    allowed = position is not None
    return CapabilityResult(
        status=CapabilityStatus.SUCCESS,
        domain_result={
            "schema_version": 1,
            "capability_id": "employee.detail",
            "records": ({"record_ref": "record-0001", "fields": fields},),
            "coverage": {"returned_count": 1, "truncated": False, "total_count": 1},
        },
        egress=ModelEgressResult(
            disposition=EgressDisposition.ALLOWED if allowed else EgressDisposition.DENIED,
            policy_version="business-egress-v1",
            safe_payload={"facts": ()} if allowed else None,
            reason_code=None if allowed else "business.no_model_fields",
        ),
        failure=None,
    )


def _journal(tmp_path: Path) -> QualificationLifecycleJournalV2:
    return QualificationLifecycleJournalV2(
        tmp_path / f"{RUN_ID}.lifecycle.jsonl",
        manifest_sha256=_MANIFEST_SHA,
    )


def _complete_success(journal: QualificationLifecycleJournalV2) -> None:
    journal.record_database_selection_started()
    journal.record_database_selection_terminal(status="completed", selected_rows=1)
    journal.record_employee_detail_started()
    journal.record_employee_detail_terminal(status="completed")
    journal.record_run_terminal(
        status=QualificationRunStatus.QUALIFIED,
        failure_phase=None,
        failure_reason=None,
    )


def test_lifecycle_is_exclusive_and_fsynced_before_database_selection(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    snapshot = validate_lifecycle(journal.path, manifest_sha256=_MANIFEST_SHA)

    assert snapshot.record_count == 1
    assert snapshot.database_selection_started == 0
    assert snapshot.employee_detail_started == 0
    with pytest.raises(FileExistsError):
        _journal(tmp_path)


def test_qualified_result_contains_only_presence_counts_and_hashes(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    _complete_success(journal)

    result = build_result(
        lifecycle_path=journal.path,
        manifest_sha256=_MANIFEST_SHA,
        result=_success(),
        raw_logs_deleted=True,
        log_leak_count=0,
    )

    assert result["status"] == "qualified"
    assert result["codecMinimumFieldPresence"] == {
        "idCardNo": True,
        "chineseName": True,
        "position": True,
        "workBaseSi": True,
    }
    assert result["requiredUserResultFieldPresence"] == {
        "employeeIdMasked": True,
        "chineseName": True,
    }
    assert result["counts"] == {
        "databaseSelectionStarted": 1,
        "databaseSelectionTerminal": 1,
        "databaseSelectionRows": 1,
        "employeeDetailStarted": 1,
        "employeeDetailTerminal": 1,
        "otherEmployeeEndpoints": 0,
        "modelCalls": 0,
        "retryCount": 0,
        "resumeCount": 0,
    }
    encoded = json.dumps(result, ensure_ascii=False)
    assert "synthetic-position" not in encoded
    assert "synthetic-name" not in encoded
    assert "synthetic-work-base" not in encoded


@pytest.mark.parametrize(
    ("phase", "reason", "prepare", "expected_counts"),
    [
        (
            QualificationFailurePhase.DATABASE_SELECTION,
            QualificationReason.DATABASE_SELECTION_FAILED,
            lambda journal: journal.record_database_selection_started(),
            (1, 0, 0, 0, 0),
        ),
        (
            QualificationFailurePhase.DATABASE_SELECTION,
            QualificationReason.NO_QUALIFIED_INPUT,
            lambda journal: (
                journal.record_database_selection_started(),
                journal.record_database_selection_terminal(status="completed", selected_rows=0),
            ),
            (1, 1, 0, 0, 0),
        ),
        (
            QualificationFailurePhase.EMPLOYEE_DETAIL,
            QualificationReason.EMPLOYEE_REQUEST_FAILED,
            lambda journal: (
                journal.record_database_selection_started(),
                journal.record_database_selection_terminal(status="completed", selected_rows=1),
                journal.record_employee_detail_started(),
                journal.record_employee_detail_terminal(status="failed"),
            ),
            (1, 1, 1, 1, 1),
        ),
    ],
)
def test_each_prepared_failure_window_has_finite_terminal_counts(
    tmp_path: Path,
    phase: QualificationFailurePhase,
    reason: QualificationReason,
    prepare: Callable[[QualificationLifecycleJournalV2], object],
    expected_counts: tuple[int, int, int, int, int],
) -> None:
    journal = _journal(tmp_path)
    prepare(journal)
    status = (
        QualificationRunStatus.NOT_QUALIFIED
        if reason is QualificationReason.NO_QUALIFIED_INPUT
        else QualificationRunStatus.FAILED
    )
    journal.record_run_terminal(status=status, failure_phase=phase, failure_reason=reason)
    snapshot = validate_lifecycle(journal.path, manifest_sha256=_MANIFEST_SHA)

    assert (
        snapshot.database_selection_started,
        snapshot.database_selection_terminal,
        snapshot.database_selection_rows,
        snapshot.employee_detail_started,
        snapshot.employee_detail_terminal,
    ) == expected_counts
    assert snapshot.run_status is status


def test_detail_cannot_start_before_one_selected_row_or_run_twice(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    with pytest.raises(QualificationV2Error):
        journal.record_employee_detail_started()
    journal.record_database_selection_started()
    journal.record_database_selection_terminal(status="completed", selected_rows=1)
    journal.record_employee_detail_started()
    with pytest.raises(QualificationV2Error):
        journal.record_employee_detail_started()


def _set_model_call(value: dict[str, Any]) -> None:
    cast(dict[str, Any], value["counts"])["modelCalls"] = 1


def _set_identifier_persisted(value: dict[str, Any]) -> None:
    cast(dict[str, Any], value["safety"])["identifierPersisted"] = True


def _add_extra(value: dict[str, Any]) -> None:
    value["extra"] = "forbidden"


@pytest.mark.parametrize("mutate", [_set_model_call, _set_identifier_persisted, _add_extra])
def test_result_validator_is_strict_and_fail_closed(
    tmp_path: Path,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    journal = _journal(tmp_path)
    _complete_success(journal)
    result = build_result(
        lifecycle_path=journal.path,
        manifest_sha256=_MANIFEST_SHA,
        result=_success(),
        raw_logs_deleted=True,
        log_leak_count=0,
    )
    copied = cast(dict[str, Any], json.loads(json.dumps(result)))
    mutate(copied)

    with pytest.raises(QualificationV2Error):
        validate_result(copied)


def test_result_validator_rejects_mismatched_failure_reason(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    journal.record_database_selection_started()
    journal.record_database_selection_terminal(status="completed", selected_rows=0)
    journal.record_run_terminal(
        status=QualificationRunStatus.NOT_QUALIFIED,
        failure_phase=QualificationFailurePhase.DATABASE_SELECTION,
        failure_reason=QualificationReason.NO_QUALIFIED_INPUT,
    )
    result = build_result(
        lifecycle_path=journal.path,
        manifest_sha256=_MANIFEST_SHA,
        result=None,
        raw_logs_deleted=True,
        log_leak_count=0,
    )
    result["egressReason"] = QualificationReason.EMPLOYEE_REQUEST_FAILED.value

    with pytest.raises(QualificationV2Error):
        validate_result(result)


def test_schemas_are_strict_and_zero_model() -> None:
    evidence = Path(__file__).parent / "evidence"
    lifecycle_schema = json.loads(
        (evidence / "employee-egress-input-qualification-v2-lifecycle.schema.json").read_text(
            encoding="utf-8"
        )
    )
    result_schema = json.loads(
        (evidence / "employee-egress-input-qualification-v2-result.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert lifecycle_schema["additionalProperties"] is False
    assert result_schema["additionalProperties"] is False
    assert result_schema["properties"]["counts"]["properties"]["modelCalls"] == {"const": 0}
    assert result_schema["properties"]["safety"]["properties"]["llmApiKeyRead"] == {
        "const": False
    }
    assert result_schema["properties"]["safety"]["properties"]["logScanCompleted"] == {
        "type": "boolean"
    }


def test_frozen_manifest_authorization_history_and_consumed_outputs(tmp_path: Path) -> None:
    repository = Path(__file__).parents[5]
    evidence = Path(__file__).parent / "evidence"
    manifest_path = evidence / f"{RUN_ID}.manifest.json"
    authorization_path = evidence / f"{RUN_ID}.authorization.json"
    manifest_sha = sha256_file(manifest_path)
    manifest_value = load_strict_json(manifest_path)
    assert type(manifest_value) is dict

    prepared_repository = tmp_path / "prepared-repository"
    asset_groups = (
        cast(dict[str, Any], manifest_value["retiredQualificationRun"])["assetHashes"],
        manifest_value["employeeEgressHistory"],
        manifest_value["assetHashes"],
    )
    for group in asset_groups:
        assert type(group) is list
        for untyped_asset in group:
            asset = cast(dict[str, Any], untyped_asset)
            relative_path = cast(str, asset["path"])
            target = prepared_repository / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            if relative_path == (
                "agent-runtime/tests/integration/adapters/employee/"
                "test_employee_egress_input_qualification_v2.py"
            ):
                frozen = subprocess.run(
                    ["git", "show", f"{_FROZEN_PREPARATION_COMMIT}:{relative_path}"],
                    cwd=repository,
                    check=True,
                    capture_output=True,
                ).stdout
                target.write_bytes(frozen)
            else:
                target.write_bytes((repository / relative_path).read_bytes())

    manifest = validate_manifest(manifest_value, repository_root=prepared_repository)
    authorization = validate_authorization(
        load_strict_json(authorization_path), manifest_sha256=manifest_sha
    )
    assert manifest["retiredQualificationRun"]["runId"] == RETIRED_RUN_ID
    assert len(manifest["employeeEgressHistory"]) == 8
    assert authorization["liveExecutionAuthorized"] is False
    for _, path, digest in EMPLOYEE_EGRESS_HISTORY:
        assert sha256_file(repository / path) == digest
    lifecycle_path = evidence / f"{RUN_ID}.lifecycle.jsonl"
    result_path = evidence / f"{RUN_ID}.result.json"
    assert sha256_file(lifecycle_path) == _CONSUMED_LIFECYCLE_SHA256
    assert sha256_file(result_path) == _CONSUMED_RESULT_SHA256
    lifecycle = validate_lifecycle(lifecycle_path, manifest_sha256=manifest_sha)
    assert lifecycle.run_status is QualificationRunStatus.NOT_QUALIFIED
    assert lifecycle.failure_reason is QualificationReason.NO_QUALIFIED_INPUT
    validate_result(load_strict_json(result_path))


def test_launcher_requires_new_live_authorization_before_any_external_process() -> None:
    repository = Path(__file__).parents[5]
    launcher = (
        repository / "agent-runtime/scripts/run-employee-egress-input-qualification-candidate-02.ps1"
    ).read_text(encoding="utf-8")

    assert RUN_ID in launcher
    assert AUTHORIZATION_REFERENCE in launcher
    assert GATE_ID in launcher
    authorization_guard = launcher.index(
        "employee.egress_input_qualification_v2_live_not_authorized"
    )
    external_process = launcher.index("Start-Process")
    assert authorization_guard < external_process
    assert "GetEnvironmentVariable('LLM_API_KEY'" not in launcher
    assert "Remove-Item Env:\\LLM_API_KEY -ErrorAction SilentlyContinue" in launcher
    assert "employee.egress_input_qualification_v2_live_not_authorized" in launcher
    assert "employee.egress_input_qualification_v2_not_qualified" in launcher


def test_java_candidate_source_covers_codec_and_required_user_minimums() -> None:
    repository = Path(__file__).parents[5]
    source = (
        repository
        / "employee-service/src/test/java/com/dylan/employee/live/"
        "EmployeeEgressInputQualificationV2LiveIntegrationTest.java"
    ).read_text(encoding="utf-8")

    for token in (
        "ID_CARD_NO",
        "CHINESE_NAME",
        "POSITION",
        "WORK_BASE_SI",
        "CHAR_LENGTH(ID_CARD_NO) BETWEEN 5 AND 64",
        "OCTET_LENGTH(ID_CARD_NO) <= 192",
        "CHAR_LENGTH(CHINESE_NAME) BETWEEN 1 AND 128",
        "CHAR_LENGTH(POSITION) BETWEEN 1 AND 256",
        "CHAR_LENGTH(WORK_BASE_SI) BETWEEN 1 AND 256",
        "ID_CARD_NO NOT REGEXP '[[:cntrl:]]'",
        "CHINESE_NAME NOT REGEXP '[[:cntrl:]]'",
        "POSITION NOT REGEXP '[[:cntrl:]]'",
        "WORK_BASE_SI NOT REGEXP '[[:cntrl:]]'",
        "HEX(ID_CARD_NO) NOT REGEXP",
        "HEX(CHINESE_NAME) NOT REGEXP",
        "HEX(POSITION) NOT REGEXP",
        "HEX(WORK_BASE_SI) NOT REGEXP",
        "E280AA|E280AB|E280AC|E280AD|E280AE|E281A6|E281A7|E281A8|E281A9",
        "LIMIT 1",
    ):
        assert token in source
    assert source.index("createLifecycleJournal") < source.index("jdbcTemplate.query")
    assert source.count("writeLimitedFailureResult(") >= 4
    assert "LLM_API_KEY" not in source
