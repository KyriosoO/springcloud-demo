from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from agent_runtime.capability_api.contracts import JsonObject
from agent_runtime.model.contracts import BusinessQueryPlanTaskInput, ModelCallContext
from tests.uat.employee_nl.contracts import (
    CASE_COUNT,
    EMPLOYEE_SEARCH_BUDGET,
    MODEL_CALL_BUDGET,
    cases,
    sha256_file,
    validate_manifest,
    validate_result,
)
from tests.uat.employee_nl.runner import CountingPlanGenerator, UatMetrics, _ACTIVE_CASE


_ROOT = Path(__file__).resolve().parents[4]
_MANIFEST = Path(__file__).with_name("evidence") / (
    "employee-natural-language-v1-20260828-candidate-01.manifest.json"
)


class _Generator:
    async def generate(
        self, input: BusinessQueryPlanTaskInput, *, context: ModelCallContext
    ) -> JsonObject:
        del input, context
        return {
            "domain": "employee",
            "action": "employee.search",
            "arguments": {
                "filters": (
                    {
                        "field": "chinese_name",
                        "operator": "prefix",
                        "value": {"value_ref": "slot-1"},
                    },
                ),
                "page": 1,
                "size": 20,
                "sorts": (),
            },
        }


def test_manifest_freezes_cases_budgets_and_all_asset_hashes() -> None:
    manifest = validate_manifest(
        json.loads(_MANIFEST.read_text(encoding="utf-8")),
        repository=_ROOT,
    )
    assert len(cast(list[object], manifest["cases"])) == CASE_COUNT
    assert sum(case.expected_model_calls for case in cases()) <= MODEL_CALL_BUDGET
    assert sum(case.expected_employee_calls for case in cases()) <= EMPLOYEE_SEARCH_BUDGET
    assert sha256_file(_MANIFEST) == sha256_file(_MANIFEST)


@pytest.mark.asyncio
async def test_first_model_outbound_consumes_once_and_never_records_protected_value(
    tmp_path: Path,
) -> None:
    metrics = UatMetrics()
    consumed = tmp_path / "authorization.consumed.json"
    lifecycle = tmp_path / "lifecycle.jsonl"
    generator = CountingPlanGenerator(
        _Generator(),
        metrics=metrics,
        consumed_path=consumed,
        lifecycle_path=lifecycle,
        frozen_head="0" * 40,
        manifest_sha256="1" * 64,
    )
    token = _ACTIVE_CASE.set("UAT-EMP-NL-301")
    try:
        output = await generator.generate(
            BusinessQueryPlanTaskInput(
                minimized_question="姓 protected-ref(slot-1) 的员工",
                catalog={"schema_version": 3, "snapshot_id": "2" * 64},
                catalog_snapshot_id="2" * 64,
            ),
            context=ModelCallContext(
                request_id="request-1", correlation_id="case-1", deadline_monotonic=1.0
            ),
        )
        assert output["action"] == "employee.search"
        assert consumed.is_file()
        assert metrics.model_calls == 1
        assert "杨" not in consumed.read_text(encoding="utf-8")
        with pytest.raises(AssertionError, match="model_call_scope_invalid"):
            await generator.generate(
                BusinessQueryPlanTaskInput(
                    minimized_question="姓 protected-ref(slot-1) 的员工",
                    catalog={"schema_version": 3, "snapshot_id": "2" * 64},
                    catalog_snapshot_id="2" * 64,
                ),
                context=ModelCallContext(
                    request_id="request-1", correlation_id="case-1", deadline_monotonic=1.0
                ),
            )
    finally:
        _ACTIVE_CASE.reset(token)


def test_result_schema_rejects_nonzero_forbidden_endpoints() -> None:
    result: dict[str, object] = {
        "schemaVersion": 1,
        "status": "failed_unconsumed",
        "runId": "employee-natural-language-v1-20260828-candidate-01",
        "authorizationReference": "P3_00:GATE-082",
        "frozenHead": "0" * 40,
        "manifestSha256": "1" * 64,
        "cases": [],
        "counts": {
            "modelCalls": 0,
            "employeeSearchCalls": 0,
            "employeeSemantic": 1,
            "transaction": 0,
            "knowledge": 0,
            "answer": 0,
            "otherEmployeeEndpoints": 0,
            "retry": 0,
            "resume": 0,
        },
        "security": {
            "forbiddenPlanValues": 0,
            "forbiddenPersistence": 0,
            "logLeakCount": 0,
        },
        "cleanup": {
            "runtimeClosed": False,
            "modelClosed": False,
            "domainClientClosed": False,
        },
        "failureReason": "employee_nl_uat.unexpected_failure",
    }
    with pytest.raises(ValueError, match="result_counts_invalid"):
        validate_result(result)
