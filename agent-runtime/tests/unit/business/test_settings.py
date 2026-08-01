from __future__ import annotations

from dataclasses import replace

import pytest

from agent_runtime.adapters.employee.definition import employee_detail_definition
from agent_runtime.adapters.employee.settings import EmployeeAdapterSettings
from agent_runtime.adapters.transaction.definition import transaction_search_definition
from agent_runtime.adapters.transaction.settings import TransactionAdapterSettings
from agent_runtime.business.contracts import BusinessServiceKey
from agent_runtime.business.settings import (
    BusinessConfigurationError,
    BusinessConfigurationSource,
    BusinessGlobalSettings,
    BusinessServiceBinding,
    BusinessSettingsValidator,
)


def _source(*, transaction: TransactionAdapterSettings | None = None) -> BusinessConfigurationSource:
    employee = EmployeeAdapterSettings.from_env({})
    transaction = transaction or TransactionAdapterSettings.from_env({})
    return BusinessConfigurationSource(
        global_settings=BusinessGlobalSettings(),
        actions=(("employee.detail", employee.action), ("transaction.search", transaction.action)),
        service_bindings=(
            BusinessServiceBinding(service_key=BusinessServiceKey("employee-service"), base_endpoint="http://employee.test"),
            BusinessServiceBinding(service_key=BusinessServiceKey("mq-procedure-service"), base_endpoint="http://transaction.test"),
        ),
    )


def test_settings_snapshot_is_order_independent_and_tracks_effective_narrowing() -> None:
    definitions = (employee_detail_definition(), transaction_search_definition())
    source = _source()
    validator = BusinessSettingsValidator()

    first = validator.validate(definitions, source, core_max_domain_result_bytes=1048576)
    reordered = validator.validate(
        tuple(reversed(definitions)),
        replace(source, actions=tuple(reversed(source.actions)), service_bindings=tuple(reversed(source.service_bindings))),
        core_max_domain_result_bytes=1048576,
    )
    narrowed = validator.validate(
        definitions,
        _source(transaction=TransactionAdapterSettings.from_env({"AGENT_TRANSACTION_SEARCH_FILTER_FIELDS": "trans_id"})),
        core_max_domain_result_bytes=1048576,
    )

    assert first.snapshot_id == reordered.snapshot_id
    assert first.snapshot_id != narrowed.snapshot_id
    assert len(first.snapshot_id) == 64


def test_settings_validator_rejects_duplicate_transform_and_unsafe_binding() -> None:
    definitions = (employee_detail_definition(), transaction_search_definition())
    source = _source()
    transaction = source.actions[1][1]
    duplicate = replace(transaction, user_transforms=transaction.user_transforms + transaction.user_transforms[:1])
    with pytest.raises(BusinessConfigurationError, match="business.invalid_user_transforms"):
        BusinessSettingsValidator().validate(
            definitions,
            replace(source, actions=(source.actions[0], ("transaction.search", duplicate))),
            core_max_domain_result_bytes=1048576,
        )

    unsafe = replace(
        source,
        service_bindings=(
            replace(source.service_bindings[0], base_endpoint="http://user@employee.test"),
            source.service_bindings[1],
        ),
    )
    with pytest.raises(BusinessConfigurationError, match="business.invalid_service_binding"):
        BusinessSettingsValidator().validate(definitions, unsafe, core_max_domain_result_bytes=1048576)


def test_global_settings_parser_is_exact_and_bounded() -> None:
    assert BusinessGlobalSettings.from_env({"AGENT_BUSINESS_EGRESS_ENABLED": "true"}).egress_enabled
    with pytest.raises(BusinessConfigurationError):
        BusinessGlobalSettings.from_env({"AGENT_BUSINESS_MAX_SAFE_FACTS": "020"})
    with pytest.raises(BusinessConfigurationError):
        BusinessGlobalSettings.from_env({"AGENT_BUSINESS_UNKNOWN": "x"})
