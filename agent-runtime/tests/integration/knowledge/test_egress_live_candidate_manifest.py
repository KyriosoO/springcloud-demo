from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
MANIFEST_02 = ROOT / "tests/integration/knowledge/evidence/knowledge-egress-v1-20260812-candidate-02.manifest.json"
MANIFEST_03 = ROOT / "tests/integration/knowledge/evidence/knowledge-egress-v1-20260812-candidate-03.manifest.json"
CANDIDATE_03_MANIFEST_SHA256 = "ef1751a4297b653d0ee746c7653bba5642384e5b8a027a912b2760a581d19b18"
CANDIDATE_03_CONSUMED = ROOT / "tests/integration/knowledge/evidence/gate040-knowledge-egress-v1-20260812-candidate-03.consumed.json"
CANDIDATE_03_FAILED_ATTEMPT = ROOT / "tests/integration/knowledge/evidence/wp-k-egress-01-20260812T085839Z.failed-attempt.json"
CANDIDATE_03_FAILED_JOURNAL = ROOT / "tests/integration/knowledge/evidence/wp-k-egress-01-20260812T085839Z.failed-attempt.jsonl"
CANDIDATE_03_HISTORY_HASHES = {
    CANDIDATE_03_CONSUMED: "6d96b5e260f454f2ef15c2a7a4794e6f45304e5b2702a3ea3be10b4b60291e37",
    CANDIDATE_03_FAILED_ATTEMPT: "70a71461fff58e6638e8e3a686cacd5ab260a7ee9b6c82b94da89db2ba9c674c",
    CANDIDATE_03_FAILED_JOURNAL: "b8cbc36a38ca97ca39b7cbcafa768795c72b30b4e007c8ba11ce59aaad23a94b",
}
TOP_KEYS = {
    "schemaVersion",
    "runId",
    "workPackageId",
    "closureGateId",
    "authorizationGateId",
    "authorizationReference",
    "recordedAt",
    "status",
    "executionBoundary",
    "frozenInputs",
    "immutableHistory",
}
BOUNDARY_KEYS = {
    "caseIds",
    "repeatCount",
    "executionOrder",
    "authorizedSummaryCalls",
    "successCriteria",
    "firstOutboundConsumesAuthorization",
    "retryAllowed",
    "resumeAllowed",
    "answerCallsAllowed",
    "p5Allowed",
    "realBusinessDataAllowed",
    "consumedMarkerPath",
}
FILE_KEYS = {"path", "sha256"}
SUCCESS_CRITERIA_KEYS = {
    "resultRecordCount",
    "terminalRecordCount",
    "minimumValidSummaryCount",
    "minimumValidSummaryCountPerCase",
    "invalidQuoteAcceptedCount",
    "retryCount",
    "forbiddenFieldCount",
    "businessCallCount",
    "logLeakCount",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _files(value: object) -> list[dict[str, Any]]:
    assert type(value) is list and value
    assert all(type(item) is dict and set(item) == FILE_KEYS for item in value)
    return value


def test_candidate_02_manifest_and_failure_evidence_are_immutable_history() -> None:
    expected_hashes = {
        MANIFEST_02: "505998232ca20000ad072159430cd4fe8c79d163079048bc6a8953d74f67b907",
        ROOT / "tests/integration/knowledge/evidence/gate039-knowledge-egress-v1-20260812-candidate-02.consumed.json": "533326a49de1f0da50b486df12be7b7f9dcd24251095773e8a4733eccd045053",
        ROOT / "tests/integration/knowledge/evidence/wp-k-egress-01-20260812T082724Z.failed-attempt.json": "8974c81b54d2dbfee657282af5b7ffc75f3cadaa4d95ae7befb7a7c331f24d6b",
        ROOT / "tests/integration/knowledge/evidence/wp-k-egress-01-20260812T082724Z.failed-attempt.jsonl": "c61538602b4da7483f84aa624a951a46c4dc14d1f469647f05b561947f09dd1e",
    }
    assert all(path.is_file() and _sha256(path) == expected for path, expected in expected_hashes.items())


def test_candidate_03_manifest_and_consumed_failure_are_immutable_history() -> None:
    assert _sha256(MANIFEST_03) == CANDIDATE_03_MANIFEST_SHA256
    value = json.loads(MANIFEST_03.read_text(encoding="utf-8"))
    assert type(value) is dict and set(value) == TOP_KEYS
    assert value["schemaVersion"] == 1
    assert value["runId"] == "knowledge-egress-v1-20260812-candidate-03"
    assert value["workPackageId"] == "WP-K-EGRESS-01"
    assert value["closureGateId"] == "GATE-022"
    assert value["authorizationGateId"] == "GATE-040"
    assert value["authorizationReference"] == "P3_00:GATE-040"
    assert value["status"] == "prepared_unconsumed"
    boundary = value["executionBoundary"]
    assert type(boundary) is dict and set(boundary) == BOUNDARY_KEYS
    assert boundary == {
        "caseIds": ["tax-policy", "tax-law", "tax-mixed"],
        "repeatCount": 10,
        "executionOrder": "round_major_tax_policy_tax_law_tax_mixed",
        "authorizedSummaryCalls": 30,
        "successCriteria": {
            "resultRecordCount": 30,
            "terminalRecordCount": 30,
            "minimumValidSummaryCount": 27,
            "minimumValidSummaryCountPerCase": 9,
            "invalidQuoteAcceptedCount": 0,
            "retryCount": 0,
            "forbiddenFieldCount": 0,
            "businessCallCount": 0,
            "logLeakCount": 0,
        },
        "firstOutboundConsumesAuthorization": True,
        "retryAllowed": False,
        "resumeAllowed": False,
        "answerCallsAllowed": False,
        "p5Allowed": False,
        "realBusinessDataAllowed": False,
        "consumedMarkerPath": "agent-runtime/tests/integration/knowledge/evidence/gate040-knowledge-egress-v1-20260812-candidate-03.consumed.json",
    }
    assert set(boundary["successCriteria"]) == SUCCESS_CRITERIA_KEYS
    assert ROOT.parent / boundary["consumedMarkerPath"] == CANDIDATE_03_CONSUMED
    for item in (*_files(value["frozenInputs"]), *_files(value["immutableHistory"])):
        path = ROOT.parent / item["path"]
        assert path.is_file(), item["path"]
        assert _sha256(path) == item["sha256"], item["path"]

    assert all(path.is_file() and _sha256(path) == expected for path, expected in CANDIDATE_03_HISTORY_HASHES.items())
    consumed = json.loads(CANDIDATE_03_CONSUMED.read_text(encoding="utf-8"))
    assert consumed == {
        "schemaVersion": 1,
        "gateId": "GATE-040",
        "closureGateId": "GATE-022",
        "workPackageId": "WP-K-EGRESS-01",
        "runId": "knowledge-egress-v1-20260812-candidate-03",
        "authorizationReference": "P3_00:GATE-040",
        "consumedAt": "2026-08-12T08:57:33Z",
        "authorizedSummaryCalls": 30,
        "retryAllowed": False,
    }
    attempt = json.loads(CANDIDATE_03_FAILED_ATTEMPT.read_text(encoding="utf-8"))
    assert attempt["status"] == "failed"
    assert attempt["actualSummaryCalls"] == 30
    assert attempt["retryCount"] == 0
    assert attempt["payloadForbiddenFieldCount"] == 0
    assert len(attempt["caseResults"]) == 30
    result_counts = {
        (case_id, evidence_kind): sum(
            item["caseId"] == case_id and item["evidenceKind"] == evidence_kind
            for item in attempt["caseResults"]
        )
        for case_id in ("tax-policy", "tax-law", "tax-mixed")
        for evidence_kind in ("success", "downstream_failure")
    }
    assert result_counts == {
        ("tax-policy", "success"): 0,
        ("tax-policy", "downstream_failure"): 10,
        ("tax-law", "success"): 6,
        ("tax-law", "downstream_failure"): 4,
        ("tax-mixed", "success"): 10,
        ("tax-mixed", "downstream_failure"): 0,
    }


def test_candidate_03_history_contains_no_questions_credentials_or_real_domain_data() -> None:
    raw = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in (MANIFEST_03, *CANDIDATE_03_HISTORY_HASHES)
    )
    assert all(
        marker not in raw
        for marker in ("增值税", "个人所得税", "身份证", "jwt", "api_key", "employee", "transaction")
    )
