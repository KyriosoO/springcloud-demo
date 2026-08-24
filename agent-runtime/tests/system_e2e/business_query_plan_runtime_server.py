from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import uvicorn

from agent_runtime.adapters.employee.protected_input import EmployeeProtectedValueExtractor
from agent_runtime.adapters.employee.provider import EmployeeDomainProvider
from agent_runtime.adapters.employee.settings import EmployeeAdapterSettings
from agent_runtime.adapters.transaction.protected_input import TransactionProtectedValueExtractor
from agent_runtime.adapters.transaction.provider import TransactionDomainProvider
from agent_runtime.adapters.transaction.settings import TransactionAdapterSettings
from agent_runtime.api.app import create_app
from agent_runtime.api.settings import RuntimeHttpSettings
from agent_runtime.bootstrap import LocalModelCompositionRoot, RuntimeCompositionRoot
from agent_runtime.business.contracts import BusinessServiceKey
from agent_runtime.business.egress import BusinessEgressProjector
from agent_runtime.business.handler import BoundBusinessActionHandler
from agent_runtime.business.http_client import (
    FakeDomainHttpRequest,
    FakeDomainHttpResponse,
    UserJwtBusinessHttpClient,
)
from agent_runtime.business.protected_input import CompositeBusinessProtectedValueExtractor
from agent_runtime.business.provider import BusinessSupportFactory
from agent_runtime.business.settings import (
    BusinessConfigurationSource,
    BusinessGlobalSettings,
    BusinessServiceBinding,
    GlobalBusinessEgressPolicy,
)
from agent_runtime.business.user_projection import BusinessUserResultProjector
from agent_runtime.capability_api.contracts import CapabilityRegistrationCandidate
from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.graph.action_resolution import (
    CapabilitySelectionDecision,
    CapabilitySelectionDecisionKind,
    CapabilitySelectionInput,
)
from agent_runtime.graph.business_query_planning import BusinessQueryPlanRuntimeBindings
from agent_runtime.graph.state import AgentSemanticOutcome, AnswerGenerationInput
from agent_runtime.model.contracts import (
    ModelTaskId,
    StructuredFinishKind,
    StructuredModelRequest,
    StructuredModelResponse,
)
from agent_runtime.model.context import ModelContextBindingRuntimeInvoker
from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.model.settings import ModelSettings
from agent_runtime.settings import CoreRuntimeSettings
from tests.system_e2e.business_query_plan_evidence import write_business_query_plan_evidence


_SAFE_CASE_ID = re.compile(r"bq-nonlive-[a-z0-9-]{1,40}")
_AMOUNT = re.compile(r"金额\s*(?:为|是|=|:|：|大于|>)\s*(-?[0-9]+(?:\.[0-9]+)?)")


class _StaticProvider:
    def __init__(self, *registrations: CapabilityRegistrationCandidate[Any]) -> None:
        self._registrations = tuple(registrations)

    def registrations(self) -> tuple[CapabilityRegistrationCandidate[Any], ...]:
        return self._registrations


class _ForbiddenFallbackSelector:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, input: CapabilitySelectionInput) -> CapabilitySelectionDecision:
        del input
        self.calls += 1
        return CapabilitySelectionDecision(kind=CapabilitySelectionDecisionKind.UNSUPPORTED)


class _ForbiddenAnswerGenerator:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, input: AnswerGenerationInput) -> Any:
        del input
        self.calls += 1
        raise AssertionError("business_query_plan_e2e.answer_generation_forbidden")


class _FakeBusinessQueryPlanTransport:
    def __init__(self) -> None:
        self.query_plan_calls = 0
        self.other_task_calls = 0

    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        if call_deadline <= asyncio.get_running_loop().time():
            raise TimeoutError("business_query_plan_e2e.deadline")
        if request.task_id is not ModelTaskId.BUSINESS_QUERY_PLAN:
            self.other_task_calls += 1
            raise AssertionError("business_query_plan_e2e.other_model_task_forbidden")
        self.query_plan_calls += 1
        payload = json.loads(request.user_payload_json)
        if type(payload) is not dict or type(payload.get("question")) is not str:
            raise AssertionError("business_query_plan_e2e.model_payload_invalid")
        question = payload["question"]
        if "模型超时" in question:
            raise TimeoutError("business_query_plan_e2e.synthetic_timeout")
        if "第二动作" in question:
            content = '{"domain":"employee","action":"employee.detail","arguments":{},"second_action":"transaction.search"}'
        elif "跨域计划" in question:
            content = '{"domain":"employee","action":"transaction.search","arguments":{"amount":{"literal":"1.00"}}}'
        elif "员工" in question or "employee" in question.casefold():
            if "工作地" in question or "列表" in question:
                content = '{"domain":"employee","action":"unsupported","arguments":{}}'
            elif "protected-ref(slot-1)" in question:
                content = '{"domain":"employee","action":"employee.detail","arguments":{"employee_identifier":{"value_ref":"slot-1"}}}'
            else:
                content = '{"domain":"employee","action":"unsupported","arguments":{}}'
        elif "交易" in question or "transaction" in question.casefold():
            match = _AMOUNT.search(question)
            amount = match.group(1) if match is not None else "1.00"
            content = json.dumps(
                {
                    "domain": "transaction",
                    "action": "transaction.search",
                    "arguments": {"amount": {"literal": amount}},
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        else:
            content = '{"domain":"unsupported","action":"unsupported","arguments":{}}'
        return StructuredModelResponse(
            finish_kind=StructuredFinishKind.STOP,
            content=content,
            tool_calls=(),
            usage_total_tokens=0,
        )


class _FakeBusinessDomainTransport:
    def __init__(self, *, domain: str, admin_token: str) -> None:
        if domain not in {"employee", "transaction"} or not admin_token:
            raise ValueError("business_query_plan_e2e.domain_transport_invalid")
        self._domain = domain
        self._admin_authorization = f"Bearer {admin_token}"
        self.calls = 0
        self.other_endpoint_calls = 0

    async def send(self, outbound: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        request = outbound.request
        expected = (
            request.method == "GET"
            and request.relative_path == "/employees/ABCDE"
            and request.query == ()
            and request.json_body is None
            if self._domain == "employee"
            else request.method == "POST"
            and request.relative_path == "/txn/search"
            and request.query == ()
            and request.json_body is not None
        )
        if not expected:
            self.other_endpoint_calls += 1
            return FakeDomainHttpResponse(status_code=404, content_type="application/json", body=b"{}")
        self.calls += 1
        if outbound.authorization != self._admin_authorization:
            return FakeDomainHttpResponse(status_code=403, content_type="application/json", body=b"{}")
        if self._domain == "employee":
            body: dict[str, object] = {
                "idCardNo": "ABCDE",
                "memberNo": "MEM01",
                "chineseName": "测试员工",
                "publicEmail": "synthetic@example.invalid",
                "position": "工程师",
                "workBaseSi": "合成地点",
            }
        else:
            body = {
                "rows": [{"transId": "SYNTHETIC-TXN", "transType": "TEST", "amount": 1.00}],
                "total": 1,
                "totalExact": True,
                "page": 1,
                "size": 20,
            }
        return FakeDomainHttpResponse(
            status_code=200,
            content_type="application/json",
            body=json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        )

    async def aclose(self) -> None:
        return None


class BusinessQueryPlanNonLiveRuntime:
    def __init__(
        self,
        *,
        delegate: ModelContextBindingRuntimeInvoker,
        evidence_path: Path,
        model: _FakeBusinessQueryPlanTransport,
        fallback: _ForbiddenFallbackSelector,
        answer: _ForbiddenAnswerGenerator,
        employee: _FakeBusinessDomainTransport,
        transaction: _FakeBusinessDomainTransport,
    ) -> None:
        self._delegate = delegate
        self._evidence_path = evidence_path
        self._model = model
        self._fallback = fallback
        self._answer = answer
        self._employee = employee
        self._transaction = transaction
        self._cases: dict[str, tuple[str, str | None]] = {}
        self._closed = False
        self._lock = asyncio.Lock()

    async def ainvoke(self, *, question: str, scope: RequestExecutionScope) -> AgentSemanticOutcome:
        result = await self._delegate.ainvoke(question=question, scope=scope)
        case_id = scope.context.correlation_id
        if _SAFE_CASE_ID.fullmatch(case_id) is not None:
            if case_id in self._cases:
                raise RuntimeError("business_query_plan_e2e.duplicate_case")
            self._cases[case_id] = (result.status.value, result.capability_id)
        return result

    async def aclose(self) -> None:
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            failure: Exception | None = None
            for close in (self._delegate.aclose, self._employee.aclose, self._transaction.aclose):
                try:
                    await close()
                except Exception as exc:
                    if failure is None:
                        failure = exc
            write_business_query_plan_evidence(
                self._evidence_path,
                cases=self._cases,
                request_counts={
                    "queryPlanModel": self._model.query_plan_calls,
                    "otherModelTasks": self._model.other_task_calls,
                    "employee": self._employee.calls,
                    "transaction": self._transaction.calls,
                    "otherBusinessEndpoints": self._employee.other_endpoint_calls + self._transaction.other_endpoint_calls,
                    "fallbackSelector": self._fallback.calls,
                    "answerGeneration": self._answer.calls,
                    "externalModelOutbound": 0,
                },
                runtime_closed=failure is None,
            )
            if failure is not None:
                raise failure


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if value is None or not value.strip():
        raise ValueError(f"business_query_plan_e2e.env_missing:{name}")
    return value


def build_business_query_plan_nonlive_runtime(
    env: Mapping[str, str] | None = None,
) -> BusinessQueryPlanNonLiveRuntime:
    active = dict(os.environ if env is None else env)
    if active.get("AGENT_MODEL_PROVIDER", "stub") != "stub":
        raise ValueError("business_query_plan_e2e.model_provider_must_be_stub")
    evidence_path = Path(_required(active, "BUSINESS_QUERY_PLAN_E2E_EVIDENCE_PATH")).resolve()
    admin_token = _required(active, "BUSINESS_QUERY_PLAN_E2E_ADMIN_TOKEN")
    core_settings = CoreRuntimeSettings()
    employee_domain = EmployeeDomainProvider(
        settings=EmployeeAdapterSettings.from_env({"AGENT_EMPLOYEE_DETAIL_ENABLED": "true"}),
        service_binding=BusinessServiceBinding(
            service_key=BusinessServiceKey("employee-service"),
            base_endpoint="http://employee.invalid",
        ),
    )
    transaction_domain = TransactionDomainProvider(
        settings=TransactionAdapterSettings.from_env({"AGENT_TRANSACTION_SEARCH_ENABLED": "true"}),
        service_binding=BusinessServiceBinding(
            service_key=BusinessServiceKey("mq-procedure-service"),
            base_endpoint="http://transaction.invalid",
        ),
    )
    definitions = (*employee_domain.definitions(), *transaction_domain.definitions())
    fragments = (employee_domain.configuration_fragment(), transaction_domain.configuration_fragment())
    global_settings = BusinessGlobalSettings()
    support = BusinessSupportFactory().build(
        definitions=definitions,
        config=BusinessConfigurationSource(
            global_settings=global_settings,
            actions=tuple(item for fragment in fragments for item in fragment.actions),
            service_bindings=tuple(item for fragment in fragments for item in fragment.service_bindings),
        ),
        core_max_domain_result_bytes=core_settings.max_domain_result_bytes,
    )
    if support.planner_catalog is None:
        raise ValueError("business_query_plan_e2e.catalog_unavailable")
    employee_transport = _FakeBusinessDomainTransport(domain="employee", admin_token=admin_token)
    transaction_transport = _FakeBusinessDomainTransport(domain="transaction", admin_token=admin_token)
    clients = {
        "employee-service": UserJwtBusinessHttpClient(
            transport=employee_transport,
            max_response_bytes=global_settings.http_max_response_bytes,
        ),
        "mq-procedure-service": UserJwtBusinessHttpClient(
            transport=transaction_transport,
            max_response_bytes=global_settings.http_max_response_bytes,
        ),
    }
    registrations = tuple(
        CapabilityRegistrationCandidate[Any](
            descriptor=item.definition.descriptor,
            enabled=item.settings.enabled,
            argument_validator=item.definition.argument_validator,
            handler=BoundBusinessActionHandler(
                definition=item.definition,
                settings=item.settings,
                client=clients[str(item.definition.service_key)],
                user_projector=BusinessUserResultProjector(),
                egress_projector=BusinessEgressProjector(),
                egress_policy=GlobalBusinessEgressPolicy.from_settings(support.global_settings),
                config_snapshot_id=support.snapshot_id,
                max_user_result_bytes=support.global_settings.max_user_result_bytes,
            ),
        )
        for item in support.actions
        if item.settings.enabled
    )
    model_transport = _FakeBusinessQueryPlanTransport()
    model = LocalModelCompositionRoot.build(
        settings=ModelSettings(),
        transport=model_transport,
        grounding_policies={},
    )
    fallback = _ForbiddenFallbackSelector()
    answer = _ForbiddenAnswerGenerator()
    runtime = RuntimeCompositionRoot.build(
        settings=core_settings,
        providers=(_StaticProvider(*registrations),),
        capability_selector=fallback,
        answer_generator=answer,
        business_query_plan=BusinessQueryPlanRuntimeBindings(
            definitions=definitions,
            snapshot=support.configuration_snapshot,
            planner_catalog=support.planner_catalog,
            generator=model.business_query_plan_generator,
            context_accessor=model.context_accessor,
            protected_value_extractor=CompositeBusinessProtectedValueExtractor(
                (EmployeeProtectedValueExtractor(), TransactionProtectedValueExtractor())
            ),
            guard=QuestionEgressGuard(),
        ),
    )
    return BusinessQueryPlanNonLiveRuntime(
        delegate=model.bind_runtime(runtime),
        evidence_path=evidence_path,
        model=model_transport,
        fallback=fallback,
        answer=answer,
        employee=employee_transport,
        transaction=transaction_transport,
    )


async def _serve(settings: RuntimeHttpSettings, stop_path: Path) -> None:
    stop_path.parent.mkdir(parents=True, exist_ok=True)
    stop_path.unlink(missing_ok=True)
    app = create_app(settings, build_business_query_plan_nonlive_runtime)
    server = uvicorn.Server(uvicorn.Config(
        app=app,
        host=settings.host,
        port=settings.port,
        workers=1,
        http="h11",
        h11_max_incomplete_event_size=settings.max_incomplete_event_bytes,
        access_log=False,
        log_level="warning",
    ))

    async def watch_stop() -> None:
        while not stop_path.exists():
            await asyncio.sleep(0.05)
        server.should_exit = True

    watcher = asyncio.create_task(watch_stop())
    try:
        await server.serve()
    finally:
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass


def main() -> None:
    settings = RuntimeHttpSettings.from_env()
    stop_path = Path(_required(os.environ, "BUSINESS_QUERY_PLAN_E2E_STOP_PATH")).resolve()
    asyncio.run(_serve(settings, stop_path))


if __name__ == "__main__":
    main()
