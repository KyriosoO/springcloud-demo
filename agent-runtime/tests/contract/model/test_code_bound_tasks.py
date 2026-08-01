from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from agent_runtime.bootstrap import LocalModelCompositionRoot
from agent_runtime.model.contracts import ModelCallContext, ModelProviderFailureKind
from agent_runtime.model.deepseek.action_selector import (
    ActionSelectionTaskInput,
    build_action_selection_task_definition,
)
from agent_runtime.model.deepseek.tools import project_capability_tools
from agent_runtime.model.gateway import BoundedStructuredModelGateway
from agent_runtime.model.settings import ModelApiKey, ModelProvider, ModelSettings
from tests.helpers import descriptor
from tests.model_helpers import FakeStructuredModelTransport


@pytest.mark.asyncio
async def test_equivalent_but_unregistered_definition_cannot_execute() -> None:
    definition = build_action_selection_task_definition(timeout_ms=8000)
    equivalent = replace(definition)
    transport = FakeStructuredModelTransport()
    gateway = BoundedStructuredModelGateway(
        transport=transport,
        definitions=(definition,),
        max_concurrency=1,
    )
    input = ActionSelectionTaskInput(
        minimized_question="查询员工列表支持哪些条件",
        projection=project_capability_tools((descriptor(),)),
    )

    result = await gateway.generate(
        definition=equivalent,
        input=input,
        context=ModelCallContext(
            request_id="req-1",
            correlation_id="corr-1",
            deadline_monotonic=asyncio.get_running_loop().time() + 10,
        ),
    )

    assert result.failure_kind is ModelProviderFailureKind.INPUT_DENIED
    assert transport.calls == 0


@pytest.mark.asyncio
async def test_dynamic_task_input_over_limit_maps_to_input_denied_without_transport() -> None:
    definition = build_action_selection_task_definition(timeout_ms=8000, max_input_bytes=32)
    transport = FakeStructuredModelTransport()
    gateway = BoundedStructuredModelGateway(
        transport=transport,
        definitions=(definition,),
        max_concurrency=1,
    )
    input = ActionSelectionTaskInput(
        minimized_question="税" * 64,
        projection=project_capability_tools((descriptor(),)),
    )

    result = await gateway.generate(
        definition=definition,
        input=input,
        context=ModelCallContext(
            request_id="req-1",
            correlation_id="corr-1",
            deadline_monotonic=asyncio.get_running_loop().time() + 10,
        ),
    )

    assert result.failure_kind is ModelProviderFailureKind.INPUT_DENIED
    assert transport.calls == 0


@pytest.mark.asyncio
async def test_wrong_input_class_cannot_reach_registered_task() -> None:
    definition = build_action_selection_task_definition(timeout_ms=8000)
    transport = FakeStructuredModelTransport()
    gateway = BoundedStructuredModelGateway(
        transport=transport,
        definitions=(definition,),
        max_concurrency=1,
    )

    result = await gateway.generate(
        definition=definition,
        input={"minimized_question": "查询员工列表支持哪些条件"},  # type: ignore[arg-type]
        context=ModelCallContext(
            request_id="req-1",
            correlation_id="corr-1",
            deadline_monotonic=asyncio.get_running_loop().time() + 10,
        ),
    )

    assert result.failure_kind is ModelProviderFailureKind.INPUT_DENIED
    assert transport.calls == 0


def test_duplicate_task_id_and_version_prevents_startup() -> None:
    definition = build_action_selection_task_definition(timeout_ms=8000)

    with pytest.raises(ValueError, match="model.duplicate_task_definition"):
        BoundedStructuredModelGateway(
            transport=FakeStructuredModelTransport(),
            definitions=(definition, replace(definition)),
            max_concurrency=1,
        )


def test_local_composition_rejects_deepseek_provider_even_with_key() -> None:
    settings = ModelSettings(
        provider=ModelProvider.DEEPSEEK,
        api_key=ModelApiKey("sentinel-secret"),
    )

    with pytest.raises(ValueError, match="model.local_composition_requires_stub"):
        LocalModelCompositionRoot.build(
            settings=settings,
            transport=FakeStructuredModelTransport(),
            grounding_policies={},
        )
