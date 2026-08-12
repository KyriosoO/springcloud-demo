from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
EVIDENCE_ROOT = Path(__file__).with_name("evidence")
MANIFEST_PATH = EVIDENCE_ROOT / "knowledge-egress-diagnostic-v1-20260812-candidate-01.manifest.json"
CONSUMED_PATH = EVIDENCE_ROOT / "gate041-knowledge-egress-diagnostic-v1-20260812-candidate-01.consumed.json"
RESULT_PATH = EVIDENCE_ROOT / "wp-k-egress-diagnostic-01-20260812T100734Z.json"
JOURNAL_PATH = EVIDENCE_ROOT / "wp-k-egress-diagnostic-01-20260812T100734Z.attempt.jsonl"
RUN_ID = "knowledge-egress-diagnostic-v1-20260812-candidate-01"
AUTHORIZATION_REFERENCE = "P3_00:GATE-041"
MANIFEST_SHA256 = "a5d46cb2e3a7bfd1bb6f09ac8a79e672b0b5fbab69d9cccfdcc42cc1e259ea8a"
PRE_CONSUMPTION_TEST_SHA256 = "5e42339b1c9de586c8a40e03f791d0e13c27c2be8d481a322d6e087b60b17fa9"
HISTORY_SHA256 = {
    CONSUMED_PATH: "7ca40ac5e86b28bc4a20196cda938576d99a3cf6672f42bfeee2f622f2e8ca43",
    RESULT_PATH: "c9fd4546b2fe2d76cf0929f4af862e10a1846e2f830d16c6cfee1f8940870b32",
    JOURNAL_PATH: "9ca0b874c27143bbac36adc36b99e2606e722af9992645f85007b4088bffda9c",
}
FORBIDDEN_PERSISTED_KEYS = {
    "question",
    "quote",
    "knowledgeContent",
    "rawModelResponse",
    "jwt",
    "subject",
    "evidenceIdentity",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _all_json_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        keys = {key for key in value if isinstance(key, str)}
        return keys.union(*(_all_json_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_all_json_keys(item) for item in value))
    return set()


def test_candidate_01_manifest_is_strict_prepared_snapshot() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert _sha256(MANIFEST_PATH) == MANIFEST_SHA256
    assert set(manifest) == {
        "schemaVersion",
        "runId",
        "workPackageId",
        "authorizationGateId",
        "authorizationReference",
        "recordedAt",
        "status",
        "diagnosticOnly",
        "executionBoundary",
        "frozenInputs",
        "immutableHistory",
    }
    assert manifest["schemaVersion"] == 1
    assert manifest["runId"] == RUN_ID
    assert manifest["workPackageId"] == "WP-K-EGRESS-DIAG-01"
    assert manifest["authorizationGateId"] == "GATE-041"
    assert manifest["authorizationReference"] == AUTHORIZATION_REFERENCE
    assert manifest["status"] == "prepared_unconsumed"
    assert manifest["diagnosticOnly"] is True
    boundary = manifest["executionBoundary"]
    assert boundary == {
        "caseIds": ["tax-policy", "tax-law", "tax-mixed"],
        "repeatCount": 3,
        "executionOrder": "round_major_tax_policy_tax_law_tax_mixed",
        "authorizedSummaryCalls": 9,
        "firstOutboundConsumesAuthorization": True,
        "retryAllowed": False,
        "resumeAllowed": False,
        "answerCallsAllowed": False,
        "p5Allowed": False,
        "businessCallsAllowed": False,
        "closureClaimAllowed": False,
        "persistedDiagnosticFields": ["status", "validationReason", "integerCounts"],
        "forbiddenPersistedFields": [
            "question",
            "quote",
            "knowledgeContent",
            "rawModelResponse",
            "jwt",
            "subject",
            "evidenceIdentity",
        ],
        "consumedMarkerPath": "agent-runtime/tests/integration/knowledge/evidence/gate041-knowledge-egress-diagnostic-v1-20260812-candidate-01.consumed.json",
    }
    assert REPOSITORY_ROOT / boundary["consumedMarkerPath"] == CONSUMED_PATH
    assert len(manifest["frozenInputs"]) == 11
    assert len(manifest["immutableHistory"]) == 4
    for record in (*manifest["frozenInputs"], *manifest["immutableHistory"]):
        assert set(record) == {"path", "sha256"}
        path = REPOSITORY_ROOT / record["path"]
        assert path.is_file()
        if path.resolve() == Path(__file__).resolve():
            assert record["sha256"] == PRE_CONSUMPTION_TEST_SHA256
        else:
            assert _sha256(path) == record["sha256"]


def test_candidate_01_consumed_result_and_journal_are_immutable_history() -> None:
    assert all(path.is_file() and _sha256(path) == expected for path, expected in HISTORY_SHA256.items())

    consumed: dict[str, Any] = json.loads(CONSUMED_PATH.read_text(encoding="utf-8"))
    assert consumed == {
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "authorizedSummaryCalls": 9,
        "consumedAt": "2026-08-12T10:07:09Z",
        "diagnosticOnly": True,
        "gateId": "GATE-041",
        "manifestSha256": MANIFEST_SHA256,
        "retryAllowed": False,
        "runId": RUN_ID,
        "schemaVersion": 1,
        "workPackageId": "WP-K-EGRESS-DIAG-01",
    }

    result: dict[str, Any] = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert result == {
        "actualSummaryCalls": 9,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "authorizedSummaryCalls": 9,
        "closureClaimed": False,
        "dataBoundary": {
            "businessCallCount": 0,
            "jwtPersisted": False,
            "knowledgeContentPersisted": False,
            "questionPersisted": False,
            "quotePersisted": False,
            "rawModelResponsePersisted": False,
        },
        "diagnosticOnly": True,
        "gateId": "GATE-041",
        "manifestSha256": MANIFEST_SHA256,
        "recordedAt": "2026-08-12T10:07:33.831Z",
        "retryCount": 0,
        "runId": RUN_ID,
        "schemaVersion": 1,
        "status": "diagnostic_completed",
        "statusCounts": {"quote_invalid": 6, "success": 3},
        "terminalRecordCount": 9,
        "validationReasonCounts": {"duplicate_evidence_ref": 6},
        "workPackageId": "WP-K-EGRESS-DIAG-01",
    }

    journal: list[dict[str, Any]] = [
        json.loads(line) for line in JOURNAL_PATH.read_text(encoding="utf-8").splitlines()
    ]
    assert len(journal) == 19
    header = journal[0]
    assert header["event"] == "attempt_started"
    assert header["runId"] == RUN_ID
    assert header["workPackageId"] == "WP-K-EGRESS-DIAG-01"
    assert header["gateId"] == "GATE-041"
    assert header["authorizationReference"] == AUTHORIZATION_REFERENCE
    assert header["manifestSha256"] == MANIFEST_SHA256
    assert header["authorizedSummaryCalls"] == 9
    assert header["retryAllowed"] is False
    assert header["diagnosticOnly"] is True

    expected_cases = ["tax-policy", "tax-law", "tax-mixed"] * 3
    outbound = journal[1::2]
    terminal = journal[2::2]
    assert [(record["callOrdinal"], record["caseId"]) for record in outbound] == list(
        enumerate(expected_cases, start=1)
    )
    assert all(record["event"] == "outbound_started" and record["runId"] == RUN_ID for record in outbound)
    assert [(record["callOrdinal"], record["caseId"]) for record in terminal] == list(
        enumerate(expected_cases, start=1)
    )
    assert [record["status"] for record in terminal] == [
        "quote_invalid",
        "quote_invalid",
        "success",
    ] * 3
    assert [record.get("validationReason") for record in terminal] == [
        "duplicate_evidence_ref",
        "duplicate_evidence_ref",
        None,
    ] * 3
    assert all(record["event"] == "call_terminal" and record["runId"] == RUN_ID for record in terminal)

    persisted = [consumed, result, *journal]
    assert FORBIDDEN_PERSISTED_KEYS.isdisjoint(_all_json_keys(persisted))


def test_manifest_does_not_embed_sensitive_or_closure_material() -> None:
    serialized = MANIFEST_PATH.read_text(encoding="utf-8").lower()

    for forbidden in (
        "llm_api_key",
        "authorization: bearer",
        "auth_token",
        "idcard",
        "raw response",
        '"closureclaimed": true',
    ):
        assert forbidden not in serialized
