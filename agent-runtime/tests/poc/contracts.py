from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent_runtime.capability_api.contracts import JsonValue, canonical_json_bytes


HISTORICAL_ACTION_V4_RUN_ID = "action-selection-v4-20260807-candidate-01"
HISTORICAL_ACTION_V4_CASE_IDS = (
    "tax_policy_scope",
    "tax_invoice_rule",
    "tax_filing_rule",
    "employee_detail_how",
    "employee_detail_view",
    "employee_detail_single",
    "transaction_conditions",
    "transaction_fields",
    "transaction_filters",
    "unsupported_traffic_law",
)

HISTORICAL_ACTION_V4_IMPLEMENTATION_PATHS = (
    "src/agent_runtime/adapters/employee/definition.py",
    "src/agent_runtime/adapters/transaction/definition.py",
    "src/agent_runtime/knowledge/provider.py",
    "src/agent_runtime/model/input_guard.py",
    "src/agent_runtime/model/question_policy.py",
    "src/agent_runtime/model/deepseek/action_selector.py",
    "src/agent_runtime/model/deepseek/tools.py",
    "src/agent_runtime/model/deepseek/dto.py",
    "src/agent_runtime/model/deepseek/json_codec.py",
    "tests/poc/contracts.py",
    "tests/poc/fixtures.py",
    "tests/poc/fixtures/action_selection_v4.json",
    "tests/poc/prepare_action_selection_v4_manifest.py",
    "tests/poc/runner.py",
    "tests/poc/test_deepseek_action_selection_live.py",
)

ACTION_V4_IMPLEMENTATION_PATHS = tuple(
    "tests/poc/fixtures/action_selection_v4_2.json"
    if path == "tests/poc/fixtures/action_selection_v4.json"
    else path
    for path in HISTORICAL_ACTION_V4_IMPLEMENTATION_PATHS
)


class PocFileHash(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    path: str = Field(pattern=r"^[a-z0-9_./-]{3,255}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ActionPocManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal[1] = 1
    run_id: str = Field(pattern=r"^action-selection-v4-[a-z0-9][a-z0-9-]{5,63}$")
    created_at_utc: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")
    model: Literal["deepseek-v4-pro"] = "deepseek-v4-pro"
    task_version: Literal["action-selection-v4"] = "action-selection-v4"
    authorization_reference: str = Field(pattern=r"^[A-Za-z0-9_.:-]{3,128}$")
    authorized_call_limit: Literal[30] = 30
    case_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    system_instruction_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    implementation_files: tuple[PocFileHash, ...]

    @model_validator(mode="after")
    def validate_file_set(self) -> "ActionPocManifest":
        paths = tuple(item.path for item in self.implementation_files)
        expected_paths = (
            HISTORICAL_ACTION_V4_IMPLEMENTATION_PATHS
            if self.run_id == HISTORICAL_ACTION_V4_RUN_ID
            else ACTION_V4_IMPLEMENTATION_PATHS
        )
        if paths != expected_paths:
            raise ValueError("poc.manifest_file_set_invalid")
        return self


class ActionPocRunAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    run_id: str = Field(pattern=r"^action-selection-v4-[a-z0-9][a-z0-9-]{5,63}$")
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authorization_reference: str = Field(pattern=r"^[A-Za-z0-9_.:-]{3,128}$")
    authorized_call_limit: Literal[30] = 30


class PocCallRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    ordinal: int = Field(ge=1, le=36)
    case_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")
    repetition: int = Field(ge=1, le=3)
    decision: str = Field(min_length=1, max_length=128)
    structure_valid: bool
    expected_match: bool
    arguments_empty: bool | None = None
    grounding_accepted: bool | None = None
    public_unsupported_claim: bool = False
    latency_ms: int = Field(ge=0, le=120000)
    usage_total_tokens: int | None = Field(default=None, ge=0)


class DeepSeekPocResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal[1] = 1
    task: Literal["action_selection", "answer_generation"]
    model: Literal["deepseek-v4-pro"] = "deepseek-v4-pro"
    task_version: str = Field(min_length=1, max_length=64)
    run_id: str | None = Field(
        default=None,
        pattern=r"^action-selection-v(?:3|4)-[a-z0-9][a-z0-9-]{5,63}$",
    )
    manifest_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    started_at_utc: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")
    finished_at_utc: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")
    authorized_call_limit: int = Field(ge=1, le=30)
    attempted_calls: int = Field(ge=0, le=30)
    completed_calls: int = Field(ge=0, le=30)
    total_tokens: int = Field(ge=0)
    conclusion: Literal["passed", "failed", "incomplete"]
    structure_valid_calls: int = Field(ge=0, le=30)
    expected_calls: int = Field(ge=0, le=30)
    grounding_expected_calls: int | None = Field(default=None, ge=0, le=6)
    invalid_execution_count: Literal[0] = 0
    public_unsupported_claims: Literal[0] = 0
    calls: tuple[PocCallRecord, ...]

    @model_validator(mode="after")
    def validate_counts(self) -> "DeepSeekPocResult":
        if self.attempted_calls != len(self.calls):
            raise ValueError("poc.call_count_mismatch")
        if self.completed_calls > self.attempted_calls:
            raise ValueError("poc.completed_count_invalid")
        if self.structure_valid_calls > self.completed_calls or self.expected_calls > self.completed_calls:
            raise ValueError("poc.metric_count_invalid")
        if (
            self.structure_valid_calls != sum(call.structure_valid for call in self.calls)
            or self.expected_calls != sum(call.expected_match for call in self.calls)
        ):
            raise ValueError("poc.metric_count_mismatch")
        expected_limit = 30 if self.task == "action_selection" else 6
        if self.authorized_call_limit != expected_limit:
            raise ValueError("poc.authorized_limit_invalid")
        if self.task == "action_selection" and self.grounding_expected_calls is not None:
            raise ValueError("poc.action_grounding_forbidden")
        if self.task == "answer_generation" and self.grounding_expected_calls is None:
            raise ValueError("poc.answer_grounding_required")
        if self.task == "action_selection" and self.task_version in {
            "action-selection-v3",
            "action-selection-v4",
        }:
            if self.run_id is None or self.manifest_sha256 is None:
                raise ValueError("poc.action_manifest_required")
            keys = tuple((call.case_id, call.repetition) for call in self.calls)
            if (
                tuple(call.ordinal for call in self.calls) != tuple(range(1, len(self.calls) + 1))
                or len(keys) != len(set(keys))
                or any(call.arguments_empty is None for call in self.calls)
            ):
                raise ValueError("poc.action_record_invalid")
            allowed_decisions = {
                "knowledge.query",
                "employee.detail",
                "transaction.search",
                "agent_unsupported",
                "invalid_output",
                "provider_input_denied",
                "provider_provider_timeout",
                "provider_provider_failure",
                "provider_invalid_output",
            }
            if any(call.decision not in allowed_decisions for call in self.calls):
                raise ValueError("poc.action_record_invalid")
            if self.task_version == "action-selection-v4":
                from tests.poc.fixtures import ACTION_CASES

                case_ids = (
                    HISTORICAL_ACTION_V4_CASE_IDS
                    if self.run_id == HISTORICAL_ACTION_V4_RUN_ID
                    else tuple(case.case_id for case in ACTION_CASES)
                )
                expected_keys = {
                    (case_id, repetition)
                    for case_id in case_ids
                    for repetition in range(1, 4)
                }
                if not set(keys).issubset(expected_keys):
                    raise ValueError("poc.action_record_invalid")
                if self.conclusion == "passed" and set(keys) != expected_keys:
                    raise ValueError("poc.action_pass_invalid")
            if self.conclusion == "passed" and (
                len(self.calls) != 30
                or self.completed_calls != 30
                or self.structure_valid_calls != 30
                or self.expected_calls < 27
                or not all(call.arguments_empty is True for call in self.calls)
            ):
                raise ValueError("poc.action_pass_invalid")
            if self.task_version == "action-selection-v4" and self.conclusion == "passed":
                if any(
                    sum(
                        call.expected_match
                        for call in self.calls
                        if call.case_id == case_id
                    )
                    < 2
                    for case_id in {call.case_id for call in self.calls}
                ):
                    raise ValueError("poc.action_pass_invalid")
        elif self.run_id is not None or self.manifest_sha256 is not None:
            raise ValueError("poc.manifest_reference_forbidden")
        return self


def build_action_poc_manifest(
    *,
    repository_root: Path,
    run_id: str,
    created_at_utc: str,
    authorization_reference: str,
) -> ActionPocManifest:
    from agent_runtime.model.deepseek.action_selector import ACTION_SELECTION_SYSTEM_INSTRUCTION
    from agent_runtime.model.deepseek.tools import project_capability_catalog
    from tests.poc.fixtures import ACTION_CASES, action_descriptors

    cases = tuple(case.model_dump(mode="json") for case in ACTION_CASES)
    catalog = project_capability_catalog(action_descriptors())
    file_hashes = tuple(
        PocFileHash(path=path, sha256=_sha256_bytes((repository_root / path).read_bytes()))
        for path in ACTION_V4_IMPLEMENTATION_PATHS
    )
    return ActionPocManifest(
        run_id=run_id,
        created_at_utc=created_at_utc,
        authorization_reference=authorization_reference,
        case_manifest_sha256=_sha256_canonical(cases),
        system_instruction_sha256=_sha256_canonical(ACTION_SELECTION_SYSTEM_INSTRUCTION),
        catalog_sha256=_sha256_canonical(catalog),
        implementation_files=file_hashes,
    )


def write_append_only_manifest(manifest: ActionPocManifest, *, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_json_bytes(cast(JsonValue, manifest.model_dump(mode="json"))) + b"\n"
    with path.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    parsed = parse_action_manifest(path.read_bytes())
    if parsed != manifest:
        raise RuntimeError("poc.manifest_round_trip_failed")
    return _sha256_bytes(path.read_bytes())


def parse_action_manifest(raw: bytes) -> ActionPocManifest:
    value = _parse_unique_json(raw, duplicate_code="poc.manifest_duplicate_key", invalid_code="poc.manifest_json_invalid")
    return ActionPocManifest.model_validate(_freeze_lists(value), strict=True)


def validate_action_poc_manifest(*, path: Path, repository_root: Path) -> tuple[ActionPocManifest, str]:
    raw = path.read_bytes()
    manifest = parse_action_manifest(raw)
    expected = build_action_poc_manifest(
        repository_root=repository_root,
        run_id=manifest.run_id,
        created_at_utc=manifest.created_at_utc,
        authorization_reference=manifest.authorization_reference,
    )
    if manifest != expected:
        raise ValueError("poc.manifest_drift")
    return manifest, _sha256_bytes(raw)


def consume_action_poc_authorization(
    *,
    manifest_path: Path,
    manifest: ActionPocManifest,
    manifest_sha256: str,
    authorization: ActionPocRunAuthorization,
    consumed_at_utc: str,
) -> Path:
    if (
        authorization.run_id != manifest.run_id
        or authorization.manifest_sha256 != manifest_sha256
        or authorization.authorization_reference != manifest.authorization_reference
        or authorization.authorized_call_limit != manifest.authorized_call_limit
    ):
        raise ValueError("poc.authorization_mismatch")
    marker = manifest_path.with_suffix(manifest_path.suffix + ".consumed.json")
    payload = {
        "schema_version": 1,
        "run_id": manifest.run_id,
        "manifest_sha256": manifest_sha256,
        "consumed_at_utc": consumed_at_utc,
    }
    encoded = canonical_json_bytes(cast(JsonValue, payload)) + b"\n"
    try:
        with marker.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise RuntimeError("poc.authorization_already_consumed") from exc
    return marker


def write_append_only_result(result: DeepSeekPocResult, *, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stem = result.started_at_utc.replace(":", "").replace("-", "").replace(".", "")
    target = directory / f"{result.task}-{stem}.json"
    encoded = result.model_dump_json(indent=2).encode("utf-8") + b"\n"
    with target.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    decoded = DeepSeekPocResult.model_validate_json(target.read_bytes(), strict=True)
    if decoded != result:
        raise RuntimeError("poc.result_round_trip_failed")
    return target


def parse_result(raw: bytes) -> DeepSeekPocResult:
    value = _parse_unique_json(raw, duplicate_code="poc.result_duplicate_key", invalid_code="poc.result_json_invalid")
    return DeepSeekPocResult.model_validate(_freeze_lists(value), strict=True)


def _parse_unique_json(raw: bytes, *, duplicate_code: str, invalid_code: str) -> object:
    try:
        return json.loads(raw, object_pairs_hook=_unique_object)
    except _DuplicateKey as exc:
        raise ValueError(duplicate_code) from exc
    except (TypeError, ValueError) as exc:
        raise ValueError(invalid_code) from exc


def _sha256_canonical(value: object) -> str:
    return _sha256_bytes(canonical_json_bytes(cast(JsonValue, value)))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class _DuplicateKey(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey
        result[key] = value
    return result


def _freeze_lists(value: object) -> object:
    if isinstance(value, list):
        return tuple(_freeze_lists(item) for item in value)
    if isinstance(value, dict):
        return {key: _freeze_lists(item) for key, item in value.items()}
    return value
