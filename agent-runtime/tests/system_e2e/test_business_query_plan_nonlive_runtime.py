from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus, OpaqueUserToken
from agent_runtime.core.execution import RequestExecutionScope
from tests.helpers import scope
from tests.system_e2e.business_query_plan_evidence import (
    validate_business_query_plan_evidence,
    write_business_query_plan_evidence,
)
from tests.system_e2e.business_query_plan_runtime_server import (
    build_business_query_plan_nonlive_runtime,
)


_ADMIN = "synthetic-admin-token"
_DENIED = "synthetic-denied-token"


def _environment(tmp_path: Path) -> dict[str, str]:
    return {
        "AGENT_MODEL_PROVIDER": "stub",
        "BUSINESS_QUERY_PLAN_E2E_EVIDENCE_PATH": str(tmp_path / "evidence.json"),
        "BUSINESS_QUERY_PLAN_E2E_ADMIN_TOKEN": _ADMIN,
    }


def _scope(question: str, *, case_id: str, token: str) -> RequestExecutionScope:
    original = scope(question).context
    return RequestExecutionScope(context=replace(
        original,
        request_id=f"request-{case_id}",
        correlation_id=case_id,
        user_token=OpaqueUserToken.from_raw(token),
    ))


@pytest.mark.asyncio
async def test_business_query_plan_nonlive_matrix_is_single_action_and_fail_closed(
    tmp_path: Path,
) -> None:
    runtime = build_business_query_plan_nonlive_runtime(
        {**_environment(tmp_path), "LLM_API_KEY": "must-not-be-read"}
    )
    cases = (
        ("bq-nonlive-emp-ok", "查询员工详情 员工标识=ABCDE", _ADMIN, CapabilityStatus.SUCCESS, "employee.detail"),
        ("bq-nonlive-emp-deny", "查询员工详情 员工标识=ABCDE", _DENIED, CapabilityStatus.FORBIDDEN, "employee.detail"),
        ("bq-nonlive-txn-ok", "查询交易 金额=1.00", _ADMIN, CapabilityStatus.SUCCESS, "transaction.search"),
        ("bq-nonlive-txn-deny", "查询交易 金额=1.00", _DENIED, CapabilityStatus.FORBIDDEN, "transaction.search"),
        ("bq-nonlive-invalid", "查询交易 金额=1.000", _ADMIN, CapabilityStatus.INVALID_ARGUMENT, None),
        ("bq-nonlive-unsupported", "查询员工列表 工作地=上海", _ADMIN, CapabilityStatus.UNSUPPORTED, None),
        ("bq-nonlive-second", "查询员工 第二动作", _ADMIN, CapabilityStatus.INVALID_ARGUMENT, None),
        ("bq-nonlive-cross", "查询员工 跨域计划", _ADMIN, CapabilityStatus.UNSUPPORTED, None),
        ("bq-nonlive-timeout", "查询交易 模型超时", _ADMIN, CapabilityStatus.TIMEOUT, None),
        ("bq-nonlive-sensitive", "查询员工 联系电话 13800138000", _ADMIN, CapabilityStatus.FORBIDDEN, None),
    )

    for case_id, question, token, status, capability_id in cases:
        outcome = await runtime.ainvoke(
            question=question,
            scope=_scope(question, case_id=case_id, token=token),
        )
        assert outcome.status is status
        assert outcome.capability_id == capability_id
    await runtime.aclose()

    evidence_path = tmp_path / "evidence.json"
    raw = evidence_path.read_text(encoding="utf-8")
    evidence = json.loads(raw)
    validate_business_query_plan_evidence(evidence)
    assert evidence["status"] == "passed"
    assert evidence["requestCounts"] == {
        "queryPlanModel": 9,
        "otherModelTasks": 0,
        "employee": 2,
        "transaction": 2,
        "otherBusinessEndpoints": 0,
        "fallbackSelector": 0,
        "answerGeneration": 0,
        "externalModelOutbound": 0,
    }
    assert "ABCDE" not in raw
    assert "13800138000" not in raw
    assert _ADMIN not in raw
    assert _DENIED not in raw


def test_business_query_plan_nonlive_rejects_deepseek_and_evidence_extensions(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="business_query_plan_e2e.model_provider_must_be_stub"):
        build_business_query_plan_nonlive_runtime(
            {**_environment(tmp_path), "AGENT_MODEL_PROVIDER": "deepseek"}
        )
    invalid: dict[str, object] = {
        "schemaVersion": 1,
        "workPackage": "WP-BQ-QUERYPLAN-NONLIVE-E2E-01",
        "status": "passed",
        "providers": {"model": "fake", "employee": "fake", "transaction": "fake"},
        "cases": [],
        "requestCounts": {
            "queryPlanModel": 0,
            "otherModelTasks": 0,
            "employee": 0,
            "transaction": 0,
            "otherBusinessEndpoints": 0,
            "fallbackSelector": 0,
            "answerGeneration": 0,
            "externalModelOutbound": 0,
        },
        "security": {"sensitivePersistence": False, "logLeakCount": 0},
        "cleanup": {"runtimeClosed": True},
        "rawQuestion": "forbidden",
    }
    with pytest.raises(ValueError, match="business_query_plan_e2e.evidence_shape_invalid"):
        validate_business_query_plan_evidence(invalid)


def test_incomplete_business_query_plan_evidence_cannot_be_marked_passed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "incomplete.json"
    write_business_query_plan_evidence(
        path,
        cases={},
        request_counts={
            "queryPlanModel": 0,
            "otherModelTasks": 0,
            "employee": 0,
            "transaction": 0,
            "otherBusinessEndpoints": 0,
            "fallbackSelector": 0,
            "answerGeneration": 0,
            "externalModelOutbound": 0,
        },
        runtime_closed=True,
    )

    evidence = json.loads(path.read_text(encoding="utf-8"))
    validate_business_query_plan_evidence(evidence)
    assert evidence["status"] == "failed"
