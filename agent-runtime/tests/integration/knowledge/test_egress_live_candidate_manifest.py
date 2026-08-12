from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "tests/integration/knowledge/evidence/knowledge-egress-v1-20260812-candidate-02.manifest.json"
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
    "authorizedSummaryCalls",
    "firstOutboundConsumesAuthorization",
    "retryAllowed",
    "resumeAllowed",
    "answerCallsAllowed",
    "p5Allowed",
    "realBusinessDataAllowed",
    "consumedMarkerPath",
}
FILE_KEYS = {"path", "sha256"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _files(value: object) -> list[dict[str, Any]]:
    assert type(value) is list and value
    assert all(type(item) is dict and set(item) == FILE_KEYS for item in value)
    return value


def test_candidate_02_manifest_is_exact_hash_bound_and_unconsumed() -> None:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert type(value) is dict and set(value) == TOP_KEYS
    assert value["schemaVersion"] == 1
    assert value["runId"] == "knowledge-egress-v1-20260812-candidate-02"
    assert value["workPackageId"] == "WP-K-EGRESS-01"
    assert value["closureGateId"] == "GATE-022"
    assert value["authorizationGateId"] == "GATE-039"
    assert value["authorizationReference"] == "P3_00:GATE-039"
    assert value["status"] == "prepared_unconsumed"
    boundary = value["executionBoundary"]
    assert type(boundary) is dict and set(boundary) == BOUNDARY_KEYS
    assert boundary == {
        "caseIds": ["tax-policy", "tax-law", "tax-mixed"],
        "authorizedSummaryCalls": 3,
        "firstOutboundConsumesAuthorization": True,
        "retryAllowed": False,
        "resumeAllowed": False,
        "answerCallsAllowed": False,
        "p5Allowed": False,
        "realBusinessDataAllowed": False,
        "consumedMarkerPath": "agent-runtime/tests/integration/knowledge/evidence/gate039-knowledge-egress-v1-20260812-candidate-02.consumed.json",
    }
    assert not (ROOT.parent / boundary["consumedMarkerPath"]).exists()
    for item in (*_files(value["frozenInputs"]), *_files(value["immutableHistory"])):
        path = ROOT.parent / item["path"]
        assert path.is_file(), item["path"]
        assert _sha256(path) == item["sha256"], item["path"]


def test_candidate_manifest_contains_no_questions_credentials_or_real_domain_data() -> None:
    raw = MANIFEST.read_text(encoding="utf-8").lower()
    assert all(
        marker not in raw
        for marker in ("增值税", "个人所得税", "身份证", "jwt", "api_key", "employee", "transaction")
    )
