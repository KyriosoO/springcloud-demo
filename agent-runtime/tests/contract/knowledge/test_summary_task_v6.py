from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict, replace
import json

import pytest

from agent_runtime.knowledge.evidence.contracts import KnowledgeSummaryInput, KnowledgeRequirementSummaryInput, KnowledgeRequirementSummaryOutput
from agent_runtime.knowledge.evidence.summary_task import summary_input_json
from agent_runtime.knowledge.evidence.summary_task_v5 import KnowledgeSummaryTaskV5
from agent_runtime.knowledge.evidence.summary_task_v6 import KnowledgeSummaryTaskV6, SUMMARY_PROMPT_V6, requirement_summary_input_json
from agent_runtime.model.contracts import InvalidModelOutput, ModelCallContext, ModelProviderFailureKind, StructuredFinishKind
from agent_runtime.model.gateway import BoundedStructuredModelGateway
from tests.contract.knowledge.test_summary_task_v5 import _response
from tests.model_helpers import FakeStructuredModelTransport
from tests.requirement_evidence_helpers import bound_input, output_for


def wire():
    _, _, value = bound_input()
    return json.loads(json.dumps(asdict(output_for(value))))


def parse(value):
    return KnowledgeSummaryTaskV6.definition().parse_response(_response(json.dumps(value)))


def test_precise_version_subtype_prompt_limits_and_old_payload_unchanged():
    _, _, value = bound_input()
    new = KnowledgeSummaryTaskV6.definition()
    request = new.build_request(value)
    assert (new.input_type, new.task_version, new.max_input_bytes, new.timeout_ms, new.max_output_tokens) == (
        KnowledgeRequirementSummaryInput, "6", 49152, 15000, 1536)
    assert len(SUMMARY_PROMPT_V6.encode()) <= 8192 and request.tools == ()
    payload = json.loads(request.user_payload_json)
    assert set(payload) == {"schema_version", "question", "coverage", "evidence", "requirements"}
    assert payload["schema_version"] == 2 and len(payload["requirements"]) == 3
    assert all(set(r) == {"requirement_id", "domain_id", "kind", "focus"} for r in payload["requirements"])
    for token in ("酒店", "住宿", "gold", "KB-", "candidate-", "policy_ref", "content_sha256", "requirement_ids"):
        assert token not in request.user_payload_json + SUMMARY_PROMPT_V6
    for token in ("实际输出的quote", "每个需求", "不增删", "分类", "常识", "部分肯定", "连续", "512", "唯一ref"):
        assert token in SUMMARY_PROMPT_V6
    base = KnowledgeSummaryInput(schema_version=1, question=value.question, coverage=value.coverage, evidence=value.evidence)
    assert json.loads(summary_input_json(base)).keys() == {"schema_version", "question", "coverage", "evidence"}
    assert KnowledgeSummaryTaskV5.definition().build_request(base).user_payload_json == summary_input_json(base)
    with pytest.raises(FrozenInstanceError):
        value.requirements = ()


@pytest.mark.parametrize("fault", ["old_type", "schema_bool", "schema_old", "no_requirements", "list_requirements", "bad_id", "extra_req", "too_many_evidence", "no_evidence", "too_many_bytes"])
def test_bad_input_rejected_before_transport(fault):
    _, _, value = bound_input()
    if fault == "old_type":
        value = KnowledgeSummaryInput(schema_version=1, question=value.question, coverage=value.coverage, evidence=value.evidence)
    elif fault in {"schema_bool", "schema_old"}:
        value = replace(value, schema_version=True if fault == "schema_bool" else 1)
    elif fault in {"no_requirements", "list_requirements", "extra_req", "bad_id"}:
        reqs = () if fault == "no_requirements" else list(value.requirements) if fault == "list_requirements" else value.requirements * 2 if fault == "extra_req" else (replace(value.requirements[0], requirement_id="r0"),) + value.requirements[1:]
        value = replace(value, requirements=reqs)
    elif fault == "too_many_bytes":
        value = replace(value, evidence=(replace(value.evidence[0], content="字" * 11000),))
    else:
        value = replace(value, evidence=() if fault == "no_evidence" else value.evidence * 3)
    with pytest.raises(ValueError):
        KnowledgeSummaryTaskV6.definition().build_request(value)


@pytest.mark.asyncio
@pytest.mark.parametrize("new_task", [True, False])
async def test_gateway_exact_type_pairing_has_zero_outbound(new_task):
    _, _, value = bound_input()
    definition = KnowledgeSummaryTaskV6.definition() if new_task else KnowledgeSummaryTaskV5.definition()
    if new_task:
        value = KnowledgeSummaryInput(schema_version=1, question=value.question, coverage=value.coverage, evidence=value.evidence)
    transport = FakeStructuredModelTransport()
    gateway = BoundedStructuredModelGateway(transport=transport, definitions=(definition,), max_concurrency=1)
    result = await gateway.generate(definition=definition, input=value, context=ModelCallContext(request_id="r", correlation_id="c", deadline_monotonic=0))
    assert result.failure_kind is ModelProviderFailureKind.INPUT_DENIED and transport.calls == 0


def test_valid_output_exact_frozen_subtype_and_insufficient():
    value = parse(wire())
    assert type(value) is KnowledgeRequirementSummaryOutput and type(value.coverage) is tuple
    with pytest.raises(FrozenInstanceError):
        value.coverage = ()
    insufficient = parse({"outcome": "insufficient_evidence", "points": [], "coverage": []})
    assert insufficient.points == insufficient.coverage == ()


@pytest.mark.parametrize("fault", ["extra", "missing", "null", "outcome_bool", "points_null", "coverage_null", "zero_points", "six_points", "zero_coverage", "five_coverage", "extra_point", "null_quote", "bad_ref", "duplicate_ref", "extra_coverage", "bad_id", "repeat_id", "empty_refs", "duplicate_refs", "ref_null", "wrong_ref", "insufficient_nonempty"])
def test_exact_decoder_rejects_invalid_shapes(fault):
    value = deepcopy(wire())
    if fault == "extra": value["extra"] = 1
    elif fault == "missing": del value["coverage"]
    elif fault == "null": value = None
    elif fault == "outcome_bool": value["outcome"] = True
    elif fault == "points_null": value["points"] = None
    elif fault == "coverage_null": value["coverage"] = None
    elif fault == "zero_points": value["points"] = []
    elif fault == "six_points": value["points"] *= 2
    elif fault == "zero_coverage": value["coverage"] = []
    elif fault == "five_coverage": value["coverage"] *= 2
    elif fault == "extra_point": value["points"][0]["extra"] = 1
    elif fault == "null_quote": value["points"][0]["quote"] = None
    elif fault == "bad_ref": value["points"][0]["evidence_ref"] = "e9"
    elif fault == "duplicate_ref": value["points"][1] = value["points"][0]
    elif fault == "extra_coverage": value["coverage"][0]["extra"] = 1
    elif fault == "bad_id": value["coverage"][0]["requirement_id"] = "r5"
    elif fault == "repeat_id": value["coverage"][1] = value["coverage"][0]
    elif fault == "empty_refs": value["coverage"][0]["evidence_refs"] = []
    elif fault == "duplicate_refs": value["coverage"][0]["evidence_refs"] = ["e1", "e1"]
    elif fault == "ref_null": value["coverage"][0]["evidence_refs"] = None
    elif fault == "wrong_ref": value["coverage"][0]["evidence_refs"] = [True]
    elif fault == "insufficient_nonempty": value["outcome"] = "insufficient_evidence"
    with pytest.raises(InvalidModelOutput): parse(value)


@pytest.mark.parametrize("body", ['{"outcome":"answer","outcome":"answer","points":[],"coverage":[]}',
    '{"outcome":"answer","points":[{"evidence_ref":"e1","evidence_ref":"e1","quote":"q"}],"coverage":[]}',
    '```json\n{"outcome":"insufficient_evidence","points":[],"coverage":[]}\n```'])
def test_duplicate_keys_and_markdown_rejected(body):
    with pytest.raises(InvalidModelOutput): KnowledgeSummaryTaskV6.definition().parse_response(_response(body))


@pytest.mark.parametrize("fault", ["nonstop", "missing_content"])
def test_nonstop_or_missing_output_rejected(fault):
    with pytest.raises(InvalidModelOutput):
        response = _response(json.dumps(wire()))
        response = replace(response, finish_kind=StructuredFinishKind.TOOL_CALLS) if fault == "nonstop" else replace(response, content=None)
        KnowledgeSummaryTaskV6.definition().parse_response(response)
