from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from .acquire import OfficialAssetAcquirer
from .chunking import chunk_document
from .errors import ContractError, SafetyError, StateConflict
from .jsonio import load_jsonl, load_model, sha256_file, write_jsonl, write_model
from .models import (
    AcquisitionResult,
    AssetManifest,
    CorpusChunk,
    CorpusSourceCatalog,
    ParsedDocument,
    ProcessingResult,
    SourcePolicy,
    StageAFailure,
)
from .parsing import RapidOcrEngine, discover_attachments, parse_asset


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def acquire_catalog(
    *,
    catalog_path: Path,
    policy_path: Path,
    workspace: Path,
    run_id: str,
    source_get_budget: int,
) -> AcquisitionResult:
    catalog = load_model(catalog_path, CorpusSourceCatalog)
    policy = load_model(policy_path, SourcePolicy)
    started = datetime.now(UTC)
    manifests: list[AssetManifest] = []
    failures: list[StageAFailure] = []
    references = 0
    get_used = 0
    run_dir = workspace.resolve() / "runs" / run_id
    acquirer = OfficialAssetAcquirer(
        workspace=workspace,
        allowed_hosts=frozenset(policy.allowed_hosts),
        max_asset_bytes=policy.max_asset_bytes,
    )
    try:
        for source in catalog.assets:
            if get_used >= source_get_budget:
                raise ContractError("source GET budget exhausted")
            get_used += 1
            try:
                parent = acquirer.fetch(
                    url=source.source_url,
                    parent_document_id=source.document_id,
                    official_source_proof=source.official_replacement_proof,
                    filename="source.html",
                )
                manifests.append(parent)
            except (SafetyError, StateConflict, OSError) as exc:
                failures.append(
                    StageAFailure(
                        phase="source",
                        source_url_sha256=_url_hash(source.source_url),
                        reason="source_unreachable",
                    )
                )
                continue
            page = workspace / parent.storage_relative_path
            try:
                attachments = discover_attachments(
                    page.read_bytes(),
                    source_page_url=parent.source_final_url,
                    parent_document_id=source.document_id,
                    allowed_hosts=frozenset(policy.allowed_hosts),
                )
            except SafetyError:
                failures.append(
                    StageAFailure(
                        phase="source",
                        asset_id=parent.asset_id,
                        source_url_sha256=_url_hash(source.source_url),
                        reason="unsafe_url",
                    )
                )
                continue
            references += len(attachments)
            for reference in attachments:
                if get_used >= source_get_budget:
                    raise ContractError("source GET budget exhausted")
                get_used += 1
                try:
                    manifests.append(
                        acquirer.fetch(
                            url=reference.attachment_url,
                            parent_document_id=reference.parent_document_id,
                            official_source_proof=f"official attachment link ordinal {reference.ordinal} on {reference.source_page_url}",
                            filename=reference.filename,
                        )
                    )
                except SafetyError as exc:
                    reason = "asset_too_large" if "size" in str(exc) else "invalid_mime" if "MIME" in str(exc) or "signature" in str(exc) else "source_unreachable"
                    failures.append(
                        StageAFailure(
                            phase="download",
                            source_url_sha256=_url_hash(reference.attachment_url),
                            reason=cast(Literal["source_unreachable", "invalid_mime", "asset_too_large"], reason),
                        )
                    )
    finally:
        acquirer.close()
    write_jsonl(run_dir / "asset-manifest.v1.jsonl", manifests)
    result = AcquisitionResult(
        schema_version=1,
        run_id=run_id,
        started_at_utc=started,
        completed_at_utc=datetime.now(UTC),
        source_get_budget=source_get_budget,
        source_get_used=get_used,
        retry_count=0,
        parent_count=len(catalog.assets),
        attachment_reference_count=references,
        downloaded_asset_count=len(manifests),
        failures=tuple(failures),
    )
    write_model(run_dir / "acquisition-result.v1.json", result)
    return result


def process_assets(
    *,
    asset_manifest_path: Path,
    workspace: Path,
    run_id: str,
    enable_ocr: bool,
) -> ProcessingResult:
    manifests = load_jsonl(asset_manifest_path, AssetManifest)
    run_dir = workspace.resolve() / "runs" / run_id
    copied_manifest_path = run_dir / "asset-manifest.v1.jsonl"
    if copied_manifest_path.resolve() != asset_manifest_path.resolve():
        write_jsonl(copied_manifest_path, manifests)
    parsed_documents: list[ParsedDocument] = []
    chunks: list[CorpusChunk] = []
    failures: list[StageAFailure] = []
    ocr = RapidOcrEngine() if enable_ocr else None
    accepted = review = rejected = 0
    for manifest in manifests:
        asset_path = workspace / manifest.storage_relative_path
        if sha256_file(asset_path) != manifest.sha256:
            raise StateConflict(f"asset hash changed: {manifest.asset_id}")
        try:
            parsed = parse_asset(
                asset_path,
                asset_id=manifest.asset_id,
                asset_sha256=manifest.sha256,
                ocr_engine=ocr,
            )
        except (ContractError, OSError, ValueError):
            rejected += 1
            failures.append(StageAFailure(phase="parse", asset_id=manifest.asset_id, reason="parse_failed"))
            continue
        parsed_documents.append(parsed)
        if parsed.quality_status == "accepted":
            accepted += 1
            if manifest.extension not in {".html", ".htm"}:
                chunks.extend(
                    chunk_document(
                        parsed,
                        document_id=manifest.parent_document_id,
                        asset_version=manifest.asset_version,
                    )
                )
        elif parsed.quality_status == "review_required":
            review += 1
            failures.append(StageAFailure(phase="ocr", asset_id=manifest.asset_id, reason="ocr_review_required"))
        else:
            rejected += 1
            failures.append(StageAFailure(phase="parse", asset_id=manifest.asset_id, reason="quality_rejected"))
    write_jsonl(run_dir / "parsed-documents.v1.jsonl", parsed_documents)
    write_jsonl(run_dir / "chunks.v1.jsonl", chunks)
    result = ProcessingResult(
        schema_version=1,
        run_id=run_id,
        asset_count=len(manifests),
        accepted_asset_count=accepted,
        review_required_asset_count=review,
        rejected_asset_count=rejected,
        chunk_count=len(chunks),
        failures=tuple(failures),
    )
    write_model(run_dir / "processing-result.v1.json", result)
    return result
