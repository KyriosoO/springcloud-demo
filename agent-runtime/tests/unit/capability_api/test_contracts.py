from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from agent_runtime.capability_api.contracts import (
    ActionCandidate,
    CapabilityResult,
    CapabilityStatus,
    ContractViolation,
    EgressDisposition,
    ModelEgressResult,
    OpaqueUserToken,
    canonical_json_bytes,
    freeze_json_object,
    validate_capability_result,
)
from agent_runtime.core.registry import CapabilityRegistryBuilder, InvalidValidatedCall
from agent_runtime.settings import CoreRuntimeSettings
from tests.helpers import QueryValidator, ResultHandler, descriptor, registration, scope, success_result


def test_json_contract_freezes_nested_values_and_is_canonical() -> None:
    raw = {"z": [1, {"b": True}], "a": "value"}
    frozen = freeze_json_object(raw, max_bytes=1024, max_depth=8, max_collection_items=16)

    assert isinstance(frozen["z"], tuple)
    assert canonical_json_bytes(frozen) == b'{"a":"value","z":[1,{"b":true}]}'
    with pytest.raises(TypeError):
        frozen["new"] = "forbidden"  # type: ignore[index]


@pytest.mark.parametrize("invalid", [math.nan, math.inf, b"secret", object()])
def test_json_contract_rejects_non_json_values(invalid: object) -> None:
    with pytest.raises(ContractViolation):
        ActionCandidate(capability_id="test.query", arguments={"value": invalid})  # type: ignore[dict-item]


def test_token_never_exposes_raw_value_in_string_or_hash() -> None:
    token = OpaqueUserToken.from_raw("sensitive-token")

    assert str(token) == "<redacted>"
    assert repr(token) == "<redacted>"
    assert token.reveal_for_outbound() == "sensitive-token"
    with pytest.raises(TypeError):
        hash(token)


def test_descriptor_is_frozen_and_schema_is_strict() -> None:
    value = descriptor()

    with pytest.raises(FrozenInstanceError):
        value.capability_id = "other.query"  # type: ignore[misc]
    assert value.argument_schema["additionalProperties"] is False


def test_result_contract_rejects_allowed_without_safe_payload() -> None:
    result = CapabilityResult(
        status=CapabilityStatus.SUCCESS,
        domain_result={"value": "result"},
        egress=ModelEgressResult(
            disposition=EgressDisposition.ALLOWED,
            policy_version="v1",
        ),
        failure=None,
    )

    with pytest.raises(ContractViolation, match="core.invalid_result"):
        validate_capability_result(
            result,
            max_domain_result_bytes=262144,
            max_model_payload_bytes=65536,
            max_json_depth=8,
            max_collection_items=256,
        )


@pytest.mark.asyncio
async def test_validated_call_cannot_cross_registered_capability_boundary() -> None:
    first = registration(
        capability_id="first.query",
        validator=QueryValidator(),
        handler=ResultHandler(success_result()),
    )
    second = registration(
        capability_id="second.query",
        validator=QueryValidator(),
        handler=ResultHandler(success_result()),
    )
    registry = CapabilityRegistryBuilder(CoreRuntimeSettings()).build((first, second))
    first_registered = registry.resolve("first.query")
    second_registered = registry.resolve("second.query")
    assert first_registered is not None and second_registered is not None
    call = first_registered.validate(ActionCandidate(capability_id="first.query", arguments={"value": "x"}).arguments)

    with pytest.raises(InvalidValidatedCall):
        await second_registered.invoke(call, scope().context)
