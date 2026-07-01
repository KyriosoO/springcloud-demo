#!/usr/bin/env python3
"""(1) Re-run generate_contract_models.py to a temp file, (2) compare with committed."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GENERATE_SCRIPT = ROOT / "scripts" / "generate_contract_models.py"
COMMITTED = ROOT / "app" / "contracts" / "generated_models.py"
PYTHON = sys.executable


def main() -> int:
    tmp = COMMITTED.with_suffix(".tmp.py")

    # Run the full post-processed generation to temp output.
    rc = subprocess.run([
        PYTHON, str(GENERATE_SCRIPT),
        "--output", str(tmp),
    ]).returncode
    if rc != 0:
        tmp.unlink(missing_ok=True)
        print("ERROR: generate_contract_models.py failed")
        return rc

    committed_text = COMMITTED.read_text(encoding="utf-8")
    generated_text = tmp.read_text(encoding="utf-8")
    tmp.unlink()

    if generated_text.strip() != committed_text.strip():
        print("ERROR: Python generated models are out of date.")
        print(f"  Source:  agent-api/src/main/resources/openapi/agent-runtime-openapi.json")
        print(f"  Target:  {COMMITTED}")
        print(f"  Action:  cd agent-runtime && python scripts/generate_contract_models.py")
        return 1

    print("OK: generated_models.py matches OpenAPI spec.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
