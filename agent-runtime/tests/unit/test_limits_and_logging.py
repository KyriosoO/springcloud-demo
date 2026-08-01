from __future__ import annotations

import logging

import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.core.execution import CapabilityExecutionCore
from agent_runtime.core.registry import CapabilityRegistryBuilder
from agent_runtime.settings import CoreRuntimeSettings
from tests.helpers import QueryValidator, ResultHandler, candidate, registration, scope, success_result


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_capabilities", 0),
        ("max_descriptor_bytes", 999),
        ("max_question_chars", 16400),
        ("max_json_depth", 17),
        ("max_collection_items", 15),
    ],
)
def test_settings_fail_closed_outside_range(field: str, value: int) -> None:
    with pytest.raises(ValueError, match=f"core.settings_invalid:{field}"):
        CoreRuntimeSettings(**{field: value})


@pytest.mark.asyncio
async def test_logs_and_fingerprint_do_not_depend_on_exception_secret(caplog: pytest.LogCaptureFixture) -> None:
    fingerprints: list[str] = []
    caplog.set_level(logging.WARNING)
    for secret in ("secret-a", "secret-b"):
        handler = ResultHandler(success_result(), exception=RuntimeError(secret))
        registry = CapabilityRegistryBuilder(CoreRuntimeSettings()).build(
            (registration(validator=QueryValidator(), handler=handler),)
        )
        result = await CapabilityExecutionCore(registry, CoreRuntimeSettings()).execute(
            candidate=candidate(),
            scope=scope(question=f"private question {secret}"),
        )
        assert result.status is CapabilityStatus.INTERNAL_FAILURE
        fingerprints.append(str(getattr(caplog.records[-1], "diagnostic_fingerprint")))

    assert fingerprints[0] == fingerprints[1]
    assert "secret-a" not in caplog.text
    assert "secret-b" not in caplog.text
    assert "header.payload.signature" not in caplog.text


@pytest.mark.asyncio
async def test_argument_byte_limit_rejects_before_handler() -> None:
    settings = CoreRuntimeSettings(max_argument_bytes=1024)
    handler = ResultHandler(success_result())
    registry = CapabilityRegistryBuilder(settings).build(
        (registration(validator=QueryValidator(), handler=handler),)
    )
    oversized = candidate(value="x" * 1100)

    result = await CapabilityExecutionCore(registry, settings).execute(
        candidate=oversized,
        scope=scope(),
    )

    assert result.status is CapabilityStatus.INVALID_ARGUMENT
    assert handler.calls == 0
