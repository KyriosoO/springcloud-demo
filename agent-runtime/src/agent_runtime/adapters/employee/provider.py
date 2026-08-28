from __future__ import annotations

from typing import Any

from agent_runtime.business.contracts import (
    BusinessActionDefinition,
    BusinessActionSettings,
    BusinessDomainId,
)
from agent_runtime.business.settings import BusinessConfigurationFragment, BusinessServiceBinding
from agent_runtime.adapters.employee.definition import (
    employee_search_definition,
    employee_semantic_search_definition,
)


class EmployeeSearchDomainProvider:
    __slots__ = ("_binding", "_search_settings", "_semantic_settings")

    def __init__(
        self,
        *,
        search_settings: BusinessActionSettings,
        service_binding: BusinessServiceBinding,
        semantic_settings: BusinessActionSettings | None = None,
    ) -> None:
        if str(service_binding.service_key) != "employee-service":
            raise ValueError("business.employee_service_binding_invalid")
        self._search_settings = search_settings
        self._semantic_settings = semantic_settings
        self._binding = service_binding

    def domain_id(self) -> BusinessDomainId:
        return BusinessDomainId("employee")

    def definitions(self) -> tuple[BusinessActionDefinition[Any, Any, Any, Any], ...]:
        if self._search_settings.code_contract_version == "employee-search-plan-v3":
            contract_version = "v3"
        elif self._search_settings.code_contract_version == "employee-search-plan-v2":
            contract_version = "v2"
        else:
            raise ValueError("business.unknown_action_contract")
        if self._semantic_settings is None:
            return (employee_search_definition(contract_version=contract_version),)
        return (
            employee_search_definition(contract_version=contract_version),
            employee_semantic_search_definition(),
        )

    def configuration_fragment(self) -> BusinessConfigurationFragment:
        actions: tuple[tuple[str, BusinessActionSettings], ...] = (
            ("employee.search", self._search_settings),
        )
        if self._semantic_settings is not None:
            actions += (("employee.semantic_search", self._semantic_settings),)
        return BusinessConfigurationFragment(
            actions=actions,
            service_bindings=(self._binding,),
        )
