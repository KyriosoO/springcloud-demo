"""当前路由/计划运行时契约的提示词契约测试。"""

import json
import re
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from app.contracts.generated_models import (
    AgentOperator,
    AggregateFunction,
    ClarificationRequired,
    ExecutablePlan,
    PlanOutcome,
    RouteDecision,
    RouteOutcome,
    RuntimeOperationType,
)
from app.contracts.models import unwrap_root

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "app" / "prompts"

VALID_OPERATORS = {item.value for item in AgentOperator}
VALID_AGGREGATE_FUNCTIONS = {item.value for item in AggregateFunction}
FORBIDDEN_TERMS = {
    "bucketSize",
    "BucketSize",
    "bucket_size",
    "PlanGenerateRequest",
    "PlanGenerateResponse",
    "/plans/generate",
    '"planVersion"',
    '"intent"',
    '"clarify"',
    '"question"',
}


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    assert path.exists(), f"Prompt file not found: {path}"
    return path.read_text(encoding="utf-8")


def _extract_json_blocks(text: str) -> list[dict]:
    blocks: list[dict] = []
    for match in re.findall(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL):
        blocks.append(json.loads(match.strip()))
    return blocks


def _metadata_operation(block: dict) -> str:
    return block["metadata"]["operation"]


class TestPromptExamples:
    def test_route_examples_parse_as_route_outcomes(self):
        blocks = _extract_json_blocks(_load_prompt("route_system.md"))
        assert len(blocks) >= 3

        outcomes = [unwrap_root(TypeAdapter(RouteOutcome).validate_python(block)) for block in blocks]
        assert any(isinstance(outcome, RouteDecision) for outcome in outcomes)
        assert any(isinstance(outcome, ClarificationRequired) for outcome in outcomes)
        assert {_metadata_operation(block) for block in blocks} == {RuntimeOperationType.route.value}

    def test_query_examples_parse_as_plan_outcomes(self):
        blocks = _extract_json_blocks(_load_prompt("query_system.md"))
        assert len(blocks) >= 2

        outcomes = [unwrap_root(TypeAdapter(PlanOutcome).validate_python(block)) for block in blocks]
        assert any(
            isinstance(outcome, ExecutablePlan) and outcome.plan.plan_kind == "QUERY"
            for outcome in outcomes
        )
        assert any(isinstance(outcome, ClarificationRequired) for outcome in outcomes)
        assert {_metadata_operation(block) for block in blocks} == {RuntimeOperationType.plan.value}

    def test_aggregate_examples_parse_as_plan_outcomes(self):
        blocks = _extract_json_blocks(_load_prompt("aggregate_system.md"))
        assert len(blocks) >= 2

        outcomes = [unwrap_root(TypeAdapter(PlanOutcome).validate_python(block)) for block in blocks]
        executable = next(
            outcome
            for outcome in outcomes
            if isinstance(outcome, ExecutablePlan) and outcome.plan.plan_kind == "AGGREGATE"
        )
        assert executable.plan.aggregate.metrics
        assert any(isinstance(outcome, ClarificationRequired) for outcome in outcomes)
        assert {_metadata_operation(block) for block in blocks} == {RuntimeOperationType.plan.value}

    def test_document_examples_parse_as_plan_outcomes(self):
        blocks = _extract_json_blocks(_load_prompt("document_system.md"))
        assert len(blocks) >= 2

        outcomes = [unwrap_root(TypeAdapter(PlanOutcome).validate_python(block)) for block in blocks]
        assert any(
            isinstance(outcome, ExecutablePlan) and outcome.plan.plan_kind == "DOCUMENT"
            for outcome in outcomes
        )
        assert any(isinstance(outcome, ClarificationRequired) for outcome in outcomes)
        assert {_metadata_operation(block) for block in blocks} == {RuntimeOperationType.plan.value}

    def test_document_prompt_does_not_generate_answer(self):
        text = _load_prompt("document_system.md")
        for term in ("agent-service", "retrieval", "generation", "citation verification"):
            assert term in text

        forbidden_output_fields = {
            "answerText",
            "summaryText",
            "summaryBullets",
            "citations",
            "hits",
            "coverage",
        }
        for block in _extract_json_blocks(text):
            serialized = json.dumps(block, ensure_ascii=False)
            for field in forbidden_output_fields:
                assert f'"{field}"' not in serialized

        executable_blocks = [
            unwrap_root(TypeAdapter(PlanOutcome).validate_python(block))
            for block in _extract_json_blocks(text)
            if block["outcomeType"] == "EXECUTABLE"
        ]
        assert executable_blocks
        document = executable_blocks[0].plan.document
        assert document.retrieval_options is None
        assert document.generation_options.enabled is True


class TestPromptEnums:
    @pytest.mark.parametrize("filename", ["query_system.md", "aggregate_system.md", "document_system.md"])
    def test_operator_examples_use_generated_values(self, filename: str):
        text = _load_prompt(filename)
        for operator in re.findall(r'"operator":\s*"([A-Z_]+)"', text):
            assert operator in VALID_OPERATORS

    def test_aggregate_function_examples_use_generated_values(self):
        text = _load_prompt("aggregate_system.md")
        for function in re.findall(r'"function":\s*"([A-Z]+)"', text):
            assert function in VALID_AGGREGATE_FUNCTIONS


class TestNoLegacyPromptContract:
    @pytest.mark.parametrize("filename", ["route_system.md", "query_system.md", "aggregate_system.md", "document_system.md"])
    def test_no_legacy_terms(self, filename: str):
        text = _load_prompt(filename)
        for term in FORBIDDEN_TERMS:
            assert term not in text, f"{filename} contains forbidden term {term!r}"

    @pytest.mark.parametrize("filename", ["route_system.md", "query_system.md", "aggregate_system.md", "document_system.md"])
    def test_examples_use_target_discriminators(self, filename: str):
        blocks = _extract_json_blocks(_load_prompt(filename))
        assert blocks
        for block in blocks:
            assert "outcomeType" in block
            assert "requestId" in block
            assert "metadata" in block
            assert block["outcomeType"] in {"DECISION", "EXECUTABLE", "CLARIFICATION"}

    @pytest.mark.parametrize("filename", ["route_system.md", "query_system.md", "aggregate_system.md", "document_system.md"])
    def test_prompt_does_not_pin_query_preview_as_static_route(self, filename: str):
        assert "query.preview" not in _load_prompt(filename)

    def test_query_prompt_preserves_pagination_context_rules(self):
        text = _load_prompt("query_system.md")
        assert "totalPages" in text
        assert "totalExact=true" in text
        assert "page-only follow-up" in text
