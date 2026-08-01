from __future__ import annotations

import json
import unicodedata

from agent_runtime.capability_api.contracts import freeze_json_object
from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeEvidenceBundle,
    KnowledgeEvidenceLimits,
    KnowledgeSummaryOutput,
    SummaryOutcome,
    SummaryValidationResult,
)


class InvalidSummary(ValueError):
    pass


class ExtractiveSummaryValidator:
    def validate(
        self,
        *,
        output: KnowledgeSummaryOutput,
        bundle: KnowledgeEvidenceBundle,
        limits: KnowledgeEvidenceLimits,
    ) -> SummaryValidationResult:
        if output.outcome is SummaryOutcome.INSUFFICIENT_EVIDENCE:
            if output.points:
                raise InvalidSummary("knowledge.invalid_summary")
            return SummaryValidationResult(domain_result=None, insufficient=True)
        if not 1 <= len(output.points) <= limits.max_summary_points:
            raise InvalidSummary("knowledge.invalid_summary")
        by_ref = {f"e{index}": item for index, item in enumerate(bundle.evidence, 1)}
        seen: set[str] = set()
        points: list[dict[str, object]] = []
        summary_lines: list[str] = []
        for ordinal, point in enumerate(output.points, 1):
            if point.evidence_ref in seen or point.evidence_ref not in by_ref:
                raise InvalidSummary("knowledge.invalid_summary")
            seen.add(point.evidence_ref)
            quote = unicodedata.normalize("NFC", point.quote)
            evidence = by_ref[point.evidence_ref]
            if not 1 <= len(quote) <= limits.max_quote_chars or quote not in evidence.content:
                raise InvalidSummary("knowledge.invalid_summary")
            if any(ord(character) < 32 or ord(character) == 127 for character in quote):
                raise InvalidSummary("knowledge.invalid_summary")
            summary_lines.append(f"{ordinal}. {quote}")
            points.append(
                {
                    "quote": quote,
                    "citation": {
                        "evidenceId": evidence.evidence_id,
                        "domainIds": evidence.domain_ids,
                        "title": evidence.source.title,
                        "sourceUrl": evidence.source.source_url,
                        "documentNumber": evidence.source.document_number,
                        "writtenDate": evidence.source.written_date.isoformat() if evidence.source.written_date else None,
                    },
                }
            )
        answer = "\n".join(summary_lines)
        if len(answer) > 3072:
            raise InvalidSummary("knowledge.invalid_summary")
        domain_result: dict[str, object] = {
            "schemaVersion": 1,
            "summaryType": "extractive_evidence",
            "answerSummary": answer,
            "points": points,
            "coverage": {
                "retrievalComplete": bundle.coverage.retrieval_complete,
                "domainCoverageComplete": not bundle.coverage.missing_domain_ids,
                "selectedDomainIds": bundle.coverage.selected_domain_ids,
                "representedDomainIds": bundle.coverage.represented_domain_ids,
                "missingDomainIds": bundle.coverage.missing_domain_ids,
                "failedPaths": [
                    {
                        "logicalDomainId": item.logical_domain_id,
                        "path": item.path.value,
                        "failureKind": item.failure_kind.value,
                    }
                    for item in bundle.coverage.failed_paths
                ],
            },
        }
        if len(json.dumps(domain_result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")) > limits.max_domain_result_bytes:
            raise InvalidSummary("knowledge.invalid_summary")
        frozen = freeze_json_object(
            domain_result,
            max_bytes=limits.max_domain_result_bytes,
            max_depth=6,
            max_collection_items=256,
        )
        return SummaryValidationResult(domain_result=frozen, insufficient=False)
