from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from agent_runtime.business.contracts import BusinessActionDefinition, BusinessActionSettings, BusinessDomainId
from agent_runtime.business.settings import (
    BusinessConfigurationFragment,
    BusinessConfigurationSnapshot,
    BusinessConfigurationSource,
    BusinessGlobalSettings,
    BusinessServiceBinding,
    BusinessSettingsValidator,
)


class BusinessDomainProvider(Protocol):
    def domain_id(self) -> BusinessDomainId: ...
    def definitions(self) -> tuple[BusinessActionDefinition[Any, Any, Any, Any], ...]: ...
    def configuration_fragment(self) -> BusinessConfigurationFragment: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class BoundBusinessActionSupport:
    definition: BusinessActionDefinition[Any, Any, Any, Any]
    settings: BusinessActionSettings


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessSupportSnapshot:
    global_settings: BusinessGlobalSettings
    actions: tuple[BoundBusinessActionSupport, ...]
    service_bindings: tuple[BusinessServiceBinding, ...]
    snapshot_id: str


class BusinessSupportFactory:
    def build(
        self,
        *,
        definitions: Sequence[BusinessActionDefinition[Any, Any, Any, Any]],
        config: BusinessConfigurationSource,
        core_max_domain_result_bytes: int,
    ) -> BusinessSupportSnapshot:
        validated = BusinessSettingsValidator().validate(
            definitions, config, core_max_domain_result_bytes=core_max_domain_result_bytes
        )
        by_id = {item.descriptor.capability_id: item for item in definitions}
        return BusinessSupportSnapshot(
            global_settings=validated.global_settings,
            actions=tuple(
                BoundBusinessActionSupport(definition=by_id[capability_id], settings=settings)
                for capability_id, settings in validated.actions
            ),
            service_bindings=validated.service_bindings,
            snapshot_id=validated.snapshot_id,
        )
