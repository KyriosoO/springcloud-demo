from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeSummaryInput,
    SummaryCoverageInput,
    SummaryEvidenceInput,
)
from agent_runtime.knowledge.evidence.summary_task_v2 import KnowledgeSummaryTaskV2
from agent_runtime.knowledge.evidence.summary_task_v3 import (
    SUMMARY_PROMPT_V3,
    KnowledgeSummaryTaskV3,
)
from agent_runtime.model.contracts import StructuredOutputMode, StructuredToolMode


ROOT = Path(__file__).resolve().parents[3]
V1_TASK = ROOT / "src/agent_runtime/knowledge/evidence/summary_task.py"
V2_TASK = ROOT / "src/agent_runtime/knowledge/evidence/summary_task_v2.py"
VALIDATOR = ROOT / "src/agent_runtime/knowledge/evidence/summary_validation.py"
V1_TASK_SHA256 = "dba0175a7e2810ea1a1c5601499cd9da74de6c3cf60b4026cc7136233b864645"
V2_TASK_SHA256 = "cf8e8c7f56a9bffb36828a91a923955529d0e23fbd9084229a68ea47a8d8643b"
VALIDATOR_SHA256 = "80a3846814dc360291078649697aebdd2b393971b8abb933ed0f645200c4f6d6"


def _input() -> KnowledgeSummaryInput:
    return KnowledgeSummaryInput(
        schema_version=1,
        question="一般纳税人与小规模纳税人的增值税税率分别是什么？",
        coverage=SummaryCoverageInput(retrieval_complete=True, domain_coverage_complete=True),
        evidence=(
            SummaryEvidenceInput(evidence_ref="e1", content="一般纳税人适用税率为甲。", domain_ids=("tax.policy",)),
            SummaryEvidenceInput(evidence_ref="e2", content="小规模纳税人适用征收率为乙。", domain_ids=("tax.policy",)),
        ),
    )


def test_v3_only_changes_version_and_coverage_instruction() -> None:
    v2 = KnowledgeSummaryTaskV2.definition()
    v3 = KnowledgeSummaryTaskV3.definition()

    assert v3.task_id is v2.task_id
    assert v3.task_version == "3"
    assert v3.input_type is v2.input_type
    assert v3.parse_response is v2.parse_response
    assert (v3.max_input_bytes, v3.timeout_ms, v3.max_output_tokens) == (
        v2.max_input_bytes,
        v2.timeout_ms,
        v2.max_output_tokens,
    )

    request = v3.build_request(_input())
    assert request.task_version == "3"
    assert request.system_instruction == SUMMARY_PROMPT_V3
    assert request.tools == ()
    assert request.tool_mode is StructuredToolMode.NONE
    assert request.output_mode is StructuredOutputMode.JSON_OBJECT
    assert request.max_output_tokens == 1536
    assert len(json.loads(request.user_payload_json)["evidence"]) == 2


def test_v3_instruction_strengthens_independent_coverage_without_weakening_safety() -> None:
    required = (
        "不同 evidence 独立回答的多个条件、日期、税率、主体类型或子问题",
        "必须为每个独立要点选择一个不同 evidence_ref",
        "最多 5 个 points",
        "如果一个 evidence_ref 已足以回答全部问题，只输出一个 point",
        "不得增加冗余引用",
        "evidence_ref 必须两两不同",
        "逐字复制的一个连续片段",
    )
    assert all(item in SUMMARY_PROMPT_V3 for item in required)
    assert "重试" not in SUMMARY_PROMPT_V3
    assert "去重后接受" not in SUMMARY_PROMPT_V3


def test_v3_rejects_out_of_bounds_input_before_transport() -> None:
    with pytest.raises(ValueError, match="knowledge.summary_input_invalid"):
        KnowledgeSummaryTaskV3.definition().build_request(
            KnowledgeSummaryInput(
                schema_version=1,
                question="税务问题",
                coverage=SummaryCoverageInput(retrieval_complete=True, domain_coverage_complete=True),
                evidence=(),
            )
        )


def test_v1_v2_and_validator_sources_remain_byte_identical() -> None:
    assert hashlib.sha256(V1_TASK.read_bytes()).hexdigest() == V1_TASK_SHA256
    assert hashlib.sha256(V2_TASK.read_bytes()).hexdigest() == V2_TASK_SHA256
    assert hashlib.sha256(VALIDATOR.read_bytes()).hexdigest() == VALIDATOR_SHA256
