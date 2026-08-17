from __future__ import annotations

from pathlib import Path

from tests.integration.adapters.transaction.egress_candidate_v2 import (
    RUN_ID,
    consumed_path_for,
    lifecycle_path_for,
    load_strict_json,
    result_path_for,
    sha256_file,
)


EVIDENCE = Path(__file__).resolve().parent / "evidence"
FAILURE = EVIDENCE / f"{RUN_ID}.initialization-failure.json"
FAILURE_SHA256 = "37c4cf079cf1bb28e17c9b087df5707bf19c5bbfd8318d6c3f5f611f08fd72d9"


def test_candidate02_initialization_failure_is_exact_and_unconsumed() -> None:
    assert sha256_file(FAILURE) == FAILURE_SHA256
    value = load_strict_json(FAILURE)

    assert set(value) == {
        "schemaVersion",
        "evidenceKind",
        "workPackageId",
        "gateId",
        "runId",
        "status",
        "recordedAt",
        "frozenHead",
        "manifestSha256",
        "authorizationReference",
        "failure",
        "authorization",
        "counts",
        "safety",
        "gateDecision",
    }
    assert value["schemaVersion"] == 1
    assert value["evidenceKind"] == "post_run_initialization_diagnosis"
    assert value["workPackageId"] == "WP-TXN-EGRESS-01"
    assert value["gateId"] == "GATE-026"
    assert value["runId"] == RUN_ID
    assert value["frozenHead"] == "4a271966de8fab75e648da15c0f4cdc57ba35f09"
    assert value["manifestSha256"] == (
        "527845915ad15aa6f24fe59ed31885dcd3fef245109e7cee820217a86cbafa9c"
    )
    assert value["status"] == "failed_unconsumed"
    assert value["failure"] == {
        "phase": "pytest_collection",
        "reason": "transaction.candidate_python_import_path_missing",
        "exceptionType": "ModuleNotFoundError",
        "missingModule": "agent_runtime",
        "evidenceStrength": "reproduced_non_live",
        "candidateLifecycleCreated": False,
    }
    assert value["counts"] == {
        "databaseSelectorStatements": 1,
        "candidateLauncherInvocations": 1,
        "transactionSearchRequests": 0,
        "otherTransactionEndpoints": 0,
        "modelOutboundRequests": 0,
        "paidModelRequests": 0,
        "retryCount": 0,
        "resumeCount": 0,
    }
    assert value["authorization"] == {
        "modelOutboundConsumed": False,
        "retryPerformed": False,
        "resumePerformed": False,
        "rerunAllowedByThisEvidence": False,
    }
    assert value["safety"] == {
        "transactionTypePersisted": False,
        "jwtPersisted": False,
        "transactionDataPersisted": False,
        "rawModelResponsePersisted": False,
        "rawLogsDeleted": True,
        "temporaryRunDirectoryDeleted": True,
        "ownedProcessesStopped": True,
        "logLeakCount": 0,
    }
    assert value["gateDecision"] == {
        "gate026": "Open",
        "transactionScopeSaGate006": "Open",
        "gate034": "Open",
        "workPackage": "Blocked",
        "reason": (
            "candidate-02 did not reach lifecycle, Transaction search, or model "
            "outbound; its one-shot execution was attempted and must not be rerun"
        ),
    }

    assert not lifecycle_path_for(EVIDENCE).exists()
    assert not consumed_path_for(EVIDENCE).exists()
    assert not result_path_for(EVIDENCE).exists()
