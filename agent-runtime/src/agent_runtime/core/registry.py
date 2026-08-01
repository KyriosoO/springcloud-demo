from __future__ import annotations

import hashlib
import inspect
import logging
from dataclasses import dataclass, fields
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any, Sequence, cast

from agent_runtime.capability_api.contracts import (
    CapabilityDescriptor,
    CapabilityExecutionContext,
    CapabilityRegistrationCandidate,
    CapabilityResult,
    ContractViolation,
    InvalidCapabilityArguments,
    JsonObject,
    canonical_json_bytes,
    descriptor_to_json,
    validate_descriptor,
)
from agent_runtime.settings import CoreRuntimeSettings

_LOGGER = logging.getLogger(__name__)


class CapabilityRegistryError(RuntimeError):
    def __init__(self, code: str, capability_id: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.capability_id = capability_id


class InvalidValidatedCall(RuntimeError):
    def __init__(self) -> None:
        super().__init__("core.invalid_validated_call")
        self.code = "core.invalid_validated_call"


@dataclass(frozen=True, slots=True)
class ValidatedCapabilityCall:
    _owner: object
    capability_id: str
    registry_snapshot_id: str
    _input: object


class RegisteredCapability:
    __slots__ = ("_candidate", "_owner", "_snapshot_id")

    def __init__(self, candidate: CapabilityRegistrationCandidate[Any], snapshot_id: str) -> None:
        self._candidate = candidate
        self._snapshot_id = snapshot_id
        self._owner = object()

    @property
    def capability_id(self) -> str:
        return self._candidate.descriptor.capability_id

    def validate(self, arguments: JsonObject) -> ValidatedCapabilityCall:
        validator = self._candidate.argument_validator
        if validator is None:
            raise InvalidCapabilityArguments("core.invalid_arguments")
        typed_input = validator.validate(arguments)
        if not _is_immutable_input(typed_input):
            raise InvalidValidatedCall()
        return ValidatedCapabilityCall(
            _owner=self._owner,
            capability_id=self.capability_id,
            registry_snapshot_id=self._snapshot_id,
            _input=typed_input,
        )

    async def invoke(
        self,
        call: ValidatedCapabilityCall,
        context: CapabilityExecutionContext,
    ) -> CapabilityResult:
        if (
            not isinstance(call, ValidatedCapabilityCall)
            or call._owner is not self._owner
            or call.capability_id != self.capability_id
            or call.registry_snapshot_id != self._snapshot_id
        ):
            raise InvalidValidatedCall()
        handler = self._candidate.handler
        if handler is None:
            raise InvalidValidatedCall()
        return await handler.handle(call._input, context)


def _is_immutable_input(value: object) -> bool:
    parameters = getattr(value.__class__, "__dataclass_params__", None)
    if parameters is not None:
        if not bool(parameters.frozen):
            return False
        return all(_is_immutable_input(getattr(value, item.name)) for item in fields(cast(Any, value)))
    if isinstance(value, tuple):
        return all(_is_immutable_input(item) for item in value)
    if isinstance(value, frozenset):
        return all(_is_immutable_input(item) for item in value)
    if isinstance(value, MappingProxyType):
        return all(isinstance(key, str) and _is_immutable_input(item) for key, item in value.items())
    return value is None or isinstance(value, (str, int, float, bool, Decimal, Enum))


class FrozenCapabilityRegistry:
    __slots__ = ("_descriptors", "_registered", "snapshot_id")

    def __init__(
        self,
        *,
        snapshot_id: str,
        descriptors: tuple[CapabilityDescriptor, ...],
        registered: dict[str, RegisteredCapability],
    ) -> None:
        self.snapshot_id = snapshot_id
        self._descriptors = descriptors
        self._registered = MappingProxyType(dict(registered))

    def descriptors(self) -> tuple[CapabilityDescriptor, ...]:
        return self._descriptors

    def resolve(self, capability_id: str) -> RegisteredCapability | None:
        return self._registered.get(capability_id)

    def contains(self, capability_id: str) -> bool:
        return capability_id in self._registered


class CapabilityRegistryBuilder:
    __slots__ = ("_settings",)

    def __init__(self, settings: CoreRuntimeSettings) -> None:
        self._settings = settings

    def build(
        self,
        candidates: Sequence[CapabilityRegistrationCandidate[Any]],
    ) -> FrozenCapabilityRegistry:
        if len(candidates) > self._settings.max_capabilities:
            raise CapabilityRegistryError("registry.too_many_candidates")

        normalized: list[CapabilityRegistrationCandidate[Any]] = []
        identifiers: set[str] = set()
        aliases: set[str] = set()
        for candidate in candidates:
            if not isinstance(candidate, CapabilityRegistrationCandidate):
                raise CapabilityRegistryError("registry.invalid_descriptor")
            candidate_id = (
                candidate.descriptor.capability_id
                if isinstance(candidate.descriptor, CapabilityDescriptor)
                and isinstance(candidate.descriptor.capability_id, str)
                else None
            )
            if type(candidate.enabled) is not bool:
                raise CapabilityRegistryError("registry.invalid_enabled", candidate_id)
            try:
                descriptor = validate_descriptor(
                    candidate.descriptor,
                    max_bytes=self._settings.max_descriptor_bytes,
                    max_depth=self._settings.max_json_depth,
                    max_collection_items=self._settings.max_collection_items,
                )
            except ContractViolation as exc:
                raise CapabilityRegistryError(exc.code, candidate_id) from exc

            if descriptor.capability_id in identifiers:
                raise CapabilityRegistryError("registry.duplicate_id", descriptor.capability_id)
            if descriptor.capability_id in aliases:
                raise CapabilityRegistryError("registry.duplicate_alias", descriptor.capability_id)
            identifiers.add(descriptor.capability_id)
            for alias in descriptor.aliases:
                if alias in aliases or alias in identifiers:
                    raise CapabilityRegistryError("registry.duplicate_alias", descriptor.capability_id)
                aliases.add(alias)

            if candidate.enabled:
                if candidate.argument_validator is None or candidate.handler is None:
                    raise CapabilityRegistryError("registry.enabled_binding_missing", descriptor.capability_id)
                handle = getattr(candidate.handler, "handle", None)
                if handle is None or not inspect.iscoroutinefunction(handle):
                    raise CapabilityRegistryError("registry.enabled_binding_missing", descriptor.capability_id)
            normalized.append(
                CapabilityRegistrationCandidate(
                    descriptor=descriptor,
                    enabled=candidate.enabled,
                    argument_validator=candidate.argument_validator,
                    handler=candidate.handler,
                )
            )

        enabled = sorted((item for item in normalized if item.enabled), key=lambda item: item.descriptor.capability_id)
        canonical_descriptors = tuple(item.descriptor for item in enabled)
        snapshot_material = tuple(descriptor_to_json(item) for item in canonical_descriptors)
        snapshot_id = hashlib.sha256(canonical_json_bytes(snapshot_material)).hexdigest()
        registered = {
            item.descriptor.capability_id: RegisteredCapability(item, snapshot_id)
            for item in enabled
        }
        registry = FrozenCapabilityRegistry(
            snapshot_id=snapshot_id,
            descriptors=canonical_descriptors,
            registered=registered,
        )
        _LOGGER.info(
            "capability_registry_frozen",
            extra={
                "registry_snapshot_prefix": snapshot_id[:12],
                "enabled_capabilities": len(enabled),
                "disabled_capabilities": len(normalized) - len(enabled),
                "capability_api_version": 1,
            },
        )
        return registry
