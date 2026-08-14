from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.integration.adapters.employee.fixture_metadata_diagnostic_v2 import (
    AUTHORIZATION_REFERENCE,
    MAX_QUERIES,
    QUERY_PHASES,
    RUN_01_FAILURE_EVIDENCE_PATH,
    RUN_01_FAILURE_EVIDENCE_SHA256,
    RUN_01_FAILURE_SCHEMA_PATH,
    RUN_01_FAILURE_SCHEMA_SHA256,
    SOURCE_EVIDENCE_PATH,
    SOURCE_EVIDENCE_SHA256,
    execute_fake_candidate,
    load_strict_json,
    sha256_file,
    validate_lifecycle,
    validate_manifest,
    validate_result,
    verify_history,
)


REPOSITORY = Path(__file__).resolve().parents[5]
JAVA_PROBE = REPOSITORY / (
    "employee-service/src/test/java/com/dylan/employee/live/"
    "EmployeeFixtureMetadataDiagnosticV2LiveIntegrationTest.java"
)
LAUNCHER = Path(__file__).with_name("run_employee_fixture_metadata_diagnostic_v2.ps1")
EVIDENCE = Path(__file__).with_name("evidence")


def _success() -> object:
    return object()


def _failure() -> object:
    raise RuntimeError("synthetic-stage-failure")


def test_history_bindings_are_exact_and_immutable() -> None:
    verify_history(REPOSITORY)
    expected = {
        SOURCE_EVIDENCE_PATH: SOURCE_EVIDENCE_SHA256,
        RUN_01_FAILURE_EVIDENCE_PATH: RUN_01_FAILURE_EVIDENCE_SHA256,
        RUN_01_FAILURE_SCHEMA_PATH: RUN_01_FAILURE_SCHEMA_SHA256,
    }
    for path, digest in expected.items():
        assert sha256_file(REPOSITORY / path) == digest


def test_lifecycle_is_exclusive_and_exists_before_first_query(tmp_path: Path) -> None:
    lifecycle = tmp_path / "lifecycle.jsonl"
    result = tmp_path / "result.json"
    observations: list[bool] = []

    def observe() -> object:
        observations.append(lifecycle.is_file() and lifecycle.stat().st_size > 0)
        return object()

    execute_fake_candidate(lifecycle, result, [observe, _success, _success, _success])
    records = validate_lifecycle(lifecycle)
    assert observations == [True]
    assert len(records) == 10
    assert [record["phase"] for record in records[1:-1:2]] == list(QUERY_PHASES)
    validate_result(load_strict_json(result))
    with pytest.raises(FileExistsError):
        execute_fake_candidate(lifecycle, tmp_path / "second.json", [_success] * 4)


@pytest.mark.parametrize("failed_ordinal", range(1, MAX_QUERIES + 1))
def test_each_query_failure_stops_immediately_with_finite_result(
    tmp_path: Path, failed_ordinal: int
) -> None:
    lifecycle = tmp_path / f"lifecycle-{failed_ordinal}.jsonl"
    result_path = tmp_path / f"result-{failed_ordinal}.json"
    calls: list[int] = []
    operations: list[Callable[[], object]] = []
    for ordinal in range(1, MAX_QUERIES + 1):
        if ordinal == failed_ordinal:
            operations.append(_failure)
        else:
            def record_call(current: int = ordinal) -> object:
                calls.append(current)
                return object()

            operations.append(record_call)
    execute_fake_candidate(lifecycle, result_path, operations)
    records = validate_lifecycle(lifecycle)
    result = load_strict_json(result_path)
    validate_result(result)
    assert result["status"] == "failed"
    assert result["failure"] == {
        "phase": QUERY_PHASES[failed_ordinal - 1],
        "queryOrdinal": failed_ordinal,
        "reason": "information_schema_query_failed",
        "sqlState": None,
        "vendorCode": None,
    }
    assert result["queryCounts"] == {
        "maximum": 4,
        "started": failed_ordinal,
        "terminal": failed_ordinal,
        "succeeded": failed_ordinal - 1,
        "failed": 1,
        "retryCount": 0,
        "resumeCount": 0,
    }
    assert len(records) == 2 + failed_ordinal * 2
    assert calls == list(range(1, failed_ordinal))


def test_strict_result_rejects_extra_sensitive_and_retry_fields(tmp_path: Path) -> None:
    lifecycle = tmp_path / "lifecycle.jsonl"
    result_path = tmp_path / "result.json"
    execute_fake_candidate(lifecycle, result_path, [_success] * 4)
    result = load_strict_json(result_path)
    result["idCardNo"] = "synthetic-forbidden"
    with pytest.raises(ValueError, match="employee.fixture_metadata_v2_invalid"):
        validate_result(result)
    result.pop("idCardNo")
    result["queryCounts"]["retryCount"] = 1
    with pytest.raises(ValueError, match="employee.fixture_metadata_v2_invalid"):
        validate_result(result)


def test_result_assembly_failure_is_finite_and_strict(tmp_path: Path) -> None:
    lifecycle = tmp_path / "lifecycle.jsonl"
    result_path = tmp_path / "result.json"
    execute_fake_candidate(lifecycle, result_path, [_success] * 4)
    records = [json.loads(line) for line in lifecycle.read_text(encoding="utf-8").splitlines()]
    records[-1]["status"] = "failed"
    records[-1]["reason"] = "metadata_invalid"
    lifecycle.write_text(
        "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )
    validate_lifecycle(lifecycle)

    result = load_strict_json(result_path)
    result.pop("metadata")
    result["status"] = "failed"
    result["failure"] = {
        "phase": "result_assembly",
        "reason": "metadata_invalid",
        "queryOrdinal": 4,
        "sqlState": None,
        "vendorCode": None,
    }
    validate_result(result)
    result["failure"]["phase"] = "triggers"
    with pytest.raises(ValueError, match="employee.fixture_metadata_v2_invalid"):
        validate_result(result)


def test_lifecycle_rejects_status_reason_and_post_failure_drift(tmp_path: Path) -> None:
    lifecycle = tmp_path / "lifecycle.jsonl"
    result_path = tmp_path / "result.json"
    execute_fake_candidate(lifecycle, result_path, [_success, _failure, _success, _success])
    original = lifecycle.read_text(encoding="utf-8").splitlines()

    for index, key, value in (
        (1, "status", "succeeded"),
        (2, "reason", "metadata_invalid"),
        (-1, "reason", None),
    ):
        mutated = [json.loads(line) for line in original]
        mutated[index][key] = value
        candidate = tmp_path / f"invalid-{index}-{key}.jsonl"
        candidate.write_text(
            "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in mutated),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="employee.fixture_metadata_v2_invalid"):
            validate_lifecycle(candidate)


def test_manifest_rejects_missing_or_duplicate_frozen_assets(tmp_path: Path) -> None:
    manifest_path = EVIDENCE / (
        "employee-fixture-metadata-diagnostic-v2-20260814-candidate-02.manifest.json"
    )
    authorization_path = EVIDENCE / (
        "employee-fixture-metadata-diagnostic-v2-20260814-candidate-02.authorization.json"
    )
    manifest = load_strict_json(manifest_path)
    manifest["assetHashes"] = manifest["assetHashes"][:-1]
    missing = tmp_path / "missing-asset.manifest.json"
    missing.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="employee.fixture_metadata_v2_invalid"):
        validate_manifest(missing, authorization_path, REPOSITORY)

    manifest = load_strict_json(manifest_path)
    manifest["assetHashes"][-1] = manifest["assetHashes"][0]
    duplicate = tmp_path / "duplicate-asset.manifest.json"
    duplicate.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="employee.fixture_metadata_v2_invalid"):
        validate_manifest(duplicate, authorization_path, REPOSITORY)


def _sql_blocks(source: str) -> dict[str, str]:
    pattern = re.compile(
        r'private static final String (COLUMN_AND_ENGINE_SQL|KEY_AND_FOREIGN_KEY_SQL|CHECK_SQL|TRIGGER_SQL) = """(.*?)""";',
        re.DOTALL,
    )
    return {name: sql for name, sql in pattern.findall(source)}


def test_java_probe_keeps_four_projections_and_uses_binary_name_comparisons() -> None:
    source = JAVA_PROBE.read_text(encoding="utf-8")
    blocks = _sql_blocks(source)
    assert set(blocks) == {
        "COLUMN_AND_ENGINE_SQL",
        "KEY_AND_FOREIGN_KEY_SQL",
        "CHECK_SQL",
        "TRIGGER_SQL",
    }
    aliases = {
        "COLUMN_AND_ENGINE_SQL": {
            "columnName", "ordinalPosition", "dataType", "columnType", "isNullable",
            "columnDefault", "extra", "generationExpression", "characterMaximumLength",
            "characterSetName", "collationName", "tableEngine",
        },
        "KEY_AND_FOREIGN_KEY_SQL": {
            "direction", "constraintName", "constraintType", "tableName", "columnName",
            "ordinalPosition", "referencedTableName", "referencedColumnName",
        },
        "CHECK_SQL": {"constraintName", "checkClause"},
        "TRIGGER_SQL": {"triggerName", "timing", "event", "orientation", "actionStatement"},
    }
    relation_counts = {
        "COLUMN_AND_ENGINE_SQL": {
            "information_schema.columns": 1,
            "information_schema.tables": 1,
        },
        "KEY_AND_FOREIGN_KEY_SQL": {
            "information_schema.table_constraints": 2,
            "information_schema.key_column_usage": 2,
        },
        "CHECK_SQL": {
            "information_schema.table_constraints": 1,
            "information_schema.check_constraints": 1,
        },
        "TRIGGER_SQL": {"information_schema.triggers": 1},
    }
    for name, sql in blocks.items():
        assert set(re.findall(r"\bAS\s+([A-Za-z][A-Za-z0-9]*)", sql)) == aliases[name]
        assert "LOWER(" not in sql
        observed_relations = {
            relation: sql.count(relation) for relation in relation_counts[name]
        }
        assert observed_relations == relation_counts[name]
    comparison_lines = [
        line.strip()
        for sql in blocks.values()
        for line in sql.splitlines()
        if any(token in line for token in ("TABLE_SCHEMA", "TABLE_NAME", "CONSTRAINT_SCHEMA", "CONSTRAINT_NAME", "EVENT_OBJECT_SCHEMA", "EVENT_OBJECT_TABLE"))
        and ("=" in line or line.startswith("AND NOT"))
    ]
    assert comparison_lines
    assert all("BINARY" in line or line.startswith("AND NOT") for line in comparison_lines)
    assert source.count("executeQuery(") == 5  # four invocations plus the helper declaration
    invocation_offsets = [
        source.index(f'journal, "{phase}", {ordinal},')
        for ordinal, phase in enumerate(QUERY_PHASES, start=1)
    ]
    assert invocation_offsets == sorted(invocation_offsets)
    assert "@Transactional(readOnly = true)" in source
    assert "CREATE_NEW" in source and "channel.force(true)" in source


def test_schemas_are_closed_and_launcher_is_prepared_only() -> None:
    for name in (
        "employee-fixture-metadata-diagnostic-v2-lifecycle.schema.json",
        "employee-fixture-metadata-diagnostic-v2-success.schema.json",
        "employee-fixture-metadata-diagnostic-v2-failure.schema.json",
    ):
        schema = json.loads((EVIDENCE / name).read_text(encoding="utf-8"))
        assert schema["additionalProperties"] is False
        assert schema["properties"]["runId"]["const"].endswith("candidate-02")
        assert schema["properties"]["authorizationReference"]["const"] == AUTHORIZATION_REFERENCE
    launcher = LAUNCHER.read_text(encoding="utf-8")
    assert "employee.fixture_metadata_v2_live_not_authorized" in launcher
    assert "RUN_EMPLOYEE_FIXTURE_METADATA_DIAG_V2" in launcher
    assert "LLM_API_KEY" in launcher and "Remove-Item Env:\\LLM_API_KEY" in launcher
    assert "EMPLOYEE_LIVE_TEST_IDENTIFIER" in launcher
    assert "Get-FileHash" in launcher
    assert "-Dtest=EmployeeFixtureMetadataDiagnosticV2LiveIntegrationTest" in launcher
    assert "INSERT INTO" not in launcher and "DELETE FROM" not in launcher


def test_post_consumption_outputs_are_strict_and_frozen() -> None:
    prefix = "employee-fixture-metadata-diagnostic-v2-20260814-candidate-02"
    lifecycle = EVIDENCE / f"{prefix}.lifecycle.jsonl"
    result_path = EVIDENCE / f"{prefix}.result.json"
    assert sha256_file(lifecycle) == (
        "affbd35987e4caaa4950888eaed80cf12e695470b1703735716f2dd54d52a105"
    )
    assert sha256_file(result_path) == (
        "9973863d43112a8142bf54eaa1ea18905112d8ca802a24dda7eed5599ab7cd51"
    )
    records = validate_lifecycle(lifecycle)
    result = load_strict_json(result_path)
    validate_result(result)
    assert len(records) == 10
    assert result["status"] == "passed"
    assert result["queryCounts"] == {
        "maximum": 4,
        "started": 4,
        "terminal": 4,
        "succeeded": 4,
        "failed": 0,
        "retryCount": 0,
        "resumeCount": 0,
    }
    metadata = result["metadata"]
    assert metadata["table"]["engine"] == "InnoDB"
    assert len(metadata["table"]["columns"]) == 58
    assert metadata["constraints"] == []
    assert metadata["checks"] == []
    assert metadata["triggers"] == []
