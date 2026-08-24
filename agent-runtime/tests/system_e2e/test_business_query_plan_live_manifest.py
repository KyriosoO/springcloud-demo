from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from tests.system_e2e.business_query_plan_live_contracts import (
    sha256_file,
    validate_authorization_template,
    validate_manifest,
)


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "agent-runtime/tests/system_e2e/live/evidence"
RUN_ID = "business-query-plan-live-v1-20260824-candidate-01"
MANIFEST = EVIDENCE / f"{RUN_ID}.manifest.json"
AUTHORIZATION_TEMPLATE = EVIDENCE / f"{RUN_ID}.authorization-template.json"


def test_candidate_manifest_authorization_and_assets_are_frozen_unconsumed() -> None:
    manifest_sha256 = sha256_file(MANIFEST)
    manifest = validate_manifest(json.loads(MANIFEST.read_text(encoding="utf-8")))
    for asset in cast(list[dict[str, str]], manifest["assets"]):
        path = (ROOT / asset["path"]).resolve()
        assert path.is_relative_to(ROOT)
        assert sha256_file(path) == asset["sha256"]

    authorization = json.loads(AUTHORIZATION_TEMPLATE.read_text(encoding="utf-8"))
    validate_authorization_template(
        authorization,
        manifest_sha256=manifest_sha256,
        prepared_head=cast(str, manifest["preparedHead"]),
    )
    assert authorization["liveExecutionAuthorized"] is False
    assert not (ROOT / f"agent-runtime/tests/system_e2e/live/results/{RUN_ID}").exists()


def test_candidate_assets_contain_no_secret_or_runtime_value_fields() -> None:
    raw = MANIFEST.read_text(encoding="utf-8") + AUTHORIZATION_TEMPLATE.read_text(encoding="utf-8")
    for forbidden in (
        "LLM_API_KEY",
        "Authorization: Bearer",
        "employeeIdentifierValue",
        "employeeJwtValue",
        "transactionJwtValue",
    ):
        assert forbidden not in raw
