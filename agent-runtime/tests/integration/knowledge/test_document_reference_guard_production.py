"""Current root with fake transports, not a real model or retrieval quality test."""
import asyncio
from copy import deepcopy
from dataclasses import asdict
import json

import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.knowledge.document_reference_semantics import DocumentReferenceSemanticGuard
from agent_runtime.main import build_runtime
from agent_runtime.model.contracts import ModelTaskId
from agent_runtime.observation import observation_scope
from tests.helpers import scope
from tests.integration.knowledge import test_requirement_runtime_composition as harness
from tests.integration.knowledge.test_production_runtime_wiring import _enabled_environment


FOCUS = "财税〔2011〕100号的软件产品定义"
QUESTION = "请分别查找" + FOCUS


def output(query=FOCUS, focus=FOCUS):
    value = harness.plan(applicability=False, question=query)
    value["requirements"][0]["focus"] = focus
    return value


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["请分别查找", "帮我查询", "请同时检索", "请查阅", "请查看", "对比"])
async def test_current_root_accepts_reference_query_and_focus_without_rewriting_input(prefix, monkeypatch, caplog):
    monkeypatch.setattr(harness, "FOCUSES", (FOCUS,) + harness.FOCUSES[1:])
    seen = []
    extract = DocumentReferenceSemanticGuard.extract

    def observe(self, question):
        seen.append((self, question))
        return extract(self, question)

    monkeypatch.setattr(DocumentReferenceSemanticGuard, "extract", observe)
    question = prefix + FOCUS
    result, model, clients, observation = await harness.invoke(output(), question=question, monkeypatch=monkeypatch)
    assert result.status is CapabilityStatus.SUCCESS, result.failure
    assert result.capability_id == "knowledge.query"
    assert len({id(guard) for guard, _ in seen}) == 1
    assert all(type(guard) is DocumentReferenceSemanticGuard for guard, _ in seen)
    assert [(request.task_id, request.task_version) for request in model.requests] == [
        (ModelTaskId.ACTION_SELECTION, "action-selection-v4"),
        (ModelTaskId.KNOWLEDGE_REWRITE, "10"), (ModelTaskId.KNOWLEDGE_SUMMARY, "7"),
    ]
    for request in model.requests[1:]:
        assert json.loads(request.user_payload_json)["question"] == question
    assert clients.paths.count("/es/knowledge/search") == 2
    assert clients.paths.count("/embed") == 1 and clients.paths.count("/rerank") == 1
    assert [body["queryText"] for path, body in clients.payloads
            if path == "/es/knowledge/search" and body["path"] == "keyword"] == [question]
    assert [body["texts"] for path, body in clients.payloads if path == "/embed"] == [[FOCUS]]
    assert len(observation.plans) == 1
    assert [item["query_text"] for item in observation.plans[0]["plan"]["items"]] == [question, FOCUS]
    assert "original_keyword_query" not in observation.plans[0]["plan"]
    visible = json.dumps(asdict(observation), ensure_ascii=False) + caplog.text
    assert "header.payload.signature" not in visible
    assert all(text not in visible for text in harness.CONTENTS)
    assert all("header.payload.signature" not in request.user_payload_json for request in model.requests)


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["query", "focus"])
@pytest.mark.parametrize("bad", [
    FOCUS.replace("财税", "苏财税"), FOCUS.replace("2011", "2012"), FOCUS.replace("100", "101"),
    FOCUS.replace("财税", "国税函"), FOCUS.replace("〔2011〕", "[2011]"),
    FOCUS + "，财税〔2011〕100号", FOCUS + "，6%", FOCUS + "，不得适用",
])
async def test_invalid_query_or_focus_rejects_whole_plan_before_downstream(field, bad, monkeypatch):
    result, model, clients, observation = await harness.invoke(output(**{field: bad}), question=QUESTION, monkeypatch=monkeypatch)
    assert result.status is CapabilityStatus.DOWNSTREAM_FAILURE
    assert result.failure.code == "knowledge.rewrite_failure"
    assert [request.task_id for request in model.requests] == [ModelTaskId.ACTION_SELECTION, ModelTaskId.KNOWLEDGE_REWRITE]
    assert clients.payloads == [] and observation.downstream_calls == () and observation.plans == ()


@pytest.mark.asyncio
async def test_invalid_second_domain_rejects_valid_first_domain_too(monkeypatch):
    value = output(query=QUESTION)
    value["queries"].append({"domain_id": "tax.law", "query": QUESTION.replace("财税", "国税函")})
    requirement = deepcopy(value["requirements"][0])
    requirement.update(requirement_id="r2", domain_id="tax.law")
    value["requirements"].append(requirement)
    result, model, clients, observation = await harness.invoke(value, question=QUESTION, monkeypatch=monkeypatch)
    assert result.status is CapabilityStatus.DOWNSTREAM_FAILURE
    assert result.failure.code == "knowledge.rewrite_failure"
    assert len(model.requests) == 2 and clients.paths == [] and observation.plans == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("global_condition", ["", "2026年，"], ids=["local-only", "shared-year"])
@pytest.mark.parametrize("mutation", [None, "missing_condition", "other_domain", "new_focus_condition"])
async def test_original_multi_domain_question_allows_local_focus_without_invented_reference(monkeypatch, global_condition, mutation):
    policy_focus = global_condition + FOCUS
    law_focus = global_condition + "增值税法第十条的销售服务税率规定"
    monkeypatch.setattr(harness, "FOCUSES", (policy_focus, law_focus, harness.FOCUSES[2]))
    question = global_condition + "请分别查找财税〔2011〕100号的软件产品定义，以及增值税法第十条的销售服务税率规定。"
    value = output(query=policy_focus, focus=policy_focus)
    value["queries"].append({"domain_id": "tax.law", "query": law_focus})
    value["requirements"].append({"requirement_id": "r2", "domain_id": "tax.law", "kind": "rule", "focus": law_focus})
    if mutation == "missing_condition":
        value["queries"][1]["query"] = law_focus.replace(global_condition or "第十条", "")
    elif mutation == "other_domain":
        value["queries"][1]["query"] += FOCUS
    elif mutation == "new_focus_condition":
        value["requirements"][1]["focus"] += "2027年"
    result, model, clients, observation = await harness.invoke(value, question=question, multi=True, monkeypatch=monkeypatch)
    if mutation is not None:
        assert result.status is CapabilityStatus.DOWNSTREAM_FAILURE
        assert result.failure.code == "knowledge.rewrite_failure"
        assert len(model.requests) == 2
        assert clients.paths == [] and observation.plans == () and observation.downstream_calls == ()
        return
    assert result.status is CapabilityStatus.SUCCESS, result.failure
    assert len(model.requests) == 3 and clients.paths.count("/es/knowledge/search") == 4
    assert clients.paths.count("/embed") == 2 and clients.paths.count("/rerank") == 2
    assert [(body["logicalDomainId"], body["queryText"]) for path, body in clients.payloads
            if path == "/es/knowledge/search" and body["path"] == "keyword"] == [
        ("tax.policy", question), ("tax.law", question),
    ]
    assert [body["texts"] for path, body in clients.payloads if path == "/embed"] == [[policy_focus], [law_focus]]
    assert observation.plans[0]["plan"]["selected_domain_ids"] == ["tax.policy", "tax.law"]
    assert [point["quote"] for point in result.user_result["points"]] == list(harness.CONTENTS[:2])
    # Synthetic evidence proves wiring and guards, not actual legal correctness.
    assert json.loads(model.requests[-1].user_payload_json)["question"] == question


@pytest.mark.asyncio
async def test_same_runtime_does_not_share_reference_constraints_between_requests(monkeypatch):
    monkeypatch.setattr(harness, "FOCUSES", (FOCUS,) + harness.FOCUSES[1:])
    model, clients = harness.Model(output()), harness.Clients()
    runtime = build_runtime(_enabled_environment(), model_transport=model, knowledge_http_client_factory=clients)

    async def one(question):
        with observation_scope() as collector:
            result = await runtime.ainvoke(question=question, scope=scope(question))
            return result, collector.snapshot()

    try:
        good, bad = await asyncio.gather(one(QUESTION), one(QUESTION.replace("2011", "2012")))
    finally:
        await runtime.aclose()
        await runtime.aclose()
    assert good[0].status is CapabilityStatus.SUCCESS
    assert bad[0].status is CapabilityStatus.DOWNSTREAM_FAILURE
    assert bad[0].failure.code == "knowledge.rewrite_failure"
    assert len(good[1].downstream_calls) == 4 and bad[1].downstream_calls == ()
    assert clients.paths.count("/es/knowledge/search") == 2 and len(model.requests) == 5
    assert all(client.is_closed for client in clients.clients)


@pytest.mark.asyncio
async def test_disabled_root_does_not_instantiate_reference_guard(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("disabled Knowledge must not construct dependencies")

    monkeypatch.setattr(DocumentReferenceSemanticGuard, "__init__", forbidden)
    model = harness.Model(output())
    runtime = build_runtime({**_enabled_environment(), "AGENT_KNOWLEDGE_ENABLED": "false"},
                            model_transport=model, knowledge_http_client_factory=forbidden)
    await runtime.aclose()
    assert model.requests == []
