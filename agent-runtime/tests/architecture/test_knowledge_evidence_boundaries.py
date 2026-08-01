from __future__ import annotations

from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "src" / "agent_runtime" / "knowledge" / "evidence"


def test_evidence_has_no_provider_http_es_or_role_dependency() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in SOURCE.glob("*.py"))
    for marker in ("httpx", "deepseek", "elasticsearch", "ROLE_ADMIN", "ROLE_VIEWER", "user_token"):
        assert marker not in text


def test_no_real_policy_resource_is_created_in_fake_only_slice() -> None:
    assert not (SOURCE / "egress-policy-catalog.json").exists()

