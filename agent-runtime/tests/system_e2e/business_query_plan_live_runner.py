from __future__ import annotations

import asyncio
import json
import os
import subprocess
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, cast

import httpx

from agent_runtime.business.http_client import (
    FakeDomainHttpRequest,
    FakeDomainHttpResponse,
    FakeDomainTransport,
)
from agent_runtime.capability_api.contracts import (
    CapabilityExecutionContext,
    CapabilityStatus,
    OpaqueUserToken,
    SubjectType,
)
from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.graph.action_resolution import (
    CapabilitySelectionDecision,
    CapabilitySelectionDecisionKind,
    CapabilitySelectionInput,
)
from agent_runtime.graph.state import AnswerGenerationInput
from agent_runtime.model.context import ModelCallContextAccessor, ModelContextBindingRuntimeInvoker
from agent_runtime.model.contracts import (
    ModelTaskId,
    StructuredFinishKind,
    StructuredModelRequest,
    StructuredModelResponse,
    StructuredModelTransport,
)
from agent_runtime.model.deepseek.business_query_plan import (
    DeepSeekBusinessQueryPlanGenerator,
    build_business_query_plan_task_definition,
)
from agent_runtime.model.deepseek.transport import DeepSeekChatTransport, build_deepseek_http_client
from agent_runtime.model.gateway import BoundedStructuredModelGateway
from agent_runtime.model.settings import ModelProvider, ModelSettings
from agent_runtime.runtime import AgentRuntimeInvoker
from tests.helpers import ManualCancellationSignal
from tests.system_e2e.business_query_plan_live_contracts import (
    AUTHORIZATION_REFERENCE,
    CASE_IDS,
    EMPLOYEE_BASE_URL,
    EMPLOYEE_DETAIL_BUDGET,
    MODEL_CALL_BUDGET,
    RUN_ID,
    TRANSACTION_BASE_URL,
    TRANSACTION_SEARCH_BUDGET,
    append_journal,
    sha256_file,
    validate_attempt_journal,
    validate_consumed,
    validate_lifecycle,
    validate_manifest,
    validate_result,
    write_exclusive_json,
)
from tests.system_e2e.business_query_plan_runtime_support import (
    build_business_query_plan_runtime,
    business_query_plan_snapshot_id,
)


_ACTIVE_CASE: ContextVar[str | None] = ContextVar("business_query_plan_live_case", default=None)


@dataclass(frozen=True, slots=True, kw_only=True)
class CandidatePaths:
    lifecycle: Path
    consumed: Path
    journal: Path
    result: Path


@dataclass(slots=True)
class CandidateMetrics:
    model_calls: int = 0
    employee_detail: int = 0
    transaction_search: int = 0
    other_business_endpoints: int = 0
    fallback_selector: int = 0
    answer_generation: int = 0
    knowledge: int = 0
    retry: int = 0
    resume: int = 0
    forbidden_fields: int = 0
    model_calls_by_case: dict[str, int] = field(default_factory=dict)
    domain_calls_by_case: dict[str, int] = field(default_factory=dict)

    def as_result(self) -> dict[str, int]:
        return {
            "modelCalls": self.model_calls,
            "employeeDetail": self.employee_detail,
            "transactionSearch": self.transaction_search,
            "otherBusinessEndpoints": self.other_business_endpoints,
            "fallbackSelector": self.fallback_selector,
            "answerGeneration": self.answer_generation,
            "knowledge": self.knowledge,
            "retry": self.retry,
            "resume": self.resume,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class CandidateSecrets:
    employee_identifier: str
    admin_jwt: str
    denied_jwt: str
    model_api_key: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class CandidateDependencies:
    metrics: CandidateMetrics
    model_transport: StructuredModelTransport
    model_settings: ModelSettings
    employee_transport: FakeDomainTransport
    transaction_transport: FakeDomainTransport
    close_model: Callable[[], Awaitable[None]] | None
    close_domains: Callable[[], Awaitable[None]]
    expected_snapshot_id: str | None = None


class _ForbiddenFallbackSelector:
    def __init__(self, metrics: CandidateMetrics) -> None:
        self._metrics = metrics

    async def __call__(self, input: CapabilitySelectionInput) -> CapabilitySelectionDecision:
        del input
        self._metrics.fallback_selector += 1
        return CapabilitySelectionDecision(kind=CapabilitySelectionDecisionKind.UNSUPPORTED)


class _ForbiddenAnswerGenerator:
    def __init__(self, metrics: CandidateMetrics) -> None:
        self._metrics = metrics

    async def __call__(self, input: AnswerGenerationInput) -> Any:
        del input
        self._metrics.answer_generation += 1
        raise AssertionError("business_query_plan_live.answer_generation_forbidden")


class _BudgetedModelTransport:
    def __init__(
        self,
        *,
        delegate: StructuredModelTransport,
        metrics: CandidateMetrics,
        live: bool,
        paths: CandidatePaths,
        manifest_sha256: str,
        secrets: CandidateSecrets,
    ) -> None:
        self._delegate = delegate
        self._metrics = metrics
        self._live = live
        self._paths = paths
        self._manifest_sha256 = manifest_sha256
        self._secrets = secrets

    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        case_id = _ACTIVE_CASE.get()
        if case_id not in CASE_IDS or request.task_id is not ModelTaskId.BUSINESS_QUERY_PLAN:
            raise AssertionError("business_query_plan_live.model_scope_invalid")
        if any(
            value and value in request.user_payload_json
            for value in (
                self._secrets.employee_identifier,
                self._secrets.admin_jwt,
                self._secrets.denied_jwt,
                self._secrets.model_api_key,
            )
        ):
            self._metrics.forbidden_fields += 1
            raise AssertionError("business_query_plan_live.model_input_leak")
        if self._metrics.model_calls >= MODEL_CALL_BUDGET:
            raise AssertionError("business_query_plan_live.model_budget_exceeded")
        if self._live and not self._paths.consumed.exists():
            write_exclusive_json(
                self._paths.consumed,
                {
                    "schemaVersion": 1,
                    "runId": RUN_ID,
                    "authorizationReference": AUTHORIZATION_REFERENCE,
                    "manifestSha256": self._manifest_sha256,
                    "event": "first_model_outbound",
                },
            )
        self._metrics.model_calls += 1
        self._metrics.model_calls_by_case[case_id] = self._metrics.model_calls_by_case.get(case_id, 0) + 1
        if self._metrics.model_calls_by_case[case_id] != 1:
            raise AssertionError("business_query_plan_live.multiple_plans_for_request")
        ordinal = self._metrics.model_calls
        try:
            response = await self._delegate.complete(request, call_deadline=call_deadline)
        except BaseException:
            append_journal(
                self._paths.journal,
                {"caseId": case_id, "modelCall": ordinal, "terminal": "failed"},
            )
            raise
        append_journal(
            self._paths.journal,
            {"caseId": case_id, "modelCall": ordinal, "terminal": "completed"},
        )
        return response


class _ModelComposition:
    def __init__(
        self,
        *,
        transport: StructuredModelTransport,
        settings: ModelSettings,
        close: Callable[[], Awaitable[None]] | None,
    ) -> None:
        definition = build_business_query_plan_task_definition(timeout_ms=settings.action_timeout_ms)
        gateway = BoundedStructuredModelGateway(
            transport=transport,
            definitions=(definition,),
            max_concurrency=1,
        )
        self.business_query_plan_generator = DeepSeekBusinessQueryPlanGenerator(
            gateway=gateway,
            definition=definition,
        )
        self.context_accessor = ModelCallContextAccessor()
        self._close = close
        self._closed = False

    def bind_runtime(self, runtime: AgentRuntimeInvoker) -> ModelContextBindingRuntimeInvoker:
        return ModelContextBindingRuntimeInvoker(runtime, close=self.aclose)

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._close is not None:
            await self._close()


class FakeQueryPlanTransport:
    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        if call_deadline <= asyncio.get_running_loop().time():
            raise TimeoutError("business_query_plan_live.fake_deadline")
        case_id = _ACTIVE_CASE.get()
        if request.task_id is not ModelTaskId.BUSINESS_QUERY_PLAN or case_id not in CASE_IDS:
            raise AssertionError("business_query_plan_live.fake_model_scope_invalid")
        if case_id == "bq-live-emp-unsupported":
            content = '{"domain":"employee","action":"unsupported","arguments":{}}'
        elif case_id in {"bq-live-emp-admin", "bq-live-emp-denied"}:
            content = (
                '{"domain":"employee","action":"employee.detail",'
                '"arguments":{"employee_identifier":{"value_ref":"slot-1"}}}'
            )
        elif case_id == "bq-live-txn-unsupported":
            content = '{"domain":"transaction","action":"unsupported","arguments":{}}'
        else:
            content = (
                '{"domain":"transaction","action":"transaction.search",'
                '"arguments":{"amount":{"literal":"1.00"}}}'
            )
        return StructuredModelResponse(
            finish_kind=StructuredFinishKind.STOP,
            content=content,
            tool_calls=(),
            usage_total_tokens=0,
        )


class FakeLiveDomainTransport:
    def __init__(
        self,
        *,
        domain: str,
        admin_jwt: str,
        employee_identifier: str,
        metrics: CandidateMetrics,
    ) -> None:
        if domain not in {"employee", "transaction"}:
            raise ValueError("business_query_plan_live.fake_domain_invalid")
        self._domain = domain
        self._authorization = f"Bearer {admin_jwt}"
        self._employee_identifier = employee_identifier
        self._metrics = metrics

    async def send(self, outbound: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        request = outbound.request
        expected = _expected_endpoint(self._domain, request.method, request.relative_path, request.query, request.json_body)
        if not expected:
            self._metrics.other_business_endpoints += 1
            return FakeDomainHttpResponse(status_code=404, content_type="application/json", body=b"{}")
        _increment_domain(self._domain, self._metrics)
        if outbound.authorization != self._authorization:
            return FakeDomainHttpResponse(status_code=403, content_type="application/json", body=b"{}")
        body: dict[str, object]
        if self._domain == "employee":
            body = {
                "idCardNo": self._employee_identifier,
                "memberNo": "SYNTHETIC",
                "chineseName": "合成员工",
                "publicEmail": "synthetic@example.invalid",
                "position": "工程师",
                "workBaseSi": "合成地点",
            }
        else:
            body = {
                "rows": [{"transId": "SYNTHETIC", "transType": "TEST", "amount": 1.00}],
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


class HttpxLiveDomainTransport:
    def __init__(self, *, domain: str, client: httpx.AsyncClient, metrics: CandidateMetrics) -> None:
        self._domain = domain
        self._client = client
        self._metrics = metrics

    async def send(self, outbound: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        request = outbound.request
        if not _expected_endpoint(self._domain, request.method, request.relative_path, request.query, request.json_body):
            self._metrics.other_business_endpoints += 1
            raise AssertionError("business_query_plan_live.domain_endpoint_forbidden")
        _increment_domain(self._domain, self._metrics)
        headers = {"Accept": "application/json", "Accept-Encoding": "identity", "Authorization": outbound.authorization}
        content: bytes | None = None
        if request.json_body is not None:
            headers["Content-Type"] = "application/json"
            content = bytes(request.json_body.content)
        response = await self._client.request(
            request.method,
            request.relative_path,
            params=request.query,
            content=content,
            headers=headers,
        )
        content_type = response.headers.get("Content-Type")
        return FakeDomainHttpResponse(
            status_code=response.status_code,
            content_type=None if content_type is None else content_type.split(";", 1)[0].strip().casefold(),
            body=response.content,
        )

    async def aclose(self) -> None:
        await self._client.aclose()


async def run_candidate(
    *,
    live: bool,
    paths: CandidatePaths,
    manifest_sha256: str,
    secrets: CandidateSecrets,
    dependencies: CandidateDependencies,
) -> dict[str, object]:
    for path in (paths.lifecycle, paths.consumed, paths.journal, paths.result):
        if path.exists():
            raise RuntimeError("business_query_plan_live.run_already_exists")
    metrics = dependencies.metrics
    write_exclusive_json(
        paths.lifecycle,
        {
            "schemaVersion": 1,
            "runId": RUN_ID,
            "authorizationReference": AUTHORIZATION_REFERENCE,
            "manifestSha256": manifest_sha256,
            "event": "run_started",
        },
    )
    cases: list[dict[str, object]] = []
    failure_case: dict[str, object] | None = None
    failure: BaseException | None = None
    runtime_closed = False
    model_closed = False
    domains_closed = False
    model: _ModelComposition | None = None
    runtime: ModelContextBindingRuntimeInvoker | None = None
    try:
        budgeted = _BudgetedModelTransport(
            delegate=dependencies.model_transport,
            metrics=metrics,
            live=live,
            paths=paths,
            manifest_sha256=manifest_sha256,
            secrets=secrets,
        )
        model = _ModelComposition(
            transport=budgeted,
            settings=dependencies.model_settings,
            close=dependencies.close_model,
        )
        fallback = _ForbiddenFallbackSelector(metrics)
        answer = _ForbiddenAnswerGenerator(metrics)
        runtime = build_business_query_plan_runtime(
            model=model,
            employee_transport=dependencies.employee_transport,
            transaction_transport=dependencies.transaction_transport,
            fallback_selector=fallback,
            answer_generator=answer,
            employee_endpoint=EMPLOYEE_BASE_URL,
            transaction_endpoint=TRANSACTION_BASE_URL,
            expected_snapshot_id=dependencies.expected_snapshot_id,
        )
        for case_id in CASE_IDS:
            question, jwt = _case_input(case_id, secrets)
            token: Token[str | None] = _ACTIVE_CASE.set(case_id)
            try:
                outcome = await runtime.ainvoke(
                    question=question,
                    scope=_scope(question, case_id=case_id, jwt=jwt),
                )
            finally:
                _ACTIVE_CASE.reset(token)
            case_result: dict[str, object] = {
                "caseId": case_id,
                "domain": "employee" if "-emp-" in case_id else "transaction",
                "status": outcome.status.value,
                "capabilityId": outcome.capability_id,
                "planCalls": metrics.model_calls_by_case.get(case_id, 0),
                "domainCalls": metrics.domain_calls_by_case.get(case_id, 0),
            }
            try:
                _validate_case_result(case_result)
            except AssertionError:
                failure_case = _finite_failure_case(case_result)
                raise
            cases.append(case_result)
    except BaseException as exc:
        failure = exc
    finally:
        try:
            if runtime is not None:
                await runtime.aclose()
                runtime_closed = True
                model_closed = True
            elif model is not None:
                await model.aclose()
                model_closed = True
        except BaseException as exc:
            if failure is None:
                failure = exc
        try:
            await dependencies.close_domains()
            domains_closed = True
        except BaseException as exc:
            if failure is None:
                failure = exc

    try:
        validate_lifecycle(json.loads(paths.lifecycle.read_text(encoding="utf-8")), manifest_sha256=manifest_sha256)
        journal_entries = tuple(
            json.loads(line)
            for line in paths.journal.read_text(encoding="utf-8").splitlines()
        ) if paths.journal.exists() else ()
        validate_attempt_journal(journal_entries, expected_calls=metrics.model_calls)
        if paths.consumed.exists():
            validate_consumed(
                json.loads(paths.consumed.read_text(encoding="utf-8")),
                manifest_sha256=manifest_sha256,
            )
        if paths.consumed.exists() is not (live and metrics.model_calls > 0):
            raise ValueError("business_query_plan_live.consumption_state_invalid")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        if failure is None:
            failure = exc
    leaked = _scan_sensitive(paths, secrets)
    if failure is None and (
        leaked
        or metrics.as_result() != {
            "modelCalls": MODEL_CALL_BUDGET,
            "employeeDetail": EMPLOYEE_DETAIL_BUDGET,
            "transactionSearch": TRANSACTION_SEARCH_BUDGET,
            "otherBusinessEndpoints": 0,
            "fallbackSelector": 0,
            "answerGeneration": 0,
            "knowledge": 0,
            "retry": 0,
            "resume": 0,
        }
    ):
        failure = AssertionError("business_query_plan_live.count_or_security_invalid")
    status = "passed" if failure is None else ("failed_consumed" if paths.consumed.exists() else "failed_unconsumed")
    reason = "business_query_plan_live.passed" if failure is None else _safe_failure_reason(failure)
    result: dict[str, object] = {
        "schemaVersion": 2,
        "workPackage": "WP-BQ-QUERYPLAN-LIVE-01",
        "runId": RUN_ID,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "manifestSha256": manifest_sha256,
        "status": status,
        "reason": reason,
        "cases": cases,
        "failureCase": failure_case,
        "counts": metrics.as_result(),
        "security": {
            "forbiddenFields": metrics.forbidden_fields,
            "sensitivePersistence": leaked,
            "logLeakCount": 0,
        },
        "cleanup": {
            "runtimeClosed": runtime_closed,
            "modelClientClosed": model_closed,
            "domainClientsClosed": domains_closed,
        },
    }
    write_exclusive_json(paths.result, result)
    validate_result(result, require_passed=failure is None)
    if failure is not None:
        raise RuntimeError(reason) from None
    return result


async def run_live_from_environment(env: Mapping[str, str] | None = None) -> dict[str, object]:
    active = dict(os.environ if env is None else env)
    if active.get("BUSINESS_QUERY_PLAN_LIVE_ENABLE") != "1":
        raise RuntimeError("business_query_plan_live.not_enabled")
    manifest_path = Path(_required(active, "BUSINESS_QUERY_PLAN_LIVE_MANIFEST_PATH")).resolve()
    manifest_sha256 = _required(active, "BUSINESS_QUERY_PLAN_LIVE_MANIFEST_SHA256")
    if sha256_file(manifest_path) != manifest_sha256:
        raise RuntimeError("business_query_plan_live.manifest_hash_mismatch")
    manifest = validate_manifest(json.loads(manifest_path.read_text(encoding="utf-8")))
    if manifest["runId"] != _required(active, "BUSINESS_QUERY_PLAN_LIVE_RUN_ID"):
        raise RuntimeError("business_query_plan_live.run_binding_mismatch")
    if manifest["authorizationReference"] != _required(active, "BUSINESS_QUERY_PLAN_LIVE_AUTHORIZATION_REFERENCE"):
        raise RuntimeError("business_query_plan_live.authorization_binding_mismatch")
    repository_root = Path(__file__).resolve().parents[3]
    frozen_head = _required(active, "BUSINESS_QUERY_PLAN_LIVE_FROZEN_HEAD")
    current_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if current_head != frozen_head:
        raise RuntimeError("business_query_plan_live.head_mismatch")
    for raw_asset in cast(list[dict[str, str]], manifest["assets"]):
        asset_path = (repository_root / raw_asset["path"]).resolve()
        if not asset_path.is_relative_to(repository_root) or sha256_file(asset_path) != raw_asset["sha256"]:
            raise RuntimeError("business_query_plan_live.asset_hash_mismatch")

    employee_endpoint = _required(active, "BUSINESS_QUERY_PLAN_LIVE_EMPLOYEE_BASE_URL")
    transaction_endpoint = _required(active, "BUSINESS_QUERY_PLAN_LIVE_TRANSACTION_BASE_URL")
    if employee_endpoint != EMPLOYEE_BASE_URL or transaction_endpoint != TRANSACTION_BASE_URL:
        raise RuntimeError("business_query_plan_live.endpoint_invalid")
    expected_snapshot_id = business_query_plan_snapshot_id(
        employee_endpoint=employee_endpoint,
        transaction_endpoint=transaction_endpoint,
    )
    if cast(dict[str, str], manifest["snapshots"])["configSha256"] != expected_snapshot_id:
        raise RuntimeError("business_query_plan_live.snapshot_mismatch")

    settings = ModelSettings.from_env(active)
    if settings.provider is not ModelProvider.DEEPSEEK:
        raise RuntimeError("business_query_plan_live.deepseek_required")
    result_dir = Path(_required(active, "BUSINESS_QUERY_PLAN_LIVE_RESULT_DIR")).resolve()
    paths = CandidatePaths(
        lifecycle=result_dir / "lifecycle.jsonl",
        consumed=result_dir / "authorization.consumed.json",
        journal=result_dir / "model-attempts.jsonl",
        result=result_dir / "result.json",
    )
    if any(path.exists() for path in (paths.lifecycle, paths.consumed, paths.journal, paths.result)):
        raise RuntimeError("business_query_plan_live.run_already_exists")
    secrets = CandidateSecrets(
        employee_identifier=_required(active, "BUSINESS_QUERY_PLAN_LIVE_EMPLOYEE_IDENTIFIER"),
        admin_jwt=_required(active, "BUSINESS_QUERY_PLAN_LIVE_ADMIN_JWT"),
        denied_jwt=_required(active, "BUSINESS_QUERY_PLAN_LIVE_DENIED_JWT"),
        model_api_key=_required(active, "LLM_API_KEY"),
    )
    model_client = build_deepseek_http_client(settings)
    employee_client = _domain_client(employee_endpoint)
    transaction_client = _domain_client(transaction_endpoint)
    metrics = CandidateMetrics()
    employee_transport = HttpxLiveDomainTransport(domain="employee", client=employee_client, metrics=metrics)
    transaction_transport = HttpxLiveDomainTransport(domain="transaction", client=transaction_client, metrics=metrics)

    async def close_domains() -> None:
        await asyncio.gather(employee_transport.aclose(), transaction_transport.aclose())

    # Domain counters must be shared with the Runtime candidate metrics. The
    # injected wrappers below rebind them once run_candidate creates that object.
    dependencies = CandidateDependencies(
        metrics=metrics,
        model_transport=DeepSeekChatTransport(settings=settings, client=model_client),
        model_settings=settings,
        employee_transport=employee_transport,
        transaction_transport=transaction_transport,
        close_model=model_client.aclose,
        close_domains=close_domains,
        expected_snapshot_id=expected_snapshot_id,
    )
    return await run_candidate(
        live=True,
        paths=paths,
        manifest_sha256=manifest_sha256,
        secrets=secrets,
        dependencies=dependencies,
    )


def build_fake_dependencies(
    *,
    secrets: CandidateSecrets,
    metrics: CandidateMetrics,
) -> CandidateDependencies:
    employee = FakeLiveDomainTransport(
        domain="employee",
        admin_jwt=secrets.admin_jwt,
        employee_identifier=secrets.employee_identifier,
        metrics=metrics,
    )
    transaction = FakeLiveDomainTransport(
        domain="transaction",
        admin_jwt=secrets.admin_jwt,
        employee_identifier=secrets.employee_identifier,
        metrics=metrics,
    )

    async def close_domains() -> None:
        return None

    return CandidateDependencies(
        metrics=metrics,
        model_transport=FakeQueryPlanTransport(),
        model_settings=ModelSettings(max_concurrency=1),
        employee_transport=employee,
        transaction_transport=transaction,
        close_model=None,
        close_domains=close_domains,
        expected_snapshot_id=business_query_plan_snapshot_id(
            employee_endpoint=EMPLOYEE_BASE_URL,
            transaction_endpoint=TRANSACTION_BASE_URL,
        ),
    )


def _domain_client(base_url: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url,
        follow_redirects=False,
        trust_env=False,
        timeout=httpx.Timeout(10.0),
        limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        headers={"Accept-Encoding": "identity"},
    )


def _expected_endpoint(domain: str, method: str, path: str, query: object, json_body: object) -> bool:
    if domain == "employee":
        suffix = path.removeprefix("/employees/")
        return method == "GET" and path.startswith("/employees/") and bool(suffix) and "/" not in suffix and query == () and json_body is None
    return domain == "transaction" and method == "POST" and path == "/txn/search" and query == () and json_body is not None


def _increment_domain(domain: str, metrics: CandidateMetrics) -> None:
    case_id = _ACTIVE_CASE.get()
    expected_domain = "employee" if isinstance(case_id, str) and "-emp-" in case_id else "transaction"
    if case_id not in CASE_IDS or domain != expected_domain:
        metrics.other_business_endpoints += 1
        raise AssertionError("business_query_plan_live.cross_domain_call_forbidden")
    metrics.domain_calls_by_case[case_id] = metrics.domain_calls_by_case.get(case_id, 0) + 1
    if metrics.domain_calls_by_case[case_id] != 1:
        raise AssertionError("business_query_plan_live.second_action_forbidden")
    if domain == "employee":
        if metrics.employee_detail >= EMPLOYEE_DETAIL_BUDGET:
            raise AssertionError("business_query_plan_live.employee_budget_exceeded")
        metrics.employee_detail += 1
    elif domain == "transaction":
        if metrics.transaction_search >= TRANSACTION_SEARCH_BUDGET:
            raise AssertionError("business_query_plan_live.transaction_budget_exceeded")
        metrics.transaction_search += 1
    else:
        raise AssertionError("business_query_plan_live.domain_invalid")


def _case_input(case_id: str, secrets: CandidateSecrets) -> tuple[str, str]:
    if case_id == "bq-live-emp-admin":
        return f"查询员工详情 员工标识={secrets.employee_identifier}", secrets.admin_jwt
    if case_id == "bq-live-emp-denied":
        return f"查询员工详情 员工标识={secrets.employee_identifier}", secrets.denied_jwt
    if case_id == "bq-live-emp-unsupported":
        return "帮我查看上海的员工", secrets.admin_jwt
    if case_id == "bq-live-txn-admin":
        return "查询金额为1.00的交易", secrets.admin_jwt
    if case_id == "bq-live-txn-denied":
        return "查询金额为1.00的交易", secrets.denied_jwt
    if case_id == "bq-live-txn-unsupported":
        return "查询今天发生的交易", secrets.admin_jwt
    raise AssertionError("business_query_plan_live.case_invalid")


def _scope(question: str, *, case_id: str, jwt: str) -> RequestExecutionScope:
    return RequestExecutionScope(
        context=CapabilityExecutionContext(
            request_id=f"request-{case_id}",
            correlation_id=case_id,
            original_question=question,
            subject_id="business-query-plan-live-user",
            subject_type=SubjectType.USER,
            user_token=OpaqueUserToken.from_raw(jwt),
            deadline_monotonic=asyncio.get_running_loop().time() + 20.0,
            cancellation=ManualCancellationSignal(),
        )
    )


def _validate_case_result(value: Mapping[str, object]) -> None:
    case_id = cast(str, value["caseId"])
    status = cast(str, value["status"])
    capability_id = value["capabilityId"]
    domain_calls = value["domainCalls"]
    plan_calls = value["planCalls"]
    expected_statuses, expected_capability, expected_domain_calls = _case_expectations(case_id)
    if (
        status not in expected_statuses
        or capability_id != expected_capability
        or plan_calls != 1
        or domain_calls != expected_domain_calls
    ):
        raise AssertionError("business_query_plan_live.case_failed")


def _case_expectations(case_id: str) -> tuple[frozenset[str], str | None, int]:
    expected_statuses: dict[str, frozenset[str]] = {
        "bq-live-emp-admin": frozenset({CapabilityStatus.SUCCESS.value}),
        "bq-live-emp-denied": frozenset({CapabilityStatus.FORBIDDEN.value}),
        "bq-live-emp-unsupported": frozenset({CapabilityStatus.UNSUPPORTED.value}),
        "bq-live-txn-admin": frozenset({CapabilityStatus.SUCCESS.value, CapabilityStatus.NO_RESULT.value}),
        "bq-live-txn-denied": frozenset({CapabilityStatus.FORBIDDEN.value}),
        "bq-live-txn-unsupported": frozenset({CapabilityStatus.UNSUPPORTED.value}),
    }
    expected_capability = None if case_id.endswith("unsupported") else (
        "employee.detail" if "emp-" in case_id else "transaction.search"
    )
    expected_domain_calls = 0 if case_id.endswith("unsupported") else 1
    return expected_statuses[case_id], expected_capability, expected_domain_calls


def _finite_failure_case(value: Mapping[str, object]) -> dict[str, object]:
    case_id = cast(str, value["caseId"])
    status = cast(str, value["status"])
    capability_id = value["capabilityId"]
    plan_calls = value["planCalls"]
    domain_calls = value["domainCalls"]
    expected_statuses, expected_capability, expected_domain_calls = _case_expectations(case_id)
    if status not in expected_statuses:
        reason = "status_mismatch"
    elif capability_id != expected_capability:
        reason = "capability_mismatch"
    elif plan_calls != 1:
        reason = "plan_call_mismatch"
    elif domain_calls != expected_domain_calls:
        reason = "domain_call_mismatch"
    else:
        raise AssertionError("business_query_plan_live.failure_case_not_failed")
    return {
        "caseId": case_id,
        "status": status,
        "capabilityId": capability_id,
        "planCalls": plan_calls,
        "domainCalls": domain_calls,
        "reason": reason,
    }


def _scan_sensitive(paths: CandidatePaths, secrets: CandidateSecrets) -> bool:
    values = tuple(item.encode("utf-8") for item in (
        secrets.employee_identifier,
        secrets.admin_jwt,
        secrets.denied_jwt,
        secrets.model_api_key,
    ) if item)
    for path in (paths.lifecycle, paths.consumed, paths.journal):
        if path.exists():
            payload = path.read_bytes()
            if any(value in payload for value in values):
                return True
    return False


def _safe_failure_reason(error: BaseException | None) -> str:
    if error is None:
        return "business_query_plan_live.unknown_failure"
    if isinstance(error, AssertionError):
        return "business_query_plan_live.assertion_failed"
    if isinstance(error, TimeoutError):
        return "business_query_plan_live.timeout"
    return "business_query_plan_live.execution_failed"


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"business_query_plan_live.env_missing:{name}")
    return value


def main() -> None:
    asyncio.run(run_live_from_environment())


if __name__ == "__main__":
    main()
