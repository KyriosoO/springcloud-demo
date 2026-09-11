"""Current production admission and explicit legacy compatibility; no live calls."""
import json

import pytest

from agent_runtime.bootstrap import KnowledgeCompositionRoot
from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.knowledge.evidence.admission import ScoreAwareEvidenceSelector
from agent_runtime.knowledge.settings import KnowledgeSettings
from agent_runtime.model.contracts import ModelTaskId
from tests.integration.knowledge.test_production_runtime_wiring import _enabled_environment
from tests.integration.knowledge.test_requirement_runtime_composition import CONTENTS, invoke, plan


@pytest.fixture
def production_admission(monkeypatch):
    original = KnowledgeCompositionRoot.build_provider
    calls = []
    original_select = ScoreAwareEvidenceSelector.select

    def select(self, **kwargs):
        calls.append(kwargs["candidates"])
        return original_select(self, **kwargs)

    def build(**kwargs):
        assert kwargs["evidence_selection_version"] == ScoreAwareEvidenceSelector.VERSION
        return original(**kwargs)

    monkeypatch.setattr(ScoreAwareEvidenceSelector, "select", select)
    monkeypatch.setattr(KnowledgeCompositionRoot, "build_provider", staticmethod(build))
    return calls


@pytest.mark.asyncio
@pytest.mark.parametrize("multi", [False, True])
async def test_current_root_single_capability_and_lifecycle(multi, production_admission, monkeypatch):
    result, model, clients, _ = await invoke(multi=multi, monkeypatch=monkeypatch)
    assert result.status is CapabilityStatus.SUCCESS
    assert len(production_admission) == 1 and len(production_admission[0]) == 3
    assert all(item.coverage_anchor for item in production_admission[0])
    assert len(model.requests) == 3 and model.requests[-1].task_version == "7"
    assert clients.paths.count("/es/knowledge/search") == (4 if multi else 2)
    assert clients.paths.count("/rerank") == 3 and all(c.is_closed for c in clients.clients)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,expected", [
    ("denied", CapabilityStatus.FORBIDDEN), ("all_failed", CapabilityStatus.DOWNSTREAM_FAILURE),
    ("policy", CapabilityStatus.MODEL_EGRESS_DENIED), ("empty", CapabilityStatus.NO_RESULT),
])
async def test_admission_does_not_bypass_domain_or_egress_failure(fault, expected, production_admission, monkeypatch):
    result, model, clients, _ = await invoke(client_fault=fault, monkeypatch=monkeypatch)
    assert result.status is expected
    assert not any(r.task_id is ModelTaskId.KNOWLEDGE_SUMMARY for r in model.requests)
    assert len(production_admission) == (1 if fault == "policy" else 0)
    assert clients.paths.count("/es/knowledge/search") == 2


@pytest.mark.parametrize("version", ["unknown", "", None, True, 1])
def test_unknown_version_rejected_before_handler_or_model_use(version):
    with pytest.raises(ValueError, match="^knowledge.evidence_selection_version_invalid$"):
        KnowledgeCompositionRoot.build_provider(settings=KnowledgeSettings.from_env(_enabled_environment()),
            model=None, tasks=KnowledgeCompositionRoot.task_definitions(enabled=True, enabled_domain_ids=("tax.policy",)), retrieval=object(),
            evidence_selection_version=version)


@pytest.mark.asyncio
async def test_current_default_filters_optional_tail_without_extra_calls(production_admission, monkeypatch):
    result, model, clients, _ = await invoke(plan(applicability=False), monkeypatch=monkeypatch)
    assert result.status is CapabilityStatus.SUCCESS
    verified = production_admission[0]
    assert len(verified) == 3 and sum(c.coverage_anchor for c in verified) == 1
    assert [c.rerank_score for c in verified] == [1.0, 0.0, 0.0]
    payload = json.loads(model.requests[-1].user_payload_json)
    assert [item["content"] for item in payload["evidence"]] == [CONTENTS[0]]
    assert [point["quote"] for point in result.user_result["points"]] == [CONTENTS[0]]
    assert len(model.requests) == 3
    assert clients.paths.count("/es/knowledge/search") == 2
    assert clients.paths.count("/embed") == clients.paths.count("/rerank") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("omit_version", [False, True])
async def test_internal_legacy_default_and_explicit_rollback_preserve_original_selection(omit_version, monkeypatch):
    original = KnowledgeCompositionRoot.build_provider

    def build(**kwargs):
        assert kwargs.pop("evidence_selection_version") == ScoreAwareEvidenceSelector.VERSION
        if not omit_version:
            kwargs["evidence_selection_version"] = "legacy"
        return original(**kwargs)

    def forbidden(*args, **kwargs): raise AssertionError("Legacy must not allocate the new selector")
    monkeypatch.setattr(KnowledgeCompositionRoot, "build_provider", staticmethod(build))
    monkeypatch.setattr(ScoreAwareEvidenceSelector, "__init__", forbidden)
    result, model, clients, _ = await invoke(plan(applicability=False), monkeypatch=monkeypatch)
    assert result.status is CapabilityStatus.SUCCESS
    assert [e["content"] for e in json.loads(model.requests[-1].user_payload_json)["evidence"]] == list(CONTENTS)
    assert len(model.requests) == 3 and clients.paths.count("/es/knowledge/search") == 2


def test_disabled_root_does_not_instantiate_candidate_or_require_its_config(monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError("Disabled must not allocate selector")
    monkeypatch.setattr(ScoreAwareEvidenceSelector, "__init__", forbidden)
    KnowledgeCompositionRoot.build_provider(settings=KnowledgeSettings.from_env({"AGENT_KNOWLEDGE_ENABLED": "false"}),
        model=None, tasks=None, retrieval=None, evidence_selection_version="ignored-while-disabled")


def test_historical_bridge_is_not_a_second_current_production_binding():
    from agent_runtime import main
    from tests.integration.knowledge.conftest import legacy_root

    historical = legacy_root()
    assert main.KnowledgeCompositionRoot is KnowledgeCompositionRoot
    assert historical is not KnowledgeCompositionRoot
    assert historical.task_definitions(enabled=True).summary.task_version == "5"
    assert KnowledgeCompositionRoot.task_definitions(enabled=True, enabled_domain_ids=("tax.policy",)).summary.task_version == "7"
    with pytest.raises(ValueError, match="^knowledge.historical_selection_version_invalid$"):
        historical.build_provider(evidence_selection_version="unapproved")
