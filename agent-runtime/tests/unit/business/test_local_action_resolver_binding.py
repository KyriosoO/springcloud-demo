from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

import pytest

from agent_runtime.adapters.employee.definition import employee_detail_definition
from agent_runtime.adapters.employee.settings import EmployeeAdapterSettings
from agent_runtime.adapters.transaction.definition import transaction_search_definition
from agent_runtime.adapters.transaction.settings import TransactionAdapterSettings
from agent_runtime.business.contracts import BusinessActionDefinition, BusinessServiceKey
from agent_runtime.business.provider import BusinessSupportFactory
from agent_runtime.business.settings import (
    BusinessConfigurationError,
    BusinessConfigurationSource,
    BusinessGlobalSettings,
    BusinessServiceBinding,
)
from agent_runtime.capability_api.action_resolution import LocalActionResolution, LocalActionResolutionKind


class ResolverStub:
    def __init__(self, capability_id: str) -> None:
        self._capability_id = capability_id

    @property
    def capability_id(self) -> str:
        return self._capability_id

    def resolve(self, question: str) -> LocalActionResolution:
        del question
        return LocalActionResolution(kind=LocalActionResolutionKind.NO_MATCH)


def _source(*, employee_enabled: bool, transaction_enabled: bool) -> BusinessConfigurationSource:
    employee = EmployeeAdapterSettings.from_env(
        {"AGENT_EMPLOYEE_DETAIL_ENABLED": str(employee_enabled).lower()}
    )
    transaction = TransactionAdapterSettings.from_env(
        {"AGENT_TRANSACTION_SEARCH_ENABLED": str(transaction_enabled).lower()}
    )
    return BusinessConfigurationSource(
        global_settings=BusinessGlobalSettings(),
        actions=(
            ("employee.detail", employee.action),
            ("transaction.search", transaction.action),
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


def _definitions() -> tuple[
    BusinessActionDefinition[object, object, object, object],
    BusinessActionDefinition[object, object, object, object],
]:
    return (
        cast(BusinessActionDefinition[object, object, object, object], employee_detail_definition()),
        cast(BusinessActionDefinition[object, object, object, object], transaction_search_definition()),
    )


@pytest.mark.parametrize(
    ("employee_enabled", "transaction_enabled"),
    [
        (False, False),
        (True, False),
        (False, True),
        (True, True),
    ],
)
def test_queryplan_business_snapshot_has_no_enabled_local_resolvers(
    employee_enabled: bool,
    transaction_enabled: bool,
) -> None:
    snapshot = BusinessSupportFactory().build(
        definitions=tuple(reversed(_definitions())),
        config=_source(
            employee_enabled=employee_enabled,
            transaction_enabled=transaction_enabled,
        ),
        core_max_domain_result_bytes=1048576,
    )

    assert not hasattr(snapshot, "local_action_resolvers")
    expected_action_ids = tuple(
        capability_id
        for capability_id, enabled in (
            ("employee.detail", employee_enabled),
            ("transaction.search", transaction_enabled),
        )
        if enabled
    )
    assert tuple(
        item.definition.descriptor.capability_id
        for item in snapshot.actions
        if item.settings.enabled
    ) == expected_action_ids
    assert snapshot.planner_catalog is not None
    assert len(snapshot.planner_catalog.payload["actions"]) == len(expected_action_ids)  # type: ignore[arg-type]
def test_queryplan_definition_rejects_legacy_resolver_binding() -> None:
    employee, transaction = _definitions()
    transaction = replace(transaction, local_action_resolver=ResolverStub("employee.detail"))

    with pytest.raises(BusinessConfigurationError, match="business.invalid_local_action_resolver"):
        BusinessSupportFactory().build(
            definitions=(employee, transaction),
            config=_source(employee_enabled=True, transaction_enabled=True),
            core_max_domain_result_bytes=1048576,
        )


def test_any_legacy_resolver_prevents_support_readiness() -> None:
    employee, transaction = _definitions()
    shared = ResolverStub("employee.detail")
    employee = replace(employee, local_action_resolver=shared)
    transaction = replace(transaction, local_action_resolver=shared)

    with pytest.raises(BusinessConfigurationError, match="business.invalid_local_action_resolver"):
        BusinessSupportFactory().build(
            definitions=(employee, transaction),
            config=_source(employee_enabled=False, transaction_enabled=False),
            core_max_domain_result_bytes=1048576,
        )
