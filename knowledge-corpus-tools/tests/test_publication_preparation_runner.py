"""Non-live preparation guards; no real ES, services, models or publication."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import httpx
import pytest

from knowledge_corpus_tools.catalog_preparation import profile_snapshot
from knowledge_corpus_tools.vector_candidate import (
    MAPPING_VERSION, TRACE_FIELDS, _Record, _fingerprint, canonical_bytes,
)


@pytest.fixture
def runner():
    path = Path(__file__).parents[1] / "scripts/prepare-policy-vector-publication.py"
    spec = importlib.util.spec_from_file_location("publication_preparation_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def definitions():
    source = {"aliases": {"read-alias": {}}, "settings": {"index": {
        "uuid": "old-uuid", "blocks": {"write": "true"},
        "number_of_shards": "1", "number_of_replicas": "0",
    }}, "mappings": {"_meta": {"mapping_version": "old-mapping"},
                    "properties": {"content": {"type": "text"}}}}
    candidate = copy.deepcopy(source)
    candidate["aliases"] = {}
    candidate["settings"]["index"]["uuid"] = "new-uuid"
    candidate["mappings"]["_meta"]["mapping_version"] = MAPPING_VERSION
    candidate["mappings"]["properties"].update({key: {"type": "keyword"} for key in TRACE_FIELDS})
    return source, candidate


def test_exact_mapping_and_settings_allow_only_reviewed_changes(runner):
    runner.verify_candidate_definition(*definitions(), "new-uuid")


@pytest.mark.parametrize("fault", [
    "uuid", "write_block", "alias", "mapping_version", "original_field",
    "trace_type", "extra_field", "shards", "replicas", "analysis", "source_trace",
])
def test_unreviewed_changes_fail_even_if_version_matches(runner, fault):
    source, candidate = definitions()
    index = candidate["settings"]["index"]
    mapping = candidate["mappings"]
    if fault == "uuid": index["uuid"] = "other"
    elif fault == "write_block": index["blocks"]["write"] = False
    elif fault == "alias": candidate["aliases"] = {"read-alias": {}}
    elif fault == "mapping_version": mapping["_meta"]["mapping_version"] = "wrong"
    elif fault == "original_field": mapping["properties"]["content"]["type"] = "keyword"
    elif fault == "trace_type": mapping["properties"][TRACE_FIELDS[0]]["type"] = "text"
    elif fault == "extra_field": mapping["properties"]["unknown"] = {"type": "keyword"}
    elif fault == "shards": index["number_of_shards"] = "2"
    elif fault == "replicas": index["number_of_replicas"] = "1"
    elif fault == "analysis": index["analysis"] = {"analyzer": {}}
    elif fault == "source_trace": source["mappings"]["properties"][TRACE_FIELDS[0]] = {"type": "keyword"}
    with pytest.raises(AssertionError):
        runner.verify_candidate_definition(source, candidate, "new-uuid")


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'[]', b' ' * (4 * 1024 * 1024 + 1)],
                         ids=["duplicate_key", "non_finite", "array", "oversized"])
def test_bounded_strict_input(runner, tmp_path, raw):
    path = tmp_path / "invalid.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        runner.read_json(path)


@pytest.mark.parametrize("fault", [None, "write_attempt", "budget", "fingerprint", "membership", "source_drift"])
def test_full_fake_preparation_preserves_current_files_and_never_writes_es(
    runner, monkeypatch, tmp_path, capsys, fault,
):
    source, candidate = definitions()
    spec = {
        "source_index": "source", "source_uuid": "old-uuid", "mapping_sha256": "a" * 64,
        "source_fingerprint": "b" * 64, "total_count": 2, "policy_count": 1, "attachment_count": 1,
        "candidate_index": "agent-doc-tax-policy-v5-20260907-vector-b2", "model_snapshot_sha256": "c" * 64,
    }
    records = tuple(_Record(identifier=f"record-{i}", chunk_id=f"chunk-{i}", fields={
        "documentId": f"doc-{i}", "aclRef": "public:test", "channel": channel,
    }, vector=b"fake", seq_no=0, primary_term=1) for i, channel in enumerate(("财税文件", "法律")))
    old_snapshots = {domain: profile_snapshot(profile, "source", "old-uuid", "old-mapping")
                     for domain, profile in (("tax.policy", "tax-policy-v1"), ("tax.law", "tax-law-v1"))}
    old_binding = {"schemaVersion": 1, "readAlias": "read-alias", "expectedIndexName": "source",
                   "expectedIndexUuid": "old-uuid", "mappingVersion": "old-mapping",
                   "policySnapshotId": old_snapshots["tax.policy"], "lawSnapshotId": old_snapshots["tax.law"]}
    catalog = {"schemaVersion": 1, "catalogVersion": "tax-egress-catalog-v2", "authorityId": "authority",
               "exportId": "old", "sourceRevision": "old", "policies": [{"policyRef": "public:test"}],
               "bindings": [{"documentId": f"doc-{i}", "policyRef": "public:test", "policyVersion": "1",
                             "allowedIndexSnapshotIds": [old_snapshots[domain]]}
                            for i, domain in enumerate(("tax.policy", "tax.law"))]}
    binding = {"spec": spec}
    result = {"status": "built_read_only_unpublished", "bindingSha256": hashlib.sha256(canonical_bytes(binding)).hexdigest(),
              "result": {"candidate_uuid": "new-uuid", "candidate_fingerprint": _fingerprint(records)}}
    values = {"binding.json": binding, "result.json": result, "knowledge-runtime-binding.v1.json": old_binding,
              "egress-policy-catalog-v2.json": catalog}
    original = copy.deepcopy(values)
    monkeypatch.setattr(runner, "read_json", lambda path: (canonical_bytes(values[path.name]), values[path.name]))
    monkeypatch.setattr(runner, "OLD_CATALOG_SHA", hashlib.sha256(canonical_bytes(catalog)).hexdigest())
    monkeypatch.setattr(runner, "BUILD_RESULT_SHA", hashlib.sha256(canonical_bytes(result)).hexdigest())
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={})
    monkeypatch.setattr(runner.httpx, "HTTPTransport", lambda **kwargs: httpx.MockTransport(respond))

    class FakeBuild:
        def __init__(self, spec, client):
            self.client = client
            self.calls = 0
            self.source_calls = 0
        def read(self, path):
            self.client.get(path)
            self.calls += 1
        def source(self):
            self.read("/source")
            self.source_calls += 1
            if fault == "source_drift" and self.source_calls > 1:
                return {**source, "aliases": {}}
            return source
        def definition(self, index):
            self.read("/" + index)
            return candidate
        def scan(self, index):
            if fault == "write_attempt":
                self.client.post("/_aliases", json={})
            if fault == "budget":
                for _ in range(81):
                    self.read("/" + index)
            self.read("/" + index + "/_search")
            if fault == "fingerprint": return records[:1]
            if fault == "membership": records[0].fields["aclRef"] = "other"
            return records

    monkeypatch.setattr(runner, "_Build", FakeBuild)
    destination = tmp_path / "pending"
    monkeypatch.setattr(sys, "argv", ["prepare", "--candidate-directory", str(tmp_path),
                                     "--output-directory", str(destination)])
    if fault:
        with pytest.raises((AssertionError, ValueError)):
            runner.main()
        assert not destination.exists()
    else:
        runner.main()
        evidence = json.loads((destination / "preparation.json").read_text())
        assert evidence["status"] == "prepared_not_activated"
        assert evidence["documentCount"] == 2
        assert evidence["esReadHttp"] == len(requests) == 5
        assert all(evidence[key] == 0 for key in ("paid", "embedding", "esWrites", "aliasWrites"))
        assert evidence["oldBindingsPreserved"] is True
        assert evidence["policiesChanged"] is False
        assert "runtime_loader_validation_pending" in evidence["limitations"]
        updated = json.loads((destination / "egress-policy-catalog-v3.json").read_text())
        assert updated["policies"] == catalog["policies"]
        before = len(requests)
        with pytest.raises(ValueError, match="output_exists"):
            runner.main()
        assert len(requests) == before
        assert "doc-0" not in capsys.readouterr().out
    assert values == original
    assert all(request.method == "GET" for request in requests)
    assert len(requests) <= 80


def test_optimized_interpreter_stops_before_io_and_emits_only_finite_failure(tmp_path):
    script = Path(__file__).parents[1] / "scripts/prepare-policy-vector-publication.py"
    result = subprocess.run([sys.executable, "-O", str(script), "--candidate-directory", str(tmp_path),
                             "--output-directory", str(tmp_path / "out")],
                            check=False, capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    assert json.loads(result.stdout) == {"status": "failed", "reason": "publication_preparation_failed_no_retry"}
    assert result.stderr == ""
    assert not (tmp_path / "out").exists()
