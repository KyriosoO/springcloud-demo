from __future__ import annotations

from pathlib import Path

from tests.integration.adapters.employee.egress_candidate_v2 import (
    CANDIDATE_01_HISTORY_SHA256,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[5]
EVIDENCE = ROOT / "agent-runtime/tests/integration/adapters/employee/evidence"
HISTORY_PATHS = {
    "manifest": EVIDENCE / "employee-egress-v1-20260813-candidate-01.manifest.json",
    "authorization": EVIDENCE / "employee-egress-v1-20260813-candidate-01.authorization.json",
    "environment_diagnostic": EVIDENCE / "wp-emp-egress-env-diag-01-20260814T004517Z.json",
    "pre_model_failure": (
        EVIDENCE
        / "employee-egress-v1-20260813-candidate-01.pre-model-failure-20260814T005222Z.json"
    ),
}


def test_candidate_01_four_historical_assets_are_byte_immutable() -> None:
    assert set(HISTORY_PATHS) == set(CANDIDATE_01_HISTORY_SHA256)
    for kind, path in HISTORY_PATHS.items():
        assert path.is_file()
        assert sha256_file(path) == CANDIDATE_01_HISTORY_SHA256[kind]


def test_candidate_01_was_not_reopened_for_retry_or_resume() -> None:
    forbidden_outputs = (
        EVIDENCE / "employee-egress-v1-20260813-candidate-01.authorization.consumed.json",
        EVIDENCE / "employee-egress-v1-20260813-candidate-01.attempts.jsonl",
        EVIDENCE / "employee-egress-v1-20260813-candidate-01.result.json",
    )
    assert all(not path.exists() for path in forbidden_outputs)
