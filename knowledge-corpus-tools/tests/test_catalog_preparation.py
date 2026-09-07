import copy
import hashlib
import json
from pathlib import Path

import pytest

from knowledge_corpus_tools.catalog_preparation import extend_catalog, profile_snapshot


def inputs():
    old = {"tax.policy": "a" * 64, "tax.law": "b" * 64}
    new = {"tax.policy": "c" * 64, "tax.law": "d" * 64}
    catalog = {
        "schemaVersion": 1, "catalogVersion": "tax-egress-catalog-v2",
        "authorityId": "authority", "exportId": "old", "sourceRevision": "old",
        "policies": [{"policyRef": "public:test", "policyVersion": "1", "disposition": "allow_minimal",
                      "allowedFields": ["content"], "maxContentCodePoints": 10}],
        "bindings": [{"documentId": "doc-1", "policyRef": "public:test", "policyVersion": "1",
                      "allowedIndexSnapshotIds": list(old.values())}],
    }
    kwargs = {"members": {"doc-1": ("public:test", frozenset({"tax.policy"}))},
              "old_snapshots": old, "new_snapshots": new, "export_id": "new", "source_revision": "new"}
    return catalog, kwargs


def test_only_actual_domain_snapshot_is_added_without_mutating_input():
    catalog, kwargs = inputs()
    original = copy.deepcopy(catalog)
    result = extend_catalog(catalog, **kwargs)
    assert catalog == original
    assert result["policies"] == catalog["policies"]
    assert result["authorityId"] == catalog["authorityId"]
    binding = result["bindings"][0]
    assert binding["allowedIndexSnapshotIds"] == ["a" * 64, "b" * 64, "c" * 64]
    assert {k: v for k, v in binding.items() if k != "allowedIndexSnapshotIds"} == {
        k: v for k, v in catalog["bindings"][0].items() if k != "allowedIndexSnapshotIds"}


def test_genuine_shared_document_retains_both_domains():
    catalog, kwargs = inputs()
    kwargs["members"]["doc-1"] = ("public:test", frozenset({"tax.policy", "tax.law"}))
    assert set(extend_catalog(catalog, **kwargs)["bindings"][0]["allowedIndexSnapshotIds"]) == {
        "a" * 64, "b" * 64, "c" * 64, "d" * 64}


@pytest.mark.parametrize("fault", [
    "missing_document", "extra_document", "duplicate_binding", "wrong_policy", "unknown_domain",
    "empty_domain", "missing_old_snapshot", "duplicate_old_snapshot", "snapshot_overflow",
    "same_new_snapshot", "reuse_snapshot", "missing_domain_snapshot", "invalid_hash",
    "unknown_binding_field", "already_migrated", "invalid_export",
])
def test_invalid_migration_never_returns_permissive_catalog(fault):
    catalog, kwargs = inputs()
    binding = catalog["bindings"][0]
    if fault == "missing_document": kwargs["members"] = {}
    elif fault == "extra_document": kwargs["members"]["doc-2"] = kwargs["members"]["doc-1"]
    elif fault == "duplicate_binding": catalog["bindings"].append(copy.deepcopy(binding))
    elif fault == "wrong_policy": kwargs["members"]["doc-1"] = ("other", frozenset({"tax.policy"}))
    elif fault == "unknown_domain": kwargs["members"]["doc-1"] = ("public:test", frozenset({"other"}))
    elif fault == "empty_domain": kwargs["members"]["doc-1"] = ("public:test", frozenset())
    elif fault == "missing_old_snapshot": binding["allowedIndexSnapshotIds"] = ["b" * 64]
    elif fault == "duplicate_old_snapshot": binding["allowedIndexSnapshotIds"].append("a" * 64)
    elif fault == "snapshot_overflow": binding["allowedIndexSnapshotIds"] += [str(i) * 64 for i in range(6)]
    elif fault == "same_new_snapshot": kwargs["new_snapshots"]["tax.law"] = "c" * 64
    elif fault == "reuse_snapshot": kwargs["new_snapshots"]["tax.policy"] = "a" * 64
    elif fault == "missing_domain_snapshot": del kwargs["new_snapshots"]["tax.law"]
    elif fault == "invalid_hash": kwargs["new_snapshots"]["tax.law"] = "bad"
    elif fault == "unknown_binding_field": binding["allowedFields"] = ["everything"]
    elif fault == "already_migrated": catalog["catalogVersion"] = "tax-egress-catalog-v3"
    elif fault == "invalid_export": kwargs["export_id"] = "bad/value"
    with pytest.raises(ValueError):
        extend_catalog(catalog, **kwargs)


def test_snapshot_matches_java_five_component_contract():
    assert profile_snapshot("tax-policy-v1", "index", "uuid", "mapping") == hashlib.sha256(
        b"tax-policy-v1\nindex\nuuid\ntax-knowledge-search-v1\nmapping").hexdigest()
    with pytest.raises(ValueError):
        profile_snapshot("arbitrary", "index", "uuid", "mapping")


def test_recorded_preparation_is_pending_and_preserves_immutable_build():
    evidence = Path(__file__).parents[1] / "evidence"
    directory = evidence / "policy-vector-publication-20260907-b2"
    expected = {
        "preparation.json": "cfce562ee4f5e69e75c511450a9598ce9cda9c721a3f07b1b117df2754c3c7d3",
        "runtime-catalog-check.json": "0fd0fd58904298c8181bc87d9e398a7b5d303020e91fc191d6b393bc9258cebd",
    }
    values = {}
    for name, sha in expected.items():
        raw = (directory / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == sha
        values[name] = json.loads(raw)
    preparation, runtime = values.values()
    build = (evidence / "policy-vector-candidate-20260907-b2/result.json").read_bytes()
    assert hashlib.sha256(build).hexdigest() == preparation["candidateResultSha256"]
    assert preparation["candidateFingerprint"] == json.loads(build)["result"]["candidate_fingerprint"]
    assert preparation["status"] == "prepared_not_activated"
    assert runtime["status"] == "passed_not_activated"
    assert preparation["catalogSha256"] == runtime["catalogSha256"]
    assert preparation["documentCount"] == runtime["documentCount"] == 5600
    assert runtime["newBindingsResolved"] == sum(runtime["newSnapshotDocumentCounts"].values()) == 5600
    assert runtime["unknownSnapshotRejected"] == 5600
    assert runtime["policiesEqual"] and runtime["currentCatalogUnchanged"]
    assert preparation["recordCounts"] == {"tax.policy": 13909, "tax.law": 1612}
    assert preparation["esReadHttp"] == 67
    assert all(preparation[key] == 0 for key in ("paid", "embedding", "esWrites", "aliasWrites"))
    assert runtime["limitations"] == ["not_typed_uat", "no_publication"]
