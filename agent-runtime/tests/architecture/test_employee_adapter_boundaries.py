from __future__ import annotations

from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "src" / "agent_runtime" / "adapters" / "employee"


def test_employee_adapter_has_no_role_java_database_or_other_domain_dependency() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in SOURCE.glob("*.py"))
    for marker in ("ROLE_ADMIN", "ROLE_VIEWER", "mq-procedure", "transaction", "sql", "repository", "httpx"):
        assert marker not in text

