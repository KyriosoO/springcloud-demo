from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from agent_runtime.capability_api.action_resolution import LocalActionResolver
from agent_runtime.business.contracts import BusinessActionDefinition, BusinessActionSettings, BusinessDomainId
from agent_runtime.business.settings import (
    BusinessConfigurationError,
    BusinessConfigurationFragment,
    BusinessConfigurationSnapshot,
    BusinessConfigurationSource,
    BusinessGlobalSettings,
    BusinessServiceBinding,
    BusinessSettingsValidator,
)
from agent_runtime.business.planner_catalog import (
    BusinessPlannerCatalog,
    build_business_planner_catalog,
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
    local_action_resolvers: tuple[LocalActionResolver, ...]
    service_bindings: tuple[BusinessServiceBinding, ...]
    snapshot_id: str
    configuration_snapshot: BusinessConfigurationSnapshot
    planner_catalog: BusinessPlannerCatalog | None


class BusinessSupportFactory:
    def build(
        self,
        *,
        definitions: Sequence[BusinessActionDefinition[Any, Any, Any, Any]],
        config: BusinessConfigurationSource,
        core_max_domain_result_bytes: int,
    ) -> BusinessSupportSnapshot:
        definitions = tuple(definitions)
        resolver_objects = tuple(
            id(item.local_action_resolver)
            for item in definitions
            if item.local_action_resolver is not None
        )
        if len(set(resolver_objects)) != len(resolver_objects):
            raise BusinessConfigurationError("business.duplicate_local_action_resolver")
        validated = BusinessSettingsValidator().validate(
            definitions, config, core_max_domain_result_bytes=core_max_domain_result_bytes
        )
        by_id = {item.descriptor.capability_id: item for item in definitions}
        enabled_resolvers = tuple(
            resolver
            for capability_id, settings in validated.actions
            if settings.enabled
            for resolver in (by_id[capability_id].local_action_resolver,)
            if resolver is not None
        )
        planner_ready = all(
            not settings.enabled
            or bool(by_id[capability_id].query_fields and settings.query_fields)
            for capability_id, settings in validated.actions
        )
        planner_catalog = (
            build_business_planner_catalog(definitions, validated)
            if planner_ready
            else None
        )
        return BusinessSupportSnapshot(
            global_settings=validated.global_settings,
            actions=tuple(
                BoundBusinessActionSupport(definition=by_id[capability_id], settings=settings)
                for capability_id, settings in validated.actions
            ),
            local_action_resolvers=enabled_resolvers,
            service_bindings=validated.service_bindings,
            snapshot_id=validated.snapshot_id,
            configuration_snapshot=validated,
            planner_catalog=planner_catalog,
        )
