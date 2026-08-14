from __future__ import annotations

from agent_runtime.business.grounding import BusinessAnswerGroundingPolicy
from agent_runtime.model.contracts import CandidateAnswer, GroundingInput


def _input(answer: str, used: tuple[str, ...], *, truncated: bool = False) -> GroundingInput:
    return GroundingInput(
        capability_id="employee.detail",
        minimized_question="查询员工",
        safe_payload={
            "schema_version": 1,
            "policy_version": "business-egress-v1",
            "config_snapshot_id": "a" * 64,
            "facts": (
                {"fact_id": "fact-0001", "value_type": "text", "value": "工程师", "transform_id": "bounded_text", "source": {"record_ref": "record-0001", "field_id": "position"}},
            ),
            "presentation": {"mode": "business_facts", "action_id": "employee.detail"},
            "coverage": {"truncated": truncated},
        },
        candidate=CandidateAnswer(answer=answer, used_fact_ids=used, unsupported_claims=()),
    )


def test_grounding_accepts_marked_fact_sentence() -> None:
    assert BusinessAnswerGroundingPolicy().validate(_input("职位为工程师 [fact-0001]。", ("fact-0001",))).accepted


def test_grounding_rejects_unmarked_or_overclaiming_truncated_answer() -> None:
    assert not BusinessAnswerGroundingPolicy().validate(_input("职位为工程师。", ("fact-0001",))).accepted
    assert not BusinessAnswerGroundingPolicy().validate(_input("这是全部结果 [fact-0001]。", ("fact-0001",), truncated=True)).accepted


def test_grounding_rejects_protected_token_not_present_in_referenced_fact() -> None:
    assert not BusinessAnswerGroundingPolicy().validate(
        _input("职位代码为 ADMIN [fact-0001]。", ("fact-0001",))
    ).accepted


def test_grounding_keeps_exact_decimal_value_in_one_sentence() -> None:
    input_value = GroundingInput(
        capability_id="transaction.search",
        minimized_question="概述这一条交易结果的交易类型和金额",
        safe_payload={
            "schema_version": 1,
            "policy_version": "business-egress-v1",
            "config_snapshot_id": "a" * 64,
            "facts": (
                {"fact_id": "fact-0001", "value_type": "enum", "value": "PAYMENT", "transform_id": "enum_code", "source": {"record_ref": "record-0001", "field_id": "transaction_type"}},
                {"fact_id": "fact-0002", "value_type": "decimal", "value": "100.10", "transform_id": "decimal_2", "source": {"record_ref": "record-0001", "field_id": "amount"}},
            ),
            "presentation": {"mode": "business_facts", "action_id": "transaction.search"},
            "coverage": {"truncated": False},
        },
        candidate=CandidateAnswer(
            answer="交易类型为 PAYMENT [fact-0001]。金额为 100.10 [fact-0002]。",
            used_fact_ids=("fact-0001", "fact-0002"),
            unsupported_claims=(),
        ),
    )

    assert BusinessAnswerGroundingPolicy().validate(input_value).accepted
