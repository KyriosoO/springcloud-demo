from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
FROZEN_HEAD = "e4ba0c6c5909bb04bbcd0206085e95952b2350a3"
RUN_ID = "knowledge-p5-live-v4-20260828-candidate-07"
AUTHORIZATION_REFERENCE = "P3_00:GATE-079"
MANIFEST_RELATIVE = Path(
    "agent-runtime/tests/evaluation/knowledge/live/evidence/"
    "knowledge-p5-live-v4-20260828-candidate-07.manifest.json"
)
AUTHORIZATION_RELATIVE = Path(
    "agent-runtime/tests/evaluation/knowledge/live/evidence/"
    "knowledge-p5-live-v4-20260828-candidate-07.authorization.json"
)
RESULT_ROOT = Path("agent-runtime/tests/evaluation/knowledge/results") / RUN_ID
FAILURE_RELATIVE = RESULT_ROOT / "preflight-failure.json"
EXPECTED_HASHES = {
    MANIFEST_RELATIVE.as_posix(): "af545166b37a33899d6f1d7830c09472df8cc2fe45047fea242ecc524bfc2211",
    AUTHORIZATION_RELATIVE.as_posix(): "47575441f1c9123facc19ad32210375cb919174c0260c6fc0e612740abf07a06",
    FAILURE_RELATIVE.as_posix(): "919fa1480b2ad3c7144559a3f10746ded7e0d069beae0977e0a7222e771d32d6",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_candidate_07_failed_unconsumed_assets_are_append_only_and_bound() -> None:
    for relative, expected in EXPECTED_HASHES.items():
        assert _sha256(REPOSITORY_ROOT / relative) == expected

    manifest = json.loads((REPOSITORY_ROOT / MANIFEST_RELATIVE).read_text(encoding="utf-8"))
    authorization = json.loads((REPOSITORY_ROOT / AUTHORIZATION_RELATIVE).read_text(encoding="utf-8"))
    failure = json.loads((REPOSITORY_ROOT / FAILURE_RELATIVE).read_text(encoding="utf-8"))

    assert manifest["status"] == "prepared_unconsumed"
    assert authorization["status"] == "authorized_unconsumed"
    assert failure["status"] == "failed_unconsumed"
    assert manifest["runId"] == authorization["runId"] == failure["runId"] == RUN_ID
    assert (
        manifest["authorizationReference"]
        == authorization["authorizationReference"]
        == failure["authorizationReference"]
        == AUTHORIZATION_REFERENCE
    )
    assert authorization["frozenHead"] == failure["frozenHead"] == FROZEN_HEAD
    assert authorization["manifestSha256"] == failure["manifestSha256"] == EXPECTED_HASHES[
        MANIFEST_RELATIVE.as_posix()
    ]
    assert authorization["maximumPaidRequests"] == 78
    assert failure["failureStage"] == "preflight"
    assert failure["failureReason"] == "knowledge.p5_live_preflight_failed"
    assert failure["failedCheck"] == "test_candidate_07_prepared_assets_contain_no_secret_or_live_result"
    assert failure["counts"] == {
        "modelOutbound": 0,
        "paidRequests": 0,
        "answerRequests": 0,
        "businessCalls": 0,
        "retry": 0,
        "resume": 0,
    }
    assert failure["execution"] == {
        "authorizationConsumed": False,
        "isolatedServicesStarted": False,
        "liveRunnerStarted": False,
    }
    assert sorted(path.name for path in (REPOSITORY_ROOT / RESULT_ROOT).iterdir()) == ["preflight-failure.json"]


def test_candidate_07_manifest_assets_match_frozen_head() -> None:
    manifest = json.loads((REPOSITORY_ROOT / MANIFEST_RELATIVE).read_text(encoding="utf-8"))

    assert len(manifest["assetHashes"]) == 100
    for asset in manifest["assetHashes"]:
        frozen = subprocess.run(
            ["git", "show", f"{FROZEN_HEAD}:{asset['path']}"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
        ).stdout
        assert hashlib.sha256(frozen).hexdigest() == asset["sha256"]
