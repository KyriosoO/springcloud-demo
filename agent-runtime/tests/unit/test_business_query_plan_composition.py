from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from typing import cast

import pytest

from agent_runtime.adapters.employee.protected_input import EmployeeProtectedValueExtractor
from agent_runtime.adapters.employee.contracts import EmployeeDetailInput
from agent_runtime.adapters.transaction.protected_input import TransactionProtectedValueExtractor
from agent_runtime.bootstrap import RuntimeCompositionRoot
from agent_runtime.business.planner_catalog import BusinessPlannerCatalog
from agent_runtime.business.protected_input import CompositeBusinessProtectedValueExtractor
from agent_runtime.business.settings import BusinessConfigurationSnapshot
from agent_runtime.capability_api.action_resolution import (
    LocalActionResolution,
    LocalActionResolutionKind,
)
from agent_runtime.capability_api.contracts import (
    CapabilityDescriptor,
    CapabilityKind,
    CapabilityRegistrationCandidate,
    CapabilityStatus,
    JsonObject,
    CancellationSource,
    freeze_json_object,
)
from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.graph.action_resolution import (
    CapabilitySelectionDecision,
    CapabilitySelectionDecisionKind,
)
from agent_runtime.graph.business_query_planning import BusinessQueryPlanRuntimeBindings
from agent_runtime.graph.state import AnswerGenerationDecision, AnswerGenerationDecisionKind
from agent_runtime.model.context import ModelCallContextAccessor, ModelContextBindingRuntimeInvoker
from agent_runtime.model.contracts import (
    BusinessQueryPlanGenerator,
    BusinessQueryPlanTaskInput,
    ModelCallContext,
)
from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.settings import CoreRuntimeSettings
from tests.helpers import (
    FixedAnswerGenerator,
    FixedLocalActionResolver,
    FixedSelector,
    ManualCancellationSignal,
    Provider,
    scope,
    success_result,
)
from tests.query_plan_runtime_helpers import (
    CaptureBusinessHandler,
    business_registration,
    runtime_business_fixture,
)


class _QuestionPlanGenerator:
    def __init__(self) -> None:
        self.calls = 0
        self.inputs: list[BusinessQueryPlanTaskInput] = []
        self.contexts: list[ModelCallContext] = []

    async def generate(
        self,
        input: BusinessQueryPlanTaskInput,
        *,
        context: ModelCallContext,
    ) -> JsonObject:
        self.calls += 1
        self.inputs.append(input)
        self.contexts.append(context)
        await asyncio.sleep(0)
        if "员工" in input.minimized_question:
            return {
                "domain": "employee",
                "action": "employee.detail",
                "arguments": {"employee_identifier": {"value_ref": "slot-1"}},
            }
        return {
            "domain": "transaction",
            "action": "transaction.search",
            "arguments": {"trans_type": {"literal": "PAYMENT"}},
        }


class _FixedPlanGenerator:
    def __init__(self, payload: JsonObject) -> None:
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
        return self._payload


@dataclass(frozen=True, slots=True)
class _EmptyInput:
    pass


class _EmptyValidator:
    def validate(self, arguments: JsonObject) -> _EmptyInput:
        if arguments:
            raise ValueError("test.arguments_not_empty")
        return _EmptyInput()


def _answer() -> FixedAnswerGenerator:
    return FixedAnswerGenerator(
        AnswerGenerationDecision(
            kind=AnswerGenerationDecisionKind.ANSWER,
            answer_text="unused",
        )
    )


def _unsupported_selector() -> FixedSelector:
    return FixedSelector(
        CapabilitySelectionDecision(
            kind=CapabilitySelectionDecisionKind.UNSUPPORTED,
        )
    )


def _bindings(
    generator: BusinessQueryPlanGenerator,
    *,
    catalog: BusinessPlannerCatalog | None = None,
    snapshot: BusinessConfigurationSnapshot | None = None,
) -> BusinessQueryPlanRuntimeBindings:
    fixture = runtime_business_fixture()
    return BusinessQueryPlanRuntimeBindings(
        definitions=fixture.definitions,
        snapshot=snapshot or fixture.snapshot,
        planner_catalog=catalog or fixture.catalog,
        generator=generator,
        context_accessor=ModelCallContextAccessor(),
        protected_value_extractor=CompositeBusinessProtectedValueExtractor(
            (EmployeeProtectedValueExtractor(), TransactionProtectedValueExtractor())
        ),
        guard=QuestionEgressGuard(),
    )


def _runtime(
    generator: BusinessQueryPlanGenerator,
    *,
    selector: FixedSelector | None = None,
    extra_providers: tuple[Provider, ...] = (),
    local_resolvers: tuple[FixedLocalActionResolver, ...] = (),
) -> tuple[
    ModelContextBindingRuntimeInvoker,
    CaptureBusinessHandler,
    CaptureBusinessHandler,
    FixedSelector,
]:
    fixture = runtime_business_fixture()
    employee_handler = CaptureBusinessHandler()
    transaction_handler = CaptureBusinessHandler()
    fallback = selector or _unsupported_selector()
    runtime = RuntimeCompositionRoot.build(
        settings=CoreRuntimeSettings(),
        providers=(
            Provider(
                business_registration(fixture.definitions[0], employee_handler),
                business_registration(fixture.definitions[1], transaction_handler),
            ),
            *extra_providers,
        ),
        capability_selector=fallback,
        answer_generator=_answer(),
        local_action_resolvers=local_resolvers,
        business_query_plan=_bindings(generator),
    )
    return (
        ModelContextBindingRuntimeInvoker(runtime),
        employee_handler,
        transaction_handler,
        fallback,
    )


@pytest.mark.asyncio
async def test_employee_and_transaction_use_query_plan_and_execute_one_action() -> None:
    generator = _QuestionPlanGenerator()
    runtime, employee, transaction, fallback = _runtime(generator)

    employee_outcome = await runtime.ainvoke(
        question="查询员工，员工标识 ABCDE",
        scope=scope("查询员工，员工标识 ABCDE"),
    )
    transaction_outcome = await runtime.ainvoke(
        question="查询交易类型 PAYMENT",
        scope=scope("查询交易类型 PAYMENT"),
    )

    assert employee_outcome.status is CapabilityStatus.SUCCESS
    assert employee_outcome.capability_id == "employee.detail"
    assert transaction_outcome.status is CapabilityStatus.SUCCESS
    assert transaction_outcome.capability_id == "transaction.search"
    assert generator.calls == 2
    assert employee.calls == 1
    assert transaction.calls == 1
    assert fallback.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "status"),
    (
        (
            {"domain": "unsupported", "action": "unsupported", "arguments": {}},
            CapabilityStatus.UNSUPPORTED,
        ),
        (
            {
                "domain": "employee",
                "action": "employee.detail",
                "arguments": {"employee_identifier": {"literal": "ABCDE"}},
            },
            CapabilityStatus.INVALID_ARGUMENT,
        ),
        (
            {
                "domain": "knowledge",
                "action": "knowledge.query",
                "arguments": {},
            },
            CapabilityStatus.UNSUPPORTED,
        ),
    ),
)
async def test_unsupported_invalid_or_cross_domain_plan_has_zero_fallback_and_handler_calls(
    payload: JsonObject,
    status: CapabilityStatus,
) -> None:
    runtime, employee, transaction, fallback = _runtime(_FixedPlanGenerator(payload))

    outcome = await runtime.ainvoke(
        question="查询员工，员工标识 ABCDE",
        scope=scope("查询员工，员工标识 ABCDE"),
    )

    assert outcome.status is status
    assert employee.calls == 0
    assert transaction.calls == 0
    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_invalid_business_input_does_not_fall_back_to_non_business_selector() -> None:
    generator = _QuestionPlanGenerator()
    runtime, employee, transaction, fallback = _runtime(generator)
    question = "查询员工\x00详情"

    outcome = await runtime.ainvoke(question=question, scope=scope(question))

    assert outcome.status is CapabilityStatus.INVALID_ARGUMENT
    assert generator.calls == 0
    assert employee.calls == 0
    assert transaction.calls == 0
    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_sensitive_business_input_is_forbidden_without_model_or_fallback() -> None:
    generator = _QuestionPlanGenerator()
    runtime, employee, transaction, fallback = _runtime(generator)
    question = "查询员工，员工标识 ABCDE，联系电话 13800138000"

    outcome = await runtime.ainvoke(question=question, scope=scope(question))

    assert outcome.status is CapabilityStatus.FORBIDDEN
    assert outcome.failure is not None
    assert outcome.failure.code == "business.plan_input_denied"
    assert generator.calls == 0
    assert employee.calls == 0
    assert transaction.calls == 0
    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_non_business_fallback_catalog_excludes_business_descriptors() -> None:
    knowledge_handler = CaptureBusinessHandler(success_result())
    knowledge_registration = CapabilityRegistrationCandidate[_EmptyInput](
        descriptor=CapabilityDescriptor(
            capability_id="knowledge.query",
            api_version=1,
            kind=CapabilityKind.QUERY,
            display_name="Knowledge query",
            description="Query bounded public policy knowledge.",
            aliases=("knowledge",),
            argument_schema={
                "type": "object",
                "properties": {},
                "required": (),
                "additionalProperties": False,
            },
        ),
        enabled=True,
        argument_validator=_EmptyValidator(),
        handler=knowledge_handler,
    )
    selector = FixedSelector(
        CapabilitySelectionDecision(
            kind=CapabilitySelectionDecisionKind.CANDIDATE,
            capability_id="knowledge.query",
        )
    )
    generator = _QuestionPlanGenerator()
    runtime, employee, transaction, fallback = _runtime(
        generator,
        selector=selector,
        extra_providers=(Provider(knowledge_registration),),
    )

    outcome = await runtime.ainvoke(
        question="现行税务政策是什么",
        scope=scope("现行税务政策是什么"),
    )

    assert outcome.status is CapabilityStatus.SUCCESS
    assert outcome.capability_id == "knowledge.query"
    assert generator.calls == 0
    assert employee.calls == 0
    assert transaction.calls == 0
    assert fallback.calls == 1
    assert tuple(item.capability_id for item in fallback.inputs[0].descriptors) == (
        "knowledge.query",
    )


@pytest.mark.asyncio
async def test_cancelled_non_business_request_preserves_fallback_routing() -> None:
    signal = ManualCancellationSignal()
    signal.cancel(CancellationSource.CLIENT_DISCONNECT)
    generator = _QuestionPlanGenerator()
    runtime, employee, transaction, fallback = _runtime(generator)
    question = "现行税务政策是什么"

    outcome = await runtime.ainvoke(
        question=question,
        scope=scope(question, cancellation=signal),
    )

    assert outcome.status is CapabilityStatus.UNSUPPORTED
    assert generator.calls == 0
    assert employee.calls == 0
    assert transaction.calls == 0
    assert fallback.calls == 1


@pytest.mark.asyncio
async def test_concurrent_protected_slots_remain_request_local() -> None:
    generator = _QuestionPlanGenerator()
    runtime, employee, transaction, fallback = _runtime(generator)
    first_question = "查询员工，员工标识 EMP-A"
    second_question = "查询员工，员工标识 EMP-B"
    first_scope = RequestExecutionScope(context=replace(
        scope(first_question).context,
        request_id="request-a",
        correlation_id="correlation-a",
    ))
    second_scope = RequestExecutionScope(context=replace(
        scope(second_question).context,
        request_id="request-b",
        correlation_id="correlation-b",
    ))

    outcomes = await asyncio.gather(
        runtime.ainvoke(
            question=first_question,
            scope=first_scope,
        ),
        runtime.ainvoke(
            question=second_question,
            scope=second_scope,
        ),
    )

    assert all(item.status is CapabilityStatus.SUCCESS for item in outcomes)
    assert all(isinstance(item, EmployeeDetailInput) for item in employee.inputs)
    assert {
        item.employee_identifier
        for item in employee.inputs
        if isinstance(item, EmployeeDetailInput)
    } == {"EMP-A", "EMP-B"}
    assert {context.request_id for context in employee.contexts} == {"request-a", "request-b"}
    assert transaction.calls == 0
    assert fallback.calls == 0


def test_startup_rejects_catalog_registry_or_business_resolver_mismatch() -> None:
    fixture = runtime_business_fixture()
    handlers = (CaptureBusinessHandler(), CaptureBusinessHandler())
    providers = (
        Provider(
            business_registration(fixture.definitions[0], handlers[0]),
            business_registration(fixture.definitions[1], handlers[1]),
        ),
    )
    generator = _QuestionPlanGenerator()
    bad_catalog = BusinessPlannerCatalog(
        snapshot_id="mismatch-v1",
        payload=fixture.catalog.payload,
    )
    with pytest.raises(ValueError, match="business.plan_composition_invalid"):
        RuntimeCompositionRoot.build(
            settings=CoreRuntimeSettings(),
            providers=providers,
            capability_selector=_unsupported_selector(),
            answer_generator=_answer(),
            business_query_plan=_bindings(generator, catalog=bad_catalog),
        )
    catalog_actions = cast(
        tuple[JsonObject, ...],
        fixture.catalog.payload["actions"],
    )
    drifted_actions: list[JsonObject] = []
    for action in catalog_actions:
        drifted_action = dict(action)
        if action["action"] == "transaction.search":
            limits = cast(JsonObject, action["limits"])
            drifted_action["limits"] = {**limits, "max_page_size": 999}
        drifted_actions.append(drifted_action)
    drifted_payload = dict(fixture.catalog.payload)
    drifted_payload["actions"] = tuple(drifted_actions)
    drifted_catalog = BusinessPlannerCatalog(
        snapshot_id=fixture.catalog.snapshot_id,
        payload=freeze_json_object(
            drifted_payload,
            max_bytes=32768,
            max_depth=8,
            max_collection_items=256,
        ),
    )
    with pytest.raises(ValueError, match="business.plan_composition_invalid"):
        RuntimeCompositionRoot.build(
            settings=CoreRuntimeSettings(),
            providers=providers,
            capability_selector=_unsupported_selector(),
            answer_generator=_answer(),
            business_query_plan=_bindings(generator, catalog=drifted_catalog),
        )
    with pytest.raises(ValueError, match="business.plan_composition_invalid"):
        RuntimeCompositionRoot.build(
            settings=CoreRuntimeSettings(),
            providers=(Provider(business_registration(fixture.definitions[0], handlers[0])),),
            capability_selector=_unsupported_selector(),
            answer_generator=_answer(),
            business_query_plan=_bindings(generator),
        )
    reduced_snapshot = replace(
        fixture.snapshot,
        actions=(fixture.snapshot.actions[0],),
    )
    with pytest.raises(ValueError, match="business.plan_composition_invalid"):
        RuntimeCompositionRoot.build(
            settings=CoreRuntimeSettings(),
            providers=providers,
            capability_selector=_unsupported_selector(),
            answer_generator=_answer(),
            business_query_plan=_bindings(generator, snapshot=reduced_snapshot),
        )
    mismatched_employee = replace(
        business_registration(fixture.definitions[0], handlers[0]),
        descriptor=replace(
            fixture.definitions[0].descriptor,
            description="Different model-safe description.",
        ),
    )
    with pytest.raises(ValueError, match="business.plan_composition_invalid"):
        RuntimeCompositionRoot.build(
            settings=CoreRuntimeSettings(),
            providers=(
                Provider(
                    mismatched_employee,
                    business_registration(fixture.definitions[1], handlers[1]),
                ),
            ),
            capability_selector=_unsupported_selector(),
            answer_generator=_answer(),
            business_query_plan=_bindings(generator),
        )
    with pytest.raises(ValueError, match="runtime.local_action_resolver_not_enabled"):
        RuntimeCompositionRoot.build(
            settings=CoreRuntimeSettings(),
            providers=providers,
            capability_selector=_unsupported_selector(),
            answer_generator=_answer(),
            local_action_resolvers=(
                FixedLocalActionResolver(
                    "employee.detail",
                    LocalActionResolution(
                        kind=LocalActionResolutionKind.CANDIDATE,
                        arguments={"employee_identifier": "ABCDE"},
                    ),
                ),
            ),
            business_query_plan=_bindings(generator),
        )


@pytest.mark.asyncio
async def test_cancelled_business_request_has_zero_model_fallback_and_handler_calls() -> None:
    generator = _QuestionPlanGenerator()
    runtime, employee, transaction, fallback = _runtime(generator)
    signal = ManualCancellationSignal()
    signal.cancel(CancellationSource.CLIENT_DISCONNECT)
    question = "查询员工，员工标识 ABCDE"

    outcome = await runtime.ainvoke(
        question=question,
        scope=scope(question, cancellation=signal),
    )

    assert outcome.status is CapabilityStatus.TIMEOUT
    assert generator.calls == 0
    assert employee.calls == 0
    assert transaction.calls == 0
    assert fallback.calls == 0
