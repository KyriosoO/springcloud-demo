"""Fixed slots change representation, not semantic admission or service contracts."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import subprocess

import pytest

from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput
from agent_runtime.knowledge.rewrite_v9 import KnowledgeRewriteTaskV9
from agent_runtime.knowledge.rewrite_v10 import KnowledgeRewriteTaskV10
from agent_runtime.knowledge.rewrite_v11 import KnowledgeRewriteTaskV11, OUTPUT_NAME
from agent_runtime.model.contracts import (
    InvalidModelOutput, StructuredFinishKind, StructuredModelResponse, StructuredToolCall,
    StructuredToolMode, StructuredOutputMode,
)
from agent_runtime.model.deepseek.dto import project_deepseek_request
from tests.contract.knowledge.test_rewrite_task_v2 import _response
from tests.contract.knowledge.test_rewrite_task_v7 import invalid_values, wire_plan

DOMAINS = ("tax.policy", "tax.law")


def definition(domains=DOMAINS):
    return KnowledgeRewriteTaskV11.definition(enabled_domain_ids=domains)


def response(value=None, *, raw=None):
    return StructuredModelResponse(
        finish_kind=StructuredFinishKind.TOOL_CALLS, content=None,
        tool_calls=(StructuredToolCall(name=OUTPUT_NAME, arguments_json=json.dumps(value) if raw is None else raw),),
        usage_total_tokens=0,
    )


def slotted(value, domains=DOMAINS):
    """Fixture representation only; never erase an invalid/duplicate array item."""
    result = deepcopy(value)
    if not isinstance(result, dict) or not isinstance(result.get("queries"), list):
        return result
    slots = dict.fromkeys(domains, "")
    seen = set()
    for item in result["queries"]:
        if (not isinstance(item, dict) or set(item) != {"domain_id", "query"}
                or not isinstance(item["domain_id"], str) or item["domain_id"] not in domains
                or item["domain_id"] in seen):
            return result
        seen.add(item["domain_id"])
        slots[item["domain_id"]] = item["query"]
    result["queries"] = slots
    return result


@pytest.mark.parametrize("domains", [DOMAINS, ("tax.policy",), ("tax.law",)])
def test_schema_input_and_examples_use_the_same_exact_enabled_snapshot(domains):
    task = definition(domains)
    value = KnowledgeSemanticPlanInput(minimized_question="税务规则查询", enabled_domain_ids=domains)
    request = task.build_request(value)
    old = KnowledgeRewriteTaskV10.definition().build_request(value)
    assert (task.task_version, task.max_input_bytes, task.timeout_ms, task.max_output_tokens) == ("11", 16384, 8000, 1536)
    assert request.user_payload_json == old.user_payload_json
    assert request.tool_mode is StructuredToolMode.SCHEMA_ONLY
    assert request.output_mode is StructuredOutputMode.TOOL_CALLS
    assert request.max_output_tokens == 1536 and len(request.tools) == 1
    assert len(request.system_instruction.encode()) <= 8192
    schema = request.tools[0].arguments_schema
    assert schema["required"] == old.tools[0].arguments_schema["required"]
    assert schema["additionalProperties"] is False
    slots = schema["properties"]["queries"]
    assert slots["type"] == "object" and slots["required"] == domains
    assert slots["additionalProperties"] is False
    assert slots["properties"] == {domain: {"type": "string"} for domain in domains}
    for key in ("outcome", "question_kind", "requirements", "missing_conditions"):
        assert schema["properties"][key] == old.tools[0].arguments_schema["properties"][key]
    assert schema["properties"]["requirements"]["items"]["properties"]["domain_id"]["enum"] == domains
    assert tuple(item["domain_id"] for item in json.loads(request.user_payload_json)["domains"]) == domains
    instruction = request.system_instruction
    assert '"queries":[' not in instruction and "queries含1至2个唯一启用域" not in instruction
    assert "每个非空槽位至少一项需求" in instruction and "未分配给任何focus" in instruction
    for fragment in ("不能为凑齐角色强制双域", "不猜测、不补条件", "普通查阅不机械要求纳税人类型", "不执行函数"):
        assert fragment in instruction
    for label in ("检索结构：", "澄清结构：", "不支持结构："):
        text = instruction.split(label, 1)[1].split("。", 1)[0]
        example = json.loads(text)
        assert set(example["queries"]) == set(domains)
        task.parse_response(response(example))
    projected = project_deepseek_request(request).payload
    assert projected["model"] == "deepseek-flash" and projected["tools"][0]["function"]["strict"] is True
    assert projected["thinking"] == {"type": "disabled"} and projected["stream"] is False


@pytest.mark.parametrize("domains", [None, [], (), ["tax.policy"], (True,), ("employee",),
    ("tax.policy", "tax.policy"), ("tax.law", "tax.policy"), ("tax.policy", "tax.law", "extra")])
def test_factory_rejects_missing_unknown_repeated_or_noncanonical_domains(domains):
    with pytest.raises(ValueError, match="knowledge.enabled_domains_invalid"):
        definition(domains)


@pytest.mark.parametrize("domains", [("tax.law",), DOMAINS, [], ["tax.policy"], ()])
def test_input_snapshot_mismatch_fails_before_a_model_request(domains):
    with pytest.raises(ValueError, match="knowledge.enabled_domains_mismatch"):
        definition(("tax.policy",)).build_request(KnowledgeSemanticPlanInput(
            minimized_question="税务政策", enabled_domain_ids=domains))


@pytest.mark.parametrize("value", [wire_plan(), wire_plan(applicability=True),
    wire_plan(applicability=True, second_domain=True),
    dict(outcome="clarification_required", question_kind="none", queries=[], requirements=[], missing_conditions=["taxpayer_type"]),
    dict(outcome="unsupported", question_kind="none", queries=[], requirements=[], missing_conditions=[])])
def test_valid_original_semantics_equal_without_repair(value):
    old = KnowledgeRewriteTaskV9.definition().parse_response(_response(json.dumps(value)))
    actual = definition().parse_response(response(slotted(value)))
    ordered = tuple(query for domain in DOMAINS for query in old.queries if query.domain_id == domain)
    assert actual == replace(old, queries=ordered)
    assert actual.evidence_requirements == old.evidence_requirements


def test_multiple_requirements_share_one_domain_and_mapping_uses_catalog_order():
    value = wire_plan(applicability=True, second_domain=True)
    value["queries"].reverse()
    slots = slotted(value)
    slots["queries"] = dict(reversed(tuple(slots["queries"].items())))
    actual = definition().parse_response(response(slots))
    old = KnowledgeRewriteTaskV9.definition().parse_response(_response(json.dumps(value)))
    assert tuple(query.domain_id for query in actual.queries) == DOMAINS
    assert actual.queries == tuple(reversed(old.queries))
    assert actual.evidence_requirements == old.evidence_requirements


@pytest.mark.parametrize("value", invalid_values())
def test_original_illegal_semantics_or_unrepresentable_old_shape_still_rejected(value):
    with pytest.raises(InvalidModelOutput):
        KnowledgeRewriteTaskV9.definition().parse_response(_response(json.dumps(value)))
    with pytest.raises(InvalidModelOutput, match="knowledge.invalid_requirement_plan"):
        definition().parse_response(response(slotted(value)))


@pytest.mark.parametrize("slots", [None, [], {}, {"tax.policy": "税务政策"},
    {"tax.policy": "税务政策", "tax.law": "", "extra": ""},
    {"tax.policy": "税务政策", "employee": ""},
    {"tax.policy": " ", "tax.law": ""}, {"tax.policy": "", "tax.law": ""},
    {"tax.policy": True, "tax.law": ""}, {"tax.policy": None, "tax.law": ""},
    {"tax.policy": ["税务政策"], "tax.law": ""},
    {"tax.policy": "", "tax.law": "税务法律"},
    {"tax.policy": "税" * 1025, "tax.law": ""}, {"tax.policy": "税务e\u0301", "tax.law": ""},
    {"tax.policy": "税务\u200b", "tax.law": ""}, {"tax.policy": "税务\ud800", "tax.law": ""}])
def test_direct_new_wire_rejects_unknown_missing_empty_or_illegal_slots(slots):
    value = slotted(wire_plan())
    value["queries"] = slots
    with pytest.raises(InvalidModelOutput, match="knowledge.invalid_requirement_plan"):
        definition().parse_response(response(value))


@pytest.mark.parametrize("raw", ["{} {}", "not-json", '{"outcome":NaN}', '{"outcome":Infinity}',
    '{"outcome":"unsupported","outcome":"search"}',
    json.dumps(slotted(wire_plan())).replace('"tax.policy":', '"tax.policy":"税务政策","tax.policy":', 1),
    json.dumps(slotted(wire_plan())).replace('"focus":', '"focus":"税务政策","focus":', 1),
    '[' * 2000 + '0' + ']' * 2000])
def test_raw_duplicates_invalid_json_nonfinite_and_depth_fail_closed(raw):
    with pytest.raises(InvalidModelOutput, match="knowledge.invalid_requirement_plan"):
        definition().parse_response(response(raw=raw))


@pytest.mark.parametrize("kind", [kind for kind in StructuredFinishKind if kind is not StructuredFinishKind.TOOL_CALLS])
def test_framing_finish_cannot_be_repaired(kind):
    item = response(slotted(wire_plan()))
    calls = () if kind is StructuredFinishKind.STOP else item.tool_calls
    with pytest.raises(InvalidModelOutput):
        definition().parse_response(replace(item, finish_kind=kind, tool_calls=calls))


@pytest.mark.parametrize("fault", ["second", "wrong_name", "content", "whitespace", "old_array", "disabled_domain"])
def test_framing_and_version_boundary_is_strict(fault):
    item = response(slotted(wire_plan()))
    if fault == "second": item = replace(item, tool_calls=item.tool_calls * 2)
    elif fault == "wrong_name": item = replace(item, tool_calls=(replace(item.tool_calls[0], name="execute_query"),))
    elif fault in {"content", "whitespace"}: item = replace(item, content="raw marker" if fault == "content" else " ")
    elif fault == "old_array": item = response(wire_plan())
    with pytest.raises(InvalidModelOutput):
        definition(("tax.policy",) if fault == "disabled_domain" else DOMAINS).parse_response(item)


def test_empty_content_allowed_but_new_wire_is_not_accepted_by_v10():
    item = replace(response(slotted(wire_plan())), content="")
    assert definition().parse_response(item).queries[0].domain_id == "tax.policy"
    with pytest.raises(InvalidModelOutput):
        KnowledgeRewriteTaskV10.definition().parse_response(item)


def test_definitions_are_isolated_across_concurrent_different_domain_snapshots():
    tasks = [definition((domain,)) for domain in DOMAINS]

    def check(index):
        domain = DOMAINS[index % 2]
        task = tasks[index % 2]
        value = wire_plan()
        value["queries"][0]["domain_id"] = domain
        value["requirements"][0]["domain_id"] = domain
        request = task.build_request(KnowledgeSemanticPlanInput(minimized_question="税务规则", enabled_domain_ids=(domain,)))
        actual = task.parse_response(response(slotted(value, (domain,))))
        assert tuple(request.tools[0].arguments_schema["properties"]["queries"]["properties"]) == (domain,)
        assert tuple(item.domain_id for item in actual.queries) == (domain,)

    with ThreadPoolExecutor(max_workers=4) as pool:
        tuple(pool.map(check, range(32)))


def test_historical_rewrite_source_bytes_are_not_changed():
    repo = Path(__file__).resolve().parents[4]
    baseline = "dbb5120608c06d7953ab4384dbcc6eac17dee827"
    for name in ("rewrite.py", *(f"rewrite_v{version}.py" for version in range(2, 11))):
        path = repo / "agent-runtime/src/agent_runtime/knowledge" / name
        frozen = subprocess.check_output(["git", "show", f"{baseline}:{path.relative_to(repo).as_posix()}"], cwd=repo)
        assert path.read_bytes() == frozen
