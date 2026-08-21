from __future__ import annotations

from pathlib import Path

from tests.integration.adapters.frozen_manifest import materialize_manifest_at_commit
from tests.integration.adapters.employee.egress_input_qualification_v6 import (
    AUTHORIZATION_REFERENCE,
    RUN_ID,
    load_strict_json,
    sha256_file,
    validate_authorization,
    validate_lifecycle,
    validate_manifest,
    validate_result,
)
from tests.integration.adapters.employee.egress_input_qualification_v6_host import (
    validate_host_lifecycle,
)


REPOSITORY = Path(__file__).resolve().parents[5]
EVIDENCE = Path(__file__).parent / "evidence"
MANIFEST = EVIDENCE / f"{RUN_ID}.manifest.json"
AUTHORIZATION = EVIDENCE / f"{RUN_ID}.authorization.json"
HOST_LIFECYCLE = EVIDENCE / f"{RUN_ID}.host-lifecycle.jsonl"
LIFECYCLE = EVIDENCE / f"{RUN_ID}.lifecycle.jsonl"
RESULT = EVIDENCE / f"{RUN_ID}.result.json"

EXPECTED_MANIFEST_SHA256 = "44f25232b445e0f1c8184b31ccf2dff4d5751a796b4f3ec327fb1ea2cbb702b2"
EXPECTED_AUTHORIZATION_SHA256 = "bd0cb4d67c00e2aeba7756860f02a4f7df1fd9f17eb9420cc3ece4e524a697c5"
EXPECTED_HOST_LIFECYCLE_SHA256 = "9c4f7d9981bef665bd06068a96155433bfbe838ebad65d4ac5dc4424106c28d5"
EXPECTED_LIFECYCLE_SHA256 = "ec87bcb430fc90b3e9511871625bba60c07f7d4cc7e12842f3e18255624f6677"
EXPECTED_RESULT_SHA256 = "750f2e0d13866203116884e1950734bcb2b06100343f142cb5e96c63fe55a9cd"
FROZEN_SOURCE_COMMIT = "9585d1e77bba019ddef81a8d548eb3ddc16ee1b7"


def test_candidate_v6_prepared_and_consumed_assets_are_exact(tmp_path: Path) -> None:
    assert sha256_file(MANIFEST) == EXPECTED_MANIFEST_SHA256
    assert sha256_file(AUTHORIZATION) == EXPECTED_AUTHORIZATION_SHA256
    assert sha256_file(HOST_LIFECYCLE) == EXPECTED_HOST_LIFECYCLE_SHA256
    assert sha256_file(LIFECYCLE) == EXPECTED_LIFECYCLE_SHA256
    assert sha256_file(RESULT) == EXPECTED_RESULT_SHA256

    raw_manifest = load_strict_json(MANIFEST)
    frozen_repository = materialize_manifest_at_commit(
        raw_manifest,
        repository_root=REPOSITORY,
        destination=tmp_path / "frozen-repository",
        source_commit=FROZEN_SOURCE_COMMIT,
        collection_names=("history", "assetHashes"),
    )
    manifest = validate_manifest(raw_manifest, repository_root=frozen_repository)
    authorization = validate_authorization(
        load_strict_json(AUTHORIZATION), manifest_sha256=EXPECTED_MANIFEST_SHA256
    )
    assert manifest["runId"] == RUN_ID
    assert authorization["authorizationReference"] == AUTHORIZATION_REFERENCE
    assert authorization["liveExecutionAuthorized"] is False


def test_candidate_v6_qualified_after_one_complete_safe_lifecycle() -> None:
    host_records = validate_host_lifecycle(
        HOST_LIFECYCLE, manifest_sha256=EXPECTED_MANIFEST_SHA256
    )
    lifecycle_records = validate_lifecycle(
        LIFECYCLE, manifest_sha256=EXPECTED_MANIFEST_SHA256
    )
    result = validate_result(load_strict_json(RESULT))

    assert len(host_records) == 4
    assert host_records[-1]["state"] == "succeeded"
    assert len(lifecycle_records) == 16
    assert [
        (record["sequence"], record["phase"], record["state"], record["reason"])
        for record in lifecycle_records
    ] == [
        (1, "run", "started", "none"),
        (2, "fixture_precheck", "started", "none"),
        (3, "fixture_precheck", "succeeded", "none"),
        (4, "fixture_insert", "started", "none"),
        (5, "fixture_insert", "succeeded", "none"),
        (6, "fixture_verify", "started", "none"),
        (7, "fixture_verify", "succeeded", "none"),
        (8, "employee_detail", "started", "none"),
        (9, "employee_detail", "succeeded", "none"),
        (10, "cleanup_delete", "started", "none"),
        (11, "cleanup_delete", "succeeded", "none"),
        (12, "cleanup_verify", "started", "none"),
        (13, "cleanup_verify", "succeeded", "none"),
        (14, "host_validation", "started", "none"),
        (15, "host_validation", "succeeded", "none"),
        (16, "run", "succeeded", "none"),
    ]
    assert result["status"] == "qualified"
    assert result["reason"] == "none"
    assert result["lifecycleSha256"] == EXPECTED_LIFECYCLE_SHA256
    assert result["counts"] == {
        "databaseDeleteStarted": 1,
        "databaseDeleteTerminal": 1,
        "databaseInsertStarted": 1,
        "databaseInsertTerminal": 1,
        "databaseSelectStarted": 3,
        "databaseSelectTerminal": 3,
        "deleted": 1,
        "employeeDetailStarted": 1,
        "employeeDetailTerminal": 1,
        "inserted": 1,
        "modelCalls": 0,
        "otherEmployeeEndpoints": 0,
        "preexisting": 0,
        "remaining": 0,
        "resumeCount": 0,
        "retryCount": 0,
        "verified": 1,
    }
    assert all(result["fieldPresence"]["codec"].values())
    assert all(result["fieldPresence"]["requiredUser"].values())
    assert result["fieldPresence"]["egressAllowed"] is True
    assert result["safety"] == {
        "existingRowsModified": 0,
        "fieldValuesPersisted": False,
        "identifierPersisted": False,
        "jwtPersisted": False,
        "llmApiKeyRead": False,
        "logLeakCount": 0,
        "modelOutbound": False,
        "nonRealIdentifier": True,
        "rawLogsDeleted": True,
        "rawResponsePersisted": False,
        "synthetic": True,
    }

    for suffix in ("pre-sql-failure.json", "pending.json", "qualification-staging.json"):
        assert not (EVIDENCE / f"{RUN_ID}.{suffix}").exists()
