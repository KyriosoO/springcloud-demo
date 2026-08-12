from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "src/agent_runtime/knowledge/evidence/egress-policy-catalog.json"
MANIFEST = ROOT / "tests/integration/knowledge/evidence/knowledge-egress-export-20260812-01.manifest.json"
VALIDATOR = ROOT / "tools/validate_knowledge_egress_catalog.py"


def run_validator(manifest: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--catalog", str(CATALOG), "--manifest", str(manifest)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_real_catalog_matches_frozen_metadata_manifest() -> None:
    result = run_validator(MANIFEST)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed"
    assert payload["documentCount"] == 5596
    assert payload["chunkCount"] == 14783


def test_manifest_binding_drift_fails_closed(tmp_path: Path) -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    payload["documents"][0]["logicalDomainIds"] = ["tax.law"]
    drifted = tmp_path / "manifest.json"
    drifted.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    result = run_validator(drifted)

    assert result.returncode == 2
    assert json.loads(result.stdout)["code"] == "knowledge.egress_manifest_metadata_hash_mismatch"
