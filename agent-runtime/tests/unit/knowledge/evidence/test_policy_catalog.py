from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from agent_runtime.knowledge.evidence import catalog as catalog_module
from agent_runtime.knowledge.evidence.catalog import (
    KnowledgeEgressPolicyCatalog,
    KnowledgePolicyCatalogError,
    _parse_snapshot,
)


RESOURCE = Path(catalog_module.__file__).with_name("egress-policy-catalog.json")


def test_real_catalog_loads_from_fixed_hash_bound_resource() -> None:
    catalog = KnowledgeEgressPolicyCatalog.load_v1_resource()

    assert catalog.snapshot.catalog_version == "tax-egress-catalog-v1"
    assert catalog.snapshot.authority_id == "tax-knowledge-metadata-v1"
    assert len(catalog.snapshot.bindings) == 5596
    assert catalog.snapshot.source_sha256 == hashlib.sha256(RESOURCE.read_bytes()).hexdigest()
    first = catalog.snapshot.bindings[0]
    policy, binding = catalog.resolve(
        document_id=first.document_id,
        policy_ref=first.policy_ref,
        index_snapshot_id=sorted(first.allowed_index_snapshot_ids)[0],
    )
    assert policy.disposition.value == "allow_minimal"
    assert binding == first


def test_resource_hash_mismatch_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(catalog_module, "EXPECTED_KNOWLEDGE_EGRESS_CATALOG_SHA256", "0" * 64)

    with pytest.raises(KnowledgePolicyCatalogError, match="knowledge.policy_catalog_hash_mismatch"):
        KnowledgeEgressPolicyCatalog.load_v1_resource()


@pytest.mark.parametrize(
    "raw",
    (
        b'{"schemaVersion":1,"schemaVersion":1}',
        b'{"schemaVersion":1} trailing',
        b'{"schemaVersion":1,"unknown":true}',
        b'{"schemaVersion":NaN}',
    ),
)
def test_strict_catalog_decoder_rejects_duplicate_trailing_unknown_and_nonfinite(raw: bytes) -> None:
    with pytest.raises(KnowledgePolicyCatalogError, match="knowledge.policy_catalog_invalid"):
        _parse_snapshot(raw, source_sha256="a" * 64)


@pytest.mark.parametrize(
    ("field", "invalid"),
    (
        ("policyRef", 1),
        ("policyVersion", None),
        ("allowedFields", [{"not": "hashable"}]),
    ),
)
def test_strict_catalog_decoder_maps_wrong_policy_types_to_catalog_error(
    field: str,
    invalid: object,
) -> None:
    value = json.loads(RESOURCE.read_text(encoding="utf-8"))
    value["policies"][0][field] = invalid
    raw = json.dumps(value, ensure_ascii=False).encode("utf-8")

    with pytest.raises(KnowledgePolicyCatalogError, match="knowledge.policy_catalog_invalid"):
        _parse_snapshot(raw, source_sha256="a" * 64)
