from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from agent_runtime.knowledge.evidence.summary_task_v2 import SUMMARY_PROMPT_V2, KnowledgeSummaryTaskV2


ROOT = Path(__file__).resolve().parents[3]
REPOSITORY = ROOT.parent
MANIFEST = ROOT / "tests/integration/knowledge/evidence/knowledge-egress-v2-20260812-candidate-01.manifest.json"
MANIFEST_SHA256 = "712ecedd405083e85090b525d25250d5e1dff58084a76ab4a0970c06dbeb4405"
CONSUMED = ROOT / "tests/integration/knowledge/evidence/gate043-knowledge-egress-v2-20260812-candidate-01.consumed.json"
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
    assert value["runId"] == "knowledge-egress-v2-20260812-candidate-01"
    assert value["workPackageId"] == "WP-K-EGRESS-01"
    assert value["closureGateId"] == "GATE-022"
    assert value["authorizationGateId"] == "GATE-043"
    assert value["authorizationReference"] == "P3_00:GATE-043"
    assert value["status"] == "prepared_unconsumed"
    assert not CONSUMED.exists()

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
    for item in (*frozen, *history):
        path = REPOSITORY / item["path"]
        assert path.is_file(), item["path"]
        assert _sha256(path) == item["sha256"], item["path"]


def test_gate043_manifest_contains_no_questions_credentials_or_domain_records() -> None:
    raw = MANIFEST.read_text(encoding="utf-8").lower()
    assert all(
        marker not in raw
        for marker in ("增值税", "个人所得税", "身份证", "jwt", "api_key", "employee", "transaction")
    )
