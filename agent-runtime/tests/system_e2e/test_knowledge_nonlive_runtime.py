from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from agent_runtime.capability_api.contracts import (
    CapabilityStatus,
    OpaqueUserToken,
)
from agent_runtime.core.execution import RequestExecutionScope
from tests.helpers import scope
from tests.system_e2e.knowledge_nonlive_evidence import (
    validate_knowledge_nonlive_evidence,
)
from tests.system_e2e.knowledge_runtime_server import (
    build_knowledge_nonlive_runtime,
)


_ADMIN = "synthetic-knowledge-admin"
_VIEWER = "synthetic-knowledge-viewer"
_DENIED = "synthetic-knowledge-denied"


def _environment(tmp_path: Path) -> dict[str, str]:
    return {
        "AGENT_MODEL_PROVIDER": "stub",
        "KNOWLEDGE_NONLIVE_EVIDENCE_PATH": str(tmp_path / "evidence.json"),
        "KNOWLEDGE_NONLIVE_ADMIN_TOKEN": _ADMIN,
        "KNOWLEDGE_NONLIVE_VIEWER_TOKEN": _VIEWER,
    }


def _scope(question: str, *, case_id: str, token: str) -> RequestExecutionScope:
    base = scope(question).context
    return RequestExecutionScope(context=replace(
        base,
        request_id=f"request-{case_id}",
        correlation_id=case_id,
        user_token=OpaqueUserToken.from_raw(token),
    ))


@pytest.mark.asyncio
async def test_current_production_composition_executes_knowledge_matrix(
    tmp_path: Path,
) -> None:
    runtime = build_knowledge_nonlive_runtime(
        {**_environment(tmp_path), "LLM_API_KEY": "must-not-be-read"}
    )
    cases = (
        ("k-nonlive-policy-admin", "现行增值税政策有哪些", _ADMIN, CapabilityStatus.SUCCESS),
        ("k-nonlive-law-viewer", "税收法律第一条规定什么", _VIEWER, CapabilityStatus.SUCCESS),
        ("k-nonlive-multi-domain", "税务政策和税收法律有哪些规定", _ADMIN, CapabilityStatus.SUCCESS),
        ("k-nonlive-rewrite-fallback", "税务政策改写失败仍如何处理", _ADMIN, CapabilityStatus.SUCCESS),
        ("k-nonlive-rewrite-invalid", "税务政策改写非法仍如何处理", _ADMIN, CapabilityStatus.SUCCESS),
        ("k-nonlive-no-result", "不存在资料的税务政策是什么", _ADMIN, CapabilityStatus.NO_RESULT),
        ("k-nonlive-read-denied", "现行税务政策是什么", _DENIED, CapabilityStatus.FORBIDDEN),
        ("k-nonlive-partial-path", "税务政策单路失败如何处理", _ADMIN, CapabilityStatus.SUCCESS),
        ("k-nonlive-all-paths-fail", "税务政策全部检索失败", _ADMIN, CapabilityStatus.DOWNSTREAM_FAILURE),
        ("k-nonlive-policy-missing", "税务政策未分类策略", _ADMIN, CapabilityStatus.MODEL_EGRESS_DENIED),
        ("k-nonlive-invalid-ref", "税务政策非法引用", _ADMIN, CapabilityStatus.DOWNSTREAM_FAILURE),
        ("k-nonlive-duplicate-ref", "税务政策重复引用", _ADMIN, CapabilityStatus.DOWNSTREAM_FAILURE),
        ("k-nonlive-summary-failure", "税务政策摘要失败", _ADMIN, CapabilityStatus.DOWNSTREAM_FAILURE),
        ("k-nonlive-sensitive", "税务政策 password=synthetic-secret", _ADMIN, CapabilityStatus.MODEL_EGRESS_DENIED),
        ("k-nonlive-second-action", "税务政策 第二动作", _ADMIN, CapabilityStatus.DOWNSTREAM_FAILURE),
        ("k-nonlive-unsupported", "不支持能力的税务咨询", _ADMIN, CapabilityStatus.UNSUPPORTED),
    )
    outcomes = {}
    for case_id, question, token, expected in cases:
        outcome = await runtime.ainvoke(
            question=question,
            scope=_scope(question, case_id=case_id, token=token),
        )
        outcomes[case_id] = outcome
        assert outcome.status is expected, (case_id, outcome.failure)
    await runtime.aclose()

    evidence_path = tmp_path / "evidence.json"
    raw = evidence_path.read_text(encoding="utf-8")
    evidence = json.loads(raw)
    validate_knowledge_nonlive_evidence(evidence)
    assert evidence["status"] == "passed"
    assert outcomes["k-nonlive-sensitive"].capability_id is None
    assert outcomes["k-nonlive-read-denied"].failure is not None
    assert outcomes["k-nonlive-read-denied"].failure.code == "knowledge.domain_forbidden"
    sensitive = next(
        item for item in evidence["cases"]
        if item["caseId"] == "k-nonlive-sensitive"
    )
    assert all(count == 0 for count in sensitive["calls"].values())
    assert evidence["totals"]["businessModel"] == 0
    assert evidence["totals"]["externalModelOutbound"] == 0
    assert "synthetic-secret" not in raw
    assert _ADMIN not in raw
    assert _VIEWER not in raw
    assert _DENIED not in raw


def test_nonlive_runtime_rejects_real_model_provider(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="knowledge_nonlive.model_provider_must_be_stub"):
        build_knowledge_nonlive_runtime({
            **_environment(tmp_path),
            "AGENT_MODEL_PROVIDER": "deepseek",
        })
