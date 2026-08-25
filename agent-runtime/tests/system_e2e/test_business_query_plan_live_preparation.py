from __future__ import annotations

import copy
import json
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

import tests.system_e2e.business_query_plan_live_runner as live_runner
from agent_runtime.model.contracts import StructuredModelRequest, StructuredModelResponse
from agent_runtime.model.contracts import StructuredFinishKind
from tests.system_e2e.business_query_plan_live_contracts import (
    AUTHORIZATION_REFERENCE,
    EMPLOYEE_BASE_URL,
    MODEL_CALL_BUDGET,
    RUN_ID,
    TRANSACTION_BASE_URL,
    sha256_file,
    validate_authorization_template,
    validate_result,
)
from tests.system_e2e.business_query_plan_runtime_support import business_query_plan_snapshot_id
from tests.system_e2e.business_query_plan_live_runner import (
    CandidateMetrics,
    CandidatePaths,
    CandidateSecrets,
    FakeQueryPlanTransport,
    build_fake_dependencies,
    run_candidate,
    run_live_from_environment,
)


_SECRETS = CandidateSecrets(
    employee_identifier="ABCDE",
    admin_jwt="synthetic-admin.jwt.value",
    denied_jwt="synthetic-denied.jwt.value",
    model_api_key="synthetic-model-key",
)


def _paths(root: Path) -> CandidatePaths:
    return CandidatePaths(
        lifecycle=root / "lifecycle.jsonl",
        consumed=root / "authorization.consumed.json",
        journal=root / "model-attempts.jsonl",
        result=root / "result.json",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("live", [False, True])
async def test_fake_candidate_proves_exact_matrix_budget_and_first_outbound_consumption(
    tmp_path: Path,
    live: bool,
) -> None:
    metrics = CandidateMetrics()
    paths = _paths(tmp_path)
    dependencies = build_fake_dependencies(secrets=_SECRETS, metrics=metrics)
    assert dependencies.expected_snapshot_id == business_query_plan_snapshot_id(
        employee_endpoint=EMPLOYEE_BASE_URL,
        transaction_endpoint=TRANSACTION_BASE_URL,
    )
    result = await run_candidate(
        live=live,
        paths=paths,
        manifest_sha256="a" * 64,
        secrets=_SECRETS,
        dependencies=dependencies,
    )

    validate_result(result, require_passed=True)
    assert result["schemaVersion"] == 2
    assert result["failureCase"] is None
    assert result["runId"] == RUN_ID
    assert result["authorizationReference"] == AUTHORIZATION_REFERENCE
    assert result["counts"] == {
        "modelCalls": MODEL_CALL_BUDGET,
        "employeeDetail": 2,
        "transactionSearch": 2,
        "otherBusinessEndpoints": 0,
        "fallbackSelector": 0,
        "answerGeneration": 0,
        "knowledge": 0,
        "retry": 0,
        "resume": 0,
    }
    assert paths.consumed.exists() is live
    persisted = "".join(
        path.read_text(encoding="utf-8")
        for path in (paths.lifecycle, paths.journal, paths.result)
    )
    for forbidden in (
        _SECRETS.employee_identifier,
        _SECRETS.admin_jwt,
        _SECRETS.denied_jwt,
        _SECRETS.model_api_key,
    ):
        assert forbidden not in persisted


class _FailingTransport(FakeQueryPlanTransport):
    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        del request, call_deadline
        raise RuntimeError("raw provider failure must not persist")


class _CrossDomainTransport(FakeQueryPlanTransport):
    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        del request, call_deadline
        return StructuredModelResponse(
            finish_kind=StructuredFinishKind.STOP,
            content=(
                '{"domain":"transaction","action":"transaction.search",'
                '"arguments":{"amount":{"literal":"1.00"}}}'
            ),
            tool_calls=(),
            usage_total_tokens=0,
        )


class _TransactionDateVariantTransport(FakeQueryPlanTransport):
    def __init__(self, response: str) -> None:
        self._response = response

    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        if live_runner._ACTIVE_CASE.get() != "bq-live-txn-unsupported":
            return await super().complete(request, call_deadline=call_deadline)
        return StructuredModelResponse(
            finish_kind=StructuredFinishKind.STOP,
            content=self._response,
            tool_calls=(),
            usage_total_tokens=0,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "expected_terminal", "expected_status"),
    [
        (
            '{"domain":"transaction","action":"unsupported","arguments":{}}',
            "passed",
            "unsupported",
        ),
        (
            '{"domain":"transaction","action":"transaction.search",'
            '"arguments":{"date":{"literal":"2026-08-25"}}}',
            "passed",
            "unsupported",
        ),
        (
            '{"domain":"transaction","action":"transaction.search","arguments":{}}',
            "failed_consumed",
            "invalid_argument",
        ),
        (
            '{"domain":"transaction","action":"transaction.search",'
            '"arguments":{"date":"today"}}',
            "failed_consumed",
            "invalid_argument",
        ),
        (
            '{"domain":"transaction","action":"unsupported",'
            '"arguments":{"date":{"literal":"today"}}}',
            "failed_consumed",
            "invalid_argument",
        ),
    ],
    ids=("explicit-unsupported", "unopened-date-field", "empty-search", "invalid-argument-shape", "nonempty-unsupported"),
)
async def test_transaction_date_variants_remain_fail_closed_and_diagnosable(
    tmp_path: Path,
    response: str,
    expected_terminal: str,
    expected_status: str,
) -> None:
    metrics = CandidateMetrics()
    dependencies = replace(
        build_fake_dependencies(secrets=_SECRETS, metrics=metrics),
        model_transport=_TransactionDateVariantTransport(response),
    )
    paths = _paths(tmp_path)
    if expected_terminal == "passed":
        result = await run_candidate(
            live=True,
            paths=paths,
            manifest_sha256="8" * 64,
            secrets=_SECRETS,
            dependencies=dependencies,
        )
        assert result["failureCase"] is None
        assert cast(list[dict[str, object]], result["cases"])[-1]["status"] == expected_status
    else:
        with pytest.raises(RuntimeError, match="business_query_plan_live.assertion_failed"):
            await run_candidate(
                live=True,
                paths=paths,
                manifest_sha256="8" * 64,
                secrets=_SECRETS,
                dependencies=dependencies,
            )
        result = validate_result(
            json.loads(paths.result.read_text(encoding="utf-8")),
            require_passed=False,
        )
        assert result["failureCase"] == {
            "caseId": "bq-live-txn-unsupported",
            "status": expected_status,
            "capabilityId": None,
            "planCalls": 1,
            "domainCalls": 0,
            "reason": "status_mismatch",
        }
        assert len(cast(list[object], result["cases"])) == 5
    assert result["status"] == expected_terminal
    assert metrics.model_calls == 6
    assert metrics.employee_detail == 2
    assert metrics.transaction_search == 2
    assert metrics.domain_calls_by_case.get("bq-live-txn-unsupported", 0) == 0
    assert paths.consumed.exists()
    assert len(paths.journal.read_text(encoding="utf-8").splitlines()) == 6
    assert response not in paths.result.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_result_v2_rejects_unbounded_or_sensitive_failure_diagnostics(tmp_path: Path) -> None:
    metrics = CandidateMetrics()
    dependencies = replace(
        build_fake_dependencies(secrets=_SECRETS, metrics=metrics),
        model_transport=_TransactionDateVariantTransport(
            '{"domain":"transaction","action":"transaction.search","arguments":{}}'
        ),
    )
    paths = _paths(tmp_path)
    with pytest.raises(RuntimeError, match="business_query_plan_live.assertion_failed"):
        await run_candidate(
            live=True,
            paths=paths,
            manifest_sha256="9" * 64,
            secrets=_SECRETS,
            dependencies=dependencies,
        )
    original = json.loads(paths.result.read_text(encoding="utf-8"))
    for forbidden_key in ("question", "modelResponse", "businessResponse", "jwt", "employeeIdentifier"):
        value = copy.deepcopy(original)
        value["failureCase"][forbidden_key] = "must-not-persist"
        with pytest.raises(ValueError, match="business_query_plan_live.object_shape_invalid"):
            validate_result(value, require_passed=False)
    value = copy.deepcopy(original)
    value["failureCase"]["reason"] = "unbounded_raw_exception"
    with pytest.raises(ValueError, match="business_query_plan_live.result_failure_case_invalid"):
        validate_result(value, require_passed=False)
    for field_name, invalid_value in (
        ("status", {"raw": "invalid_argument"}),
        ("capabilityId", ["transaction.search"]),
        ("planCalls", True),
        ("domainCalls", 2),
        ("reason", {"raw": "status_mismatch"}),
    ):
        value = copy.deepcopy(original)
        value["failureCase"][field_name] = invalid_value
        with pytest.raises(ValueError, match="business_query_plan_live.result_failure_case_invalid"):
            validate_result(value, require_passed=False)


@pytest.mark.asyncio
async def test_fake_failure_is_consumed_once_and_cannot_be_resumed(tmp_path: Path) -> None:
    metrics = CandidateMetrics()
    dependencies = build_fake_dependencies(secrets=_SECRETS, metrics=metrics)
    dependencies = replace(dependencies, model_transport=_FailingTransport())
    paths = _paths(tmp_path)

    with pytest.raises(RuntimeError, match="business_query_plan_live.assertion_failed"):
        await run_candidate(
            live=True,
            paths=paths,
            manifest_sha256="b" * 64,
            secrets=_SECRETS,
            dependencies=dependencies,
        )

    result = json.loads(paths.result.read_text(encoding="utf-8"))
    validate_result(result, require_passed=False)
    assert result["status"] == "failed_consumed"
    assert result["cases"] == []
    assert result["counts"]["modelCalls"] == 1
    assert paths.consumed.exists()
    assert len(paths.journal.read_text(encoding="utf-8").splitlines()) == 1
    assert "raw provider failure" not in paths.result.read_text(encoding="utf-8")

    with pytest.raises(RuntimeError, match="business_query_plan_live.run_already_exists"):
        await run_candidate(
            live=True,
            paths=paths,
            manifest_sha256="b" * 64,
            secrets=_SECRETS,
            dependencies=build_fake_dependencies(secrets=_SECRETS, metrics=CandidateMetrics()),
        )


@pytest.mark.asyncio
async def test_snapshot_mismatch_fails_unconsumed_with_finite_result(tmp_path: Path) -> None:
    metrics = CandidateMetrics()
    dependencies = replace(
        build_fake_dependencies(secrets=_SECRETS, metrics=metrics),
        expected_snapshot_id="0" * 64,
    )
    paths = _paths(tmp_path)

    with pytest.raises(RuntimeError, match="business_query_plan_live.execution_failed"):
        await run_candidate(
            live=False,
            paths=paths,
            manifest_sha256="c" * 64,
            secrets=_SECRETS,
            dependencies=dependencies,
        )

    result = json.loads(paths.result.read_text(encoding="utf-8"))
    validate_result(result, require_passed=False)
    assert result["status"] == "failed_unconsumed"
    assert result["counts"]["modelCalls"] == 0
    assert result["cleanup"] == {
        "runtimeClosed": False,
        "modelClientClosed": True,
        "domainClientsClosed": True,
    }


@pytest.mark.asyncio
async def test_fake_endpoint_snapshot_cannot_reach_model_or_business_transport(
    tmp_path: Path,
) -> None:
    metrics = CandidateMetrics()
    fake_endpoint_snapshot = business_query_plan_snapshot_id(
        employee_endpoint="http://employee.invalid",
        transaction_endpoint="http://transaction.invalid",
    )
    dependencies = replace(
        build_fake_dependencies(secrets=_SECRETS, metrics=metrics),
        expected_snapshot_id=fake_endpoint_snapshot,
    )
    paths = _paths(tmp_path)

    with pytest.raises(RuntimeError, match="business_query_plan_live.execution_failed"):
        await run_candidate(
            live=False,
            paths=paths,
            manifest_sha256="e" * 64,
            secrets=_SECRETS,
            dependencies=dependencies,
        )

    result = validate_result(
        json.loads(paths.result.read_text(encoding="utf-8")),
        require_passed=False,
    )
    assert result["status"] == "failed_unconsumed"
    counts = cast(dict[str, int], result["counts"])
    assert counts["modelCalls"] == 0
    assert counts["employeeDetail"] == 0
    assert counts["transactionSearch"] == 0
    assert not paths.consumed.exists()
    assert not paths.journal.exists()


@pytest.mark.asyncio
async def test_cross_domain_plan_cannot_switch_employee_request_to_transaction(tmp_path: Path) -> None:
    metrics = CandidateMetrics()
    dependencies = replace(
        build_fake_dependencies(secrets=_SECRETS, metrics=metrics),
        model_transport=_CrossDomainTransport(),
    )
    paths = _paths(tmp_path)

    with pytest.raises(RuntimeError, match="business_query_plan_live.assertion_failed"):
        await run_candidate(
            live=False,
            paths=paths,
            manifest_sha256="d" * 64,
            secrets=_SECRETS,
            dependencies=dependencies,
        )

    result = json.loads(paths.result.read_text(encoding="utf-8"))
    validate_result(result, require_passed=False)
    assert result["status"] == "failed_unconsumed"
    assert result["counts"]["transactionSearch"] == 0
    assert result["counts"]["otherBusinessEndpoints"] == 1
    assert result["cases"] == []


@pytest.mark.asyncio
async def test_live_entry_fails_before_secret_or_outbound_when_not_explicitly_enabled() -> None:
    with pytest.raises(RuntimeError, match="business_query_plan_live.not_enabled"):
        await run_live_from_environment(
            {
                "LLM_API_KEY": "must-not-be-read",
                "BUSINESS_QUERY_PLAN_LIVE_EMPLOYEE_IDENTIFIER": "must-not-be-read",
            }
        )


@pytest.mark.asyncio
async def test_live_preflight_rejects_snapshot_drift_before_reading_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Path(__file__).resolve().parents[3]
    manifest = (
        root
        / "agent-runtime/tests/system_e2e/live/evidence"
        / f"{RUN_ID}.manifest.json"
    )
    current_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    def wrong_snapshot(*, employee_endpoint: str, transaction_endpoint: str) -> str:
        del employee_endpoint, transaction_endpoint
        return "0" * 64

    monkeypatch.setattr(live_runner, "business_query_plan_snapshot_id", wrong_snapshot)
    environment = {
        "BUSINESS_QUERY_PLAN_LIVE_ENABLE": "1",
        "BUSINESS_QUERY_PLAN_LIVE_MANIFEST_PATH": str(manifest),
        "BUSINESS_QUERY_PLAN_LIVE_MANIFEST_SHA256": sha256_file(manifest),
        "BUSINESS_QUERY_PLAN_LIVE_RUN_ID": RUN_ID,
        "BUSINESS_QUERY_PLAN_LIVE_AUTHORIZATION_REFERENCE": AUTHORIZATION_REFERENCE,
        "BUSINESS_QUERY_PLAN_LIVE_FROZEN_HEAD": current_head,
        "BUSINESS_QUERY_PLAN_LIVE_EMPLOYEE_BASE_URL": EMPLOYEE_BASE_URL,
        "BUSINESS_QUERY_PLAN_LIVE_TRANSACTION_BASE_URL": TRANSACTION_BASE_URL,
    }
    assert "LLM_API_KEY" not in environment

    with pytest.raises(RuntimeError, match="business_query_plan_live.snapshot_mismatch"):
        await run_live_from_environment(environment)


def test_authorization_template_is_non_executable_until_final_binding() -> None:
    value = {
        "schemaVersion": 1,
        "state": "prepared_unconsumed",
        "liveExecutionAuthorized": False,
        "runId": RUN_ID,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "sourcePreparedHead": "e" * 40,
        "manifestSha256": "f" * 64,
        "budgets": {
            "modelCalls": 6,
            "employeeDetail": 2,
            "transactionSearch": 2,
            "retry": 0,
            "resume": 0,
        },
        "requiredBindings": {
            "finalFrozenHead": "required_in_final_authorization",
            "processLlmApiKey": "required_memory_only",
            "processEmployeeIdentifier": "required_memory_only",
            "processAdminJwt": "required_memory_only",
            "processDeniedJwt": "required_memory_only",
            "employeeBaseUrl": "http://127.0.0.1:9210",
            "transactionBaseUrl": "http://127.0.0.1:8182",
        },
        "constraints": {
            "singleUse": True,
            "firstOutboundConsumes": True,
            "automaticRetry": False,
            "rerun": False,
            "resume": False,
            "answerTask": False,
        },
    }
    validate_authorization_template(value, manifest_sha256="f" * 64, prepared_head="e" * 40)
    value["liveExecutionAuthorized"] = True
    with pytest.raises(ValueError, match="business_query_plan_live.authorization_template_invalid"):
        validate_authorization_template(value, manifest_sha256="f" * 64, prepared_head="e" * 40)
