"""Bind existing JDK25 before any startup side effect; no global environment edits."""
from contextlib import contextmanager
import os
from pathlib import Path
import re
import shutil
import subprocess
from unittest.mock import patch

from tests.system_e2e import knowledge_stage_b_uat_v10 as previous

RUN_ID = "knowledge-stage-b-uat-v11-20260909-run-11"
REFERENCE = "P3_00:WP-KRETRIEVAL-UAT-01/run-11"
JAVA_ROOT = Path("C:/Program Files/Java/jdk-25.0.2")
TOTAL_LIMITS = {**previous.TOTAL_LIMITS, "rerank": 49}
PREFLIGHT_ROOT = Path(__file__).with_name("knowledge_stage_b_run_10")
HASHES = {
    "manifest.json": "c8d1605700a23a72e85155a957570f11fad31cee2dfc3b5860a8beb5ffceaccf",
    "startup.jsonl": "c833763dfb7b728fc5abb79eae9af93a30eb91dfabbc050542c32c4b0c37a7b2",
    "environment.jsonl": "47c722d5dd46790257be65356d314908ff55a773f53209d022b24a5ae0e113f6",
}
_manifest = previous.current_manifest
legacy = previous.previous.legacy


def java_binding():
    executable = JAVA_ROOT / "bin/java.exe"
    resolved = shutil.which("java")
    if resolved is None or Path(resolved).resolve() != executable.resolve():
        raise ValueError("stage_b.java_resolution_invalid")
    result = subprocess.run([str(executable), "-version"], capture_output=True, timeout=10, check=True)
    match = re.search(rb'version "(\d+(?:\.\d+)+)"', result.stderr)
    if match is None or match.group(1).split(b".")[0] != b"25":
        raise ValueError("stage_b.java_version_invalid")
    return dict(path=str(executable.resolve()), version=match.group(1).decode("ascii"),
                sha256=legacy.digest(executable.read_bytes()))


@contextmanager
def java_environment():
    saved = {key: os.environ.get(key) for key in ("JAVA_HOME", "PATH")}
    os.environ.update(JAVA_HOME=str(JAVA_ROOT), PATH=str(JAVA_ROOT / "bin") + os.pathsep + (saved["PATH"] or ""))
    try:
        java_binding()  # Must precede prepare, warmup, owned processes, and credentials.
        yield
    finally:
        for key, value in saved.items():
            if value is None: os.environ.pop(key, None)
            else: os.environ[key] = value


def current_manifest(root):
    binding = java_binding()
    if set(p.name for p in PREFLIGHT_ROOT.iterdir()) != set(HASHES) or any(
            legacy.digest((PREFLIGHT_ROOT / name).read_bytes()) != sha for name, sha in HASHES.items()):
        raise ValueError("stage_b.prior_preflight_changed")
    value = _manifest(root)
    value.update(schemaVersion=11, javaBinding=binding,
                 failedPreflight=dict(runId="knowledge-stage-b-uat-v10-20260909-run-10", hashes=HASHES, model=0, startupRerank=1))
    # The preflight is not a formal E2E attempt, but its startup inference is still counted.
    used = sum(row["calls"]["rerank"] + row["startupCalls"].get("rerank", 0) for row in value["priorRuns"])
    if used + 1 + value["limits"]["rerank"] + value["startupLimits"]["rerank"] > TOTAL_LIMITS["rerank"]:
        raise ValueError("stage_b.cumulative_budget_invalid")
    return value


@contextmanager
def overrides():
    with patch.multiple(previous, RUN_ID=RUN_ID, REFERENCE=REFERENCE, TOTAL_LIMITS=TOTAL_LIMITS,
                        current_manifest=current_manifest), previous.overrides():
        yield


if __name__ == "__main__":
    with java_environment(), overrides():
        previous.previous.main()
