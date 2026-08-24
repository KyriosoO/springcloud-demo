from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_runtime.adapters.employee.definition import employee_detail_definition
from agent_runtime.adapters.employee.settings import EmployeeAdapterSettings
from agent_runtime.adapters.transaction.definition import transaction_search_definition
from agent_runtime.adapters.transaction.settings import TransactionAdapterSettings
from agent_runtime.business.contracts import BusinessActionDefinition, BusinessServiceKey
from agent_runtime.business.planner_catalog import BusinessPlannerCatalog
from agent_runtime.business.provider import BusinessSupportFactory
from agent_runtime.business.settings import (
    BusinessConfigurationSource,
    BusinessConfigurationSnapshot,
    BusinessGlobalSettings,
    BusinessServiceBinding,
)
from agent_runtime.capability_api.contracts import (
    CapabilityExecutionContext,
    CapabilityRegistrationCandidate,
    CapabilityResult,
    JsonObject,
)
from agent_runtime.model.contracts import (
    BusinessQueryPlanTaskInput,
    ModelCallContext,
)
from tests.helpers import success_result


Definition = BusinessActionDefinition[Any, Any, Any, Any]


@dataclass(frozen=True, slots=True)
class RuntimeBusinessFixture:
    definitions: tuple[Definition, Definition]
    snapshot: BusinessConfigurationSnapshot
    catalog: BusinessPlannerCatalog


class RecordingPlanGenerator:
    def __init__(self, payloads: tuple[JsonObject, ...]) -> None:
        self._payloads = iter(payloads)
        self.calls = 0
        self.inputs: list[BusinessQueryPlanTaskInput] = []
        self.contexts: list[ModelCallContext] = []

    async def generate(
        self,
        input: BusinessQueryPlanTaskInput,
        *,
        context: ModelCallContext,
    ) -> JsonObject:
        self.calls += 1
        self.inputs.append(input)
        self.contexts.append(context)
        return next(self._payloads)


class CaptureBusinessHandler:
    def __init__(self, result: CapabilityResult | None = None) -> None:
        self.result = result or success_result()
        self.calls = 0
        self.inputs: list[object] = []
        self.contexts: list[CapabilityExecutionContext] = []

    async def handle(
        self,
        input: object,
        context: CapabilityExecutionContext,
    ) -> CapabilityResult:
        self.calls += 1
        self.inputs.append(input)
        self.contexts.append(context)
        return self.result


def runtime_business_fixture() -> RuntimeBusinessFixture:
    definitions = (employee_detail_definition(), transaction_search_definition())
    source = BusinessConfigurationSource(
        global_settings=BusinessGlobalSettings(),
        actions=(
            (
                "employee.detail",
                EmployeeAdapterSettings.from_env(
                    {"AGENT_EMPLOYEE_DETAIL_ENABLED": "true"}
                ).action,
            ),
            (
                "transaction.search",
                TransactionAdapterSettings.from_env(
                    {"AGENT_TRANSACTION_SEARCH_ENABLED": "true"}
                ).action,
            ),
        ),
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
    support = BusinessSupportFactory().build(
        definitions=definitions,
        config=source,
        core_max_domain_result_bytes=262144,
    )
    assert support.planner_catalog is not None
    return RuntimeBusinessFixture(
        definitions=definitions,
        snapshot=support.configuration_snapshot,
        catalog=support.planner_catalog,
    )


def business_registration(
    definition: Definition,
    handler: CaptureBusinessHandler,
) -> CapabilityRegistrationCandidate[Any]:
    return CapabilityRegistrationCandidate(
        descriptor=definition.descriptor,
        enabled=True,
        argument_validator=definition.argument_validator,
        handler=handler,
    )
