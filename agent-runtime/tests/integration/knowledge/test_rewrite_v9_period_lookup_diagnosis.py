"""TEST-KFLOW-016: synthetic diagnosis, never reconstruction of live model output."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.knowledge.contracts import KnowledgeQuestionKind, KnowledgeRequirementKind
from agent_runtime.knowledge.errors import KnowledgeInputError
from agent_runtime.knowledge.rewrite_v7 import KnowledgeRequirementPlanOutput
from agent_runtime.knowledge.rewrite_v9 import KnowledgeRewriteTaskV9
from agent_runtime.model.contracts import InvalidModelOutput, ModelTaskId
from tests.contract.knowledge.test_rewrite_task_v2 import _response
from tests.integration.knowledge.test_requirement_runtime_composition import invoke
from tests.system_e2e.knowledge_model_failure_probe_v1 import observe_failures, project_failure


QUESTION = "财政部税务总局公告2022年第13号和2023年第6号各自规定的执行期限是什么？"
FOCUSES = (
    "财政部税务总局公告2022年第13号规定的执行期限是什么？",
    "2023年第6号税务公告规定的执行期限是什么？",
)
PLAN_ERROR = "knowledge.invalid_requirement_plan"
REQUIREMENT_ERROR = "knowledge.invalid_evidence_requirements"
DIAGNOSTIC = {"phase": "rewrite_decoder", "code": PLAN_ERROR, "cause": "semantic_contract"}


def declared_plan():
    # Public question only: no dataset gold, expected dates or real response are used.
    return {
        "outcome": "search", "question_kind": "lookup",
        "queries": [{"domain_id": "tax.policy", "query": QUESTION}],
        "requirements": [
            {"requirement_id": f"r{i}", "domain_id": "tax.policy", "kind": "temporal_scope", "focus": focus}
            for i, focus in enumerate(FOCUSES, 1)
        ],
        "missing_conditions": [],
    }


INVALID_VALUES = [
    pytest.param(("queries",), [], PLAN_ERROR, id="no-query"),
    pytest.param(("queries", 0, "query"), "", PLAN_ERROR, id="empty-query"),
    pytest.param(("queries", 0, "query"), True, PLAN_ERROR, id="query-type"),
    pytest.param(("queries", 0, "query"), "e\u0301", PLAN_ERROR, id="query-non-nfc"),
    pytest.param(("queries", 0, "query"), QUESTION + "\n", PLAN_ERROR, id="query-control"),
    pytest.param(("queries", 0, "query"), "甲" * 1025, PLAN_ERROR, id="query-length"),
    pytest.param(("missing_conditions",), ["taxpayer_type"], PLAN_ERROR, id="search-with-missing"),
    pytest.param(("missing_conditions",), ["subject", "subject"], PLAN_ERROR, id="duplicate-missing"),
    pytest.param(("outcome",), "unsupported", PLAN_ERROR, id="terminal-with-plan"),
    pytest.param(("requirements",), [], REQUIREMENT_ERROR, id="no-requirement"),
    pytest.param(("requirements", 1, "requirement_id"), "r1", REQUIREMENT_ERROR, id="duplicate-id"),
    pytest.param(("requirements", 1, "domain_id"), "tax.law", REQUIREMENT_ERROR, id="unqueried-domain"),
    pytest.param(("requirements", 0, "focus"), "", REQUIREMENT_ERROR, id="empty-focus"),
    pytest.param(("requirements", 0, "focus"), True, REQUIREMENT_ERROR, id="focus-type"),
    pytest.param(("requirements", 0, "focus"), "甲" * 193, REQUIREMENT_ERROR, id="focus-length"),
    pytest.param(("requirements", 0, "focus"), "e\u0301", REQUIREMENT_ERROR, id="focus-non-nfc"),
    pytest.param(("question_kind",), "applicability", REQUIREMENT_ERROR, id="wrong-kind-roles"),
    pytest.param(("queries",), [{"domain_id": "tax.policy", "query": QUESTION}] * 2,
                 REQUIREMENT_ERROR, id="duplicate-domain"),
    pytest.param(("queries",), [{"domain_id": domain, "query": QUESTION} for domain in ("tax.policy", "tax.law")],
                 REQUIREMENT_ERROR, id="domain-without-requirement"),
]


def changed_plan(path, replacement):
    value = declared_plan()
    target = value
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = deepcopy(replacement)
    return value


def parse(value):
    return KnowledgeRewriteTaskV9.definition().parse_response(_response(json.dumps(value, ensure_ascii=False)))


def test_two_period_lookup_is_expressible_without_applicability_roles():
    output = parse(declared_plan())
    assert type(output) is KnowledgeRequirementPlanOutput
    assert output.question_kind is KnowledgeQuestionKind.LOOKUP
    assert [(q.domain_id, q.query) for q in output.queries] == [("tax.policy", QUESTION)]
    assert [(r.requirement_id, r.domain_id, r.kind, r.focus) for r in output.evidence_requirements] == [
        (f"r{i}", "tax.policy", KnowledgeRequirementKind.TEMPORAL_SCOPE, focus)
        for i, focus in enumerate(FOCUSES, 1)
    ]
    assert output.missing_conditions == ()


@pytest.mark.parametrize("path,replacement,inner_code", INVALID_VALUES)
def test_different_semantic_rejections_have_indistinguishable_finite_diagnostics(path, replacement, inner_code):
    with pytest.raises(InvalidModelOutput) as caught:
        parse(changed_plan(path, replacement))
    assert type(caught.value.__cause__) is KnowledgeInputError
    assert caught.value.__cause__.code == inner_code
    assert asdict(project_failure(caught.value)) == DIAGNOSTIC


@pytest.mark.asyncio
async def test_declared_lookup_reaches_current_root_retrieval_without_losing_question(monkeypatch, caplog):
    with observe_failures() as diagnostics:
        result, model, clients, observation = await invoke(
            declared_plan(), question=QUESTION, client_fault="empty", monkeypatch=monkeypatch,
        )
    # Empty fake index proves legal planning, not actual recall, dates or UAT success.
    assert result.status is CapabilityStatus.NO_RESULT
    assert diagnostics.records == ()
    assert [(r.task_id, r.task_version) for r in model.requests] == [
        (ModelTaskId.ACTION_SELECTION, "action-selection-v4"), (ModelTaskId.KNOWLEDGE_REWRITE, "10"),
    ]
    assert clients.paths.count("/es/knowledge/search") == 2
    assert clients.paths.count("/embed") == 1 and "/rerank" not in clients.paths
    search = [body for path, body in clients.payloads if path == "/es/knowledge/search"]
    assert {body["logicalDomainId"] for body in search} == {"tax.policy"}
    assert {body["path"] for body in search} == {"keyword", "vector"}
    assert next(body["queryText"] for body in search if body["path"] == "keyword") == QUESTION
    assert next(body["texts"] for path, body in clients.payloads if path == "/embed") == [QUESTION]
    assert len(observation.plans) == 1
    assert all(focus not in repr(observation) + caplog.text for focus in FOCUSES)


@pytest.mark.asyncio
@pytest.mark.parametrize("path,replacement,inner_code", INVALID_VALUES)
async def test_semantic_rejection_at_current_root_keeps_all_downstream_calls_zero(path, replacement, inner_code, monkeypatch, caplog):
    with observe_failures() as diagnostics:
        result, model, clients, observation = await invoke(
            changed_plan(path, replacement), question=QUESTION, monkeypatch=monkeypatch,
        )
    assert result.status is CapabilityStatus.DOWNSTREAM_FAILURE
    assert [(r.task_id, r.task_version) for r in model.requests] == [
        (ModelTaskId.ACTION_SELECTION, "action-selection-v4"), (ModelTaskId.KNOWLEDGE_REWRITE, "10"),
    ]
    assert [asdict(record) for record in diagnostics.records] == [DIAGNOSTIC]
    assert not diagnostics.overflowed
    assert clients.paths == [] and observation.plans == () and observation.downstream_calls == ()
    assert all(focus not in repr(observation) + caplog.text for focus in FOCUSES)


def test_historical_failure_remains_immutable_and_does_not_identify_one_rejection():
    archive = Path(__file__).resolve().parents[2] / "system_e2e/knowledge_representative_human_run_04/result.json"
    raw = archive.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "81f7d4151cbe1273a5ce1189267a77c94745184763ecfdb729023f2ef2822db4"
    case = next(case for case in json.loads(raw)["cases"] if case["caseId"] == "KRB-006")
    assert case["modelFailure"] == {"overflowed": False, "records": [DIAGNOSTIC]}
    assert case["automaticPassed"] is False and case["manualUsefulness"] == "not_assessed"
    assert case["calls"] == {"business": 0, "e2e": 1, "embedding": 0, "model": 2, "rerank": 0, "resume": 0, "retry": 0, "search": 0}
