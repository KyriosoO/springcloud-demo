from __future__ import annotations

from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "src" / "agent_runtime" / "adapters" / "transaction"


def test_transaction_adapter_has_only_search_and_no_java_mq_es_or_other_domain_dependency() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in SOURCE.glob("*.py"))
    for marker in ("ROLE_ADMIN", "ROLE_VIEWER", "employee", "kafka", "rabbit", "elasticsearch", "aggregate", "write", "httpx"):
        assert marker not in text.casefold()


def test_transaction_adapter_contains_no_real_endpoint_or_date_projection() -> None:
    assert "9200" not in "\n".join(path.read_text(encoding="utf-8") for path in SOURCE.glob("*.py"))
    assert not any(name in {"trans_date", "date"} for name in ("trans_id", "trans_type", "amount"))

