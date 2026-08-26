from __future__ import annotations

from dataclasses import replace
from typing import Any

from agent_runtime.adapters.employee.provider import EmployeeSearchDomainProvider
from agent_runtime.adapters.transaction.provider import TransactionListDomainProvider
from agent_runtime.bootstrap import (
    BusinessQueryRuntimeCompositionRoot,
    LocalModelComponents,
)
from agent_runtime.business.contracts import BusinessActionDefinition, BusinessServiceKey
from agent_runtime.business.http_client import FakeDomainTransport
from agent_runtime.business.provider import BusinessSupportFactory, BusinessSupportSnapshot
from agent_runtime.business.settings import (
    BusinessConfigurationSource,
    BusinessGlobalSettings,
    BusinessQueryConfigurationLoader,
    BusinessServiceBinding,
)
from agent_runtime.graph.action_resolution import CapabilitySelectionNode
from agent_runtime.graph.nodes import AnswerGenerationNode
from agent_runtime.model.context import ModelContextBindingRuntimeInvoker
from agent_runtime.settings import CoreRuntimeSettings


def build_business_query_plan_runtime(
    *,
    model: LocalModelComponents,
    employee_transport: FakeDomainTransport,
    transaction_transport: FakeDomainTransport,
    fallback_selector: CapabilitySelectionNode,
    answer_generator: AnswerGenerationNode,
    employee_endpoint: str,
    transaction_endpoint: str,
    expected_snapshot_id: str | None = None,
) -> ModelContextBindingRuntimeInvoker:
    _, support = _build_business_query_plan_support(
        employee_endpoint=employee_endpoint,
        transaction_endpoint=transaction_endpoint,
        core_settings=CoreRuntimeSettings(),
    )
    if expected_snapshot_id is not None and (
        support.snapshot_id != expected_snapshot_id
        or support.planner_catalog is None
        or support.planner_catalog.snapshot_id != expected_snapshot_id
    ):
        raise ValueError("business_query_plan_live.snapshot_mismatch")
    test_model = replace(
        model,
        action_selector=fallback_selector,
        answer_generator=answer_generator,
    )
    return BusinessQueryRuntimeCompositionRoot.build(
        model=test_model,
        employee_transport=employee_transport,
        transaction_transport=transaction_transport,
        employee_endpoint=employee_endpoint,
        transaction_endpoint=transaction_endpoint,
    )


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
    configured = dict(BusinessQueryConfigurationLoader.load_v2_resource().actions)
    employee_domain = EmployeeSearchDomainProvider(
        search_settings=configured["employee.search"],
        semantic_settings=configured["employee.semantic_search"],
        service_binding=BusinessServiceBinding(
            service_key=BusinessServiceKey("employee-service"),
            base_endpoint=employee_endpoint,
        ),
    )
    transaction_domain = TransactionListDomainProvider(
        settings=configured["transaction.search"],
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
