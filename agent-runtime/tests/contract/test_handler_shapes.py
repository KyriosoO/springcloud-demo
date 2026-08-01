from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_runtime.capability_api.contracts import (
    CapabilityExecutionContext,
    CapabilityRegistrationCandidate,
    CapabilityResult,
    JsonObject,
)
from agent_runtime.core.execution import CapabilityExecutionCore
from agent_runtime.core.registry import CapabilityRegistryBuilder
from agent_runtime.settings import CoreRuntimeSettings
from tests.helpers import QueryInput, QueryValidator, candidate, descriptor, scope, success_result


class FakeKnowledgePort:
    def __init__(self) -> None:
        self.calls = 0

    async def retrieve(self, query: str) -> None:
        del query
        self.calls += 1


@dataclass(frozen=True, slots=True)
class KnowledgeCapability:
    port: FakeKnowledgePort

    async def handle(self, input: QueryInput, context: CapabilityExecutionContext) -> CapabilityResult:
        del context
        await self.port.retrieve(input.value)
        await self.port.retrieve(input.value)
        return success_result()


class DirectBusinessAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def handle(self, input: QueryInput, context: CapabilityExecutionContext) -> CapabilityResult:
        del input, context
        self.calls += 1
        return success_result()


@pytest.mark.asyncio
async def test_both_handler_shapes_share_one_core_contract() -> None:
    knowledge_port = FakeKnowledgePort()
    knowledge = KnowledgeCapability(knowledge_port)
    business = DirectBusinessAdapter()
    candidates = (
        CapabilityRegistrationCandidate(
            descriptor=descriptor("knowledge.query"),
            enabled=True,
            argument_validator=QueryValidator(),
            handler=knowledge,
        ),
        CapabilityRegistrationCandidate(
            descriptor=descriptor("employee.get"),
            enabled=True,
            argument_validator=QueryValidator(),
            handler=business,
        ),
    )
    core = CapabilityExecutionCore(
        CapabilityRegistryBuilder(CoreRuntimeSettings()).build(candidates),
        CoreRuntimeSettings(),
    )

    knowledge_result = await core.execute(
        candidate=candidate("knowledge.query"),
        scope=scope(),
    )
    business_result = await core.execute(
        candidate=candidate("employee.get"),
        scope=scope(),
    )

    assert knowledge_result.status == business_result.status
    assert knowledge_port.calls == 2
    assert business.calls == 1


def test_handler_shape_contract_does_not_expose_transport_objects() -> None:
    annotation = KnowledgeCapability.handle.__annotations__["input"]

    assert annotation == "QueryInput"
    assert JsonObject is not annotation

