from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from agent_runtime.bootstrap import BusinessQueryRuntimeCompositionRoot, LocalModelCompositionRoot
from agent_runtime.business.http_client import FakeDomainHttpRequest, FakeDomainHttpResponse
from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.model.contracts import BusinessQueryPlanGenerator, ModelProviderFailureKind
from agent_runtime.model.settings import ModelSettings
from tests.system_e2e.business_list_live import (
    CountingDomainTransport,
    CountingPlanGenerator,
    LiveCase,
    LiveMetrics,
    controlled_cases,
    run_cases,
    uat_cases,
    validate_evidence,
    validate_manifest,
)
from tests.system_e2e.test_business_list_query_nonlive import (
    _ADMIN_TOKEN,
    _DENIED_TOKEN,
    _EMPLOYEE_PLAN,
    _EmployeeServer,
    _PlanTransport,
    _TransactionServer,
    _filters_plan,
)


def _fake_cases() -> tuple[LiveCase, ...]:
    return controlled_cases()


def _plans() -> dict[str, dict[str, Any] | str | ModelProviderFailureKind]:
    return {
        "帮我查一下在上海的员工": _EMPLOYEE_PLAN,
        "查询具备金融风控经验的员工": {
            "domain": "employee", "action": "employee.semantic_search",
            "arguments": {"query": {"literal": "金融风控经验"}, "size": 20},
        },
        "查询金额大于0.01的交易": _filters_plan(
            "transaction", "transaction.search", "amount", "gt", "0.01"
        ),
        "查询员工的workBaseSi等于上海": {
            "domain": "employee", "action": "unsupported", "arguments": {},
        },
    }


class _PagedEmployeeServer(_EmployeeServer):
    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        response = await super().send(request)
        if response.status_code != 200 or request.request.json_body is None:
            return response
        body = json.loads(request.request.json_body.content)
        offset = body.get("from", 0)
        if offset == 0:
            return response
        value = json.loads(response.body)
        value["hits"]["total"]["value"] = offset + 1
        return replace(response, body=json.dumps(value, ensure_ascii=False).encode("utf-8"))


class _PagedTransactionServer(_TransactionServer):
    async def send(self, request: FakeDomainHttpRequest) -> FakeDomainHttpResponse:
        response = await super().send(request)
        if response.status_code != 200 or request.request.json_body is None:
            return response
        body = json.loads(request.request.json_body.content)
        page = body.get("page", 1)
        size = body.get("size", 20)
        if page == 1 and size == 20:
            return response
        value = json.loads(response.body)
        value["page"] = page
        value["size"] = size
        value["total"] = (page - 1) * size + 1
        return replace(response, body=json.dumps(value).encode("utf-8"))


@pytest.mark.asyncio
async def test_controlled_runner_uses_real_production_composition_and_strict_fake_budget(
    tmp_path: Path,
) -> None:
    cases = _fake_cases()
    metrics = LiveMetrics()
    transport = _PlanTransport(_plans())
    raw_model = LocalModelCompositionRoot.build(
        settings=ModelSettings(), transport=transport, grounding_policies={}
    )
    generator = CountingPlanGenerator(
        raw_model.business_query_plan_generator,
        metrics=metrics,
        budget=6,
        secret_values=(_ADMIN_TOKEN, _DENIED_TOKEN, "synthetic-secret-key"),
    )
    model = replace(
        raw_model,
        business_query_plan_generator=cast(BusinessQueryPlanGenerator, generator),
    )
    employee = CountingDomainTransport(
        _EmployeeServer(), metrics=metrics,
        allowed_paths=frozenset({"/employees/es/search", "/employees/es/vector-search"}),
    )
    transaction = CountingDomainTransport(
        _TransactionServer(), metrics=metrics, allowed_paths=frozenset({"/txn/search"}),
    )
    runtime = BusinessQueryRuntimeCompositionRoot.build(
        model=model, employee_transport=employee, transaction_transport=transaction,
        employee_endpoint="http://127.0.0.1:9210",
        transaction_endpoint="http://127.0.0.1:8182",
    )
    output = tmp_path / "controlled.json"
    result = await run_cases(
        cases=cases, stage="controlled", model=generator, runtime=runtime,
        metrics=metrics,
        principals={"admin": _ADMIN_TOKEN, "viewer": _ADMIN_TOKEN, "denied": _DENIED_TOKEN},
        evidence_path=output,
    )

    assert result["status"] == "passed"
    assert result["counts"] == {
        "modelQueryPlan": 6,
        "employeeSearch": 2,
        "employeeSemantic": 1,
        "transactionSearch": 2,
        "otherBusinessEndpoints": 0,
        "answerGeneration": 0,
        "knowledge": 0,
        "retry": 0,
        "resume": 0,
    }
    raw = output.read_text(encoding="utf-8")
    assert _ADMIN_TOKEN not in raw
    assert _DENIED_TOKEN not in raw
    assert "上海" not in raw
    assert len(transport.requests) == 6
    validate_evidence(result, stage="controlled")


def test_manifest_freezes_only_task_configuration_cases_and_bounded_budgets() -> None:
    path = Path(__file__).with_name("business_list_live_manifest_v2.json")
    manifest = validate_manifest(json.loads(path.read_text(encoding="utf-8")))
    assert manifest["budgets"] == {"controlled": 6, "uat": 18}
    modified = dict(manifest)
    modified["promptSha256"] = "0" * 64
    with pytest.raises(ValueError, match="business_list_live.manifest_invalid"):
        validate_manifest(modified)


def test_controlled_failures_are_immutable_and_retry_uses_an_independent_path() -> None:
    root = Path(__file__).resolve().parents[3]
    historical = root / "agent-runtime/tests/system_e2e/live/results/business-list-v2-controlled.result.json"
    assert hashlib.sha256(historical.read_bytes()).hexdigest() == (
        "fdc37b16e45d58733ede0a468e90b4db5242de8c84bcda7cca18ef07bd368607"
    )
    evidence = json.loads(historical.read_text(encoding="utf-8"))
    assert evidence["status"] == "failed"
    assert evidence["cases"] == [{
        "capabilityId": "employee.search", "caseId": "LIVE-EMP-001",
        "domainCalls": 1, "fields": ["contact_address"], "modelCalls": 1,
        "operators": ["contains"], "rowCount": 0, "status": "forbidden",
    }]
    assert evidence["counts"]["modelQueryPlan"] == 1
    assert evidence["counts"]["employeeSearch"] == 1

    second = root / "agent-runtime/tests/system_e2e/live/results/business-list-v2-controlled-run02.result.json"
    assert hashlib.sha256(second.read_bytes()).hexdigest() == (
        "121814993c53c2f0b4910bb5efe8b35bfe3da65dc395bd3270aa1c57b6eb5a08"
    )
    second_evidence = json.loads(second.read_text(encoding="utf-8"))
    assert second_evidence["status"] == "failed"
    assert second_evidence["cases"] == [{
        "capabilityId": "employee.search", "caseId": "LIVE-EMP-001",
        "domainCalls": 1, "fields": ["contact_address"], "modelCalls": 1,
        "operators": ["contains"], "rowCount": 0, "status": "downstream_failure",
    }]
    assert second_evidence["counts"]["modelQueryPlan"] == 1
    assert second_evidence["counts"]["employeeSearch"] == 1

    third = root / "agent-runtime/tests/system_e2e/live/results/business-list-v2-controlled-run03.result.json"
    assert hashlib.sha256(third.read_bytes()).hexdigest() == (
        "737d76c296d7803618f74c370a4478b73e2a65a3bbec66ffee3d2d577b4a467d"
    )
    third_evidence = json.loads(third.read_text(encoding="utf-8"))
    assert third_evidence["status"] == "failed"
    assert [case["status"] for case in third_evidence["cases"]] == ["success", "timeout"]
    assert third_evidence["cases"][0]["rowCount"] == 20
    assert third_evidence["counts"]["modelQueryPlan"] == 2
    assert third_evidence["counts"]["employeeSearch"] == 1
    assert third_evidence["counts"]["employeeSemantic"] == 1

    launcher = root / "agent-runtime/scripts/run-business-list-live.ps1"
    source = launcher.read_text(encoding="utf-8")
    assert "business-list-v2-controlled-run04.result.json" in source
    assert "business-list-v2-uat.result.json" in source
    assert "spring.cloud.discovery.client.simple.instances.es-query-service[0].uri=http://127.0.0.1:9201" in source
    assert "[switch]$DownstreamOnly" in source
    assert "[switch]$SemanticOnly" in source

    historical_manifest = root / "agent-runtime/tests/system_e2e/business_list_live_manifest.json"
    assert hashlib.sha256(historical_manifest.read_bytes()).hexdigest() == (
        "974228e060383324255a393d3f1107506510b515d0577b44c2671ea24d3a7d90"
    )
    assert json.loads(historical_manifest.read_text(encoding="utf-8"))["configurationSha256"] == (
        "55352c6c2f91b01f5faba42b48eb80bbae143a11b846bd7fb5ec5ca3a76c1601"
    )


def test_uat_catalog_covers_three_live_actions_and_safe_zero_call_boundaries() -> None:
    cases = uat_cases(transaction_type="SYNTHETIC", employee_identifier="SYNTHETIC12345")
    assert len(cases) == 18
    assert len({case.case_id for case in cases}) == len(cases)
    assert {case.expected_action for case in cases} == {
        "employee.search", "employee.semantic_search", "transaction.search", None,
    }
    assert all(case.expected_model_calls == 1 for case in cases)
    assert any(case.principal == "viewer" for case in cases)
    assert any(case.principal == "denied" for case in cases)
    assert all(
        case.expected_action is None
        for case in cases
        if case.case_id in {"UAT-EMP-209", "UAT-EMP-210", "UAT-TXN-212", "UAT-TXN-215"}
    )


@pytest.mark.asyncio
async def test_uat_runner_covers_all_eighteen_cases_with_fake_model_and_domain_servers(
    tmp_path: Path,
) -> None:
    identifier = "SYNTHETIC12345"
    transaction_type = "PAYMENT"
    cases = uat_cases(transaction_type=transaction_type, employee_identifier=identifier)
    plans: dict[str, dict[str, Any] | str | ModelProviderFailureKind] = {}
    for case in cases:
        question = case.question
        if case.case_id == "UAT-EMP-205":
            question = "查询员工，员工标识 protected-ref(slot-1)"
            plan: dict[str, Any] = {
                "domain": "employee", "action": "employee.search",
                "arguments": {
                    "filters": [{
                        "field": "employee_identifier", "operator": "eq",
                        "value": {"value_ref": "slot-1"},
                    }],
                    "page": 1, "size": 20, "sorts": [],
                },
            }
        elif case.expected_action is None:
            domain = "employee" if case.case_id.startswith("UAT-EMP") else "transaction"
            plan = {"domain": domain, "action": "unsupported", "arguments": {}}
        elif case.expected_action == "employee.semantic_search":
            plan = {
                "domain": "employee", "action": case.expected_action,
                "arguments": {"query": {"literal": "金融风控经验"}, "size": 20},
            }
        else:
            domain = "employee" if case.expected_action == "employee.search" else "transaction"
            field = case.expected_fields[0]
            operator = case.expected_operators[0]
            value: object = {
                "contact_address": "上海", "position": "工程", "trans_type": transaction_type,
                "trans_date": "2020-01-01T00:00:00+08:00", "amount": "0.01",
            }[field]
            plan = _filters_plan(domain, case.expected_action, field, operator, value)
            if case.expected_page is not None:
                plan["arguments"]["page"] = case.expected_page
                plan["arguments"]["size"] = 10
            if case.case_id == "UAT-TXN-206":
                plan["arguments"]["filters"].append({
                    "field": "amount", "operator": "lt", "value": {"literal": "999999.99"},
                })
        plans[question] = plan

    metrics = LiveMetrics()
    raw_model = LocalModelCompositionRoot.build(
        settings=ModelSettings(), transport=_PlanTransport(plans), grounding_policies={}
    )
    generator = CountingPlanGenerator(
        raw_model.business_query_plan_generator,
        metrics=metrics, budget=18,
        secret_values=(_ADMIN_TOKEN, _DENIED_TOKEN, identifier),
    )
    model = replace(
        raw_model, business_query_plan_generator=cast(BusinessQueryPlanGenerator, generator)
    )
    runtime = BusinessQueryRuntimeCompositionRoot.build(
        model=model,
        employee_transport=CountingDomainTransport(
            _PagedEmployeeServer(), metrics=metrics,
            allowed_paths=frozenset({"/employees/es/search", "/employees/es/vector-search"}),
        ),
        transaction_transport=CountingDomainTransport(
            _PagedTransactionServer(), metrics=metrics, allowed_paths=frozenset({"/txn/search"}),
        ),
        employee_endpoint="http://127.0.0.1:9210",
        transaction_endpoint="http://127.0.0.1:8182",
    )
    output = tmp_path / "uat.json"
    evidence = await run_cases(
        cases=cases, stage="uat", model=generator, runtime=runtime, metrics=metrics,
        principals={"admin": _ADMIN_TOKEN, "viewer": _ADMIN_TOKEN, "denied": _DENIED_TOKEN},
        evidence_path=output,
    )

    assert evidence["status"] == "passed"
    assert evidence["counts"] == {
        "modelQueryPlan": 18,
        "employeeSearch": 6,
        "employeeSemantic": 1,
        "transactionSearch": 7,
        "otherBusinessEndpoints": 0,
        "answerGeneration": 0,
        "knowledge": 0,
        "retry": 0,
        "resume": 0,
    }
    assert identifier not in output.read_text(encoding="utf-8")
    validate_evidence(evidence, stage="uat")


@pytest.mark.asyncio
async def test_controlled_failure_is_persisted_without_question_or_secrets(tmp_path: Path) -> None:
    selected = replace(
        controlled_cases()[0], expected_statuses=(CapabilityStatus.FORBIDDEN,)
    )
    metrics = LiveMetrics()
    raw_model = LocalModelCompositionRoot.build(
        settings=ModelSettings(), transport=_PlanTransport(_plans()), grounding_policies={}
    )
    generator = CountingPlanGenerator(
        raw_model.business_query_plan_generator,
        metrics=metrics, budget=1, secret_values=(_ADMIN_TOKEN,),
    )
    model = replace(
        raw_model, business_query_plan_generator=cast(BusinessQueryPlanGenerator, generator)
    )
    runtime = BusinessQueryRuntimeCompositionRoot.build(
        model=model,
        employee_transport=CountingDomainTransport(
            _EmployeeServer(), metrics=metrics,
            allowed_paths=frozenset({"/employees/es/search", "/employees/es/vector-search"}),
        ),
        transaction_transport=CountingDomainTransport(
            _TransactionServer(), metrics=metrics, allowed_paths=frozenset({"/txn/search"}),
        ),
        employee_endpoint="http://127.0.0.1:9210",
        transaction_endpoint="http://127.0.0.1:8182",
    )
    output = tmp_path / "failed.json"
    with pytest.raises(RuntimeError, match="business_list_live.case_failed:LIVE-EMP-001"):
        await run_cases(
            cases=(selected,), stage="controlled", model=generator, runtime=runtime,
            metrics=metrics, principals={"admin": _ADMIN_TOKEN}, evidence_path=output,
        )
    value = json.loads(output.read_text(encoding="utf-8"))
    assert value["status"] == "failed"
    assert value["counts"]["modelQueryPlan"] == 1
    assert value["counts"]["employeeSearch"] == 1
    assert "上海" not in output.read_text(encoding="utf-8")
    validate_evidence(value, stage="controlled", allow_failed=True)
