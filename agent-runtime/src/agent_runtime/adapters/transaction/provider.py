from __future__ import annotations

from typing import Any

from agent_runtime.business.contracts import (
    BusinessActionDefinition,
    BusinessActionSettings,
    BusinessDomainId,
)
from agent_runtime.business.settings import BusinessConfigurationFragment, BusinessServiceBinding
from agent_runtime.adapters.transaction.definition import (
    transaction_list_search_definition,
    transaction_search_definition,
)
from agent_runtime.adapters.transaction.settings import TransactionAdapterSettings


class TransactionDomainProvider:
    __slots__ = ("_binding", "_settings")

    def __init__(self, *, settings: TransactionAdapterSettings, service_binding: BusinessServiceBinding) -> None:
        if str(service_binding.service_key) != "mq-procedure-service":
            raise ValueError("business.transaction_service_binding_invalid")
        self._settings = settings
        self._binding = service_binding

    def domain_id(self) -> BusinessDomainId:
        return BusinessDomainId("transaction")

    def definitions(self) -> tuple[BusinessActionDefinition[Any, Any, Any, Any], ...]:
        return (transaction_search_definition(),)

    def configuration_fragment(self) -> BusinessConfigurationFragment:
        return BusinessConfigurationFragment(
            actions=(("transaction.search", self._settings.action),),
            service_bindings=(self._binding,),
        )


class TransactionListDomainProvider:
    __slots__ = ("_binding", "_settings")

    def __init__(
        self, *, settings: BusinessActionSettings, service_binding: BusinessServiceBinding
    ) -> None:
        if str(service_binding.service_key) != "mq-procedure-service":
            raise ValueError("business.transaction_service_binding_invalid")
        self._settings = settings
        self._binding = service_binding

    def domain_id(self) -> BusinessDomainId:
        return BusinessDomainId("transaction")

    def definitions(self) -> tuple[BusinessActionDefinition[Any, Any, Any, Any], ...]:
        return (transaction_list_search_definition(),)

    def configuration_fragment(self) -> BusinessConfigurationFragment:
        return BusinessConfigurationFragment(
            actions=(("transaction.search", self._settings),),
            service_bindings=(self._binding,),
        )
