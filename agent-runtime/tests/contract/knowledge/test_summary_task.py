from __future__ import annotations

import json

import pytest

from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeSummaryInput,
    SummaryCoverageInput,
    SummaryEvidenceInput,
    SummaryOutcome,
)
from agent_runtime.knowledge.evidence.summary_task import KnowledgeSummaryTaskV1
from agent_runtime.model.contracts import InvalidModelOutput, StructuredFinishKind, StructuredModelResponse


def _input() -> KnowledgeSummaryInput:
    return KnowledgeSummaryInput(
        schema_version=1,
        question="税务政策",
        coverage=SummaryCoverageInput(retrieval_complete=True, domain_coverage_complete=True),
        evidence=(SummaryEvidenceInput(evidence_ref="e1", content="税务政策正文", domain_ids=("tax.policy",)),),
    )


def test_summary_task_has_no_tools_or_internal_evidence_identity() -> None:
    definition = KnowledgeSummaryTaskV1.definition()
    request = definition.build_request(_input())
    payload = json.loads(request.user_payload_json)

    assert request.tools == ()
    assert request.task_id.value == "knowledge_summary"
    assert payload["evidence"][0]["evidence_ref"] == "e1"
    assert not set(payload["evidence"][0]) & {"evidence_id", "document_id", "chunk_id", "source_url", "policy_ref"}


def test_summary_parser_rejects_extra_fields() -> None:
    definition = KnowledgeSummaryTaskV1.definition()
    with pytest.raises(InvalidModelOutput):
        definition.parse_response(
            StructuredModelResponse(
                finish_kind=StructuredFinishKind.STOP,
                content='{"outcome":"answer","points":[],"answer":"bad"}',
                tool_calls=(), usage_total_tokens=None,
            )
        )


def test_summary_parser_accepts_typed_answer() -> None:
    output = KnowledgeSummaryTaskV1.definition().parse_response(
        StructuredModelResponse(
            finish_kind=StructuredFinishKind.STOP,
            content='{"outcome":"answer","points":[{"evidence_ref":"e1","quote":"税务政策正文"}]}',
            tool_calls=(), usage_total_tokens=None,
        )
    )
    assert output.outcome is SummaryOutcome.ANSWER

