from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any

import httpx
import uvicorn

from agent_runtime.adapters.employee.provider import EmployeeDomainProvider
from agent_runtime.adapters.employee.protected_input import EmployeeProtectedValueExtractor
from agent_runtime.adapters.employee.settings import EmployeeAdapterSettings
from agent_runtime.adapters.transaction.provider import TransactionDomainProvider
from agent_runtime.adapters.transaction.protected_input import TransactionProtectedValueExtractor
from agent_runtime.adapters.transaction.settings import TransactionAdapterSettings
from agent_runtime.api.app import create_app
from agent_runtime.api.settings import RuntimeHttpSettings
from agent_runtime.bootstrap import KnowledgeCompositionRoot, LocalModelCompositionRoot, RuntimeCompositionRoot
from agent_runtime.business.contracts import BusinessServiceKey, BusinessTransportFailure, BusinessTransportFailureKind
from agent_runtime.business.egress import BusinessEgressProjector
from agent_runtime.business.handler import BoundBusinessActionHandler
from agent_runtime.business.http_client import FakeDomainHttpRequest, FakeDomainHttpResponse, UserJwtBusinessHttpClient
from agent_runtime.business.provider import BusinessSupportFactory
from agent_runtime.business.protected_input import CompositeBusinessProtectedValueExtractor
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
from agent_runtime.knowledge.retrieval.bge_embedding import BgeM3EmbeddingAdapter
from agent_runtime.knowledge.retrieval.bge_rerank import BgeRerankAdapter
from agent_runtime.knowledge.retrieval.es_adapter import EsKnowledgeSearchAdapter
from agent_runtime.knowledge.retrieval.http import (
    BoundedHttpRequest,
    BoundedHttpResponse,
    HttpxKnowledgeTransport,
    build_knowledge_http_client,
)
from agent_runtime.knowledge.retrieval.settings import KnowledgeRetrievalSettings
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from agent_runtime.knowledge.settings import KnowledgeSettings
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
from tests.system_e2e.evidence_contract import write_runtime_evidence


_SAFE_CASE_ID = re.compile(r"system-[a-z0-9-]{1,48}")
_MAX_DOMAIN_RESPONSE_BYTES = 1_048_576


class _StaticProvider:
    def __init__(self, *registrations: CapabilityRegistrationCandidate[Any]) -> None:
        self._registrations = tuple(registrations)

    def registrations(self) -> tuple[CapabilityRegistrationCandidate[Any], ...]:
        return self._registrations


class _KnowledgeOnlySelector:
    async def __call__(self, input: CapabilitySelectionInput) -> CapabilitySelectionDecision:
        if not any(item.capability_id == "knowledge.query" for item in input.descriptors):
            return CapabilitySelectionDecision(kind=CapabilitySelectionDecisionKind.UNSUPPORTED)
        return CapabilitySelectionDecision(
            kind=CapabilitySelectionDecisionKind.CANDIDATE,
            capability_id="knowledge.query",
        )


class _ForbiddenAnswerGenerator:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, input: AnswerGenerationInput) -> Any:
        del input
        self.calls += 1
        raise AssertionError("system_e2e.answer_generation_forbidden")


class _DeterministicKnowledgeModelTransport:
    """Local deterministic transport for Knowledge tasks and Business QueryPlan."""

    def __init__(self) -> None:
        self.calls = 0
        self.calls_by_task: dict[str, int] = {}

    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        if call_deadline <= asyncio.get_running_loop().time():
            raise TimeoutError("system_e2e.local_model_deadline")
        self.calls += 1
        task = request.task_id.value
        self.calls_by_task[task] = self.calls_by_task.get(task, 0) + 1
        payload = json.loads(request.user_payload_json)
        if type(payload) is not dict:
            raise AssertionError("system_e2e.local_model_payload_invalid")
        if request.task_id is ModelTaskId.KNOWLEDGE_REWRITE:
            question = payload.get("question")
            if type(question) is not str or not question:
                raise AssertionError("system_e2e.local_model_payload_invalid")
            content = json.dumps({"candidates": [question]}, ensure_ascii=False, separators=(",", ":"))
        elif request.task_id is ModelTaskId.KNOWLEDGE_SUMMARY:
            raw_evidence = payload.get("evidence")
            if type(raw_evidence) is not list or not raw_evidence or type(raw_evidence[0]) is not dict:
                raise AssertionError("system_e2e.local_model_payload_invalid")
            first = raw_evidence[0]
            evidence_ref = first.get("evidence_ref")
            source = first.get("content")
            if type(evidence_ref) is not str or type(source) is not str:
                raise AssertionError("system_e2e.local_model_payload_invalid")
            match = re.search(r"[^\x00-\x1f\x7f]{1,512}", source)
            if match is None:
                content = '{"outcome":"insufficient_evidence","points":[]}'
            else:
                content = json.dumps(
                    {
                        "outcome": "answer",
                        "points": [{"evidence_ref": evidence_ref, "quote": match.group(0)}],
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
        elif request.task_id is ModelTaskId.BUSINESS_QUERY_PLAN:
            question = payload.get("question")
            if type(question) is not str or not question:
                raise AssertionError("system_e2e.local_model_payload_invalid")
            if "员工" in question or "employee" in question.casefold():
                content = (
                    '{"domain":"employee","action":"employee.detail",'
                    '"arguments":{"employee_identifier":{"value_ref":"slot-1"}}}'
                    if "protected-ref(slot-1)" in question
                    else '{"domain":"employee","action":"unsupported","arguments":{}}'
                )
            elif "交易" in question or "transaction" in question.casefold():
                amount = re.search(r"金额\s*(?:为|是|=|:|：|大于|>)\s*(-?[0-9]+(?:\.[0-9]+)?)", question)
                content = json.dumps(
                    {
                        "domain": "transaction",
                        "action": "transaction.search",
                        "arguments": {"amount": {"literal": amount.group(1) if amount is not None else "1.00"}},
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            else:
                content = '{"domain":"unsupported","action":"unsupported","arguments":{}}'
        else:
            raise AssertionError("system_e2e.model_task_forbidden")
        return StructuredModelResponse(
            finish_kind=StructuredFinishKind.STOP,
            content=content,
            tool_calls=(),
            usage_total_tokens=0,
        )


class _CountingKnowledgeTransport:
    def __init__(self, delegate: HttpxKnowledgeTransport) -> None:
        self._delegate = delegate
        self.calls_by_path: dict[str, int] = {}

    async def send(self, *, request: BoundedHttpRequest, timeout_s: float) -> BoundedHttpResponse:
        self.calls_by_path[request.relative_path] = self.calls_by_path.get(request.relative_path, 0) + 1
        return await self._delegate.send(request=request, timeout_s=timeout_s)


class _DomainTransport:
    def __init__(self, *, domain: str, base_url: str) -> None:
        if domain not in {"employee", "transaction"}:
            raise ValueError("system_e2e.domain_invalid")
        self._domain = domain
        self._client = httpx.AsyncClient(
            base_url=base_url,
            follow_redirects=False,
            trust_env=False,
            timeout=None,
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=1),
        )
        self.calls = 0
        self.other_endpoint_calls = 0

    async def send(self, outbound: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        request = outbound.request
        expected = (
            request.method == "GET"
            and request.relative_path.startswith("/employees/")
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
            raise BusinessTransportFailure(BusinessTransportFailureKind.PROTOCOL)
        self.calls += 1
        headers = {"Accept-Encoding": "identity", "Authorization": outbound.authorization}
        body = None
        if request.json_body is not None:
            headers["Content-Type"] = "application/json"
            body = bytes(request.json_body.content)
        async with self._client.stream(
            request.method,
            request.relative_path,
            params=request.query,
            headers=headers,
            content=body,
            follow_redirects=False,
        ) as response:
            raw = bytearray()
            async for chunk in response.aiter_raw():
                raw.extend(chunk)
                if len(raw) > _MAX_DOMAIN_RESPONSE_BYTES:
                    raise BusinessTransportFailure(BusinessTransportFailureKind.RESPONSE_TOO_LARGE)
            media_type = response.headers.get("Content-Type")
            return FakeDomainHttpResponse(
                status_code=response.status_code,
                content_type=None if media_type is None else media_type.split(";", 1)[0].strip().lower(),
                body=bytes(raw),
            )

    async def aclose(self) -> None:
        await self._client.aclose()


class SystemE2ERuntime:
    def __init__(
        self,
        *,
        delegate: ModelContextBindingRuntimeInvoker,
        evidence_path: Path,
        model_transport: _DeterministicKnowledgeModelTransport,
        answer_generator: _ForbiddenAnswerGenerator,
        knowledge_transports: tuple[_CountingKnowledgeTransport, ...],
        knowledge_clients: tuple[httpx.AsyncClient, ...],
        employee_transport: _DomainTransport,
        transaction_transport: _DomainTransport,
    ) -> None:
        self._delegate = delegate
        self._evidence_path = evidence_path
        self._model = model_transport
        self._answer = answer_generator
        self._knowledge_transports = knowledge_transports
        self._knowledge_clients = knowledge_clients
        self._employee = employee_transport
        self._transaction = transaction_transport
        self._cases: dict[str, tuple[str, str | None]] = {}
        self._closed = False
        self._lock = asyncio.Lock()

    async def ainvoke(self, *, question: str, scope: RequestExecutionScope) -> AgentSemanticOutcome:
        result = await self._delegate.ainvoke(question=question, scope=scope)
        case_id = scope.context.correlation_id
        if _SAFE_CASE_ID.fullmatch(case_id) is not None:
            if case_id in self._cases:
                raise RuntimeError("system_e2e.duplicate_case")
            self._cases[case_id] = (result.status.value, result.capability_id)
        return result

    async def aclose(self) -> None:
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            close_failure: Exception | None = None

            async def close_one(close: Callable[[], Awaitable[None]]) -> None:
                nonlocal close_failure
                try:
                    await close()
                except Exception as failure:  # Preserve the first failure after attempting every owned close.
                    if close_failure is None:
                        close_failure = failure

            await close_one(self._delegate.aclose)
            await close_one(self._employee.aclose)
            await close_one(self._transaction.aclose)
            for client in self._knowledge_clients:
                await close_one(client.aclose)
            counts: dict[str, int] = {}
            for transport in self._knowledge_transports:
                for path, value in transport.calls_by_path.items():
                    counts[path] = counts.get(path, 0) + value
            write_runtime_evidence(
                self._evidence_path,
                cases=self._cases,
                request_counts={
                    "knowledgeSearch": counts.get("/es/knowledge/search", 0),
                    "embedding": counts.get("/embed", 0),
                    "rerank": counts.get("/rerank", 0),
                    "employee": self._employee.calls,
                    "transaction": self._transaction.calls,
                    "otherBusinessEndpoints": self._employee.other_endpoint_calls
                    + self._transaction.other_endpoint_calls,
                    "localKnowledgeModel": sum(
                        self._model.calls_by_task.get(task.value, 0)
                        for task in (ModelTaskId.KNOWLEDGE_REWRITE, ModelTaskId.KNOWLEDGE_SUMMARY)
                    ),
                    "answerGeneration": self._answer.calls,
                    "externalModelOutbound": 0,
                },
                runtime_closed=close_failure is None,
            )
            if close_failure is not None:
                raise close_failure


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if value is None or not value.strip():
        raise ValueError(f"system_e2e.env_missing:{name}")
    return value


def build_system_e2e_runtime(env: Mapping[str, str] | None = None) -> SystemE2ERuntime:
    active = dict(os.environ if env is None else env)
    if active.get("AGENT_MODEL_PROVIDER", "stub") != "stub":
        raise ValueError("system_e2e.model_provider_must_be_stub")
    evidence_path = Path(_required(active, "SYSTEM_E2E_EVIDENCE_PATH")).resolve()
    core_settings = CoreRuntimeSettings()

    knowledge_settings = KnowledgeSettings.from_env(
        {
            "AGENT_KNOWLEDGE_ENABLED": "true",
            "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,tax.law",
            "AGENT_KNOWLEDGE_PER_PATH_CANDIDATES": "5",
            "AGENT_KNOWLEDGE_MIN_PARTIAL_CANDIDATES": "3",
        }
    )
    retrieval_settings = KnowledgeRetrievalSettings.from_env(
        {
            "AGENT_KNOWLEDGE_ES_BASE_URL": _required(active, "SYSTEM_E2E_KNOWLEDGE_BASE_URL"),
            "AGENT_KNOWLEDGE_EMBEDDING_BASE_URL": _required(active, "SYSTEM_E2E_EMBEDDING_BASE_URL"),
            "AGENT_KNOWLEDGE_RERANK_BASE_URL": _required(active, "SYSTEM_E2E_RERANK_BASE_URL"),
            "AGENT_KNOWLEDGE_FINAL_CANDIDATES": "10",
        },
        enabled=True,
    )
    assert retrieval_settings.es_base_url is not None
    es_client = build_knowledge_http_client(retrieval_settings.es_base_url)
    embedding_client = build_knowledge_http_client(retrieval_settings.embedding_base_url)
    rerank_client = build_knowledge_http_client(retrieval_settings.rerank_base_url)
    search_transport = _CountingKnowledgeTransport(HttpxKnowledgeTransport(es_client))
    embedding_transport = _CountingKnowledgeTransport(HttpxKnowledgeTransport(embedding_client))
    rerank_transport = _CountingKnowledgeTransport(HttpxKnowledgeTransport(rerank_client))
    retrieval = DefaultKnowledgeRetrievalStage(
        search=EsKnowledgeSearchAdapter(
            search_transport,
            expected_profile_version=retrieval_settings.profile_version,
        ),
        embedding=BgeM3EmbeddingAdapter(embedding_transport),
        rerank=BgeRerankAdapter(rerank_transport),
        final_candidates=retrieval_settings.final_candidates,
    )

    tasks = KnowledgeCompositionRoot.task_definitions(enabled=True)
    assert tasks is not None
    model_transport = _DeterministicKnowledgeModelTransport()
    model = LocalModelCompositionRoot.build(
        settings=ModelSettings(),
        transport=model_transport,
        grounding_policies={},
        additional_definitions=tasks.as_tuple(),
    )
    knowledge_provider = KnowledgeCompositionRoot.build_provider(
        settings=knowledge_settings,
        model=model,
        tasks=tasks,
        retrieval=retrieval,
    )

    employee_binding = BusinessServiceBinding(
        service_key=BusinessServiceKey("employee-service"),
        base_endpoint=_required(active, "SYSTEM_E2E_EMPLOYEE_BASE_URL"),
    )
    transaction_binding = BusinessServiceBinding(
        service_key=BusinessServiceKey("mq-procedure-service"),
        base_endpoint=_required(active, "SYSTEM_E2E_TRANSACTION_BASE_URL"),
    )
    employee_domain = EmployeeDomainProvider(
        settings=EmployeeAdapterSettings.from_env({"AGENT_EMPLOYEE_DETAIL_ENABLED": "true"}),
        service_binding=employee_binding,
    )
    transaction_domain = TransactionDomainProvider(
        settings=TransactionAdapterSettings.from_env({"AGENT_TRANSACTION_SEARCH_ENABLED": "true"}),
        service_binding=transaction_binding,
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
        raise ValueError("system_e2e.business_planner_catalog_unavailable")
    employee_transport = _DomainTransport(domain="employee", base_url=employee_binding.base_endpoint)
    transaction_transport = _DomainTransport(domain="transaction", base_url=transaction_binding.base_endpoint)
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
    answer_generator = _ForbiddenAnswerGenerator()
    runtime = RuntimeCompositionRoot.build(
        settings=core_settings,
        providers=(knowledge_provider, _StaticProvider(*registrations)),
        capability_selector=_KnowledgeOnlySelector(),
        answer_generator=answer_generator,
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
    return SystemE2ERuntime(
        delegate=model.bind_runtime(runtime),
        evidence_path=evidence_path,
        model_transport=model_transport,
        answer_generator=answer_generator,
        knowledge_transports=(search_transport, embedding_transport, rerank_transport),
        knowledge_clients=(es_client, embedding_client, rerank_client),
        employee_transport=employee_transport,
        transaction_transport=transaction_transport,
    )


async def _serve(settings: RuntimeHttpSettings, stop_path: Path) -> None:
    stop_path.parent.mkdir(parents=True, exist_ok=True)
    stop_path.unlink(missing_ok=True)
    app = create_app(settings, build_system_e2e_runtime)
    server = uvicorn.Server(uvicorn.Config(
        app=app,
        host=settings.host,
        port=settings.port,
        workers=1,
        http="h11",
        h11_max_incomplete_event_size=settings.max_incomplete_event_bytes,
        access_log=False,
    ))
    serving = asyncio.create_task(server.serve(), name="system-e2e-runtime")
    try:
        while not serving.done() and not stop_path.exists():
            await asyncio.sleep(0.1)
        if stop_path.exists():
            server.should_exit = True
        await serving
    finally:
        server.should_exit = True
        if not serving.done():
            await serving


def main() -> None:
    settings = RuntimeHttpSettings.from_env()
    stop_path = Path(_required(os.environ, "SYSTEM_E2E_RUNTIME_STOP_PATH")).resolve()
    asyncio.run(_serve(settings, stop_path))


if __name__ == "__main__":
    main()
