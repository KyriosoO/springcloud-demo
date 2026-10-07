from __future__ import annotations

import io
import hashlib
import re
import zipfile
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError as MetadataPackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal, Protocol, cast
from urllib.parse import unquote, urljoin, urlsplit

from bs4 import BeautifulSoup
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.opc.exceptions import PackageNotFoundError
import pymupdf
from openpyxl import load_workbook  # type: ignore[import-untyped]
from openpyxl.utils.exceptions import InvalidFileException  # type: ignore[import-untyped]
from pypdf import PdfReader
from pypdf.errors import PdfReadError
import xlrd  # type: ignore[import-untyped]
from xlrd.biffh import XLRDError  # type: ignore[import-untyped]

from .errors import ContractError
from .models import AttachmentReference, BlockKind, OcrStatus, ParsedBlock, ParsedDocument
from .safety import ALLOWED_EXTENSIONS, extension_from_name, normalize_official_url, validate_zip_container
from .structure_patterns import CLAUSE_PATTERN

HEADING_PATTERN = re.compile(
    r"^(?:附件(?:[一二三四五六七八九十百千0-9]+)?[:：]?|"
    r"第[一二三四五六七八九十百千0-9]+章(?:\s|$)|"
    r"[一二三四五六七八九十百千]+、)"
)
STRUCTURE_HEADING_PATTERN = re.compile(r"^第[一二三四五六七八九十百千0-9]+[章节](?:\s|[:：]|$)")
OcrPage = Callable[[bytes], tuple[str, tuple[float, ...]]]
_pymupdf: Any = pymupdf


class OcrEngine(Protocol):
    def __call__(self, image: bytes) -> tuple[str, tuple[float, ...]]: ...


class RapidOcrEngine:
    """Lazy local OCR adapter; model files are local and no network call is made."""

    def __init__(self) -> None:
        from rapidocr import RapidOCR

        self._engine: Any = RapidOCR()

    def __call__(self, image: bytes) -> tuple[str, tuple[float, ...]]:
        result = self._engine(image)
        texts = tuple(result.txts or ())
        scores = tuple(float(score) for score in (result.scores or ()))
        if len(texts) != len(scores) or any(not 0.0 <= score <= 1.0 for score in scores):
            raise ContractError("invalid OCR output")
        return "\n".join(texts), scores


def _clean(text: str) -> str:
    text = re.sub(r'HYPERLINK\s+"[^"]+"\s+\\t\s+"[^"]+"', "", text)
    return "\n".join(line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip())


def _block(ordinal: int, kind: BlockKind, text: str, **kwargs: Any) -> ParsedBlock:
    return ParsedBlock(ordinal=ordinal, kind=kind, text=_clean(text), **kwargs)


def _is_structural_heading(text: str) -> bool:
    return len(text) <= 120 and STRUCTURE_HEADING_PATTERN.match(text) is not None


def _parse_structured_text(
    text: str,
    *,
    page_number: int | None = None,
    start_ordinal: int = 1,
    recognize_sections: bool = False,
) -> list[ParsedBlock]:
    """Preserve line, clause, heading and tabular boundaries from plain text."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x0c", "\n")
    blocks: list[ParsedBlock] = []
    section_path: tuple[str, ...] = ()
    table_rows: list[str] = []
    table_number = 0

    def append_table() -> None:
        nonlocal table_number
        if not table_rows:
            return
        table_number += 1
        blocks.append(
            _block(
                start_ordinal + len(blocks),
                BlockKind.TABLE,
                "\n".join(table_rows),
                section_path=section_path,
                page_number=page_number,
                table_id=f"table-{table_number}",
            )
        )
        table_rows.clear()

    for raw_line in normalized.split("\n"):
        if "\t" in raw_line:
            cells = tuple(cell.strip() for cell in raw_line.split("\t"))
            if any(cells):
                table_rows.append(" | ".join(cells))
            continue
        append_table()
        line = _clean(raw_line)
        if not line:
            continue
        clause_match = CLAUSE_PATTERN.match(line)
        is_heading = clause_match is None and len(line) <= 120 and (
            HEADING_PATTERN.match(line) is not None
            or recognize_sections and _is_structural_heading(line)
        )
        if is_heading:
            section_path = (line,)
            kind = BlockKind.HEADING
        elif clause_match is not None:
            kind = BlockKind.CLAUSE
        else:
            kind = BlockKind.PARAGRAPH
        blocks.append(
            _block(
                start_ordinal + len(blocks),
                kind,
                line,
                section_path=section_path,
                page_number=page_number,
                clause_id=clause_match.group(1) if clause_match else None,
            )
        )
    append_table()
    return blocks


def parse_asset(
    path: Path,
    *,
    asset_id: str,
    asset_sha256: str,
    ocr_engine: OcrEngine | None = None,
) -> ParsedDocument:
    return _parse_asset_bytes(
        path, path.read_bytes(), asset_id=asset_id, asset_sha256=asset_sha256,
        ocr_engine=ocr_engine, ordered_v2=False,
    )


def _parse_asset_bytes(
    path: Path,
    raw: bytes,
    *,
    asset_id: str,
    asset_sha256: str,
    ocr_engine: OcrEngine | None,
    ordered_v2: bool,
) -> ParsedDocument:
    suffix = path.suffix.lower()
    try:
        if suffix in {".html", ".htm"}:
            blocks = _parse_html(raw, recognize_sections=ordered_v2)
            parser_name = "beautifulsoup4-html"
            parser_version = "4.15.0+sections-v2" if ordered_v2 else "4.15.0"
        elif suffix == ".pdf":
            blocks = _parse_pdf(raw, recognize_sections=ordered_v2)
            parser_name = "pypdf-structured"
            parser_version = "6.16.2+sections-v2" if ordered_v2 else "6.16.2+structure-v1"
            ocr_status = OcrStatus.NOT_APPLIED
            if not blocks and ocr_engine is not None:
                blocks, ocr_status = _parse_scanned_pdf(raw, ocr_engine, recognize_sections=ordered_v2)
                parser_name = "pymupdf+rapidocr"
                parser_version = "1.28.2+3.9.2+sections-v2" if ordered_v2 else "1.28.2+3.9.2"
        elif suffix == ".docx":
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                validate_zip_container(archive)
            blocks = _parse_docx_v2(raw) if ordered_v2 else _parse_docx(raw)
            parser_name = "python-docx"
            parser_version = "1.2.0+ordered-v2" if ordered_v2 else "1.2.0"
        elif suffix == ".xlsx":
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                validate_zip_container(archive)
            blocks = _parse_xlsx(raw)
            parser_name = "openpyxl"
            parser_version = "3.1.5"
        elif suffix == ".xls":
            blocks = _parse_xls(raw)
            parser_name = "xlrd"
            parser_version = "2.0.2"
        elif suffix == ".doc":
            blocks = _parse_legacy_doc_v2(raw) if ordered_v2 else _parse_legacy_doc(path)
            parser_name = "legacy-doc-structured"
            parser_version = "0.2.1+native-paragraphs-v2" if ordered_v2 else "0.2.1+structure-v1"
        else:
            raise ContractError(f"unsupported parser extension: {suffix}")
    except (zipfile.BadZipFile, PdfReadError, PackageNotFoundError, InvalidFileException, XLRDError) as exc:
        raise ContractError("asset parser rejected malformed content") from exc
    if suffix != ".pdf":
        ocr_status = OcrStatus.NOT_APPLIED
    quality = "accepted" if blocks and ocr_status is not OcrStatus.REJECTED else "rejected"
    if ocr_status is OcrStatus.REVIEW_REQUIRED:
        quality = "review_required"
    reasons = () if quality == "accepted" else (("ocr_review_required",) if quality == "review_required" else ("empty_parsed_body",))
    return ParsedDocument(
        schema_version=1,
        asset_id=asset_id,
        asset_sha256=asset_sha256,
        parser_name=parser_name,
        parser_version=parser_version,
        ocr_status=ocr_status,
        blocks=tuple(blocks),
        quality_status=cast(Literal["accepted", "review_required", "rejected"], quality),
        quality_reasons=reasons,
    )


def parse_asset_v2(
    path: Path,
    *,
    asset_id: str,
    asset_sha256: str,
    ocr_engine: OcrEngine | None = None,
) -> ParsedDocument:
    """Parse the exact SHA-bound bytes with v2 section and DOCX order rules."""

    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != asset_sha256:
        raise ContractError("asset bytes SHA-256 mismatch")
    return _parse_asset_bytes(
        path, raw, asset_id=asset_id, asset_sha256=asset_sha256,
        ocr_engine=ocr_engine, ordered_v2=True,
    )


def _parse_html(raw: bytes, *, recognize_sections: bool = False) -> list[ParsedBlock]:
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    root = soup.select_one(".TRS_Editor, .article-content, #zoom, .content") or soup.body or soup
    blocks: list[ParsedBlock] = []
    for element in root.find_all(["h1", "h2", "h3", "h4", "p", "table"], recursive=True):
        text = element.get_text(" | " if element.name == "table" else " ", strip=True)
        if not text:
            continue
        match = CLAUSE_PATTERN.match(text)
        if element.name == "table":
            kind = BlockKind.TABLE
        elif match and recognize_sections:
            kind = BlockKind.CLAUSE
        elif element.name.startswith("h") or recognize_sections and _is_structural_heading(text):
            kind = BlockKind.HEADING
        elif match:
            kind = BlockKind.CLAUSE
        else:
            kind = BlockKind.PARAGRAPH
        kwargs: dict[str, Any] = {}
        if kind is BlockKind.TABLE:
            kwargs["table_id"] = f"table-{len(blocks) + 1}"
        if match and (not recognize_sections or kind is BlockKind.CLAUSE):
            kwargs["clause_id"] = match.group(1)
        blocks.append(_block(len(blocks) + 1, kind, text, **kwargs))
    return blocks


def _parse_pdf(raw: bytes, *, recognize_sections: bool = False) -> list[ParsedBlock]:
    reader = PdfReader(io.BytesIO(raw), strict=True)
    blocks: list[ParsedBlock] = []
    for page_number, page in enumerate(reader.pages, start=1):
        blocks.extend(
            _parse_structured_text(
                page.extract_text() or "",
                page_number=page_number,
                start_ordinal=len(blocks) + 1,
                recognize_sections=recognize_sections,
            )
        )
    return blocks


def _parse_scanned_pdf(
    raw: bytes, engine: OcrEngine, *, recognize_sections: bool = False,
) -> tuple[list[ParsedBlock], OcrStatus]:
    try:
        document: Any = _pymupdf.open(stream=raw, filetype="pdf")
    except Exception as exc:
        raise ContractError("invalid PDF for OCR") from exc
    if document.page_count > 200:
        document.close()
        raise ContractError("OCR page limit exceeded")
    blocks: list[ParsedBlock] = []
    scores: list[float] = []
    try:
        for page_number, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(matrix=_pymupdf.Matrix(2.0, 2.0), alpha=False)
            image = pixmap.tobytes("png")
            text, page_scores = engine(image)
            scores.extend(page_scores)
            blocks.extend(
                _parse_structured_text(
                    text,
                    page_number=page_number,
                    start_ordinal=len(blocks) + 1,
                    recognize_sections=recognize_sections,
                )
            )
    finally:
        document.close()
    if not blocks or not scores:
        return blocks, OcrStatus.REJECTED
    minimum = min(scores)
    average = sum(scores) / len(scores)
    if minimum < 0.50 or average < 0.75:
        return blocks, OcrStatus.REVIEW_REQUIRED
    return blocks, OcrStatus.ACCEPTED


def discover_attachments(
    raw: bytes,
    *,
    source_page_url: str,
    parent_document_id: str,
    allowed_hosts: frozenset[str],
) -> tuple[AttachmentReference, ...]:
    soup = BeautifulSoup(raw, "html.parser")
    root = soup.select_one(".TRS_Editor, .article-content, #zoom, .content") or soup.body or soup
    references: list[AttachmentReference] = []
    seen: set[str] = set()
    for anchor in root.find_all("a", href=True):
        href = str(anchor.get("href", "")).strip()
        if not href:
            continue
        joined = urljoin(source_page_url, href)
        path_name = Path(unquote(urlsplit(joined).path)).name
        label = anchor.get_text(" ", strip=True)
        filename = path_name or label
        try:
            extension = extension_from_name(filename)
        except Exception:
            continue
        if extension not in ALLOWED_EXTENSIONS - {".html", ".htm"}:
            continue
        candidate = normalize_official_url(joined, allowed_hosts)
        if candidate in seen:
            continue
        if label:
            filename = f"{label}{extension}" if not label.lower().endswith(extension) else label
        seen.add(candidate)
        references.append(
            AttachmentReference(
                schema_version=1,
                parent_document_id=parent_document_id,
                source_page_url=source_page_url,
                attachment_url=candidate,
                filename=filename,
                extension=cast(Literal[".pdf", ".doc", ".docx", ".xls", ".xlsx"], extension),
                ordinal=len(references) + 1,
            )
        )
    return tuple(references)


def _parse_docx(raw: bytes) -> list[ParsedBlock]:
    document = Document(io.BytesIO(raw))
    blocks: list[ParsedBlock] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style = (paragraph.style.name if paragraph.style else "").lower()
        match = CLAUSE_PATTERN.match(text)
        kind = BlockKind.HEADING if "heading" in style or "标题" in style else BlockKind.CLAUSE if match else BlockKind.PARAGRAPH
        blocks.append(_block(len(blocks) + 1, kind, text, clause_id=match.group(1) if match else None))
    for table_number, table in enumerate(document.tables, start=1):
        rows = [" | ".join(cell.text.strip() for cell in row.cells) for row in table.rows]
        text = "\n".join(row for row in rows if row.strip(" |"))
        if text:
            blocks.append(_block(len(blocks) + 1, BlockKind.TABLE, text, table_id=f"table-{table_number}"))
    return blocks


def _parse_docx_v2(raw: bytes) -> list[ParsedBlock]:
    document = Document(io.BytesIO(raw))
    blocks: list[ParsedBlock] = []
    table_number = 0
    for item in document.iter_inner_content():
        if isinstance(item, Paragraph):
            text = item.text.strip()
            if not text:
                continue
            style = (item.style.name if item.style else "").lower()
            match = CLAUSE_PATTERN.match(text)
            kind = BlockKind.CLAUSE if match else BlockKind.HEADING if "heading" in style or "标题" in style or _is_structural_heading(text) else BlockKind.PARAGRAPH
            blocks.append(_block(len(blocks) + 1, kind, text, clause_id=match.group(1) if match else None))
        elif isinstance(item, Table):
            table_number += 1
            rows = [" | ".join(cell.text.strip() for cell in row.cells) for row in item.rows]
            text = "\n".join(row for row in rows if row.strip(" |"))
            if text:
                blocks.append(_block(len(blocks) + 1, BlockKind.TABLE, text, table_id=f"table-{table_number}"))
        else:
            raise ContractError("unsupported DOCX body content")
    return blocks


def _parse_xlsx(raw: bytes) -> list[ParsedBlock]:
    workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=False, keep_links=False)
    blocks: list[ParsedBlock] = []
    for worksheet in workbook.worksheets:
        rows: list[str] = []
        for row in worksheet.iter_rows(values_only=False):
            values = ["" if cell.value is None else str(cell.value) for cell in row]
            if any(values):
                rows.append(" | ".join(values))
        if rows:
            blocks.append(_block(len(blocks) + 1, BlockKind.TABLE, "\n".join(rows), table_id=f"sheet:{worksheet.title}"))
    workbook.close()
    return blocks


def _parse_xls(raw: bytes) -> list[ParsedBlock]:
    workbook = xlrd.open_workbook(file_contents=raw, on_demand=True)
    blocks: list[ParsedBlock] = []
    for sheet in workbook.sheets():
        rows = [" | ".join(str(sheet.cell_value(r, c)) for c in range(sheet.ncols)) for r in range(sheet.nrows)]
        text = "\n".join(row for row in rows if row.strip(" |"))
        if text:
            blocks.append(_block(len(blocks) + 1, BlockKind.TABLE, text, table_id=f"sheet:{sheet.name}"))
    workbook.release_resources()
    return blocks


def _parse_legacy_doc(path: Path) -> list[ParsedBlock]:
    return _parse_legacy_doc_bytes(path.read_bytes())


def _parse_legacy_doc_bytes(raw: bytes, *, recognize_sections: bool = False) -> list[ParsedBlock]:
    try:
        from legacy_doc import extract_text  # type: ignore[import-untyped]
    except (ImportError, AttributeError) as exc:
        raise ContractError("legacy DOC parser unavailable") from exc
    result = extract_text(raw)
    return _parse_structured_text(str(result.text), recognize_sections=recognize_sections)


def _legacy_doc_raw_text(raw: bytes) -> str:
    """Read the pinned parser's pre-normalized stream to retain CR versus VT."""
    try:
        from legacy_doc.ole import OleReader  # type: ignore[import-untyped]
        from legacy_doc.types import ExtractionOptions  # type: ignore[import-untyped]
        from legacy_doc.word import (  # type: ignore[import-untyped]
            _extract_text_from_piece_table, _find_clx,
        )
    except (ImportError, AttributeError) as exc:
        raise ContractError("pinned legacy DOC structure reader unavailable") from exc
    ole = OleReader(raw, options=ExtractionOptions())
    word = ole.read_stream("WordDocument")
    if len(word) < 0x44:
        raise ContractError("legacy DOC WordDocument stream is too small")
    flags = int.from_bytes(word[0x0A:0x0C], "little")
    table = ole.read_stream("1Table" if flags & 0x0200 else "0Table")
    fc_min = int.from_bytes(word[0x18:0x1C], "little")
    fc_mac = int.from_bytes(word[0x1C:0x20], "little")
    if fc_mac <= fc_min:
        raise ContractError("legacy DOC has no readable text range")
    clx = _find_clx(table)
    _validate_legacy_doc_pieces(word, clx, fc_min=fc_min, fc_mac=fc_mac)
    text = _extract_text_from_piece_table(word, clx, fc_min, fc_mac)
    if not isinstance(text, str):
        raise ContractError("legacy DOC structure reader returned invalid text")
    return text


def _validate_legacy_doc_pieces(word: bytes, clx: bytes, *, fc_min: int, fc_mac: int) -> None:
    """Reject any piece the pinned extractor would silently skip or replace."""
    if fc_min < 0 or fc_mac <= fc_min or fc_mac > len(word):
        raise ContractError("legacy DOC text range is invalid")
    if len(clx) < 16 or (len(clx) - 4) % 12:
        raise ContractError("legacy DOC piece table is malformed")
    piece_count = (len(clx) - 4) // 12
    cp_size = 4 * (piece_count + 1)
    if cp_size + 8 * piece_count != len(clx):
        raise ContractError("legacy DOC piece table has incomplete records")
    cps = tuple(int.from_bytes(clx[i * 4:i * 4 + 4], "little")
                for i in range(piece_count + 1))
    if cps[0] != 0 or any(right <= left for left, right in zip(cps, cps[1:])):
        raise ContractError("legacy DOC piece positions have gaps or empty pieces")
    for index, (cp_start, cp_end) in enumerate(zip(cps, cps[1:])):
        encoded = int.from_bytes(clx[cp_size + index * 8 + 2:cp_size + index * 8 + 6], "little")
        compressed = bool(encoded & 0x40000000)
        fc = (encoded & 0x3FFFFFFF) // 2 if compressed else encoded
        byte_count = (cp_end - cp_start) * (1 if compressed else 2)
        if fc < fc_min or fc + byte_count > fc_mac or fc + byte_count > len(word):
            raise ContractError("legacy DOC piece points outside the complete source range")
        data = word[fc:fc + byte_count]
        try:
            decoded = data.decode("cp1252" if compressed else "utf-16le", errors="strict")
        except UnicodeDecodeError as exc:
            raise ContractError("legacy DOC piece has undecodable text") from exc
        if "\ufffd" in decoded:
            raise ContractError("legacy DOC piece contains replacement characters")


def _parse_legacy_doc_v2(raw: bytes) -> list[ParsedBlock]:
    """Keep native paragraphs intact while retaining their manual line breaks."""
    try:
        from legacy_doc import LegacyDocError, extract_text
        from legacy_doc.normalize import normalize_word_text  # type: ignore[import-untyped]
    except (ImportError, AttributeError) as exc:
        raise ContractError("pinned legacy DOC parser unavailable") from exc
    try:
        if version("legacy-doc") != "0.2.1":
            raise ContractError("unsupported legacy DOC parser version")
        public = extract_text(raw)
        if public.version != "0.2.1":
            raise ContractError("legacy DOC result version mismatch")
        native = _legacy_doc_raw_text(raw)
        # The current DOC path has no reliable table-cell structure contract.
        if "\x07" in native:
            raise ContractError("legacy DOC table structure requires review")
        paragraphs = tuple(part for raw_part in native.split("\r")
                           if (part := normalize_word_text(raw_part)))
    except MetadataPackageNotFoundError as exc:
        raise ContractError("pinned legacy DOC parser unavailable") from exc
    except (LegacyDocError, ValueError, IndexError, AttributeError) as exc:
        raise ContractError("legacy DOC structure extraction failed") from exc
    flat_text = "\n".join(paragraphs)
    if not paragraphs or flat_text != public.text:
        raise ContractError("legacy DOC native paragraphs differ from public extraction")

    flat_blocks = _parse_structured_text(flat_text, recognize_sections=True)
    grouped: list[ParsedBlock] = []
    cursor = 0
    for paragraph in paragraphs:
        lines = paragraph.split("\n")
        group = flat_blocks[cursor:cursor + len(lines)]
        if len(group) != len(lines) or tuple(block.text for block in group) != tuple(_clean(line) for line in lines):
            raise ContractError("legacy DOC paragraph-to-block mapping is ambiguous")
        if len(group) > 1 and any(block.kind is not BlockKind.PARAGRAPH for block in group):
            raise ContractError("legacy DOC mixed native paragraph structure requires review")
        first = group[0]
        grouped.append(ParsedBlock(
            ordinal=len(grouped) + 1, kind=first.kind,
            text="\n".join(block.text for block in group),
            section_path=first.section_path, page_number=first.page_number,
            table_id=first.table_id, clause_id=first.clause_id,
        ))
        cursor += len(lines)
    if cursor != len(flat_blocks):
        raise ContractError("legacy DOC paragraph mapping omitted blocks")
    return grouped
