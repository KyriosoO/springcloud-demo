from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path

import pytest

from agent_runtime.knowledge.evidence import catalog as catalog_module
from agent_runtime.knowledge.evidence.catalog import (
    KnowledgeEgressPolicyCatalog,
    KnowledgePolicyCatalogError,
    _parse_snapshot,
)


RESOURCE = Path(catalog_module.__file__).with_name("egress-policy-catalog.json")
V2_RESOURCE = Path(catalog_module.__file__).with_name("egress-policy-catalog-v2.json")
CURRENT_RESOURCE = Path(catalog_module.__file__).with_name("egress-policy-catalog-v3.json")
V2_POLICY_SNAPSHOT = "5e7323100b1bfd44e7452e3ce409ff146800961c07a077b2585b670665b03136"
V2_LAW_SNAPSHOT = "b537176bf80323178aaaa1ca328f1534641b62f2671d8aa2e136fcef63495104"
CURRENT_POLICY_SNAPSHOT = "8bb0918b1a8e6edd9bc2b88b23bb99571810b1423796b27ed3287e92a82d6025"
CURRENT_LAW_SNAPSHOT = "522d4da243e338196143a92bf7e57ed6dffa063c9abd009892e2a5ed8fa8a7a3"


def test_all_versioned_catalogs_are_in_installed_package_data() -> None:
    project = Path(__file__).resolve().parents[4] / "pyproject.toml"
    config = tomllib.loads(project.read_text(encoding="utf-8"))
    assert config["tool"]["setuptools"]["package-data"]["agent_runtime.knowledge.evidence"] == [
        "egress-policy-catalog.json", "egress-policy-catalog-v2.json", "egress-policy-catalog-v3.json",
    ]


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


def test_current_catalog_adds_candidate_snapshot_and_attachment_bindings() -> None:
    catalog = KnowledgeEgressPolicyCatalog.load_current_resource()

    assert catalog.snapshot.catalog_version == "tax-egress-catalog-v3"
    assert len(catalog.snapshot.bindings) == 5600
    assert catalog.snapshot.source_sha256 == hashlib.sha256(CURRENT_RESOURCE.read_bytes()).hexdigest()
    attachment_id = "tax-50abf52b7a181b8974c97fd4@asset-0b9c99e7dfb27c8e600743d7"
    policy, binding = catalog.resolve(
        document_id=attachment_id,
        policy_ref="public:tax_policy",
        index_snapshot_id=CURRENT_POLICY_SNAPSHOT,
    )
    assert policy.disposition.value == "allow_minimal"
    assert binding.document_id == attachment_id
    law_binding = next(
        item
        for item in catalog.snapshot.bindings
        if CURRENT_LAW_SNAPSHOT in item.allowed_index_snapshot_ids
    )
    law_policy, resolved_law_binding = catalog.resolve(
        document_id=law_binding.document_id,
        policy_ref=law_binding.policy_ref,
        index_snapshot_id=CURRENT_LAW_SNAPSHOT,
    )
    assert law_policy.disposition.value == "allow_minimal"
    assert resolved_law_binding == law_binding


def test_v3_adds_only_same_domain_snapshot_and_preserves_v2_policy_and_history() -> None:
    old = KnowledgeEgressPolicyCatalog.load_v2_resource()
    current = KnowledgeEgressPolicyCatalog.load_current_resource()
    assert old.snapshot.catalog_version == "tax-egress-catalog-v2"
    assert old.snapshot.export_id == "tax-egress-export-20260903-corpus-a5"
    assert old.snapshot.source_sha256 == hashlib.sha256(V2_RESOURCE.read_bytes()).hexdigest()
    assert old.snapshot.policies == current.snapshot.policies
    previous = {item.document_id: item for item in old.snapshot.bindings}
    assert len(previous) == len(current.snapshot.bindings) == 5600
    counts = {CURRENT_POLICY_SNAPSHOT: 0, CURRENT_LAW_SNAPSHOT: 0}
    for binding in current.snapshot.bindings:
        before = previous[binding.document_id]
        assert (binding.policy_ref, binding.policy_version) == (before.policy_ref, before.policy_version)
        expected = CURRENT_POLICY_SNAPSHOT if V2_POLICY_SNAPSHOT in before.allowed_index_snapshot_ids else CURRENT_LAW_SNAPSHOT
        if expected == CURRENT_LAW_SNAPSHOT:
            assert V2_LAW_SNAPSHOT in before.allowed_index_snapshot_ids
        assert binding.allowed_index_snapshot_ids == before.allowed_index_snapshot_ids | {expected}
        counts[expected] += 1
        current.resolve(document_id=binding.document_id, policy_ref=binding.policy_ref, index_snapshot_id=expected)
        with pytest.raises(KnowledgePolicyCatalogError, match="knowledge.policy_missing"):
            current.resolve(document_id=binding.document_id, policy_ref=binding.policy_ref, index_snapshot_id="0" * 64)
    assert counts == {CURRENT_POLICY_SNAPSHOT: 5463, CURRENT_LAW_SNAPSHOT: 137}


def test_launcher_defaults_to_v2_binding_but_v1_remains_available() -> None:
    root = Path(__file__).resolve().parents[5]
    source = (root / "serviceCenter/run-all-services.ps1").read_text(encoding="utf-8")
    assert "Join-Path $PSScriptRoot 'knowledge-runtime-binding.v2.json'" in source
    old = json.loads((root / "serviceCenter/knowledge-runtime-binding.v1.json").read_text())
    current = json.loads((root / "serviceCenter/knowledge-runtime-binding.v2.json").read_text())
    assert set(old) == set(current) and old["readAlias"] == current["readAlias"]
    assert (old["policySnapshotId"], old["lawSnapshotId"]) == (V2_POLICY_SNAPSHOT, V2_LAW_SNAPSHOT)
    assert (current["policySnapshotId"], current["lawSnapshotId"]) == (CURRENT_POLICY_SNAPSHOT, CURRENT_LAW_SNAPSHOT)
    assert old["expectedIndexUuid"] != current["expectedIndexUuid"]


def test_resource_hash_mismatch_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(catalog_module, "EXPECTED_KNOWLEDGE_EGRESS_CATALOG_SHA256", "0" * 64)

    with pytest.raises(KnowledgePolicyCatalogError, match="knowledge.policy_catalog_hash_mismatch"):
        KnowledgeEgressPolicyCatalog.load_v1_resource()


def test_current_resource_hash_mismatch_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        catalog_module,
        "EXPECTED_CURRENT_KNOWLEDGE_EGRESS_CATALOG_SHA256",
        "0" * 64,
    )

    with pytest.raises(KnowledgePolicyCatalogError, match="knowledge.policy_catalog_hash_mismatch"):
        KnowledgeEgressPolicyCatalog.load_current_resource()


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
