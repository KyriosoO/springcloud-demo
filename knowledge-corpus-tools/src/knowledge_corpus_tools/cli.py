from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .audit import normalize_v1_audit
from .indexing import build_candidate_index
from .jsonio import canonical_bytes, load_jsonl, load_model, sha256_file
from .models import AuditItem, AuditSummary, StageAUatResult
from .pipeline import acquire_catalog, process_assets
from .release import AliasReleaseManager
from .jsonio import write_jsonl


def _path(value: str) -> Path:
    return Path(value).resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="knowledge-corpus")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate-audit")
    validate.add_argument("--items", required=True, type=_path)
    validate.add_argument("--summary", required=True, type=_path)
    normalize = subparsers.add_parser("normalize-audit-v1")
    normalize.add_argument("--input", required=True, type=_path)
    normalize.add_argument("--output", required=True, type=_path)
    normalize.add_argument("--summary", required=True, type=_path)
    normalize.add_argument("--p0-id", action="append", default=[])
    normalize.add_argument("--p1-id", action="append", default=[])
    normalize.add_argument("--alias", required=True)
    normalize.add_argument("--index", required=True)
    normalize.add_argument("--index-uuid", required=True)
    normalize.add_argument("--chunk-count", required=True, type=int)
    normalize.add_argument("--es-read-requests", required=True, type=int)
    normalize.add_argument("--source-get-budget", required=True, type=int)
    schemas = subparsers.add_parser("print-schemas")
    schemas.add_argument("--model", choices=["audit-item", "audit-summary", "stage-a-uat-result"], required=True)
    validate_uat = subparsers.add_parser("validate-uat")
    validate_uat.add_argument("--result", required=True, type=_path)
    acquire = subparsers.add_parser("acquire")
    acquire.add_argument("--catalog", required=True, type=_path)
    acquire.add_argument("--policy", required=True, type=_path)
    acquire.add_argument("--workspace", required=True, type=_path)
    acquire.add_argument("--run-id", required=True)
    acquire.add_argument("--source-get-budget", required=True, type=int)
    process = subparsers.add_parser("process")
    process.add_argument("--asset-manifest", required=True, type=_path)
    process.add_argument("--workspace", required=True, type=_path)
    process.add_argument("--run-id", required=True)
    process.add_argument("--enable-ocr", action="store_true")
    build = subparsers.add_parser("build-candidate")
    build.add_argument("--workspace", required=True, type=_path)
    build.add_argument("--run-id", required=True)
    build.add_argument("--es-endpoint", required=True)
    build.add_argument("--embedding-endpoint", required=True)
    build.add_argument("--source-index", required=True)
    build.add_argument("--source-uuid", required=True)
    build.add_argument("--source-document-count", required=True, type=int)
    build.add_argument("--candidate-index", required=True)
    release = subparsers.add_parser("release-rehearsal")
    release.add_argument("--workspace", required=True, type=_path)
    release.add_argument("--run-id", required=True)
    release.add_argument("--es-endpoint", required=True)
    release.add_argument("--alias", required=True)
    release.add_argument("--old-index", required=True)
    release.add_argument("--old-uuid", required=True)
    release.add_argument("--candidate-index", required=True)
    release.add_argument("--candidate-uuid", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate-audit":
        items = load_jsonl(args.items, AuditItem)
        summary = load_model(args.summary, AuditSummary)
        if len(items) != summary.audit_item_count:
            raise SystemExit("audit item count differs from summary")
        if sha256_file(args.items) != summary.audit_jsonl_sha256:
            raise SystemExit("audit JSONL hash differs from summary")
        print(json.dumps({"valid": True, "items": len(items), "sha256": summary.audit_jsonl_sha256}, sort_keys=True))
        return 0
    if args.command == "normalize-audit-v1":
        summary = normalize_v1_audit(
            v1_path=args.input,
            output_jsonl=args.output,
            output_summary=args.summary,
            p0_document_ids=frozenset(args.p0_id),
            p1_document_ids=frozenset(args.p1_id),
            current_alias=args.alias,
            current_index=args.index,
            current_index_uuid=args.index_uuid,
            current_chunk_count=args.chunk_count,
            es_read_requests=args.es_read_requests,
            source_get_budget=args.source_get_budget,
        )
        print(canonical_bytes(summary.model_dump(mode="json")).decode("utf-8"), end="")
        return 0
    if args.command == "print-schemas":
        model = AuditItem if args.model == "audit-item" else AuditSummary if args.model == "audit-summary" else StageAUatResult
        print(json.dumps(model.model_json_schema(), ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    if args.command == "validate-uat":
        uat = load_model(args.result, StageAUatResult)
        print(json.dumps({"valid": True, "cases": len(uat.cases), "conclusion": uat.conclusion}, sort_keys=True))
        return 0
    if args.command == "acquire":
        acquisition_result = acquire_catalog(
            catalog_path=args.catalog,
            policy_path=args.policy,
            workspace=args.workspace,
            run_id=args.run_id,
            source_get_budget=args.source_get_budget,
        )
        print(canonical_bytes(acquisition_result.model_dump(mode="json")).decode("utf-8"), end="")
        return 0 if not acquisition_result.failures else 2
    if args.command == "process":
        processing_result = process_assets(
            asset_manifest_path=args.asset_manifest,
            workspace=args.workspace,
            run_id=args.run_id,
            enable_ocr=args.enable_ocr,
        )
        print(canonical_bytes(processing_result.model_dump(mode="json")).decode("utf-8"), end="")
        return 0 if not processing_result.failures else 2
    if args.command == "build-candidate":
        build_result = build_candidate_index(
            workspace=args.workspace,
            run_id=args.run_id,
            es_endpoint=args.es_endpoint,
            embedding_endpoint=args.embedding_endpoint,
            source_index=args.source_index,
            source_uuid=args.source_uuid,
            source_document_count=args.source_document_count,
            candidate_index=args.candidate_index,
        )
        print(canonical_bytes(build_result.model_dump(mode="json")).decode("utf-8"), end="")
        return 0
    if args.command == "release-rehearsal":
        output = args.workspace / "runs" / args.run_id / "release-journal.v1.jsonl"
        if output.exists():
            raise SystemExit("release journal already exists")
        manager = AliasReleaseManager(args.es_endpoint)
        try:
            states = (
                manager.switch(alias=args.alias, expected_from_index=args.old_index, expected_from_uuid=args.old_uuid, target_index=args.candidate_index, target_uuid=args.candidate_uuid, phase="candidate"),
                manager.switch(alias=args.alias, expected_from_index=args.candidate_index, expected_from_uuid=args.candidate_uuid, target_index=args.old_index, target_uuid=args.old_uuid, phase="rolled_back"),
                manager.switch(alias=args.alias, expected_from_index=args.old_index, expected_from_uuid=args.old_uuid, target_index=args.candidate_index, target_uuid=args.candidate_uuid, phase="published"),
            )
        finally:
            manager.close()
        write_jsonl(output, states)
        print(canonical_bytes(states[-1].model_dump(mode="json")).decode("utf-8"), end="")
        return 0
    raise SystemExit("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
