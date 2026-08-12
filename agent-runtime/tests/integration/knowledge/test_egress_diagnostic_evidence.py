from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from tests.integration.knowledge.egress_diagnostic_evidence import (
    KnowledgeEgressDiagnosticEvidenceError,
    validate_diagnostic_evidence,
    write_diagnostic_evidence,
)


def fixture() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "workPackageId": "WP-K-EGRESS-01",
        "gateId": "GATE-022",
        "runId": "knowledge-egress-v1-20260812-diagnostic-01",
        "recordedAt": "2026-08-12T00:00:00Z",
        "mode": "real_retrieval_local_deterministic_summary",
        "dataBoundary": {
            "realKnowledgeContentPersisted": False,
            "questionPersisted": False,
            "jwtPersisted": False,
            "rawModelPayloadPersisted": False,
            "externalModelCalled": False,
            "p5Executed": False,
        },
        "catalog": {
            "catalogSha256": "a" * 64,
            "metadataSha256": "b" * 64,
            "bindingsSha256": "c" * 64,
            "documentCount": 5596,
        },
        "retrievalSnapshot": {
            "readIndex": "agent-doc-tax-policy-v3-20260803-agent-read-v1",
            "readIndexUuid": "k97bn1gxROSfVm7zGfzbOg",
            "profileVersion": "tax-knowledge-search-v1",
            "indexSnapshotIds": ["d" * 64, "e" * 64],
        },
        "localSummaryCalls": 3,
        "externalModelCalls": 0,
        "cases": [
            {
                "caseId": case_id,
                "selectedDomainIds": domains,
                "retrievalKind": "success",
                "coverageComplete": True,
                "candidateCount": 5,
                "selectedEvidenceCount": 2,
                "summaryPayloadBytes": 1024,
                "evidenceKind": "success",
                "pointCount": 1,
                "decoderValidation": "passed",
                "referenceValidation": "passed",
                "substringValidation": "passed",
                "localAssembly": "passed",
            }
            for case_id, domains in (
                ("tax-policy", ["tax.policy"]),
                ("tax-law", ["tax.law"]),
                ("tax-mixed", ["tax.policy", "tax.law"]),
            )
        ],
        "negativeMatrix": [
            {
                "caseId": case_id,
                "resultKind": result_kind,
                "reason": reason,
                "localSummaryCallDelta": 0,
                "externalModelCallDelta": 0,
            }
            for case_id, (result_kind, reason) in (
                ("question-denied", ("model_egress_denied", "question_denied")),
                ("policy-missing", ("model_egress_denied", "policy_missing")),
                ("document-denied", ("model_egress_denied", "document_denied")),
                ("policy-conflict", ("model_egress_denied", "policy_conflict")),
                ("snapshot-mismatch", ("model_egress_denied", "policy_missing")),
            )
        ],
        "validation": {"catalogValidation": "passed", "logLeakCount": 0, "schemaValidation": "passed"},
    }


def test_diagnostic_evidence_accepts_only_structural_zero_external_model_result(tmp_path: Path) -> None:
    value = fixture()
    path = tmp_path / "diagnostic.json"

    write_diagnostic_evidence(path, value)

    assert validate_diagnostic_evidence(value) == value
    raw = path.read_text(encoding="utf-8")
    assert all(
        forbidden not in raw
        for forbidden in ('"question":', '"content":', '"jwt":', "documentId", "evidenceId")
    )


@pytest.mark.parametrize(
    "field,value",
    (
        ("externalModelCalls", 1),
        ("localSummaryCalls", 2),
        ("mode", "live"),
    ),
)
def test_diagnostic_evidence_rejects_external_calls_or_incomplete_run(field: str, value: object) -> None:
    candidate = deepcopy(fixture())
    candidate[field] = value

    with pytest.raises(KnowledgeEgressDiagnosticEvidenceError):
        validate_diagnostic_evidence(candidate)
