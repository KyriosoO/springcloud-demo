"""Output envelope is strict; semantic decisions still pass the unchanged validators."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess

import pytest

from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput
from agent_runtime.knowledge.rewrite_v9 import KnowledgeRewriteTaskV9
from agent_runtime.knowledge.rewrite_v10 import KnowledgeRewriteTaskV10, OUTPUT_NAME
from agent_runtime.model.contracts import (
    InvalidModelOutput, ModelInputDenied, StructuredFinishKind, StructuredModelResponse,
    StructuredToolCall, StructuredToolMode, StructuredOutputMode,
)
from agent_runtime.model.deepseek.dto import project_deepseek_request
from tests.contract.knowledge.test_rewrite_task_v2 import _response
from tests.contract.knowledge.test_rewrite_task_v7 import invalid_values, wire_plan


def response(value, *, name=OUTPUT_NAME, content=None):
    return StructuredModelResponse(
        finish_kind=StructuredFinishKind.TOOL_CALLS, content=content,
        tool_calls=(StructuredToolCall(name=name, arguments_json=json.dumps(value, ensure_ascii=False)),),
        usage_total_tokens=0,
    )


def request():
    return KnowledgeRewriteTaskV10.definition().build_request(KnowledgeSemanticPlanInput(
        minimized_question="税务政策及法律规则", enabled_domain_ids=("tax.policy", "tax.law"),
    ))


def test_request_has_exact_nested_schema_and_preserves_semantics_and_limits():
    current = request()
    old = KnowledgeRewriteTaskV9.definition().build_request(KnowledgeSemanticPlanInput(
        minimized_question="税务政策及法律规则", enabled_domain_ids=("tax.policy", "tax.law"),
    ))
    assert current.task_version == "10" and current.max_output_tokens == old.max_output_tokens == 1536
    assert current.user_payload_json == old.user_payload_json
    assert current.tool_mode is StructuredToolMode.SCHEMA_ONLY
    assert current.output_mode is StructuredOutputMode.TOOL_CALLS
    assert len(current.tools) == 1 and current.tools[0].name == OUTPUT_NAME
    schema = current.tools[0].arguments_schema
    assert set(schema["required"]) == {"outcome", "question_kind", "queries", "requirements", "missing_conditions"}
    assert schema["additionalProperties"] is False
    for field in ("queries", "requirements"):
        child = schema["properties"][field]["items"]
        assert set(child["required"]) == set(child["properties"])
        assert child["additionalProperties"] is False
        assert child["properties"]["domain_id"]["enum"] == ("tax.policy", "tax.law")
    assert len(current.system_instruction.encode()) <= 8192
    assert "工具调用或代码" not in current.system_instruction
    assert "不执行函数" in current.system_instruction and "未分配给任何focus" in current.system_instruction
    assert not any(s in current.system_instruction for s in ("KRB-", "gold", "酒店", "root_fields"))
    assert KnowledgeRewriteTaskV10.definition().timeout_ms == KnowledgeRewriteTaskV9.definition().timeout_ms


@pytest.mark.parametrize("value", [wire_plan(), wire_plan(applicability=True), wire_plan(applicability=True, second_domain=True),
    dict(outcome="clarification_required", question_kind="none", queries=[], requirements=[], missing_conditions=["taxpayer_type"]),
    dict(outcome="unsupported", question_kind="none", queries=[], requirements=[], missing_conditions=[])])
def test_valid_semantics_equal_v9_without_field_repair(value):
    assert KnowledgeRewriteTaskV10.definition().parse_response(response(value)) == KnowledgeRewriteTaskV9.definition().parse_response(
        _response(json.dumps(value)))


@pytest.mark.parametrize("value", invalid_values())
def test_original_semantic_rejections_still_apply(value):
    with pytest.raises(InvalidModelOutput):
        KnowledgeRewriteTaskV10.definition().parse_response(response(value))


@pytest.mark.parametrize("fault", ["none", "two", "name", "text", "whitespace", "duplicate", "nan", "truncated", "root_fields"])
def test_invalid_framing_fails_without_coercion(fault):
    item = response(wire_plan())
    if fault == "none": item = _response(json.dumps(wire_plan()))
    elif fault == "two": item = replace(item, tool_calls=item.tool_calls * 2)
    elif fault == "name": item = response(wire_plan(), name="execute_search")
    elif fault in {"text", "whitespace"}: item = replace(item, content="explanation" if fault == "text" else " ")
    else:
        raw = {"duplicate": '{"outcome":"search","outcome":"unsupported"}', "nan": '{"outcome":NaN}',
               "truncated": '{"outcome":', "root_fields": '{}'}[fault]
        item = replace(item, tool_calls=(StructuredToolCall(name=OUTPUT_NAME, arguments_json=raw),))
    with pytest.raises(InvalidModelOutput): KnowledgeRewriteTaskV10.definition().parse_response(item)


@pytest.mark.parametrize("tools", [(), "duplicate"])
def test_request_enforces_exactly_one_output_definition(tools):
    item = request()
    with pytest.raises(ModelInputDenied): replace(item, tools=item.tools * 2 if tools == "duplicate" else tools)


def test_provider_strict_projection_and_no_json_mode_conflict():
    payload = project_deepseek_request(request()).payload
    assert payload["model"] == "deepseek-flash"
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["tool_choice"] == {"type": "function", "function": {"name": OUTPUT_NAME}}
    assert payload["tools"][0]["function"]["strict"] is True
    assert "response_format" not in payload and payload["stream"] is False


@pytest.mark.parametrize("fault", ["optional", "minItems", "maxLength", "number"])
def test_provider_does_not_silently_drop_unsupported_schema_constraints(fault):
    item = request()
    # All are valid generic Core schemas, but not this deliberately bounded provider subset.
    prop = {"type": "array", "items": {"type": "string"}, "minItems": 1} if fault == "minItems" else (
        {"type": "string", "maxLength": 12} if fault == "maxLength" else
        {"type": "number"} if fault == "number" else {"type": "string"})
    schema = {"type": "object", "properties": {"x": prop}, "required": [] if fault == "optional" else ["x"],
              "additionalProperties": False}
    changed = replace(item, tools=(replace(item.tools[0], arguments_schema=schema),))
    with pytest.raises(ModelInputDenied, match="strict_schema_unsupported"): project_deepseek_request(changed)


def test_historical_rewrite_sources_are_unchanged():
    repo = Path(__file__).resolve().parents[4]
    baseline = "e50eae962c499fe4b747e7cb5f7fb9e6c1c48b6b"
    for name in ("rewrite.py", *(f"rewrite_v{version}.py" for version in range(2, 10))):
        path = repo / "agent-runtime/src/agent_runtime/knowledge" / name
        relative = path.relative_to(repo).as_posix()
        frozen = subprocess.check_output(["git", "show", f"{baseline}:{relative}"], cwd=repo)
        assert path.read_text(encoding="utf-8").encode() == frozen
