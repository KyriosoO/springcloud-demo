from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
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
    ("employee_enabled", "transaction_enabled", "expected_ids"),
    [
        (False, False, ()),
        (True, False, ("employee.detail",)),
        (False, True, ("transaction.search",)),
        (True, True, ("employee.detail", "transaction.search")),
    ],
)
def test_support_snapshot_projects_only_enabled_resolvers_in_canonical_order(
    employee_enabled: bool,
    transaction_enabled: bool,
    expected_ids: tuple[str, ...],
) -> None:
    snapshot = BusinessSupportFactory().build(
        definitions=tuple(reversed(_definitions())),
        config=_source(
            employee_enabled=employee_enabled,
            transaction_enabled=transaction_enabled,
        ),
        core_max_domain_result_bytes=1048576,
    )

    assert tuple(item.capability_id for item in snapshot.local_action_resolvers) == expected_ids
    assert tuple(
        item.definition.descriptor.capability_id
        for item in snapshot.actions
        if item.settings.enabled
    ) == expected_ids
    with pytest.raises(FrozenInstanceError):
        snapshot.local_action_resolvers = ()  # type: ignore[misc]


def test_definition_resolver_id_mismatch_prevents_support_readiness() -> None:
    employee, transaction = _definitions()
    employee = replace(employee, local_action_resolver=ResolverStub("transaction.search"))

    with pytest.raises(BusinessConfigurationError, match="business.invalid_definition"):
        BusinessSupportFactory().build(
            definitions=(employee, transaction),
            config=_source(employee_enabled=True, transaction_enabled=True),
            core_max_domain_result_bytes=1048576,
        )


def test_definition_without_resolver_prevents_support_readiness() -> None:
    employee, transaction = _definitions()
    employee = replace(employee, local_action_resolver=cast(Any, None))

    with pytest.raises(BusinessConfigurationError, match="business.invalid_local_action_resolver"):
        BusinessSupportFactory().build(
            definitions=(employee, transaction),
            config=_source(employee_enabled=True, transaction_enabled=False),
            core_max_domain_result_bytes=1048576,
        )


def test_duplicate_resolver_object_prevents_support_readiness() -> None:
    employee, transaction = _definitions()
    shared = ResolverStub("employee.detail")
    employee = replace(employee, local_action_resolver=shared)
    transaction = replace(transaction, local_action_resolver=shared)

    with pytest.raises(BusinessConfigurationError, match="business.duplicate_local_action_resolver"):
        BusinessSupportFactory().build(
            definitions=(employee, transaction),
            config=_source(employee_enabled=False, transaction_enabled=False),
            core_max_domain_result_bytes=1048576,
        )
