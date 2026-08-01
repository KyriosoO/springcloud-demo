from __future__ import annotations

from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "src" / "agent_runtime"


def test_capability_has_no_provider_or_http_dependency() -> None:
    text = (SOURCE / "knowledge" / "capability.py").read_text(encoding="utf-8")
    for marker in ("retrieval.es_adapter", "bge_embedding", "bge_rerank", "httpx", "9200", "8908", "8909"):
        assert marker not in text


def test_profile_mapping_is_code_bound_and_has_no_physical_resources() -> None:
    text = (SOURCE / "knowledge" / "retrieval" / "es_adapter.py").read_text(encoding="utf-8")
    assert '"tax.policy": "tax-policy-v1"' in text
    assert '"tax.law": "tax-law-v1"' in text
    assert "agent-doc-tax-policy" not in text
    assert "9200" not in text

