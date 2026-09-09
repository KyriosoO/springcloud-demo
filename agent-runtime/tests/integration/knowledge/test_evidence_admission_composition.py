"""Explicit candidate injection, not a claim that main enables the candidate."""
import pytest

from agent_runtime.bootstrap import KnowledgeCompositionRoot
from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.knowledge.evidence.admission import ScoreAwareEvidenceSelector
from agent_runtime.knowledge.settings import KnowledgeSettings
from agent_runtime.model.contracts import ModelTaskId
from tests.integration.knowledge.test_production_runtime_wiring import _enabled_environment
from tests.integration.knowledge.test_requirement_runtime_composition import invoke


@pytest.fixture
def explicit_candidate(monkeypatch):
    original = KnowledgeCompositionRoot.build_provider
    calls = []
    original_select = ScoreAwareEvidenceSelector.select

    def select(self, **kwargs):
        calls.append(kwargs["candidates"])
        return original_select(self, **kwargs)

    def build(**kwargs):
        assert "evidence_selection_version" not in kwargs
        return original(**kwargs, evidence_selection_version=ScoreAwareEvidenceSelector.VERSION)

    monkeypatch.setattr(ScoreAwareEvidenceSelector, "select", select)
    monkeypatch.setattr(KnowledgeCompositionRoot, "build_provider", staticmethod(build))
    return calls


@pytest.mark.asyncio
@pytest.mark.parametrize("multi", [False, True])
async def test_explicit_candidate_current_root_single_capability_and_lifecycle(multi, explicit_candidate, monkeypatch):
    result, model, clients, _ = await invoke(multi=multi, monkeypatch=monkeypatch)
    assert result.status is CapabilityStatus.SUCCESS
    assert len(explicit_candidate) == 1 and len(explicit_candidate[0]) == 3
    assert all(item.coverage_anchor for item in explicit_candidate[0])
    assert len(model.requests) == 3 and model.requests[-1].task_version == "7"
    assert clients.paths.count("/es/knowledge/search") == (4 if multi else 2)
    assert clients.paths.count("/rerank") == 3 and all(c.is_closed for c in clients.clients)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,expected", [
    ("denied", CapabilityStatus.FORBIDDEN), ("all_failed", CapabilityStatus.DOWNSTREAM_FAILURE),
    ("policy", CapabilityStatus.MODEL_EGRESS_DENIED), ("empty", CapabilityStatus.NO_RESULT),
])
async def test_candidate_does_not_bypass_domain_or_egress_failure(fault, expected, explicit_candidate, monkeypatch):
    result, model, clients, _ = await invoke(client_fault=fault, monkeypatch=monkeypatch)
    assert result.status is expected
    assert not any(r.task_id is ModelTaskId.KNOWLEDGE_SUMMARY for r in model.requests)
    assert len(explicit_candidate) == (1 if fault == "policy" else 0)
    assert clients.paths.count("/es/knowledge/search") == 2


@pytest.mark.parametrize("version", ["unknown", "", None, True, 1])
def test_unknown_version_rejected_before_handler_or_model_use(version):
    with pytest.raises(ValueError, match="^knowledge.evidence_selection_version_invalid$"):
        KnowledgeCompositionRoot.build_provider(settings=KnowledgeSettings.from_env(_enabled_environment()),
            model=None, tasks=KnowledgeCompositionRoot.task_definitions(enabled=True), retrieval=object(),
            evidence_selection_version=version)


@pytest.mark.asyncio
async def test_default_production_binding_does_not_instantiate_candidate(monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError("Candidate not approved for default production")
    monkeypatch.setattr(ScoreAwareEvidenceSelector, "__init__", forbidden)
    result, _, _, _ = await invoke(monkeypatch=monkeypatch)
    assert result.status is CapabilityStatus.SUCCESS


def test_disabled_root_does_not_instantiate_candidate_or_require_its_config(monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError("Disabled must not allocate selector")
    monkeypatch.setattr(ScoreAwareEvidenceSelector, "__init__", forbidden)
    KnowledgeCompositionRoot.build_provider(settings=KnowledgeSettings.from_env({"AGENT_KNOWLEDGE_ENABLED": "false"}),
        model=None, tasks=None, retrieval=None, evidence_selection_version="ignored-while-disabled")
