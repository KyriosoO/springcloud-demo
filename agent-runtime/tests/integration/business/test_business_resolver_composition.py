from __future__ import annotations

from collections.abc import Mapping

from agent_runtime.adapters.employee.definition import employee_detail_definition
from agent_runtime.adapters.employee.settings import EmployeeAdapterSettings
from agent_runtime.adapters.transaction.definition import transaction_search_definition
from agent_runtime.adapters.transaction.settings import TransactionAdapterSettings
from agent_runtime.business.contracts import BusinessServiceKey
from agent_runtime.business.provider import BusinessSupportFactory, BusinessSupportSnapshot
from agent_runtime.business.settings import (
    BusinessConfigurationSource,
    BusinessGlobalSettings,
    BusinessServiceBinding,
)


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


def test_business_snapshot_exposes_only_queryplan_catalog_and_no_resolver_path() -> None:
    snapshot = _support()

    assert not hasattr(snapshot, "local_action_resolvers")
    assert snapshot.planner_catalog is not None
    actions = snapshot.planner_catalog.payload["actions"]
    assert isinstance(actions, tuple)
    assert all(isinstance(item, Mapping) for item in actions)
    assert tuple(item["action"] for item in actions if isinstance(item, Mapping)) == (
        "employee.detail",
        "transaction.search",
    )
