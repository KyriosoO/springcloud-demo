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
    "mode",
    "dataBoundary",
    "catalog",
    "retrievalSnapshot",
    "localSummaryCalls",
    "externalModelCalls",
    "cases",
    "negativeMatrix",
    "validation",
}
DATA_KEYS = {
    "realKnowledgeContentPersisted",
    "questionPersisted",
    "jwtPersisted",
    "rawModelPayloadPersisted",
    "externalModelCalled",
    "p5Executed",
}
CATALOG_KEYS = {"catalogSha256", "metadataSha256", "bindingsSha256", "documentCount"}
SNAPSHOT_KEYS = {"readIndex", "readIndexUuid", "profileVersion", "indexSnapshotIds"}
CASE_KEYS = {
    "caseId",
    "selectedDomainIds",
    "retrievalKind",
    "coverageComplete",
    "candidateCount",
    "selectedEvidenceCount",
    "summaryPayloadBytes",
    "evidenceKind",
    "pointCount",
    "decoderValidation",
    "referenceValidation",
    "substringValidation",
    "localAssembly",
}
NEGATIVE_KEYS = {"caseId", "resultKind", "reason", "localSummaryCallDelta", "externalModelCallDelta"}
VALIDATION_KEYS = {"catalogValidation", "logLeakCount", "schemaValidation"}
CASE_IDS = ("tax-policy", "tax-law", "tax-mixed")
NEGATIVE_EXPECTED = {
    "question-denied": ("model_egress_denied", "question_denied"),
    "policy-missing": ("model_egress_denied", "policy_missing"),
    "document-denied": ("model_egress_denied", "document_denied"),
    "policy-conflict": ("model_egress_denied", "policy_conflict"),
    "snapshot-mismatch": ("model_egress_denied", "policy_missing"),
}


class KnowledgeEgressDiagnosticEvidenceError(ValueError):
    pass


def _exact(value: object, keys: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise KnowledgeEgressDiagnosticEvidenceError("knowledge.egress_diagnostic_evidence_invalid")
    return value


def validate_diagnostic_evidence(value: object) -> dict[str, Any]:
    evidence = _exact(value, TOP_KEYS)
    if (
        evidence["schemaVersion"] != 1
        or evidence["workPackageId"] != "WP-K-EGRESS-01"
        or evidence["gateId"] != "GATE-022"
        or evidence["runId"] != "knowledge-egress-v1-20260812-diagnostic-01"
        or evidence["mode"] != "real_retrieval_local_deterministic_summary"
        or type(evidence["recordedAt"]) is not str
        or evidence["localSummaryCalls"] != 3
        or evidence["externalModelCalls"] != 0
    ):
        raise KnowledgeEgressDiagnosticEvidenceError("knowledge.egress_diagnostic_evidence_invalid")
    data = _exact(evidence["dataBoundary"], DATA_KEYS)
    if data != {
        "realKnowledgeContentPersisted": False,
        "questionPersisted": False,
        "jwtPersisted": False,
        "rawModelPayloadPersisted": False,
        "externalModelCalled": False,
        "p5Executed": False,
    }:
        raise KnowledgeEgressDiagnosticEvidenceError("knowledge.egress_diagnostic_evidence_invalid")
    catalog = _exact(evidence["catalog"], CATALOG_KEYS)
    if (
        catalog["documentCount"] != 5596
        or any(type(catalog[key]) is not str or len(catalog[key]) != 64 for key in CATALOG_KEYS - {"documentCount"})
    ):
        raise KnowledgeEgressDiagnosticEvidenceError("knowledge.egress_diagnostic_evidence_invalid")
    snapshot = _exact(evidence["retrievalSnapshot"], SNAPSHOT_KEYS)
    if (
        snapshot["readIndex"] != "agent-doc-tax-policy-v3-20260803-agent-read-v1"
        or snapshot["readIndexUuid"] != "k97bn1gxROSfVm7zGfzbOg"
        or snapshot["profileVersion"] != "tax-knowledge-search-v1"
        or type(snapshot["indexSnapshotIds"]) is not list
        or len(snapshot["indexSnapshotIds"]) != 2
        or any(type(item) is not str or len(item) != 64 for item in snapshot["indexSnapshotIds"])
    ):
        raise KnowledgeEgressDiagnosticEvidenceError("knowledge.egress_diagnostic_evidence_invalid")
    cases = evidence["cases"]
    if type(cases) is not list or len(cases) != 3:
        raise KnowledgeEgressDiagnosticEvidenceError("knowledge.egress_diagnostic_evidence_invalid")
    for expected_case_id, item in zip(CASE_IDS, cases, strict=True):
        case = _exact(item, CASE_KEYS)
        if (
            case["caseId"] != expected_case_id
            or case["retrievalKind"] != "success"
            or case["coverageComplete"] is not True
            or type(case["candidateCount"]) is not int
            or case["candidateCount"] <= 0
            or type(case["selectedEvidenceCount"]) is not int
            or not 1 <= case["selectedEvidenceCount"] <= 8
            or type(case["summaryPayloadBytes"]) is not int
            or not 1 <= case["summaryPayloadBytes"] <= 32768
            or case["evidenceKind"] != "success"
            or case["pointCount"] != 1
            or any(case[key] != "passed" for key in ("decoderValidation", "referenceValidation", "substringValidation", "localAssembly"))
        ):
            raise KnowledgeEgressDiagnosticEvidenceError("knowledge.egress_diagnostic_evidence_invalid")
    negatives = evidence["negativeMatrix"]
    if type(negatives) is not list or len(negatives) != len(NEGATIVE_EXPECTED):
        raise KnowledgeEgressDiagnosticEvidenceError("knowledge.egress_diagnostic_evidence_invalid")
    if [item.get("caseId") for item in negatives if isinstance(item, dict)] != list(NEGATIVE_EXPECTED):
        raise KnowledgeEgressDiagnosticEvidenceError("knowledge.egress_diagnostic_evidence_invalid")
    for item in negatives:
        negative = _exact(item, NEGATIVE_KEYS)
        expected = NEGATIVE_EXPECTED[negative["caseId"]]
        if (
            (negative["resultKind"], negative["reason"]) != expected
            or negative["localSummaryCallDelta"] != 0
            or negative["externalModelCallDelta"] != 0
        ):
            raise KnowledgeEgressDiagnosticEvidenceError("knowledge.egress_diagnostic_evidence_invalid")
    validation = _exact(evidence["validation"], VALIDATION_KEYS)
    if validation != {"catalogValidation": "passed", "logLeakCount": 0, "schemaValidation": "passed"}:
        raise KnowledgeEgressDiagnosticEvidenceError("knowledge.egress_diagnostic_evidence_invalid")
    raw = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(raw) > 32768:
        raise KnowledgeEgressDiagnosticEvidenceError("knowledge.egress_diagnostic_evidence_invalid")
    return evidence


def write_diagnostic_evidence(path: Path, value: object) -> None:
    evidence = validate_diagnostic_evidence(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(evidence, stream, ensure_ascii=False, indent=2)
        stream.write("\n")

