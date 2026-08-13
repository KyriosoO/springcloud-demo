from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agent_runtime.model.contracts import (
    ModelTaskId,
    StructuredModelRequest,
    StructuredModelResponse,
    StructuredModelTransport,
)


_ASCII_SAFE = re.compile(r"^[A-Za-z0-9._:/+-]+$")
_LOWER_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_LOWER_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_RFC3339_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class StrictLiveModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, populate_by_name=True)


class LiveAssetHash(StrictLiveModel):
    path: str = Field(min_length=1, max_length=512)
    sha256: str

    @model_validator(mode="after")
    def validate_asset(self) -> "LiveAssetHash":
        if (
            "\\" in self.path
            or self.path.startswith("/")
            or ".." in Path(self.path).parts
            or not _LOWER_HEX_64.fullmatch(self.sha256)
        ):
            raise ValueError("evaluation.live_manifest_asset_invalid")
        return self


class LivePaidRequestBudget(StrictLiveModel):
    capability_executions: Literal[52] = Field(alias="capabilityExecutions")
    knowledge_rewrite: Literal[26] = Field(alias="knowledgeRewrite")
    knowledge_summary: Literal[52] = Field(alias="knowledgeSummary")
    core_answer: Literal[0] = Field(alias="coreAnswer")
    retry: Literal[0]
    maximum_paid_requests: Literal[78] = Field(alias="maximumPaidRequests")


class LiveGateEvidence(StrictLiveModel):
    gate_id: Literal["SA-GATE-002", "CR-GATE-003", "SA-GATE-003", "SA-GATE-006"] = Field(alias="gateId")
    evidence_ref: str = Field(alias="evidenceRef", min_length=1, max_length=256)

    @field_validator("evidence_ref")
    @classmethod
    def validate_reference(cls, value: str) -> str:
        if not _ASCII_SAFE.fullmatch(value):
            raise ValueError("evaluation.live_gate_reference_invalid")
        return value


class LiveRetrievalBinding(StrictLiveModel):
    read_alias: Literal["agent-doc-tax-policy-v2-read"] = Field(alias="readAlias")
    expected_index_name: Literal["agent-doc-tax-policy-v3-20260803-agent-read-v1"] = Field(alias="expectedIndexName")
    expected_index_uuid: Literal["k97bn1gxROSfVm7zGfzbOg"] = Field(alias="expectedIndexUuid")
    mapping_version: Literal["agent-knowledge-tax-v1"] = Field(alias="mappingVersion")
    policy_snapshot_id: Literal["7c71202794927a9497fed9df7cc0db5a052a53f0f6c2afdb6c0a16089f1c96ed"] = Field(
        alias="policySnapshotId"
    )
    law_snapshot_id: Literal["99ae962ae1c8e5026187c864eada38b3c3b82d6b017e6e8f076f116aba53fce2"] = Field(
        alias="lawSnapshotId"
    )


class LiveP5Manifest(StrictLiveModel):
    schema_version: Literal[1, 2] = Field(alias="schemaVersion")
    status: Literal["prepared_unconsumed"]
    work_package_id: Literal["WP-KP5-LIVE-01"] = Field(alias="workPackageId")
    run_id: str = Field(alias="runId", min_length=1, max_length=64)
    authorization_reference: str = Field(alias="authorizationReference", min_length=1, max_length=256)
    dataset_path: Literal["agent-runtime/tests/evaluation/knowledge/representative_questions.v1.jsonl"] = Field(alias="datasetPath")
    dataset_sha256: str = Field(alias="datasetSha256")
    dataset_case_count: Literal[26] = Field(alias="datasetCaseCount")
    evaluation_variants: tuple[Literal["primary"], Literal["rewrite_ablation"]] = Field(alias="evaluationVariants")
    principal_profile_id: Literal["tax-knowledge-admin-reader-v1"] = Field(alias="principalProfileId")
    read_authorization_evidence_ref: Literal["WP-KRET-REAL-01:authorizationMatrix.admin"] = Field(alias="readAuthorizationEvidenceRef")
    gate_evidence: tuple[LiveGateEvidence, LiveGateEvidence, LiveGateEvidence, LiveGateEvidence] = Field(alias="gateEvidence")
    paid_request_budget: LivePaidRequestBudget = Field(alias="paidRequestBudget")
    provider_mode: Literal["live"] = Field(alias="providerMode")
    model_name: Literal["deepseek-v4-pro"] = Field(alias="modelName")
    task_versions: dict[Literal["knowledge_rewrite", "knowledge_summary"], str] = Field(alias="taskVersions")
    index_snapshot_ids: tuple[str, str] = Field(alias="indexSnapshotIds")
    retrieval_binding: LiveRetrievalBinding | None = Field(default=None, alias="retrievalBinding")
    asset_hashes: tuple[LiveAssetHash, ...] = Field(alias="assetHashes", min_length=1)
    prepared_at: str = Field(alias="preparedAt")

    @field_validator("evaluation_variants", "gate_evidence", "index_snapshot_ids", "asset_hashes", mode="before")
    @classmethod
    def decode_json_array(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def validate_manifest(self) -> "LiveP5Manifest":
        expected_gates = ("SA-GATE-002", "CR-GATE-003", "SA-GATE-003", "SA-GATE-006")
        if (
            not _ASCII_SAFE.fullmatch(self.run_id)
            or not _ASCII_SAFE.fullmatch(self.authorization_reference)
            or not _LOWER_HEX_64.fullmatch(self.dataset_sha256)
            or tuple(item.gate_id for item in self.gate_evidence) != expected_gates
            or set(self.task_versions) != {"knowledge_rewrite", "knowledge_summary"}
            or self.task_versions != {"knowledge_rewrite": "1", "knowledge_summary": "2"}
            or len(set(self.index_snapshot_ids)) != 2
            or any(not _LOWER_HEX_64.fullmatch(item) for item in self.index_snapshot_ids)
            or (self.schema_version == 1 and self.retrieval_binding is not None)
            or (self.schema_version == 2 and self.retrieval_binding is None)
            or tuple(item.path for item in self.asset_hashes) != tuple(sorted(item.path for item in self.asset_hashes))
            or len({item.path for item in self.asset_hashes}) != len(self.asset_hashes)
            or not _valid_utc_seconds(self.prepared_at)
        ):
            raise ValueError("evaluation.live_manifest_invalid")
        if self.retrieval_binding is not None and self.index_snapshot_ids != (
            self.retrieval_binding.policy_snapshot_id,
            self.retrieval_binding.law_snapshot_id,
        ):
            raise ValueError("evaluation.live_manifest_retrieval_binding_invalid")
        return self


class LiveAuthorizationRecord(StrictLiveModel):
    schema_version: Literal[1] = Field(alias="schemaVersion")
    status: Literal["authorized_unconsumed"]
    work_package_id: Literal["WP-KP5-LIVE-01"] = Field(alias="workPackageId")
    run_id: str = Field(alias="runId", min_length=1, max_length=64)
    authorization_reference: str = Field(alias="authorizationReference", min_length=1, max_length=256)
    single_use: Literal[True] = Field(alias="singleUse")
    maximum_paid_requests: Literal[78] = Field(alias="maximumPaidRequests")
    retry_allowed: Literal[False] = Field(alias="retryAllowed")
    answer_requests_allowed: Literal[False] = Field(alias="answerRequestsAllowed")
    live_p5_authorized: Literal[True] = Field(alias="liveP5Authorized")
    dataset_sha256: str = Field(alias="datasetSha256")
    principal_profile_id: Literal["tax-knowledge-admin-reader-v1"] = Field(alias="principalProfileId")
    read_authorization_evidence_ref: Literal["WP-KRET-REAL-01:authorizationMatrix.admin"] = Field(alias="readAuthorizationEvidenceRef")
    jwt_persisted: Literal[False] = Field(alias="jwtPersisted")
    api_key_persisted: Literal[False] = Field(alias="apiKeyPersisted")
    confirmed_by: Literal["project-maintainer"] = Field(alias="confirmedBy")
    confirmed_at: str = Field(alias="confirmedAt")

    @model_validator(mode="after")
    def validate_authorization(self) -> "LiveAuthorizationRecord":
        if (
            not _ASCII_SAFE.fullmatch(self.run_id)
            or not _ASCII_SAFE.fullmatch(self.authorization_reference)
            or not _LOWER_HEX_64.fullmatch(self.dataset_sha256)
            or not _valid_utc_seconds(self.confirmed_at)
        ):
            raise ValueError("evaluation.live_authorization_invalid")
        return self


class HumanRubricDecision(StrictLiveModel):
    case_id: str = Field(alias="caseId", min_length=1, max_length=64)
    faithful: bool
    relevant: bool
    sufficient_for_initial_answer: bool = Field(alias="sufficientForInitialAnswer")
    useful: bool
    judgment_reason: Literal["none", "quote_context", "relevance", "coverage", "gold_issue"] = Field(alias="judgmentReason")

    @model_validator(mode="after")
    def validate_decision(self) -> "HumanRubricDecision":
        if not _ASCII_SAFE.fullmatch(self.case_id) or self.useful != (
            self.faithful and self.relevant and self.sufficient_for_initial_answer
        ):
            raise ValueError("evaluation.live_rubric_invalid")
        if self.useful != (self.judgment_reason == "none"):
            raise ValueError("evaluation.live_rubric_reason_invalid")
        return self


class HumanRubricSubmission(StrictLiveModel):
    schema_version: Literal[1] = Field(alias="schemaVersion")
    run_id: str = Field(alias="runId", min_length=1, max_length=64)
    reviewer: str = Field(min_length=1, max_length=128)
    decisions: tuple[HumanRubricDecision, ...] = Field(min_length=26, max_length=26)

    @field_validator("decisions", mode="before")
    @classmethod
    def decode_json_array(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def validate_submission(self) -> "HumanRubricSubmission":
        if (
            not _ASCII_SAFE.fullmatch(self.run_id)
            or not _ASCII_SAFE.fullmatch(self.reviewer)
            or len({item.case_id for item in self.decisions}) != 26
        ):
            raise ValueError("evaluation.live_rubric_invalid")
        return self


def _valid_utc_seconds(value: str) -> bool:
    if not _RFC3339_UTC.fullmatch(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    offset = parsed.utcoffset()
    return offset is not None and offset.total_seconds() == 0


def strict_json_bytes(path: Path) -> tuple[dict[str, Any], bytes]:
    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in pairs:
            if key in output:
                raise ValueError("evaluation.live_duplicate_json_key")
            output[key] = value
        return output

    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_pairs)
    if type(value) is not dict:
        raise ValueError("evaluation.live_json_object_required")
    return value, raw


def load_manifest(path: Path) -> tuple[LiveP5Manifest, str]:
    value, raw = strict_json_bytes(path)
    return LiveP5Manifest.model_validate(value), hashlib.sha256(raw).hexdigest()


def load_authorization(path: Path) -> LiveAuthorizationRecord:
    value, _ = strict_json_bytes(path)
    return LiveAuthorizationRecord.model_validate(value)


def verify_manifest_assets(*, manifest: LiveP5Manifest, repository_root: Path) -> None:
    for asset in manifest.asset_hashes:
        resolved = (repository_root / asset.path).resolve()
        try:
            resolved.relative_to(repository_root.resolve())
        except ValueError as exc:
            raise ValueError("evaluation.live_manifest_asset_invalid") from exc
        if not resolved.is_file() or hashlib.sha256(resolved.read_bytes()).hexdigest() != asset.sha256:
            raise ValueError("evaluation.live_manifest_asset_drift")


@dataclass(frozen=True, slots=True, kw_only=True)
class LiveAttemptContext:
    case_id: str
    variant: Literal["primary", "rewrite_ablation"]


class BudgetedLiveModelTransport:
    def __init__(
        self,
        *,
        delegate: StructuredModelTransport,
        output_dir: Path,
        manifest: LiveP5Manifest,
        manifest_sha256: str,
        frozen_head: str,
    ) -> None:
        if not _LOWER_HEX_64.fullmatch(manifest_sha256) or not _LOWER_HEX_40.fullmatch(frozen_head):
            raise ValueError("evaluation.live_binding_invalid")
        self._delegate = delegate
        self._output_dir = output_dir
        self._manifest = manifest
        self._manifest_sha256 = manifest_sha256
        self._frozen_head = frozen_head
        self._active: LiveAttemptContext | None = None
        self._tasks_in_active: set[ModelTaskId] = set()
        self._calls_by_task = {ModelTaskId.KNOWLEDGE_REWRITE: 0, ModelTaskId.KNOWLEDGE_SUMMARY: 0}
        self._total_calls = 0
        self._unauthorized_content_count = 0

    @property
    def total_calls(self) -> int:
        return self._total_calls

    @property
    def rewrite_calls(self) -> int:
        return self._calls_by_task[ModelTaskId.KNOWLEDGE_REWRITE]

    @property
    def summary_calls(self) -> int:
        return self._calls_by_task[ModelTaskId.KNOWLEDGE_SUMMARY]

    @property
    def unauthorized_content_count(self) -> int:
        return self._unauthorized_content_count

    def begin(self, *, case_id: str, variant: Literal["primary", "rewrite_ablation"]) -> None:
        if self._active is not None:
            raise RuntimeError("evaluation.live_attempt_overlap")
        self._active = LiveAttemptContext(case_id=case_id, variant=variant)
        self._tasks_in_active.clear()

    def end(self) -> None:
        if self._active is None:
            raise RuntimeError("evaluation.live_attempt_missing")
        self._active = None
        self._tasks_in_active.clear()

    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        active = self._active
        if active is None:
            raise RuntimeError("evaluation.live_attempt_missing")
        if request.task_id not in self._calls_by_task:
            raise RuntimeError("evaluation.live_task_forbidden")
        if request.task_id in self._tasks_in_active:
            raise RuntimeError("evaluation.live_retry_forbidden")
        if active.variant == "rewrite_ablation" and request.task_id is ModelTaskId.KNOWLEDGE_REWRITE:
            raise RuntimeError("evaluation.live_ablation_rewrite_forbidden")
        limits = {
            ModelTaskId.KNOWLEDGE_REWRITE: self._manifest.paid_request_budget.knowledge_rewrite,
            ModelTaskId.KNOWLEDGE_SUMMARY: self._manifest.paid_request_budget.knowledge_summary,
        }
        if self._total_calls >= self._manifest.paid_request_budget.maximum_paid_requests:
            raise RuntimeError("evaluation.live_paid_budget_exhausted")
        if self._calls_by_task[request.task_id] >= limits[request.task_id]:
            raise RuntimeError("evaluation.live_task_budget_exhausted")
        if request.task_id is ModelTaskId.KNOWLEDGE_SUMMARY:
            self._unauthorized_content_count += _forbidden_payload_key_count(request.user_payload_json)
            if self._unauthorized_content_count:
                raise RuntimeError("evaluation.live_unauthorized_content")
        if self._total_calls == 0:
            self._consume_authorization()
        self._tasks_in_active.add(request.task_id)
        self._total_calls += 1
        self._calls_by_task[request.task_id] += 1
        ordinal = self._total_calls
        self._append_journal(
            {
                "schemaVersion": 1,
                "runId": self._manifest.run_id,
                "callOrdinal": ordinal,
                "caseId": active.case_id,
                "variant": active.variant,
                "taskId": request.task_id.value,
                "event": "started",
            }
        )
        try:
            response = await self._delegate.complete(request, call_deadline=call_deadline)
        except BaseException:
            self._append_terminal(ordinal=ordinal, active=active, request=request, status="failed")
            raise
        self._append_terminal(ordinal=ordinal, active=active, request=request, status="completed")
        return response

    def _consume_authorization(self) -> None:
        self._output_dir.mkdir(parents=True, exist_ok=False)
        value = {
            "schemaVersion": 1,
            "status": "consumed",
            "workPackageId": "WP-KP5-LIVE-01",
            "runId": self._manifest.run_id,
            "manifestSha256": self._manifest_sha256,
            "authorizationReference": self._manifest.authorization_reference,
            "frozenGitCommit": self._frozen_head,
            "maximumPaidRequests": self._manifest.paid_request_budget.maximum_paid_requests,
            "retryAllowed": False,
        }
        _write_exclusive(self._output_dir / "authorization.consumed.json", value)

    def _append_terminal(
        self,
        *,
        ordinal: int,
        active: LiveAttemptContext,
        request: StructuredModelRequest,
        status: Literal["completed", "failed"],
    ) -> None:
        self._append_journal(
            {
                "schemaVersion": 1,
                "runId": self._manifest.run_id,
                "callOrdinal": ordinal,
                "caseId": active.case_id,
                "variant": active.variant,
                "taskId": request.task_id.value,
                "event": "terminal",
                "status": status,
            }
        )

    def _append_journal(self, value: dict[str, Any]) -> None:
        path = self._output_dir / "paid-attempts.jsonl"
        encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())


def _forbidden_payload_key_count(raw: str) -> int:
    forbidden = {
        "evidence_id",
        "document_id",
        "chunk_id",
        "source_url",
        "policy_ref",
        "policy_version",
        "index_snapshot_id",
        "read_policy_version",
        "subject",
        "jwt",
        "user_token",
    }
    value = json.loads(raw)

    def count(item: object) -> int:
        if isinstance(item, dict):
            return sum(key in forbidden for key in item) + sum(count(child) for child in item.values())
        if isinstance(item, list):
            return sum(count(child) for child in item)
        return 0

    return count(value)


def _write_exclusive(path: Path, value: object) -> None:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    with path.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
