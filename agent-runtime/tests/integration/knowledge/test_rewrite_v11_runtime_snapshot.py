"""Current root owns one immutable configured domain snapshot, never defaults both."""
from dataclasses import FrozenInstanceError, replace
import json
from types import SimpleNamespace

import pytest

from agent_runtime import bootstrap, main
from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.knowledge.evidence.summary_task_v7 import KnowledgeSummaryTaskV7
from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput
from agent_runtime.knowledge.rewrite_v11 import KnowledgeRewriteTaskV11
from agent_runtime.knowledge.settings import KnowledgeSettings
from tests.integration.knowledge.test_requirement_runtime_composition import Model, Clients, plan


@pytest.mark.parametrize("domains", [("tax.policy",), ("tax.law",), ("tax.policy", "tax.law")])
def test_current_factory_captures_exact_immutable_domains(domains):
    tasks = bootstrap.KnowledgeCompositionRoot.task_definitions(enabled=True, enabled_domain_ids=domains)
    assert tasks.enabled_domain_ids is domains
    assert [(item.task_id.value, item.task_version) for item in tasks.as_tuple()] == [
        ("knowledge_rewrite", "11"), ("knowledge_summary", "7")]
    request = tasks.rewrite.build_request(KnowledgeSemanticPlanInput(
        minimized_question="税务政策及法律依据", enabled_domain_ids=domains))
    assert tuple(row["domain_id"] for row in json.loads(request.user_payload_json)["domains"]) == domains
    assert tuple(request.tools[0].arguments_schema["properties"]["queries"]["properties"]) == domains
    with pytest.raises(FrozenInstanceError):
        tasks.enabled_domain_ids = ()


@pytest.mark.parametrize("domains", [None, (), [], ["tax.policy"], ("employee",),
    ("tax.policy", "tax.policy"), ("tax.law", "tax.policy")])
def test_enabled_requires_explicit_valid_snapshot_before_provider(domains):
    with pytest.raises(ValueError, match="knowledge.enabled_domains"):
        bootstrap.KnowledgeCompositionRoot.task_definitions(enabled=True, enabled_domain_ids=domains)


def test_disabled_does_not_validate_domains_or_create_model_tasks(monkeypatch):
    def forbidden(**kwargs):
        pytest.fail("Disabled must not build a Knowledge task")
    monkeypatch.setattr(KnowledgeRewriteTaskV11, "definition", forbidden)
    monkeypatch.setattr(KnowledgeSummaryTaskV7, "definition", forbidden)
    assert bootstrap.KnowledgeCompositionRoot.task_definitions(enabled=False, enabled_domain_ids=("unknown",)) is None


@pytest.mark.parametrize("domains", [(), ["tax.policy"], ("tax.law",), ("tax.policy", "tax.law")])
def test_mismatched_provider_snapshot_fails_before_model_or_handler(domains):
    tasks = bootstrap.KnowledgeCompositionRoot.task_definitions(enabled=True, enabled_domain_ids=("tax.policy",))
    tasks = replace(tasks, enabled_domain_ids=domains)
    settings = KnowledgeSettings.from_env({"AGENT_KNOWLEDGE_ENABLED": "true", "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy"})
    with pytest.raises(ValueError, match="knowledge.task_domain_snapshot_mismatch"):
        bootstrap.KnowledgeCompositionRoot.build_provider(settings=settings, model=None, tasks=tasks, retrieval=object())


@pytest.mark.asyncio
@pytest.mark.parametrize("domains", [("tax.policy",), ("tax.law",), ("tax.policy", "tax.law")])
async def test_main_transmits_validated_snapshot_to_factory_and_provider(domains, monkeypatch):
    factory, provider = bootstrap.KnowledgeCompositionRoot.task_definitions, bootstrap.KnowledgeCompositionRoot.build_provider
    snapshots = []

    def capture_factory(**kwargs):
        tasks = factory(**kwargs)
        snapshots.append(tasks)
        assert kwargs["enabled_domain_ids"] == domains
        return tasks

    def capture_provider(**kwargs):
        assert kwargs["tasks"] is snapshots[0]
        assert kwargs["tasks"].enabled_domain_ids == kwargs["settings"].enabled_domain_ids == domains
        return provider(**kwargs)

    monkeypatch.setattr(bootstrap.KnowledgeCompositionRoot, "task_definitions", capture_factory)
    monkeypatch.setattr(bootstrap.KnowledgeCompositionRoot, "build_provider", capture_provider)
    clients = Clients()
    runtime = main.build_runtime({"AGENT_MODEL_PROVIDER": "stub", "AGENT_KNOWLEDGE_ENABLED": "true",
        "AGENT_KNOWLEDGE_ENABLED_DOMAINS": ",".join(domains), "AGENT_KNOWLEDGE_ES_BASE_URL": "http://knowledge.test"},
        model_transport=Model(plan()), knowledge_http_client_factory=clients)
    await runtime.aclose()
    assert len(snapshots) == 1 and all(client.is_closed for client in clients.clients)


def test_frozen_flash_fixture_restores_current_root_entrypoint_and_helper(monkeypatch):
    import sys
    from tests.integration.knowledge import test_requirement_runtime_composition as current
    from tests.system_e2e.conftest import isolate_consumed_flash_root
    root, build = bootstrap.KnowledgeCompositionRoot, main.build_runtime
    request = SimpleNamespace(module=SimpleNamespace(__name__="tests.system_e2e.test_knowledge_model_failure_probe_v3",
        invoke=current.invoke), function=SimpleNamespace(__name__="test_current_production_root_rejects_with_zero_downstream"))
    with monkeypatch.context() as patch:
        isolate_consumed_flash_root.__wrapped__(request, patch)
        assert bootstrap.KnowledgeCompositionRoot is not root and main.build_runtime is not build
        assert bootstrap.KnowledgeCompositionRoot.task_definitions(enabled=True).rewrite.task_version == "10"
        assert request.module.invoke is sys.modules[current.__name__].invoke
        assert request.module.invoke is not current.invoke
    assert bootstrap.KnowledgeCompositionRoot is root and main.build_runtime is build
    assert sys.modules[current.__name__] is current and request.module.invoke is current.invoke
    request.function.__name__ = "unrelated_test"
    isolate_consumed_flash_root.__wrapped__(request, monkeypatch)
    assert bootstrap.KnowledgeCompositionRoot is root and main.build_runtime is build


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["old_array", "missing_slot", "unknown_slot", "wrong_type", "blank_slot", "missing_requirement", "duplicate_key"])
async def test_current_root_rejects_new_wire_faults_after_exactly_two_model_calls(fault):
    from dataclasses import asdict
    from agent_runtime.model.contracts import ModelTaskId, StructuredToolCall
    from tests.helpers import scope
    from agent_runtime.observation import observation_scope
    from tests.integration.knowledge.test_requirement_runtime_composition import QUESTION
    value = plan()
    if fault == "old_array":
        value["queries"] = [{"domain_id": "tax.policy", "query": QUESTION}]
    elif fault == "missing_slot":
        del value["queries"]["tax.law"]
    elif fault == "unknown_slot":
        value["queries"]["employee"] = ""
    elif fault == "wrong_type":
        value["queries"]["tax.policy"] = [QUESTION]
    elif fault == "blank_slot":
        value["queries"]["tax.law"] = " "
    elif fault == "missing_requirement":
        value["queries"]["tax.law"] = QUESTION

    class WireModel(Model):
        async def complete(self, request, **kwargs):
            response = await super().complete(request, **kwargs)
            if fault == "duplicate_key" and request.task_id is ModelTaskId.KNOWLEDGE_REWRITE:
                call = response.tool_calls[0]
                raw = call.arguments_json.replace('"tax.policy":', '"tax.policy":"duplicate-response-marker","tax.policy":', 1)
                return replace(response, tool_calls=(StructuredToolCall(name=call.name, arguments_json=raw),))
            return response

    model, clients = WireModel(value), Clients()
    runtime = main.build_runtime({"AGENT_MODEL_PROVIDER": "stub", "AGENT_KNOWLEDGE_ENABLED": "true",
        "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,tax.law", "AGENT_KNOWLEDGE_ES_BASE_URL": "http://knowledge.test"},
        model_transport=model, knowledge_http_client_factory=clients)
    try:
        with observation_scope() as collector:
            result = await runtime.ainvoke(question=QUESTION, scope=scope(QUESTION))
            observed = collector.snapshot()
    finally:
        await runtime.aclose()
    assert result.status is CapabilityStatus.DOWNSTREAM_FAILURE
    assert [item.task_id for item in model.requests] == [ModelTaskId.ACTION_SELECTION, ModelTaskId.KNOWLEDGE_REWRITE]
    assert model.requests[-1].task_version == "11" and observed.model_calls[-1]["failureKind"] == "invalid_output"
    assert not clients.paths and not observed.plans and not observed.downstream_calls
    assert "duplicate-response-marker" not in json.dumps(asdict(observed))
    assert all(client.is_closed for client in clients.clients)
