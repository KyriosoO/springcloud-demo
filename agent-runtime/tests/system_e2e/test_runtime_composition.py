from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.model.context import ModelContextBindingRuntimeInvoker
from tests.helpers import scope
from tests.system_e2e.evidence_contract import runtime_evidence, validate_system_e2e_evidence
from tests.system_e2e.runtime_server import (
    SystemE2ERuntime,
    _DeterministicKnowledgeModelTransport,
    _DomainTransport,
    _ForbiddenAnswerGenerator,
    build_system_e2e_runtime,
)


def _environment(tmp_path: Path) -> dict[str, str]:
    path = tmp_path / "runtime-evidence.json"
    return {
        "AGENT_MODEL_PROVIDER": "stub",
        "SYSTEM_E2E_EVIDENCE_PATH": str(path),
        "SYSTEM_E2E_KNOWLEDGE_BASE_URL": "http://127.0.0.1:19201",
        "SYSTEM_E2E_EMBEDDING_BASE_URL": "http://127.0.0.1:18908",
        "SYSTEM_E2E_RERANK_BASE_URL": "http://127.0.0.1:18909",
        "SYSTEM_E2E_EMPLOYEE_BASE_URL": "http://127.0.0.1:19210",
        "SYSTEM_E2E_TRANSACTION_BASE_URL": "http://127.0.0.1:18182",
    }


@pytest.mark.asyncio
async def test_test_only_composition_uses_stub_and_rejects_invalid_local_arguments_without_network(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    runtime = build_system_e2e_runtime({**environment, "LLM_API_KEY": "must-not-be-read"})
    question = "查询交易 金额=1.000"

    outcome = await runtime.ainvoke(question=question, scope=scope(question=question))
    await runtime.aclose()

    assert outcome.status is CapabilityStatus.INVALID_ARGUMENT
    evidence = json.loads((tmp_path / "runtime-evidence.json").read_text(encoding="utf-8"))
    validate_system_e2e_evidence(evidence, final=False)
    assert evidence["providers"]["model"] == "stub"
    assert all(value == 0 for value in evidence["requestCounts"].values())


def test_deepseek_provider_is_rejected_before_runtime_build(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="system_e2e.model_provider_must_be_stub"):
        build_system_e2e_runtime({**_environment(tmp_path), "AGENT_MODEL_PROVIDER": "deepseek"})


def test_strict_evidence_contract_rejects_forbidden_fields() -> None:
    value = runtime_evidence(cases={}, request_counts={key: 0 for key in (
        "knowledgeSearch",
        "embedding",
        "rerank",
        "employee",
        "transaction",
        "otherBusinessEndpoints",
        "localKnowledgeModel",
        "answerGeneration",
        "externalModelOutbound",
    )})
    value["rawResponse"] = "forbidden"
    with pytest.raises(ValueError, match="system_e2e.evidence_shape_invalid"):
        validate_system_e2e_evidence(value, final=False)


def test_launcher_routes_surefire_reports_into_ephemeral_scanned_directory() -> None:
    launcher = (Path(__file__).parents[2] / "scripts" / "run-system-e2e.ps1").read_text(encoding="utf-8")

    assert '"-Dsurefire.reportsDirectory=$surefireReports"' in launcher
    assert "Get-ChildItem -LiteralPath $surefireReports -Recurse -File" in launcher
    assert "Remove-Item -LiteralPath $surefireReports -Recurse -Force" in launcher


class _CloseProbe:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True
        if self.failure is not None:
            raise self.failure


class _DomainCloseProbe(_DomainTransport):
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.calls = 0
        self.other_endpoint_calls = 0
        self.failure = failure
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True
        if self.failure is not None:
            raise self.failure


@pytest.mark.asyncio
async def test_close_failure_does_not_skip_other_owned_resources_or_finite_evidence(tmp_path: Path) -> None:
    delegate = _CloseProbe()
    employee = _DomainCloseProbe(failure=RuntimeError("close failed"))
    transaction = _DomainCloseProbe()
    knowledge_client = httpx.AsyncClient()
    runtime = SystemE2ERuntime(
        delegate=cast(ModelContextBindingRuntimeInvoker, cast(Any, delegate)),
        evidence_path=tmp_path / "runtime-evidence.json",
        model_transport=_DeterministicKnowledgeModelTransport(),
        answer_generator=_ForbiddenAnswerGenerator(),
        knowledge_transports=(),
        knowledge_clients=(knowledge_client,),
        employee_transport=employee,
        transaction_transport=transaction,
    )

    with pytest.raises(RuntimeError, match="close failed"):
        await runtime.aclose()

    assert delegate.closed is True
    assert employee.closed is True
    assert transaction.closed is True
    assert knowledge_client.is_closed is True
    evidence = json.loads((tmp_path / "runtime-evidence.json").read_text(encoding="utf-8"))
    validate_system_e2e_evidence(evidence, final=False)
    assert evidence["cleanup"]["runtimeClosed"] is False
