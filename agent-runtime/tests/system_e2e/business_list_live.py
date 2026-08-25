from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Final, Protocol, cast

from agent_runtime.adapters.http_transport import HttpxBusinessDomainTransport
from agent_runtime.bootstrap import BusinessQueryRuntimeCompositionRoot, LocalModelCompositionRoot
from agent_runtime.business.http_client import (
    FakeDomainHttpRequest,
    FakeDomainHttpResponse,
    FakeDomainTransport,
)
from agent_runtime.capability_api.contracts import CapabilityStatus, JsonObject, OpaqueUserToken
from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.model.context import ModelContextBindingRuntimeInvoker
from agent_runtime.model.contracts import (
    BusinessQueryPlanGenerator,
    BusinessQueryPlanTaskInput,
    ModelCallContext,
)
from agent_runtime.model.deepseek.business_query_plan import (
    BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION,
    BUSINESS_QUERY_PLAN_TASK_VERSION,
)
from agent_runtime.model.settings import ModelProvider, ModelSettings
from tests.helpers import scope


_ROOT: Final = Path(__file__).resolve().parents[3]
_CONFIG: Final = _ROOT / "agent-runtime/src/agent_runtime/business/business-query.v2.json"
_MANIFEST: Final = Path(__file__).with_name("business_list_live_manifest.json")
_ACTIVE_CASE: ContextVar[str] = ContextVar("business_list_live_active_case", default="")
_ALLOWED_PATHS: Final = {
    "/employees/es/search": "employeeSearch",
    "/employees/es/vector-search": "employeeSemantic",
    "/txn/search": "transactionSearch",
}
_CASE_ID: Final = re.compile(r"(?:LIVE|UAT)-(?:EMP|TXN)-[0-9]{3}")
_ALLOWED_EMPLOYEE_RESULT_FIELDS: Final = frozenset({
    "contact_address", "chinese_name", "employee_identifier", "member_no",
    "phone_no", "email", "position",
})


@dataclass(frozen=True, slots=True, kw_only=True)
class LiveCase:
    case_id: str
    question: str
    expected_action: str | None
    expected_statuses: tuple[CapabilityStatus, ...]
    principal: str = "admin"
    expected_fields: tuple[str, ...] = ()
    expected_operators: tuple[str, ...] = ()
    minimum_rows: int = 0
    expected_page: int | None = None
    expected_model_calls: int = 1


def controlled_cases() -> tuple[LiveCase, ...]:
    return (
        LiveCase(case_id="LIVE-EMP-001", question="帮我查一下在上海的员工", expected_action="employee.search", expected_statuses=(CapabilityStatus.SUCCESS,), expected_fields=("contact_address",), expected_operators=("contains",), minimum_rows=1),
        LiveCase(case_id="LIVE-EMP-002", question="查询具备金融风控经验的员工", expected_action="employee.semantic_search", expected_statuses=(CapabilityStatus.SUCCESS,), minimum_rows=1),
        LiveCase(case_id="LIVE-TXN-001", question="查询金额大于0.01的交易", expected_action="transaction.search", expected_statuses=(CapabilityStatus.SUCCESS, CapabilityStatus.NO_RESULT), expected_fields=("amount",), expected_operators=("gt",)),
        LiveCase(case_id="LIVE-EMP-003", question="帮我查一下在上海的员工", expected_action="employee.search", expected_statuses=(CapabilityStatus.FORBIDDEN,), principal="denied", expected_fields=("contact_address",), expected_operators=("contains",)),
        LiveCase(case_id="LIVE-TXN-002", question="查询金额大于0.01的交易", expected_action="transaction.search", expected_statuses=(CapabilityStatus.FORBIDDEN,), principal="denied", expected_fields=("amount",), expected_operators=("gt",)),
        LiveCase(case_id="LIVE-EMP-004", question="查询员工的workBaseSi等于上海", expected_action=None, expected_statuses=(CapabilityStatus.UNSUPPORTED, CapabilityStatus.INVALID_ARGUMENT)),
    )


def uat_cases(*, transaction_type: str, employee_identifier: str) -> tuple[LiveCase, ...]:
    if not transaction_type or len(transaction_type) > 64 or len(employee_identifier) < 5:
        raise ValueError("business_list_live.runtime_input_invalid")
    type_fragment = transaction_type[: max(1, min(3, len(transaction_type)))]
    return (
        LiveCase(case_id="UAT-EMP-201", question="帮我查一下在上海的员工", expected_action="employee.search", expected_statuses=(CapabilityStatus.SUCCESS,), expected_fields=("contact_address",), expected_operators=("contains",), minimum_rows=1),
        LiveCase(case_id="UAT-EMP-203", question="查询职位包含工程的员工", expected_action="employee.search", expected_statuses=(CapabilityStatus.SUCCESS, CapabilityStatus.NO_RESULT), expected_fields=("position",), expected_operators=("contains",)),
        LiveCase(case_id="UAT-EMP-205", question=f"查询员工，员工标识 {employee_identifier}", expected_action="employee.search", expected_statuses=(CapabilityStatus.SUCCESS,), expected_fields=("employee_identifier",), expected_operators=("eq",), minimum_rows=1),
        LiveCase(case_id="UAT-EMP-207", question="查询在上海的员工，每页10条，显示第2页", expected_action="employee.search", expected_statuses=(CapabilityStatus.SUCCESS,), expected_fields=("contact_address",), expected_operators=("contains",), minimum_rows=1, expected_page=2),
        LiveCase(case_id="UAT-EMP-208", question="查询具备金融风控经验的员工", expected_action="employee.semantic_search", expected_statuses=(CapabilityStatus.SUCCESS,), minimum_rows=1),
        LiveCase(case_id="UAT-EMP-209", question="查询员工的workBaseAf等于上海", expected_action=None, expected_statuses=(CapabilityStatus.UNSUPPORTED, CapabilityStatus.INVALID_ARGUMENT)),
        LiveCase(case_id="UAT-EMP-210", question="按语义搜索金融风控经验并限定上海员工", expected_action=None, expected_statuses=(CapabilityStatus.UNSUPPORTED, CapabilityStatus.INVALID_ARGUMENT)),
        LiveCase(case_id="UAT-EMP-211", question="帮我查一下在上海的员工", expected_action="employee.search", expected_statuses=(CapabilityStatus.SUCCESS,), principal="viewer", expected_fields=("contact_address",), expected_operators=("contains",), minimum_rows=1),
        LiveCase(case_id="UAT-EMP-212", question="帮我查一下在上海的员工", expected_action="employee.search", expected_statuses=(CapabilityStatus.FORBIDDEN,), principal="denied", expected_fields=("contact_address",), expected_operators=("contains",)),
        LiveCase(case_id="UAT-TXN-201", question=f"查询交易类型等于{transaction_type}的交易", expected_action="transaction.search", expected_statuses=(CapabilityStatus.SUCCESS,), expected_fields=("trans_type",), expected_operators=("eq",), minimum_rows=1),
        LiveCase(case_id="UAT-TXN-202", question=f"查询交易类型包含{type_fragment}的交易", expected_action="transaction.search", expected_statuses=(CapabilityStatus.SUCCESS,), expected_fields=("trans_type",), expected_operators=("contains",), minimum_rows=1),
        LiveCase(case_id="UAT-TXN-203", question="查询交易时间晚于2020-01-01T00:00:00+08:00的交易", expected_action="transaction.search", expected_statuses=(CapabilityStatus.SUCCESS, CapabilityStatus.NO_RESULT), expected_fields=("trans_date",), expected_operators=("gt",)),
        LiveCase(case_id="UAT-TXN-205", question="查询交易金额大于0.01的交易", expected_action="transaction.search", expected_statuses=(CapabilityStatus.SUCCESS, CapabilityStatus.NO_RESULT), expected_fields=("amount",), expected_operators=("gt",)),
        LiveCase(case_id="UAT-TXN-206", question="查询交易金额大于0.01且小于999999.99的交易", expected_action="transaction.search", expected_statuses=(CapabilityStatus.SUCCESS, CapabilityStatus.NO_RESULT), expected_fields=("amount", "amount"), expected_operators=("gt", "lt")),
        LiveCase(case_id="UAT-TXN-208", question=f"查询交易类型等于{transaction_type}的交易，每页10条，显示第2页", expected_action="transaction.search", expected_statuses=(CapabilityStatus.SUCCESS, CapabilityStatus.NO_RESULT), expected_fields=("trans_type",), expected_operators=("eq",), expected_page=2),
        LiveCase(case_id="UAT-TXN-212", question="查询今天发生的交易", expected_action=None, expected_statuses=(CapabilityStatus.UNSUPPORTED, CapabilityStatus.INVALID_ARGUMENT)),
        LiveCase(case_id="UAT-TXN-213", question="查询交易金额大于0.01的交易", expected_action="transaction.search", expected_statuses=(CapabilityStatus.FORBIDDEN,), principal="denied", expected_fields=("amount",), expected_operators=("gt",)),
        LiveCase(case_id="UAT-TXN-215", question="汇总所有交易的总金额", expected_action=None, expected_statuses=(CapabilityStatus.UNSUPPORTED, CapabilityStatus.INVALID_ARGUMENT)),
    )


@dataclass(slots=True)
class LiveMetrics:
    model_calls: int = 0
    employee_search: int = 0
    employee_semantic: int = 0
    transaction_search: int = 0
    forbidden_fields: int = 0
    observations: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = field(default_factory=dict)
    pages: dict[str, int] = field(default_factory=dict)

    def domain_total(self) -> int:
        return self.employee_search + self.employee_semantic + self.transaction_search


class QueryPlanGenerator(Protocol):
    async def generate(
        self, input: BusinessQueryPlanTaskInput, *, context: ModelCallContext
    ) -> JsonObject: ...


class CountingPlanGenerator:
    def __init__(
        self, delegate: QueryPlanGenerator, *, metrics: LiveMetrics, budget: int,
        secret_values: tuple[str, ...],
    ) -> None:
        self._delegate = delegate
        self._metrics = metrics
        self._budget = budget
        self._secrets = tuple(value for value in secret_values if value)

    async def generate(
        self, input: BusinessQueryPlanTaskInput, *, context: ModelCallContext
    ) -> JsonObject:
        case_id = _ACTIVE_CASE.get()
        if _CASE_ID.fullmatch(case_id) is None:
            raise AssertionError("business_list_live.case_scope_invalid")
        if any(value in input.minimized_question for value in self._secrets):
            self._metrics.forbidden_fields += 1
            raise AssertionError("business_list_live.sensitive_model_input")
        if self._metrics.model_calls >= self._budget or case_id in self._metrics.observations:
            raise AssertionError("business_list_live.model_budget_exceeded")
        self._metrics.model_calls += 1
        response = await self._delegate.generate(input, context=context)
        action = response.get("action")
        arguments = response.get("arguments")
        fields: tuple[str, ...] = ()
        operators: tuple[str, ...] = ()
        if isinstance(arguments, Mapping):
            page = arguments.get("page")
            if type(page) is int:
                self._metrics.pages[case_id] = page
            filters = arguments.get("filters")
            if isinstance(filters, tuple):
                fields = tuple(str(item.get("field", "")) for item in filters if isinstance(item, Mapping))
                operators = tuple(str(item.get("operator", "")) for item in filters if isinstance(item, Mapping))
        self._metrics.observations[case_id] = (str(action), fields, operators)
        return response


class CountingDomainTransport:
    def __init__(
        self, delegate: FakeDomainTransport, *, metrics: LiveMetrics,
        allowed_paths: frozenset[str],
    ) -> None:
        self._delegate = delegate
        self._metrics = metrics
        self._allowed_paths = allowed_paths

    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        if request.request.method != "POST" or request.request.relative_path not in self._allowed_paths:
            raise AssertionError("business_list_live.forbidden_endpoint")
        counter = _ALLOWED_PATHS[request.request.relative_path]
        if counter == "employeeSearch":
            self._metrics.employee_search += 1
        elif counter == "employeeSemantic":
            self._metrics.employee_semantic += 1
        else:
            self._metrics.transaction_search += 1
        return await self._delegate.send(request)

    async def aclose(self) -> None:
        await self._delegate.aclose()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_manifest(value: object) -> dict[str, object]:
    if type(value) is not dict:
        raise ValueError("business_list_live.manifest_invalid")
    manifest = cast(dict[str, object], value)
    if set(manifest) != {
        "schemaVersion", "taskVersion", "promptSha256", "configurationSha256",
        "endpoints", "budgets", "controlledCaseIds", "uatCaseIds",
    }:
        raise ValueError("business_list_live.manifest_invalid")
    expected_uat = uat_cases(
        transaction_type="SYNTHETIC", employee_identifier="SYNTHETIC12345"
    )
    expected = {
        "schemaVersion": 1,
        "taskVersion": BUSINESS_QUERY_PLAN_TASK_VERSION,
        "promptSha256": hashlib.sha256(
            BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION.encode("utf-8")
        ).hexdigest(),
        "configurationSha256": _sha256(_CONFIG),
        "endpoints": {
            "employee": "http://127.0.0.1:9210",
            "transaction": "http://127.0.0.1:8182",
        },
        "budgets": {"controlled": len(controlled_cases()), "uat": len(expected_uat)},
        "controlledCaseIds": [case.case_id for case in controlled_cases()],
        "uatCaseIds": [case.case_id for case in expected_uat],
    }
    if manifest != expected:
        raise ValueError("business_list_live.manifest_invalid")
    return manifest


def validate_evidence(value: object, *, stage: str, allow_failed: bool = False) -> None:
    if type(value) is not dict:
        raise ValueError("business_list_live.evidence_invalid")
    evidence = cast(dict[str, object], value)
    if set(evidence) != {
        "schemaVersion", "workPackage", "stage", "status", "modelTaskVersion",
        "promptSha256", "configurationSha256", "cases", "counts", "security",
    }:
        raise ValueError("business_list_live.evidence_invalid")
    expected_work_package = (
        "WP-BQ-CONTROLLED-LIVE-02" if stage == "controlled" else "WP-BQ-UAT-HANDOFF-02"
    )
    if (
        evidence.get("schemaVersion") != 2
        or evidence.get("stage") != stage
        or evidence.get("workPackage") != expected_work_package
        or evidence.get("status") not in ({"passed", "failed"} if allow_failed else {"passed"})
        or evidence.get("modelTaskVersion") != BUSINESS_QUERY_PLAN_TASK_VERSION
        or evidence.get("configurationSha256") != _sha256(_CONFIG)
        or evidence.get("promptSha256")
        != hashlib.sha256(BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION.encode()).hexdigest()
    ):
        raise ValueError("business_list_live.evidence_identity_invalid")
    cases = evidence.get("cases")
    counts = evidence.get("counts")
    security = evidence.get("security")
    if (
        type(cases) is not list
        or type(counts) is not dict
        or type(security) is not dict
        or set(counts) != {
            "modelQueryPlan", "employeeSearch", "employeeSemantic", "transactionSearch",
            "otherBusinessEndpoints", "answerGeneration", "knowledge", "retry", "resume",
        }
        or set(security) != {"forbiddenFields", "sensitivePersistence"}
        or any(type(item) is not int or item < 0 for item in counts.values())
        or security != {"forbiddenFields": 0, "sensitivePersistence": False}
        or any(counts[item] != 0 for item in (
            "otherBusinessEndpoints", "answerGeneration", "knowledge", "retry", "resume"
        ))
    ):
        raise ValueError("business_list_live.evidence_counts_invalid")
    case_ids: set[str] = set()
    model_total = 0
    domain_total = 0
    for item in cases:
        if type(item) is not dict or set(item) != {
            "caseId", "status", "capabilityId", "modelCalls", "domainCalls",
            "fields", "operators", "rowCount",
        }:
            raise ValueError("business_list_live.evidence_case_invalid")
        case_id = item.get("caseId")
        if (
            type(case_id) is not str
            or _CASE_ID.fullmatch(case_id) is None
            or case_id in case_ids
            or type(item.get("modelCalls")) is not int
            or item["modelCalls"] not in {0, 1}
            or type(item.get("domainCalls")) is not int
            or item["domainCalls"] not in {0, 1}
            or type(item.get("rowCount")) is not int
            or item["rowCount"] < 0
            or type(item.get("fields")) is not list
            or type(item.get("operators")) is not list
            or any(type(field) is not str for field in item["fields"])
            or any(operator not in {"eq", "contains", "prefix", "in", "gt", "lt"}
                   for operator in item["operators"])
        ):
            raise ValueError("business_list_live.evidence_case_invalid")
        case_ids.add(case_id)
        model_total += item["modelCalls"]
        domain_total += item["domainCalls"]
    if (
        model_total != counts["modelQueryPlan"]
        or domain_total != counts["employeeSearch"] + counts["employeeSemantic"] + counts["transactionSearch"]
        or counts["modelQueryPlan"] > (6 if stage == "controlled" else 18)
    ):
        raise ValueError("business_list_live.evidence_counts_invalid")


def _scope(*, case: LiveCase, jwt: str) -> RequestExecutionScope:
    original = scope(case.question, deadline_monotonic=asyncio.get_running_loop().time() + 25.0).context
    return RequestExecutionScope(context=replace(
        original, request_id=f"request-{case.case_id}", correlation_id=case.case_id,
        user_token=OpaqueUserToken.from_raw(jwt),
    ))


def _row_count(result: Mapping[str, object] | None) -> int:
    if result is None:
        return 0
    rows = result.get("records")
    return len(rows) if isinstance(rows, (tuple, list)) else 0


def _evidence(
    *, stage: str, observations: list[dict[str, object]], metrics: LiveMetrics, status: str
) -> dict[str, object]:
    return {
        "schemaVersion": 2,
        "workPackage": "WP-BQ-CONTROLLED-LIVE-02" if stage == "controlled" else "WP-BQ-UAT-HANDOFF-02",
        "stage": stage,
        "status": status,
        "modelTaskVersion": BUSINESS_QUERY_PLAN_TASK_VERSION,
        "promptSha256": hashlib.sha256(BUSINESS_QUERY_PLAN_SYSTEM_INSTRUCTION.encode()).hexdigest(),
        "configurationSha256": _sha256(_CONFIG),
        "cases": observations,
        "counts": {
            "modelQueryPlan": metrics.model_calls,
            "employeeSearch": metrics.employee_search,
            "employeeSemantic": metrics.employee_semantic,
            "transactionSearch": metrics.transaction_search,
            "otherBusinessEndpoints": 0,
            "answerGeneration": 0,
            "knowledge": 0,
            "retry": 0,
            "resume": 0,
        },
        "security": {"forbiddenFields": metrics.forbidden_fields, "sensitivePersistence": False},
    }


async def run_cases(
    *, cases: tuple[LiveCase, ...], stage: str, model: QueryPlanGenerator,
    runtime: ModelContextBindingRuntimeInvoker, metrics: LiveMetrics,
    principals: Mapping[str, str], evidence_path: Path,
) -> dict[str, object]:
    del model
    observations: list[dict[str, object]] = []
    failure: Exception | None = None
    try:
        for case in cases:
            if case.principal not in principals:
                raise RuntimeError("business_list_live.principal_missing")
            before_model = metrics.model_calls
            before_domain = metrics.domain_total()
            token = _ACTIVE_CASE.set(case.case_id)
            try:
                result = await runtime.ainvoke(question=case.question, scope=_scope(case=case, jwt=principals[case.principal]))
            finally:
                _ACTIVE_CASE.reset(token)
            model_calls = metrics.model_calls - before_model
            domain_calls = metrics.domain_total() - before_domain
            planned = metrics.observations.get(case.case_id, ("", (), ()))
            row_count = _row_count(cast(Mapping[str, object] | None, result.user_result))
            observation: dict[str, object] = {
                "caseId": case.case_id,
                "status": result.status.value,
                "capabilityId": result.capability_id,
                "modelCalls": model_calls,
                "domainCalls": domain_calls,
                "fields": list(planned[1]),
                "operators": list(planned[2]),
                "rowCount": row_count,
            }
            observations.append(observation)
            expected_domain_calls = 0 if case.expected_action is None else 1
            if (
                result.status not in case.expected_statuses
                or result.capability_id != case.expected_action
                or model_calls != case.expected_model_calls
                or domain_calls != expected_domain_calls
                or case.expected_fields and planned[1] != case.expected_fields
                or case.expected_operators and planned[2] != case.expected_operators
                or row_count < case.minimum_rows
                or case.expected_page is not None
                and metrics.pages.get(case.case_id) != case.expected_page
            ):
                raise RuntimeError(f"business_list_live.case_failed:{case.case_id}")
            if case.expected_action is not None and case.expected_action.startswith("employee."):
                rows = result.user_result.get("records", ()) if result.user_result is not None else ()
                if isinstance(rows, (tuple, list)) and any(
                    not isinstance(row, Mapping)
                    or not isinstance(row.get("fields"), Mapping)
                    or not set(cast(Mapping[str, object], row["fields"])).issubset(
                        _ALLOWED_EMPLOYEE_RESULT_FIELDS
                    )
                    for row in rows
                ):
                    metrics.forbidden_fields += 1
                    raise RuntimeError("business_list_live.result_projection_invalid")
    except Exception as exc:
        failure = exc
    finally:
        await runtime.aclose()
        evidence = _evidence(stage=stage, observations=observations, metrics=metrics, status="failed" if failure else "passed")
        validate_evidence(evidence, stage=stage, allow_failed=True)
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        with evidence_path.open("x", encoding="utf-8") as stream:
            json.dump(evidence, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    if failure is not None:
        raise failure
    return evidence


def build_runtime(
    *, metrics: LiveMetrics, cases: tuple[LiveCase, ...], principals: Mapping[str, str],
    employee_identifier: str, environ: Mapping[str, str],
) -> tuple[ModelContextBindingRuntimeInvoker, QueryPlanGenerator]:
    settings = ModelSettings.from_env(environ)
    if settings.provider is not ModelProvider.DEEPSEEK:
        raise ValueError("business_list_live.deepseek_required")
    active_model = LocalModelCompositionRoot.build(settings=settings, grounding_policies={})
    secrets = (*principals.values(), employee_identifier, environ.get("LLM_API_KEY", ""))
    counted = CountingPlanGenerator(
        active_model.business_query_plan_generator,
        metrics=metrics,
        budget=sum(case.expected_model_calls for case in cases),
        secret_values=secrets,
    )
    configured_model = replace(
        active_model,
        business_query_plan_generator=cast(BusinessQueryPlanGenerator, counted),
    )
    employee = CountingDomainTransport(
        HttpxBusinessDomainTransport(
            base_endpoint="http://127.0.0.1:9210",
            allowed_paths=frozenset({"/employees/es/search", "/employees/es/vector-search"}),
            max_response_bytes=1048576,
        ),
        metrics=metrics,
        allowed_paths=frozenset({"/employees/es/search", "/employees/es/vector-search"}),
    )
    transaction = CountingDomainTransport(
        HttpxBusinessDomainTransport(
            base_endpoint="http://127.0.0.1:8182",
            allowed_paths=frozenset({"/txn/search"}),
            max_response_bytes=1048576,
        ),
        metrics=metrics,
        allowed_paths=frozenset({"/txn/search"}),
    )
    return BusinessQueryRuntimeCompositionRoot.build(
        model=configured_model,
        employee_transport=employee,
        transaction_transport=transaction,
        employee_endpoint="http://127.0.0.1:9210",
        transaction_endpoint="http://127.0.0.1:8182",
    ), counted


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("controlled", "uat"), required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    selected = parser.parse_args()
    env = os.environ
    if env.get("RUN_BUSINESS_LIST_LIVE") != "1":
        raise RuntimeError("business_list_live.not_enabled")
    validate_manifest(json.loads(_MANIFEST.read_text(encoding="utf-8")))
    if selected.evidence.exists():
        raise RuntimeError("business_list_live.evidence_exists")
    principals = {
        "admin": env.get("BUSINESS_LIST_ADMIN_JWT", ""),
        "viewer": env.get("BUSINESS_LIST_VIEWER_JWT", ""),
        "denied": env.get("BUSINESS_LIST_DENIED_JWT", ""),
    }
    if any(not value for value in principals.values()):
        raise RuntimeError("business_list_live.principal_missing")
    identifier = env.get("BUSINESS_LIST_EMPLOYEE_IDENTIFIER", "")
    transaction_type = env.get("BUSINESS_LIST_TRANSACTION_TYPE", "")
    cases = controlled_cases() if selected.stage == "controlled" else uat_cases(
        transaction_type=transaction_type, employee_identifier=identifier
    )
    metrics = LiveMetrics()
    runtime, model = build_runtime(
        metrics=metrics, cases=cases, principals=principals,
        employee_identifier=identifier, environ=env,
    )
    evidence = await run_cases(
        cases=cases, stage=selected.stage, model=model, runtime=runtime,
        metrics=metrics, principals=principals, evidence_path=selected.evidence,
    )
    print(json.dumps({"status": evidence["status"], "cases": len(cases), "counts": evidence["counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
