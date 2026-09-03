from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from .errors import ContractError
from .jsonio import sha256_file, strict_loads, write_jsonl, write_model
from .models import (
    AuditItem,
    AuditSummary,
    IndexInventory,
    IntegrityFinding,
    IntegrityStatus,
    Priority,
    SourceProbe,
    SourceStatus,
)


def normalize_v1_audit(
    *,
    v1_path: Path,
    output_jsonl: Path,
    output_summary: Path,
    p0_document_ids: frozenset[str],
    p1_document_ids: frozenset[str],
    current_alias: str,
    current_index: str,
    current_index_uuid: str,
    current_chunk_count: int,
    es_read_requests: int,
    source_get_budget: int,
) -> AuditSummary:
    raw_lines = v1_path.read_text(encoding="utf-8").splitlines()
    items: list[AuditItem] = []
    seen: set[str] = set()
    for number, line in enumerate(raw_lines, start=1):
        value = strict_loads(line)
        if not isinstance(value, dict):
            raise ContractError(f"audit v1 line {number} is not an object")
        document_id = str(value["documentId"])
        if document_id in seen:
            raise ContractError(f"duplicate documentId: {document_id}")
        seen.add(document_id)
        source_status = _source_status(value)
        priority = Priority.P0 if document_id in p0_document_ids else Priority.P1 if document_id in p1_document_ids else Priority.P2
        inventory = None
        if bool(value.get("bodyExistsInCurrentIndex")):
            inventory = IndexInventory(
                index_name=str(value.get("currentIndexVersion") or current_index),
                profile_version=str(value.get("currentProfileVersion") or "unknown"),
                chunk_count=int(value.get("fragmentCount", 0)),
                indexed_text_length=int(value.get("currentIndexedTextLength", 0)),
                keyword_indexed=bool(value.get("keywordIndexed")),
                vector_indexed=bool(value.get("vectorIndexed")),
            )
        source = SourceProbe(
            requested_url=None if source_status is SourceStatus.URL_MISSING else value.get("officialSourceUrl"),
            final_url=value.get("sourceFinalUrl"),
            status=source_status,
            http_status=value.get("sourceHttpStatus"),
            redirect_count=int(value.get("sourceRedirectCount", 0)),
            checked_at_utc=None,
            official_replacement_proof=None,
        )
        if source_status is SourceStatus.OK:
            body_empty = bool(value.get("bodyEmpty"))
            truncated = bool(value.get("bodyTruncatedSuspected"))
            only_names = bool(value.get("onlyAttachmentNamesSuspected"))
            gap = body_empty or truncated or only_names
            integrity = IntegrityFinding(
                status=IntegrityStatus.VERIFIED_GAP if gap else IntegrityStatus.VERIFIED_COMPLETE,
                official_text_length=int(value.get("officialPageTextLength", 0)),
                body_empty=body_empty,
                truncated_suspected=truncated,
                only_attachment_names_suspected=only_names,
                attachment_reference_count=int(value.get("attachmentCount", 0)),
                reason="empty_body" if body_empty else "truncated_body" if truncated else "only_attachment_names" if only_names else "none",
            )
        else:
            integrity = IntegrityFinding(status=IntegrityStatus.NOT_ASSESSABLE, reason="source_not_readable")
        items.append(
            AuditItem(
                schema_version=2,
                document_id=document_id,
                document_number=value.get("documentNumber"),
                title=str(value["title"]),
                issuing_authority=value.get("issuingAuthority"),
                published_date=value.get("publishedDate"),
                effective_date=value.get("effectiveDate"),
                expiry_or_repeal_date=value.get("expiryOrRepealDate"),
                validity_status=cast(Literal["ACTIVE", "AMENDED", "EXPIRED", "PENDING", "REPEALED", "UNKNOWN"], str(value.get("validityStatus", "UNKNOWN"))),
                logical_domain_id=cast(Literal["tax.policy", "tax.law"], str(value["logicalDomainId"])),
                priority=priority,
                priority_reason="curated_stage_a_target" if priority is not Priority.P2 else "inventory_only",
                inventory=inventory,
                source=source,
                integrity=integrity,
                requires_human_review=source_status is not SourceStatus.OK or integrity.status is not IntegrityStatus.VERIFIED_COMPLETE,
            )
        )
    write_jsonl(output_jsonl, items)
    priority_counts = Counter(item.priority for item in items)
    source_counts = Counter(item.source.status for item in items)
    integrity_counts = Counter(item.integrity.status for item in items)
    summary = AuditSummary(
        schema_version=2,
        generated_at_utc=datetime.now(UTC),
        current_alias=current_alias,
        current_index=current_index,
        current_index_uuid=current_index_uuid,
        current_document_count=sum(1 for item in items if item.inventory is not None),
        current_chunk_count=current_chunk_count,
        audit_item_count=len(items),
        priority_counts={priority: priority_counts.get(priority, 0) for priority in Priority},
        source_status_counts={status: source_counts.get(status, 0) for status in SourceStatus},
        integrity_status_counts={status: integrity_counts.get(status, 0) for status in IntegrityStatus},
        es_read_requests=es_read_requests,
        source_get_budget=source_get_budget,
        source_get_used=len(items) - source_counts.get(SourceStatus.URL_MISSING, 0),
        retry_count=0,
        index_write_count=0,
        audit_jsonl_sha256=sha256_file(output_jsonl),
    )
    write_model(output_summary, summary)
    return summary


def _source_status(value: dict[str, Any]) -> SourceStatus:
    url = value.get("officialSourceUrl")
    if not isinstance(url, str) or not url.strip():
        return SourceStatus.URL_MISSING
    if value.get("sourceFetchStatus") == "ok" and value.get("sourceHttpStatus") == 200:
        return SourceStatus.OK
    return SourceStatus.UNREACHABLE
