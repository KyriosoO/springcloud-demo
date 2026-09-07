from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json

import pytest

from agent_runtime.knowledge.contracts import KnowledgeQuestionKind, KnowledgeRequirementKind
from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput
from agent_runtime.knowledge.rewrite_v6 import KnowledgeRewriteTaskV6
from agent_runtime.knowledge.rewrite_v7 import INSTRUCTION, KnowledgeRequirementPlanOutput, KnowledgeRewriteTaskV7
from agent_runtime.model.contracts import InvalidModelOutput, StructuredFinishKind
from tests.contract.knowledge.test_rewrite_task_v2 import _response


def wire_plan(*, applicability=False, second_domain=False):
    query = "一般纳税人一般计税2026年运输服务税率"
    value = {
        "outcome": "search", "question_kind": "applicability" if applicability else "lookup",
        "queries": [{"domain_id": "tax.policy", "query": query}],
        "requirements": [{"requirement_id": "r1", "domain_id": "tax.policy", "kind": "subject_scope", "focus": "运输服务税务分类依据"}],
        "missing_conditions": [],
    }
    if applicability:
        for kind, focus in (("rule", "运输服务税率依据"), ("temporal_scope", "2026年运输服务税务规则施行依据")):
            value["requirements"].append({"requirement_id": f"r{len(value['requirements']) + 1}", "domain_id": "tax.policy", "kind": kind, "focus": focus})
    if second_domain:
        value["queries"].append({"domain_id": "tax.law", "query": query})
        value["requirements"][-1]["domain_id"] = "tax.law"
    return value


def parse(value):
    return KnowledgeRewriteTaskV7.definition().parse_response(_response(json.dumps(value, ensure_ascii=False)))


def test_v7_input_catalog_and_old_task_unchanged_with_explicit_budget_increase():
    old, new = KnowledgeRewriteTaskV6.definition(), KnowledgeRewriteTaskV7.definition()
    value = KnowledgeSemanticPlanInput(minimized_question="税务政策定义", enabled_domain_ids=("tax.policy", "tax.law"))
    before, after = old.build_request(value), new.build_request(value)
    assert after.user_payload_json == before.user_payload_json
    assert replace(after, task_version="6", system_instruction=before.system_instruction, max_output_tokens=512) == before
    assert new.input_type is old.input_type
    assert new.parse_response is not old.parse_response
    assert (new.task_version, new.max_input_bytes, new.timeout_ms, new.max_output_tokens) == ("7", 16384, 8000, 1536)
    assert 0 < len(INSTRUCTION.encode()) <= 8192
    for term in ("酒店", "住宿", "UAT-KB", "gold", "chunk-", "2026"):
        assert term not in INSTRUCTION
    for term in ("temporal_scope", "subject_scope", "constraint", "lookup", "applicability", "不能新增", "不广播全部域"):
        assert term in INSTRUCTION


@pytest.mark.parametrize("applicability,second_domain", [(False, False), (True, False), (True, True)])
def test_search_exact_typed_immutable_output(applicability, second_domain):
    output = parse(wire_plan(applicability=applicability, second_domain=second_domain))
    assert type(output) is KnowledgeRequirementPlanOutput
    assert output.question_kind is (KnowledgeQuestionKind.APPLICABILITY if applicability else KnowledgeQuestionKind.LOOKUP)
    assert output.evidence_requirements[0].kind is KnowledgeRequirementKind.SUBJECT_SCOPE
    assert type(output.evidence_requirements) is tuple
    with pytest.raises(FrozenInstanceError):
        output.evidence_requirements[0].focus = "changed"


@pytest.mark.parametrize("outcome,missing", [("unsupported", []), ("clarification_required", ["taxpayer_type"])])
def test_nonsearch_none_is_not_null(outcome, missing):
    output = parse({"outcome": outcome, "question_kind": "none", "queries": [], "requirements": [], "missing_conditions": missing})
    assert output.question_kind is None and output.evidence_requirements == () and output.queries == ()


def invalid_values():
    valid = wire_plan(applicability=True)
    values = [None, [], {}, {key: item for key, item in valid.items() if key != "requirements"}]
    for key, invalid in (
        ("outcome", None), ("outcome", "invented"), ("question_kind", None), ("question_kind", True),
        ("question_kind", "none"), ("question_kind", "invented"), ("queries", []),
        ("queries", valid["queries"] * 2), ("requirements", []), ("requirements", valid["requirements"] * 2),
        ("requirements", valid["requirements"][:2]), ("missing_conditions", ["subject"]), ("missing_conditions", None),
    ):
        values.append({**valid, key: invalid})
    for key, invalid in (
        ("requirement_id", "r2"), ("requirement_id", 1), ("domain_id", "tax.law"),
        ("domain_id", []), ("kind", "invented"), ("kind", True), ("kind", "rule"),
        ("focus", ""), ("focus", "税" * 193), ("focus", "税务\n依据"), ("focus", "税务\u200b依据"),
        ("focus", "税务e\u0301"), ("focus", "税务\ud800"), ("focus", ["税务依据"]),
    ):
        changed = deepcopy(valid)
        changed["requirements"][0][key] = invalid
        values.append(changed)
    for key, invalid in (("domain_id", "unknown"), ("query", True), ("query", "税" * 1025), ("query", "税务\n依据")):
        changed = deepcopy(valid)
        changed["queries"][0][key] = invalid
        values.append(changed)
    for container in ("queries", "requirements"):
        changed = deepcopy(valid)
        changed[container][0]["extra"] = "untrusted"
        values.append(changed)
    values.append({**valid, "extra": True})
    # A selected domain without a requirement is invalid, not optional coverage.
    values.append({**valid, "queries": valid["queries"] + [{"domain_id": "tax.law", "query": "税务法律"}]})
    for outcome in ("unsupported", "clarification_required"):
        base = {"outcome": outcome, "question_kind": "none", "queries": [], "requirements": [], "missing_conditions": [] if outcome == "unsupported" else ["subject"]}
        for key, invalid in (("question_kind", "lookup"), ("queries", valid["queries"]), ("requirements", valid["requirements"]),
                             ("missing_conditions", ["unknown"]), ("missing_conditions", ["subject", "subject"]),
                             ("missing_conditions", ["subject", "taxpayer_type", "calculation_method", "applicable_period"])):
            values.append({**base, key: invalid})
    values.append({"outcome": "clarification_required", "question_kind": "none", "queries": [], "requirements": [], "missing_conditions": []})
    return values


@pytest.mark.parametrize("value", invalid_values())
def test_invalid_shapes_fail_closed(value):
    # ensure_ascii also exercises escaped unpaired surrogates in the decoder.
    with pytest.raises(InvalidModelOutput):
        KnowledgeRewriteTaskV7.definition().parse_response(_response(json.dumps(value)))


@pytest.mark.parametrize("raw", [
    "{} {}", "not json", '{"outcome":"unsupported","outcome":"search"}',
    '{"outcome":NaN}', '{"outcome":Infinity}',
    json.dumps(wire_plan()).replace('"focus":', '"focus":"税务政策","focus":'),
    json.dumps(wire_plan()).replace('"domain_id":', '"domain_id":"tax.policy","domain_id":', 1),
])
def test_duplicate_keys_constants_and_trailing_content_fail(raw):
    with pytest.raises(InvalidModelOutput):
        KnowledgeRewriteTaskV7.definition().parse_response(_response(raw))


@pytest.mark.parametrize("finish", [kind for kind in StructuredFinishKind if kind is not StructuredFinishKind.STOP])
def test_truncated_or_tool_finish_is_not_partial_plan(finish):
    with pytest.raises(InvalidModelOutput):
        KnowledgeRewriteTaskV7.definition().parse_response(replace(_response(json.dumps(wire_plan())), finish_kind=finish))


def test_old_decoder_does_not_accept_new_contract():
    with pytest.raises(InvalidModelOutput):
        KnowledgeRewriteTaskV6.definition().parse_response(_response(json.dumps(wire_plan())))
