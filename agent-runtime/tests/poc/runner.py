from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Literal

from agent_runtime.capability_api.contracts import JsonObject
from agent_runtime.model.contracts import (
    InvalidModelOutput,
    ModelInputDenied,
    ModelTransportError,
    QuestionEgressDisposition,
    StructuredModelTransport,
)
from agent_runtime.model.deepseek.action_selector import (
    ActionSelectionTaskInput,
    build_action_selection_task_definition,
)
from agent_runtime.model.deepseek.answer_generator import (
    AnswerGenerationTaskInput,
    build_answer_generation_task_definition,
)
from agent_runtime.model.deepseek.json_codec import parse_unique_json_object
from agent_runtime.model.deepseek.tools import UNSUPPORTED_TOOL_NAME, project_capability_tools
from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.model.settings import ModelSettings
from tests.poc.contracts import DeepSeekPocResult, PocCallRecord, write_append_only_result
from tests.poc.fixtures import ACTION_CASES, ANSWER_CASES, ActionPocCase, AnswerPocCase, action_descriptors


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


async def run_action_poc(
    *,
    transport: StructuredModelTransport,
    result_directory: Path,
    timeout_ms: int = 8000,
) -> tuple[DeepSeekPocResult, Path]:
    started = _utc_now()
    definition = build_action_selection_task_definition(timeout_ms=timeout_ms)
    projection = project_capability_tools(action_descriptors())
    guard = QuestionEgressGuard()
    records: list[PocCallRecord] = []
    total_tokens = 0
    provider_failed = False

    for case in ACTION_CASES:
        decision = guard.evaluate(case.question)
        if decision.disposition is not QuestionEgressDisposition.ALLOWED or decision.minimized_question is None:
            raise RuntimeError(f"poc.fixture_denied:{case.case_id}")
        for repetition in range(1, 4):
            if len(records) >= 30:
                raise RuntimeError("poc.action_budget_exceeded")
            started_call = perf_counter()
            structure_valid = False
            expected_match = False
            decision_name = "invalid_output"
            usage_total_tokens = None
            try:
                request = definition.build_request(
                    ActionSelectionTaskInput(
                        minimized_question=decision.minimized_question,
                        projection=projection,
                    )
                )
                response = await transport.complete(
                    request,
                    call_deadline=asyncio.get_running_loop().time() + timeout_ms / 1000,
                )
                usage_total_tokens = response.usage_total_tokens
                total_tokens += usage_total_tokens or 0
                call = definition.parse_response(response)
                decision_name, arguments = _map_action_call(call.name, call.arguments_json, projection.capability_by_tool)
                structure_valid = _validate_action_arguments(decision_name, arguments)
                expected_match = structure_valid and decision_name == case.expected_capability_id
            except (InvalidModelOutput, ModelInputDenied):
                pass
            except ModelTransportError as exc:
                decision_name = f"provider_{exc.kind.value}"
                provider_failed = True
            records.append(
                PocCallRecord(
                    ordinal=len(records) + 1,
                    case_id=case.case_id,
                    repetition=repetition,
                    decision=decision_name,
                    structure_valid=structure_valid,
                    expected_match=expected_match,
                    latency_ms=round((perf_counter() - started_call) * 1000),
                    usage_total_tokens=usage_total_tokens,
                )
            )
            if provider_failed:
                break
        if provider_failed:
            break

    completed = sum(not record.decision.startswith("provider_") for record in records)
    valid = sum(record.structure_valid for record in records)
    expected = sum(record.expected_match for record in records)
    per_case_passed = all(
        sum(record.expected_match for record in records if record.case_id == case.case_id) >= 2
        for case in ACTION_CASES
    )
    passed = len(records) == 30 and completed == 30 and valid == 30 and expected >= 27 and per_case_passed
    conclusion: Literal["passed", "failed", "incomplete"] = (
        "passed" if passed else ("incomplete" if provider_failed or len(records) < 30 else "failed")
    )
    result = DeepSeekPocResult(
        task="action_selection",
        task_version=definition.task_version,
        started_at_utc=started,
        finished_at_utc=_utc_now(),
        authorized_call_limit=30,
        attempted_calls=len(records),
        completed_calls=completed,
        total_tokens=total_tokens,
        conclusion=conclusion,
        structure_valid_calls=valid,
        expected_calls=expected,
        grounding_expected_calls=None,
        calls=tuple(records),
    )
    return result, write_append_only_result(result, directory=result_directory)


async def run_answer_poc(
    *,
    transport: StructuredModelTransport,
    result_directory: Path,
    timeout_ms: int = 15000,
) -> tuple[DeepSeekPocResult, Path]:
    started = _utc_now()
    definition = build_answer_generation_task_definition(timeout_ms=timeout_ms)
    guard = QuestionEgressGuard()
    records: list[PocCallRecord] = []
    total_tokens = 0
    provider_failed = False

    for case in ANSWER_CASES:
        decision = guard.evaluate(case.question)
        if decision.disposition is not QuestionEgressDisposition.ALLOWED or decision.minimized_question is None:
            raise RuntimeError(f"poc.fixture_denied:{case.case_id}")
        for repetition in range(1, 3):
            if len(records) >= 6:
                raise RuntimeError("poc.answer_budget_exceeded")
            started_call = perf_counter()
            structure_valid = False
            expected_match = False
            grounding_accepted = False
            decision_name = "invalid_output"
            usage_total_tokens = None
            try:
                request = definition.build_request(
                    AnswerGenerationTaskInput(
                        minimized_question=decision.minimized_question,
                        safe_payload=case.safe_payload,
                    )
                )
                response = await transport.complete(
                    request,
                    call_deadline=asyncio.get_running_loop().time() + timeout_ms / 1000,
                )
                usage_total_tokens = response.usage_total_tokens
                total_tokens += usage_total_tokens or 0
                candidate = definition.parse_response(response)
                structure_valid = True
                grounding_accepted = _validate_answer_grounding(case, candidate.answer, frozenset(candidate.used_fact_ids))
                expected_match = grounding_accepted
                decision_name = "accepted" if grounding_accepted else "grounding_rejected"
            except (InvalidModelOutput, ModelInputDenied):
                pass
            except ModelTransportError as exc:
                decision_name = f"provider_{exc.kind.value}"
                provider_failed = True
            records.append(
                PocCallRecord(
                    ordinal=len(records) + 1,
                    case_id=case.case_id,
                    repetition=repetition,
                    decision=decision_name,
                    structure_valid=structure_valid,
                    expected_match=expected_match,
                    grounding_accepted=grounding_accepted,
                    latency_ms=round((perf_counter() - started_call) * 1000),
                    usage_total_tokens=usage_total_tokens,
                )
            )
            if provider_failed:
                break
        if provider_failed:
            break

    completed = sum(not record.decision.startswith("provider_") for record in records)
    valid = sum(record.structure_valid for record in records)
    expected = sum(record.expected_match for record in records)
    grounded = sum(record.grounding_accepted is True for record in records)
    passed = len(records) == 6 and completed == 6 and valid == 6 and expected == 6 and grounded == 6
    conclusion: Literal["passed", "failed", "incomplete"] = (
        "passed" if passed else ("incomplete" if provider_failed or len(records) < 6 else "failed")
    )
    result = DeepSeekPocResult(
        task="answer_generation",
        task_version=definition.task_version,
        started_at_utc=started,
        finished_at_utc=_utc_now(),
        authorized_call_limit=6,
        attempted_calls=len(records),
        completed_calls=completed,
        total_tokens=total_tokens,
        conclusion=conclusion,
        structure_valid_calls=valid,
        expected_calls=expected,
        grounding_expected_calls=grounded,
        calls=tuple(records),
    )
    return result, write_append_only_result(result, directory=result_directory)


def _map_action_call(name: str, arguments_json: str, reverse: object) -> tuple[str, JsonObject]:
    from collections.abc import Mapping

    if not isinstance(reverse, Mapping):
        raise InvalidModelOutput("poc.action_reverse_invalid")
    arguments = parse_unique_json_object(arguments_json, max_bytes=16384, max_depth=8, max_items=256)
    if name == UNSUPPORTED_TOOL_NAME:
        return "agent_unsupported", arguments
    capability_id = reverse.get(name)
    if not isinstance(capability_id, str):
        raise InvalidModelOutput("poc.action_tool_unknown")
    return capability_id, arguments


def _validate_action_arguments(capability_id: str, arguments: JsonObject) -> bool:
    if capability_id == "knowledge.query":
        return set(arguments) == {"question"} and isinstance(arguments.get("question"), str)
    if capability_id in {"employee.query", "transaction.query", "agent_unsupported"}:
        return not arguments
    return False


def _validate_answer_grounding(case: AnswerPocCase, answer: str, used_fact_ids: frozenset[str]) -> bool:
    return used_fact_ids == case.required_fact_ids and all(fragment in answer for fragment in case.required_answer_fragments)
