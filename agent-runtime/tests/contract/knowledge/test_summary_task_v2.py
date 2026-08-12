from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from agent_runtime.knowledge.evidence.builder import (
    DeterministicEvidenceSelector,
    EvidenceIntegrityVerifier,
)
from agent_runtime.knowledge.evidence.contracts import (
    KnowledgeEvidenceBundle,
    KnowledgeEvidenceLimits,
    KnowledgeSummaryInput,
    KnowledgeSummaryPoint,
    SummaryCoverageInput,
    SummaryEvidenceInput,
)
from agent_runtime.knowledge.evidence.summary_task import KnowledgeSummaryTaskV1
from agent_runtime.knowledge.evidence.summary_task_v2 import (
    SUMMARY_PROMPT_V2,
    KnowledgeSummaryTaskV2,
)
from agent_runtime.knowledge.evidence.summary_validation import (
    ExtractiveSummaryValidator,
    InvalidSummary,
    SummaryValidationFailureReason,
)
from agent_runtime.model.contracts import (
    StructuredFinishKind,
    StructuredModelResponse,
    StructuredOutputMode,
    StructuredToolMode,
)
from tests.evidence_helpers import evidence_input


ROOT = Path(__file__).resolve().parents[3]
V1_TASK = ROOT / "src/agent_runtime/knowledge/evidence/summary_task.py"
VALIDATOR = ROOT / "src/agent_runtime/knowledge/evidence/summary_validation.py"
V1_TASK_SHA256 = "dba0175a7e2810ea1a1c5601499cd9da74de6c3cf60b4026cc7136233b864645"
VALIDATOR_SHA256 = "80a3846814dc360291078649697aebdd2b393971b8abb933ed0f645200c4f6d6"
V2_PROMPT_SHA256 = "b6cf5e9a2d49ef09ce441ee5547eb57429f4df37c9efa6cc0bf29feec06a4797"


def _input() -> KnowledgeSummaryInput:
    return KnowledgeSummaryInput(
        schema_version=1,
        question="税务政策",
        coverage=SummaryCoverageInput(
            retrieval_complete=True,
            domain_coverage_complete=True,
        ),
        evidence=(
            SummaryEvidenceInput(
                evidence_ref="e1",
                content="税务政策正文",
                domain_ids=("tax.policy",),
            ),
        ),
    )


def _bundle() -> KnowledgeEvidenceBundle:
    source = evidence_input()
    selection = DeterministicEvidenceSelector().select(
        candidates=EvidenceIntegrityVerifier().verify(input=source),
        input=source,
        minimized_question="现行增值税政策是什么",
        limits=KnowledgeEvidenceLimits.v1(),
    )
    assert selection.bundle is not None
    return selection.bundle


def test_v2_definition_only_changes_version_and_request_instruction() -> None:
    v1 = KnowledgeSummaryTaskV1.definition()
    v2 = KnowledgeSummaryTaskV2.definition()

    assert v2.task_id is v1.task_id
    assert v2.task_version == "2"
    assert v2.input_type is v1.input_type
    assert v2.parse_response is v1.parse_response
    assert (v2.max_input_bytes, v2.timeout_ms, v2.max_output_tokens) == (
        v1.max_input_bytes,
        v1.timeout_ms,
        v1.max_output_tokens,
    )

    request = v2.build_request(_input())
    assert request.task_version == "2"
    assert request.system_instruction == SUMMARY_PROMPT_V2
    assert request.tools == ()
    assert request.tool_mode is StructuredToolMode.NONE
    assert request.output_mode is StructuredOutputMode.JSON_OBJECT
    assert request.max_output_tokens == 1536
    assert json.loads(request.user_payload_json)["evidence"][0]["evidence_ref"] == "e1"


def test_v2_instruction_contains_only_the_documented_uniqueness_strengthening() -> None:
    required = (
        "evidence_ref 必须两两不同",
        "同一个 evidence_ref 最多出现一次",
        "只选择最能直接回答问题的一个连续片段",
        "如果只有一个 evidence_ref 足以回答，只输出一个 point",
        "输出前检查 points 中没有重复 evidence_ref",
    )
    assert all(item in SUMMARY_PROMPT_V2 for item in required)
    assert hashlib.sha256(SUMMARY_PROMPT_V2.encode("utf-8")).hexdigest() == V2_PROMPT_SHA256
    assert "重试" not in SUMMARY_PROMPT_V2
    assert "去重后接受" not in SUMMARY_PROMPT_V2


def test_v2_reuses_v1_parser_and_validator_still_rejects_duplicate_ref() -> None:
    output = KnowledgeSummaryTaskV2.definition().parse_response(
        StructuredModelResponse(
            finish_kind=StructuredFinishKind.STOP,
            content=(
                '{"outcome":"answer","points":['
                '{"evidence_ref":"e1","quote":"税务政策"},'
                '{"evidence_ref":"e1","quote":"正文"}]}'
            ),
            tool_calls=(),
            usage_total_tokens=None,
        )
    )

    with pytest.raises(InvalidSummary) as raised:
        ExtractiveSummaryValidator().validate(
            output=output,
            bundle=_bundle(),
            limits=KnowledgeEvidenceLimits.v1(),
        )
    assert raised.value.reason is SummaryValidationFailureReason.DUPLICATE_EVIDENCE_REF


def test_v1_task_and_validator_files_remain_byte_identical() -> None:
    assert hashlib.sha256(V1_TASK.read_bytes()).hexdigest() == V1_TASK_SHA256
    assert hashlib.sha256(VALIDATOR.read_bytes()).hexdigest() == VALIDATOR_SHA256
