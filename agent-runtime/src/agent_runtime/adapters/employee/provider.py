from __future__ import annotations

from typing import Any

from agent_runtime.business.contracts import (
    BusinessActionDefinition,
    BusinessActionSettings,
    BusinessDomainId,
)
from agent_runtime.business.settings import BusinessConfigurationFragment, BusinessServiceBinding
from agent_runtime.adapters.employee.definition import (
    employee_detail_definition,
    employee_search_definition,
)
from agent_runtime.adapters.employee.settings import EmployeeAdapterSettings


class EmployeeDomainProvider:
    __slots__ = ("_binding", "_settings")

    def __init__(self, *, settings: EmployeeAdapterSettings, service_binding: BusinessServiceBinding) -> None:
        if str(service_binding.service_key) != "employee-service":
            raise ValueError("business.employee_service_binding_invalid")
        self._settings = settings
        self._binding = service_binding

    def domain_id(self) -> BusinessDomainId:
        return BusinessDomainId("employee")

    def definitions(self) -> tuple[BusinessActionDefinition[Any, Any, Any, Any], ...]:
        return (employee_detail_definition(),)

    def configuration_fragment(self) -> BusinessConfigurationFragment:
        return BusinessConfigurationFragment(
            actions=(("employee.detail", self._settings.action),),
            service_bindings=(self._binding,),
        )


class EmployeeSearchDomainProvider:
    __slots__ = ("_binding", "_search_settings")

    def __init__(
        self,
        *,
        search_settings: BusinessActionSettings,
        service_binding: BusinessServiceBinding,
    ) -> None:
        if str(service_binding.service_key) != "employee-service":
            raise ValueError("business.employee_service_binding_invalid")
        self._search_settings = search_settings
        self._binding = service_binding

    def domain_id(self) -> BusinessDomainId:
        return BusinessDomainId("employee")

    def definitions(self) -> tuple[BusinessActionDefinition[Any, Any, Any, Any], ...]:
        return (employee_search_definition(),)

    def configuration_fragment(self) -> BusinessConfigurationFragment:
        return BusinessConfigurationFragment(
            actions=(("employee.search", self._search_settings),),
            service_bindings=(self._binding,),
        )
