from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Final, Protocol, cast

from agent_runtime.adapters.http_transport import HttpxBusinessDomainTransport
from agent_runtime.bootstrap import (
    BusinessQueryRuntimeCompositionRoot,
    LocalModelComponents,
    LocalModelCompositionRoot,
)
from agent_runtime.business.http_client import (
    FakeDomainHttpRequest,
    FakeDomainHttpResponse,
    FakeDomainTransport,
)
from agent_runtime.capability_api.contracts import JsonObject, OpaqueUserToken
from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.model.context import ModelContextBindingRuntimeInvoker
from agent_runtime.model.contracts import (
    BusinessQueryPlanGenerator,
    BusinessQueryPlanTaskInput,
    ModelCallContext,
    canonical_object_json,
)
from agent_runtime.model.settings import ModelProvider, ModelSettings
from tests.helpers import scope
from tests.uat.employee_nl.contracts import (
    AUTHORIZATION_REFERENCE,
    CASE_COUNT,
    EMPLOYEE_SEARCH_BUDGET,
    MODEL_CALL_BUDGET,
    RUN_ID,
    EmployeeNaturalLanguageCase,
    append_json_line,
    cases,
    current_head,
    sha256_file,
    validate_authorization,
    validate_manifest,
    validate_result,
    write_exclusive_json,
)


_ACTIVE_CASE: ContextVar[str] = ContextVar("employee_nl_uat_active_case", default="")
_EMPLOYEE_PATH: Final = "/employees/es/search"
_FORBIDDEN_PLAN_TOKENS: Final = (
    "杨", "王", "欧阳", "杨明", "王芳", "明", "赵", "钱", "孙", "李",
    "周", "吴", "郑", "冯", "陈", "褚", "卫", "蒋", "沈", "韩", "朱",
)


class QueryPlanGenerator(Protocol):
    async def generate(
        self, input: BusinessQueryPlanTaskInput, *, context: ModelCallContext
    ) -> JsonObject: ...


@dataclass(slots=True)
class UatMetrics:
    model_calls: int = 0
    employee_search_calls: int = 0
    forbidden_plan_values: int = 0
    plans: dict[str, tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = field(
        default_factory=dict
    )
    protected_reference_diagnostics: dict[str, tuple[str, int]] = field(
        default_factory=dict
    )


class CountingPlanGenerator:
    def __init__(
        self,
        delegate: QueryPlanGenerator,
        *,
        metrics: UatMetrics,
        consumed_path: Path,
        lifecycle_path: Path,
        frozen_head: str,
        manifest_sha256: str,
    ) -> None:
        self._delegate = delegate
        self._metrics = metrics
        self._consumed_path = consumed_path
        self._lifecycle_path = lifecycle_path
        self._frozen_head = frozen_head
        self._manifest_sha256 = manifest_sha256

    async def generate(
        self, input: BusinessQueryPlanTaskInput, *, context: ModelCallContext
    ) -> JsonObject:
        case_id = _ACTIVE_CASE.get()
        if not case_id or case_id in self._metrics.plans:
            raise AssertionError("employee_nl_uat.model_call_scope_invalid")
        serialized_input = input.minimized_question
        if any(token in serialized_input for token in _FORBIDDEN_PLAN_TOKENS):
            self._metrics.forbidden_plan_values += 1
            raise AssertionError("employee_nl_uat.protected_value_model_leak")
        if self._metrics.model_calls >= MODEL_CALL_BUDGET:
            raise AssertionError("employee_nl_uat.model_budget_exceeded")
        if self._metrics.model_calls == 0:
            write_exclusive_json(
                self._consumed_path,
                {
                    "schemaVersion": 1,
                    "state": "consumed",
                    "runId": RUN_ID,
                    "authorizationReference": AUTHORIZATION_REFERENCE,
                    "frozenHead": self._frozen_head,
                    "manifestSha256": self._manifest_sha256,
                    "maximumModelCalls": MODEL_CALL_BUDGET,
                    "maximumEmployeeSearchCalls": EMPLOYEE_SEARCH_BUDGET,
                },
            )
            append_json_line(
                self._lifecycle_path,
                {
                    "schemaVersion": 1,
                    "runId": RUN_ID,
                    "event": "authorization_consumed",
                    "caseId": case_id,
                    "modelCalls": 0,
                },
            )
        self._metrics.model_calls += 1
        response = await self._delegate.generate(input, context=context)
        # Model output is an immutable JsonObject (mappingproxy/tuples).  Use the
        # shared canonical serializer rather than json.dumps, which cannot encode
        # the frozen container types and caused candidate-01 to fail after its
        # first successful provider response.
        serialized_output = canonical_object_json(response)
        if any(token in serialized_output for token in _FORBIDDEN_PLAN_TOKENS):
            self._metrics.forbidden_plan_values += 1
            raise AssertionError("employee_nl_uat.protected_value_plan_leak")
        self._metrics.protected_reference_diagnostics[case_id] = (
            _protected_reference_diagnostic(response, input.minimized_question)
        )
        action, fields, operators, shapes = _plan_shape(response)
        self._metrics.plans[case_id] = (action, fields, operators, shapes)
        return response


class CountingEmployeeTransport:
    def __init__(self, delegate: FakeDomainTransport, *, metrics: UatMetrics) -> None:
        self._delegate = delegate
        self._metrics = metrics
        self.closed = False

    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        if (
            request.request.method != "POST"
            or request.request.relative_path != _EMPLOYEE_PATH
        ):
            raise AssertionError("employee_nl_uat.forbidden_employee_endpoint")
        if self._metrics.employee_search_calls >= EMPLOYEE_SEARCH_BUDGET:
            raise AssertionError("employee_nl_uat.employee_budget_exceeded")
        self._metrics.employee_search_calls += 1
        return await self._delegate.send(request)

    async def aclose(self) -> None:
        await self._delegate.aclose()
        self.closed = True


class RejectingTransport:
    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        del request
        raise AssertionError("employee_nl_uat.forbidden_non_employee_call")

    async def aclose(self) -> None:
        return None


def _plan_shape(
    response: Mapping[str, object],
) -> tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    action = response.get("action")
    arguments = response.get("arguments")
    if type(action) is not str or not isinstance(arguments, Mapping):
        return "", (), (), ()
    raw_filters = arguments.get("filters")
    if type(raw_filters) is not tuple:
        return action, (), (), ()
    fields: list[str] = []
    operators: list[str] = []
    shapes: list[str] = []
    for raw in raw_filters:
        if not isinstance(raw, Mapping):
            continue
        fields.append(str(raw.get("field", "")))
        operators.append(str(raw.get("operator", "")))
        value = raw.get("value")
        shape = "invalid"
        if isinstance(value, Mapping):
            if set(value) == {"value_ref"}:
                shape = "value_ref"
            elif set(value) == {"value_refs"}:
                shape = "value_refs"
            elif set(value) == {"literal"}:
                shape = "literal_list" if type(value.get("literal")) is tuple else "literal"
        shapes.append(shape)
    return action, tuple(fields), tuple(operators), tuple(shapes)


def _protected_reference_diagnostic(
    response: Mapping[str, object], minimized_question: str
) -> tuple[str, int]:
    source_refs = tuple(
        re.findall(r"protected-ref\((slot-[1-9][0-9]{0,5})\)", minimized_question)
    )
    arguments = response.get("arguments")
    if not isinstance(arguments, Mapping):
        return ("not_observed", 0)
    raw_filters = arguments.get("filters")
    if type(raw_filters) is not tuple:
        return ("missing", 0) if source_refs else ("not_applicable", 0)
    output_refs: list[str] = []
    for raw_filter in raw_filters:
        if not isinstance(raw_filter, Mapping):
            continue
        value = raw_filter.get("value")
        if not isinstance(value, Mapping):
            continue
        if set(value) == {"value_ref"}:
            raw_ref = value.get("value_ref")
            if type(raw_ref) is not str:
                return ("malformed", len(output_refs))
            output_refs.append(raw_ref)
        elif set(value) == {"value_refs"}:
            raw_refs = value.get("value_refs")
            if type(raw_refs) is not tuple or any(type(item) is not str for item in raw_refs):
                return ("malformed", len(output_refs))
            output_refs.extend(cast(tuple[str, ...], raw_refs))
    if not source_refs and not output_refs:
        return ("not_applicable", 0)
    if any(ref.startswith("protected-ref(") for ref in output_refs):
        return ("wrapper", len(output_refs))
    if len(output_refs) != len(set(output_refs)):
        return ("duplicate", len(output_refs))
    if any(ref not in source_refs for ref in output_refs):
        return ("unknown", len(output_refs))
    if set(output_refs) != set(source_refs):
        return ("missing", len(output_refs))
    return ("valid", len(output_refs))


def _limited_failure_code(code: str | None) -> str | None:
    allowed = {
        "business.plan_context_missing",
        "business.plan_input_denied",
        "business.plan_internal_failure",
        "business.plan_invalid",
        "business.plan_model_denied",
        "business.plan_model_failure",
        "business.plan_model_timeout",
        "business.plan_registry_mismatch",
        "business.plan_snapshot_mismatch",
        "business.plan_unsupported",
        "business.protected_value_invalid",
        "core.downstream_failure",
        "core.forbidden",
        "core.invalid_argument",
    }
    if code is None:
        return None
    return code if code in allowed else "employee_nl_uat.other_failure"


def _plan_shape_matches(
    case: EmployeeNaturalLanguageCase,
    plan: tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]],
) -> bool:
    if case.expected_action is None:
        return True
    return plan == (
        case.expected_action,
        case.expected_fields,
        case.expected_operators,
        case.expected_value_shapes,
    )


def _execution_scope(case: EmployeeNaturalLanguageCase, *, jwt: str) -> RequestExecutionScope:
    original = scope(
        case.question,
        deadline_monotonic=asyncio.get_running_loop().time() + 30.0,
    ).context
    return RequestExecutionScope(
        context=replace(
            original,
            request_id=f"request-{case.case_id}",
            correlation_id=case.case_id,
            user_token=OpaqueUserToken.from_raw(jwt),
        )
    )


def _row_count(value: Mapping[str, object] | None) -> int:
    if value is None:
        return 0
    records = value.get("records")
    return len(records) if isinstance(records, (tuple, list)) else 0


def _limited_reason(error: BaseException | None) -> str | None:
    if error is None:
        return None
    message = str(error)
    allowed = {
        "employee_nl_uat.case_failed",
        "employee_nl_uat.model_call_scope_invalid",
        "employee_nl_uat.protected_value_model_leak",
        "employee_nl_uat.protected_value_plan_leak",
        "employee_nl_uat.model_budget_exceeded",
        "employee_nl_uat.employee_budget_exceeded",
        "employee_nl_uat.forbidden_employee_endpoint",
        "employee_nl_uat.forbidden_non_employee_call",
    }
    prefix = message.split(":", 1)[0]
    return prefix if prefix in allowed else "employee_nl_uat.unexpected_failure"


async def execute(
    *,
    repository: Path,
    manifest_path: Path,
    authorization_path: Path,
    result_root: Path,
    admin_jwt: str,
    denied_jwt: str,
    environ: Mapping[str, str],
) -> dict[str, object]:
    lifecycle_path = result_root / "lifecycle.jsonl"
    consumed_path = result_root / "authorization.consumed.json"
    journal_path = result_root / "attempts.jsonl"
    result_path = result_root / "result.json"
    if any(path.exists() for path in (lifecycle_path, consumed_path, journal_path, result_path)):
        raise RuntimeError("employee_nl_uat.run_already_started")
    frozen_head = current_head(repository)
    manifest_sha256 = sha256_file(manifest_path)
    manifest = validate_manifest(
        json.loads(manifest_path.read_text(encoding="utf-8")),
        repository=repository,
    )
    validate_authorization(
        json.loads(authorization_path.read_text(encoding="utf-8")),
        manifest_sha256=manifest_sha256,
        frozen_head=frozen_head,
    )
    source_head = cast(str, manifest["sourceHead"])
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", source_head, frozen_head],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    ).returncode != 0:
        raise RuntimeError("employee_nl_uat.source_head_invalid")
    configuration = cast(dict[str, object], manifest["configuration"])
    employee_base_url = cast(str, configuration["employeeBaseUrl"])
    result_root.mkdir(parents=True, exist_ok=True)
    append_json_line(
        lifecycle_path,
        {
            "schemaVersion": 1,
            "runId": RUN_ID,
            "event": "run_started",
            "frozenHead": frozen_head,
            "manifestSha256": manifest_sha256,
        },
    )
    metrics = UatMetrics()
    active_model: LocalModelComponents | None = None
    employee_transport: CountingEmployeeTransport | None = None
    runtime: ModelContextBindingRuntimeInvoker | None = None
    observations: list[dict[str, object]] = []
    failure: BaseException | None = None
    runtime_closed = False
    model_closed = False
    domain_closed = False
    active_case: EmployeeNaturalLanguageCase | None = None
    before_model = 0
    before_employee = 0
    try:
        settings = ModelSettings.from_env(environ)
        if settings.provider is not ModelProvider.DEEPSEEK:
            raise RuntimeError("employee_nl_uat.deepseek_required")
        active_model = LocalModelCompositionRoot.build(
            settings=settings, grounding_policies={}
        )
        counted_model = CountingPlanGenerator(
            active_model.business_query_plan_generator,
            metrics=metrics,
            consumed_path=consumed_path,
            lifecycle_path=lifecycle_path,
            frozen_head=frozen_head,
            manifest_sha256=manifest_sha256,
        )
        configured_model = replace(
            active_model,
            business_query_plan_generator=cast(
                BusinessQueryPlanGenerator, counted_model
            ),
        )
        employee_transport = CountingEmployeeTransport(
            HttpxBusinessDomainTransport(
                base_endpoint=employee_base_url,
                allowed_paths=frozenset({_EMPLOYEE_PATH}),
                max_response_bytes=1048576,
            ),
            metrics=metrics,
        )
        runtime = BusinessQueryRuntimeCompositionRoot.build(
            model=configured_model,
            employee_transport=employee_transport,
            transaction_transport=RejectingTransport(),
            employee_endpoint=employee_base_url,
            transaction_endpoint="http://127.0.0.1:8182",
        )
        principals = {"admin": admin_jwt, "denied": denied_jwt}
        for case in cases():
            active_case = case
            before_model = metrics.model_calls
            before_employee = metrics.employee_search_calls
            token = _ACTIVE_CASE.set(case.case_id)
            try:
                outcome = await runtime.ainvoke(
                    question=case.question,
                    scope=_execution_scope(case, jwt=principals[case.principal]),
                )
            finally:
                _ACTIVE_CASE.reset(token)
            model_calls = metrics.model_calls - before_model
            employee_calls = metrics.employee_search_calls - before_employee
            plan = metrics.plans.get(case.case_id, ("", (), (), ()))
            reference_diagnostic = metrics.protected_reference_diagnostics.get(
                case.case_id, ("not_observed", 0)
            )
            row_count = _row_count(cast(Mapping[str, object] | None, outcome.user_result))
            expected_reference_status = (
                "not_observed"
                if case.expected_model_calls == 0
                else (
                    "valid"
                    if case.expected_protected_reference_count > 0
                    else "not_applicable"
                )
            )
            plan_shape_matches = _plan_shape_matches(case, plan)
            passed = (
                outcome.status in case.expected_statuses
                and outcome.capability_id == case.expected_action
                and model_calls == case.expected_model_calls
                and employee_calls == case.expected_employee_calls
                and plan_shape_matches
                and reference_diagnostic
                == (
                    expected_reference_status,
                    case.expected_protected_reference_count,
                )
                and row_count >= case.minimum_rows
                and metrics.forbidden_plan_values == 0
            )
            observation: dict[str, object] = {
                "caseId": case.case_id,
                "inputClass": case.input_class,
                "status": outcome.status.value,
                "capabilityId": outcome.capability_id,
                "fields": list(plan[1]),
                "operators": list(plan[2]),
                "valueShapes": list(plan[3]),
                "protectedReferenceStatus": reference_diagnostic[0],
                "protectedReferenceCount": reference_diagnostic[1],
                "failureCode": _limited_failure_code(
                    None if outcome.failure is None else outcome.failure.code
                ),
                "modelCalls": model_calls,
                "employeeSearchCalls": employee_calls,
                "rowCount": row_count,
                "securityPassed": metrics.forbidden_plan_values == 0,
                "passed": passed,
            }
            observations.append(observation)
            append_json_line(journal_path, observation)
            if not passed:
                raise RuntimeError(f"employee_nl_uat.case_failed:{case.case_id}")
            active_case = None
    except BaseException as exc:
        failure = exc
        if active_case is not None and not any(
            item.get("caseId") == active_case.case_id for item in observations
        ):
            plan = metrics.plans.get(active_case.case_id, ("", (), (), ()))
            reference_diagnostic = metrics.protected_reference_diagnostics.get(
                active_case.case_id, ("not_observed", 0)
            )
            failed_observation: dict[str, object] = {
                "caseId": active_case.case_id,
                "inputClass": active_case.input_class,
                "status": "internal_failure",
                "capabilityId": None,
                "fields": list(plan[1]),
                "operators": list(plan[2]),
                "valueShapes": list(plan[3]),
                "protectedReferenceStatus": reference_diagnostic[0],
                "protectedReferenceCount": reference_diagnostic[1],
                "failureCode": "employee_nl_uat.runner_exception",
                "modelCalls": metrics.model_calls - before_model,
                "employeeSearchCalls": metrics.employee_search_calls - before_employee,
                "rowCount": 0,
                "securityPassed": metrics.forbidden_plan_values == 0,
                "passed": False,
            }
            observations.append(failed_observation)
            append_json_line(journal_path, failed_observation)
    finally:
        if runtime is not None:
            try:
                await runtime.aclose()
                runtime_closed = True
                model_closed = True
                domain_closed = True
            except BaseException as close_error:
                if failure is None:
                    failure = close_error
        elif active_model is not None:
            try:
                await active_model.aclose()
                model_closed = True
            except BaseException as close_error:
                if failure is None:
                    failure = close_error
            if employee_transport is not None:
                try:
                    await employee_transport.aclose()
                    domain_closed = True
                except BaseException as close_error:
                    if failure is None:
                        failure = close_error
        status = (
            "passed"
            if failure is None and len(observations) == CASE_COUNT
            else "failed_consumed"
            if consumed_path.exists()
            else "failed_unconsumed"
        )
        result = {
            "schemaVersion": 1,
            "status": status,
            "runId": RUN_ID,
            "authorizationReference": AUTHORIZATION_REFERENCE,
            "frozenHead": frozen_head,
            "manifestSha256": manifest_sha256,
            "cases": observations,
            "counts": {
                "modelCalls": metrics.model_calls,
                "employeeSearchCalls": metrics.employee_search_calls,
                "employeeSemantic": 0,
                "transaction": 0,
                "knowledge": 0,
                "answer": 0,
                "otherEmployeeEndpoints": 0,
                "retry": 0,
                "resume": 0,
            },
            "security": {
                "forbiddenPlanValues": metrics.forbidden_plan_values,
                "forbiddenPersistence": 0,
                "logLeakCount": 0,
            },
            "cleanup": {
                "runtimeClosed": runtime_closed,
                "modelClosed": model_closed,
                "domainClientClosed": domain_closed,
            },
            "failureReason": _limited_reason(failure),
        }
        validate_result(result)
        write_exclusive_json(result_path, result)
        append_json_line(
            lifecycle_path,
            {
                "schemaVersion": 1,
                "runId": RUN_ID,
                "event": "run_terminal",
                "status": status,
                "modelCalls": metrics.model_calls,
                "employeeSearchCalls": metrics.employee_search_calls,
            },
        )
    if failure is not None:
        raise failure
    return result


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--result-root", type=Path, required=True)
    selected = parser.parse_args()
    env = os.environ
    if env.get("RUN_EMPLOYEE_NL_UAT") != "1":
        raise RuntimeError("employee_nl_uat.not_enabled")
    admin = env.get("EMPLOYEE_NL_UAT_ADMIN_JWT", "")
    denied = env.get("EMPLOYEE_NL_UAT_DENIED_JWT", "")
    if not admin or not denied:
        raise RuntimeError("employee_nl_uat.principal_missing")
    result = await execute(
        repository=selected.repository.resolve(),
        manifest_path=selected.manifest.resolve(),
        authorization_path=selected.authorization.resolve(),
        result_root=selected.result_root.resolve(),
        admin_jwt=admin,
        denied_jwt=denied,
        environ=env,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "cases": len(cast(list[object], result["cases"])),
                "counts": result["counts"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
