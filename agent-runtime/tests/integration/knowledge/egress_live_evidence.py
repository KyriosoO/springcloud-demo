from __future__ import annotations

import json
from pathlib import Path
from typing import Any


TOP_KEYS = {
    "schemaVersion",
    "workPackageId",
    "gateId",
    "runId",
    "recordedAt",
    "authorizationReference",
    "dataBoundary",
    "catalog",
    "retrievalSnapshot",
    "budget",
    "negativeMatrix",
    "cases",
    "validation",
}
DATA_KEYS = {
    "questionKind",
    "realKnowledgeContentPersisted",
    "jwtPersisted",
    "rawModelPayloadPersisted",
    "p5Executed",
}
CATALOG_KEYS = {"catalogSha256", "metadataSha256", "bindingsSha256", "documentCount"}
SNAPSHOT_KEYS = {"readIndex", "readIndexUuid", "profileVersion", "indexSnapshotIds"}
BUDGET_KEYS = {"authorizedSummaryCalls", "actualSummaryCalls", "retryCount"}
NEGATIVE_KEYS = {"caseId", "resultKind", "denialReason", "summaryCallDelta"}
CASE_KEYS = {
    "caseId",
    "repeatOrdinal",
    "selectedDomainIds",
    "retrievalKind",
    "coverageComplete",
    "candidateCount",
    "evidenceKind",
    "summaryCallDelta",
    "pointCount",
    "quoteValidation",
}
VALIDATION_KEYS = {
    "catalogValidation",
    "payloadForbiddenFieldCount",
    "logLeakCount",
    "schemaValidation",
    "resultRecordCount",
    "terminalRecordCount",
    "invalidQuoteAcceptedCount",
    "businessCallCount",
}
CASE_IDS = ("tax-policy", "tax-law", "tax-mixed")
REPEAT_COUNT = 10
AUTHORIZED_SUMMARY_CALLS = len(CASE_IDS) * REPEAT_COUNT
ALLOWED_EVIDENCE_KINDS = {
    "success",
    "no_result",
    "model_egress_denied",
    "forbidden",
    "timeout",
    "downstream_failure",
}


class KnowledgeEgressEvidenceError(ValueError):
    pass


def _exact(value: object, keys: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise KnowledgeEgressEvidenceError("knowledge.egress_evidence_invalid")
    return value


def validate_live_evidence(value: object) -> dict[str, Any]:
    evidence = _exact(value, TOP_KEYS)
    if (
        evidence["schemaVersion"] != 1
        or evidence["workPackageId"] != "WP-K-EGRESS-01"
        or evidence["gateId"] != "GATE-022"
        or evidence["runId"] != "knowledge-egress-v1-20260812-candidate-03"
        or evidence["authorizationReference"] != "P3_00:GATE-040"
        or type(evidence["recordedAt"]) is not str
    ):
        raise KnowledgeEgressEvidenceError("knowledge.egress_evidence_invalid")
    data = _exact(evidence["dataBoundary"], DATA_KEYS)
    if data != {
        "questionKind": "fixed_non_sensitive_public_knowledge",
        "realKnowledgeContentPersisted": False,
        "jwtPersisted": False,
        "rawModelPayloadPersisted": False,
        "p5Executed": False,
    }:
        raise KnowledgeEgressEvidenceError("knowledge.egress_evidence_invalid")
    catalog = _exact(evidence["catalog"], CATALOG_KEYS)
    if (
        catalog["documentCount"] != 5596
        or any(type(catalog[key]) is not str or len(catalog[key]) != 64 for key in CATALOG_KEYS - {"documentCount"})
    ):
        raise KnowledgeEgressEvidenceError("knowledge.egress_evidence_invalid")
    snapshot = _exact(evidence["retrievalSnapshot"], SNAPSHOT_KEYS)
    if (
        snapshot["readIndex"] != "agent-doc-tax-policy-v3-20260803-agent-read-v1"
        or snapshot["readIndexUuid"] != "k97bn1gxROSfVm7zGfzbOg"
        or snapshot["profileVersion"] != "tax-knowledge-search-v1"
        or type(snapshot["indexSnapshotIds"]) is not list
        or len(snapshot["indexSnapshotIds"]) != 2
        or any(type(item) is not str or len(item) != 64 for item in snapshot["indexSnapshotIds"])
    ):
        raise KnowledgeEgressEvidenceError("knowledge.egress_evidence_invalid")
    budget = _exact(evidence["budget"], BUDGET_KEYS)
    if budget != {
        "authorizedSummaryCalls": AUTHORIZED_SUMMARY_CALLS,
        "actualSummaryCalls": AUTHORIZED_SUMMARY_CALLS,
        "retryCount": 0,
    }:
        raise KnowledgeEgressEvidenceError("knowledge.egress_evidence_invalid")
    negatives = evidence["negativeMatrix"]
    if type(negatives) is not list or len(negatives) != 2:
        raise KnowledgeEgressEvidenceError("knowledge.egress_evidence_invalid")
    expected_negatives = {
        "question-denied": "question_denied",
        "policy-missing": "policy_missing",
    }
    for item in negatives:
        negative = _exact(item, NEGATIVE_KEYS)
        if (
            negative["caseId"] not in expected_negatives
            or negative["resultKind"] != "model_egress_denied"
            or negative["denialReason"] != expected_negatives[negative["caseId"]]
            or negative["summaryCallDelta"] != 0
        ):
            raise KnowledgeEgressEvidenceError("knowledge.egress_evidence_invalid")
    cases = evidence["cases"]
    if type(cases) is not list or len(cases) != AUTHORIZED_SUMMARY_CALLS:
        raise KnowledgeEgressEvidenceError("knowledge.egress_evidence_invalid")
    success_by_case = dict.fromkeys(CASE_IDS, 0)
    expected_matrix = tuple(
        (repeat_ordinal, case_id)
        for repeat_ordinal in range(1, REPEAT_COUNT + 1)
        for case_id in CASE_IDS
    )
    for (expected_repeat_ordinal, expected_case_id), item in zip(expected_matrix, cases, strict=True):
        case = _exact(item, CASE_KEYS)
        if (
            case["caseId"] != expected_case_id
            or case["repeatOrdinal"] != expected_repeat_ordinal
            or case["retrievalKind"] != "success"
            or case["coverageComplete"] is not True
            or type(case["candidateCount"]) is not int
            or case["candidateCount"] <= 0
            or case["evidenceKind"] not in ALLOWED_EVIDENCE_KINDS
            or case["summaryCallDelta"] != 1
            or type(case["pointCount"]) is not int
            or (
                case["evidenceKind"] == "success"
                and (not 1 <= case["pointCount"] <= 5 or case["quoteValidation"] != "passed")
            )
            or (
                case["evidenceKind"] != "success"
                and (case["pointCount"] != 0 or case["quoteValidation"] != "failed")
            )
        ):
            raise KnowledgeEgressEvidenceError("knowledge.egress_evidence_invalid")
        if case["evidenceKind"] == "success":
            success_by_case[expected_case_id] += 1
    if sum(success_by_case.values()) < 27 or any(count < 9 for count in success_by_case.values()):
        raise KnowledgeEgressEvidenceError("knowledge.egress_evidence_invalid")
    validation = _exact(evidence["validation"], VALIDATION_KEYS)
    if validation != {
        "catalogValidation": "passed",
        "payloadForbiddenFieldCount": 0,
        "logLeakCount": 0,
        "schemaValidation": "passed",
        "resultRecordCount": AUTHORIZED_SUMMARY_CALLS,
        "terminalRecordCount": AUTHORIZED_SUMMARY_CALLS,
        "invalidQuoteAcceptedCount": 0,
        "businessCallCount": 0,
    }:
        raise KnowledgeEgressEvidenceError("knowledge.egress_evidence_invalid")
    raw = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(raw) > 32768:
        raise KnowledgeEgressEvidenceError("knowledge.egress_evidence_invalid")
    return evidence


def write_live_evidence(path: Path, value: object) -> None:
    evidence = validate_live_evidence(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(evidence, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
