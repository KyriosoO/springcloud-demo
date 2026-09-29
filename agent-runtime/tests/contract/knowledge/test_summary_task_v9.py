from __future__ import annotations

import json
from typing import Any, cast

import pytest

from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeModeSummaryInput, KnowledgeSummaryInput, SummaryCoverageInput, SummaryEvidenceInput,
    SummaryOutcome,
)
from agent_runtime.knowledge.evidence.summary_task_v9 import OUTPUT_NAME, KnowledgeSummaryTaskV9
from agent_runtime.capability_api.contracts import canonical_json_bytes
from agent_runtime.knowledge.intent_contracts import KnowledgeQueryMode
from agent_runtime.model.contracts import (
    InvalidModelOutput, ModelInputDenied, StructuredFinishKind, StructuredModelResponse,
    StructuredOutputMode, StructuredToolCall, StructuredToolMode,
)


def _input(mode: KnowledgeQueryMode = KnowledgeQueryMode.LOOKUP) -> KnowledgeModeSummaryInput:
    return KnowledgeModeSummaryInput(
        schema_version=3, question="查询增值税政策", query_mode=mode,
        coverage=SummaryCoverageInput(retrieval_complete=True, domain_coverage_complete=True),
        evidence=(SummaryEvidenceInput(evidence_ref="e1", content="税务政策正文"),),
    )


def _response(arguments: str, *, name: str = OUTPUT_NAME, content: str | None = None,
              multiple: bool = False) -> StructuredModelResponse:
    calls: tuple[StructuredToolCall, ...] = (StructuredToolCall(name=name, arguments_json=arguments),)
    if multiple:
        calls += (StructuredToolCall(name=name, arguments_json=arguments),)
    return StructuredModelResponse(finish_kind=StructuredFinishKind.TOOL_CALLS, content=content,
                                   tool_calls=calls, usage_total_tokens=None)


def test_v9_one_schema_only_task_and_existing_mode_input_contract() -> None:
    definition = KnowledgeSummaryTaskV9.definition()
    assert definition.task_version == "9" and definition.input_type is KnowledgeModeSummaryInput
    assert definition.timeout_ms == 15000 and definition.max_output_tokens == 1536
    for mode in (KnowledgeQueryMode.LOOKUP, KnowledgeQueryMode.EXPLANATION, KnowledgeQueryMode.APPLICABILITY):
        request = definition.build_request(_input(mode))
        payload = json.loads(request.user_payload_json)
        assert request.tool_mode is StructuredToolMode.SCHEMA_ONLY
        assert request.output_mode is StructuredOutputMode.TOOL_CALLS
        assert len(request.tools) == 1 and request.tools[0].name == OUTPUT_NAME
        assert len(request.system_instruction.encode("utf-8")) <= 8192
        assert request.max_output_tokens == 1536
        assert payload == {"schema_version": 3, "question": "查询增值税政策",
                           "query_mode": mode.value,
                           "coverage": {"retrieval_complete": True, "domain_coverage_complete": True},
                           "evidence": [{"evidence_ref": "e1", "content": "税务政策正文"}]}
        schema = cast(dict[str, Any], json.loads(canonical_json_bytes(request.tools[0].arguments_schema)))
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == {"outcome", "points"}
        point_schema = schema["properties"]["points"]["items"]
        assert point_schema["additionalProperties"] is False
        assert set(point_schema["required"]) == {"evidence_ref", "quote", "claim"}


def test_v9_input_mismatch_and_budget_fail_before_transport() -> None:
    definition = KnowledgeSummaryTaskV9.definition()
    value = _input()
    invalid = (
        KnowledgeSummaryInput(schema_version=3, question=value.question,
                              coverage=value.coverage, evidence=value.evidence),
        KnowledgeModeSummaryInput(schema_version=2, question=value.question, query_mode=value.query_mode,
                                  coverage=value.coverage, evidence=value.evidence),
        KnowledgeModeSummaryInput(schema_version=3, question=value.question, query_mode=KnowledgeQueryMode.NONE,
                                  coverage=value.coverage, evidence=value.evidence),
        KnowledgeModeSummaryInput(schema_version=3, question=value.question, query_mode=value.query_mode,
                                  coverage=value.coverage,
                                  evidence=(SummaryEvidenceInput(evidence_ref="e2", content="正文"),)),
        KnowledgeModeSummaryInput(schema_version=3, question=value.question, query_mode=value.query_mode,
                                  coverage=value.coverage,
                                  evidence=tuple(SummaryEvidenceInput(evidence_ref=f"e{index}", content="税" * 4096)
                                                 for index in range(1, 9))),
    )
    for item in invalid:
        with pytest.raises(ModelInputDenied):
            definition.build_request(item)


def test_v9_exact_output_and_insufficient_are_separate_from_v8() -> None:
    parse = KnowledgeSummaryTaskV9.definition().parse_response
    answer = parse(_response('{"outcome":"answer","points":[{"evidence_ref":"e1",'
                             '"quote":"税务政策正文","claim":"相关政策见引文。"}]}'))
    insufficient = parse(_response('{"outcome":"insufficient_evidence","points":[]}'))
    assert answer.outcome is SummaryOutcome.ANSWER and answer.points[0].claim == "相关政策见引文。"
    assert insufficient.outcome is SummaryOutcome.INSUFFICIENT_EVIDENCE and insufficient.points == ()


@pytest.mark.parametrize("arguments", [
    '{"outcome":"answer","points":[{"evidence_ref":"e1","quote":"正文"}]}',
    '{"outcome":"answer","points":[{"evidence_ref":"e1","quote":"正文","claim":"答",'
    '"citation":"伪引用"}]}',
    '{"outcome":"answer","points":[],"coverage":[]}',
    '{"outcome":"answer","outcome":"answer","points":[]}',
    '{"outcome":"answer","points":[]}',
    '{"outcome":"insufficient_evidence","points":[{"evidence_ref":"e1","quote":"正文",'
    '"claim":"答"}]}',
    '{"outcome":"answer","points":[{"evidence_ref":"e9","quote":"正文","claim":"答"}]}',
    '{"outcome":"answer","points":[{"evidence_ref":"e1","quote":"正文","claim":1}]}',
    '{"outcome":"answer","points":NaN}',
])
def test_v9_decoder_rejects_missing_extra_duplicate_or_malformed_fields(arguments: str) -> None:
    with pytest.raises(InvalidModelOutput):
        KnowledgeSummaryTaskV9.definition().parse_response(_response(arguments))


@pytest.mark.parametrize("name,content,multiple", [
    ("other", None, False), (OUTPUT_NAME, "额外正文", False), (OUTPUT_NAME, None, True),
])
def test_v9_decoder_rejects_wrong_envelope(name: str, content: str | None, multiple: bool) -> None:
    with pytest.raises(InvalidModelOutput):
        KnowledgeSummaryTaskV9.definition().parse_response(
            _response('{"outcome":"insufficient_evidence","points":[]}',
                      name=name, content=content, multiple=multiple),
        )
