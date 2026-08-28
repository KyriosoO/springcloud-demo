from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
RUN_ID = "knowledge-p5-live-v3-20260828-candidate-06"
FROZEN_HEAD = "4f304fab0b52339dbbc8c75cf58ed123d88f8b02"
MANIFEST_SHA256 = "7f54ddff600726d364edee6f7c6939d99c52aa5b533ac309d98887b6e8cc51b8"
AUTHORIZATION_REFERENCE = "P3_00:GATE-077"
AUTHORIZATION_PATH = REPOSITORY_ROOT / (
    "agent-runtime/tests/evaluation/knowledge/live/evidence/"
    "knowledge-p5-live-v3-20260828-candidate-06.authorization.json"
)
RESULT_ROOT = REPOSITORY_ROOT / "agent-runtime/tests/evaluation/knowledge/results" / RUN_ID
EXPECTED_HASHES = {
    AUTHORIZATION_PATH: "b33c069cd636de69cdf2ae2fa4278eeb8385edd941d079ed2cd2fbb345117d4c",
    RESULT_ROOT / "authorization.consumed.json": "eee6a52f0ff280285b4a8d57fb7bfbf85bb8655ac24a8103ce785b4dc08f5692",
    RESULT_ROOT / "paid-attempts.jsonl": "bb858dd398426d3de4247151663822c1195c04c13b5d02d7e583db461365ac46",
    RESULT_ROOT / "phase-checkpoints.jsonl": "1bb5db868b717bc7f0f0fe56337a7ef8496121e7f5388beef481c0d0e9ade427",
    RESULT_ROOT / "failure.json": "ac2a1f913093c278cae3d174607b2d52d0b55d208fdfd0f994ca6be9abdd7a0f",
}


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert type(value) is dict
    return value


def test_candidate_06_consumed_failure_assets_are_byte_immutable() -> None:
    for path, expected in EXPECTED_HASHES.items():
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected


def test_candidate_06_failure_binding_and_terminal_counts_are_exact() -> None:
    authorization = _json(AUTHORIZATION_PATH)
    consumed = _json(RESULT_ROOT / "authorization.consumed.json")
    failure = _json(RESULT_ROOT / "failure.json")
    paid = [json.loads(line) for line in (RESULT_ROOT / "paid-attempts.jsonl").read_text(encoding="utf-8").splitlines()]
    phases = [
        json.loads(line)
        for line in (RESULT_ROOT / "phase-checkpoints.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert authorization["runId"] == consumed["runId"] == failure["runId"] == RUN_ID
    assert authorization["authorizationReference"] == consumed["authorizationReference"] == AUTHORIZATION_REFERENCE
    assert authorization["frozenHead"] == consumed["frozenGitCommit"] == failure["gitCommit"] == FROZEN_HEAD
    assert authorization["manifestSha256"] == consumed["manifestSha256"] == MANIFEST_SHA256
    assert consumed["status"] == "consumed"
    assert consumed["retryAllowed"] is False
    assert failure["failureCode"] == "snapshot_changed"

    assert len(paid) == 88
    assert [event["callOrdinal"] for event in paid[::2]] == list(range(1, 45))
    assert all(started["event"] == "started" for started in paid[::2])
    assert all(terminal["event"] == "terminal" and terminal["status"] == "completed" for terminal in paid[1::2])
    assert sum(event["taskId"] == "knowledge_rewrite" and event["event"] == "terminal" for event in paid) == 22
    assert sum(event["taskId"] == "knowledge_summary" and event["event"] == "terminal" for event in paid) == 22

    assert len(phases) == 592
    assert [event["sequence"] for event in phases] == list(range(1, 593))
    assert len({(event["caseId"], event["variant"]) for event in phases}) == 52
    assert all(event.get("status") in {None, "completed"} for event in phases)


def test_candidate_06_failure_did_not_create_effect_result() -> None:
    assert not (RESULT_ROOT / "result.json").exists()
    assert not (RESULT_ROOT / "evidence.json").exists()
