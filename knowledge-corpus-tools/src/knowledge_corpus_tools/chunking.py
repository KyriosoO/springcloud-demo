from __future__ import annotations

import hashlib

from .models import CorpusChunk, OcrStatus, ParsedBlock, ParsedDocument

CHUNKER_VERSION = "knowledge-structure-chunker-v1"


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _segments(text: str, *, max_length: int, overlap: int) -> tuple[str, ...]:
    if len(text) <= max_length:
        return (text,)
    output: list[str] = []
    start = 0
    while start < len(text):
        stop = min(len(text), start + max_length)
        if stop < len(text):
            boundary = max(text.rfind("\n", start, stop), text.rfind("。", start, stop))
            if boundary > start + max_length // 2:
                stop = boundary + 1
        output.append(text[start:stop].strip())
        if stop == len(text):
            break
        start = max(stop - overlap, start + 1)
    return tuple(segment for segment in output if segment)


def chunk_document(
    parsed: ParsedDocument,
    *,
    document_id: str,
    asset_version: str,
    max_length: int = 1600,
    overlap: int = 160,
) -> tuple[CorpusChunk, ...]:
    if parsed.quality_status != "accepted":
        return ()
    if not 1 <= max_length <= 1600 or not 0 <= overlap <= 160 or overlap >= max_length:
        raise ValueError("invalid chunk boundaries")
    chunks: list[CorpusChunk] = []
    for block in parsed.blocks:
        for segment in _segments(block.text, max_length=max_length, overlap=overlap):
            content_hash = _hash(segment)
            identity = "|".join(
                [document_id, asset_version, "/".join(block.section_path), str(len(chunks) + 1), content_hash]
            )
            chunks.append(
                CorpusChunk(
                    schema_version=1,
                    chunk_id=f"chunk-{_hash(identity)[:32]}",
                    document_id=document_id,
                    asset_id=parsed.asset_id,
                    asset_version=asset_version,
                    ordinal=len(chunks) + 1,
                    content=segment,
                    content_sha256=content_hash,
                    section_path=block.section_path,
                    clause_id=block.clause_id,
                    table_id=block.table_id,
                    ocr_applied=parsed.ocr_status is not OcrStatus.NOT_APPLIED,
                    ocr_confidence_status=parsed.ocr_status,
                )
            )
    return tuple(chunks)

