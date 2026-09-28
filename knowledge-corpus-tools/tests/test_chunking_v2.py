from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from knowledge_corpus_tools.chunking_v2 import (
    StructureUnitV2,
    _validate_units,
    chunk_document_v2,
)
from knowledge_corpus_tools.errors import ContractError
from knowledge_corpus_tools.models import ParsedDocument
from knowledge_corpus_tools.normalization_v2 import (
    CorpusDocumentV2,
    MetadataV2,
    ParsedSourceV2,
    RelationV2,
    SourceAssertionV2,
    TemporalV2,
    build_document_v2,
    parsed_source_v2,
)
from knowledge_corpus_tools.parsing import parse_asset_v2

SHA = "a" * 64
NOW = datetime(2026, 9, 28, tzinfo=UTC)


def _inputs(blocks: list[dict[str, object]], *, parser_version: str = "fixture-1",
            verified: bool = True, asset_sha: str = SHA):
    parsed = ParsedDocument.model_validate_json(json.dumps({
        "schema_version": 1, "asset_id": "asset-1", "asset_sha256": asset_sha,
        "parser_name": "fixture-parser", "parser_version": parser_version,
        "ocr_status": "not_applied", "quality_status": "accepted",
        "blocks": [{"ordinal": i, **block} for i, block in enumerate(blocks, start=1)],
    }, ensure_ascii=False))
    has_table = any(block["kind"] == "table" for block in blocks)
    source = parsed_source_v2(
        parsed,
        order_proof_ref="fixture:raw-order" if verified else None,
        structure_proof_ref="fixture:structure" if verified and not has_table else None,
    )
    return _bound_inputs(parsed, source)


def _bound_inputs(
    parsed: ParsedDocument, source: ParsedSourceV2,
) -> tuple[CorpusDocumentV2, ParsedDocument, ParsedSourceV2]:
    assertion = SourceAssertionV2.model_validate_json(json.dumps({
        "kind": "official", "sourceSnapshot": "fixture-snapshot-v1",
        "finalUrl": "https://www.chinatax.gov.cn/example.html",
        "officialPublisher": "国家税务总局", "officialProofRef": "fixture:official-page",
        "rawHashScope": "asset_bytes", "rawSha256": parsed.asset_sha256,
        "assetId": parsed.asset_id, "assetVersion": parsed.asset_sha256,
    }, ensure_ascii=False))
    document = build_document_v2(
        document_id="doc-1", source=assertion, metadata=MetadataV2(),
        temporal=TemporalV2.model_validate_json(json.dumps({"snapshotAt": NOW.isoformat()})),
        relations=RelationV2(), parsed_source=source,
        parsed_source_ref="parsed/asset-1.json",
    )
    return document, parsed, source


def test_article_units_have_stable_same_version_parents_and_exact_spans() -> None:
    inputs = _inputs([
        {"kind": "heading", "text": "第一章总则"},
        {"kind": "clause", "text": "第一条 适用范围。", "clause_id": "第一条"},
        {"kind": "paragraph", "text": "但以下情况除外。"},
        {"kind": "clause", "text": "第二条 办理程序。", "clause_id": "第二条"},
    ])
    result = chunk_document_v2(*inputs)
    assert result == chunk_document_v2(*inputs)
    assert result.publishable
    assert [unit.unit_type for unit in result.units] == ["section", "article", "article"]
    chapter, first, second = result.units
    assert first.parent_unit_id == chapter.unit_id == second.parent_unit_id
    assert chapter.parent_unit_id is None
    assert chapter.section_path == ("第一章总则",)
    assert first.section_path == second.section_path == ("第一章总则",)
    assert all(unit.document_version_id == result.document_version_id for unit in result.units)
    assert all(unit.structure_status == "complete_verified" for unit in result.units)
    assert all(item.status == "covered_parsed_source" for item in result.unit_coverage)
    source = inputs[2]
    assert [chunk.content for chunk in result.chunks] == [
        "第一章总则", "第一条 适用范围。\n但以下情况除外。", "第二条 办理程序。",
    ]
    assert all(chunk.content == source.text[chunk.start:chunk.end] for chunk in result.chunks)
    assert all(chunk.end - chunk.start <= 1600 for chunk in result.chunks)


def test_long_article_splits_only_at_complete_sentence_and_retains_coverage() -> None:
    text = "第一条 " + "完整条件。" * 12 + "例外除外。"
    inputs = _inputs([{"kind": "clause", "text": text, "clause_id": "第一条"}])
    result = chunk_document_v2(*inputs, max_length=24)
    assert len(result.chunks) > 1
    assert "".join(chunk.content for chunk in result.chunks) == text
    assert all(len(chunk.content) <= 24 and chunk.content.endswith("。") for chunk in result.chunks)
    assert all("split_context_required" in chunk.quality_flags for chunk in result.chunks)
    assert result.unit_coverage[0].status == "covered_parsed_source"
    assert result.publishable


def test_chapter_section_article_hierarchy_keeps_versioned_parent_links() -> None:
    inputs = _inputs([
        {"kind": "heading", "text": "第一章总则"},
        {"kind": "heading", "text": "第一节适用范围"},
        {"kind": "clause", "text": "第一条 适用。", "clause_id": "第一条"},
        {"kind": "heading", "text": "第二节其他规定"},
        {"kind": "clause", "text": "第二条 其他。", "clause_id": "第二条"},
    ])
    result = chunk_document_v2(*inputs)
    chapter, first_section, first_article, second_section, second_article = result.units
    assert first_section.parent_unit_id == second_section.parent_unit_id == chapter.unit_id
    assert first_article.parent_unit_id == first_section.unit_id
    assert second_article.parent_unit_id == second_section.unit_id
    assert first_article.section_path == ("第一章总则", "第一节适用范围")
    assert second_article.section_path == ("第一章总则", "第二节其他规定")
    assert result.publishable


def test_real_html_parser_to_chunk_preserves_bounded_chapter_section_article(tmp_path: Path) -> None:
    path = tmp_path / "legal.html"
    path.write_text(
        "<html><body><p>第一章 总则</p><p>第一节 适用范围</p>"
        "<h2>第一条 具体规定。</h2></body></html>", encoding="utf-8",
    )
    parsed = parse_asset_v2(path, asset_id="asset-1", asset_sha256=sha256(path.read_bytes()).hexdigest())
    source = parsed_source_v2(parsed, order_proof_ref="fixture:html-order",
                              structure_proof_ref="fixture:html-structure")
    result = chunk_document_v2(*_bound_inputs(parsed, source))
    chapter, section, article = result.units
    assert (chapter.unit_type, section.unit_type, article.unit_type) == ("section", "section", "article")
    assert section.parent_unit_id == chapter.unit_id
    assert article.parent_unit_id == section.unit_id
    assert article.clause_id == "第一条"
    assert result.publishable


@pytest.mark.parametrize("first_line", ["第一节适用范围", "第一节中规定的条件"])
def test_unspaced_possible_heading_is_conservatively_review_required(
    tmp_path: Path, first_line: str,
) -> None:
    path = tmp_path / "ambiguous.html"
    path.write_text(f"<html><body><p>{first_line}</p><p>第一条 规定。</p></body></html>",
                    encoding="utf-8")
    parsed = parse_asset_v2(path, asset_id="asset-1", asset_sha256=sha256(path.read_bytes()).hexdigest())
    source = parsed_source_v2(parsed, order_proof_ref="fixture:html-order",
                              structure_proof_ref="fixture:html-structure")
    result = chunk_document_v2(*_bound_inputs(parsed, source))
    assert result.units[0].structure_status == "review_required"
    assert not result.publishable


def test_long_unbreakable_block_is_explicitly_unresolved_not_truncated() -> None:
    inputs = _inputs([{"kind": "paragraph", "text": "甲" * 100}])
    result = chunk_document_v2(*inputs, max_length=30)
    assert result.chunks == ()
    assert result.unresolved[0].reason == "no_safe_boundary"
    assert result.unit_coverage[0].status == "incomplete"
    assert not result.publishable


def test_table_and_old_order_remain_unverified_and_never_publishable() -> None:
    inputs = _inputs([
        {"kind": "paragraph", "text": "表前条件。"},
        {"kind": "table", "text": "税种 | 税率\n甲 | 6%", "table_id": "table-1"},
        {"kind": "paragraph", "text": "表后例外。"},
    ])
    result = chunk_document_v2(*inputs)
    table = next(unit for unit in result.units if unit.unit_type == "table")
    assert table.structure_status == "review_required"
    assert table.table_id is None
    assert all(chunk.table_id is None for chunk in result.chunks)
    assert any("table_structure_unknown" in chunk.quality_flags for chunk in result.chunks)
    assert all(chunk.content == inputs[2].text[chunk.start:chunk.end] for chunk in result.chunks)
    assert not result.publishable
    old = _inputs([{"kind": "clause", "text": "第一条 旧解析。", "clause_id": "第一条"}],
                  verified=False)
    old_result = chunk_document_v2(*old)
    assert old_result.units[0].structure_status == "unverified"
    assert not old_result.publishable


def test_short_unresolved_is_retained_but_not_release_ready() -> None:
    inputs = _inputs([{"kind": "paragraph", "text": "注："}])
    result = chunk_document_v2(*inputs)
    assert result.chunks[0].content == "注："
    assert "short_unresolved" in result.chunks[0].quality_flags
    assert not result.publishable


def test_tampered_parser_or_cross_version_relation_fails_closed() -> None:
    document, parsed, source = _inputs([{"kind": "paragraph", "text": "完整原文。"}])
    changed = parsed.model_copy(update={"asset_sha256": "b" * 64})
    with pytest.raises(ContractError, match="identity"):
        chunk_document_v2(document, changed, source)
    bad_blocks = parsed.model_copy(update={"blocks": (parsed.blocks[0].model_copy(update={"text": "篡改"}),)})
    with pytest.raises(ContractError, match="do not match"):
        chunk_document_v2(document, bad_blocks, source)
    first = chunk_document_v2(document, parsed, source)
    second_document = document.model_copy(update={"document_version_id": "b" * 64})
    # The immutable document contract refuses a new version without its source identity.
    with pytest.raises(ValidationError, match="documentVersionId mismatch"):
        type(document).model_validate_json(second_document.model_dump_json())
    alien_parent = first.units[0].model_copy(update={"parent_unit_id": "b" * 64})
    with pytest.raises(ContractError, match="parent is absent"):
        _validate_units([alien_parent], source)


def test_clause_location_must_match_hash_bound_source_text() -> None:
    document, parsed, source = _inputs([
        {"kind": "clause", "text": "第一条 适用。", "clause_id": "第一条"},
    ])
    changed = parsed.model_copy(update={
        "blocks": (parsed.blocks[0].model_copy(update={"clause_id": "第九条"}),),
    })
    with pytest.raises(ContractError, match="clause location"):
        chunk_document_v2(document, changed, source)
    result = chunk_document_v2(document, parsed, source)
    assert result.publishable
    assert result.units[0].clause_id == result.chunks[0].clause_id == "第一条"


def test_result_schema_does_not_expose_online_parent_fetch() -> None:
    document, parsed, source = _inputs([{"kind": "paragraph", "text": "可核对。"}])
    result = chunk_document_v2(document, parsed, source)
    assert result.model_dump(mode="json", by_alias=True)["chunks"][0]["content"] == "可核对。"
    assert "onlineParentFetch" not in json.dumps(result.model_dump(mode="json", by_alias=True))
    with pytest.raises(ContractError, match="length"):
        chunk_document_v2(document, parsed, source, max_length=1601)
