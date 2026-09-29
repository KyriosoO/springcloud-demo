"""Freeze and consume one B representation candidate without retaining source text.

This is an offline driver for the existing one-use candidate builder.  A frozen
binding is not evidence that the live source or model still matches: the builder
must prove those facts again before it clones an index.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
import unicodedata

import httpx

from .jsonio import exclusive_write
from .errors import ContractError
from .b_id_mapping_v1 import BIdMappingError, MappingScanSpec, scan_id_mapping_v1
from .rechunk_candidate_v1 import (
    CandidateSpec, PrepareVectors, RechunkCandidateError, RepresentationScopeV1,
    build_rechunk_candidate_v1, new_build_owner_alias,
)
from .vector_candidate import _reject_constant, _unique_pairs, canonical_bytes

_SHA = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_RUN = re.compile(r"[a-z0-9][a-z0-9-]{4,95}")
_SPEC_KEYS = frozenset({
    "source_index", "source_uuid", "source_mapping_sha256", "source_fingerprint",
    "source_count", "read_alias", "online_index", "online_uuid",
    "online_mapping_sha256", "alias_snapshot_sha256", "candidate_index",
    "target_mapping_version", "target_mapping_sha256", "baseline_model_snapshot",
    "model_snapshot", "tokenizer_sha256", "baseline_representation_version",
})
_ROW_KEYS = frozenset({
    "identifier", "document_id", "parent_document_id", "asset_id",
    "asset_version", "version", "input_sha256", "body_sha256",
})
_BUDGET_KEYS = frozenset({
    "esHttp", "embeddingHttp", "writeOps", "paid", "retry", "resume",
    "onlineAliasWrites", "candidates",
})
_INPUT_KEYS = frozenset({
    "schemaVersion", "runId", "frozenHead", "assessmentIntentSha256", "idMappingSha256", "candidate",
    "representationBindings", "budget", "mappingScanBudget",
})
_SCAN_INPUT_KEYS = _INPUT_KEYS - {"idMappingSha256"}
_SCAN_BUDGET_KEYS = frozenset({"sourceEsHttp", "candidateEsHttp", "retry", "resume"})
_BINDING_KEYS = frozenset({
    "schemaVersion", "kind", "runId", "frozenHead", "branch",
    "assessmentIntentSha256", "idMappingSha256", "idMappingSourceFingerprint",
    "freezeInputSha256", "scanPlanSha256", "sourceMapScanResultSha256",
    "sourceVerification",
    "spec", "representationBindings", "budget", "mappingScanBudget",
})
_INTENT_KEYS = frozenset({
    "schemaVersion", "kind", "uatFixtureSha256", "source", "candidate",
    "profileParameters", "baselineProfileSnapshots", "builderBudget",
    "mappingScanBudget", "comparisonBudget", "representationBindings",
    "modelBindings", "sourceBuildEvidence", "cases", "thresholds",
})
_SOURCE_BUILD_EVIDENCE_KEYS = frozenset({
    "bindingPath", "bindingSha256", "resultPath", "resultSha256",
})
_SOURCE_BUILD_DIRECTORY = "knowledge-corpus-tools/evidence/policy-vector-candidate-20260907-b2"
_SOURCE_BUILD_PATHS = (
    f"{_SOURCE_BUILD_DIRECTORY}/binding.json",
    f"{_SOURCE_BUILD_DIRECTORY}/result.json",
)
_INTENT_SOURCE_KEYS = frozenset({
    "indexName", "indexUuid", "mappingSha256", "sourceFingerprint", "recordCount",
})
_INTENT_CANDIDATE_KEYS = frozenset({"indexName", "mappingSha256", "mappingVersion"})
_PROFILE_PARAMETER_KEYS = frozenset({
    "profileId", "profileVersion", "readPolicyVersion", "baselineMappingVersion",
    "candidateMappingVersion", "configSha256",
})
_COMPARISON_BUDGET_KEYS = frozenset({
    "typedSearch", "queryEmbedding", "rerank", "aliasWrites", "metadataEsHttp",
    "paid", "retry", "resume",
})
_MODEL_BINDING_KEYS = frozenset({
    "baselineModelSnapshotSha256", "currentModelSnapshotSha256",
    "tokenizerSha256", "baselineRepresentationVersion",
    "candidateRepresentationVersion",
})
_FINAL_KEYS = frozenset({
    "schemaVersion", "kind", "assessmentIntentSha256", "bindingSha256",
    "builderResultSha256", "sourceMapScanResultSha256",
    "candidateMapScanResultSha256", "sourceIdMappingSha256",
    "candidateIdMappingSha256", "candidateIdentity", "candidateProfileSnapshots",
})
_MAX_JSON = 2 * 1024 * 1024
_MAX_MAPPING_JSON = 16 * 1024 * 1024
_FIXTURE_PATH = "agent-runtime/tests/uat/knowledge_rebuild_measure.v1.json"
_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class BFreezeError(Exception):
    """Finite reason only; never embed JSON, text, HTTP or provider exceptions."""

    def __init__(self, reason: str) -> None:
        self.reason = reason if reason in {
            "input_invalid", "assessment_invalid", "git_state_invalid", "budget_invalid",
            "binding_invalid", "already_frozen", "already_consumed", "evidence_io_failed",
        } else "input_invalid"
        super().__init__(self.reason)


@dataclass(frozen=True, slots=True)
class GitState:
    branch: str
    head: str
    tracked_clean: bool


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_object(raw: bytes, *, maximum: int = _MAX_JSON) -> dict[str, Any]:
    if not raw or len(raw) > maximum:
        raise BFreezeError("input_invalid")
    try:
        value = json.loads(raw, object_pairs_hook=_unique_pairs,
                           parse_constant=_reject_constant)
    except (UnicodeError, ValueError):
        raise BFreezeError("input_invalid") from None
    if type(value) is not dict:
        raise BFreezeError("input_invalid")
    return value


def _id_mapping(raw: bytes, *, source_index: str, source_uuid: str,
                source_fingerprint: str, source_count: int) -> tuple[str, str, tuple[tuple[str, str, str, str], ...]]:
    """Validate a content-free, ordered `_id` bridge; the scanner owns its provenance."""
    value = _json_object(raw, maximum=_MAX_MAPPING_JSON)
    if (set(value) != {"schemaVersion", "indexName", "indexUuid", "sourceFingerprint",
                       "recordCount", "records"}
            or type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1
            or value["indexName"] != source_index
            or value["indexUuid"] != source_uuid
            or type(value["recordCount"]) is not int
            or value["recordCount"] != source_count
            or not _hash(value["sourceFingerprint"])
            or value["sourceFingerprint"] != source_fingerprint
            or type(value["records"]) is not list
            or len(value["records"]) != source_count
            or canonical_bytes(value) != raw):
        raise BFreezeError("binding_invalid")
    previous = ""
    pairs: set[tuple[str, str]] = set()
    identities: list[tuple[str, str, str, str]] = []
    for item in value["records"]:
        if type(item) is not dict or set(item) != {
                "id", "documentId", "chunkId", "contentSha256"}:
            raise BFreezeError("binding_invalid")
        if (any(type(item[key]) is not str or not 1 <= len(item[key]) <= 256
                or item[key] != unicodedata.normalize("NFC", item[key])
                for key in ("id", "documentId", "chunkId"))
                or not _hash(item["contentSha256"]) or item["id"] <= previous):
            raise BFreezeError("binding_invalid")
        previous = item["id"]
        pair = (item["documentId"], item["chunkId"])
        if pair in pairs:
            raise BFreezeError("binding_invalid")
        pairs.add(pair)
        identities.append((item["id"], item["documentId"], item["chunkId"],
                           item["contentSha256"]))
    return _sha(raw), value["sourceFingerprint"], tuple(identities)


_B_CASE_IDS = tuple(f"UAT-KM-{number:03d}" for number in
                    (1, 2, 3, 5, 6, 7, 8, 9, 11, 12))
_THRESHOLDS = {
    "macroRecallStrictlyImproves": True,
    "macroPrecisionNoRegression": True,
    "medianLatencyRatioMax": 1.1,
    "coreAndRetainedNoRegression": True,
    "missingBlindLabel": "not_assessed",
    "unexplainedKeywordDrift": "not_assessed",
}


def _plan(case: dict[str, Any]) -> None:
    plan = case.get("plan")
    if (type(plan) is not dict
            or set(plan) != {"schemaVersion", "catalogVersion", "originalQuestion",
                             "queryMode", "selectedDomainIds", "profileBindings",
                             "settings", "items"}
            or plan["schemaVersion"] != 3
            or plan["catalogVersion"] != "tax-domain-catalog-v2"
            or plan["originalQuestion"] != case["question"]
            or plan["queryMode"] != case["queryMode"]
            or plan["selectedDomainIds"] != case["selectedDomainIds"]
            or type(plan["settings"]) is not dict
            or type(plan["items"]) is not list
            or not _hash(case["planHash"])
            or _sha(canonical_bytes(plan)) != case["planHash"]):
        raise BFreezeError("assessment_invalid")
    settings = plan["settings"]
    if (set(settings) != {"enabledDomainIds", "perPathCandidateLimit",
                         "finalCandidateLimit", "minPartialCandidates",
                         "retrievalTimeoutSeconds", "configVersion"}
            or settings["configVersion"] != "knowledge-minimal-v1"
            or settings["enabledDomainIds"] != ["tax.policy", "tax.law"]
            or type(settings["perPathCandidateLimit"]) is not int
            or not 5 <= settings["perPathCandidateLimit"] <= 20
            or type(settings["finalCandidateLimit"]) is not int
            or not 3 <= settings["finalCandidateLimit"] <= 20
            or type(settings["minPartialCandidates"]) is not int
            or not 3 <= settings["minPartialCandidates"] <= settings["perPathCandidateLimit"]
            or type(settings["retrievalTimeoutSeconds"]) not in (int, float)
            or not 0 < settings["retrievalTimeoutSeconds"] <= 20):
        raise BFreezeError("assessment_invalid")
    bindings = [[domain, {"tax.policy": "tax-policy-v1", "tax.law": "tax-law-v1"}[domain]]
                for domain in case["selectedDomainIds"]]
    items = [{"logicalDomainId": domain, "path": path,
              "queryText": case["question"],
              "candidateLimit": settings["perPathCandidateLimit"],
              "ordinal": index * 2 + offset}
             for index, domain in enumerate(case["selectedDomainIds"])
             for offset, path in enumerate(("keyword", "vector"), start=1)]
    if plan["profileBindings"] != bindings or plan["items"] != items:
        raise BFreezeError("assessment_invalid")


def _profile_snapshot(profile_id: str, index_name: str, index_uuid: str,
                      profile_version: str, mapping_version: str) -> str:
    """Match KnowledgeProfileVerifier.snapshot's five UTF-8 LF-separated fields."""
    return _sha("\n".join((profile_id, index_name, index_uuid,
                          profile_version, mapping_version)).encode("utf-8"))


def _intent(raw: bytes, fixture_raw: bytes) -> dict[str, Any]:
    value = _json_object(raw)
    fixture = _json_object(fixture_raw)
    if (set(value) != _INTENT_KEYS
            or type(value["schemaVersion"]) is not int or value["schemaVersion"] != 2
            or value["kind"] != "knowledge_b_assessment_intent_v2"
            or value["uatFixtureSha256"] != _sha(fixture_raw)
            or type(value["thresholds"]) is not dict
            or set(value["thresholds"]) != set(_THRESHOLDS)
            or any(type(value["thresholds"][key]) is not type(expected)
                   or value["thresholds"][key] != expected
                   for key, expected in _THRESHOLDS.items())
            or type(value["cases"]) is not list or len(value["cases"]) != 10
            or type(fixture.get("cases")) is not list
            or type(fixture.get("sources")) is not list
            or canonical_bytes(value) != raw):
        raise BFreezeError("assessment_invalid")
    source = value["source"]
    source_evidence = value["sourceBuildEvidence"]
    candidate = value["candidate"]
    parameters = value["profileParameters"]
    snapshots = value["baselineProfileSnapshots"]
    if (type(source_evidence) is not dict
            or set(source_evidence) != _SOURCE_BUILD_EVIDENCE_KEYS
            or source_evidence["bindingPath"] != _SOURCE_BUILD_PATHS[0]
            or source_evidence["resultPath"] != _SOURCE_BUILD_PATHS[1]
            or not _hash(source_evidence["bindingSha256"])
            or not _hash(source_evidence["resultSha256"])
            or type(source) is not dict or set(source) != _INTENT_SOURCE_KEYS
            or type(candidate) is not dict or set(candidate) != _INTENT_CANDIDATE_KEYS
            or type(parameters) is not dict
            or set(parameters) != {"tax.policy", "tax.law"}
            or type(snapshots) is not dict
            or set(snapshots) != {"tax.policy", "tax.law"}
            or type(source["indexName"]) is not str or not source["indexName"]
            or type(source["indexUuid"]) is not str or not source["indexUuid"]
            or type(source["recordCount"]) is not int
            or not 1 <= source["recordCount"] <= 20000
            or not _hash(source["mappingSha256"])
            or not _hash(source["sourceFingerprint"])
            or type(candidate["indexName"]) is not str or not candidate["indexName"]
            or candidate["indexName"] == source["indexName"]
            or not _hash(candidate["mappingSha256"])
            or type(candidate["mappingVersion"]) is not str
            or not candidate["mappingVersion"]):
        raise BFreezeError("assessment_invalid")
    for domain, profile_id in (("tax.policy", "tax-policy-v1"),
                               ("tax.law", "tax-law-v1")):
        parameter = parameters[domain]
        if (type(parameter) is not dict or set(parameter) != _PROFILE_PARAMETER_KEYS
                or parameter["profileId"] != profile_id
                or parameter["profileVersion"] != "tax-knowledge-search-v1"
                or parameter["readPolicyVersion"] != "tax-public-authenticated-v1"
                or any(type(parameter[key]) is not str or not parameter[key]
                       for key in ("baselineMappingVersion", "candidateMappingVersion"))
                or parameter["candidateMappingVersion"] != candidate["mappingVersion"]
                or not _hash(parameter["configSha256"])
                or snapshots[domain] != _profile_snapshot(
                    profile_id, source["indexName"], source["indexUuid"],
                    parameter["profileVersion"], parameter["baselineMappingVersion"])):
            raise BFreezeError("assessment_invalid")
    if (parameters["tax.policy"]["baselineMappingVersion"]
            != parameters["tax.law"]["baselineMappingVersion"]):
        raise BFreezeError("assessment_invalid")
    rows, _ = _rows(value["representationBindings"])
    model = value["modelBindings"]
    if (type(model) is not dict or set(model) != _MODEL_BINDING_KEYS
            or not all(_hash(model[key]) for key in (
                "baselineModelSnapshotSha256", "currentModelSnapshotSha256",
                "tokenizerSha256"))
            or model["baselineRepresentationVersion"] != "policy-title-section-body-v1"
            or model["candidateRepresentationVersion"] != "body-only-v2"
            or type(value["builderBudget"]) is not dict
            or value["builderBudget"] != _budget(source["recordCount"], len(rows))
            or type(value["mappingScanBudget"]) is not dict
            or value["mappingScanBudget"] != _scan_budget(source["recordCount"])):
        raise BFreezeError("assessment_invalid")
    comparison = value["comparisonBudget"]
    if (type(comparison) is not dict or set(comparison) != _COMPARISON_BUDGET_KEYS
            or any(type(item) is not int for item in comparison.values())
            or not 1 <= comparison["metadataEsHttp"] <= 512
            or {key: item for key, item in comparison.items()
                if key != "metadataEsHttp"} != {
                "typedSearch": 44, "queryEmbedding": 10, "rerank": 22,
                "aliasWrites": 4,
                "paid": 0, "retry": 0, "resume": 0,
            }):
        raise BFreezeError("assessment_invalid")
    source_by_id: dict[str, dict[str, Any]] = {}
    for source in fixture["sources"]:
        if (type(source) is not dict or type(source.get("id")) is not str
                or source["id"] in source_by_id):
            raise BFreezeError("assessment_invalid")
        source_by_id[source["id"]] = source
    fixture_by_id = {case.get("caseId"): case for case in fixture["cases"]
                     if type(case) is dict and type(case.get("caseId")) is str}
    if len(fixture_by_id) != len(fixture["cases"]):
        raise BFreezeError("assessment_invalid")
    if tuple(case.get("caseId") for case in value["cases"]
             if type(case) is dict) != _B_CASE_IDS:
        raise BFreezeError("assessment_invalid")
    core_ids = fixture.get("thresholds", {}).get("uat", {}).get("coreCases")
    retained_ids = fixture.get("thresholds", {}).get("comparisonB", {}).get("retainedCases")
    if (type(core_ids) is not list or type(retained_ids) is not list
            or retained_ids != list(_B_CASE_IDS)):
        raise BFreezeError("assessment_invalid")
    for case in value["cases"]:
        if (type(case) is not dict
                or set(case) != {"caseId", "queryMode", "question", "selectedDomainIds",
                                 "core", "retained", "necessarySources", "planHash", "plan"}
                or type(case["question"]) is not str or not case["question"].strip()
                or not _hash(case["planHash"])
                or type(case["core"]) is not bool or type(case["retained"]) is not bool
                or case["retained"] is not True):
            raise BFreezeError("assessment_invalid")
        original = fixture_by_id.get(case["caseId"])
        if (type(original) is not dict or original.get("retrievalDenominator") is not True
                or case["question"] != original.get("question")
                or case["queryMode"] != original.get("queryMode")
                or case["selectedDomainIds"] != original.get("expectedDomains")
                or case["core"] != (case["caseId"] in core_ids)
                or type(case["necessarySources"]) is not list
                or not case["necessarySources"]):
            raise BFreezeError("assessment_invalid")
        expected: list[dict[str, str]] = []
        for source_id in original.get("necessarySources", ()):
            source = source_by_id.get(source_id)
            if source is None:
                raise BFreezeError("assessment_invalid")
            expected.append({"documentId": source["documentId"],
                             "chunkId": source["chunkId"],
                             "contentSha256": source["contentSha256"]})
        if case["necessarySources"] != expected:
            raise BFreezeError("assessment_invalid")
        _plan(case)
    return value


def _exact(value: Any, keys: frozenset[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise BFreezeError("input_invalid")
    return value


def _hash(value: Any) -> bool:
    return type(value) is str and _SHA.fullmatch(value) is not None


def _commit(value: Any) -> bool:
    return type(value) is str and _COMMIT.fullmatch(value) is not None


def _check_git(state: GitState, expected_head: str) -> None:
    if (type(state) is not GitState or state.branch != "codex_0915"
            or state.tracked_clean is not True or not _commit(state.head)
            or state.head != expected_head):
        raise BFreezeError("git_state_invalid")


FixtureBlobReader = Callable[[str], bytes]
SourceBuildBlobReader = Callable[[str, str], bytes]


def _git_source_build_blob(frozen_head: str, path: str) -> bytes:
    if not _commit(frozen_head) or path not in _SOURCE_BUILD_PATHS:
        raise BFreezeError("git_state_invalid")
    try:
        result = subprocess.run(
            ["git", "show", f"{frozen_head}:{path}"],
            cwd=_REPOSITORY_ROOT, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, check=False, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise BFreezeError("git_state_invalid") from None
    if result.returncode != 0 or not 0 < len(result.stdout) <= _MAX_JSON:
        raise BFreezeError("git_state_invalid")
    return result.stdout


def _verify_source_build_evidence(
    intent: dict[str, Any], frozen_head: str,
    reader: SourceBuildBlobReader = _git_source_build_blob,
) -> None:
    """Prove the old representation and source identity from frozen Git blobs."""
    evidence = intent["sourceBuildEvidence"]
    try:
        binding_raw = reader(frozen_head, evidence["bindingPath"])
        result_raw = reader(frozen_head, evidence["resultPath"])
    except BFreezeError:
        raise
    except Exception:
        raise BFreezeError("git_state_invalid") from None
    if (type(binding_raw) is not bytes or type(result_raw) is not bytes
            or _sha(binding_raw) != evidence["bindingSha256"]
            or _sha(result_raw) != evidence["resultSha256"]):
        raise BFreezeError("binding_invalid")
    binding = _json_object(binding_raw)
    result = _json_object(result_raw)
    source = intent["source"]
    baseline_model = intent["modelBindings"]["baselineModelSnapshotSha256"]
    built = result.get("result")
    spec = binding.get("spec")
    if (type(spec) is not dict or type(built) is not dict
            or result.get("status") != "built_read_only_unpublished"
            or result.get("bindingSha256") != _sha(binding_raw)
            or result.get("candidate") != source["indexName"]
            or spec.get("candidate_index") != source["indexName"]
            or spec.get("total_count") != source["recordCount"]
            or spec.get("model_snapshot_sha256") != baseline_model
            or _sha(canonical_bytes(binding.get("modelSnapshot"))) != baseline_model
            or built.get("candidate_index") != source["indexName"]
            or built.get("candidate_uuid") != source["indexUuid"]
            or built.get("candidate_fingerprint") != source["sourceFingerprint"]
            or built.get("total_count") != source["recordCount"]
            or built.get("model_snapshot_sha256") != baseline_model
            or built.get("representation_version")
            != intent["modelBindings"]["baselineRepresentationVersion"]
            or any(result.get(key) != 0 for key in
                   ("aliasWrites", "paid", "retry", "resume"))):
        raise BFreezeError("binding_invalid")


def _git_fixture_blob(frozen_head: str) -> bytes:
    """Read the committed UAT fixture, not a caller-supplied path or shell command."""
    if not _commit(frozen_head):
        raise BFreezeError("git_state_invalid")
    try:
        result = subprocess.run(
            ["git", "show", f"{frozen_head}:{_FIXTURE_PATH}"],
            cwd=_REPOSITORY_ROOT, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, check=False, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise BFreezeError("git_state_invalid") from None
    if result.returncode != 0 or not 0 < len(result.stdout) <= _MAX_JSON:
        raise BFreezeError("git_state_invalid")
    return result.stdout


def _verify_fixture_blob(raw: bytes, frozen_head: str,
                         reader: FixtureBlobReader) -> str:
    try:
        committed = reader(frozen_head)
    except BFreezeError:
        raise
    except Exception:
        raise BFreezeError("git_state_invalid") from None
    if type(committed) is not bytes or committed != raw:
        raise BFreezeError("assessment_invalid")
    return _sha(committed)


def _verify_fixture_digest(frozen_head: str, expected_sha256: Any,
                           reader: FixtureBlobReader) -> None:
    try:
        committed = reader(frozen_head)
    except BFreezeError:
        raise
    except Exception:
        raise BFreezeError("git_state_invalid") from None
    if (type(committed) is not bytes or not 0 < len(committed) <= _MAX_JSON
            or not _hash(expected_sha256) or _sha(committed) != expected_sha256):
        raise BFreezeError("assessment_invalid")


def _budget(source_count: int, updates: int) -> dict[str, int]:
    if (type(source_count) is not int or not 1 <= source_count <= 20000
            or type(updates) is not int or not 1 <= updates <= min(2000, source_count)):
        raise BFreezeError("budget_invalid")
    pages = (source_count + 249) // 250
    batches = (updates + 31) // 32
    es_http = 42 + 4 * pages + 3 * batches
    if es_http > 400 or batches > 63:
        raise BFreezeError("budget_invalid")
    return {"esHttp": es_http, "embeddingHttp": batches, "writeOps": updates,
            "paid": 0, "retry": 0, "resume": 0,
            "onlineAliasWrites": 0, "candidates": 1}


def _scan_budget(source_count: int) -> dict[str, int]:
    if type(source_count) is not int or not 1 <= source_count <= 20000:
        raise BFreezeError("budget_invalid")
    per_arm = 1 + (source_count + 249) // 250
    return {"sourceEsHttp": per_arm, "candidateEsHttp": per_arm,
            "retry": 0, "resume": 0}


def _scan_input(request: dict[str, Any]) -> dict[str, Any]:
    return {key: request[key] for key in _SCAN_INPUT_KEYS}


def prepare_b_mapping_scans_v1(
    preliminary_raw: bytes, intent_raw: bytes, uat_fixture_raw: bytes,
    run_directory: Path, *, git_state: GitState,
    fixture_blob_reader: FixtureBlobReader = _git_fixture_blob,
) -> dict[str, Any]:
    """Freeze both future scan ceilings before any ES/BGE operation."""
    preliminary = _exact(_json_object(preliminary_raw), _SCAN_INPUT_KEYS)
    intent = _intent(intent_raw, uat_fixture_raw)
    if (preliminary["schemaVersion"] != 2
            or type(preliminary["runId"]) is not str
            or _RUN.fullmatch(preliminary["runId"]) is None
            or not _commit(preliminary["frozenHead"])
            or preliminary["assessmentIntentSha256"] != _sha(intent_raw)):
        raise BFreezeError("input_invalid")
    _check_git(git_state, preliminary["frozenHead"])
    committed_fixture_sha = _verify_fixture_blob(
        uat_fixture_raw, preliminary["frozenHead"], fixture_blob_reader)
    run_directory = run_directory.resolve()
    if run_directory.exists() or run_directory.name != preliminary["runId"]:
        raise BFreezeError("already_frozen")
    rows, scopes = _rows(preliminary["representationBindings"])
    candidate = _exact(preliminary["candidate"], _SPEC_KEYS)
    source = intent["source"]
    selected = intent["candidate"]
    model = intent["modelBindings"]
    if (source != {
                "indexName": candidate["source_index"],
                "indexUuid": candidate["source_uuid"],
                "mappingSha256": candidate["source_mapping_sha256"],
                "sourceFingerprint": candidate["source_fingerprint"],
                "recordCount": candidate["source_count"],
            }
            or selected != {
                "indexName": candidate["candidate_index"],
                "mappingSha256": candidate["target_mapping_sha256"],
                "mappingVersion": candidate["target_mapping_version"],
            }
            or intent["representationBindings"] != list(rows)
            or model != {
                "baselineModelSnapshotSha256": _sha(canonical_bytes(candidate["baseline_model_snapshot"])),
                "currentModelSnapshotSha256": _sha(canonical_bytes(candidate["model_snapshot"])),
                "tokenizerSha256": candidate["tokenizer_sha256"],
                "baselineRepresentationVersion": candidate["baseline_representation_version"],
                "candidateRepresentationVersion": "body-only-v2",
            }):
        raise BFreezeError("binding_invalid")
    corpus = _json_object(uat_fixture_raw).get("sourceCorpus")
    if (type(corpus) is not dict
            or corpus.get("readAlias") != candidate["read_alias"]
            or corpus.get("index") != candidate["source_index"]
            or corpus.get("indexUuid") != candidate["source_uuid"]
            or corpus.get("recordCount") != candidate["source_count"]
            or corpus.get("mappingSha256") != candidate["source_mapping_sha256"]
            or corpus.get("fullFingerprint") != candidate["source_fingerprint"]):
        raise BFreezeError("binding_invalid")
    budget = _budget(candidate["source_count"], len(rows))
    scan_budget = _scan_budget(candidate["source_count"])
    if (_exact(preliminary["budget"], _BUDGET_KEYS) != budget
            or _exact(preliminary["mappingScanBudget"], _SCAN_BUDGET_KEYS)
            != scan_budget or intent["builderBudget"] != budget
            or intent["mappingScanBudget"] != scan_budget):
        raise BFreezeError("budget_invalid")
    _spec_from_input(candidate, rows, scopes, budget, run_directory,
                     new_build_owner_alias(), datetime.now(UTC).isoformat(),
                     _sha(intent_raw))
    plan = {"schemaVersion": 2, "kind": "knowledge_b_mapping_scan_plan_v2",
            "runId": preliminary["runId"], "frozenHead": preliminary["frozenHead"],
            "branch": git_state.branch, "assessmentIntentSha256": _sha(intent_raw),
            "fixtureGitBlobSha256": committed_fixture_sha,
            "requestCoreSha256": _sha(canonical_bytes(_scan_input(preliminary))),
            "sourceIndex": candidate["source_index"],
            "sourceUuid": candidate["source_uuid"],
            "sourceMappingSha256": candidate["source_mapping_sha256"],
            "sourceFingerprint": candidate["source_fingerprint"],
            "sourceCount": candidate["source_count"],
            "candidateIndex": candidate["candidate_index"],
            "candidateMappingSha256": candidate["target_mapping_sha256"],
            "mappingScanBudget": scan_budget}
    raw = canonical_bytes(plan)
    try:
        run_directory.mkdir(parents=True, exist_ok=False)
        exclusive_write(run_directory / "assessment-intent.json", intent_raw)
        exclusive_write(run_directory / "assessment-intent.sha256",
                        (_sha(intent_raw) + "\n").encode())
        exclusive_write(run_directory / "scan-plan.json", raw)
        exclusive_write(run_directory / "scan-plan.sha256", (_sha(raw) + "\n").encode())
    except (OSError, ValueError, ContractError):
        raise BFreezeError("evidence_io_failed") from None
    return {"status": "scan_plan_frozen_no_calls", "runId": plan["runId"],
            "scanPlanSha256": _sha(raw), "mappingScanBudget": scan_budget}


def _load_scan_plan(run_directory: Path) -> dict[str, Any]:
    try:
        raw = (run_directory / "scan-plan.json").read_bytes()
        digest = (run_directory / "scan-plan.sha256").read_bytes()
        intent_raw = (run_directory / "assessment-intent.json").read_bytes()
        intent_digest = (run_directory / "assessment-intent.sha256").read_bytes()
    except OSError:
        raise BFreezeError("binding_invalid") from None
    if (digest != (_sha(raw) + "\n").encode()
            or intent_digest != (_sha(intent_raw) + "\n").encode()):
        raise BFreezeError("binding_invalid")
    plan = _json_object(raw)
    if (plan.get("schemaVersion") != 2
            or plan.get("kind") != "knowledge_b_mapping_scan_plan_v2"
            or plan.get("runId") != run_directory.name
            or plan.get("branch") != "codex_0915"
            or plan.get("assessmentIntentSha256") != _sha(intent_raw)
            or plan.get("mappingScanBudget") != _scan_budget(plan["sourceCount"])):
        raise BFreezeError("binding_invalid")
    return plan


def _stored_intent_raw(run_directory: Path) -> bytes:
    try:
        return (run_directory / "assessment-intent.json").read_bytes()
    except OSError:
        raise BFreezeError("binding_invalid") from None


def scan_b_mapping_arm_v1(
    run_directory: Path, *, arm: Literal["source", "candidate"],
    git_state: GitState, client: httpx.Client,
    observed_calls: Callable[[], int],
    fixture_blob_reader: FixtureBlobReader = _git_fixture_blob,
) -> dict[str, Any]:
    """Consume one read-only scan arm, append raw local map and finite result."""
    run_directory = run_directory.resolve()
    plan = _load_scan_plan(run_directory)
    intent = _json_object(_stored_intent_raw(run_directory))
    _check_git(git_state, plan["frozenHead"])
    _verify_fixture_digest(plan["frozenHead"], plan.get("fixtureGitBlobSha256"),
                           fixture_blob_reader)
    if arm == "source":
        if (run_directory / "binding.json").exists():
            raise BFreezeError("already_consumed")
        name, uuid, fingerprint, mapping_sha = (
            plan["sourceIndex"], plan["sourceUuid"],
            plan["sourceFingerprint"], plan["sourceMappingSha256"])
    elif arm == "candidate":
        result = _json_object((run_directory / "result.json").read_bytes())
        bound_raw = (run_directory / "binding.json").read_bytes()
        if (result.get("status") != "built_read_only_unpublished"
                or result.get("sourceVerifiedByBuilder") is not True
                or result.get("assessmentIntentSha256") != plan["assessmentIntentSha256"]
                or result.get("candidateIndex") != plan["candidateIndex"]
                or result.get("candidateCount") != plan["sourceCount"]
                or result.get("bindingSha256") != _sha(bound_raw)):
            raise BFreezeError("binding_invalid")
        name, uuid, fingerprint, mapping_sha = (
            result["candidateIndex"], result["candidateUuid"],
            result["candidateFingerprint"], plan["candidateMappingSha256"])
    else:
        raise BFreezeError("input_invalid")
    attempt_path = run_directory / f"{arm}-mapping-scan-attempt.json"
    result_path = run_directory / f"{arm}-mapping-scan-result.json"
    map_path = run_directory / f"{arm}-id-mapping.json"
    if attempt_path.exists() or result_path.exists() or map_path.exists():
        raise BFreezeError("already_consumed")
    spec = MappingScanSpec(name, uuid, mapping_sha, fingerprint,
                           plan["sourceCount"],
                           plan["mappingScanBudget"][f"{arm}EsHttp"])
    try:
        exclusive_write(attempt_path, canonical_bytes({
            "schemaVersion": 2, "status": "consumed", "arm": arm,
            "assessmentIntentSha256": plan["assessmentIntentSha256"],
            "scanPlanSha256": _sha((run_directory / "scan-plan.json").read_bytes()),
            "startedAt": datetime.now(UTC).isoformat(), "retry": 0, "resume": 0,
        }))
    except (OSError, ValueError, ContractError):
        raise BFreezeError("evidence_io_failed") from None
    terminal: dict[str, Any] = {"schemaVersion": 2, "arm": arm,
                                "assessmentIntentSha256": plan["assessmentIntentSha256"],
                                "status": "failed", "reason": "scan_driver_failed",
                                "indexName": name, "indexUuid": uuid,
                                "retry": 0, "resume": 0,
                                "maxEsHttp": spec.max_http_requests}
    try:
        scan = scan_id_mapping_v1(spec, client=client)
        expected_mapping_version = (
            intent["profileParameters"]["tax.policy"]["baselineMappingVersion"]
            if arm == "source" else intent["candidate"]["mappingVersion"])
        if scan.mapping_version != expected_mapping_version:
            raise BFreezeError("binding_invalid")
        actual_calls = observed_calls()
        if type(actual_calls) is not int or actual_calls != scan.http_requests:
            raise BFreezeError("budget_invalid")
        if arm == "candidate":
            source_raw = (run_directory / "source-id-mapping.json").read_bytes()
            _, _, source_ids = _id_mapping(
                source_raw, source_index=plan["sourceIndex"],
                source_uuid=plan["sourceUuid"],
                source_fingerprint=plan["sourceFingerprint"],
                source_count=plan["sourceCount"])
            _, _, candidate_ids = _id_mapping(
                scan.raw, source_index=name, source_uuid=uuid,
                source_fingerprint=fingerprint, source_count=plan["sourceCount"])
            if candidate_ids != source_ids:
                raise BFreezeError("binding_invalid")
        exclusive_write(map_path, scan.raw)
        terminal.update(status="scanned_read_only", reason=None,
                        sha256=scan.sha256, recordCount=scan.record_count,
                        esHttp=scan.http_requests, sourceFingerprint=fingerprint,
                        mappingVersion=scan.mapping_version)
    except Exception as error:
        terminal["reason"] = (error.reason if isinstance(error, BIdMappingError)
                              else "mapping_identity_confounded" if arm == "candidate"
                              else "scan_driver_failed")
    try:
        actual_calls = observed_calls()
        if type(actual_calls) is not int or not 0 <= actual_calls <= spec.max_http_requests:
            terminal.update(status="failed", reason="scan_budget_observation_invalid",
                            esHttp=-1)
        else:
            terminal["esHttp"] = actual_calls
    except Exception:
        terminal.update(status="failed", reason="scan_budget_observation_invalid",
                        esHttp=-1)
    terminal["finishedAt"] = datetime.now(UTC).isoformat()
    try:
        exclusive_write(result_path, canonical_bytes(terminal))
    except (OSError, ValueError, ContractError):
        raise BFreezeError("evidence_io_failed") from None
    return terminal


def _rows(value: Any) -> tuple[tuple[dict[str, str], ...], tuple[RepresentationScopeV1, ...]]:
    if type(value) is not list or not 1 <= len(value) <= 2000:
        raise BFreezeError("input_invalid")
    rows: list[dict[str, str]] = []
    scopes: list[RepresentationScopeV1] = []
    seen: set[str] = set()
    for item in value:
        row = _exact(item, _ROW_KEYS)
        if (any(type(field) is not str for field in row.values())
                or row["version"] != "body-only-v2"
                or not all(_hash(row[key]) for key in (
                    "asset_version", "input_sha256", "body_sha256"))
                or not all(0 < len(row[key]) <= 256 and row[key].strip() for key in (
                    "identifier", "document_id", "parent_document_id", "asset_id"))
                or row["identifier"] in seen):
            raise BFreezeError("input_invalid")
        seen.add(row["identifier"])
        rows.append(row)
        scopes.append(RepresentationScopeV1(
            row["identifier"], row["document_id"], row["parent_document_id"],
            row["asset_id"], row["asset_version"],
        ))
    return tuple(rows), tuple(scopes)


def _spec_from_input(
    candidate: Any, rows: tuple[dict[str, str], ...],
    scopes: tuple[RepresentationScopeV1, ...], budget: dict[str, int],
    run_directory: Path, owner_alias: str, indexed_at: str,
    assessment_intent_sha256: str,
) -> CandidateSpec:
    fields = _exact(candidate, _SPEC_KEYS)
    if (type(fields["baseline_model_snapshot"]) is not dict
            or type(fields["model_snapshot"]) is not dict):
        raise BFreezeError("input_invalid")
    binding = [[row["identifier"], row["version"], row["input_sha256"],
                row["body_sha256"]] for row in rows]
    values = {key: value for key, value in fields.items()
              if key not in {"baseline_model_snapshot", "model_snapshot"}}
    try:
        return CandidateSpec(
            mode="representation", **values,
            workspace=run_directory, owner_alias=owner_alias,
            baseline_model_snapshot=canonical_bytes(fields["baseline_model_snapshot"]),
            model_snapshot=canonical_bytes(fields["model_snapshot"]),
            baseline_model_snapshot_sha256=_sha(canonical_bytes(fields["baseline_model_snapshot"])),
            model_snapshot_sha256=_sha(canonical_bytes(fields["model_snapshot"])),
            indexed_at=indexed_at, max_http_requests=budget["esHttp"],
            max_embedding_requests=budget["embeddingHttp"],
            max_write_ops=budget["writeOps"],
            changes=(), update_ids=tuple(row["identifier"] for row in rows),
            representation_scope=scopes,
            representation_binding_sha256=_sha(canonical_bytes(binding)),
            representation_version="body-only-v2",
            assessment_intent_sha256=assessment_intent_sha256,
        )
    except (RechunkCandidateError, TypeError, ValueError):
        raise BFreezeError("input_invalid") from None


def _spec_dict(spec: CandidateSpec) -> dict[str, Any]:
    value = asdict(spec)
    value["workspace"] = str(spec.workspace)
    value["baseline_model_snapshot"] = _json_object(spec.baseline_model_snapshot)
    value["model_snapshot"] = _json_object(spec.model_snapshot)
    return _json_object(canonical_bytes(value))


def _spec_from_binding(value: Any) -> CandidateSpec:
    if type(value) is not dict or set(value) != set(CandidateSpec.__dataclass_fields__):
        raise BFreezeError("binding_invalid")
    fields = dict(value)
    try:
        fields["workspace"] = Path(fields["workspace"])
        fields["baseline_model_snapshot"] = canonical_bytes(fields["baseline_model_snapshot"])
        fields["model_snapshot"] = canonical_bytes(fields["model_snapshot"])
        fields["changes"] = ()
        fields["update_ids"] = tuple(fields["update_ids"])
        fields["representation_scope"] = tuple(
            RepresentationScopeV1(**scope) for scope in fields["representation_scope"])
        spec = CandidateSpec(**fields)
    except (KeyError, RechunkCandidateError, TypeError, ValueError):
        raise BFreezeError("binding_invalid") from None
    if spec.mode != "representation" or value != _spec_dict(spec):
        raise BFreezeError("binding_invalid")
    return spec


def _candidate_input_from_spec(spec: CandidateSpec) -> dict[str, Any]:
    value = _spec_dict(spec)
    return {key: value[key] for key in _SPEC_KEYS}


def freeze_b_candidate_v1(
    request_raw: bytes, intent_raw: bytes, uat_fixture_raw: bytes,
    id_mapping_raw: bytes,
    run_directory: Path, *,
    git_state: GitState,
    owner_alias_factory: Callable[[], str] = new_build_owner_alias,
    fixture_blob_reader: FixtureBlobReader = _git_fixture_blob,
) -> dict[str, Any]:
    """Write one immutable, unconsumed binding; no network or model access."""
    request = _exact(_json_object(request_raw), _INPUT_KEYS)
    intent = _intent(intent_raw, uat_fixture_raw)
    if (type(request["schemaVersion"]) is not int or request["schemaVersion"] != 2
            or type(request["runId"]) is not str
            or _RUN.fullmatch(request["runId"]) is None
            or type(request["frozenHead"]) is not str
            or not _commit(request["frozenHead"])
            or not _hash(request["assessmentIntentSha256"])
            or not _hash(request["idMappingSha256"])
            or request["assessmentIntentSha256"] != _sha(intent_raw)):
        raise BFreezeError("assessment_invalid")
    _check_git(git_state, request["frozenHead"])
    committed_fixture_sha = _verify_fixture_blob(
        uat_fixture_raw, request["frozenHead"], fixture_blob_reader)
    run_directory = run_directory.resolve()
    if run_directory.name != request["runId"]:
        raise BFreezeError("binding_invalid")
    plan = _load_scan_plan(run_directory)
    if (plan["requestCoreSha256"] != _sha(canonical_bytes(_scan_input(request)))
            or plan["assessmentIntentSha256"] != _sha(intent_raw)
            or _stored_intent_raw(run_directory) != intent_raw
            or plan["frozenHead"] != request["frozenHead"]
            or plan["fixtureGitBlobSha256"] != committed_fixture_sha):
        raise BFreezeError("binding_invalid")
    try:
        scan_result_raw = (run_directory / "source-mapping-scan-result.json").read_bytes()
        scan_result = _json_object(scan_result_raw)
        scanned_raw = (run_directory / "source-id-mapping.json").read_bytes()
    except OSError:
        raise BFreezeError("binding_invalid") from None
    if (scan_result.get("status") != "scanned_read_only"
            or scan_result.get("sha256") != _sha(id_mapping_raw)
            or scan_result.get("recordCount") != plan["sourceCount"]
            or scan_result.get("sourceFingerprint") != plan["sourceFingerprint"]
            or scan_result.get("esHttp") != plan["mappingScanBudget"]["sourceEsHttp"]
            or scanned_raw != id_mapping_raw):
        raise BFreezeError("binding_invalid")
    if (run_directory / "binding.json").exists():
        raise BFreezeError("already_frozen")
    rows, scopes = _rows(request["representationBindings"])
    candidate = _exact(request["candidate"], _SPEC_KEYS)
    if (intent["representationBindings"] != list(rows)
            or intent["source"] != {
                "indexName": candidate["source_index"],
                "indexUuid": candidate["source_uuid"],
                "mappingSha256": candidate["source_mapping_sha256"],
                "sourceFingerprint": candidate["source_fingerprint"],
                "recordCount": candidate["source_count"],
            }
            or intent["candidate"] != {
                "indexName": candidate["candidate_index"],
                "mappingSha256": candidate["target_mapping_sha256"],
                "mappingVersion": candidate["target_mapping_version"],
            }):
        raise BFreezeError("binding_invalid")
    budget = _budget(candidate["source_count"], len(rows))
    supplied = _exact(request["budget"], _BUDGET_KEYS)
    if (any(type(value) is not int for value in supplied.values())
            or supplied != budget or intent["builderBudget"] != budget):
        raise BFreezeError("budget_invalid")
    scan_budget = _scan_budget(candidate["source_count"])
    if (_exact(request["mappingScanBudget"], _SCAN_BUDGET_KEYS) != scan_budget
            or plan["mappingScanBudget"] != scan_budget
            or intent["mappingScanBudget"] != scan_budget):
        raise BFreezeError("budget_invalid")
    spec = _spec_from_input(
        candidate, rows, scopes, budget, run_directory, owner_alias_factory(),
        datetime.now(UTC).isoformat(), _sha(intent_raw),
    )
    mapping_sha, mapping_fingerprint, _ = _id_mapping(
        id_mapping_raw, source_index=spec.source_index,
        source_uuid=spec.source_uuid, source_fingerprint=spec.source_fingerprint,
        source_count=spec.source_count)
    if mapping_sha != request["idMappingSha256"]:
        raise BFreezeError("binding_invalid")
    binding: dict[str, Any] = {
        "schemaVersion": 2, "kind": "knowledge_b_representation_candidate_v2",
        "runId": request["runId"], "frozenHead": request["frozenHead"],
        "branch": git_state.branch, "assessmentIntentSha256": request["assessmentIntentSha256"],
        "idMappingSha256": mapping_sha,
        "idMappingSourceFingerprint": mapping_fingerprint,
        "freezeInputSha256": _sha(request_raw),
        "scanPlanSha256": _sha((run_directory / "scan-plan.json").read_bytes()),
        "sourceMapScanResultSha256": _sha(scan_result_raw),
        "sourceVerification": "pending_builder_live_preflight",
        "spec": _spec_dict(spec), "representationBindings": list(rows),
        "budget": budget, "mappingScanBudget": scan_budget,
    }
    raw = canonical_bytes(binding)
    try:
        exclusive_write(run_directory / "binding.json", raw)
        exclusive_write(run_directory / "binding.sha256", (_sha(raw) + "\n").encode())
    except (OSError, ValueError, ContractError):
        raise BFreezeError("evidence_io_failed") from None
    return {"status": "frozen_not_executed", "runId": request["runId"],
            "bindingSha256": _sha(raw), "budget": budget,
            "sourceVerification": "pending_builder_live_preflight"}


def _load_binding(
    run_directory: Path, intent_raw: bytes, uat_fixture_raw: bytes,
    id_mapping_raw: bytes,
) -> tuple[dict[str, Any], CandidateSpec, str]:
    try:
        raw = (run_directory / "binding.json").read_bytes()
        digest = (run_directory / "binding.sha256").read_bytes()
    except OSError:
        raise BFreezeError("binding_invalid") from None
    if digest != (_sha(raw) + "\n").encode():
        raise BFreezeError("binding_invalid")
    binding = _exact(_json_object(raw), _BINDING_KEYS)
    if (type(binding["schemaVersion"]) is not int or binding["schemaVersion"] != 2
            or binding["kind"] != "knowledge_b_representation_candidate_v2"
            or binding["sourceVerification"] != "pending_builder_live_preflight"
            or binding["branch"] != "codex_0915"
            or binding["runId"] != run_directory.name
            or not _hash(binding["freezeInputSha256"])
            or not _hash(binding["assessmentIntentSha256"])
            or _sha(intent_raw) != binding["assessmentIntentSha256"]):
        raise BFreezeError("binding_invalid")
    plan = _load_scan_plan(run_directory)
    try:
        source_scan_raw = (run_directory / "source-mapping-scan-result.json").read_bytes()
        source_map_raw = (run_directory / "source-id-mapping.json").read_bytes()
    except OSError:
        raise BFreezeError("binding_invalid") from None
    source_scan = _json_object(source_scan_raw)
    if (binding["scanPlanSha256"] != _sha((run_directory / "scan-plan.json").read_bytes())
            or binding["sourceMapScanResultSha256"] != _sha(source_scan_raw)
            or source_scan.get("status") != "scanned_read_only"
            or source_scan.get("sha256") != binding["idMappingSha256"]
            or source_scan.get("recordCount") != plan["sourceCount"]
            or source_scan.get("sourceFingerprint") != plan["sourceFingerprint"]
            or source_scan.get("esHttp") != plan["mappingScanBudget"]["sourceEsHttp"]
            or source_map_raw != id_mapping_raw
            or plan["sourceFingerprint"] != binding["idMappingSourceFingerprint"]):
        raise BFreezeError("binding_invalid")
    intent = _intent(intent_raw, uat_fixture_raw)
    spec = _spec_from_binding(binding["spec"])
    mapping_sha, mapping_fingerprint, _ = _id_mapping(
        id_mapping_raw, source_index=spec.source_index,
        source_uuid=spec.source_uuid, source_fingerprint=spec.source_fingerprint,
        source_count=spec.source_count)
    if (mapping_sha != binding["idMappingSha256"]
            or mapping_fingerprint != binding["idMappingSourceFingerprint"]):
        raise BFreezeError("binding_invalid")
    rows, scopes = _rows(binding["representationBindings"])
    budget = _budget(spec.source_count, len(rows))
    scan_budget = _scan_budget(spec.source_count)
    candidate = _candidate_input_from_spec(spec)
    request_core: dict[str, Any] = {
        "schemaVersion": 2,
        "runId": binding["runId"],
        "frozenHead": binding["frozenHead"],
        "assessmentIntentSha256": binding["assessmentIntentSha256"],
        "candidate": candidate,
        "representationBindings": list(rows),
        "budget": budget,
        "mappingScanBudget": scan_budget,
    }
    freeze_request = dict(request_core)
    freeze_request["idMappingSha256"] = binding["idMappingSha256"]
    expected_spec = _spec_from_input(
        candidate, rows, scopes, budget, run_directory,
        spec.owner_alias, spec.indexed_at, _sha(intent_raw),
    )
    if (binding["budget"] != budget or spec.max_http_requests != budget["esHttp"]
            or binding["mappingScanBudget"] != scan_budget
            or spec.max_embedding_requests != budget["embeddingHttp"]
            or spec.max_write_ops != budget["writeOps"]
            or spec.workspace != run_directory.resolve()
            or spec.assessment_intent_sha256 != _sha(intent_raw)
            or _spec_dict(spec) != _spec_dict(expected_spec)
            or plan["assessmentIntentSha256"] != _sha(intent_raw)
            or plan["requestCoreSha256"] != _sha(canonical_bytes(request_core))
            or plan["sourceIndex"] != spec.source_index
            or plan["sourceUuid"] != spec.source_uuid
            or plan["sourceMappingSha256"] != spec.source_mapping_sha256
            or plan["sourceFingerprint"] != spec.source_fingerprint
            or plan["sourceCount"] != spec.source_count
            or plan["candidateIndex"] != spec.candidate_index
            or plan["candidateMappingSha256"] != spec.target_mapping_sha256
            or binding["freezeInputSha256"] != _sha(canonical_bytes(freeze_request))
            or intent["builderBudget"] != budget
            or intent["mappingScanBudget"] != scan_budget
            or intent["source"] != {
                "indexName": spec.source_index,
                "indexUuid": spec.source_uuid,
                "mappingSha256": spec.source_mapping_sha256,
                "sourceFingerprint": spec.source_fingerprint,
                "recordCount": spec.source_count,
            }
            or intent["candidate"] != {
                "indexName": spec.candidate_index,
                "mappingSha256": spec.target_mapping_sha256,
                "mappingVersion": spec.target_mapping_version,
            }
            or intent["representationBindings"] != list(rows)
            or intent["modelBindings"] != {
                "baselineModelSnapshotSha256": spec.baseline_model_snapshot_sha256,
                "currentModelSnapshotSha256": spec.model_snapshot_sha256,
                "tokenizerSha256": spec.tokenizer_sha256,
                "baselineRepresentationVersion": spec.baseline_representation_version,
                "candidateRepresentationVersion": "body-only-v2",
            }
            or spec.update_ids != tuple(row["identifier"] for row in rows)
            or spec.representation_scope != scopes
            or spec.representation_binding_sha256 != _sha(canonical_bytes([
                [row["identifier"], row["version"], row["input_sha256"],
                 row["body_sha256"]] for row in rows]))):
        raise BFreezeError("binding_invalid")
    return binding, spec, _sha(raw)


ClientFactory = Callable[[CandidateSpec], AbstractContextManager[httpx.Client]]
PreparationFactory = Callable[[CandidateSpec], PrepareVectors]
ObservedCounts = Callable[[], tuple[int, int]]


def execute_b_candidate_v1(
    run_directory: Path, intent_raw: bytes, uat_fixture_raw: bytes,
    id_mapping_raw: bytes, *, git_state: GitState,
    client_factory: ClientFactory, preparation_factory: PreparationFactory,
    observed_counts: ObservedCounts, execution_kind: Literal["fake", "local"],
    fixture_blob_reader: FixtureBlobReader = _git_fixture_blob,
    source_build_blob_reader: SourceBuildBlobReader = _git_source_build_blob,
) -> dict[str, Any]:
    """Consume once before any ES/BGE action; builder owns candidate sealing."""
    run_directory = run_directory.resolve()
    binding, spec, binding_sha = _load_binding(
        run_directory, intent_raw, uat_fixture_raw, id_mapping_raw)
    _check_git(git_state, binding["frozenHead"])
    if (_verify_fixture_blob(uat_fixture_raw, binding["frozenHead"], fixture_blob_reader)
            != _load_scan_plan(run_directory)["fixtureGitBlobSha256"]):
        raise BFreezeError("binding_invalid")
    if execution_kind == "local":
        _verify_source_build_evidence(
            _intent(intent_raw, uat_fixture_raw), binding["frozenHead"],
            source_build_blob_reader,
        )
    if (execution_kind not in ("fake", "local")
            or (run_directory / "attempt.json").exists()
            or (run_directory / "result.json").exists()):
        raise BFreezeError("already_consumed")
    started = datetime.now(UTC).isoformat()
    attempt = {"schemaVersion": 2, "status": "consumed", "runId": binding["runId"],
               "assessmentIntentSha256": binding["assessmentIntentSha256"],
               "bindingSha256": binding_sha, "startedAt": started,
               "executionKind": execution_kind, "retry": 0, "resume": 0}
    try:
        exclusive_write(run_directory / "attempt.json", canonical_bytes(attempt))
    except (OSError, ValueError, ContractError):
        raise BFreezeError("evidence_io_failed") from None
    terminal: dict[str, Any] = {
        "schemaVersion": 2, "runId": binding["runId"],
        "assessmentIntentSha256": binding["assessmentIntentSha256"],
        "bindingSha256": binding_sha, "executionKind": execution_kind,
        "status": "failed", "reason": "driver_failed", "phase": "preflight",
        "sealStatus": "not_needed", "candidateIndex": spec.candidate_index,
        "sourceVerifiedByBuilder": False,
    }
    build_result_http: int | None = None
    build_result_embedding: int | None = None
    try:
        with client_factory(spec) as client:
            prepared = preparation_factory(spec)
            result = build_rechunk_candidate_v1(
                spec, client=client, prepare_vectors=prepared,
            )
        terminal.update(status="built_read_only_unpublished", reason=None,
                        phase="verify", sealStatus="not_needed",
                        sourceVerifiedByBuilder=True,
                        candidateMapping="pending_postbuild_readonly_scan",
                        candidateUuid=result.candidate_uuid,
                        candidateFingerprint=result.candidate_fingerprint,
                        candidateCount=result.candidate_count,
                        updatedCount=result.updated_count)
        build_result_http = result.http_requests
        build_result_embedding = result.embedding_requests
    except RechunkCandidateError as error:
        terminal.update(reason=error.reason, phase=error.phase,
                        sealStatus=error.seal_status)
    except BaseException as error:
        note = next((item for item in getattr(error, "__notes__", ())
                     if item in {"candidate_cleanup:not_needed", "candidate_cleanup:sealed",
                                 "candidate_cleanup:candidate_seal_failed",
                                 "candidate_cleanup:ownership_unknown"}), None)
        terminal.update(reason="cancelled" if isinstance(error, KeyboardInterrupt)
                        else "driver_failed",
                        sealStatus=note.split(":", 1)[1] if note else "unknown")
    try:
        es_http, embedding_http = observed_counts()
        budget = binding["budget"]
        if (type(es_http) is not int or type(embedding_http) is not int
                or es_http < 0 or embedding_http < 0
                or es_http > budget["esHttp"] or embedding_http > budget["embeddingHttp"]
                or (build_result_http is not None and es_http != build_result_http)
                or (build_result_embedding is not None
                    and embedding_http != build_result_embedding)):
            terminal.update(status="failed", reason="budget_observation_invalid",
                            sealStatus="unknown")
            es_http, embedding_http = -1, -1
    except Exception:
        terminal.update(status="failed", reason="budget_observation_invalid",
                        sealStatus="unknown")
        es_http, embedding_http = -1, -1
    terminal.update(esHttp=es_http, embeddingHttp=embedding_http,
                    paid=0, retry=0, resume=0, onlineAliasWrites=0,
                    finishedAt=datetime.now(UTC).isoformat())
    try:
        exclusive_write(run_directory / "result.json", canonical_bytes(terminal))
    except (OSError, ValueError, ContractError):
        raise BFreezeError("evidence_io_failed") from None
    return terminal


def finalize_b_assessment_v2(
    run_directory: Path, intent_raw: bytes, uat_fixture_raw: bytes, *,
    git_state: GitState,
    fixture_blob_reader: FixtureBlobReader = _git_fixture_blob,
) -> dict[str, Any]:
    """Append the post-build assessment only after both full read-only scans."""
    run_directory = run_directory.resolve()
    plan = _load_scan_plan(run_directory)
    _check_git(git_state, plan["frozenHead"])
    intent = _intent(intent_raw, uat_fixture_raw)
    if ((run_directory / "assessment-final.json").exists()
            or (run_directory / "assessment-final.sha256").exists()):
        raise BFreezeError("already_frozen")
    if (plan["assessmentIntentSha256"] != _sha(intent_raw)
            or _stored_intent_raw(run_directory) != intent_raw
            or _verify_fixture_blob(uat_fixture_raw, plan["frozenHead"],
                                    fixture_blob_reader) != plan["fixtureGitBlobSha256"]):
        raise BFreezeError("binding_invalid")
    try:
        source_map_raw = (run_directory / "source-id-mapping.json").read_bytes()
        candidate_map_raw = (run_directory / "candidate-id-mapping.json").read_bytes()
        source_scan_raw = (run_directory / "source-mapping-scan-result.json").read_bytes()
        candidate_scan_raw = (run_directory / "candidate-mapping-scan-result.json").read_bytes()
        binding_raw = (run_directory / "binding.json").read_bytes()
        attempt_raw = (run_directory / "attempt.json").read_bytes()
        result_raw = (run_directory / "result.json").read_bytes()
    except OSError:
        raise BFreezeError("binding_invalid") from None
    binding, spec, binding_sha = _load_binding(
        run_directory, intent_raw, uat_fixture_raw, source_map_raw)
    if binding_sha != _sha(binding_raw):
        raise BFreezeError("binding_invalid")
    result = _json_object(result_raw)
    attempt = _json_object(attempt_raw)
    source_scan = _json_object(source_scan_raw)
    candidate_scan = _json_object(candidate_scan_raw)
    if (canonical_bytes(result) != result_raw
            or canonical_bytes(attempt) != attempt_raw
            or canonical_bytes(source_scan) != source_scan_raw
            or canonical_bytes(candidate_scan) != candidate_scan_raw
            or attempt.get("schemaVersion") != 2
            or attempt.get("status") != "consumed"
            or attempt.get("runId") != binding["runId"]
            or attempt.get("bindingSha256") != binding_sha
            or attempt.get("assessmentIntentSha256") != _sha(intent_raw)
            or attempt.get("executionKind") != result.get("executionKind")
            or result.get("schemaVersion") != 2
            or result.get("status") != "built_read_only_unpublished"
            or result.get("runId") != binding["runId"]
            or result.get("executionKind") not in ("fake", "local")
            or result.get("sourceVerifiedByBuilder") is not True
            or result.get("candidateMapping") != "pending_postbuild_readonly_scan"
            or result.get("bindingSha256") != binding_sha
            or result.get("assessmentIntentSha256") != _sha(intent_raw)
            or result.get("candidateIndex") != spec.candidate_index
            or not _hash(result.get("candidateFingerprint"))
            or result.get("candidateCount") != spec.source_count
            or result.get("paid") != 0 or result.get("retry") != 0
            or result.get("resume") != 0 or result.get("onlineAliasWrites") != 0
            or type(result.get("esHttp")) is not int
            or not 1 <= result["esHttp"] <= binding["budget"]["esHttp"]
            or type(result.get("embeddingHttp")) is not int
            or result["embeddingHttp"] != binding["budget"]["embeddingHttp"]
            or result.get("updatedCount") != len(binding["representationBindings"])
            or source_scan.get("schemaVersion") != 2
            or source_scan.get("arm") != "source"
            or source_scan.get("status") != "scanned_read_only"
            or source_scan.get("reason") is not None
            or source_scan.get("assessmentIntentSha256") != _sha(intent_raw)
            or source_scan.get("sha256") != _sha(source_map_raw)
            or source_scan.get("indexName") != intent["source"]["indexName"]
            or source_scan.get("indexUuid") != intent["source"]["indexUuid"]
            or source_scan.get("mappingVersion") != intent["profileParameters"]["tax.policy"]["baselineMappingVersion"]
            or source_scan.get("recordCount") != intent["source"]["recordCount"]
            or source_scan.get("esHttp") != plan["mappingScanBudget"]["sourceEsHttp"]
            or candidate_scan.get("schemaVersion") != 2
            or candidate_scan.get("arm") != "candidate"
            or candidate_scan.get("status") != "scanned_read_only"
            or candidate_scan.get("reason") is not None
            or candidate_scan.get("assessmentIntentSha256") != _sha(intent_raw)
            or candidate_scan.get("sha256") != _sha(candidate_map_raw)
            or candidate_scan.get("indexName") != spec.candidate_index
            or candidate_scan.get("indexUuid") != result.get("candidateUuid")
            or candidate_scan.get("mappingVersion") != spec.target_mapping_version
            or candidate_scan.get("sourceFingerprint") != result.get("candidateFingerprint")
            or candidate_scan.get("recordCount") != result.get("candidateCount")
            or candidate_scan.get("esHttp") != plan["mappingScanBudget"]["candidateEsHttp"]):
        raise BFreezeError("binding_invalid")
    source_identity = intent["source"]
    source_sha, _, source_records = _id_mapping(
        source_map_raw, source_index=source_identity["indexName"],
        source_uuid=source_identity["indexUuid"],
        source_fingerprint=source_identity["sourceFingerprint"],
        source_count=source_identity["recordCount"])
    candidate_uuid = result.get("candidateUuid")
    if (type(candidate_uuid) is not str or not candidate_uuid
            or candidate_uuid == source_identity["indexUuid"]):
        raise BFreezeError("binding_invalid")
    candidate_sha, _, candidate_records = _id_mapping(
        candidate_map_raw, source_index=spec.candidate_index,
        source_uuid=candidate_uuid,
        source_fingerprint=result["candidateFingerprint"],
        source_count=spec.source_count)
    if (source_records != candidate_records
            or source_sha != binding["idMappingSha256"]
            or source_scan.get("sourceFingerprint") != source_identity["sourceFingerprint"]):
        raise BFreezeError("binding_invalid")
    candidate_snapshots = {
        domain: _profile_snapshot(
            parameter["profileId"], spec.candidate_index, candidate_uuid,
            parameter["profileVersion"], parameter["candidateMappingVersion"])
        for domain, parameter in intent["profileParameters"].items()
    }
    if any(candidate_snapshots[domain] == intent["baselineProfileSnapshots"][domain]
           for domain in candidate_snapshots):
        raise BFreezeError("binding_invalid")
    final = {
        "schemaVersion": 2, "kind": "knowledge_b_retrieval_assessment_v2",
        "assessmentIntentSha256": _sha(intent_raw),
        "bindingSha256": binding_sha,
        "builderResultSha256": _sha(result_raw),
        "sourceMapScanResultSha256": _sha(source_scan_raw),
        "candidateMapScanResultSha256": _sha(candidate_scan_raw),
        "sourceIdMappingSha256": source_sha,
        "candidateIdMappingSha256": candidate_sha,
        "candidateIdentity": {
            "indexName": spec.candidate_index, "indexUuid": candidate_uuid,
            "mappingSha256": spec.target_mapping_sha256,
            "sourceFingerprint": result["candidateFingerprint"],
            "recordCount": spec.source_count,
        },
        "candidateProfileSnapshots": candidate_snapshots,
    }
    if set(final) != _FINAL_KEYS:
        raise BFreezeError("binding_invalid")
    raw = canonical_bytes(final)
    try:
        exclusive_write(run_directory / "assessment-final.json", raw)
        exclusive_write(run_directory / "assessment-final.sha256",
                        (_sha(raw) + "\n").encode())
    except (OSError, ValueError, ContractError):
        raise BFreezeError("evidence_io_failed") from None
    return {"status": "assessment_frozen", "assessmentSha256": _sha(raw),
            "assessmentIntentSha256": _sha(intent_raw),
            "candidateIndex": spec.candidate_index,
            "candidateUuid": candidate_uuid,
            "candidateProfileSnapshots": candidate_snapshots}
