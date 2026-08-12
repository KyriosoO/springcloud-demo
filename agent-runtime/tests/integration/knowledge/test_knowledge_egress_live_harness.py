from __future__ import annotations

from copy import deepcopy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.integration.knowledge.egress_live_evidence import (
    KnowledgeEgressEvidenceError,
    validate_live_evidence,
)


def fixture() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "workPackageId": "WP-K-EGRESS-01",
        "gateId": "GATE-022",
        "runId": "knowledge-egress-v1-20260812-candidate-03",
        "recordedAt": "2026-08-12T00:00:00Z",
        "authorizationReference": "P3_00:GATE-040",
        "dataBoundary": {
            "questionKind": "fixed_non_sensitive_public_knowledge",
            "realKnowledgeContentPersisted": False,
            "jwtPersisted": False,
            "rawModelPayloadPersisted": False,
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
        "budget": {"authorizedSummaryCalls": 30, "actualSummaryCalls": 30, "retryCount": 0},
        "negativeMatrix": [
            {"caseId": "question-denied", "resultKind": "model_egress_denied", "denialReason": "question_denied", "summaryCallDelta": 0},
            {"caseId": "policy-missing", "resultKind": "model_egress_denied", "denialReason": "policy_missing", "summaryCallDelta": 0},
        ],
        "cases": [
            {
                "caseId": case_id,
                "repeatOrdinal": repeat_ordinal,
                "selectedDomainIds": domains,
                "retrievalKind": "success",
                "coverageComplete": True,
                "candidateCount": 5,
                "evidenceKind": "success",
                "summaryCallDelta": 1,
                "pointCount": 1,
                "quoteValidation": "passed",
            }
            for repeat_ordinal in range(1, 11)
            for case_id, domains in (
                ("tax-policy", ["tax.policy"]),
                ("tax-law", ["tax.law"]),
                ("tax-mixed", ["tax.policy", "tax.law"]),
            )
        ],
        "validation": {
            "catalogValidation": "passed",
            "payloadForbiddenFieldCount": 0,
            "logLeakCount": 0,
            "schemaValidation": "passed",
            "resultRecordCount": 30,
            "terminalRecordCount": 30,
            "invalidQuoteAcceptedCount": 0,
            "businessCallCount": 0,
        },
    }


def test_limited_live_evidence_contract_accepts_safe_thirty_call_threshold_result() -> None:
    value = fixture()

    assert validate_live_evidence(value) == value
    keys: set[str] = set()

    def collect_keys(item: object) -> None:
        if isinstance(item, dict):
            keys.update(item)
            for child in item.values():
                collect_keys(child)
        elif isinstance(item, list):
            for child in item:
                collect_keys(child)

    collect_keys(value)
    assert not keys & {"jwt", "content", "documentId", "evidenceId", "question", "rawModelPayload"}


@pytest.mark.parametrize(
    "mutation",
    (
        lambda value: value["budget"].update(actualSummaryCalls=29),
        lambda value: value["budget"].update(retryCount=1),
        lambda value: value["cases"][0].update(summaryCallDelta=0),
        lambda value: value["validation"].update(invalidQuoteAcceptedCount=1),
        lambda value: value.update(rawPayload="forbidden"),
    ),
)
def test_evidence_contract_rejects_budget_retry_case_and_unknown_field(
    mutation: Callable[[dict[str, Any]], None],
) -> None:
    value = deepcopy(fixture())
    mutation(value)

    with pytest.raises(KnowledgeEgressEvidenceError):
        validate_live_evidence(value)


def test_evidence_contract_accepts_one_failure_per_case_but_rejects_case_below_nine_of_ten() -> None:
    threshold = fixture()
    for index in (0, 1, 2):
        threshold["cases"][index].update(
            evidenceKind="downstream_failure",
            pointCount=0,
            quoteValidation="failed",
        )
    assert validate_live_evidence(threshold) == threshold

    below_threshold = deepcopy(threshold)
    below_threshold["cases"][3].update(
        evidenceKind="downstream_failure",
        pointCount=0,
        quoteValidation="failed",
    )
    with pytest.raises(KnowledgeEgressEvidenceError):
        validate_live_evidence(below_threshold)


def test_live_runner_moves_journal_before_temporary_cleanup_on_success_and_failure() -> None:
    root = Path(__file__).resolve().parents[3]
    script = (root / "scripts/run-knowledge-egress-live.ps1").read_text(encoding="utf-8")

    assert "AGENT_KNOWLEDGE_EGRESS_JOURNAL_OUTPUT" in script
    assert "AGENT_KNOWLEDGE_EGRESS_RUN_ID" in script
    assert "AGENT_KNOWLEDGE_EGRESS_AUTHORIZATION_REFERENCE" in script
    assert "$AuthorizedRunId -ne $expectedRunId" in script
    assert "$AuthorizationReference -ne $expectedAuthorizationReference" in script
    assert "$actualManifestSha256 -ne $AuthorizedManifestSha256" in script
    binding_guard = script.index("knowledge.egress_live_authorization_binding_invalid")
    assert binding_guard < script.index("GetEnvironmentVariable('LLM_API_KEY'")
    assert binding_guard < script.index("Start-Process -FilePath 'java'")
    assert "$expectedRunId = 'knowledge-egress-v1-20260812-candidate-03'" in script
    assert "$expectedAuthorizationReference = 'P3_00:GATE-040'" in script
    assert "python -m tests.integration.knowledge.egress_attempt_journal $stagedJournal $stagedAttempt" in script
    assert script.index("tests.integration.knowledge.egress_attempt_journal") < script.index(
        "Move-Item -LiteralPath $stagedJournal"
    )
    assert script.count("Move-Item -LiteralPath $stagedJournal") == 2
    assert script.rfind("Move-Item -LiteralPath $stagedJournal") < script.rfind(
        "Remove-Item -LiteralPath $resolvedRunRoot -Recurse -Force"
    )
