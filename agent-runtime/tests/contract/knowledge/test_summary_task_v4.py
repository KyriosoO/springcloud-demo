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
from agent_runtime.knowledge.evidence.summary_task_v3 import KnowledgeSummaryTaskV3
from agent_runtime.knowledge.evidence.summary_task_v4 import (
    SUMMARY_PROMPT_V4,
    KnowledgeSummaryTaskV4,
)
from agent_runtime.model.contracts import StructuredOutputMode, StructuredToolMode


ROOT = Path(__file__).resolve().parents[3]
V1_TASK = ROOT / "src/agent_runtime/knowledge/evidence/summary_task.py"
V2_TASK = ROOT / "src/agent_runtime/knowledge/evidence/summary_task_v2.py"
V3_TASK = ROOT / "src/agent_runtime/knowledge/evidence/summary_task_v3.py"
VALIDATOR = ROOT / "src/agent_runtime/knowledge/evidence/summary_validation.py"
HISTORICAL_HASHES = {
    V1_TASK: "dba0175a7e2810ea1a1c5601499cd9da74de6c3cf60b4026cc7136233b864645",
    V2_TASK: "cf8e8c7f56a9bffb36828a91a923955529d0e23fbd9084229a68ea47a8d8643b",
    V3_TASK: "54b3d95b3c95bf84b3e8723bf96eccd7ae649a77ca9ff3ce530de53d0fe96de8",
    VALIDATOR: "80a3846814dc360291078649697aebdd2b393971b8abb933ed0f645200c4f6d6",
}


def _input() -> KnowledgeSummaryInput:
    return KnowledgeSummaryInput(
        schema_version=1,
        question="企业所得税优惠与对应法律依据分别是什么？",
        coverage=SummaryCoverageInput(retrieval_complete=True, domain_coverage_complete=True),
        evidence=(
            SummaryEvidenceInput(
                evidence_ref="e1",
                content="符合条件的企业可以适用税收优惠。",
                domain_ids=("tax.policy",),
            ),
            SummaryEvidenceInput(
                evidence_ref="e2",
                content="企业所得税法规定了适用条件。",
                domain_ids=("tax.law",),
            ),
        ),
    )


def test_v4_only_changes_version_and_coverage_instruction() -> None:
    v3 = KnowledgeSummaryTaskV3.definition()
    v4 = KnowledgeSummaryTaskV4.definition()

    assert v4.task_id is v3.task_id
    assert v4.task_version == "4"
    assert v4.input_type is v3.input_type
    assert v4.parse_response is v3.parse_response
    assert (v4.max_input_bytes, v4.timeout_ms, v4.max_output_tokens) == (
        v3.max_input_bytes,
        v3.timeout_ms,
        v3.max_output_tokens,
    )

    request = v4.build_request(_input())
    assert request.task_version == "4"
    assert request.system_instruction == SUMMARY_PROMPT_V4
    assert request.tools == ()
    assert request.tool_mode is StructuredToolMode.NONE
    assert request.output_mode is StructuredOutputMode.JSON_OBJECT
    payload = json.loads(request.user_payload_json)
    assert {tuple(item["domain_ids"]) for item in payload["evidence"]} == {
        ("tax.policy",),
        ("tax.law",),
    }


def test_v4_requires_complete_multi_point_and_visible_domain_coverage() -> None:
    required = (
        "每个独立要点选择一个不同 evidence_ref",
        "任一显式要点缺少直接证据时",
        "经策略允许而可见的 domain_ids",
        "每个适用逻辑域都必须至少选择一个直接、非重复的 evidence_ref",
        "不得给出部分肯定答案",
        "evidence_ref 必须两两不同",
        "逐字复制的一个连续片段",
        "最多 5 个 points",
    )
    assert all(item in SUMMARY_PROMPT_V4 for item in required)
    assert "重试" not in SUMMARY_PROMPT_V4
    assert "放宽" not in SUMMARY_PROMPT_V4


def test_v4_rejects_out_of_bounds_input_before_transport() -> None:
    with pytest.raises(ValueError, match="knowledge.summary_input_invalid"):
        KnowledgeSummaryTaskV4.definition().build_request(
            KnowledgeSummaryInput(
                schema_version=1,
                question="税务问题",
                coverage=SummaryCoverageInput(retrieval_complete=True, domain_coverage_complete=True),
                evidence=(),
            )
        )


def test_v1_to_v3_and_validator_sources_remain_byte_identical() -> None:
    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in HISTORICAL_HASHES
    } == HISTORICAL_HASHES
