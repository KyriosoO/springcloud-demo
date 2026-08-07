from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_runtime.model.contracts import (
    QuestionEgressDisposition,
    StructuredFinishKind,
    StructuredModelRequest,
    StructuredModelResponse,
    StructuredToolCall,
)
from agent_runtime.model.deepseek.tools import UNSUPPORTED_TOOL_NAME, project_capability_tools
from agent_runtime.model.input_guard import QuestionEgressGuard
from tests.poc.contracts import (
    ACTION_V3_IMPLEMENTATION_PATHS,
    ActionPocRunAuthorization,
    DeepSeekPocResult,
    PocCallRecord,
    build_action_poc_manifest,
    parse_action_manifest,
    parse_result,
    validate_action_poc_manifest,
    write_append_only_manifest,
    write_append_only_result,
)
from tests.poc.fixtures import ACTION_CASES, ANSWER_CASES, action_descriptors
from tests.poc.runner import run_action_poc


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
RUN_ID = "action-selection-v3-nonlive-test"
AUTHORIZATION_REFERENCE = "P3_00:GATE-035:test"
CANDIDATE_MANIFEST = REPOSITORY_ROOT / "tests/poc/manifests/action-selection-v3-20260807-candidate-01.json"
CANDIDATE_MANIFEST_SHA256 = "fdcbe2a29ab6729e412ba58d7b85c4b7baf68e83ebad4e23da66a7d8008ee635"


def _historical_result() -> DeepSeekPocResult:
    calls = tuple(
        PocCallRecord(
            ordinal=index,
            case_id=f"synthetic_{index}",
            repetition=1,
            decision="knowledge.query",
            structure_valid=True,
            expected_match=True,
            latency_ms=1,
            usage_total_tokens=1,
        )
        for index in range(1, 31)
    )
    return DeepSeekPocResult(
        task="action_selection",
        task_version="action-selection-v2",
        started_at_utc="2026-08-03T00:00:00.000000Z",
        finished_at_utc="2026-08-03T00:00:01.000000Z",
        authorized_call_limit=30,
        attempted_calls=30,
        completed_calls=30,
        total_tokens=30,
        conclusion="passed",
        structure_valid_calls=30,
        expected_calls=30,
        grounding_expected_calls=None,
        calls=calls,
    )


def _write_manifest(tmp_path: Path) -> tuple[Path, str]:
    manifest = build_action_poc_manifest(
        repository_root=REPOSITORY_ROOT,
        run_id=RUN_ID,
        created_at_utc="2026-08-07T00:00:00.000000Z",
        authorization_reference=AUTHORIZATION_REFERENCE,
    )
    path = tmp_path / f"{RUN_ID}.json"
    return path, write_append_only_manifest(manifest, path=path)


class CorrectActionTransport:
    def __init__(self) -> None:
        self.calls = 0
        projection = project_capability_tools(action_descriptors())
        self._tool_by_capability = {
            capability_id: tool_name
            for tool_name, capability_id in projection.capability_by_tool.items()
        }
        self._expected_by_question = {case.question: case.expected_capability_id for case in ACTION_CASES}

    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        del call_deadline
        self.calls += 1
        question = json.loads(request.user_payload_json)["question"]
        expected = self._expected_by_question[question]
        name = UNSUPPORTED_TOOL_NAME if expected == "agent_unsupported" else self._tool_by_capability[expected]
        return StructuredModelResponse(
            finish_kind=StructuredFinishKind.TOOL_CALLS,
            content=None,
            tool_calls=(StructuredToolCall(name=name, arguments_json="{}"),),
            usage_total_tokens=1,
        )


def test_v3_fixture_uses_actual_ids_is_fixed_synthetic_and_allowed() -> None:
    guard = QuestionEgressGuard()
    ids = [case.case_id for case in ACTION_CASES] + [case.case_id for case in ANSWER_CASES]

    assert len(ACTION_CASES) == 10
    assert len(ANSWER_CASES) == 3
    assert len(ids) == len(set(ids))
    assert {descriptor.capability_id for descriptor in action_descriptors()} == {
        "knowledge.query",
        "employee.detail",
        "transaction.search",
    }
    assert {case.expected_capability_id for case in ACTION_CASES} == {
        "knowledge.query",
        "employee.detail",
        "transaction.search",
        "agent_unsupported",
    }
    assert all(guard.evaluate(case.question).disposition is QuestionEgressDisposition.ALLOWED for case in ACTION_CASES)
    assert all(guard.evaluate(case.question).disposition is QuestionEgressDisposition.ALLOWED for case in ANSWER_CASES)


def test_result_contract_is_strict_closed_and_preserves_historical_v2() -> None:
    valid = _historical_result().model_dump()
    with pytest.raises(ValidationError):
        DeepSeekPocResult.model_validate({**valid, "question": "must never persist"}, strict=True)
    with pytest.raises(ValidationError):
        PocCallRecord.model_validate(
            {**valid["calls"][0], "raw_arguments": {"employee_identifier": "forbidden"}},
            strict=True,
        )
    with pytest.raises(ValueError, match="poc.result_duplicate_key"):
        parse_result(b'{"schema_version":1,"schema_version":1}')


def test_append_only_result_writer_refuses_overwrite_and_round_trips(tmp_path: Path) -> None:
    result = _historical_result()
    path = write_append_only_result(result, directory=tmp_path)

    assert parse_result(path.read_bytes()) == result
    with pytest.raises(FileExistsError):
        write_append_only_result(result, directory=tmp_path)


def test_manifest_is_strict_hash_bound_and_append_only(tmp_path: Path) -> None:
    path, digest = _write_manifest(tmp_path)
    manifest, validated_digest = validate_action_poc_manifest(path=path, repository_root=REPOSITORY_ROOT)

    assert validated_digest == digest
    assert manifest.task_version == "action-selection-v3"
    assert tuple(item.path for item in manifest.implementation_files) == ACTION_V3_IMPLEMENTATION_PATHS
    with pytest.raises(FileExistsError):
        write_append_only_manifest(manifest, path=path)
    with pytest.raises(ValueError, match="poc.manifest_duplicate_key"):
        parse_action_manifest(b'{"schema_version":1,"schema_version":1}')

    drifted = manifest.model_copy(update={"case_manifest_sha256": "0" * 64})
    drifted_path = tmp_path / "drifted.json"
    write_append_only_manifest(drifted, path=drifted_path)
    with pytest.raises(ValueError, match="poc.manifest_drift"):
        validate_action_poc_manifest(path=drifted_path, repository_root=REPOSITORY_ROOT)


def test_frozen_candidate_manifest_matches_current_v3_inputs() -> None:
    manifest, digest = validate_action_poc_manifest(
        path=CANDIDATE_MANIFEST,
        repository_root=REPOSITORY_ROOT,
    )

    assert manifest.run_id == "action-selection-v3-20260807-candidate-01"
    assert digest == CANDIDATE_MANIFEST_SHA256
    assert not CANDIDATE_MANIFEST.with_suffix(CANDIDATE_MANIFEST.suffix + ".consumed.json").exists()


@pytest.mark.asyncio
async def test_v3_runner_consumes_authorization_once_and_records_no_arguments(tmp_path: Path) -> None:
    manifest_path, digest = _write_manifest(tmp_path)
    authorization = ActionPocRunAuthorization(
        run_id=RUN_ID,
        manifest_sha256=digest,
        authorization_reference=AUTHORIZATION_REFERENCE,
    )
    transport = CorrectActionTransport()

    result, result_path = await run_action_poc(
        transport=transport,
        manifest_path=manifest_path,
        repository_root=REPOSITORY_ROOT,
        authorization=authorization,
        result_directory=tmp_path / "results",
    )

    assert result_path.is_file()
    assert result.conclusion == "passed"
    assert transport.calls == 30
    assert len({(call.case_id, call.repetition) for call in result.calls}) == 30
    assert all(call.arguments_empty is True for call in result.calls)
    assert "employee_identifier" not in result_path.read_text(encoding="utf-8")
    second_transport = CorrectActionTransport()
    with pytest.raises(RuntimeError, match="poc.authorization_already_consumed"):
        await run_action_poc(
            transport=second_transport,
            manifest_path=manifest_path,
            repository_root=REPOSITORY_ROOT,
            authorization=authorization,
            result_directory=tmp_path / "second-results",
        )
    assert second_transport.calls == 0


@pytest.mark.asyncio
async def test_v3_runner_rejects_manifest_authorization_mismatch_before_outbound(tmp_path: Path) -> None:
    manifest_path, _ = _write_manifest(tmp_path)
    transport = CorrectActionTransport()
    invalid_authorization = ActionPocRunAuthorization(
        run_id=RUN_ID,
        manifest_sha256="0" * 64,
        authorization_reference=AUTHORIZATION_REFERENCE,
    )

    with pytest.raises(ValueError, match="poc.authorization_mismatch"):
        await run_action_poc(
            transport=transport,
            manifest_path=manifest_path,
            repository_root=REPOSITORY_ROOT,
            authorization=invalid_authorization,
            result_directory=tmp_path / "results",
        )

    assert transport.calls == 0
    assert not manifest_path.with_suffix(manifest_path.suffix + ".consumed.json").exists()
