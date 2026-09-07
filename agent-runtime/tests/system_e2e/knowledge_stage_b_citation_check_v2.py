"""Schema-2 adapter for the unchanged, post-execution source checker."""
from collections.abc import Mapping

from agent_runtime.knowledge.evidence.contracts import KnowledgeEvidenceBundle, KnowledgeRequirementSummaryInput, KnowledgeSummaryInput
from agent_runtime.knowledge.evidence.summary_task_v6 import requirement_summary_input_json
from tests.system_e2e.knowledge_stage_b_citation_check import CitationCheck, check_citations as check_v1

CHECK_VERSION = "stage-b-citation-binding-v2"


def check_citations(
    *, bundle: KnowledgeEvidenceBundle, summary_input: KnowledgeRequirementSummaryInput,
    points: object, required: Mapping[str, Mapping[str, str]],
) -> CitationCheck:
    if type(summary_input) is not KnowledgeRequirementSummaryInput:
        raise ValueError("stage_b.invalid_requirement_summary_input")
    requirement_summary_input_json(summary_input)
    projected = KnowledgeSummaryInput(schema_version=1, question=summary_input.question,
        coverage=summary_input.coverage, evidence=summary_input.evidence)
    result = check_v1(bundle=bundle, summary_input=projected, points=points, required=required)
    if not result.binding_valid:
        return result
    # Metadata omitted by policy stays omitted. Present metadata must be authentic.
    for actual, source in zip(summary_input.evidence, bundle.evidence, strict=True):
        if ((actual.title is not None and actual.title != source.source.title)
            or (actual.document_number is not None and actual.document_number != source.source.document_number)
            or (actual.written_date is not None and actual.written_date != (source.source.written_date.isoformat() if source.source.written_date else None))
            or (actual.material_type is not None and actual.material_type != source.source.material_type)):
            return CitationCheck(False, tuple((name, False) for name in required), "input_binding_invalid")
    return result
