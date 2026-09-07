"""Validate declared coverage and authorized sources, not semantic entailment."""
from __future__ import annotations

import hashlib
import unicodedata

from agent_runtime.knowledge.contracts import KnowledgeEvidenceRequirement
from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeEvidenceBundle, KnowledgeRequirementSummaryInput, KnowledgeRequirementSummaryOutput,
    KnowledgeSummaryOutput, KnowledgeSummaryPoint, SummaryOutcome, SummaryRequirementCoverage,
)
from agent_runtime.knowledge.evidence.summary_task_v6 import requirement_summary_input_json
from agent_runtime.knowledge.evidence.summary_validation import InvalidSummary, SummaryValidationFailureReason


def _invalid() -> InvalidSummary:
    return InvalidSummary(SummaryValidationFailureReason.UNKNOWN_EVIDENCE_REF)


class RequirementCoverageValidator:
    def validate(
        self, *, output: KnowledgeSummaryOutput, requirements: tuple[KnowledgeEvidenceRequirement, ...],
        summary_input: KnowledgeRequirementSummaryInput, bundle: KnowledgeEvidenceBundle,
    ) -> KnowledgeSummaryOutput:
        if (type(output) is not KnowledgeRequirementSummaryOutput or not isinstance(output, KnowledgeRequirementSummaryOutput)
            or type(summary_input) is not KnowledgeRequirementSummaryInput or requirements != summary_input.requirements):
            raise _invalid()
        try:
            requirement_summary_input_json(summary_input)
        except (ValueError, AttributeError, TypeError) as exc:
            raise _invalid() from exc
        if (type(output.points) is not tuple or type(output.coverage) is not tuple
            or any(type(item) is not KnowledgeSummaryPoint or type(item.quote) is not str for item in output.points)
            or any(type(item) is not SummaryRequirementCoverage for item in output.coverage)
            or summary_input.question != bundle.question_trace.minimized_question
            or summary_input.coverage.retrieval_complete != bundle.coverage.retrieval_complete
            or summary_input.coverage.domain_coverage_complete != (not bundle.coverage.missing_domain_ids)
            or len(summary_input.evidence) != len(bundle.evidence) or not 1 <= len(bundle.evidence) <= 8
            or len({item.evidence_id for item in bundle.evidence}) != len(bundle.evidence)
            or len({(item.document_id, item.chunk_id) for item in bundle.evidence}) != len(bundle.evidence)):
            raise _invalid()
        for index, (actual, source) in enumerate(zip(summary_input.evidence, bundle.evidence, strict=True), 1):
            material = f"{unicodedata.normalize('NFC', source.document_id)}\n{unicodedata.normalize('NFC', source.chunk_id)}\n{source.content_sha256}"
            if (actual.evidence_ref != f"e{index}" or actual.content != source.content
                or hashlib.sha256(unicodedata.normalize("NFC", actual.content).encode()).hexdigest() != source.content_sha256
                or "ev-" + hashlib.sha256(material.encode()).hexdigest() != source.evidence_id
                or (actual.domain_ids is not None and actual.domain_ids != source.domain_ids)
                or (actual.title is not None and actual.title != source.source.title)
                or (actual.document_number is not None and actual.document_number != source.source.document_number)
                or (actual.written_date is not None and actual.written_date != (source.source.written_date.isoformat() if source.source.written_date else None))
                or (actual.material_type is not None and actual.material_type != source.source.material_type)):
                raise _invalid()
        if output.outcome is SummaryOutcome.INSUFFICIENT_EVIDENCE:
            if output.points or output.coverage:
                raise _invalid()
            return KnowledgeSummaryOutput(outcome=output.outcome, points=())
        if output.outcome is not SummaryOutcome.ANSWER or not 1 <= len(output.points) <= 5:
            raise _invalid()
        if tuple(item.requirement_id for item in output.coverage) != tuple(item.requirement_id for item in requirements):
            raise _invalid()
        point_refs = tuple(item.evidence_ref for item in output.points)
        if any(type(ref) is not str for ref in point_refs) or len(set(point_refs)) != len(point_refs):
            raise _invalid()
        by_ref = {f"e{index}": item for index, item in enumerate(bundle.evidence, 1)}
        used: set[str] = set()
        for declaration, requirement in zip(output.coverage, requirements, strict=True):
            refs = declaration.evidence_refs
            if (type(refs) is not tuple or not 1 <= len(refs) <= 5 or any(type(ref) is not str for ref in refs)
                or len(set(refs)) != len(refs) or any(ref not in point_refs or ref not in by_ref for ref in refs)
                or any(requirement.domain_id not in by_ref[ref].domain_ids for ref in refs)):
                raise _invalid()
            used.update(refs)
        if used != set(point_refs):
            raise _invalid()
        return KnowledgeSummaryOutput(outcome=output.outcome, points=output.points)
