from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from tests.integration.adapters.employee.fixture_metadata_diagnostic import sha256_file


_EVIDENCE_DIRECTORY = Path(__file__).with_name("evidence")
_FAILURE_PATH = _EVIDENCE_DIRECTORY / (
    "employee-fixture-metadata-diagnostic-v1-20260814-run-01.failure.json"
)
_SCHEMA_PATH = _EVIDENCE_DIRECTORY / (
    "employee-fixture-metadata-diagnostic-v1-failure.schema.json"
)
_LAUNCHER_PATH = Path(__file__).with_name(
    "run_employee_fixture_metadata_diagnostic.ps1"
)

_TOP_LEVEL_KEYS = {
    "schemaVersion",
    "workPackageId",
    "runId",
    "authorizationReference",
    "recordedAt",
    "status",
    "sourceEvidence",
    "implementationSources",
    "failure",
    "queryCounts",
    "rawReportDigests",
    "safety",
}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_failed_run_is_strict_finite_and_bound_to_gate_050() -> None:
    evidence = _load(_FAILURE_PATH)

    assert set(evidence) == _TOP_LEVEL_KEYS
    assert evidence["schemaVersion"] == 1
    assert evidence["workPackageId"] == "WP-EMP-EGRESS-TEST-DATA-PREP-01"
    assert evidence["runId"] == (
        "employee-fixture-metadata-diagnostic-v1-20260814-run-01"
    )
    assert evidence["authorizationReference"] == "P3_00:GATE-050"
    assert evidence["status"] == "failed"
    assert evidence["sourceEvidence"]["sha256"] == (
        "b79f3601c3ead955e5cf747fa91cc000aad9773a1294c17277deeef05f92efe6"
    )
    assert evidence["failure"] == {
        "phase": "constraint_metadata_query",
        "reason": "information_schema_collation_mismatch",
        "sqlState": "HY000",
        "vendorCode": 1267,
        "failedQueryOrdinal": 2,
    }
    assert evidence["queryCounts"] == {
        "maxQueries": 4,
        "totalStarted": 2,
        "successfulQueries": 1,
        "failedQueries": 1,
        "columnStarted": 1,
        "columnTerminal": 1,
        "constraintStarted": 1,
        "constraintTerminal": 1,
        "checkStarted": 0,
        "checkTerminal": 0,
        "triggerStarted": 0,
        "triggerTerminal": 0,
        "retryCount": 0,
        "resumeCount": 0,
    }
    assert evidence["safety"] == {
        "businessRowsRead": False,
        "identifiersPersisted": False,
        "fieldValuesPersisted": False,
        "rawTriggerStatementsPersisted": False,
        "employeeEndpointCalls": 0,
        "authCalls": 0,
        "jwtRead": False,
        "llmApiKeyRead": False,
        "modelCalls": 0,
        "modelOutbound": False,
        "databaseWrites": 0,
        "schemaChanges": 0,
        "logLeakCount": 0,
        "rawLogsDeleted": True,
    }


def test_failure_schema_is_closed_and_exactly_binds_immutable_values() -> None:
    schema = _load(_SCHEMA_PATH)
    evidence = _load(_FAILURE_PATH)
    properties = cast(dict[str, Any], schema["properties"])

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == _TOP_LEVEL_KEYS
    for name in (
        "sourceEvidence",
        "implementationSources",
        "failure",
        "queryCounts",
        "rawReportDigests",
        "safety",
    ):
        assert properties[name]["additionalProperties"] is False
    for name in (
        "schemaVersion",
        "workPackageId",
        "runId",
        "authorizationReference",
        "recordedAt",
        "status",
    ):
        assert properties[name]["const"] == evidence[name]
    for name, value in evidence["failure"].items():
        assert properties["failure"]["properties"][name]["const"] == value
    for name, value in evidence["queryCounts"].items():
        assert properties["queryCounts"]["properties"][name]["const"] == value
    for name, value in evidence["safety"].items():
        assert properties["safety"]["properties"][name]["const"] == value


def test_failed_run_sources_and_raw_report_digests_are_immutable() -> None:
    evidence = _load(_FAILURE_PATH)

    assert evidence["implementationSources"] == {
        "pythonProbe": "6737a6d775bac740f70628dad98076b93112a8f28ed1cea6f4a03e46cdd735ed",
        "pythonTest": "aa1b54205026e349c143fe313dadcdb75e5f071889b634d741d1a0251d841b21",
        "successSchema": "523bf02cb522f09f717511815ed59e025321ff43b0c31b96fef8f7774122d05b",
        "launcher": "d9e8147d5b76defc57351f3828aa09ab42996dbcfde5ba7f00e2d0c13d8c3eff",
        "javaProbe": "0581a9f1f49f0440db77545ca07e09563706ee4d6eaac6aa6cd9d8f2ed44b8e9",
    }
    assert evidence["rawReportDigests"] == {
        "text": "c83bb86c816b4e961f66d97e64cc09bcb04a6b5ee2e60ebebc76f7bb025c5d1d",
        "xml": "f33e29be20c212749c3555caa2cc81f3973522c5a56ad20d79f8f3e2271d74dd",
        "dumpstream": "b1efe518d8f49ad396d40a4728f1e3284b1c7eae5b14bdbccca3383c34f55312",
    }
    for value in evidence["implementationSources"].values():
        assert len(value) == 64
    for value in evidence["rawReportDigests"].values():
        assert len(value) == 64


def test_failure_assets_have_stable_hashes() -> None:
    assert sha256_file(_FAILURE_PATH) == (
        "dce5e7659ed9cc49b52aa9cca6b70c9701c22cc55867f26cfa6a50ead291e7a1"
    )
    assert sha256_file(_SCHEMA_PATH) == (
        "e9182239e7425a071c7daaf4c2a74fb3ef354fec9907ca0da5cef92f8ac85adc"
    )


def test_launcher_refuses_failed_run_before_any_execution_side_effect() -> None:
    source = _LAUNCHER_PATH.read_text(encoding="utf-8")
    failure_name = (
        "employee-fixture-metadata-diagnostic-v1-20260814-run-01.failure.json"
    )
    refusal = "employee.fixture_metadata_diagnostic_failure_evidence_already_exists"

    assert failure_name in source
    assert refusal in source
    refusal_offset = source.index(refusal)
    assert refusal_offset < source.index("New-Item -ItemType Directory")
    assert refusal_offset < source.index("$env:RUN_EMPLOYEE_FIXTURE_METADATA_DIAG")
    assert refusal_offset < source.index("& mvn")
