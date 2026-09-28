from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

from docx import Document
import pymupdf
import pytest

from knowledge_corpus_tools.errors import ContractError
from knowledge_corpus_tools.models import BlockKind
from knowledge_corpus_tools.normalization_v2 import TrustStatus, parsed_source_v2
from knowledge_corpus_tools.parsing import parse_asset, parse_asset_v2


def _docx_with_interleaved_table(path: Path) -> str:
    document = Document()
    document.add_paragraph("第一条 一般规定")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "项目"
    table.cell(0, 1).text = "条件"
    document.add_paragraph("第二条 例外规定")
    document.save(str(path))
    return sha256(path.read_bytes()).hexdigest()


def test_docx_v2_preserves_interleaved_body_order_without_changing_v1(tmp_path: Path) -> None:
    path = tmp_path / "source.docx"
    digest = _docx_with_interleaved_table(path)

    legacy = parse_asset(path, asset_id="source", asset_sha256=digest)
    ordered = parse_asset_v2(path, asset_id="source", asset_sha256=digest)

    assert legacy.parser_version == "1.2.0"
    assert [block.kind for block in legacy.blocks] == [BlockKind.CLAUSE, BlockKind.CLAUSE, BlockKind.TABLE]
    assert ordered.parser_version == "1.2.0+ordered-v2"
    assert [block.kind for block in ordered.blocks] == [BlockKind.CLAUSE, BlockKind.TABLE, BlockKind.CLAUSE]
    assert [block.ordinal for block in ordered.blocks] == [1, 2, 3]
    assert ordered.blocks[1].table_id == "table-1"
    assert ordered.blocks[1].text == "项目 | 条件"
    assert ordered.blocks[2].clause_id == "第二条"


def test_docx_v2_order_proof_does_not_claim_flattened_table_structure(tmp_path: Path) -> None:
    path = tmp_path / "source.docx"
    digest = _docx_with_interleaved_table(path)
    ordered = parse_asset_v2(path, asset_id="source", asset_sha256=digest)

    source = parsed_source_v2(ordered, order_proof_ref=f"source-docx-sha256:{digest}")
    assert source.order_status is TrustStatus.VERIFIED
    assert source.structure_status is TrustStatus.REVIEW_REQUIRED
    assert source.text == "第一条 一般规定\n项目 | 条件\n第二条 例外规定"


def test_parse_asset_v2_preserves_other_parser_behavior(tmp_path: Path) -> None:
    path = tmp_path / "source.html"
    path.write_text("<html><body><p>税务政策</p></body></html>", encoding="utf-8")
    digest = sha256(path.read_bytes()).hexdigest()

    legacy = parse_asset(path, asset_id="source", asset_sha256=digest)
    revised = parse_asset_v2(path, asset_id="source", asset_sha256=digest)
    assert legacy.parser_version == "4.15.0"
    assert revised.parser_version == "4.15.0+sections-v2"
    assert revised.blocks == legacy.blocks


@pytest.mark.parametrize("suffix", [".html", ".docx"])
def test_parse_asset_v2_rejects_mismatched_asset_bytes_before_parsing(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"source{suffix}"
    if suffix == ".docx":
        _docx_with_interleaved_table(path)
    else:
        path.write_text("<p>正文</p>", encoding="utf-8")

    with pytest.raises(ContractError, match="asset bytes SHA-256 mismatch"):
        parse_asset_v2(path, asset_id="source", asset_sha256="0" * 64)
    assert parse_asset(path, asset_id="source", asset_sha256="0" * 64).asset_sha256 == "0" * 64


def test_docx_v2_recognizes_sections_and_clause_overrides_heading_style(tmp_path: Path) -> None:
    path = tmp_path / "sections.docx"
    document = Document()
    document.add_paragraph("第一节 适用范围")
    document.add_paragraph("第一条 标题样式", style="Heading 1")
    document.add_paragraph("第一节中规定的条件")
    document.save(str(path))
    digest = sha256(path.read_bytes()).hexdigest()

    legacy = parse_asset(path, asset_id="source", asset_sha256=digest)
    revised = parse_asset_v2(path, asset_id="source", asset_sha256=digest)
    assert [block.kind for block in legacy.blocks] == [BlockKind.PARAGRAPH, BlockKind.HEADING, BlockKind.PARAGRAPH]
    assert [block.kind for block in revised.blocks] == [BlockKind.HEADING, BlockKind.CLAUSE, BlockKind.PARAGRAPH]
    assert revised.blocks[1].clause_id == "第一条"


def test_html_v2_recognizes_only_bounded_section_heading(tmp_path: Path) -> None:
    path = tmp_path / "sections.html"
    path.write_text(
        "<html><body><p>第一节 适用范围</p><p>第一条 具体规定</p>"
        "<p>第一节中规定的条件</p></body></html>", encoding="utf-8",
    )
    digest = sha256(path.read_bytes()).hexdigest()

    legacy = parse_asset(path, asset_id="source", asset_sha256=digest)
    revised = parse_asset_v2(path, asset_id="source", asset_sha256=digest)
    assert [block.kind for block in legacy.blocks] == [BlockKind.PARAGRAPH, BlockKind.CLAUSE, BlockKind.PARAGRAPH]
    assert [block.kind for block in revised.blocks] == [BlockKind.HEADING, BlockKind.CLAUSE, BlockKind.PARAGRAPH]


def test_html_v2_clause_text_overrides_heading_tag(tmp_path: Path) -> None:
    path = tmp_path / "article.html"
    path.write_text("<html><body><h2>第一条 适用范围</h2></body></html>", encoding="utf-8")
    digest = sha256(path.read_bytes()).hexdigest()
    legacy = parse_asset(path, asset_id="source", asset_sha256=digest)
    revised = parse_asset_v2(path, asset_id="source", asset_sha256=digest)
    assert legacy.blocks[0].kind is BlockKind.HEADING
    assert revised.blocks[0].kind is BlockKind.CLAUSE
    assert revised.blocks[0].clause_id == "第一条"


def test_real_pdf_v2_recognizes_section_heading(tmp_path: Path) -> None:
    path = tmp_path / "sections.pdf"
    pdf_api: Any = pymupdf
    document: Any = pdf_api.open()
    page = document.new_page()
    page.insert_font(fontname="CJK", fontbuffer=pdf_api.Font("china-s").buffer)
    page.insert_text((72, 72), "第一节 适用范围", fontname="CJK", fontsize=12)
    page.insert_text((72, 100), "第一条 具体规定", fontname="CJK", fontsize=12)
    path.write_bytes(document.tobytes())
    document.close()
    digest = sha256(path.read_bytes()).hexdigest()

    legacy = parse_asset(path, asset_id="source", asset_sha256=digest)
    revised = parse_asset_v2(path, asset_id="source", asset_sha256=digest)
    assert legacy.parser_version == "6.16.2+structure-v1"
    assert revised.parser_version == "6.16.2+sections-v2"
    assert [block.kind for block in legacy.blocks] == [BlockKind.PARAGRAPH, BlockKind.CLAUSE]
    assert [block.kind for block in revised.blocks] == [BlockKind.HEADING, BlockKind.CLAUSE]
    assert revised.blocks[0].text == "第一节 适用范围"
