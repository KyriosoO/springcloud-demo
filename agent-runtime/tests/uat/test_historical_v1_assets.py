from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final


_UAT_ROOT: Final[Path] = Path(__file__).parent
_EXPECTED_SHA256: Final[dict[str, str]] = {
    "uat_cases.v1.json": "b10c793a29114a7d92f048156b433056cfc8a81b0646dddf0ea1e954a3f381da",
    "evidence/structured-query-uat-access-v1.result.json": (
        "0c01ceb5b0ca0c94a63cd1a930d23bc2570a9704b34d467cf44b993eb4793057"
    ),
    "evidence/structured-query-uat-closure-v1.result.json": (
        "fb55fb34cfd684986e617bf2246441a20e4a0a747549d22454aa700c2dd8b432"
    ),
    "evidence/structured-query-uat-closure-v1.schema.json": (
        "45693a48dd586b177e44643dd108bb06ca65f869c882b83ff9ff2fd4a57e6baa"
    ),
    "evidence/structured-query-uat-employee-v1.result.json": (
        "7fac2caa7a0aa3f1af80b9bb9a42ecff7a549a19941ba8928e71dd5b4e150458"
    ),
    "evidence/structured-query-uat-stage-v1.schema.json": (
        "759deadc6b67cedf43c2d74c4794db1549ec04d520aa9b68429e8616f334216c"
    ),
    "evidence/structured-query-uat-transaction-v1.result.json": (
        "88d15ee04899fb872323d15e6787dc915bcc472e9f6e477566a4531d6591203c"
    ),
}


def test_historical_detail_stub_uat_assets_remain_byte_identical_and_non_current() -> None:
    for relative, expected in _EXPECTED_SHA256.items():
        path = _UAT_ROOT / relative
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected

    current = (_UAT_ROOT / "uat_traceability.v2.json").read_text(encoding="utf-8")
    assert "employee.detail" not in current
    assert "single-agent-structured-query-uat-v1" not in current
