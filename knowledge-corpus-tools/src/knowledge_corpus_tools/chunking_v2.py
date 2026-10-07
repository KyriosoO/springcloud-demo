"""Offline structure units and source-span chunks for a new corpus candidate.

This module neither reads a parent through the online Knowledge contract nor
changes the legacy chunker.  An unproved parser order remains unverified.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from typing import Any, Literal

from pydantic import Field, model_validator

from .errors import ContractError
from .models import BlockKind, ParsedBlock, ParsedDocument
from .normalization_v2 import (
    CorpusDocumentV2,
    ParsedSourceV2,
    TrustStatus,
    _StrictV2,
    _canonical,
    validate_source_span,
)
from .structure_patterns import CLAUSE_PATTERN

CHUNKER_VERSION: Literal["knowledge-structure-chunker-v2"] = "knowledge-structure-chunker-v2"
MAX_CHUNK_CODE_POINTS = 1600
MAX_OVERLAP_CODE_POINTS = 160
_SHA256 = r"^[0-9a-f]{64}$"
_SENTENCE_END = frozenset("。！？；.!?;\n")
_CHAPTER = re.compile(r"^第[一二三四五六七八九十百千0-9]+章")
_SECTION = re.compile(r"^第[一二三四五六七八九十百千0-9]+节")
_POSSIBLE_HEADING = re.compile(r"^第[一二三四五六七八九十百千0-9]+[章节]")


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _text_hash(text: str) -> str:
    return _hash(text.encode("utf-8"))


def _identity(payload: dict[str, Any]) -> str:
    return _hash(_canonical(payload))


class StructureUnitV2(_StrictV2):
    schema_version: Literal[2]
    unit_id: str = Field(pattern=_SHA256)
    document_version_id: str = Field(pattern=_SHA256)
    source_text_sha256: str = Field(pattern=_SHA256)
    parser_version: str = Field(min_length=1)
    unit_type: Literal["section", "article", "table", "paragraph"]
    ordinal: int = Field(ge=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    body_sha256: str = Field(pattern=_SHA256)
    parent_unit_id: str | None = Field(default=None, pattern=_SHA256)
    section_path: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    clause_id: str | None = Field(default=None, max_length=256)
    table_id: str | None = Field(default=None, max_length=256)
    structure_status: Literal["complete_verified", "unverified", "review_required"]
    context_refs: tuple[str, ...] = Field(default_factory=tuple, max_length=32)

    @model_validator(mode="after")
    def check_identity(self) -> StructureUnitV2:
        if self.end <= self.start or self.parent_unit_id == self.unit_id:
            raise ValueError("invalid structure unit range or parent")
        if self.unit_id != unit_id(
            document_version_id=self.document_version_id,
            source_text_sha256=self.source_text_sha256,
            parser_version=self.parser_version,
            unit_type=self.unit_type,
            start=self.start,
            end=self.end,
        ):
            raise ValueError("unitId mismatch")
        return self


class RetrievalChunkV2(_StrictV2):
    schema_version: Literal[2]
    chunker_version: Literal["knowledge-structure-chunker-v2"]
    chunk_id: str = Field(pattern=_SHA256)
    document_version_id: str = Field(pattern=_SHA256)
    unit_id: str = Field(pattern=_SHA256)
    asset_id: str = Field(min_length=1)
    ordinal: int = Field(ge=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    content: str = Field(min_length=1, max_length=MAX_CHUNK_CODE_POINTS, repr=False)
    body_sha256: str = Field(pattern=_SHA256)
    section_path: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    clause_id: str | None = Field(default=None, max_length=256)
    table_id: str | None = Field(default=None, max_length=256)
    quality_flags: tuple[Literal["short_unresolved", "split_context_required", "table_structure_unknown"], ...] = ()

    @model_validator(mode="after")
    def check_content(self) -> RetrievalChunkV2:
        if self.end <= self.start or self.end - self.start != len(self.content):
            raise ValueError("chunk span/content length mismatch")
        if self.body_sha256 != _text_hash(self.content):
            raise ValueError("chunk body hash mismatch")
        if self.chunk_id != chunk_id(
            document_version_id=self.document_version_id,
            unit_id=self.unit_id,
            start=self.start,
            end=self.end,
            body_sha256=self.body_sha256,
        ):
            raise ValueError("chunkId mismatch")
        return self


class UnresolvedSpanV2(_StrictV2):
    unit_id: str = Field(pattern=_SHA256)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    reason: Literal["no_safe_boundary", "table_structure_unknown", "source_structure_unverified"]


class UnitCoverageV2(_StrictV2):
    unit_id: str = Field(pattern=_SHA256)
    status: Literal["covered_parsed_source", "incomplete"]


class ChunkingResultV2(_StrictV2):
    schema_version: Literal[2]
    chunker_version: Literal["knowledge-structure-chunker-v2"]
    document_version_id: str = Field(pattern=_SHA256)
    source_text_sha256: str = Field(pattern=_SHA256)
    units: tuple[StructureUnitV2, ...]
    chunks: tuple[RetrievalChunkV2, ...]
    unit_coverage: tuple[UnitCoverageV2, ...]
    unresolved: tuple[UnresolvedSpanV2, ...]
    publishable: bool


def unit_id(
    *, document_version_id: str, source_text_sha256: str, parser_version: str,
    unit_type: str, start: int, end: int,
) -> str:
    return _identity({
        "documentVersionId": document_version_id,
        "sourceTextSha256": source_text_sha256,
        "parserVersion": parser_version,
        "unitType": unit_type,
        "start": start,
        "end": end,
    })


def chunk_id(
    *, document_version_id: str, unit_id: str, start: int, end: int,
    body_sha256: str,
) -> str:
    return _identity({
        "documentVersionId": document_version_id,
        "unitId": unit_id,
        "chunkerVersion": CHUNKER_VERSION,
        "start": start,
        "end": end,
        "bodySha256": body_sha256,
    })


class _UnitDraft:
    def __init__(self, *, unit_type: Literal["section", "article", "table", "paragraph"],
                 first: int, last: int) -> None:
        self.unit_type = unit_type
        self.first = first
        self.last = last


def _heading_rank(text: str) -> int:
    if _CHAPTER.match(text) or text.startswith("附件"):
        return 1
    if _SECTION.match(text):
        return 2
    return 3


def _unit_drafts(blocks: tuple[ParsedBlock, ...]) -> list[_UnitDraft]:
    drafts: list[_UnitDraft] = []
    headings: list[tuple[int, int]] = []  # draft index, rank
    for i, block in enumerate(blocks):
        if block.kind is not BlockKind.HEADING:
            continue
        rank = _heading_rank(block.text)
        while headings and headings[-1][1] >= rank:
            previous, _ = headings.pop()
            drafts[previous].last = i - 1
        drafts.append(_UnitDraft(unit_type="section", first=i, last=len(blocks) - 1))
        headings.append((len(drafts) - 1, rank))
    # A clause owns following paragraphs and tables up to the next clause or heading.
    for i, block in enumerate(blocks):
        if block.kind is not BlockKind.CLAUSE:
            continue
        last = i
        while last + 1 < len(blocks) and blocks[last + 1].kind not in (BlockKind.CLAUSE, BlockKind.HEADING):
            last += 1
        drafts.append(_UnitDraft(unit_type="article", first=i, last=last))
    for i, block in enumerate(blocks):
        if block.kind is not BlockKind.TABLE:
            continue
        drafts.append(_UnitDraft(unit_type="table", first=i, last=i))
    for i, block in enumerate(blocks):
        if block.kind not in (BlockKind.PARAGRAPH, BlockKind.PAGE_BOUNDARY):
            continue
        if not any(draft.first <= i <= draft.last for draft in drafts):
            drafts.append(_UnitDraft(unit_type="paragraph", first=i, last=i))
    return sorted(drafts, key=lambda draft: (draft.first, -(draft.last - draft.first), draft.unit_type))


def _validate_input(document: CorpusDocumentV2, parsed: ParsedDocument, source: ParsedSourceV2) -> None:
    binding = document.parsed_source
    if (binding is None or parsed.quality_status != "accepted" or
            document.source.asset_id != parsed.asset_id or
            document.source.asset_version != parsed.asset_sha256 or
            source.asset_id != parsed.asset_id or source.asset_sha256 != parsed.asset_sha256 or
            source.parser_name != parsed.parser_name or source.parser_version != parsed.parser_version or
            binding.source_text_sha256 != source.source_text_sha256 or
            binding.parser_version != source.parser_version or
            binding.order_status != source.order_status or
            binding.structure_status != source.structure_status or
            len(parsed.blocks) != len(source.blocks)):
        raise ContractError("chunk source identity or parser binding mismatch")
    for block, span in zip(parsed.blocks, source.blocks, strict=True):
        if (block.ordinal != span.block_ordinal or block.kind != span.kind or
                _text_hash(block.text) != span.block_sha256 or
                source.text[span.start:span.end] != block.text):
            raise ContractError("parsed blocks do not match immutable source spans")
        clause_match = CLAUSE_PATTERN.match(block.text)
        if block.kind is BlockKind.CLAUSE:
            if clause_match is None or block.clause_id != clause_match.group(1):
                raise ContractError("clause location does not match immutable source text")
        elif block.clause_id is not None or clause_match is not None:
            raise ContractError("clause location is inconsistent with block kind")


def _safe_splits(text: str, start: int, end: int, max_length: int) -> tuple[tuple[int, int], ...] | None:
    if end - start <= max_length:
        return ((start, end),)
    output: list[tuple[int, int]] = []
    position = start
    while position < end:
        limit = min(end, position + max_length)
        if limit == end:
            output.append((position, end))
            break
        boundary = next((offset + 1 for offset in range(limit - 1, position, -1)
                         if text[offset] in _SENTENCE_END), None)
        if boundary is None or boundary <= position:
            return None
        output.append((position, boundary))
        position = boundary
    return tuple(output)


def _spans_cover(start: int, end: int, intervals: Iterable[tuple[int, int]]) -> bool:
    cursor = start
    for left, right in sorted(intervals):
        if right <= cursor:
            continue
        if left > cursor:
            return False
        cursor = max(cursor, right)
        if cursor >= end:
            return True
    return False


def chunk_document_v2(
    document: CorpusDocumentV2, parsed: ParsedDocument, source: ParsedSourceV2,
    *, max_length: int = MAX_CHUNK_CODE_POINTS,
) -> ChunkingResultV2:
    """Build bounded chunks without altering or guessing the parsed source text."""
    if not isinstance(max_length, int) or isinstance(max_length, bool) or not 1 <= max_length <= MAX_CHUNK_CODE_POINTS:
        raise ContractError("invalid v2 chunk length")
    _validate_input(document, parsed, source)
    drafts = _unit_drafts(parsed.blocks)
    # Drafts are sorted for stable output; identify parents by true source containment.
    coordinates = [(source.blocks[draft.first].start, source.blocks[draft.last].end) for draft in drafts]
    ids = [unit_id(document_version_id=document.document_version_id,
                   source_text_sha256=source.source_text_sha256, parser_version=source.parser_version,
                   unit_type=draft.unit_type, start=start, end=end)
           for draft, (start, end) in zip(drafts, coordinates, strict=True)]
    if len(set(ids)) != len(ids):
        raise ContractError("duplicate structure unit identity")
    units: list[StructureUnitV2] = []
    for ordinal, (draft, (start, end), identity) in enumerate(zip(drafts, coordinates, ids, strict=True), start=1):
        parent_candidates = [i for i, (parent_start, parent_end) in enumerate(coordinates)
                             if i != ordinal - 1 and parent_start <= start and end <= parent_end
                             and (parent_start, parent_end) != (start, end)]
        parent_index = min(parent_candidates, key=lambda i: coordinates[i][1] - coordinates[i][0]) if parent_candidates else None
        block = parsed.blocks[draft.first]
        ambiguous_heading = any(item.kind is BlockKind.PARAGRAPH and _POSSIBLE_HEADING.match(item.text)
                                for item in parsed.blocks[draft.first:draft.last + 1])
        if (ambiguous_heading or draft.unit_type == "table" or block.kind is BlockKind.PAGE_BOUNDARY or
                source.structure_status is TrustStatus.REVIEW_REQUIRED):
            status = "review_required"
        elif source.order_status is TrustStatus.VERIFIED and source.structure_status is TrustStatus.VERIFIED:
            status = "complete_verified"
        else:
            status = "unverified"
        path_indices: list[int] = []
        ancestor = parent_index
        while ancestor is not None:
            if drafts[ancestor].unit_type == "section":
                path_indices.append(ancestor)
            outer = [i for i, (parent_start, parent_end) in enumerate(coordinates)
                     if i != ancestor and parent_start <= coordinates[ancestor][0]
                     and coordinates[ancestor][1] <= parent_end
                     and (parent_start, parent_end) != coordinates[ancestor]]
            ancestor = min(outer, key=lambda i: coordinates[i][1] - coordinates[i][0]) if outer else None
        path_indices.reverse()
        if draft.unit_type == "section":
            path_indices.append(ordinal - 1)
        heading_path = tuple(parsed.blocks[drafts[i].first].text for i in path_indices)
        if len(heading_path) > 16 or any(len(heading) > 512 for heading in heading_path):
            raise ContractError("heading path exceeds bounded structure metadata")
        clause_id = None
        if draft.unit_type == "article":
            clause_match = CLAUSE_PATTERN.match(block.text)
            if clause_match is None:
                raise ContractError("article location is absent from immutable source text")
            clause_id = clause_match.group(1)
        units.append(StructureUnitV2.model_validate({
            "schemaVersion": 2, "unitId": identity, "documentVersionId": document.document_version_id,
            "sourceTextSha256": source.source_text_sha256, "parserVersion": source.parser_version,
            "unitType": draft.unit_type, "ordinal": ordinal, "start": start, "end": end,
            "bodySha256": _text_hash(source.text[start:end]),
            "parentUnitId": ids[parent_index] if parent_index is not None else None,
            "sectionPath": heading_path, "clauseId": clause_id,
            # The legacy flattened table ordinal is not a verified source locator.
            "tableId": None, "structureStatus": status,
        }))
    _validate_units(units, source)

    owners: list[int] = []
    for span in source.blocks:
        containing = [i for i, unit in enumerate(units) if unit.start <= span.start and span.end <= unit.end]
        if not containing:
            raise ContractError("source block has no structure owner")
        owners.append(min(containing, key=lambda i: (units[i].end - units[i].start, -i)))

    chunks: list[RetrievalChunkV2] = []
    unresolved: list[UnresolvedSpanV2] = []

    def emit(owner: int, start: int, end: int) -> None:
        content = source.text[start:end]
        body_sha = _text_hash(content)
        validate_source_span(source, start=start, end=end, content=content, body_sha256=body_sha)
        unit = units[owner]
        flags: list[str] = []
        if len(content) <= 2:
            flags.append("short_unresolved")
        if unit.unit_type == "table":
            flags.append("table_structure_unknown")
        if start > unit.start or end < unit.end:
            flags.append("split_context_required")
        chunks.append(RetrievalChunkV2.model_validate({
            "schemaVersion": 2, "chunkerVersion": CHUNKER_VERSION,
            "chunkId": chunk_id(document_version_id=document.document_version_id,
                                 unit_id=unit.unit_id, start=start, end=end, body_sha256=body_sha),
            "documentVersionId": document.document_version_id, "unitId": unit.unit_id,
            "assetId": parsed.asset_id, "ordinal": len(chunks) + 1,
            "start": start, "end": end, "content": content, "bodySha256": body_sha,
            "sectionPath": unit.section_path, "clauseId": unit.clause_id, "tableId": unit.table_id,
            "qualityFlags": tuple(flags),
        }))

    # Only adjacent blocks with the same smallest unit may be packed together.
    run_owner: int | None = None
    run_start = 0
    run_end = 0
    for owner, span in zip(owners, source.blocks, strict=True):
        if run_owner is not None and (owner != run_owner or span.end - run_start > max_length):
            emit(run_owner, run_start, run_end)
            run_owner = None
        if span.end - span.start > max_length:
            split = _safe_splits(source.text, span.start, span.end, max_length)
            if split is None:
                unresolved.append(UnresolvedSpanV2.model_validate({
                    "unitId": units[owner].unit_id, "start": span.start, "end": span.end,
                    "reason": "no_safe_boundary",
                }))
            else:
                for start, end in split:
                    emit(owner, start, end)
            continue
        if run_owner is None:
            run_owner, run_start, run_end = owner, span.start, span.end
        else:
            run_end = span.end
    if run_owner is not None:
        emit(run_owner, run_start, run_end)

    coverage: list[UnitCoverageV2] = []
    for unit in units:
        covered = all(_spans_cover(span.start, span.end,
                                   ((chunk.start, chunk.end) for chunk in chunks
                                    if unit.start <= chunk.start and chunk.end <= unit.end))
                      for span in source.blocks if unit.start <= span.start and span.end <= unit.end)
        coverage.append(UnitCoverageV2.model_validate({
            "unitId": unit.unit_id,
            "status": "covered_parsed_source" if covered else "incomplete",
        }))
    publishable = (all(unit.structure_status == "complete_verified" for unit in units)
                   and all(item.status == "covered_parsed_source" for item in coverage)
                   and not any("short_unresolved" in chunk.quality_flags or
                               "table_structure_unknown" in chunk.quality_flags for chunk in chunks)
                   and not unresolved)
    return ChunkingResultV2.model_validate({
        "schemaVersion": 2, "chunkerVersion": CHUNKER_VERSION,
        "documentVersionId": document.document_version_id, "sourceTextSha256": source.source_text_sha256,
        "units": tuple(units), "chunks": tuple(chunks), "unitCoverage": tuple(coverage),
        "unresolved": tuple(unresolved), "publishable": publishable,
    })


def _validate_units(units: list[StructureUnitV2], source: ParsedSourceV2) -> None:
    by_id = {unit.unit_id: unit for unit in units}
    for unit in units:
        if _text_hash(source.text[unit.start:unit.end]) != unit.body_sha256:
            raise ContractError("structure unit cannot be replayed from source")
        parent = by_id.get(unit.parent_unit_id) if unit.parent_unit_id else None
        if unit.parent_unit_id and parent is None:
            raise ContractError("structure parent is absent")
        if parent is not None:
            if (parent.document_version_id != unit.document_version_id or
                    not (parent.start <= unit.start and unit.end <= parent.end) or
                    (parent.start, parent.end) == (unit.start, unit.end)):
                raise ContractError("structure parent is not a proper same-version container")
    for unit in units:
        seen: set[str] = set()
        current: StructureUnitV2 | None = unit
        while current is not None:
            if current.unit_id in seen:
                raise ContractError("structure parent cycle")
            seen.add(current.unit_id)
            current = by_id.get(current.parent_unit_id) if current.parent_unit_id else None
