from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.integration.adapters.employee.egress_input_qualification_v4_host import (
    QualificationV4HostError,
    complete_host_lifecycle,
    create_host_lifecycle,
    load_strict_json,
    validate_host_lifecycle,
    validate_pre_sql_failure,
    write_pre_sql_failure,
)


EVIDENCE = Path(__file__).parent / "evidence"
HOST_SCHEMA = EVIDENCE / "employee-egress-input-qualification-v4-host-lifecycle.schema.json"
FAILURE_SCHEMA = EVIDENCE / "employee-egress-input-qualification-v4-pre-sql-failure.schema.json"
MANIFEST_SHA = "a" * 64


@pytest.mark.parametrize("succeeded", [True, False])
def test_host_lifecycle_is_created_before_context_and_has_one_terminal(
    tmp_path: Path, succeeded: bool
) -> None:
    path = tmp_path / "host.jsonl"
    create_host_lifecycle(path, manifest_sha256=MANIFEST_SHA)
    started = path.read_text(encoding="utf-8").splitlines()
    assert len(started) == 2
    assert [json.loads(line)["phase"] for line in started] == [
        "host_bootstrap",
        "spring_context",
    ]

    complete_host_lifecycle(
        path,
        manifest_sha256=MANIFEST_SHA,
        spring_context_succeeded=succeeded,
    )
    records = validate_host_lifecycle(path, manifest_sha256=MANIFEST_SHA)
    assert [record["sequence"] for record in records] == [1, 2, 3, 4]
    assert records[-1]["state"] == ("succeeded" if succeeded else "failed")
    schema = json.loads(HOST_SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["properties"]["runId"]["const"] == records[0]["runId"]
    assert schema["properties"]["phase"]["enum"] == ["host_bootstrap", "spring_context"]


def test_pre_sql_failure_is_exclusive_strict_and_zero_call(tmp_path: Path) -> None:
    lifecycle = tmp_path / "host.jsonl"
    failure = tmp_path / "failure.json"
    create_host_lifecycle(lifecycle, manifest_sha256=MANIFEST_SHA)
    complete_host_lifecycle(
        lifecycle,
        manifest_sha256=MANIFEST_SHA,
        spring_context_succeeded=False,
    )
    value = write_pre_sql_failure(
        failure,
        host_lifecycle_path=lifecycle,
        manifest_sha256=MANIFEST_SHA,
        host_exit_code=1,
        log_leak_count=0,
        raw_logs_deleted=True,
    )
    assert validate_pre_sql_failure(load_strict_json(failure)) == value
    assert set(value["counts"].values()) == {0}
    schema = json.loads(FAILURE_SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["properties"]["status"]["const"] == "failed_unconsumed"
    assert schema["properties"]["counts"]["properties"]["modelCalls"] == {"const": 0}
    with pytest.raises(FileExistsError):
        write_pre_sql_failure(
            failure,
            host_lifecycle_path=lifecycle,
            manifest_sha256=MANIFEST_SHA,
            host_exit_code=1,
            log_leak_count=0,
            raw_logs_deleted=True,
        )


def test_pre_sql_failure_rejects_successful_context_and_leaky_logs(tmp_path: Path) -> None:
    lifecycle = tmp_path / "host.jsonl"
    create_host_lifecycle(lifecycle, manifest_sha256=MANIFEST_SHA)
    complete_host_lifecycle(
        lifecycle,
        manifest_sha256=MANIFEST_SHA,
        spring_context_succeeded=True,
    )
    with pytest.raises(QualificationV4HostError, match="invalid"):
        write_pre_sql_failure(
            tmp_path / "failure.json",
            host_lifecycle_path=lifecycle,
            manifest_sha256=MANIFEST_SHA,
            host_exit_code=1,
            log_leak_count=0,
            raw_logs_deleted=True,
        )

    failed_lifecycle = tmp_path / "failed.jsonl"
    create_host_lifecycle(failed_lifecycle, manifest_sha256=MANIFEST_SHA)
    complete_host_lifecycle(
        failed_lifecycle,
        manifest_sha256=MANIFEST_SHA,
        spring_context_succeeded=False,
    )
    with pytest.raises(QualificationV4HostError, match="invalid"):
        write_pre_sql_failure(
            tmp_path / "leaky.json",
            host_lifecycle_path=failed_lifecycle,
            manifest_sha256=MANIFEST_SHA,
            host_exit_code=1,
            log_leak_count=1,
            raw_logs_deleted=False,
        )


def test_lifecycle_is_exclusive_and_rejects_duplicate_or_incomplete_terminal(
    tmp_path: Path,
) -> None:
    path = tmp_path / "host.jsonl"
    create_host_lifecycle(path, manifest_sha256=MANIFEST_SHA)
    with pytest.raises(FileExistsError):
        create_host_lifecycle(path, manifest_sha256=MANIFEST_SHA)
    with pytest.raises(QualificationV4HostError, match="invalid"):
        validate_host_lifecycle(path, manifest_sha256=MANIFEST_SHA)
    complete_host_lifecycle(
        path,
        manifest_sha256=MANIFEST_SHA,
        spring_context_succeeded=False,
    )
    with pytest.raises(QualificationV4HostError, match="invalid"):
        complete_host_lifecycle(
            path,
            manifest_sha256=MANIFEST_SHA,
            spring_context_succeeded=False,
        )
