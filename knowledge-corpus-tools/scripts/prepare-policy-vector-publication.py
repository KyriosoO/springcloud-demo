"""Read-only candidate verification and pending catalog/Profile preparation; never publish."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import httpx

from knowledge_corpus_tools.catalog_preparation import extend_catalog, profile_snapshot
from knowledge_corpus_tools.jsonio import exclusive_write
from knowledge_corpus_tools.vector_candidate import (
    MAPPING_VERSION, POLICY_CATEGORIES, TRACE_FIELDS, VectorCandidateSpec, _Build, _fingerprint,
    _reject_constant, _unique_pairs, _write_blocked, canonical_bytes,
)

OLD_CATALOG_SHA = "76dcbfa6da01b76b431417e5b540f7a540fd9daa352a61c36d1bb9fdc31b2a9b"
BUILD_RESULT_SHA = "71f08b8be07738ce2925b2931387ff9e5ec1c1b3840b7fbb6a0273a0664de518"
LAW_CATEGORIES = frozenset({"法律", "行政法规"})


def read_json(path: Path) -> tuple[bytes, dict[str, Any]]:
    with path.open("rb") as stream:
        raw = stream.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError("input_size_limit")
    value = json.loads(raw, object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
    if type(value) is not dict:
        raise ValueError("input_shape_invalid")
    return raw, value


def verify_candidate_definition(
    source: dict[str, Any], candidate: dict[str, Any], expected_uuid: str,
) -> None:
    """Only the reviewed four trace fields and mapping version may differ."""
    index = candidate["settings"]["index"]
    assert index["uuid"] == expected_uuid
    assert _write_blocked(index) and candidate["aliases"] == {}
    mapping = source["mappings"]
    assert not set(TRACE_FIELDS) & set(mapping["properties"])
    expected_mapping = {
        **mapping,
        "_meta": {**mapping.get("_meta", {}), "mapping_version": MAPPING_VERSION},
        "properties": {**mapping["properties"], **{key: {"type": "keyword"} for key in TRACE_FIELDS}},
    }
    assert candidate["mappings"] == expected_mapping
    for key in ("number_of_shards", "number_of_replicas", "analysis"):
        assert index.get(key) == source["settings"]["index"].get(key)


def main() -> None:
    if not __debug__:
        raise RuntimeError("optimized_interpreter_not_supported")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    destination = args.output_directory.resolve()
    if destination.exists():
        raise ValueError("output_exists")
    root = Path(__file__).resolve().parents[2]
    binding_raw, binding = read_json(args.candidate_directory / "binding.json")
    result_raw, result = read_json(args.candidate_directory / "result.json")
    assert hashlib.sha256(result_raw).hexdigest() == BUILD_RESULT_SHA
    assert result["status"] == "built_read_only_unpublished"
    assert result["bindingSha256"] == hashlib.sha256(binding_raw).hexdigest()
    spec = VectorCandidateSpec(**binding["spec"])
    old_binding_raw, old_binding = read_json(root / "serviceCenter/knowledge-runtime-binding.v1.json")
    catalog_raw, catalog = read_json(root / "agent-runtime/src/agent_runtime/knowledge/evidence/egress-policy-catalog-v2.json")
    assert hashlib.sha256(catalog_raw).hexdigest() == OLD_CATALOG_SHA
    assert old_binding["expectedIndexName"] == spec.source_index
    assert old_binding["expectedIndexUuid"] == spec.source_uuid
    old_snapshots = {domain: profile_snapshot(profile, spec.source_index, spec.source_uuid,
                                             old_binding["mappingVersion"])
                     for domain, profile in (("tax.policy", "tax-policy-v1"), ("tax.law", "tax-law-v1"))}
    assert old_snapshots == {"tax.policy": old_binding["policySnapshotId"], "tax.law": old_binding["lawSnapshotId"]}
    request_count = 0
    def read_only_budget(request: httpx.Request) -> None:
        nonlocal request_count
        if request_count >= 80 or not (request.method == "GET" or (
            request.method == "POST" and request.url.path == f"/{spec.candidate_index}/_search"
        )):
            raise ValueError("read_only_budget_violation")
        request_count += 1
    with httpx.Client(base_url="http://127.0.0.1:9200", timeout=30, trust_env=False,
                      follow_redirects=False, transport=httpx.HTTPTransport(retries=0),
                      event_hooks={"request": [read_only_budget]}) as client:
        check = _Build(spec, client)
        source = check.source()
        assert source["aliases"] == {old_binding["readAlias"]: {}}
        candidate = check.definition(spec.candidate_index)
        uuid = candidate["settings"]["index"]["uuid"]
        verify_candidate_definition(source, candidate, result["result"]["candidate_uuid"])
        records = check.scan(spec.candidate_index)
        assert _fingerprint(records) == result["result"]["candidate_fingerprint"]
        assert len(records) == spec.total_count
        members: dict[str, tuple[str, frozenset[str]]] = {}
        counts = {"tax.policy": 0, "tax.law": 0}
        for record in records:
            fields = record.fields
            channel = fields["channel"]
            domain = "tax.policy" if channel in POLICY_CATEGORIES else "tax.law" if channel in LAW_CATEGORIES else None
            assert domain is not None
            counts[domain] += 1
            identifier, policy_ref = fields["documentId"], fields["aclRef"]
            assert type(identifier) is str and type(policy_ref) is str
            previous = members.get(identifier, (policy_ref, frozenset()))
            assert previous[0] == policy_ref
            members[identifier] = (policy_ref, previous[1] | frozenset({domain}))
        assert counts["tax.policy"] == spec.policy_count
        new_snapshots = {domain: profile_snapshot(profile, spec.candidate_index, uuid, MAPPING_VERSION)
                         for domain, profile in (("tax.policy", "tax-policy-v1"), ("tax.law", "tax-law-v1"))}
        updated = extend_catalog(catalog, members=members, old_snapshots=old_snapshots,
                                 new_snapshots=new_snapshots,
                                 export_id="tax-egress-export-20260907-vector-b2",
                                 source_revision="vector-b2-" + hashlib.sha256(result_raw).hexdigest())
        updated_raw = canonical_bytes(updated)
        pending_binding = {**old_binding, "expectedIndexName": spec.candidate_index,
                           "expectedIndexUuid": uuid, "mappingVersion": MAPPING_VERSION,
                           "policySnapshotId": new_snapshots["tax.policy"], "lawSnapshotId": new_snapshots["tax.law"]}
        assert check.source() == source and check.definition(spec.candidate_index) == candidate
        assert check.calls == request_count
    finite = {"schemaVersion": 1, "status": "prepared_not_activated", "esReadHttp": check.calls,
              "candidateResultSha256": hashlib.sha256(result_raw).hexdigest(),
              "candidateFingerprint": result["result"]["candidate_fingerprint"],
              "sourceBindingSha256": hashlib.sha256(old_binding_raw).hexdigest(),
              "sourceCatalogSha256": OLD_CATALOG_SHA, "catalogSha256": hashlib.sha256(updated_raw).hexdigest(),
              "pendingBindingSha256": hashlib.sha256(canonical_bytes(pending_binding)).hexdigest(),
              "recordCounts": counts, "documentCount": len(members), "policyCount": len(updated["policies"]),
              "snapshotIds": new_snapshots, "policiesChanged": False, "oldBindingsPreserved": True,
              "paid": 0, "embedding": 0, "esWrites": 0, "aliasWrites": 0,
              "limitations": ["runtime_loader_validation_pending", "not_typed_uat", "no_publication"]}
    destination.mkdir(parents=True, exist_ok=False)
    exclusive_write(destination / "egress-policy-catalog-v3.json", updated_raw)
    exclusive_write(destination / "runtime-binding.pending.json", canonical_bytes(pending_binding))
    exclusive_write(destination / "preparation.json", canonical_bytes(finite))
    print(json.dumps(finite, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    exit_code = 1
    try:
        main()
        exit_code = 0
    except Exception:
        print('{"status":"failed","reason":"publication_preparation_failed_no_retry"}')
    raise SystemExit(exit_code)
