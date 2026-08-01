from __future__ import annotations

from typing import Any, cast

import pytest

from agent_runtime.capability_api.contracts import CapabilityDescriptor, CapabilityRegistrationCandidate
from agent_runtime.core.registry import CapabilityRegistryBuilder, CapabilityRegistryError
from agent_runtime.settings import CoreRuntimeSettings
from tests.helpers import QueryInput, QueryValidator, ResultHandler, registration, success_result


def _active(
    capability_id: str,
    *,
    aliases: tuple[str, ...] = (),
) -> CapabilityRegistrationCandidate[QueryInput]:
    return registration(
        capability_id=capability_id,
        aliases=aliases,
        validator=QueryValidator(),
        handler=ResultHandler(success_result()),
    )


def test_registry_sorts_freezes_and_hashes_enabled_descriptors() -> None:
    builder = CapabilityRegistryBuilder(CoreRuntimeSettings())
    disabled = registration(capability_id="disabled.query", enabled=False)

    first = builder.build((_active("zeta.query"), disabled, _active("alpha.query")))
    second = builder.build((_active("alpha.query"), _active("zeta.query"), disabled))

    assert tuple(item.capability_id for item in first.descriptors()) == ("alpha.query", "zeta.query")
    assert first.snapshot_id == second.snapshot_id
    assert not first.contains("disabled.query")
    assert first.resolve("disabled.query") is None
    assert not hasattr(first, "register")


def test_empty_enabled_registry_is_valid() -> None:
    registry = CapabilityRegistryBuilder(CoreRuntimeSettings()).build(
        (registration(capability_id="disabled.query", enabled=False),)
    )

    assert registry.descriptors() == ()
    assert len(registry.snapshot_id) == 64


@pytest.mark.parametrize(
    ("candidates", "code"),
    [
        ((_active("same.query"), _active("same.query")), "registry.duplicate_id"),
        (
            (_active("first.query", aliases=("shared",)), _active("second.query", aliases=("shared",))),
            "registry.duplicate_alias",
        ),
    ],
)
def test_registry_rejects_duplicate_identifiers(
    candidates: tuple[CapabilityRegistrationCandidate[QueryInput], ...],
    code: str,
) -> None:
    with pytest.raises(CapabilityRegistryError) as exc_info:
        CapabilityRegistryBuilder(CoreRuntimeSettings()).build(candidates)

    assert exc_info.value.code == code


def test_registry_rejects_enabled_candidate_without_binding() -> None:
    missing = registration(capability_id="missing.query", enabled=False)
    invalid: CapabilityRegistrationCandidate[QueryInput] = CapabilityRegistrationCandidate(
        descriptor=missing.descriptor,
        enabled=True,
        argument_validator=None,
        handler=None,
    )

    with pytest.raises(CapabilityRegistryError, match="registry.enabled_binding_missing"):
        CapabilityRegistryBuilder(CoreRuntimeSettings()).build((invalid,))


def test_registry_rejects_non_boolean_enabled_value() -> None:
    valid = _active("test.query")
    invalid = CapabilityRegistrationCandidate(
        descriptor=valid.descriptor,
        enabled=cast(bool, "false"),
        argument_validator=valid.argument_validator,
        handler=valid.handler,
    )

    with pytest.raises(CapabilityRegistryError, match="registry.invalid_enabled"):
        CapabilityRegistryBuilder(CoreRuntimeSettings()).build((invalid,))


def test_registry_reports_malformed_descriptor_as_controlled_startup_failure() -> None:
    invalid: CapabilityRegistrationCandidate[Any] = CapabilityRegistrationCandidate(
        descriptor=cast(CapabilityDescriptor, object()),
        enabled=False,
        argument_validator=None,
        handler=None,
    )

    with pytest.raises(CapabilityRegistryError) as exc_info:
        CapabilityRegistryBuilder(CoreRuntimeSettings()).build((invalid,))

    assert exc_info.value.code == "registry.invalid_descriptor"
    assert exc_info.value.capability_id is None


@pytest.mark.parametrize(
    "invalid_constraint",
    [
        {"type": "string", "minLength": "1"},
        {"type": "string", "minimum": 1},
        {"type": "array", "items": {"type": "string"}, "minItems": -1},
        {"type": "object", "properties": {}, "additionalProperties": True},
    ],
)
def test_registry_rejects_invalid_schema_constraint_types(invalid_constraint: object) -> None:
    active = _active("schema.query")
    schema = {
        "type": "object",
        "properties": {"value": invalid_constraint},
        "required": ("value",),
        "additionalProperties": False,
    }
    invalid_descriptor = type(active.descriptor)(
        capability_id=active.descriptor.capability_id,
        api_version=active.descriptor.api_version,
        kind=active.descriptor.kind,
        display_name=active.descriptor.display_name,
        description=active.descriptor.description,
        aliases=active.descriptor.aliases,
        argument_schema=schema,  # type: ignore[arg-type]
    )
    invalid = CapabilityRegistrationCandidate(
        descriptor=invalid_descriptor,
        enabled=True,
        argument_validator=active.argument_validator,
        handler=active.handler,
    )

    with pytest.raises(CapabilityRegistryError, match="registry.invalid_argument_schema"):
        CapabilityRegistryBuilder(CoreRuntimeSettings()).build((invalid,))
