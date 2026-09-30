"""Comparison-only v2 binding for the already-built, read-only B candidate.

The old builder evidence is read from one immutable Git commit.  This module
never creates a builder result, writes ES, or treats the failed old comparison
as quality evidence.  The caller owns append-only persistence and the bounded
physical ES scanner; this module verifies their small, canonical receipts.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Mapping, cast

from agent_runtime.knowledge.contracts import RetrievalPath, RetrievalPlanItem
from agent_runtime.knowledge.intent_contracts import KnowledgeQueryMode
from agent_runtime.knowledge.minimal_plan import (
    MinimalKnowledgeRetrievalPlan, MinimalRetrievalSettings,
)
from tests.evaluation.knowledge.rebuild_b_comparator import (
    ArmEndpoint, CallTotals, ComparisonRunError, ComparisonSpec, FrozenIdMapping,
    LocalRuntimeAdmission, _canonical_bytes, _sha256, _sidecar,
    _verify_frozen_request_hashes, _verify_representation_binding,
    comparison_spec_fingerprint, plan_fingerprint,
)

ROOT = Path(__file__).resolve().parents[4]
OLD_COMMIT = "c9b8642e9c20765814df4b3422cfa958a2c4900c"
OLD_DIRECTORY = "knowledge-corpus-tools/evidence/knowledge-b-body-20260930-01"
OLD_RUN_ID = "knowledge-b-body-20260930-01"
FIXTURE_PATH = "agent-runtime/tests/uat/knowledge_rebuild_measure.v1.json"
CONFIG_PATH = "es-query-service/src/main/resources/application-knowledge-live.yml"
OLD_FILES = (
    "assessment-intent.json", "assessment-final.json", "scan-plan.json",
    "binding.json", "attempt.json", "result.json",
    "source-mapping-scan-result.json", "candidate-mapping-scan-result.json",
    "source-id-mapping.json", "candidate-id-mapping.json",
)
REUSE_SIDECARS = frozenset({
    "reuseIntent", "reuseFinal", "reuseAttempt", "reuseTerminal",
    "sourceScanResult", "candidateScanResult",
})
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_HEAD = re.compile(r"[0-9a-f]{40}\Z")
_RUN = re.compile(r"[a-z0-9][a-z0-9-]{4,95}\Z")
_ZERO_BUILD = {"candidates": 0, "esHttp": 0, "embeddingHttp": 0,
               "writeOps": 0, "onlineAliasWrites": 0, "paid": 0,
               "retry": 0, "resume": 0}
_COMPARISON = {"typedSearch": 44, "queryEmbedding": 10, "rerank": 22,
               "aliasWrites": 4, "metadataEsHttp": 30, "paid": 0,
               "retry": 0, "resume": 0}
_INTENT_KEYS = frozenset({
    "schemaVersion", "kind", "runId", "frozenHead", "branch",
    "oldBuilderRunId", "oldHead", "oldGitCommit", "oldGitDirectory",
    "oldFileSha256", "oldComparisonSpecSha256", "uatFixtureSha256",
    "profileConfigPath", "profileConfigSha256", "profileParameters",
    "profileSnapshots", "sourceIdentity", "candidateIdentity",
    "casePlanGoldSha256", "modelBindings", "thresholds", "builderBudget",
    "mappingScanBudget", "comparisonBudget",
})
_FINAL_KEYS = frozenset({
    "schemaVersion", "kind", "runId", "frozenHead", "reuseIntentSha256",
    "sourceScanResultSha256", "candidateScanResultSha256",
    "sourceIdMappingSha256", "candidateIdMappingSha256",
})
_ATTEMPT_KEYS = frozenset({
    "schemaVersion", "runId", "frozenHead", "reuseIntentSha256",
    "executionKind", "status", "sourceEsHttpMax", "candidateEsHttpMax",
    "builderEsHttpMax", "builderEmbeddingHttpMax", "builderWriteOpsMax",
    "paid", "retry", "resume",
})
_TERMINAL_KEYS = frozenset({
    "schemaVersion", "runId", "reuseIntentSha256", "status", "reason",
    "executionKind", "completedArms", "sourceEsHttp", "candidateEsHttp",
    "builderEsHttp", "builderEmbeddingHttp", "builderWriteOps", "paid",
    "retry", "resume", "reuseFinalSha256",
})


class ReuseBindingError(ValueError):
    """A safe, finite pre-search rejection; never include asset content."""

    def __init__(self, reason: str = "reuse_binding_invalid") -> None:
        super().__init__(reason)


GitBlobReader = Callable[[str, str], bytes]


def _object(raw: bytes) -> dict[str, Any]:
    # _sidecar performs canonical, duplicate-key and finite JSON validation.
    return cast(dict[str, Any], _sidecar(raw))


def git_blob(commit: str, path: str) -> bytes:
    """Read one frozen tracked blob without consulting the working-tree copy."""
    if (_HEAD.fullmatch(commit) is None or not path or path.startswith("/")
            or ".." in Path(path).parts or "\\" in path):
        raise ReuseBindingError()
    try:
        result = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT,
                                check=True, capture_output=True, timeout=15)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise ReuseBindingError("reuse_git_source_missing") from None
    if len(result.stdout) > 16 * 1024 * 1024:
        raise ReuseBindingError()
    return result.stdout


def _frozen_context(head: str) -> bool:
    """Reject a different or dirty tracked checkout before local ES attempts."""
    try:
        actual = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                check=True, capture_output=True, timeout=10).stdout
        dirty = subprocess.run(["git", "status", "--porcelain",
                                "--untracked-files=no"], cwd=ROOT,
                               check=True, capture_output=True, timeout=10).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    return actual == (head + "\n").encode("ascii") and dirty == b""


def _plan(raw: object) -> MinimalKnowledgeRetrievalPlan:
    if type(raw) is not dict:
        raise ReuseBindingError()
    try:
        settings_raw = raw["settings"]
        settings = MinimalRetrievalSettings(
            enabled_domain_ids=tuple(settings_raw["enabledDomainIds"]),
            per_path_candidate_limit=settings_raw["perPathCandidateLimit"],
            final_candidate_limit=settings_raw["finalCandidateLimit"],
            min_partial_candidates=settings_raw["minPartialCandidates"],
            retrieval_timeout_s=settings_raw["retrievalTimeoutSeconds"],
            config_version=settings_raw["configVersion"],
        )
        return MinimalKnowledgeRetrievalPlan(
            original_question=raw["originalQuestion"],
            query_mode=KnowledgeQueryMode(raw["queryMode"]),
            selected_domain_ids=tuple(raw["selectedDomainIds"]), settings=settings,
            items=tuple(RetrievalPlanItem(
                logical_domain_id=item["logicalDomainId"],
                path=RetrievalPath(item["path"]), query_text=item["queryText"],
                candidate_limit=item["candidateLimit"], ordinal=item["ordinal"],
            ) for item in raw["items"]),
            profile_bindings=tuple(tuple(item) for item in raw["profileBindings"]),
            catalog_version=raw["catalogVersion"], schema_version=raw["schemaVersion"],
        )
    except (KeyError, TypeError, ValueError):
        raise ReuseBindingError() from None


@dataclass(frozen=True, slots=True)
class OldBuild:
    spec: ComparisonSpec
    source_map: FrozenIdMapping
    candidate_map: FrozenIdMapping
    file_sha256: tuple[tuple[str, str], ...]
    old_head: str
    blobs: tuple[tuple[str, bytes], ...]


@dataclass(frozen=True, slots=True)
class ScanOutcome:
    """Only the bounded scanner's identity map and finite call count."""

    raw: bytes
    http_requests: int
    mapping_version: str


ScanArm = Callable[[str, object, int], ScanOutcome]
ObservedCalls = Callable[[str], int]


def load_old_build(*, read_blob: GitBlobReader = git_blob) -> OldBuild:
    """Prove the complete old local build/scan chain, not its comparison result."""
    try:
        blobs = {name: read_blob(OLD_COMMIT, f"{OLD_DIRECTORY}/{name}")
                 for name in OLD_FILES}
        if any(type(raw) is not bytes or not raw or
               len(raw) > (16 * 1024 * 1024 if name.endswith("id-mapping.json")
                           else 2 * 1024 * 1024)
               for name, raw in blobs.items()):
            raise ReuseBindingError()
        values = {name: _object(raw) for name, raw in blobs.items()
                  if not name.endswith("id-mapping.json")}
        intent = values["assessment-intent.json"]
        final = values["assessment-final.json"]
        plan = values["scan-plan.json"]
        binding = values["binding.json"]
        attempt = values["attempt.json"]
        built = values["result.json"]
        old_head = plan.get("frozenHead")
        if (plan.get("runId") != OLD_RUN_ID or binding.get("runId") != OLD_RUN_ID
                or attempt.get("runId") != OLD_RUN_ID or built.get("runId") != OLD_RUN_ID
                or type(old_head) is not str or _HEAD.fullmatch(old_head) is None
                or binding.get("frozenHead") != old_head
                or plan.get("branch") != "codex_0915"
                or attempt.get("status") != "consumed"
                or attempt.get("executionKind") != "local"
                or built.get("executionKind") != "local"
                or built.get("status") != "built_read_only_unpublished"
                or built.get("sourceVerifiedByBuilder") is not True
                or built.get("candidateMapping") != "pending_postbuild_readonly_scan"
                or any(built.get(key) != 0 for key in
                       ("paid", "retry", "resume", "onlineAliasWrites"))
                or any(attempt.get(key) != 0 for key in ("retry", "resume"))
                or binding.get("scanPlanSha256") != _sha256(blobs["scan-plan.json"])
                or binding.get("sourceMapScanResultSha256")
                   != _sha256(blobs["source-mapping-scan-result.json"])
                or attempt.get("bindingSha256") != _sha256(blobs["binding.json"])
                or built.get("bindingSha256") != _sha256(blobs["binding.json"])
                or final.get("bindingSha256") != _sha256(blobs["binding.json"])
                or final.get("builderResultSha256") != _sha256(blobs["result.json"])
                or final.get("sourceMapScanResultSha256")
                   != _sha256(blobs["source-mapping-scan-result.json"])
                or final.get("candidateMapScanResultSha256")
                   != _sha256(blobs["candidate-mapping-scan-result.json"])
                or final.get("assessmentIntentSha256")
                   != _sha256(blobs["assessment-intent.json"])
                or plan.get("assessmentIntentSha256")
                   != _sha256(blobs["assessment-intent.json"])
                or binding.get("assessmentIntentSha256")
                   != _sha256(blobs["assessment-intent.json"])
                or built.get("assessmentIntentSha256")
                   != _sha256(blobs["assessment-intent.json"])):
            raise ReuseBindingError()
        fixture = read_blob(old_head, FIXTURE_PATH)
        if _sha256(fixture) != plan.get("fixtureGitBlobSha256"):
            raise ReuseBindingError()
        cases = intent.get("cases")
        if type(cases) is not list:
            raise ReuseBindingError()
        plans = {item["caseId"]: _plan(item["plan"]) for item in cases}
        spec = ComparisonSpec.from_assessment_bytes(
            blobs["assessment-final.json"],
            expected_sha256=_sha256(blobs["assessment-final.json"]),
            intent_raw=blobs["assessment-intent.json"],
            expected_intent_sha256=_sha256(blobs["assessment-intent.json"]),
            uat_fixture_raw=fixture, authoritative_fixture_sha256=_sha256(fixture),
            plans=plans,
        )
        source_map = FrozenIdMapping.from_bytes(
            blobs["source-id-mapping.json"],
            expected_sha256=final["sourceIdMappingSha256"])
        candidate_map = FrozenIdMapping.from_bytes(
            blobs["candidate-id-mapping.json"],
            expected_sha256=final["candidateIdMappingSha256"])
        if (source_map.records != candidate_map.records
                or len(source_map.records) != spec.source_corpus.record_count
                or source_map.index_name != spec.source_corpus.index_name
                or source_map.index_uuid != spec.source_corpus.index_uuid
                or source_map.source_fingerprint != spec.source_corpus.full_fingerprint
                or candidate_map.index_name != spec.candidate_corpus.index_name
                or candidate_map.index_uuid != spec.candidate_corpus.index_uuid
                or candidate_map.source_fingerprint != spec.candidate_corpus.full_fingerprint
                or built.get("candidateIndex") != spec.candidate_corpus.index_name
                or built.get("candidateUuid") != spec.candidate_corpus.index_uuid
                or built.get("candidateFingerprint") != spec.candidate_corpus.full_fingerprint
                or built.get("candidateCount") != spec.candidate_corpus.record_count
                or binding.get("idMappingSha256") != source_map.sha256
                or binding.get("idMappingSourceFingerprint")
                   != spec.source_corpus.full_fingerprint):
            raise ReuseBindingError()
        builder_spec = binding["spec"]
        _verify_frozen_request_hashes(plan, binding, builder_spec)
        update_count = _verify_representation_binding(
            binding, builder_spec, source_map, spec.source_corpus.record_count)
        if (built.get("updatedCount") != update_count
                or built.get("embeddingHttp") != (update_count + 31) // 32
                or built.get("esHttp", 0) > binding["budget"]["esHttp"]
                or intent.get("builderBudget") != binding.get("budget")
                or intent.get("mappingScanBudget") != binding.get("mappingScanBudget")):
            raise ReuseBindingError()
        expected_scans = 1 + (spec.source_corpus.record_count + 249) // 250
        for arm, name, mapping in (
            ("source", "source-mapping-scan-result.json", source_map),
            ("candidate", "candidate-mapping-scan-result.json", candidate_map),
        ):
            scan = values[name]
            if (scan.get("status") != "scanned_read_only" or scan.get("arm") != arm
                    or scan.get("reason") is not None
                    or scan.get("assessmentIntentSha256") != spec.assessment_intent_sha256
                    or scan.get("indexName") != mapping.index_name
                    or scan.get("indexUuid") != mapping.index_uuid
                    or scan.get("sourceFingerprint") != mapping.source_fingerprint
                    or scan.get("sha256") != mapping.sha256
                    or scan.get("recordCount") != spec.source_corpus.record_count
                    or scan.get("esHttp") != expected_scans
                    or scan.get("maxEsHttp") != expected_scans
                    or scan.get("retry") != 0 or scan.get("resume") != 0):
                raise ReuseBindingError()
        return OldBuild(spec, source_map, candidate_map,
            tuple((name, _sha256(blobs[name])) for name in OLD_FILES), old_head,
            tuple((name, blobs[name]) for name in OLD_FILES))
    except (KeyError, TypeError, ValueError, ComparisonRunError,
            UnicodeError, json.JSONDecodeError):
        raise ReuseBindingError() from None


def _identity(corpus: Any) -> dict[str, object]:
    return {"indexName": corpus.index_name, "indexUuid": corpus.index_uuid,
            "mappingSha256": corpus.mapping_sha256,
            "sourceFingerprint": corpus.full_fingerprint,
            "recordCount": corpus.record_count}


def _case_plan_gold_sha256(spec: ComparisonSpec) -> str:
    return _sha256(_canonical_bytes([{
        "caseId": case.case_id, "planHash": plan_fingerprint(case.plan),
        "necessarySources": [
            {"documentId": ref.document_id, "chunkId": ref.chunk_id,
             "contentSha256": ref.content_sha256}
            for ref in case.necessary_sources],
        "core": case.core, "retained": case.retained,
    } for case in spec.cases]))


def freeze_new_reuse_input(*, old: OldBuild, run_id: str, frozen_head: str,
                           profile_parameters: Mapping[str, object],
                           config_raw: bytes, fixture_raw: bytes,
                           read_blob: GitBlobReader = git_blob) -> bytes:
    """Create a new immutable comparison intent; build/write budgets are zero."""
    spec = old.spec
    if (_RUN.fullmatch(run_id) is None or run_id == OLD_RUN_ID
            or _HEAD.fullmatch(frozen_head) is None or frozen_head == old.old_head
            or type(config_raw) is not bytes or not config_raw
            or type(fixture_raw) is not bytes
            or _sha256(fixture_raw) != spec.uat_fixture_sha256
            or read_blob(frozen_head, CONFIG_PATH) != config_raw
            or read_blob(frozen_head, FIXTURE_PATH) != fixture_raw
            or set(profile_parameters) != {"tax.policy", "tax.law"}):
        raise ReuseBindingError()
    old_params = _object(spec.intent_raw)["profileParameters"]
    params = dict(profile_parameters)
    for domain in ("tax.policy", "tax.law"):
        current = params[domain]
        prior = old_params[domain]
        if (type(current) is not dict or set(current) != set(prior)
                or any(current[key] != prior[key] for key in prior if key != "configSha256")
                or type(current["configSha256"]) is not str
                or _SHA.fullmatch(current["configSha256"]) is None):
            raise ReuseBindingError()
    per_arm = 1 + (spec.source_corpus.record_count + 249) // 250
    if per_arm != 64 or _object(spec.intent_raw)["comparisonBudget"] != _COMPARISON:
        raise ReuseBindingError()
    intent = {
        "schemaVersion": 2, "kind": "knowledge_b_reuse_comparison_intent_v2",
        "runId": run_id, "frozenHead": frozen_head, "branch": "codex_0915",
        "oldBuilderRunId": OLD_RUN_ID, "oldHead": old.old_head,
        "oldGitCommit": OLD_COMMIT, "oldGitDirectory": OLD_DIRECTORY,
        "oldFileSha256": dict(old.file_sha256),
        "oldComparisonSpecSha256": comparison_spec_fingerprint(spec),
        "uatFixtureSha256": spec.uat_fixture_sha256,
        "profileConfigPath": CONFIG_PATH,
        "profileConfigSha256": _sha256(config_raw),
        "profileParameters": params,
        "profileSnapshots": {arm: dict(entries) for arm, entries in spec.profile_snapshots},
        "sourceIdentity": _identity(spec.source_corpus),
        "candidateIdentity": _identity(spec.candidate_corpus),
        "casePlanGoldSha256": _case_plan_gold_sha256(spec),
        "modelBindings": _object(spec.intent_raw)["modelBindings"],
        "thresholds": _object(spec.intent_raw)["thresholds"],
        "builderBudget": dict(_ZERO_BUILD),
        "mappingScanBudget": {"sourceEsHttp": per_arm,
                              "candidateEsHttp": per_arm, "retry": 0, "resume": 0},
        "comparisonBudget": dict(_COMPARISON),
    }
    return _canonical_bytes(intent)


def scan_receipt(*, arm: str, intent_raw: bytes, map_raw: bytes,
                 es_http: int, mapping_version: str,
                 execution_kind: str) -> bytes:
    """Minimal witness emitted after the existing bounded full-record scanner."""
    intent = _object(intent_raw)
    if (arm not in ("source", "candidate") or execution_kind not in ("fake", "local")
            or type(es_http) is not int or type(mapping_version) is not str
            or not mapping_version):
        raise ReuseBindingError()
    identity = intent[f"{arm}Identity"]
    expected = intent["mappingScanBudget"][f"{arm}EsHttp"]
    version_key = "baselineMappingVersion" if arm == "source" else "candidateMappingVersion"
    parameters = intent["profileParameters"]
    if any(parameters[domain][version_key] != mapping_version
           for domain in ("tax.policy", "tax.law")):
        raise ReuseBindingError("scan_mapping_drift")
    mapping = FrozenIdMapping.from_bytes(map_raw, expected_sha256=_sha256(map_raw))
    if (mapping.index_name != identity["indexName"]
            or mapping.index_uuid != identity["indexUuid"]
            or mapping.source_fingerprint != identity["sourceFingerprint"]
            or len(mapping.records) != identity["recordCount"]
            or es_http != expected):
        raise ReuseBindingError()
    return _canonical_bytes({
        "schemaVersion": 2, "kind": "knowledge_b_reuse_full_scan_v2",
        "runId": intent["runId"], "frozenHead": intent["frozenHead"],
        "reuseIntentSha256": _sha256(intent_raw), "arm": arm,
        "executionKind": execution_kind, "status": "scanned_read_only",
        "indexName": mapping.index_name, "indexUuid": mapping.index_uuid,
        "mappingVersion": mapping_version,
        "mappingSha256": identity["mappingSha256"],
        "sourceFingerprint": mapping.source_fingerprint,
        "recordCount": len(mapping.records), "idMappingSha256": mapping.sha256,
        "esHttp": es_http, "maxEsHttp": expected, "retry": 0, "resume": 0,
    })


def finalize_reuse_scans(*, intent_raw: bytes,
                         source_scan_raw: bytes, candidate_scan_raw: bytes,
                         source_map_raw: bytes, candidate_map_raw: bytes) -> bytes:
    """Seal two fresh full scans; this is not a builder completion result."""
    intent = _object(intent_raw)
    for arm, receipt_raw, map_raw in (
        ("source", source_scan_raw, source_map_raw),
        ("candidate", candidate_scan_raw, candidate_map_raw),
    ):
        receipt = _object(receipt_raw)
        mapping = FrozenIdMapping.from_bytes(map_raw, expected_sha256=_sha256(map_raw))
        if (receipt.get("arm") != arm
                or receipt.get("runId") != intent.get("runId")
                or receipt.get("reuseIntentSha256") != _sha256(intent_raw)
                or receipt.get("idMappingSha256") != mapping.sha256):
            raise ReuseBindingError()
    return _canonical_bytes({
        "schemaVersion": 2, "kind": "knowledge_b_reuse_comparison_final_v2",
        "runId": intent["runId"], "frozenHead": intent["frozenHead"],
        "reuseIntentSha256": _sha256(intent_raw),
        "sourceScanResultSha256": _sha256(source_scan_raw),
        "candidateScanResultSha256": _sha256(candidate_scan_raw),
        "sourceIdMappingSha256": _sha256(source_map_raw),
        "candidateIdMappingSha256": _sha256(candidate_map_raw),
    })


def spec_for_reuse(old: OldBuild, *, intent_raw: bytes,
                   final_raw: bytes) -> ComparisonSpec:
    """Reuse exactly the old vetted cases, not the old run's assessment ID."""
    return replace(old.spec, intent_raw=intent_raw,
        assessment_intent_sha256=_sha256(intent_raw), final_raw=final_raw,
        assessment_sha256=_sha256(final_raw))


def verify_reuse_scan_execution(*, intent_raw: bytes, final_raw: bytes,
                                attempt_raw: bytes, terminal_raw: bytes) -> None:
    """Prove the new run consumed exactly one successful local scan window.

    This is a static, zero-network check of append-only evidence. The bounded
    scanner and its physical transport remain the source of observed counts.
    """
    try:
        intent, final = _object(intent_raw), _object(final_raw)
        attempt, terminal = _object(attempt_raw), _object(terminal_raw)
        if (set(intent) != _INTENT_KEYS or set(final) != _FINAL_KEYS
                or set(attempt) != _ATTEMPT_KEYS or set(terminal) != _TERMINAL_KEYS
                or intent.get("kind") != "knowledge_b_reuse_comparison_intent_v2"
                or final.get("kind") != "knowledge_b_reuse_comparison_final_v2"
                or attempt.get("schemaVersion") != 2
                or terminal.get("schemaVersion") != 2
                or attempt.get("runId") != intent.get("runId")
                or terminal.get("runId") != intent.get("runId")
                or final.get("runId") != intent.get("runId")
                or attempt.get("frozenHead") != intent.get("frozenHead")
                or final.get("frozenHead") != intent.get("frozenHead")
                or attempt.get("reuseIntentSha256") != _sha256(intent_raw)
                or terminal.get("reuseIntentSha256") != _sha256(intent_raw)
                or final.get("reuseIntentSha256") != _sha256(intent_raw)
                or attempt.get("executionKind") != "local"
                or terminal.get("executionKind") != "local"
                or attempt.get("status") != "consumed"
                or terminal.get("status") != "scanned_read_only"
                or terminal.get("reason") != "none"
                or terminal.get("completedArms") != ["source", "candidate"]
                or attempt.get("sourceEsHttpMax") != 64
                or attempt.get("candidateEsHttpMax") != 64
                or terminal.get("sourceEsHttp") != 64
                or terminal.get("candidateEsHttp") != 64
                or any(attempt.get(key) != 0 for key in (
                    "builderEsHttpMax", "builderEmbeddingHttpMax",
                    "builderWriteOpsMax", "paid", "retry", "resume"))
                or any(terminal.get(key) != 0 for key in (
                    "builderEsHttp", "builderEmbeddingHttp", "builderWriteOps",
                    "paid", "retry", "resume"))
                or terminal.get("reuseFinalSha256") != _sha256(final_raw)):
            raise ReuseBindingError("reuse_scan_execution_invalid")
    except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        raise ReuseBindingError("reuse_scan_execution_invalid") from None


def _write_once(path: Path, raw: bytes) -> None:
    if type(raw) is not bytes or not raw or len(raw) > 16 * 1024 * 1024:
        raise ReuseBindingError()
    try:
        with path.open("xb") as handle:
            handle.write(raw)
    except OSError:
        raise ReuseBindingError("reuse_run_already_used") from None


def create_reuse_run(directory: Path, intent_raw: bytes, *,
                     frozen_context: Callable[[str], bool] = _frozen_context) -> None:
    """Create the independent run directory exactly once, before any ES call."""
    intent = _object(intent_raw)
    if (set(intent) != _INTENT_KEYS or intent.get("kind")
            != "knowledge_b_reuse_comparison_intent_v2"
            or directory.name != intent.get("runId")
            or type(intent.get("frozenHead")) is not str
            or not frozen_context(intent["frozenHead"])
            or directory.exists() or not directory.parent.is_dir()):
        raise ReuseBindingError("reuse_run_already_used")
    try:
        directory.mkdir()
    except OSError:
        raise ReuseBindingError("reuse_run_already_used") from None
    _write_once(directory / "reuse-intent.json", intent_raw)


def execute_reuse_scans(directory: Path, *, scan_arm: ScanArm,
                        observed_calls: ObservedCalls,
                        execution_kind: str = "local",
                        read_blob: GitBlobReader = git_blob,
                        frozen_context: Callable[[str], bool] = _frozen_context) -> bytes:
    """Run two fresh full scans once, using a caller-owned bounded transport.

    ``scan_arm(arm, corpus_binding, 64)`` must call the existing
    ``scan_id_mapping_v1`` with a transport enforcing GET /<index> and
    POST /<index>/_search only and an independent 64-request ceiling per arm.
    ``observed_calls(arm)`` must report transport *attempts*, including failed
    HTTP calls. This function emits append-only, identity-only terminal evidence.
    """
    if execution_kind not in ("local", "fake"):
        raise ReuseBindingError()
    intent_path = directory / "reuse-intent.json"
    try:
        intent_raw = intent_path.read_bytes()
    except OSError:
        raise ReuseBindingError() from None
    intent = _object(intent_raw)
    if (set(intent) != _INTENT_KEYS or directory.name != intent.get("runId")
            or any((directory / name).exists() for name in (
                "reuse-scan-attempt.json", "reuse-scan-terminal.json",
                "reuse-final.json", "source-id-mapping.json",
                "candidate-id-mapping.json", "source-scan-result.json",
                "candidate-scan-result.json"))):
        raise ReuseBindingError("reuse_run_already_used")
    old = load_old_build(read_blob=read_blob)
    current_head = intent.get("frozenHead")
    if (type(current_head) is not str or _HEAD.fullmatch(current_head) is None
            or not frozen_context(current_head)):
        raise ReuseBindingError()
    try:
        expected = freeze_new_reuse_input(
            old=old, run_id=intent["runId"], frozen_head=current_head,
            profile_parameters=intent["profileParameters"],
            config_raw=read_blob(current_head, CONFIG_PATH),
            fixture_raw=read_blob(current_head, FIXTURE_PATH),
            read_blob=read_blob,
        )
        if expected != intent_raw:
            raise ReuseBindingError()
        from tests.evaluation.knowledge.rebuild_b_local_runner import (  # noqa: PLC0415
            BLocalRunError, _validate_profile_parameters,
        )
        try:
            _validate_profile_parameters(current_head, intent["profileParameters"])
        except BLocalRunError:
            raise ReuseBindingError("profile_config_drift") from None
    except (KeyError, TypeError, ValueError):
        raise ReuseBindingError() from None
    _write_once(directory / "reuse-scan-attempt.json", _canonical_bytes({
        "schemaVersion": 2, "runId": intent["runId"],
        "frozenHead": current_head, "reuseIntentSha256": _sha256(intent_raw),
        "executionKind": execution_kind, "status": "consumed",
        "sourceEsHttpMax": 64, "candidateEsHttpMax": 64,
        "builderEsHttpMax": 0, "builderEmbeddingHttpMax": 0,
        "builderWriteOpsMax": 0, "paid": 0, "retry": 0, "resume": 0,
    }))
    counts: dict[str, int] = {"source": 0, "candidate": 0}
    completed: list[str] = []
    outcome = "failed"
    reason = "scan_failed"
    final_raw: bytes | None = None
    try:
        receipts: dict[str, bytes] = {}
        maps: dict[str, bytes] = {}
        for arm, corpus, original in (
            ("source", old.spec.source_corpus, old.source_map),
            ("candidate", old.spec.candidate_corpus, old.candidate_map),
        ):
            scanned = scan_arm(arm, corpus, 64)
            observed = observed_calls(arm)
            if (type(scanned) is not ScanOutcome or type(observed) is not int
                    or observed != scanned.http_requests or observed != 64):
                raise ReuseBindingError("scan_budget_invalid")
            mapping = FrozenIdMapping.from_bytes(
                scanned.raw, expected_sha256=_sha256(scanned.raw))
            if (mapping.records != original.records or mapping.index_name != original.index_name
                    or mapping.index_uuid != original.index_uuid
                    or mapping.source_fingerprint != original.source_fingerprint):
                raise ReuseBindingError("scan_identity_drift")
            counts[arm] = observed
            maps[arm] = scanned.raw
            receipts[arm] = scan_receipt(
                arm=arm, intent_raw=intent_raw, map_raw=scanned.raw,
                es_http=observed, mapping_version=scanned.mapping_version,
                execution_kind=execution_kind)
            _write_once(directory / f"{arm}-id-mapping.json", scanned.raw)
            _write_once(directory / f"{arm}-scan-result.json", receipts[arm])
            completed.append(arm)
        final_raw = finalize_reuse_scans(
            intent_raw=intent_raw, source_scan_raw=receipts["source"],
            candidate_scan_raw=receipts["candidate"],
            source_map_raw=maps["source"], candidate_map_raw=maps["candidate"])
        _write_once(directory / "reuse-final.json", final_raw)
        outcome, reason = "scanned_read_only", "none"
    except BaseException as error:
        # The scanner/transport may have sent calls before failing. Preserve
        # actual attempts and a fixed reason; never serialize exception text.
        for arm in counts:
            try:
                observed = observed_calls(arm)
                counts[arm] = observed if type(observed) is int and observed >= 0 else -1
            except Exception:
                counts[arm] = -1
        if any(count < 0 or count > 64 for count in counts.values()):
            reason = "scan_count_unavailable_or_exceeded"
        elif isinstance(error, ReuseBindingError):
            reason = str(error)
        elif isinstance(error, (KeyboardInterrupt, SystemExit)):
            reason = "scan_interrupted"
        else:
            reason = "scan_failed"
    terminal = _canonical_bytes({
        "schemaVersion": 2, "runId": intent["runId"],
        "reuseIntentSha256": _sha256(intent_raw), "status": outcome,
        "reason": reason, "executionKind": execution_kind,
        "completedArms": completed, "sourceEsHttp": counts["source"],
        "candidateEsHttp": counts["candidate"], "builderEsHttp": 0,
        "builderEmbeddingHttp": 0, "builderWriteOps": 0,
        "paid": 0, "retry": 0, "resume": 0,
        "reuseFinalSha256": None if final_raw is None else _sha256(final_raw),
    })
    _write_once(directory / "reuse-scan-terminal.json", terminal)
    if outcome != "scanned_read_only":
        raise ReuseBindingError(reason)
    assert final_raw is not None
    return final_raw


def verify_reuse_provenance(spec: ComparisonSpec, baseline: ArmEndpoint,
                            candidate: ArmEndpoint, sidecars: Mapping[str, bytes],
                            local_admission: LocalRuntimeAdmission | None,
                            *, read_blob: GitBlobReader = git_blob) -> tuple[str, str]:
    """Admission branch for exact v2 sidecars; v1's verifier remains unchanged."""
    try:
        if not isinstance(sidecars, Mapping) or set(sidecars) != REUSE_SIDECARS:
            raise ReuseBindingError()
        intent_raw, final_raw = sidecars["reuseIntent"], sidecars["reuseFinal"]
        intent, final = _object(intent_raw), _object(final_raw)
        verify_reuse_scan_execution(intent_raw=intent_raw, final_raw=final_raw,
            attempt_raw=sidecars["reuseAttempt"],
            terminal_raw=sidecars["reuseTerminal"])
        old = load_old_build(read_blob=read_blob)
        expected = spec_for_reuse(old, intent_raw=intent_raw, final_raw=final_raw)
        if (spec != expected or spec.intent_raw != intent_raw or spec.final_raw != final_raw
                or set(intent) != _INTENT_KEYS or set(final) != _FINAL_KEYS
                or intent.get("kind") != "knowledge_b_reuse_comparison_intent_v2"
                or intent.get("schemaVersion") != 2
                or final.get("kind") != "knowledge_b_reuse_comparison_final_v2"
                or final.get("schemaVersion") != 2
                or intent.get("runId") in (None, OLD_RUN_ID)
                or _RUN.fullmatch(intent["runId"]) is None
                or type(intent.get("frozenHead")) is not str
                or _HEAD.fullmatch(intent["frozenHead"]) is None
                or intent["frozenHead"] == old.old_head
                or intent.get("branch") != "codex_0915"
                or intent.get("oldBuilderRunId") != OLD_RUN_ID
                or intent.get("oldHead") != old.old_head
                or intent.get("oldGitCommit") != OLD_COMMIT
                or intent.get("oldGitDirectory") != OLD_DIRECTORY
                or intent.get("oldFileSha256") != dict(old.file_sha256)
                or intent.get("oldComparisonSpecSha256")
                   != comparison_spec_fingerprint(old.spec)
                or intent.get("casePlanGoldSha256") != _case_plan_gold_sha256(old.spec)
                or intent.get("uatFixtureSha256") != spec.uat_fixture_sha256
                or intent.get("sourceIdentity") != _identity(spec.source_corpus)
                or intent.get("candidateIdentity") != _identity(spec.candidate_corpus)
                or intent.get("profileSnapshots")
                   != {arm: dict(entries) for arm, entries in spec.profile_snapshots}
                or intent.get("builderBudget") != _ZERO_BUILD
                or intent.get("comparisonBudget") != _COMPARISON
                or intent.get("mappingScanBudget")
                   != {"sourceEsHttp": 64, "candidateEsHttp": 64,
                       "retry": 0, "resume": 0}
                or intent.get("thresholds") != _object(old.spec.intent_raw)["thresholds"]
                or intent.get("modelBindings") != _object(old.spec.intent_raw)["modelBindings"]
                or intent.get("profileConfigPath") != CONFIG_PATH
                or intent.get("profileConfigSha256")
                   != _sha256(read_blob(intent["frozenHead"], CONFIG_PATH))
                or _sha256(read_blob(intent["frozenHead"], FIXTURE_PATH))
                   != spec.uat_fixture_sha256
                or final.get("runId") != intent["runId"]
                or final.get("frozenHead") != intent["frozenHead"]
                or final.get("reuseIntentSha256") != _sha256(intent_raw)
                or final.get("sourceScanResultSha256")
                   != _sha256(sidecars["sourceScanResult"])
                or final.get("candidateScanResultSha256")
                   != _sha256(sidecars["candidateScanResult"])
                or local_admission is None):
            raise ReuseBindingError()
        local_admission.validate(spec, frozen_head=intent["frozenHead"])
        if local_admission.run_id != intent["runId"]:
            raise ReuseBindingError()
        old_params = _object(old.spec.intent_raw)["profileParameters"]
        new_params = intent.get("profileParameters")
        if type(new_params) is not dict or set(new_params) != set(old_params):
            raise ReuseBindingError()
        for domain, prior in old_params.items():
            current = new_params[domain]
            if (type(current) is not dict or set(current) != set(prior)
                    or any(current[key] != prior[key] for key in prior
                           if key != "configSha256")
                    or type(current["configSha256"]) is not str
                    or _SHA.fullmatch(current["configSha256"]) is None):
                raise ReuseBindingError()
        # Reuse the existing frozen Java-launch/YAML/config-directory hash rule.
        from tests.evaluation.knowledge.rebuild_b_local_runner import (  # noqa: PLC0415
            BLocalRunError, _validate_profile_parameters,
        )
        try:
            _validate_profile_parameters(intent["frozenHead"], new_params)
        except BLocalRunError:
            raise ReuseBindingError("profile_config_drift") from None
        if (baseline.snapshots != dict(spec.profile_snapshots)["baseline"]
                or candidate.snapshots != dict(spec.profile_snapshots)["candidate"]
                or final.get("sourceIdMappingSha256") != baseline.id_mapping.sha256
                or final.get("candidateIdMappingSha256") != candidate.id_mapping.sha256
                or baseline.id_mapping.records != old.source_map.records
                or candidate.id_mapping.records != old.candidate_map.records
                or baseline.id_mapping.records != candidate.id_mapping.records):
            raise ReuseBindingError()
        for arm, endpoint, old_map in (
            ("source", baseline, old.source_map),
            ("candidate", candidate, old.candidate_map),
        ):
            receipt = _object(sidecars[f"{arm}ScanResult"])
            corpus = spec.source_corpus if arm == "source" else spec.candidate_corpus
            if (set(receipt) != {"schemaVersion", "kind", "runId", "frozenHead",
                                 "reuseIntentSha256", "arm", "executionKind",
                                 "status", "indexName", "indexUuid", "mappingVersion",
                                 "mappingSha256", "sourceFingerprint", "recordCount",
                                 "idMappingSha256", "esHttp", "maxEsHttp", "retry", "resume"}
                    or receipt["schemaVersion"] != 2
                    or receipt["kind"] != "knowledge_b_reuse_full_scan_v2"
                    or receipt["runId"] != intent["runId"]
                    or receipt["frozenHead"] != intent["frozenHead"]
                    or receipt["reuseIntentSha256"] != _sha256(intent_raw)
                    or receipt["arm"] != arm
                    or receipt["executionKind"] != "local"
                    or receipt["status"] != "scanned_read_only"
                    or receipt["indexName"] != corpus.index_name
                    or receipt["indexUuid"] != corpus.index_uuid
                    or receipt["mappingSha256"] != corpus.mapping_sha256
                    or receipt["sourceFingerprint"] != corpus.full_fingerprint
                    or receipt["mappingVersion"] != _object(old.spec.intent_raw)[
                        "profileParameters"]["tax.policy"][
                            "baselineMappingVersion" if arm == "source"
                            else "candidateMappingVersion"]
                    or receipt["recordCount"] != corpus.record_count
                    or receipt["idMappingSha256"] != endpoint.id_mapping.sha256
                    or receipt["esHttp"] != 64 or receipt["maxEsHttp"] != 64
                    or receipt["retry"] != 0 or receipt["resume"] != 0
                    or endpoint.id_mapping.index_name != old_map.index_name
                    or endpoint.id_mapping.index_uuid != old_map.index_uuid
                    or endpoint.id_mapping.source_fingerprint
                       != old_map.source_fingerprint):
                raise ReuseBindingError()
        return _sha256(_canonical_bytes({
            "reuseIntentSha256": _sha256(intent_raw),
            "reuseFinalSha256": _sha256(final_raw),
            "reuseAttemptSha256": _sha256(sidecars["reuseAttempt"]),
            "reuseTerminalSha256": _sha256(sidecars["reuseTerminal"]),
            "oldGitCommit": OLD_COMMIT,
            "oldFileSha256": dict(old.file_sha256),
            "sourceScanResultSha256": _sha256(sidecars["sourceScanResult"]),
            "candidateScanResultSha256": _sha256(sidecars["candidateScanResult"]),
            "sourceIdMappingSha256": baseline.id_mapping.sha256,
            "candidateIdMappingSha256": candidate.id_mapping.sha256,
            "localRunId": local_admission.run_id,
            "localFrozenHead": local_admission.frozen_head,
            "localArmBindings": local_admission.arm_bindings,
            "javaArtifactSha256": local_admission.java_artifact_sha256,
        })), "local"
    except (KeyError, TypeError, ValueError, ComparisonRunError,
            UnicodeError, json.JSONDecodeError):
        raise ComparisonRunError("source_id_mapping_confounded", CallTotals(0, 0, 0), ()) from None
