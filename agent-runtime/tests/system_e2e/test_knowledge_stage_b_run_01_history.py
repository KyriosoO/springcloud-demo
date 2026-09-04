"""Read-only verification of the consumed, failed Stage B run; never rerun it."""
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).with_name("knowledge_stage_b_run_01")
REPO = Path(__file__).resolve().parents[3]
HASHES = {
    "manifest.json": "ee56673a262894a135379ae50d1d0e32d4cf3fe1051d6b8b40a55ab8da08a675",
    "consumed.json": "6a07070209e331d1cab326ffa907136a5cbeed65df84d165b2f3ef9de61b4f8d",
    "journal.jsonl": "780335f53c910e84980cf479076de6bab32d579d0a8aa6388d617d44c2218d42",
    "evidence.jsonl": "563c36d4f57ea20f45c1e46fb44368e6cd862eebd67afc9f2dc5318927d0df24",
    "result.json": "819738da2abeb58164e222356b12820739d1e98f9793da8c2aa8b174eb7035f2",
}


def read(name):
    return json.loads((ROOT / name).read_bytes())


def test_run_01_bytes_counts_failure_and_cleanup_are_immutable():
    for name, expected in HASHES.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    manifest, result = read("manifest.json"), read("result.json")
    assert set(result) == {"schemaVersion", "runId", "manifestSha256", "status", "failureKind",
                           "cases", "totals", "notExecuted"}
    assert type(result["schemaVersion"]) is int and result["schemaVersion"] == 1
    assert set(manifest) == {"schemaVersion", "runId", "frozenHead", "authorizationReference", "limits",
                             "cases", "gold", "environment", "indexBinding", "assets", "executables",
                             "taskVersions", "evaluation"}
    assert manifest["authorizationReference"] == "P3_00:WP-KRETRIEVAL-UAT-01"
    assert manifest["taskVersions"] == dict(selection="action-selection-v4", rewrite="3", summary="4")
    assert manifest["frozenHead"] == "338b387100f03f4153611b2324604c8e25466a2b"
    assert result["manifestSha256"] == HASHES["manifest.json"]
    assert result["status"] == "failed" and result["failureKind"] is None
    assert result["totals"] == dict(e2e=1, model=3, search=4, embedding=2, rerank=2,
                                    business=0, retry=0, resume=0)
    assert all(type(v) is int and 0 <= v <= manifest["limits"][k] for k, v in result["totals"].items())
    assert len(result["cases"]) == 1 and not result["cases"][0]["passed"]
    assert result["cases"][0]["caseId"] == "UAT-KB-001"
    assert result["cases"][0]["status"] == "success"  # Product outcome, not UAT verdict.
    assert result["notExecuted"] == [c["caseId"] for c in manifest["cases"]][1:]
    journal = [json.loads(line) for line in (ROOT / "journal.jsonl").read_text().splitlines()]
    assert [r["ordinal"] for r in journal] == [1, 2, 3]
    assert [r["task"] for r in journal] == ["action_selection", "knowledge_rewrite", "knowledge_summary"]
    evidence = [json.loads(line) for line in (ROOT / "evidence.jsonl").read_text().splitlines()]
    assert evidence[-1] == dict(stage="cleanup", ownedProcessesStopped=True,
                                rawLogsDeleted=True, secretScanPassed=True)
    assert next(r for r in evidence if r["stage"] == "runtime_cleanup")["clientsClosed"]
    # Frozen runner's per-case e2e field was not incremented. Never rewrite it;
    # use the immutable top-level total and case list for actual E2E accounting.
    assert result["cases"][0]["calls"]["e2e"] == 0


def test_run_01_sources_are_verified_from_frozen_commit_not_current_code():
    manifest = read("manifest.json")
    for path, expected in manifest["assets"].items():
        source = subprocess.check_output(["git", "show", f"{manifest['frozenHead']}:{path}"], cwd=REPO)
        # Repository text attributes store LF; the freeze measured working-tree
        # bytes. Reconstruct the Windows text representation without changing it.
        versions = (source, source.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        assert expected in {hashlib.sha256(v).hexdigest() for v in versions}, path


def test_run_01_retained_assets_have_no_raw_model_or_secret_fields():
    forbidden = {"apiKey", "api_key", "jwt", "token", "rawResponse", "modelResponse", "content", "quote"}

    def visit(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for name in ("result.json", "consumed.json"):
        visit(read(name))
    for name in ("journal.jsonl", "evidence.jsonl"):
        for line in (ROOT / name).read_text().splitlines():
            visit(json.loads(line))
