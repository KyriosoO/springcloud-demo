from __future__ import annotations

import json

import pytest

from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeModeSummaryInput, KnowledgeSummaryInput, SummaryCoverageInput, SummaryEvidenceInput, SummaryOutcome,
)
from agent_runtime.knowledge.evidence.summary_task_v8 import (
    OUTPUT_NAME, KnowledgeSummaryTaskV8, mode_summary_input_json,
)
from agent_runtime.knowledge.intent_contracts import KnowledgeQueryMode
from agent_runtime.model.contracts import (
    InvalidModelOutput, ModelInputDenied, StructuredFinishKind, StructuredModelResponse,
    StructuredOutputMode, StructuredToolCall, StructuredToolMode,
)


def _input(mode: KnowledgeQueryMode = KnowledgeQueryMode.LOOKUP) -> KnowledgeModeSummaryInput:
    return KnowledgeModeSummaryInput(schema_version=3, question="查询增值税政策", query_mode=mode,
        coverage=SummaryCoverageInput(retrieval_complete=True, domain_coverage_complete=True),
        evidence=(SummaryEvidenceInput(evidence_ref="e1", content="税务政策正文", title="可信标题"),))


def _response(arguments: str, *, name: str = OUTPUT_NAME, content: str | None = None,
              multiple: bool = False) -> StructuredModelResponse:
    calls = (StructuredToolCall(name=name, arguments_json=arguments),)
    if multiple:
        calls += (StructuredToolCall(name=name, arguments_json=arguments),)
    return StructuredModelResponse(finish_kind=StructuredFinishKind.TOOL_CALLS, content=content,
        tool_calls=calls, usage_total_tokens=None)


def test_v8_exact_schema_only_request_and_explicit_mode_serializer():
    definition = KnowledgeSummaryTaskV8.definition()
    assert definition.task_version == "8" and definition.input_type is KnowledgeModeSummaryInput
    assert definition.timeout_ms == 15000 and definition.max_output_tokens == 1536
    for mode in (KnowledgeQueryMode.LOOKUP, KnowledgeQueryMode.EXPLANATION, KnowledgeQueryMode.APPLICABILITY):
        value = _input(mode)
        request = definition.build_request(value)
        payload = json.loads(request.user_payload_json)
        assert request.tool_mode is StructuredToolMode.SCHEMA_ONLY
        assert request.output_mode is StructuredOutputMode.TOOL_CALLS
        assert len(request.tools) == 1 and request.tools[0].name == OUTPUT_NAME
        assert len(request.system_instruction.encode("utf-8")) <= 8192
        assert set(payload) == {"schema_version", "question", "query_mode", "coverage", "evidence"}
        assert payload["schema_version"] == 3 and payload["query_mode"] == mode.value
        assert payload["evidence"] == [{"evidence_ref": "e1", "content": "税务政策正文", "title": "可信标题"}]
        assert "requirements" not in request.user_payload_json and "source_url" not in request.user_payload_json


def test_v8_input_type_version_and_budget_fail_before_transport():
    definition = KnowledgeSummaryTaskV8.definition()
    value = _input()
    old = KnowledgeSummaryInput(schema_version=1, question=value.question,
        coverage=value.coverage, evidence=value.evidence)
    for invalid in (old, KnowledgeModeSummaryInput(schema_version=2, question=value.question,
        query_mode=value.query_mode, coverage=value.coverage, evidence=value.evidence),
        KnowledgeModeSummaryInput(schema_version=3, question=value.question,
            query_mode=KnowledgeQueryMode.NONE, coverage=value.coverage, evidence=value.evidence),
        KnowledgeModeSummaryInput(schema_version=3, question=value.question,
            query_mode=value.query_mode, coverage=value.coverage,
            evidence=(SummaryEvidenceInput(evidence_ref="e2", content="正文"),))):
        with pytest.raises(ModelInputDenied):
            definition.build_request(invalid)
    huge = KnowledgeModeSummaryInput(schema_version=3, question=value.question, query_mode=value.query_mode,
        coverage=value.coverage, evidence=tuple(SummaryEvidenceInput(evidence_ref=f"e{index}", content="税" * 4096)
            for index in range(1, 9)))
    assert len(mode_summary_input_json(huge, max_bytes=None).encode("utf-8")) > 32768
    with pytest.raises(ModelInputDenied):
        definition.build_request(huge)


def test_v8_decoder_returns_only_exact_minimal_output():
    parse = KnowledgeSummaryTaskV8.definition().parse_response
    answer = parse(_response('{"outcome":"answer","points":[{"evidence_ref":"e1","quote":"税务政策正文"}]}'))
    insufficient = parse(_response('{"outcome":"insufficient_evidence","points":[]}'))
    assert answer.outcome is SummaryOutcome.ANSWER and answer.points[0].quote == "税务政策正文"
    assert insufficient.outcome is SummaryOutcome.INSUFFICIENT_EVIDENCE and insufficient.points == ()


@pytest.mark.parametrize("arguments", [
    '{"outcome":"answer","points":[{"evidence_ref":"e1","quote":"正文"}],"coverage":[]}',
    '{"outcome":"answer","outcome":"answer","points":[{"evidence_ref":"e1","quote":"正文"}]}',
    '{"outcome":"answer","points":[]}',
    '{"outcome":"insufficient_evidence","points":[{"evidence_ref":"e1","quote":"正文"}]}',
    '{"outcome":"answer","points":[{"evidence_ref":"e9","quote":"正文"}]}',
    '{"outcome":"answer","points":[{"evidence_ref":"e1","quote":1}]}',
    '{"outcome":"answer","points":[{"evidence_ref":"e1","quote":"正文","citation":"fake"}]}',
    '{"outcome":"answer","points":NaN}',
])
def test_v8_decoder_rejects_unknown_duplicate_or_invalid_fields(arguments):
    with pytest.raises(InvalidModelOutput):
        KnowledgeSummaryTaskV8.definition().parse_response(_response(arguments))


@pytest.mark.parametrize("kwargs", [{"name": "other"}, {"content": "额外正文"}, {"multiple": True}])
def test_v8_decoder_rejects_wrong_envelope(kwargs):
    with pytest.raises(InvalidModelOutput):
        KnowledgeSummaryTaskV8.definition().parse_response(_response('{"outcome":"insufficient_evidence","points":[]}', **kwargs))
