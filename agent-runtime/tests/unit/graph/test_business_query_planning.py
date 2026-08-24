from __future__ import annotations

import asyncio
from typing import Any

import pytest

from agent_runtime.business.query_plan import (
    BusinessQueryPlan,
    BusinessQueryPlanValidationResult,
    DefaultBusinessQueryPlanValidator,
    ExactBusinessQueryPlanDecoder,
    ProtectedValueSlots,
    RequestProtectedValueBinder,
    ValidatedBusinessQueryPlan,
)
from agent_runtime.capability_api.contracts import (
    ActionCandidate,
    CancellationSource,
    CapabilityRegistrationCandidate,
    CapabilityStatus,
    JsonObject,
)
from agent_runtime.core.registry import CapabilityRegistryBuilder
from agent_runtime.graph.business_query_planning import (
    BusinessPlanningInput,
    BusinessQueryPlanningNode,
)
from agent_runtime.model.contracts import (
    BusinessQueryPlanTaskInput,
    InvalidModelOutput,
    ModelCallContext,
    ModelInputDenied,
    ModelProviderFailureKind,
    ModelTransportError,
)
from agent_runtime.settings import CoreRuntimeSettings
from tests.query_plan_runtime_helpers import (
    CaptureBusinessHandler,
    business_registration,
    runtime_business_fixture,
)
from tests.helpers import ManualCancellationSignal


class _OrderedGenerator:
    def __init__(self, events: list[str], payload: JsonObject) -> None:
        self._events = events
        self._payload = payload
        self.calls = 0

    async def generate(
        self,
        input: BusinessQueryPlanTaskInput,
        *,
        context: ModelCallContext,
    ) -> JsonObject:
        del input, context
        self.calls += 1
        self._events.append("generate")
        return self._payload


class _OrderedDecoder:
    def __init__(self, events: list[str]) -> None:
        self._events = events
        self._delegate = ExactBusinessQueryPlanDecoder()

    def decode(self, payload: JsonObject) -> BusinessQueryPlan:
        self._events.append("decode")
        return self._delegate.decode(payload)


class _OrderedValidator:
    def __init__(self, events: list[str], definitions: tuple[Any, ...]) -> None:
        self._events = events
        self._delegate = DefaultBusinessQueryPlanValidator(definitions)

    def validate(
        self,
        plan: BusinessQueryPlan,
        *,
        snapshot: Any,
    ) -> BusinessQueryPlanValidationResult:
        self._events.append("plan_validate")
        return self._delegate.validate(plan, snapshot=snapshot)


class _OrderedBinder:
    def __init__(self, events: list[str]) -> None:
        self._events = events
        self._delegate = RequestProtectedValueBinder()

    def bind(
        self,
        plan: ValidatedBusinessQueryPlan,
        *,
        slots: ProtectedValueSlots,
        request_id: str,
    ) -> ActionCandidate:
        self._events.append("bind")
        return self._delegate.bind(plan, slots=slots, request_id=request_id)


class _OrderedArgumentValidator:
    def __init__(self, events: list[str], delegate: Any) -> None:
        self._events = events
        self._delegate = delegate

    def validate(self, arguments: JsonObject) -> object:
        self._events.append("argument_validate")
        return self._delegate.validate(arguments)


class _FailingGenerator:
    def __init__(self, exception: Exception) -> None:
        self._exception = exception
        self.calls = 0

    async def generate(
        self,
        input: BusinessQueryPlanTaskInput,
        *,
        context: ModelCallContext,
    ) -> JsonObject:
        del input, context
        self.calls += 1
        raise self._exception


def _planning_input(
    *,
    snapshot: Any,
    expired: bool = False,
    cancellation: ManualCancellationSignal | None = None,
) -> BusinessPlanningInput:
    deadline = asyncio.get_running_loop().time() + (-1.0 if expired else 10.0)
    return BusinessPlanningInput(
        request_id="request-1",
        minimized_question="查询员工，员工标识 protected-ref(slot-1)",
        protected_slots=ProtectedValueSlots(
            request_id="request-1",
            values={"slot-1": "ABCDE"},
        ),
        config_snapshot=snapshot,
        model_context=ModelCallContext(
            request_id="request-1",
            correlation_id="correlation-1",
            deadline_monotonic=deadline,
        ),
        cancellation=cancellation or ManualCancellationSignal(),
    )


@pytest.mark.asyncio
async def test_planning_node_executes_exact_order_before_returning_candidate() -> None:
    fixture = runtime_business_fixture()
    employee = fixture.definitions[0]
    events: list[str] = []
    handler = CaptureBusinessHandler()
    registration = CapabilityRegistrationCandidate[Any](
        descriptor=employee.descriptor,
        enabled=True,
        argument_validator=_OrderedArgumentValidator(events, employee.argument_validator),
        handler=handler,
    )
    registry = CapabilityRegistryBuilder(CoreRuntimeSettings()).build((registration,))
    generator = _OrderedGenerator(
        events,
        {
            "domain": "employee",
            "action": "employee.detail",
            "arguments": {"employee_identifier": {"value_ref": "slot-1"}},
        },
    )
    node = BusinessQueryPlanningNode(
        generator=generator,
        decoder=_OrderedDecoder(events),
        validator=_OrderedValidator(events, fixture.definitions),
        binder=_OrderedBinder(events),
        registry=registry,
        planner_catalog=fixture.catalog,
    )

    decision = await node(_planning_input(snapshot=fixture.snapshot))

    assert decision.status is None
    assert decision.candidate is not None
    assert decision.candidate.capability_id == "employee.detail"
    assert decision.candidate.arguments == {"employee_identifier": "ABCDE"}
    assert events == ["generate", "decode", "plan_validate", "bind", "argument_validate"]
    assert handler.calls == 0


@pytest.mark.asyncio
async def test_unsupported_plan_stops_before_binder_registry_and_handler() -> None:
    fixture = runtime_business_fixture()
    handler = CaptureBusinessHandler()
    registry = CapabilityRegistryBuilder(CoreRuntimeSettings()).build(
        (business_registration(fixture.definitions[0], handler),)
    )
    node = BusinessQueryPlanningNode(
        generator=_OrderedGenerator(
            [],
            {"domain": "unsupported", "action": "unsupported", "arguments": {}},
        ),
        decoder=ExactBusinessQueryPlanDecoder(),
        validator=DefaultBusinessQueryPlanValidator(fixture.definitions),
        binder=RequestProtectedValueBinder(),
        registry=registry,
        planner_catalog=fixture.catalog,
    )

    decision = await node(_planning_input(snapshot=fixture.snapshot))

    assert decision.status is CapabilityStatus.UNSUPPORTED
    assert decision.failure_code == "business.plan_unsupported"
    assert decision.candidate is None
    assert handler.calls == 0


@pytest.mark.asyncio
async def test_missing_protected_value_ref_has_the_fixed_failure_code_and_zero_handler_calls() -> None:
    fixture = runtime_business_fixture()
    handler = CaptureBusinessHandler()
    registry = CapabilityRegistryBuilder(CoreRuntimeSettings()).build(
        (business_registration(fixture.definitions[0], handler),)
    )
    node = BusinessQueryPlanningNode(
        generator=_OrderedGenerator(
            [],
            {
                "domain": "employee",
                "action": "employee.detail",
                "arguments": {"employee_identifier": {"value_ref": "slot-2"}},
            },
        ),
        decoder=ExactBusinessQueryPlanDecoder(),
        validator=DefaultBusinessQueryPlanValidator(fixture.definitions),
        binder=RequestProtectedValueBinder(),
        registry=registry,
        planner_catalog=fixture.catalog,
    )

    decision = await node(_planning_input(snapshot=fixture.snapshot))

    assert decision.status is CapabilityStatus.INVALID_ARGUMENT
    assert decision.failure_code == "business.protected_value_invalid"
    assert decision.candidate is None
    assert handler.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception", "status", "code"),
    (
        (
            ModelTransportError(ModelProviderFailureKind.PROVIDER_TIMEOUT),
            CapabilityStatus.TIMEOUT,
            "business.plan_model_timeout",
        ),
        (
            ModelTransportError(ModelProviderFailureKind.PROVIDER_FAILURE),
            CapabilityStatus.DOWNSTREAM_FAILURE,
            "business.plan_model_failure",
        ),
        (
            InvalidModelOutput("model.invalid_output"),
            CapabilityStatus.INVALID_ARGUMENT,
            "business.plan_invalid",
        ),
        (
            ModelInputDenied("model.input_denied"),
            CapabilityStatus.FORBIDDEN,
            "business.plan_model_denied",
        ),
    ),
)
async def test_model_or_output_failure_is_terminal_before_core(
    exception: Exception,
    status: CapabilityStatus,
    code: str,
) -> None:
    fixture = runtime_business_fixture()
    handler = CaptureBusinessHandler()
    registry = CapabilityRegistryBuilder(CoreRuntimeSettings()).build(
        (business_registration(fixture.definitions[0], handler),)
    )
    node = BusinessQueryPlanningNode(
        generator=_FailingGenerator(exception),
        decoder=ExactBusinessQueryPlanDecoder(),
        validator=DefaultBusinessQueryPlanValidator(fixture.definitions),
        binder=RequestProtectedValueBinder(),
        registry=registry,
        planner_catalog=fixture.catalog,
    )

    decision = await node(_planning_input(snapshot=fixture.snapshot))

    assert decision.status is status
    assert decision.failure_code == code
    assert decision.candidate is None
    assert handler.calls == 0


@pytest.mark.asyncio
async def test_expired_or_cross_request_context_stops_before_model() -> None:
    fixture = runtime_business_fixture()
    handler = CaptureBusinessHandler()
    registry = CapabilityRegistryBuilder(CoreRuntimeSettings()).build(
        (business_registration(fixture.definitions[0], handler),)
    )
    generator = _OrderedGenerator([], {})
    node = BusinessQueryPlanningNode(
        generator=generator,
        decoder=ExactBusinessQueryPlanDecoder(),
        validator=DefaultBusinessQueryPlanValidator(fixture.definitions),
        binder=RequestProtectedValueBinder(),
        registry=registry,
        planner_catalog=fixture.catalog,
    )

    expired = await node(_planning_input(snapshot=fixture.snapshot, expired=True))
    base = _planning_input(snapshot=fixture.snapshot)
    mismatch = await node(
        BusinessPlanningInput(
            request_id="request-2",
            minimized_question=base.minimized_question,
            protected_slots=base.protected_slots,
            config_snapshot=base.config_snapshot,
            model_context=base.model_context,
            cancellation=base.cancellation,
        )
    )

    assert expired.status is CapabilityStatus.TIMEOUT
    assert mismatch.status is CapabilityStatus.INTERNAL_FAILURE
    assert generator.calls == 0
    assert handler.calls == 0


@pytest.mark.asyncio
async def test_request_signal_cancellation_discards_late_model_result_before_decode() -> None:
    fixture = runtime_business_fixture()
    handler = CaptureBusinessHandler()
    registry = CapabilityRegistryBuilder(CoreRuntimeSettings()).build(
        (business_registration(fixture.definitions[0], handler),)
    )
    signal = ManualCancellationSignal()
    release = asyncio.Event()
    events: list[str] = []

    class _LateGenerator:
        async def generate(
            self,
            input: BusinessQueryPlanTaskInput,
            *,
            context: ModelCallContext,
        ) -> JsonObject:
            del input, context
            events.append("generate")
            await release.wait()
            return {
                "domain": "employee",
                "action": "employee.detail",
                "arguments": {"employee_identifier": {"value_ref": "slot-1"}},
            }

    node = BusinessQueryPlanningNode(
        generator=_LateGenerator(),
        decoder=_OrderedDecoder(events),
        validator=_OrderedValidator(events, fixture.definitions),
        binder=_OrderedBinder(events),
        registry=registry,
        planner_catalog=fixture.catalog,
    )
    running = asyncio.create_task(
        node(_planning_input(snapshot=fixture.snapshot, cancellation=signal))
    )
    await asyncio.sleep(0)
    signal.cancel(CancellationSource.CLIENT_DISCONNECT)
    release.set()

    decision = await running

    assert decision.status is CapabilityStatus.TIMEOUT
    assert events == ["generate"]
    assert handler.calls == 0


@pytest.mark.asyncio
async def test_deadline_expiry_discards_late_model_result_before_decode() -> None:
    fixture = runtime_business_fixture()
    handler = CaptureBusinessHandler()
    registry = CapabilityRegistryBuilder(CoreRuntimeSettings()).build(
        (business_registration(fixture.definitions[0], handler),)
    )
    events: list[str] = []

    class _LateGenerator:
        async def generate(
            self,
            input: BusinessQueryPlanTaskInput,
            *,
            context: ModelCallContext,
        ) -> JsonObject:
            del input, context
            events.append("generate")
            await asyncio.sleep(0.02)
            return {
                "domain": "employee",
                "action": "employee.detail",
                "arguments": {"employee_identifier": {"value_ref": "slot-1"}},
            }

    node = BusinessQueryPlanningNode(
        generator=_LateGenerator(),
        decoder=_OrderedDecoder(events),
        validator=_OrderedValidator(events, fixture.definitions),
        binder=_OrderedBinder(events),
        registry=registry,
        planner_catalog=fixture.catalog,
    )
    input = _planning_input(snapshot=fixture.snapshot)
    late_input = BusinessPlanningInput(
        request_id=input.request_id,
        minimized_question=input.minimized_question,
        protected_slots=input.protected_slots,
        config_snapshot=input.config_snapshot,
        model_context=ModelCallContext(
            request_id=input.model_context.request_id,
            correlation_id=input.model_context.correlation_id,
            deadline_monotonic=asyncio.get_running_loop().time() + 0.005,
        ),
        cancellation=input.cancellation,
    )

    decision = await node(late_input)

    assert decision.status is CapabilityStatus.TIMEOUT
    assert events == ["generate"]
    assert handler.calls == 0
