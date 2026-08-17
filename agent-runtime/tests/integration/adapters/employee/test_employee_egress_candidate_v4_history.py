from __future__ import annotations

from pathlib import Path

from tests.integration.adapters.employee.egress_candidate_v3 import (
    load_strict_json as load_v3_json,
    validate_consumed_marker as validate_v3_consumed,
    validate_lifecycle as validate_v3_lifecycle,
    validate_result as validate_v3_result,
)
from tests.integration.adapters.employee.egress_candidate_v4 import (
    HISTORY_ASSETS,
    verify_history,
)


REPOSITORY = Path(__file__).parents[5]
EVIDENCE = Path(__file__).parent / "evidence"
V3_RUN_ID = "employee-egress-v3-20260817-candidate-03"
V3_MANIFEST_SHA256 = "901ac019188e1eb15793aa93dd2add0444962f706539742ad6f5b087664ad16e"
V3_HISTORY_NAMES = {
    "egress_v3_manifest",
    "egress_v3_authorization",
    "egress_v3_lifecycle",
    "egress_v3_consumed",
    "egress_v3_result",
}


def test_candidate04_binds_all_five_candidate03_failure_assets() -> None:
    names = {name for name, _path, _sha256 in HISTORY_ASSETS}
    assert V3_HISTORY_NAMES <= names
    verify_history(REPOSITORY)


def test_candidate03_remains_failed_consumed_and_cannot_be_reclassified() -> None:
    lifecycle_path = EVIDENCE / f"{V3_RUN_ID}.lifecycle.jsonl"
    consumed_path = EVIDENCE / f"{V3_RUN_ID}.authorization.consumed.json"
    result_path = EVIDENCE / f"{V3_RUN_ID}.result.json"

    snapshot = validate_v3_lifecycle(
        lifecycle_path,
        consumed_path=consumed_path,
        manifest_sha256=V3_MANIFEST_SHA256,
    )
    consumed = validate_v3_consumed(
        load_v3_json(consumed_path), manifest_sha256=V3_MANIFEST_SHA256
    )
    result = validate_v3_result(load_v3_json(result_path))

    assert consumed["runId"] == V3_RUN_ID
    assert snapshot.status == "failed_consumed"
    assert snapshot.failure_reason == "threshold_not_met"
    assert snapshot.valid_answers == 0
    assert result["status"] == "failed_consumed"
    assert result["counts"]["modelAnswerStarted"] == 30
    assert result["counts"]["modelAnswerTerminal"] == 30
    assert result["counts"]["validAnswers"] == 0
