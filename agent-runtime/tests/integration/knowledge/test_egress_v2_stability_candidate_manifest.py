from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from agent_runtime.knowledge.evidence.summary_task_v2 import SUMMARY_PROMPT_V2, KnowledgeSummaryTaskV2


ROOT = Path(__file__).resolve().parents[3]
REPOSITORY = ROOT.parent
MANIFEST = ROOT / "tests/integration/knowledge/evidence/knowledge-egress-v2-20260812-candidate-01.manifest.json"
MANIFEST_SHA256 = "712ecedd405083e85090b525d25250d5e1dff58084a76ab4a0970c06dbeb4405"
CONSUMED = ROOT / "tests/integration/knowledge/evidence/gate043-knowledge-egress-v2-20260812-candidate-01.consumed.json"
EVIDENCE = ROOT / "tests/integration/knowledge/evidence/wp-k-egress-01-20260812T233629Z.json"
ATTEMPT = ROOT / "tests/integration/knowledge/evidence/wp-k-egress-01-20260812T233629Z.attempt.json"
JOURNAL = ROOT / "tests/integration/knowledge/evidence/wp-k-egress-01-20260812T233629Z.attempt.jsonl"
RUN_ID = "knowledge-egress-v2-20260812-candidate-01"
AUTHORIZATION_REFERENCE = "P3_00:GATE-043"
FROZEN_COMMIT = "ac799d3df4b751ae8977c039f28d6700146a993d"
HISTORY_SHA256 = {
    CONSUMED: "a50f4c7032d90d96340a71a5a82b9b8c6b3c790102ebf945f76b97576044e8e5",
    EVIDENCE: "060ca50c1f44ab7b1d85f4bc92a327f4383edfbfaf4108d9f457129aa2046fd2",
    ATTEMPT: "7cfed521eabe864e29c320e584ce8be550689cdc5b1b5447b044be737874afb1",
    JOURNAL: "a65d9a428e5a08afd62dcaf7a1324c226afa200a404c7cbb1d326922d5998805",
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
    "taskBinding",
    "retrievalSnapshot",
    "executionBoundary",
    "frozenInputs",
    "immutableHistory",
}
FILE_KEYS = {"path", "sha256"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file_records(value: object) -> list[dict[str, Any]]:
    assert type(value) is list and value
    assert all(type(item) is dict and set(item) == FILE_KEYS for item in value)
    return value


def test_gate043_v2_manifest_is_strict_prepared_and_all_frozen_hashes_match() -> None:
    assert _sha256(MANIFEST) == MANIFEST_SHA256
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert type(value) is dict and set(value) == TOP_KEYS
    assert value["schemaVersion"] == 2
    assert value["runId"] == RUN_ID
    assert value["workPackageId"] == "WP-K-EGRESS-01"
    assert value["closureGateId"] == "GATE-022"
    assert value["authorizationGateId"] == "GATE-043"
    assert value["authorizationReference"] == AUTHORIZATION_REFERENCE
    assert value["status"] == "prepared_unconsumed"

    definition = KnowledgeSummaryTaskV2.definition()
    assert value["taskBinding"] == {
        "taskId": definition.task_id.value,
        "taskVersion": definition.task_version,
        "promptVersion": "knowledge-summary-extractive-prompt-v2",
        "instructionSha256": hashlib.sha256(SUMMARY_PROMPT_V2.encode("utf-8")).hexdigest(),
    }
    assert value["retrievalSnapshot"] == {
        "readAlias": "agent-doc-tax-policy-v2-read",
        "readIndex": "agent-doc-tax-policy-v3-20260803-agent-read-v1",
        "readIndexUuid": "k97bn1gxROSfVm7zGfzbOg",
        "mappingVersion": "agent-knowledge-tax-v1",
        "retrievalProfileVersion": "tax-knowledge-search-v1",
        "indexSnapshotIds": [
            "7c71202794927a9497fed9df7cc0db5a052a53f0f6c2afdb6c0a16089f1c96ed",
            "99ae962ae1c8e5026187c864eada38b3c3b82d6b017e6e8f076f116aba53fce2",
        ],
        "metadataSha256": "64f18ff1f8525df2f9a1e1657f87b608f174876157109390e47a653ddeaf2392",
        "bindingsSha256": "dc7aa05e04176b8853dc6ba78d6941e5eff5495a80797e9f3e9b8953c81d3ed2",
    }
    boundary = value["executionBoundary"]
    assert boundary["caseIds"] == ["tax-policy", "tax-law", "tax-mixed"]
    assert boundary["repeatCount"] == 10
    assert boundary["authorizedSummaryCalls"] == 30
    assert boundary["firstOutboundConsumesAuthorization"] is True
    assert boundary["retryAllowed"] is False
    assert boundary["resumeAllowed"] is False
    assert boundary["answerCallsAllowed"] is False
    assert boundary["p5Allowed"] is False
    assert boundary["realBusinessDataAllowed"] is False
    assert boundary["successCriteria"] == {
        "resultRecordCount": 30,
        "terminalRecordCount": 30,
        "minimumValidSummaryCount": 27,
        "minimumValidSummaryCountPerCase": 9,
        "invalidQuoteAcceptedCount": 0,
        "retryCount": 0,
        "forbiddenFieldCount": 0,
        "businessCallCount": 0,
        "logLeakCount": 0,
    }
    assert REPOSITORY / boundary["consumedMarkerPath"] == CONSUMED

    frozen = _file_records(value["frozenInputs"])
    history = _file_records(value["immutableHistory"])
    assert len(frozen) == 15
    assert len(history) == 14
    assert len({item["path"] for item in (*frozen, *history)}) == 29
    for item in frozen:
        content = subprocess.run(
            ["git", "show", f"{FROZEN_COMMIT}:{item['path']}"],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
        ).stdout
        assert hashlib.sha256(content).hexdigest() == item["sha256"], item["path"]
    for item in history:
        path = REPOSITORY / item["path"]
        assert path.is_file(), item["path"]
        assert _sha256(path) == item["sha256"], item["path"]


def test_gate043_consumed_evidence_attempt_and_journal_are_immutable_and_bound() -> None:
    assert all(path.is_file() and _sha256(path) == expected for path, expected in HISTORY_SHA256.items())

    manifest: dict[str, Any] = json.loads(MANIFEST.read_text(encoding="utf-8"))
    consumed: dict[str, Any] = json.loads(CONSUMED.read_text(encoding="utf-8"))
    evidence: dict[str, Any] = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    attempt: dict[str, Any] = json.loads(ATTEMPT.read_text(encoding="utf-8"))
    journal: list[dict[str, Any]] = [
        json.loads(line) for line in JOURNAL.read_text(encoding="utf-8").splitlines()
    ]

    assert consumed == {
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "authorizedSummaryCalls": 30,
        "closureGateId": "GATE-022",
        "consumedAt": "2026-08-12T23:35:44Z",
        "gateId": "GATE-043",
        "retryAllowed": False,
        "runId": RUN_ID,
        "schemaVersion": 1,
        "workPackageId": "WP-K-EGRESS-01",
    }

    common_binding = {
        "runId": RUN_ID,
        "workPackageId": "WP-K-EGRESS-01",
        "authorizationReference": AUTHORIZATION_REFERENCE,
    }
    for record in (manifest, consumed, evidence, attempt):
        assert {key: record[key] for key in common_binding} == common_binding
    assert manifest["authorizationGateId"] == consumed["gateId"] == evidence["authorizationGateId"]
    assert manifest["closureGateId"] == consumed["closureGateId"] == evidence["gateId"] == attempt["gateId"]
    assert _sha256(MANIFEST) == MANIFEST_SHA256

    assert evidence["taskBinding"] == manifest["taskBinding"]
    manifest_snapshot = manifest["retrievalSnapshot"]
    assert evidence["retrievalSnapshot"] == {
        "readIndex": manifest_snapshot["readIndex"],
        "readIndexUuid": manifest_snapshot["readIndexUuid"],
        "profileVersion": manifest_snapshot["retrievalProfileVersion"],
        "indexSnapshotIds": manifest_snapshot["indexSnapshotIds"],
    }
    assert evidence["catalog"]["metadataSha256"] == manifest_snapshot["metadataSha256"]
    assert evidence["catalog"]["bindingsSha256"] == manifest_snapshot["bindingsSha256"]

    assert evidence["budget"] == {
        "authorizedSummaryCalls": 30,
        "actualSummaryCalls": 30,
        "retryCount": 0,
    }
    assert evidence["validation"] == {
        "catalogValidation": "passed",
        "payloadForbiddenFieldCount": 0,
        "logLeakCount": 0,
        "schemaValidation": "passed",
        "resultRecordCount": 30,
        "terminalRecordCount": 30,
        "invalidQuoteAcceptedCount": 0,
        "businessCallCount": 0,
    }
    assert len(evidence["cases"]) == 30
    assert Counter(record["caseId"] for record in evidence["cases"]) == Counter(
        {"tax-policy": 10, "tax-law": 10, "tax-mixed": 10}
    )
    assert all(
        record["evidenceKind"] == "success"
        and record["summaryCallDelta"] == 1
        and record["quoteValidation"] == "passed"
        for record in evidence["cases"]
    )

    assert attempt["status"] == "passed"
    assert attempt["actualSummaryCalls"] == 30
    assert attempt["retryCount"] == 0
    assert attempt["payloadForbiddenFieldCount"] == 0
    assert len(attempt["caseResults"]) == 30
    assert Counter(record["caseId"] for record in attempt["caseResults"]) == Counter(
        {"tax-policy": 10, "tax-law": 10, "tax-mixed": 10}
    )
    assert all(
        record["evidenceKind"] == "success" and record["summaryCallDelta"] == 1
        for record in attempt["caseResults"]
    )

    assert len(journal) == 61
    header = journal[0]
    assert header["event"] == "attempt_started"
    assert header["runId"] == RUN_ID
    assert header["workPackageId"] == "WP-K-EGRESS-01"
    assert header["gateId"] == "GATE-022"
    assert header["authorizationReference"] == AUTHORIZATION_REFERENCE
    assert header["authorizedSummaryCalls"] == 30
    assert header["retryAllowed"] is False

    expected_cases = ["tax-policy", "tax-law", "tax-mixed"] * 10
    outbound = journal[1::2]
    terminal = journal[2::2]
    assert [(record["callOrdinal"], record["caseId"]) for record in outbound] == list(
        enumerate(expected_cases, start=1)
    )
    assert [(record["callOrdinal"], record["caseId"]) for record in terminal] == list(
        enumerate(expected_cases, start=1)
    )
    assert all(record["event"] == "outbound_started" and record["runId"] == RUN_ID for record in outbound)
    assert all(
        record["event"] == "call_terminal"
        and record["runId"] == RUN_ID
        and record["status"] == "success"
        for record in terminal
    )


def test_gate043_manifest_contains_no_questions_credentials_or_domain_records() -> None:
    raw = MANIFEST.read_text(encoding="utf-8").lower()
    assert all(
        marker not in raw
        for marker in ("增值税", "个人所得税", "身份证", "jwt", "api_key", "employee", "transaction")
    )
