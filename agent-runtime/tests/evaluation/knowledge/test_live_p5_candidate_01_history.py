from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
RUN_ID = "knowledge-p5-live-v1-20260813-candidate-01"
FROZEN_COMMIT = "d30138a8af27b89784d9d45c70a6e95d0cb90408"
MANIFEST_RELATIVE = Path(
    "agent-runtime/tests/evaluation/knowledge/live/evidence/knowledge-p5-live-v1-20260813-candidate-01.manifest.json"
)
RESULT_ROOT = Path("agent-runtime/tests/evaluation/knowledge/results") / RUN_ID
EXPECTED_HASHES = {
    MANIFEST_RELATIVE.as_posix(): "b57af536909af4b6ec9a3c02b4332b91db4f48f4b23e2c33e4a1570100de7084",
    (RESULT_ROOT / "authorization.consumed.json").as_posix(): "1f767a5887854b32255134d0f0166aa106c2be4f576b59fac396cdf74eb0349e",
    (RESULT_ROOT / "paid-attempts.jsonl").as_posix(): "94846c956d867feb42c098f6881db28dd1966643ec9335d22ee300ea21433a15",
    (RESULT_ROOT / "failure.json").as_posix(): "1162eeddee526006168653c90c7fcd59eda69d6163952a6d289b2433fe4fb3b7",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_candidate_01_failure_assets_are_append_only_and_bound() -> None:
    for relative, expected in EXPECTED_HASHES.items():
        assert _sha256(REPOSITORY_ROOT / relative) == expected

    manifest = json.loads((REPOSITORY_ROOT / MANIFEST_RELATIVE).read_text(encoding="utf-8"))
    consumed = json.loads((REPOSITORY_ROOT / RESULT_ROOT / "authorization.consumed.json").read_text(encoding="utf-8"))
    failure = json.loads((REPOSITORY_ROOT / RESULT_ROOT / "failure.json").read_text(encoding="utf-8"))
    journal = [
        json.loads(line)
        for line in (REPOSITORY_ROOT / RESULT_ROOT / "paid-attempts.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert manifest["status"] == "prepared_unconsumed"
    assert consumed["status"] == "consumed"
    assert consumed["runId"] == manifest["runId"] == failure["runId"] == RUN_ID
    assert consumed["manifestSha256"] == EXPECTED_HASHES[MANIFEST_RELATIVE.as_posix()]
    assert consumed["frozenGitCommit"] == failure["gitCommit"] == FROZEN_COMMIT
    assert failure["failureCode"] == "schema_invalid"
    assert [(item["callOrdinal"], item["event"], item.get("status")) for item in journal] == [
        (1, "started", None),
        (1, "terminal", "completed"),
        (2, "started", None),
        (2, "terminal", "completed"),
    ]


def test_candidate_01_manifest_assets_match_the_frozen_commit() -> None:
    manifest = json.loads((REPOSITORY_ROOT / MANIFEST_RELATIVE).read_text(encoding="utf-8"))
    for asset in manifest["assetHashes"]:
        frozen = subprocess.run(
            ["git", "show", f"{FROZEN_COMMIT}:{asset['path']}"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
        ).stdout
        assert hashlib.sha256(frozen).hexdigest() == asset["sha256"]
