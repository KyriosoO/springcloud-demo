from __future__ import annotations

from typing import Any

import pytest

from agent_runtime.adapters.employee.definition import employee_detail_definition
from agent_runtime.adapters.employee.settings import EmployeeAdapterSettings
from agent_runtime.adapters.transaction.definition import transaction_search_definition
from agent_runtime.adapters.transaction.settings import TransactionAdapterSettings
from agent_runtime.bootstrap import RuntimeCompositionRoot
from agent_runtime.business.contracts import BusinessServiceKey
from agent_runtime.business.provider import BusinessSupportFactory, BusinessSupportSnapshot
from agent_runtime.business.settings import (
    BusinessConfigurationSource,
    BusinessGlobalSettings,
    BusinessServiceBinding,
)
from agent_runtime.capability_api.contracts import (
    CapabilityExecutionContext,
    CapabilityRegistrationCandidate,
    CapabilityResult,
)
from agent_runtime.graph.action_resolution import CapabilitySelectionDecision, CapabilitySelectionInput
from agent_runtime.graph.state import AnswerGenerationDecision, AnswerGenerationDecisionKind
from agent_runtime.settings import CoreRuntimeSettings
from tests.helpers import FixedAnswerGenerator, Provider, scope, success_result


class ForbiddenSelector:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, input: CapabilitySelectionInput) -> CapabilitySelectionDecision:
        del input
        self.calls += 1
        raise AssertionError("business local resolution must not call the model selector")


class CaptureHandler:
    def __init__(self) -> None:
        self.inputs: list[object] = []

    async def handle(self, input: object, context: CapabilityExecutionContext) -> CapabilityResult:
        del context
        self.inputs.append(input)
        return success_result()


def _support() -> BusinessSupportSnapshot:
    employee = EmployeeAdapterSettings.from_env({"AGENT_EMPLOYEE_DETAIL_ENABLED": "true"})
    transaction = TransactionAdapterSettings.from_env({"AGENT_TRANSACTION_SEARCH_ENABLED": "true"})
    source = BusinessConfigurationSource(
        global_settings=BusinessGlobalSettings(),
        actions=(("employee.detail", employee.action), ("transaction.search", transaction.action)),
        service_bindings=(
            BusinessServiceBinding(
                service_key=BusinessServiceKey("employee-service"),
                base_endpoint="http://employee.test",
            ),
            BusinessServiceBinding(
                service_key=BusinessServiceKey("mq-procedure-service"),
                base_endpoint="http://transaction.test",
            ),
        ),
    )
    snapshot = BusinessSupportFactory().build(
        definitions=(employee_detail_definition(), transaction_search_definition()),
        config=source,
        core_max_domain_result_bytes=1048576,
    )
    return snapshot


@pytest.mark.asyncio
async def test_transitional_snapshot_excludes_queryplan_employee_from_resolver_path() -> None:
    snapshot = _support()
    handler = CaptureHandler()
    candidates = tuple(
        CapabilityRegistrationCandidate[Any](
            descriptor=item.definition.descriptor,
            enabled=True,
            argument_validator=item.definition.argument_validator,
            handler=handler,
        )
        for item in snapshot.actions
        if item.settings.enabled and item.definition.local_action_resolver is not None
    )
    selector = ForbiddenSelector()
    runtime = RuntimeCompositionRoot.build(
        settings=CoreRuntimeSettings(),
        providers=(Provider(*candidates),),
        capability_selector=selector,
        answer_generator=FixedAnswerGenerator(
            AnswerGenerationDecision(
                kind=AnswerGenerationDecisionKind.ANSWER,
                answer_text="unused",
            )
        ),
        local_action_resolvers=snapshot.local_action_resolvers,
    )

    transaction_question = "查询交易 交易类型=PAY"
    transaction_outcome = await runtime.ainvoke(
        question=transaction_question,
        scope=scope(question=transaction_question),
    )

    assert tuple(item.capability_id for item in snapshot.local_action_resolvers) == ("transaction.search",)
    assert snapshot.planner_catalog is None
    assert transaction_outcome.capability_id == "transaction.search"
    assert len(handler.inputs) == 1
    assert selector.calls == 0
