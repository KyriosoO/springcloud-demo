from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from knowledge_corpus_tools.b_id_mapping_v1 import (
    BIdMappingError, MappingScanSpec, scan_id_mapping_v1,
)
from knowledge_corpus_tools.vector_candidate import canonical_bytes
from test_rechunk_candidate_v1 import fingerprint, inputs


def test_readonly_source_scan_recomputes_full_fingerprint_and_exact_body_hash(
    tmp_path: Path,
) -> None:
    es, _, _ = inputs(tmp_path)
    template = es.spec(tmp_path, mode="representation", representation_binding="a" * 64)
    spec = MappingScanSpec(template.source_index, template.source_uuid,
                           template.source_mapping_sha256, fingerprint(es.source),
                           template.source_count, 2)
    with es.client() as client:
        result = scan_id_mapping_v1(spec, client=client)
    assert result.http_requests == 2
    assert es.calls == [("GET", f"/{template.source_index}"),
                        ("POST", f"/{template.source_index}/_search")]
    value = json.loads(result.raw)
    assert result.raw == canonical_bytes(value)
    assert value["sourceFingerprint"] == spec.source_fingerprint
    assert value["recordCount"] == 3
    assert [item["id"] for item in value["records"]] == sorted(es.source)
    changed = next(item for item in value["records"] if item["id"] == "old-1")
    assert changed["contentSha256"] == hashlib.sha256(
        es.source["old-1"]["content"].encode("utf-8")
    ).hexdigest()
    assert changed["contentSha256"] == es.source["old-1"]["contentHash"]


def test_scan_rejects_non_nfc_content_before_mapping_is_trusted(tmp_path: Path) -> None:
    es, _, _ = inputs(tmp_path)
    es.source["old-1"]["content"] = "Cafe\u0301 条文"
    template = es.spec(tmp_path, mode="representation", representation_binding="a" * 64)
    spec = MappingScanSpec(template.source_index, template.source_uuid,
                           template.source_mapping_sha256, fingerprint(es.source),
                           template.source_count, 2)
    with es.client() as client, pytest.raises(BIdMappingError,
                                               match="scan_records_invalid"):
        scan_id_mapping_v1(spec, client=client)


def test_scan_rejects_wrong_fingerprint_and_budget_before_extra_calls(tmp_path: Path) -> None:
    es, _, _ = inputs(tmp_path)
    template = es.spec(tmp_path, mode="representation", representation_binding="a" * 64)
    with pytest.raises(BIdMappingError, match="scan_binding_invalid"):
        MappingScanSpec(template.source_index, template.source_uuid,
                        template.source_mapping_sha256, template.source_fingerprint,
                        template.source_count, 3)
    spec = MappingScanSpec(template.source_index, template.source_uuid,
                           template.source_mapping_sha256, "f" * 64,
                           template.source_count, 2)
    with es.client() as client, pytest.raises(BIdMappingError,
                                               match="scan_fingerprint_drift"):
        scan_id_mapping_v1(spec, client=client)
    assert len(es.calls) == 2
