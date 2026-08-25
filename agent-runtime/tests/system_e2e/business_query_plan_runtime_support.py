from __future__ import annotations

from typing import Any, Protocol

from agent_runtime.adapters.employee.protected_input import EmployeeProtectedValueExtractor
from agent_runtime.adapters.employee.provider import EmployeeDomainProvider
from agent_runtime.adapters.employee.settings import EmployeeAdapterSettings
from agent_runtime.adapters.transaction.protected_input import TransactionProtectedValueExtractor
from agent_runtime.adapters.transaction.provider import TransactionDomainProvider
from agent_runtime.adapters.transaction.settings import TransactionAdapterSettings
from agent_runtime.bootstrap import RuntimeCompositionRoot
from agent_runtime.business.contracts import BusinessActionDefinition, BusinessServiceKey
from agent_runtime.business.egress import BusinessEgressProjector
from agent_runtime.business.handler import BoundBusinessActionHandler
from agent_runtime.business.http_client import FakeDomainTransport, UserJwtBusinessHttpClient
from agent_runtime.business.protected_input import CompositeBusinessProtectedValueExtractor
from agent_runtime.business.provider import BusinessSupportFactory, BusinessSupportSnapshot
from agent_runtime.business.settings import (
    BusinessConfigurationSource,
    BusinessGlobalSettings,
    BusinessServiceBinding,
    GlobalBusinessEgressPolicy,
)
from agent_runtime.business.user_projection import BusinessUserResultProjector
from agent_runtime.capability_api.contracts import CapabilityRegistrationCandidate
from agent_runtime.graph.action_resolution import CapabilitySelectionNode
from agent_runtime.graph.business_query_planning import BusinessQueryPlanRuntimeBindings
from agent_runtime.graph.nodes import AnswerGenerationNode
from agent_runtime.model.context import ModelCallContextAccessor, ModelContextBindingRuntimeInvoker
from agent_runtime.model.contracts import BusinessQueryPlanGenerator
from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.runtime import AgentRuntimeInvoker
from agent_runtime.settings import CoreRuntimeSettings


class BusinessQueryPlanModelComposition(Protocol):
    @property
    def business_query_plan_generator(self) -> BusinessQueryPlanGenerator: ...

    @property
    def context_accessor(self) -> ModelCallContextAccessor: ...

    def bind_runtime(self, runtime: AgentRuntimeInvoker) -> ModelContextBindingRuntimeInvoker: ...


class _StaticProvider:
    def __init__(self, *registrations: CapabilityRegistrationCandidate[Any]) -> None:
        self._registrations = tuple(registrations)

    def registrations(self) -> tuple[CapabilityRegistrationCandidate[Any], ...]:
        return self._registrations


def build_business_query_plan_runtime(
    *,
    model: BusinessQueryPlanModelComposition,
    employee_transport: FakeDomainTransport,
    transaction_transport: FakeDomainTransport,
    fallback_selector: CapabilitySelectionNode,
    answer_generator: AnswerGenerationNode,
    employee_endpoint: str,
    transaction_endpoint: str,
    expected_snapshot_id: str | None = None,
) -> ModelContextBindingRuntimeInvoker:
    core_settings = CoreRuntimeSettings()
    definitions, support = _build_business_query_plan_support(
        employee_endpoint=employee_endpoint,
        transaction_endpoint=transaction_endpoint,
        core_settings=core_settings,
    )
    if support.planner_catalog is None:
        raise ValueError("business_query_plan_e2e.catalog_unavailable")
    if expected_snapshot_id is not None and (
        support.snapshot_id != expected_snapshot_id
        or support.planner_catalog.snapshot_id != expected_snapshot_id
    ):
        raise ValueError("business_query_plan_live.snapshot_mismatch")
    global_settings = support.global_settings
    clients = {
        "employee-service": UserJwtBusinessHttpClient(
            transport=employee_transport,
            max_response_bytes=global_settings.http_max_response_bytes,
        ),
        "mq-procedure-service": UserJwtBusinessHttpClient(
            transport=transaction_transport,
            max_response_bytes=global_settings.http_max_response_bytes,
        ),
    }
    registrations = tuple(
        CapabilityRegistrationCandidate[Any](
            descriptor=item.definition.descriptor,
            enabled=item.settings.enabled,
            argument_validator=item.definition.argument_validator,
            handler=BoundBusinessActionHandler(
                definition=item.definition,
                settings=item.settings,
                client=clients[str(item.definition.service_key)],
                user_projector=BusinessUserResultProjector(),
                egress_projector=BusinessEgressProjector(),
                egress_policy=GlobalBusinessEgressPolicy.from_settings(support.global_settings),
                config_snapshot_id=support.snapshot_id,
                max_user_result_bytes=support.global_settings.max_user_result_bytes,
            ),
        )
        for item in support.actions
        if item.settings.enabled
    )
    runtime = RuntimeCompositionRoot.build(
        settings=core_settings,
        providers=(_StaticProvider(*registrations),),
        capability_selector=fallback_selector,
        answer_generator=answer_generator,
        business_query_plan=BusinessQueryPlanRuntimeBindings(
            definitions=definitions,
            snapshot=support.configuration_snapshot,
            planner_catalog=support.planner_catalog,
            generator=model.business_query_plan_generator,
            context_accessor=model.context_accessor,
            protected_value_extractor=CompositeBusinessProtectedValueExtractor(
                (EmployeeProtectedValueExtractor(), TransactionProtectedValueExtractor())
            ),
            guard=QuestionEgressGuard(),
        ),
    )
    return model.bind_runtime(runtime)


def business_query_plan_snapshot_id(
    *,
    employee_endpoint: str,
    transaction_endpoint: str,
) -> str:
    _, support = _build_business_query_plan_support(
        employee_endpoint=employee_endpoint,
        transaction_endpoint=transaction_endpoint,
        core_settings=CoreRuntimeSettings(),
    )
    if support.planner_catalog is None or support.planner_catalog.snapshot_id != support.snapshot_id:
        raise ValueError("business_query_plan_e2e.catalog_unavailable")
    return support.snapshot_id


def _build_business_query_plan_support(
    *,
    employee_endpoint: str,
    transaction_endpoint: str,
    core_settings: CoreRuntimeSettings,
) -> tuple[tuple[BusinessActionDefinition[Any, Any, Any, Any], ...], BusinessSupportSnapshot]:
    employee_domain = EmployeeDomainProvider(
        settings=EmployeeAdapterSettings.from_env({"AGENT_EMPLOYEE_DETAIL_ENABLED": "true"}),
        service_binding=BusinessServiceBinding(
            service_key=BusinessServiceKey("employee-service"),
            base_endpoint=employee_endpoint,
        ),
    )
    transaction_domain = TransactionDomainProvider(
        settings=TransactionAdapterSettings.from_env({"AGENT_TRANSACTION_SEARCH_ENABLED": "true"}),
        service_binding=BusinessServiceBinding(
            service_key=BusinessServiceKey("mq-procedure-service"),
            base_endpoint=transaction_endpoint,
        ),
    )
    definitions = (*employee_domain.definitions(), *transaction_domain.definitions())
    fragments = (employee_domain.configuration_fragment(), transaction_domain.configuration_fragment())
    global_settings = BusinessGlobalSettings()
    support = BusinessSupportFactory().build(
        definitions=definitions,
        config=BusinessConfigurationSource(
            global_settings=global_settings,
            actions=tuple(item for fragment in fragments for item in fragment.actions),
            service_bindings=tuple(item for fragment in fragments for item in fragment.service_bindings),
        ),
        core_max_domain_result_bytes=core_settings.max_domain_result_bytes,
    )
    return definitions, support
