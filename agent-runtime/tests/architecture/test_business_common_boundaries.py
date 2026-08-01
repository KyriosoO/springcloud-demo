from __future__ import annotations

from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "src" / "agent_runtime"


def test_business_common_has_no_domain_or_real_http_dependency() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in (SOURCE / "business").glob("*.py"))
    for marker in ("agent_runtime.adapters.employee", "agent_runtime.adapters.transaction", "httpx", "requests", "ROLE_ADMIN", "ROLE_VIEWER"):
        assert marker not in text


def test_core_json_contract_does_not_accept_decimal() -> None:
    contract = (SOURCE / "capability_api" / "contracts.py").read_text(encoding="utf-8")
    assert "Decimal" not in contract
    assert "ExactDecimal" not in contract

