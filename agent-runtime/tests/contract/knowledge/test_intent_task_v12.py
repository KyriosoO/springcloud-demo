from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from itertools import product
import json

import pytest

from agent_runtime.knowledge.intent_contracts import KnowledgeQueryIntentInput
from agent_runtime.knowledge.intent_task_v12 import KnowledgeQueryIntentTaskV12, OUTPUT_NAME
from agent_runtime.model.contracts import (
    InvalidModelOutput, ModelInputDenied, ModelTaskId, StructuredFinishKind,
    StructuredModelResponse, StructuredToolCall, StructuredToolMode, StructuredOutputMode,
)
from agent_runtime.model.deepseek.dto import project_deepseek_request
from agent_runtime.model.gateway import FrozenModelTaskRegistry


DOMAINS = ("tax.policy", "tax.law")


def definition(domains=DOMAINS):
    return KnowledgeQueryIntentTaskV12.definition(enabled_domain_ids=domains)


def wire(*, outcome="search", mode="lookup", domains=DOMAINS, selected=("tax.policy",), missing=()):
    return {"outcome": outcome, "query_mode": mode,
            "domains": {domain: "selected" if domain in selected else "not_selected" for domain in domains},
            "missing_conditions": list(missing)}


def response(value=None, *, raw=None):
    return StructuredModelResponse(finish_kind=StructuredFinishKind.TOOL_CALLS, content=None,
        tool_calls=(StructuredToolCall(name=OUTPUT_NAME, arguments_json=json.dumps(value) if raw is None else raw),),
        usage_total_tokens=0)


@pytest.mark.parametrize("domains", [DOMAINS, ("tax.policy",), ("tax.law",)])
def test_schema_catalog_limits_and_provider_subset_are_code_bound(domains):
    task = definition(domains)
    question = "税" * 1024
    request = task.build_request(KnowledgeQueryIntentInput(minimized_question=question))
    assert (task.task_id, task.task_version, task.max_input_bytes, task.timeout_ms, task.max_output_tokens) == (
        ModelTaskId.KNOWLEDGE_REWRITE, "12", 16384, 8000, 512)
    assert len(request.system_instruction.encode()) <= 8192
    assert len(request.user_payload_json.encode()) <= task.max_input_bytes
    assert request.max_output_tokens == 512
    payload = json.loads(request.user_payload_json)
    assert set(payload) == {"question", "domains"} and payload["question"] == question
    assert tuple(item["domain_id"] for item in payload["domains"]) == domains
    assert all(set(item) == {"domain_id", "description"} for item in payload["domains"])
    assert request.tool_mode is StructuredToolMode.SCHEMA_ONLY
    assert request.output_mode is StructuredOutputMode.TOOL_CALLS
    assert len(request.tools) == 1 and request.tools[0].name == OUTPUT_NAME
    schema = request.tools[0].arguments_schema
    assert schema["required"] == ("outcome", "query_mode", "domains", "missing_conditions")
    assert schema["additionalProperties"] is False
    slots = schema["properties"]["domains"]
    assert slots["required"] == domains and slots["additionalProperties"] is False
    assert tuple(slots["properties"]) == domains
    assert schema["properties"]["missing_conditions"]["items"]["enum"] == (
        "subject", "period", "taxpayer_type", "calculation_method")
    projected = project_deepseek_request(request).payload
    assert projected["tool_choice"] == {"type": "function", "function": {"name": OUTPUT_NAME}}
    assert projected["tools"][0]["function"]["strict"] is True
    assert "response_format" not in projected
    for fragment in ("普通资料查找不机械要求", "不根据后续结果再次选域", "不生成答案或检索表达",
                     "不得猜测、补造或改变", "无法可靠确定意图", "这是结构化输出封套"):
        assert fragment in request.system_instruction


@pytest.mark.parametrize("domains", [None, [], (), ["tax.policy"], (True,), ("employee",),
    ("tax.policy", "tax.policy"), ("tax.law", "tax.policy"), DOMAINS + ("extra",)])
def test_invalid_catalog_cannot_create_task(domains):
    with pytest.raises(ValueError, match="knowledge.enabled_domains_invalid"):
        definition(domains)


def test_input_and_registration_are_exact():
    with pytest.raises(ModelInputDenied):
        definition().build_request({"question": "税务政策"})
    with pytest.raises(ValueError, match="model.duplicate_task_definition"):
        FrozenModelTaskRegistry((definition(), definition()))


@pytest.mark.parametrize("outcome,mode,selected,missing", product(
    ("search", "clarification_required", "unsupported"),
    ("lookup", "explanation", "applicability", "none"),
    ((), ("tax.policy",), ("tax.law",), DOMAINS),
    ((), ("period",), ("subject", "period", "taxpayer_type", "calculation_method")),
))
def test_terminal_combination_matrix(outcome, mode, selected, missing):
    value = wire(outcome=outcome, mode=mode, selected=selected, missing=missing)
    valid = (
        outcome == "search" and mode != "none" and bool(selected) and not missing
        or outcome == "clarification_required" and mode != "none" and not selected and bool(missing)
        or outcome == "unsupported" and mode == "none" and not selected and not missing
    )
    if valid:
        actual = definition().parse_response(response(value))
        assert (actual.outcome, actual.query_mode, actual.selected_domain_ids, actual.missing_conditions) == (
            outcome, mode, selected, missing)
    else:
        with pytest.raises(InvalidModelOutput, match="knowledge.invalid_query_intent"):
            definition().parse_response(response(value))


@pytest.mark.parametrize("field,value", [
    ("outcome", None), ("outcome", True), ("outcome", "answer"), ("query_mode", "application"),
    ("query_mode", None), ("domains", None), ("domains", []), ("domains", {}),
    ("domains", {"tax.policy": "selected"}),
    ("domains", {"tax.policy": "selected", "tax.law": "not_selected", "extra": "selected"}),
    ("domains", {"tax.policy": "selected", "tax.law": None}),
    ("domains", {"tax.policy": True, "tax.law": "not_selected"}),
    ("domains", {"tax.policy": "税务政策", "tax.law": "not_selected"}),
    ("missing_conditions", None), ("missing_conditions", "period"),
    ("missing_conditions", ["period", "period"]), ("missing_conditions", [None]),
    ("missing_conditions", ["applicable_period"]), ("missing_conditions", ["subject"] * 5),
])
def test_wrong_types_unknown_values_and_old_missing_enum_fail_closed(field, value):
    item = wire(outcome="clarification_required", mode="applicability", selected=(), missing=("period",))
    item[field] = value
    with pytest.raises(InvalidModelOutput):
        definition().parse_response(response(item))


@pytest.mark.parametrize("field", ["outcome", "query_mode", "domains", "missing_conditions"])
def test_missing_top_level_fields_rejected(field):
    item = wire()
    del item[field]
    with pytest.raises(InvalidModelOutput):
        definition().parse_response(response(item))


@pytest.mark.parametrize("field", ["question", "queries", "requirements", "focus", "schema_version", "url"])
def test_extra_fields_cannot_replace_q_or_smuggle_legacy_plan(field):
    item = wire()
    item[field] = "untrusted-extra"
    with pytest.raises(InvalidModelOutput):
        definition().parse_response(response(item))


@pytest.mark.parametrize("raw", ["{} {}", "not-json", "null", "[]", '{"outcome":NaN}',
    '{"outcome":Infinity}', '{"outcome":"search","outcome":"unsupported"}',
    json.dumps(wire()).replace('"tax.policy":', '"tax.policy":"not_selected","tax.policy":', 1),
    "[" * 2000 + "0" + "]" * 2000])
def test_duplicate_keys_nonfinite_invalid_json_and_recursion_rejected(raw):
    with pytest.raises(InvalidModelOutput, match="knowledge.invalid_query_intent"):
        definition().parse_response(response(raw=raw))


@pytest.mark.parametrize("fault", ["second_call", "wrong_name", "text", "whitespace", "json_only"])
def test_output_envelope_is_not_repaired(fault):
    item = response(wire())
    if fault == "second_call":
        item = replace(item, tool_calls=item.tool_calls * 2)
    elif fault == "wrong_name":
        item = replace(item, tool_calls=(replace(item.tool_calls[0], name="knowledge_requirement_plan"),))
    elif fault in {"text", "whitespace"}:
        item = replace(item, content="answer" if fault == "text" else " ")
    else:
        item = replace(item, finish_kind=StructuredFinishKind.STOP, tool_calls=(), content=json.dumps(wire()))
    with pytest.raises(InvalidModelOutput):
        definition().parse_response(item)


def test_wire_order_is_irrelevant_but_selected_tuple_uses_catalog_order():
    item = wire(selected=DOMAINS)
    item["domains"] = dict(reversed(tuple(item["domains"].items())))
    assert definition().parse_response(replace(response(item), content="")).selected_domain_ids == DOMAINS


def test_concurrent_single_domain_definitions_do_not_share_mutable_state():
    tasks = {domain: definition((domain,)) for domain in DOMAINS}

    def check(index):
        domain = DOMAINS[index % 2]
        item = wire(domains=(domain,), selected=(domain,))
        actual = tasks[domain].parse_response(response(item))
        assert actual.selected_domain_ids == (domain,)
        with pytest.raises(InvalidModelOutput):
            tasks[domain].parse_response(response(wire(selected=DOMAINS)))

    with ThreadPoolExecutor(max_workers=4) as pool:
        tuple(pool.map(check, range(32)))
