from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from knowledge_corpus_tools.errors import ContractError, StateConflict
from knowledge_corpus_tools.models import ParsedDocument
from knowledge_corpus_tools.normalization_v2 import (
    CorpusDocumentV2,
    FieldAssertion,
    MetadataV2,
    ParsedSourceV2,
    RelationV2,
    SourceAssertionV2,
    TemporalV2,
    TrustStatus,
    asserted_field,
    asserted_raw_field,
    build_document_v2,
    document_version_id,
    freeze_raw_record,
    load_document_v2,
    load_parsed_source_v2,
    parsed_source_v2,
    resolve_official_source_url,
    validate_relations_v2,
    validate_source_span,
    v2_json_bytes,
    write_v2_artifacts,
)

NOW = datetime(2026, 2, 27, 11, 4, 29, tzinfo=UTC)
SHA = "a" * 64
RAW = {
    "title": "e\u0301 税法", "channel": "法律", "content": "第一条\n正文", "document_number": "甲〔2026〕1号",
    "effect_level": "法律", "tax_type": "增值税,消费税", "aging": "部分失效", "labels": "主题甲,主题乙",
    "issuing_department": "某机关", "written_date": "2026-02-27", "url": "/zcfgk/c100009/example.html",
}


def raw_record():
    return freeze_raw_record(json.dumps(RAW, ensure_ascii=False).encode("utf-8"))


def dataset_source(*, snapshot: str = "revision-1", raw_sha: str | None = None) -> SourceAssertionV2:
    return SourceAssertionV2.model_validate_json(json.dumps({
        "kind": "dataset", "sourceRecordId": "row:stable-1", "sourceSnapshot": snapshot,
        "datasetRepo": "salpt/chinatax-policy-corpus", "datasetRevision": "revision-1",
        "collectedAt": NOW.isoformat(), "originalUrl": RAW["url"],
        "licenseRef": "dataset-card@revision-1", "rawRecordRef": "raw/records/row-1.json",
        "rawHashScope": "source_record_canonical_json_v1", "rawSha256": raw_sha or raw_record().canonical_sha256,
    }, ensure_ascii=False))


def temporal(**overrides: object) -> TemporalV2:
    payload = {"snapshotAt": NOW.isoformat()}
    payload.update(overrides)
    return TemporalV2.model_validate_json(json.dumps(payload, ensure_ascii=False))


def parsed(*, parser_name: str = "pypdf-structured", asset_sha: str = SHA,
           blocks: list[dict[str, object]] | None = None) -> ParsedDocument:
    payload = {
        "schema_version": 1, "asset_id": "asset-1", "asset_sha256": asset_sha,
        "parser_name": parser_name, "parser_version": "1.2.0" if parser_name == "python-docx" else "6.16.2+structure-v1",
        "ocr_status": "not_applied", "quality_status": "accepted",
        "blocks": blocks or [
            {"ordinal": 1, "kind": "heading", "text": "第一章 😀"},
            {"ordinal": 2, "kind": "clause", "text": "第一条 正文"},
        ],
    }
    return ParsedDocument.model_validate_json(json.dumps(payload, ensure_ascii=False))


def document(*, source: SourceAssertionV2 | None = None, relations: RelationV2 | None = None, parsed_source=None):
    actual_source = source or dataset_source()
    return build_document_v2(
        document_id="doc-1", source=actual_source, metadata=MetadataV2(), temporal=temporal(),
        relations=relations or RelationV2(), raw_record=raw_record(), parsed_source=parsed_source,
        parsed_source_ref="parsed/source-v2.json" if parsed_source else None,
    )


def test_raw_11_fields_are_exact_and_not_nfc_rewritten() -> None:
    frozen = raw_record()
    assert json.loads(frozen.canonical_json)["title"] == RAW["title"]
    assert frozen.canonical_sha256 == hashlib.sha256(frozen.canonical_json).hexdigest()
    assert not frozen.canonical_json.endswith(b"\n")
    with pytest.raises(ContractError, match="exact 11"):
        freeze_raw_record(json.dumps({**RAW, "unknown": 1}, ensure_ascii=False).encode("utf-8"))
    with pytest.raises(ContractError, match="exact 11"):
        freeze_raw_record(json.dumps({key: value for key, value in RAW.items() if key != "url"}, ensure_ascii=False).encode("utf-8"))
    with pytest.raises(ContractError, match="duplicate"):
        freeze_raw_record(b'{"title":1,"title":2}')
    with pytest.raises(ContractError, match="non-finite"):
        freeze_raw_record(json.dumps({**RAW, "content": float("nan")}).encode("utf-8"))
    for field, value in (("title", {"text": "错误"}), ("content", ["错误正文"]),
                         ("url", 42), ("tax_type", ["增值税", 42])):
        with pytest.raises(ContractError, match="invalid raw field types"):
            freeze_raw_record(json.dumps({**RAW, field: value}, ensure_ascii=False).encode("utf-8"))
    retained_array = freeze_raw_record(json.dumps({**RAW, "tax_type": ["增值税", "消费税"]},
                                                  ensure_ascii=False).encode("utf-8"))
    assert json.loads(retained_array.canonical_json)["tax_type"] == ["增值税", "消费税"]


def test_sidecar_version_hash_is_stable_and_source_assertion_changes_identity() -> None:
    first = document()
    assert first == document()
    assert first.document_version_id == document_version_id("doc-1", dataset_source())
    assert first.normalized_sha256 == hashlib.sha256(
        json.dumps(first.model_dump(mode="json", by_alias=True, exclude={"normalized_sha256"}),
                   ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    assert document(source=dataset_source(snapshot="revision-2")).document_version_id != first.document_version_id
    with pytest.raises(ContractError, match="hash mismatch"):
        document(source=dataset_source(raw_sha="b" * 64))
    assert load_document_v2(v2_json_bytes(first)) == first
    assert "content" not in first.model_dump_json()


def test_sidecar_rejects_unknown_duplicate_and_tampered_hash() -> None:
    original = document().model_dump(mode="json", by_alias=True)
    with pytest.raises(ValidationError, match="Extra inputs"):
        load_document_v2(json.dumps({**original, "onlineParentFetch": True}).encode("utf-8"))
    with pytest.raises(ContractError, match="duplicate"):
        load_document_v2(b'{"schemaVersion":2,"schemaVersion":2}')
    with pytest.raises(ValidationError, match="normalizedSha256 mismatch"):
        load_document_v2(json.dumps({**original, "normalizedSha256": "0" * 64}).encode("utf-8"))


def test_v2_json_schemas_are_closed_and_internal() -> None:
    for model in (CorpusDocumentV2, ParsedSourceV2):
        schema = model.model_json_schema()
        assert schema["additionalProperties"] is False
        assert all(definition["additionalProperties"] is False for definition in schema["$defs"].values()
                   if "properties" in definition)
        assert "unitId" not in schema["properties"]


def test_metadata_requires_field_provenance_and_never_infers_effective_date() -> None:
    field = asserted_field("e\u0301", origin="source", source_ref="raw:title", observed_at=NOW)
    labels = asserted_field(("甲", "甲", "e\u0301"), origin="source", source_ref="raw:labels", observed_at=NOW)
    raw_channel = asserted_raw_field("e\u0301", source_ref="raw:channel", observed_at=NOW)
    metadata = MetadataV2.model_validate({"title": field, "labelsRaw": labels, "channelRaw": raw_channel})
    assert metadata.title.value == "é"
    assert metadata.labels_raw.value == ("甲", "é")
    assert metadata.channel_raw.value == "e\u0301"
    assert metadata.applicable_subjects.value is None
    with pytest.raises(ValidationError, match="sourceRef"):
        FieldAssertion.model_validate_json(b'{"value":"current","origin":"source"}')
    with pytest.raises(ValidationError, match="inferred"):
        FieldAssertion.model_validate_json(b'{"value":"current","origin":"inferred","sourceRef":"x","observedAt":"2026-01-01T00:00:00Z"}')
    written = asserted_field("2026-02-27", origin="source", source_ref="raw:written_date", observed_at=NOW)
    legacy = asserted_raw_field("2026-02-27", source_ref="old:effectiveDate", observed_at=NOW)
    dates = TemporalV2.model_validate({"writtenDate": written, "legacyEffectiveDateRaw": legacy, "snapshotAt": NOW})
    assert dates.effective_from.value is None
    assert dates.status_verified_at is None


def test_source_raw_assertions_are_checked_before_document_is_built() -> None:
    title = asserted_field("伪造标题", origin="source", source_ref="raw:title", observed_at=NOW)
    with pytest.raises(ContractError, match="does not match frozen raw"):
        build_document_v2(document_id="doc-1", source=dataset_source(),
                          metadata=MetadataV2.model_validate({"title": title}), temporal=temporal(),
                          relations=RelationV2(), raw_record=raw_record())
    written = asserted_field("2025-01-01", origin="source", source_ref="raw:written_date", observed_at=NOW)
    with pytest.raises(ContractError, match="does not match frozen raw"):
        build_document_v2(document_id="doc-1", source=dataset_source(), metadata=MetadataV2(),
                          temporal=TemporalV2.model_validate({"writtenDate": written, "snapshotAt": NOW}),
                          relations=RelationV2(), raw_record=raw_record())
    correct = asserted_field(RAW["title"], origin="source", source_ref="raw:title", observed_at=NOW)
    sidecar = build_document_v2(document_id="doc-1", source=dataset_source(),
                                metadata=MetadataV2.model_validate({"title": correct}), temporal=temporal(),
                                relations=RelationV2(), raw_record=raw_record())
    assert sidecar.metadata.title.value == "é 税法"
    forged_url = dataset_source().model_dump(mode="json", by_alias=True)
    forged_url["originalUrl"] = "/forged-source.html"
    with pytest.raises(ContractError, match="original URL differs"):
        document(source=SourceAssertionV2.model_validate_json(json.dumps(forged_url, ensure_ascii=False)))
    missing_url_raw = freeze_raw_record(json.dumps({**RAW, "url": ""}, ensure_ascii=False).encode("utf-8"))
    unknown_url_source = dataset_source(raw_sha=missing_url_raw.canonical_sha256).model_dump(mode="json", by_alias=True)
    unknown_url_source["originalUrl"] = None
    unknown_url_document = build_document_v2(
        document_id="doc-1", source=SourceAssertionV2.model_validate_json(json.dumps(unknown_url_source)),
        metadata=MetadataV2(), temporal=temporal(), relations=RelationV2(), raw_record=missing_url_raw,
    )
    assert unknown_url_document.source.original_url is None
    assert unknown_url_document.review_status is TrustStatus.UNVERIFIED


def test_temporal_partial_invalid_and_contradictory_dates_fail_closed() -> None:
    raw_aging = asserted_raw_field(RAW["aging"], source_ref="raw:aging", observed_at=NOW)
    dates = TemporalV2.model_validate({"validityRaw": raw_aging, "snapshotAt": NOW})
    assert dates.validity_raw.value == RAW["aging"]
    assert dates.validity_status.value is None
    assert dates.status_verified_at is None
    raw_only = build_document_v2(document_id="doc-1", source=dataset_source(), metadata=MetadataV2(),
                                 temporal=dates, relations=RelationV2(), raw_record=raw_record())
    assert raw_only.review_status is TrustStatus.UNVERIFIED
    guessed_status = asserted_field("partially_invalid", origin="source", source_ref="raw:aging", observed_at=NOW)
    with pytest.raises(ContractError, match="no verifiable raw field binding"):
        build_document_v2(
            document_id="doc-1", source=dataset_source(), metadata=MetadataV2(),
            temporal=TemporalV2.model_validate({"validityStatus": guessed_status,
                                                "validityMappingVersion": "unconfirmed", "snapshotAt": NOW}),
            relations=RelationV2(), raw_record=raw_record(),
        )
    guessed_type = asserted_field("law", origin="source", source_ref="raw:channel", observed_at=NOW)
    with pytest.raises(ContractError, match="no verifiable raw field binding"):
        build_document_v2(document_id="doc-1", source=dataset_source(),
                          metadata=MetadataV2.model_validate({"documentType": guessed_type}),
                          temporal=temporal(), relations=RelationV2(), raw_record=raw_record())
    start = asserted_field("2026-12-31", origin="manual_verified", source_ref="official:span-1", observed_at=NOW)
    end = asserted_field("2026-01-01", origin="manual_verified", source_ref="official:span-2", observed_at=NOW)
    bad_dates = TemporalV2.model_validate({"effectiveFrom": start, "effectiveTo": end, "snapshotAt": NOW})
    sidecar = build_document_v2(
        document_id="doc-1", source=dataset_source(), metadata=MetadataV2(), temporal=bad_dates,
        relations=RelationV2(), raw_record=raw_record(),
    )
    assert sidecar.review_status is TrustStatus.REVIEW_REQUIRED
    tampered = sidecar.model_dump(mode="json", by_alias=True)
    tampered["reviewStatus"] = "verified"
    tampered["normalizedSha256"] = hashlib.sha256(json.dumps(
        {key: value for key, value in tampered.items() if key != "normalizedSha256"},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    with pytest.raises(ValidationError, match="contradictory effective dates"):
        load_document_v2(json.dumps(tampered).encode("utf-8"))


def test_missing_raw_body_cannot_be_promoted_by_verified_parsed_structure() -> None:
    missing_body = freeze_raw_record(json.dumps({**RAW, "content": None}, ensure_ascii=False).encode("utf-8"))
    source_payload = dataset_source(raw_sha=missing_body.canonical_sha256).model_dump(mode="json", by_alias=True)
    source_payload.update({"assetId": "asset-1", "assetVersion": SHA})
    source = SourceAssertionV2.model_validate_json(json.dumps(source_payload, ensure_ascii=False))
    verified_parsed = parsed_source_v2(parsed(), order_proof_ref="independent:order",
                                       structure_proof_ref="independent:boundaries")
    sidecar = build_document_v2(document_id="doc-1", source=source, metadata=MetadataV2(), temporal=temporal(),
                                relations=RelationV2(), raw_record=missing_body, parsed_source=verified_parsed,
                                parsed_source_ref="parsed/source-v2.json")
    assert sidecar.review_status is TrustStatus.UNVERIFIED


def test_parsed_source_uses_exact_lf_codepoint_spans_and_old_docx_is_not_verified() -> None:
    source = parsed_source_v2(parsed(), order_proof_ref="independent:asset-order", structure_proof_ref="independent:boundaries")
    assert source.text == "第一章 😀\n第一条 正文"
    assert source.blocks[1].start == len("第一章 😀\n")
    assert source.order_status is TrustStatus.VERIFIED
    assert source.structure_status is TrustStatus.VERIFIED
    assert load_parsed_source_v2(v2_json_bytes(source)) == source
    body = source.text[source.blocks[1].start:source.blocks[1].end]
    validate_source_span(source, start=source.blocks[1].start, end=source.blocks[1].end,
                         content=body, body_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest())
    with pytest.raises(ContractError, match="exact continuous"):
        validate_source_span(source, start=0, end=2, content="错误", body_sha256=SHA)
    empty_block = source.model_dump(mode="json", by_alias=True)
    empty_block["blocks"][1]["end"] = empty_block["blocks"][1]["start"]
    with pytest.raises(ValidationError, match="parsed block order/span mismatch"):
        load_parsed_source_v2(json.dumps(empty_block, ensure_ascii=False).encode("utf-8"))
    legacy = parsed_source_v2(parsed(parser_name="python-docx", blocks=[
        {"ordinal": 1, "kind": "paragraph", "text": "前段"},
        {"ordinal": 2, "kind": "table", "text": "表头 | 值"},
        {"ordinal": 3, "kind": "paragraph", "text": "后段"},
    ]))
    assert legacy.order_status is TrustStatus.REVIEW_REQUIRED
    assert legacy.structure_status is TrustStatus.REVIEW_REQUIRED
    with pytest.raises(ContractError, match="later parser-order repair"):
        parsed_source_v2(parsed(parser_name="python-docx"), order_proof_ref="asserted")
    assert "unitId" not in CorpusDocumentV2.model_json_schema()["properties"]


def test_relation_validation_uses_full_parent_inventory_and_rejects_conflicts() -> None:
    relation = RelationV2.model_validate_json(b'{"relationType":"attachment","parentDocumentId":"parent-outside-sample","parentSourceRef":"official:link"}')
    attachment = document(relations=relation)
    validate_relations_v2((attachment,), all_parent_document_ids=frozenset({"parent-outside-sample"}))
    with pytest.raises(ContractError, match="parent is absent"):
        validate_relations_v2((attachment,), all_parent_document_ids=frozenset())
    self_parent = RelationV2.model_validate_json(b'{"relationType":"attachment","parentDocumentId":"doc-1","parentSourceRef":"official:link"}')
    with pytest.raises(ValidationError, match="itself"):
        document(relations=self_parent)
    with pytest.raises(ValidationError, match="exact source"):
        RelationV2.model_validate_json(b'{"revises":["doc-2"]}')


def test_revision_cycle_and_same_assertion_different_raw_are_rejected() -> None:
    first_relation = RelationV2.model_validate_json(b'{"revises":["doc-2"],"revisionSourceRef":"official:revision"}')
    second_relation = RelationV2.model_validate_json(b'{"replaces":["doc-1"],"revisionSourceRef":"official:revision"}')
    first = document(relations=first_relation)
    second = build_document_v2(document_id="doc-2", source=dataset_source(), metadata=MetadataV2(),
                               temporal=temporal(), relations=second_relation, raw_record=raw_record())
    with pytest.raises(ContractError, match="cycle"):
        validate_relations_v2((first, second), all_parent_document_ids=frozenset({"doc-1", "doc-2"}))
    changed_raw = freeze_raw_record(json.dumps({**RAW, "title": "另一标题"}, ensure_ascii=False).encode("utf-8"))
    conflicting = build_document_v2(document_id="doc-1", source=dataset_source(raw_sha=changed_raw.canonical_sha256),
                                    metadata=MetadataV2(), temporal=temporal(), relations=RelationV2(),
                                    raw_record=changed_raw)
    with pytest.raises(ContractError, match="conflicting raw content"):
        validate_relations_v2((document(), conflicting), all_parent_document_ids=frozenset({"doc-1"}))
    source_with_asset = dataset_source().model_dump(mode="json", by_alias=True)
    source_with_asset.update({"assetId": "asset-1", "assetVersion": SHA})
    source_with_changed_asset = {**source_with_asset, "assetVersion": "b" * 64}
    first_asset = document(source=SourceAssertionV2.model_validate_json(json.dumps(source_with_asset)))
    second_asset = document(source=SourceAssertionV2.model_validate_json(json.dumps(source_with_changed_asset)))
    with pytest.raises(ContractError, match="conflicting raw content"):
        validate_relations_v2((first_asset, second_asset), all_parent_document_ids=frozenset({"doc-1"}))


def test_append_only_writer_keeps_raw_separate_and_never_overwrites(tmp_path) -> None:
    sidecar = document()
    path = write_v2_artifacts(workspace=tmp_path, document=sidecar, raw_record=raw_record())
    assert path.parent == tmp_path / "manifests" / "corpus-document-v2"
    assert load_document_v2(path.read_bytes()) == sidecar
    assert json.loads((tmp_path / "raw" / "records" / "row-1.json").read_bytes())["content"] == RAW["content"]
    assert b'"content"' not in path.read_bytes()
    assert write_v2_artifacts(workspace=tmp_path, document=sidecar, raw_record=raw_record()) == path
    path.write_bytes(b"another assertion")
    with pytest.raises(StateConflict, match="existing immutable sidecar differs"):
        write_v2_artifacts(workspace=tmp_path, document=sidecar, raw_record=raw_record())
    assert path.read_bytes() == b"another assertion"


def test_unlinked_document_source_claim_rejects_changed_raw_before_any_new_write(tmp_path) -> None:
    first = document()
    write_v2_artifacts(workspace=tmp_path, document=first, raw_record=raw_record())
    changed_raw = freeze_raw_record(json.dumps({**RAW, "content": "更新后的正文"}, ensure_ascii=False).encode("utf-8"))
    changed_source = dataset_source(raw_sha=changed_raw.canonical_sha256).model_dump(mode="json", by_alias=True)
    changed_source["rawRecordRef"] = "raw/records/row-2.json"
    second = build_document_v2(document_id="doc-1",
                               source=SourceAssertionV2.model_validate_json(json.dumps(changed_source, ensure_ascii=False)),
                               metadata=MetadataV2(), temporal=temporal(), relations=RelationV2(),
                               raw_record=changed_raw)
    assert second.document_version_id != first.document_version_id
    with pytest.raises(StateConflict, match="same source assertion has conflicting raw content"):
        write_v2_artifacts(workspace=tmp_path, document=second, raw_record=changed_raw)
    assert not (tmp_path / "raw" / "records" / "row-2.json").exists()
    assert not (tmp_path / "manifests" / "corpus-document-v2" / f"{second.document_version_id}.json").exists()


def test_writer_binds_parsed_asset_and_rejects_path_escape(tmp_path) -> None:
    asset_bytes = b"%PDF-1.4\nlocal immutable source fixture"
    asset_sha = hashlib.sha256(asset_bytes).hexdigest()
    asset_path = tmp_path / "source.pdf"
    asset_path.write_bytes(asset_bytes)
    source = SourceAssertionV2.model_validate_json(json.dumps({
        "kind": "official", "sourceSnapshot": "official-assertion-1", "rawHashScope": "asset_bytes",
        "rawSha256": asset_sha, "assetId": "asset-1", "assetVersion": asset_sha,
        "finalUrl": "https://www.chinatax.gov.cn/a.pdf", "officialPublisher": "国家税务总局",
        "officialProofRef": "manual:page-1",
    }, ensure_ascii=False))
    parsed_source = parsed_source_v2(parsed(asset_sha=asset_sha))
    relation = RelationV2.model_validate_json(b'{"relationType":"attachment","parentDocumentId":"parent-1","parentSourceRef":"official:link"}')
    sidecar = build_document_v2(document_id="attachment-1", source=source, metadata=MetadataV2(),
                                temporal=temporal(), relations=relation, parsed_source=parsed_source,
                                parsed_source_ref="parsed/source-v2.json")
    with pytest.raises(ContractError, match="frozen full relation inventory"):
        write_v2_artifacts(workspace=tmp_path, document=sidecar, parsed_source=parsed_source,
                           asset_path=asset_path)
    with pytest.raises(ContractError, match="parent is absent"):
        write_v2_artifacts(workspace=tmp_path, document=sidecar, parsed_source=parsed_source,
                           asset_path=asset_path, all_parent_document_ids=frozenset(),
                           frozen_relation_records=())
    assert not (tmp_path / "manifests").exists() and not (tmp_path / "parsed").exists()
    relation_scope = {"all_parent_document_ids": frozenset({"parent-1"}), "frozen_relation_records": ()}
    with pytest.raises(ContractError, match="local asset and version"):
        write_v2_artifacts(workspace=tmp_path, document=sidecar, parsed_source=parsed_source, **relation_scope)
    assert not (tmp_path / "manifests").exists() and not (tmp_path / "parsed").exists()
    asset_path.write_bytes(b"wrong asset bytes")
    with pytest.raises(ContractError, match="bytes SHA-256 mismatch"):
        write_v2_artifacts(workspace=tmp_path, document=sidecar, parsed_source=parsed_source,
                           asset_path=asset_path, **relation_scope)
    assert not (tmp_path / "manifests").exists() and not (tmp_path / "parsed").exists()
    asset_path.write_bytes(asset_bytes)
    path = write_v2_artifacts(workspace=tmp_path, document=sidecar, parsed_source=parsed_source,
                              asset_path=asset_path, **relation_scope)
    assert load_parsed_source_v2((tmp_path / "parsed" / "source-v2.json").read_bytes()) == parsed_source
    assert parsed_source.text not in path.read_text(encoding="utf-8")
    escaped = build_document_v2(document_id="attachment-1", source=source, metadata=MetadataV2(),
                                temporal=temporal(), relations=relation, parsed_source=parsed_source,
                                parsed_source_ref="parsed/../outside.json")
    with pytest.raises(ContractError, match="escaped"):
        write_v2_artifacts(workspace=tmp_path, document=escaped, parsed_source=parsed_source,
                           asset_path=asset_path, **relation_scope)
    windows_escaped = build_document_v2(document_id="attachment-1", source=source, metadata=MetadataV2(),
                                        temporal=temporal(), relations=relation, parsed_source=parsed_source,
                                        parsed_source_ref="parsed/..\\raw/source.json")
    with pytest.raises(ContractError, match="POSIX separators"):
        write_v2_artifacts(workspace=tmp_path, document=windows_escaped, parsed_source=parsed_source,
                           asset_path=asset_path, **relation_scope)


def test_relative_url_requires_verified_official_base() -> None:
    assert resolve_official_source_url(
        RAW["url"], verified_base_url="https://fgk.chinatax.gov.cn/",
        base_proof_ref="manual:official-base", allowed_hosts=frozenset({"fgk.chinatax.gov.cn"}),
    ) == "https://fgk.chinatax.gov.cn/zcfgk/c100009/example.html"
    with pytest.raises(ContractError, match="verified official base"):
        resolve_official_source_url(RAW["url"], verified_base_url="https://fgk.chinatax.gov.cn/",
                                    base_proof_ref="", allowed_hosts=frozenset({"fgk.chinatax.gov.cn"}))
