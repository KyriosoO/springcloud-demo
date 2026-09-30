"""One-shot local B comparison after the existing candidate freeze/finalize flow.

No LLM is used. The caller must have already frozen both full physical-ID maps
and the final assessment with run-b-representation-candidate-v1.py. This runner
only opens two owned read aliases, launches two isolated typed Java instances,
compares the same ten plans, records bounded identity-only evidence, and closes
its aliases. It cannot publish or move the production alias.
"""
from __future__ import annotations

import argparse
import asyncio
import ctypes
from contextlib import AsyncExitStack, contextmanager
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import base64
import hmac
from importlib import metadata
from io import BytesIO
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import tomllib
from typing import TYPE_CHECKING, Any, Callable, Iterator
from zipfile import ZipFile

import httpx

from agent_runtime.api.cancellation import MutableCancellationSignal
from agent_runtime.capability_api.contracts import OpaqueUserToken
from agent_runtime.knowledge.contracts import KnowledgeRetrievalContext, RetrievalPath, RetrievalPlanItem
from agent_runtime.knowledge.intent_contracts import KnowledgeQueryMode
from agent_runtime.knowledge.minimal_plan import MinimalKnowledgeRetrievalPlan, MinimalRetrievalSettings
from agent_runtime.knowledge.retrieval.bge_embedding import BgeM3EmbeddingAdapter
from agent_runtime.knowledge.retrieval.bge_rerank_context import ContextualBgeRerankAdapter
from agent_runtime.knowledge.retrieval.es_adapter import EsKnowledgeSearchAdapter
from agent_runtime.knowledge.retrieval.contracts import KnowledgePathRequest, PathRetrievalResult
from agent_runtime.knowledge.retrieval.http import HttpxKnowledgeTransport, build_knowledge_http_client
from tests.evaluation.knowledge.rebuild_b_comparator import (
    ArmEndpoint, CallTotals, ComparisonRun, ComparisonRunError, ComparisonSpec,
    FrozenIdMapping, LocalRuntimeAdmission, LocalRuntimeReceipt,
    admit_completed_local_run, blind_label_pool, run_comparison,
)
from tests.evaluation.knowledge.rebuild_b_local_transport import (
    ArmIdentity, BIsolatedAliases, BLocalTransportError, PhysicalEsProxy,
)
from tests.evaluation.knowledge import rebuild_b_reuse_binding as reuse

if TYPE_CHECKING:
    from knowledge_corpus_tools.b_candidate_freeze_v1 import GitState


ROOT = Path(__file__).resolve().parents[4]
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_OUTPUT_FILES = ("comparison-java-attestation.json", "comparison-attempt.json", "comparison-result.json",
                 "comparison-blind-label-pool.json")
_PREPARATION_OUTPUTS = ("comparison-preparation-attempt.json", "comparison-preparation-result.json",
                        "assessment-intent.json", "preliminary-request.json")
_BINDING_OUTPUTS = ("request.json", "comparison-source-binding-result.json")
_PREPARATION_MANIFEST = ROOT / "knowledge-corpus-tools/evidence/asset-manifest.candidate-05.jsonl"
_SIDECARS = {
    "scanPlan": "scan-plan.json", "binding": "binding.json",
    "builderResult": "result.json", "sourceScanResult": "source-mapping-scan-result.json",
    "candidateScanResult": "candidate-mapping-scan-result.json",
}
_EXECUTION_SOURCES = (
    "agent-runtime/scripts/run-knowledge-b-comparison-v1.ps1",
    "agent-runtime/tests/evaluation/knowledge",
    "agent-runtime/src/agent_runtime",
    "agent-runtime/pyproject.toml",
    "es-query-service/src",
    "es-query-service/pom.xml",
    "serviceCenter/pom.xml",
    "knowledge-corpus-tools/src/knowledge_corpus_tools",
    "knowledge-corpus-tools/pyproject.toml",
)
_PROFILE_IDS = {"tax.policy": "tax-policy-v1", "tax.law": "tax-law-v1"}
_PROFILE_VERSION = "tax-knowledge-search-v1"
_READ_POLICY_VERSION = "tax-public-authenticated-v1"
_RUNTIME_CONFIG_FILES = (
    "application.yml", "application-datasource.yml", "application-es.yml",
)
_RUNTIME_CONFIG_ROOT = "config-service/src/main/resources/config"
_STARTUP_EVIDENCE_ROOT = ROOT / "knowledge-corpus-tools/evidence"
_STARTUP_SOURCE_COMMIT = "c9b8642e9c20765814df4b3422cfa958a2c4900c"
_STARTUP_SOURCE_PATH = "knowledge-corpus-tools/evidence/knowledge-b-body-20260930-01"
_STARTUP_SOURCE_FILES = (
    "scan-plan.json", "binding.json", "result.json", "attempt.json", "assessment-intent.json",
    "assessment-final.json", "source-mapping-scan-result.json",
    "candidate-mapping-scan-result.json", "source-id-mapping.json",
    "candidate-id-mapping.json",
)
_STARTUP_BUDGET = {"metadataEsHttp": 30, "aliasWrites": 4,
                   "readinessPerArm": 60, "typedSearch": 0, "queryEmbedding": 0,
                   "rerank": 0, "paid": 0, "jwtHttp": 0, "retry": 0, "resume": 0}


class BLocalRunError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _read(path: Path, maximum: int = 2 * 1024 * 1024) -> bytes:
    try:
        with path.open("rb") as stream:
            raw = stream.read(maximum + 1)
    except OSError:
        raise BLocalRunError("frozen_asset_missing") from None
    if not raw or len(raw) > maximum:
        raise BLocalRunError("frozen_asset_invalid")
    return raw


def _object(raw: bytes) -> dict[str, Any]:
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise BLocalRunError("frozen_asset_invalid") from None
    if type(result) is not dict or _canonical(result) != raw:
        raise BLocalRunError("frozen_asset_invalid")
    return result


def _write_once(path: Path, value: object) -> None:
    _write_bytes_once(path, _canonical(value))


def _write_bytes_once(path: Path, raw: bytes) -> None:
    try:
        with path.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        raise BLocalRunError("append_only_evidence_failed") from None


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                            text=True, encoding="utf-8", check=False)
    if result.returncode != 0:
        raise BLocalRunError("git_state_invalid")
    return result.stdout.strip()


def _git_bytes(*args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=False)
    if result.returncode != 0:
        raise BLocalRunError("git_state_invalid")
    return result.stdout


def _frozen_runtime_config_hashes(frozen_head: str) -> dict[str, str]:
    if re.fullmatch(r"[0-9a-f]{40}", frozen_head) is None:
        raise BLocalRunError("frozen_runtime_config_invalid")
    hashes: dict[str, str] = {}
    for name in _RUNTIME_CONFIG_FILES:
        try:
            raw = _git_bytes("show", f"{frozen_head}:{_RUNTIME_CONFIG_ROOT}/{name}")
        except BLocalRunError:
            raise BLocalRunError("frozen_runtime_config_invalid") from None
        if not raw or len(raw) > 2 * 1024 * 1024:
            raise BLocalRunError("frozen_runtime_config_invalid")
        hashes[name] = sha256(raw).hexdigest()
    return hashes


def _frozen_runtime_config_dir(jar: Path, frozen_head: str) -> tuple[Path, dict[str, str]]:
    resolved = jar.resolve()
    if (resolved.name != "es-query-service-0.0.1-SNAPSHOT.jar"
            or resolved.parent.name != "target"
            or resolved.parent.parent.name != "es-query-service"):
        raise BLocalRunError("frozen_runtime_config_invalid")
    build_root = resolved.parents[2]
    config_dir = (build_root / _RUNTIME_CONFIG_ROOT).resolve()
    if not config_dir.is_relative_to(build_root):
        raise BLocalRunError("frozen_runtime_config_invalid")
    hashes = _frozen_runtime_config_hashes(frozen_head)
    for name, expected in hashes.items():
        path = (config_dir / name).resolve()
        if not path.is_relative_to(config_dir):
            raise BLocalRunError("frozen_runtime_config_invalid")
        try:
            raw = _read(path)
        except BLocalRunError:
            raise BLocalRunError("frozen_runtime_config_invalid") from None
        if sha256(raw).hexdigest() != expected:
            raise BLocalRunError("frozen_runtime_config_invalid")
    return config_dir, hashes


def _require_locked_python_environment(mode: str) -> None:
    """Reject a sibling venv or dependency drift before any source/ES operation."""
    project = "agent-runtime" if mode == "comparison" else "knowledge-corpus-tools" if mode == "preparation" else None
    if project is None or sys.version_info[:2] != (3, 12):
        raise BLocalRunError("python_environment_invalid")
    try:
        manifest = tomllib.loads(_read(ROOT / project / "pyproject.toml", 64 * 1024).decode("utf-8"))
        dependencies = manifest["project"]["dependencies"]
        if type(dependencies) is not list or not dependencies:
            raise ValueError
        for dependency in dependencies:
            if type(dependency) is not str or (match := re.fullmatch(
                    r"([A-Za-z0-9][A-Za-z0-9._-]*)==([0-9][A-Za-z0-9._+-]*)", dependency)) is None:
                raise ValueError
            if metadata.version(match.group(1)) != match.group(2):
                raise ValueError
    except (KeyError, OSError, UnicodeError, ValueError, metadata.PackageNotFoundError):
        raise BLocalRunError("python_environment_invalid") from None


def _plan(raw: dict[str, Any]) -> MinimalKnowledgeRetrievalPlan:
    try:
        s = raw["settings"]
        settings = MinimalRetrievalSettings(
            enabled_domain_ids=tuple(s["enabledDomainIds"]),
            per_path_candidate_limit=s["perPathCandidateLimit"],
            final_candidate_limit=s["finalCandidateLimit"],
            min_partial_candidates=s["minPartialCandidates"],
            retrieval_timeout_s=s["retrievalTimeoutSeconds"],
            config_version=s["configVersion"],
        )
        return MinimalKnowledgeRetrievalPlan(
            original_question=raw["originalQuestion"],
            query_mode=KnowledgeQueryMode(raw["queryMode"]),
            selected_domain_ids=tuple(raw["selectedDomainIds"]),
            settings=settings,
            items=tuple(RetrievalPlanItem(
                logical_domain_id=item["logicalDomainId"],
                path=RetrievalPath(item["path"]), query_text=item["queryText"],
                candidate_limit=item["candidateLimit"], ordinal=item["ordinal"],
            ) for item in raw["items"]),
            profile_bindings=tuple(tuple(item) for item in raw["profileBindings"]),
            catalog_version=raw["catalogVersion"], schema_version=raw["schemaVersion"],
        )
    except (KeyError, TypeError, ValueError):
        raise BLocalRunError("plan_invalid") from None


@dataclass(frozen=True, slots=True)
class FrozenInputs:
    spec: ComparisonSpec
    sidecars: dict[str, bytes]
    baseline_map: FrozenIdMapping
    candidate_map: FrozenIdMapping
    frozen_head: str
    run_id: str
    read_alias: str
    online_index: str
    online_uuid: str
    online_mapping_sha256: str
    online_alias_sha256: str
    mapping_versions: tuple[str, str]


@dataclass(frozen=True, slots=True)
class StartupInputs:
    run_id: str
    frozen_head: str
    identities: tuple[ArmIdentity, ArmIdentity]
    profile_snapshots: tuple[tuple[str, tuple[tuple[str, str], ...]], ...]
    read_alias: str
    online_index: str
    online_uuid: str
    online_mapping_sha256: str
    online_alias_sha256: str
    source_hashes: dict[str, str]
    config_hashes: dict[str, str]
    input_sha256: str = ""


def prepare_startup_inputs(run_directory: Path) -> StartupInputs:
    """Freeze a new startup-only run from one immutable, successful Git bundle."""
    directory = run_directory.resolve()
    if (not directory.is_dir() or directory.parent != _STARTUP_EVIDENCE_ROOT.resolve()
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]{4,95}", directory.name)
            or any(directory.iterdir())
            or _git("branch", "--show-current") != "codex_0915"
            or _git("status", "--porcelain", "--untracked-files=no")
            or _git("status", "--porcelain", "--untracked-files=all", "--", *_EXECUTION_SOURCES)):
        raise BLocalRunError("startup_preflight_invalid")
    head = _git("rev-parse", "HEAD")
    if re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise BLocalRunError("startup_preflight_invalid")
    try:
        _git("merge-base", "--is-ancestor", _STARTUP_SOURCE_COMMIT, head)
        source_raw = {}
        for name in _STARTUP_SOURCE_FILES:
            path = f"{_STARTUP_SOURCE_PATH}/{name}"
            original = _git_bytes("show", f"{_STARTUP_SOURCE_COMMIT}:{path}")
            if (not original or len(original) > 16 * 1024 * 1024
                    or _git_bytes("show", f"{head}:{path}") != original):
                raise BLocalRunError("startup_source_invalid")
            source_raw[name] = original
        hashes = {name: sha256(raw).hexdigest() for name, raw in source_raw.items()}
        plan, binding, result, attempt, intent, final, source_scan, candidate_scan = (
            _object(source_raw[name]) for name in _STARTUP_SOURCE_FILES[:8])
        spec = binding["spec"]
        source = intent["source"]
        candidate = final["candidateIdentity"]
        old_run_id = _STARTUP_SOURCE_PATH.rsplit("/", 1)[-1]
        if (any(value.get("runId") != old_run_id for value in (plan, binding, result))
                or plan["frozenHead"] != binding["frozenHead"]
                or hashes["scan-plan.json"] != binding["scanPlanSha256"]
                or hashes["binding.json"] != result["bindingSha256"]
                or hashes["binding.json"] != attempt["bindingSha256"]
                or hashes["binding.json"] != final["bindingSha256"]
                or hashes["result.json"] != final["builderResultSha256"]
                or any(value["assessmentIntentSha256"] != hashes["assessment-intent.json"]
                       for value in (plan, binding, result, attempt, final, source_scan, candidate_scan))
                or hashes["source-mapping-scan-result.json"] != binding["sourceMapScanResultSha256"]
                or hashes["source-mapping-scan-result.json"] != final["sourceMapScanResultSha256"]
                or hashes["candidate-mapping-scan-result.json"] != final["candidateMapScanResultSha256"]
                or hashes["source-id-mapping.json"] != final["sourceIdMappingSha256"]
                or hashes["candidate-id-mapping.json"] != final["candidateIdMappingSha256"]
                or source_scan["sha256"] != hashes["source-id-mapping.json"]
                or candidate_scan["sha256"] != hashes["candidate-id-mapping.json"]
                or source_scan["status"] != "scanned_read_only"
                or candidate_scan["status"] != "scanned_read_only"
                or result["status"] != "built_read_only_unpublished"
                or attempt["runId"] != old_run_id
                or attempt["status"] != "consumed"
                or attempt["executionKind"] != "local"
                or result["executionKind"] != "local"
                or attempt["retry"] != 0 or attempt["resume"] != 0
                or result["sourceVerifiedByBuilder"] is not True
                or result["onlineAliasWrites"] != 0
                or not (source["indexName"] == plan["sourceIndex"] == spec["source_index"])
                or not (source["indexUuid"] == plan["sourceUuid"] == spec["source_uuid"])
                or source["mappingSha256"] != plan["sourceMappingSha256"]
                or source["mappingSha256"] != spec["source_mapping_sha256"]
                or not (source["recordCount"] == plan["sourceCount"] == spec["source_count"])
                or source["sourceFingerprint"] != plan["sourceFingerprint"]
                or source["sourceFingerprint"] != spec["source_fingerprint"]
                or source_scan["indexName"] != source["indexName"]
                or source_scan["indexUuid"] != source["indexUuid"]
                or source_scan["recordCount"] != source["recordCount"]
                or source_scan["sourceFingerprint"] != source["sourceFingerprint"]
                or candidate["indexName"] != plan["candidateIndex"]
                or candidate["indexName"] != spec["candidate_index"]
                or candidate["indexName"] != result["candidateIndex"]
                or candidate["indexUuid"] != result["candidateUuid"]
                or candidate["mappingSha256"] != plan["candidateMappingSha256"]
                or candidate["mappingSha256"] != spec["target_mapping_sha256"]
                or candidate["recordCount"] != result["candidateCount"]
                or candidate["sourceFingerprint"] != result["candidateFingerprint"]
                or candidate_scan["indexName"] != candidate["indexName"]
                or candidate_scan["indexUuid"] != candidate["indexUuid"]
                or candidate_scan["recordCount"] != candidate["recordCount"]
                or candidate_scan["sourceFingerprint"] != candidate["sourceFingerprint"]
                or candidate_scan["mappingVersion"] != spec["target_mapping_version"]
                or candidate["recordCount"] != source["recordCount"]
                or spec["online_index"] != source["indexName"]
                or spec["online_uuid"] != source["indexUuid"]
                or spec["online_mapping_sha256"] != source["mappingSha256"]):
            raise BLocalRunError("startup_source_invalid")
        profiles = intent["profileParameters"]
        if (type(profiles) is not dict or set(profiles) != set(_PROFILE_IDS)
                or any(profiles[domain]["profileId"] != profile_id
                       or profiles[domain]["profileVersion"] != _PROFILE_VERSION
                       or profiles[domain]["readPolicyVersion"] != _READ_POLICY_VERSION
                       or profiles[domain]["baselineMappingVersion"] != source_scan["mappingVersion"]
                       or profiles[domain]["candidateMappingVersion"] != candidate_scan["mappingVersion"]
                       for domain, profile_id in _PROFILE_IDS.items())):
            raise BLocalRunError("startup_source_invalid")
        snapshots = (intent["baselineProfileSnapshots"], final["candidateProfileSnapshots"])
        if any(type(item) is not dict or set(item) != set(_PROFILE_IDS)
               or any(type(item[domain]) is not str or _HASH.fullmatch(item[domain]) is None
                      for domain in _PROFILE_IDS) for item in snapshots):
            raise BLocalRunError("startup_source_invalid")
        identities = (
            ArmIdentity("baseline", source["indexName"], source["indexUuid"],
                source["mappingSha256"], source_scan["mappingVersion"],
                f"b-{directory.name}-{secrets.token_hex(8)}-read"),
            ArmIdentity("candidate", candidate["indexName"], candidate["indexUuid"],
                candidate["mappingSha256"], candidate_scan["mappingVersion"],
                f"b-{directory.name}-{secrets.token_hex(8)}-read"),
        )
        config_hashes = {domain: _expected_profile_config_sha256(head, domain)
                         for domain in _PROFILE_IDS}
        runtime_hashes = _frozen_runtime_config_hashes(head)
        inputs = StartupInputs(directory.name, head, identities,
            tuple((arm, tuple((domain, values[domain]) for domain in _PROFILE_IDS))
                  for arm, values in zip(("baseline", "candidate"), snapshots, strict=True)),
            spec["read_alias"], spec["online_index"], spec["online_uuid"],
            spec["online_mapping_sha256"], spec["alias_snapshot_sha256"],
            hashes, config_hashes)
    except (BLocalRunError, BLocalTransportError, KeyError, TypeError, ValueError):
        raise BLocalRunError("startup_source_invalid") from None
    startup_input = {
        "schemaVersion": 1, "runId": inputs.run_id, "frozenHead": inputs.frozen_head,
        "sourceBundleCommit": _STARTUP_SOURCE_COMMIT,
        "sourceBundlePath": _STARTUP_SOURCE_PATH, "sourceBundleSha256": hashes,
        "arms": [asdict(identity) for identity in inputs.identities],
        "profileSnapshots": {arm: dict(values) for arm, values in inputs.profile_snapshots},
        "profileConfigSha256": config_hashes, "runtimeConfigSha256": runtime_hashes,
        "online": {"readAlias": inputs.read_alias, "indexName": inputs.online_index,
                   "indexUuid": inputs.online_uuid,
                   "mappingSha256": inputs.online_mapping_sha256,
                   "aliasSha256": inputs.online_alias_sha256},
        "budget": _STARTUP_BUDGET,
    }
    raw = _canonical(startup_input)
    _write_bytes_once(directory / "startup-input.json", raw)
    return replace(inputs, input_sha256=sha256(raw).hexdigest())


def load_frozen_inputs(run_directory: Path) -> FrozenInputs:
    """No network; reject altered fixture, code, maps or reused run evidence."""
    directory = run_directory.resolve()
    if (not directory.is_dir() or any((directory / name).exists() for name in _OUTPUT_FILES)
            or _git("branch", "--show-current") != "codex_0915"):
        raise BLocalRunError("run_preflight_invalid")
    if (directory / "reuse-intent.json").exists():
        if directory.parent != _STARTUP_EVIDENCE_ROOT.resolve():
            raise BLocalRunError("run_preflight_invalid")
        return _load_reuse_inputs(directory)
    intent_raw = _read(directory / "assessment-intent.json")
    final_raw = _read(directory / "assessment-final.json")
    fixture_path = ROOT / "agent-runtime/tests/uat/knowledge_rebuild_measure.v1.json"
    fixture_raw = _read(fixture_path)
    sidecars = {name: _read(directory / filename) for name, filename in _SIDECARS.items()}
    source_raw = _read(directory / "source-id-mapping.json", 16 * 1024 * 1024)
    candidate_raw = _read(directory / "candidate-id-mapping.json", 16 * 1024 * 1024)
    intent = _object(intent_raw)
    final = _object(final_raw)
    binding = _object(sidecars["binding"])
    scan_plan = _object(sidecars["scanPlan"])
    frozen_head = scan_plan.get("frozenHead")
    if (type(frozen_head) is not str or not re.fullmatch(r"[0-9a-f]{40}", frozen_head)
            or _git("rev-parse", "HEAD") != frozen_head
            or _git("status", "--porcelain", "--untracked-files=no")
            or _git("status", "--porcelain", "--untracked-files=all", "--", *_EXECUTION_SOURCES)
            or _git_bytes("show", f"{frozen_head}:agent-runtime/tests/uat/knowledge_rebuild_measure.v1.json")
                != fixture_raw):
        raise BLocalRunError("frozen_code_or_fixture_drift")
    if (type(intent.get("cases")) is not list
            or tuple(item.get("caseId") for item in intent["cases"])
               != tuple(f"UAT-KM-{number:03d}" for number in (1, 2, 3, 5, 6, 7, 8, 9, 11, 12))
            or intent.get("comparisonBudget") != {"typedSearch": 44, "queryEmbedding": 10,
                "rerank": 22, "aliasWrites": 4, "metadataEsHttp": 30,
                "paid": 0, "retry": 0, "resume": 0}):
        raise BLocalRunError("budget_or_case_drift")
    _validate_profile_parameters(frozen_head, intent.get("profileParameters"))
    plans = {item["caseId"]: _plan(item["plan"]) for item in intent["cases"]}
    spec = ComparisonSpec.from_assessment_bytes(final_raw,
        expected_sha256=sha256(final_raw).hexdigest(), intent_raw=intent_raw,
        expected_intent_sha256=sha256(intent_raw).hexdigest(),
        uat_fixture_raw=fixture_raw, authoritative_fixture_sha256=sha256(fixture_raw).hexdigest(),
        plans=plans)
    baseline_map = FrozenIdMapping.from_bytes(source_raw,
        expected_sha256=final["sourceIdMappingSha256"])
    candidate_map = FrozenIdMapping.from_bytes(candidate_raw,
        expected_sha256=final["candidateIdMappingSha256"])
    candidate = binding["spec"]
    if (baseline_map.index_name != spec.source_corpus.index_name
            or candidate_map.index_name != spec.candidate_corpus.index_name
            or baseline_map.source_fingerprint != spec.source_corpus.full_fingerprint
            or candidate_map.source_fingerprint != spec.candidate_corpus.full_fingerprint
            or scan_plan.get("runId") != directory.name
            or binding.get("runId") != directory.name):
        raise BLocalRunError("source_pool_confounded")
    return FrozenInputs(spec, sidecars, baseline_map, candidate_map, frozen_head,
        directory.name, candidate["read_alias"], candidate["online_index"],
        candidate["online_uuid"], candidate["online_mapping_sha256"],
        candidate["alias_snapshot_sha256"],
        (intent["profileParameters"]["tax.policy"]["baselineMappingVersion"],
         intent["profileParameters"]["tax.policy"]["candidateMappingVersion"]))


def _load_reuse_inputs(directory: Path) -> FrozenInputs:
    """No network: validate the new freeze and fresh scans before alias writes."""
    sidecars = {"reuseIntent": _read(directory / "reuse-intent.json"),
        "reuseFinal": _read(directory / "reuse-final.json"),
        "sourceScanResult": _read(directory / "source-scan-result.json"),
        "candidateScanResult": _read(directory / "candidate-scan-result.json"),
        "reuseAttempt": _read(directory / "reuse-scan-attempt.json"),
        "reuseTerminal": _read(directory / "reuse-scan-terminal.json")}
    intent = _object(sidecars["reuseIntent"])
    head = intent.get("frozenHead")
    if (type(head) is not str or re.fullmatch(r"[0-9a-f]{40}", head) is None
            or intent.get("runId") != directory.name
            or _git("rev-parse", "HEAD") != head
            or _git("status", "--porcelain", "--untracked-files=no")
            or _git("status", "--porcelain", "--untracked-files=all", "--", *_EXECUTION_SOURCES)):
        raise BLocalRunError("frozen_code_or_fixture_drift")
    try:
        old = reuse.load_old_build()
        _validate_profile_parameters(head, intent.get("profileParameters"))
        expected_intent = reuse.freeze_new_reuse_input(old=old, run_id=directory.name,
            frozen_head=head, profile_parameters=intent["profileParameters"],
            config_raw=_git_bytes("show", f"{head}:{reuse.CONFIG_PATH}"),
            fixture_raw=_read(ROOT / reuse.FIXTURE_PATH))
        if expected_intent != sidecars["reuseIntent"]:
            raise reuse.ReuseBindingError()
        source_raw = _read(directory / "source-id-mapping.json", 16 * 1024 * 1024)
        candidate_raw = _read(directory / "candidate-id-mapping.json", 16 * 1024 * 1024)
        maps = tuple(FrozenIdMapping.from_bytes(raw, expected_sha256=sha256(raw).hexdigest())
                     for raw in (source_raw, candidate_raw))
        params = intent["profileParameters"]["tax.policy"]
        versions = (params["baselineMappingVersion"], params["candidateMappingVersion"])
        for arm, raw, original, mapping, version in zip(
                ("source", "candidate"), (source_raw, candidate_raw),
                (old.source_map, old.candidate_map), maps, versions, strict=True):
            if mapping != original:
                raise reuse.ReuseBindingError()
            expected_receipt = reuse.scan_receipt(arm=arm, intent_raw=expected_intent,
                map_raw=raw, es_http=64, mapping_version=version, execution_kind="local")
            if sidecars[f"{arm}ScanResult"] != expected_receipt:
                raise reuse.ReuseBindingError()
        final = reuse.finalize_reuse_scans(intent_raw=expected_intent,
            source_scan_raw=sidecars["sourceScanResult"],
            candidate_scan_raw=sidecars["candidateScanResult"],
            source_map_raw=source_raw, candidate_map_raw=candidate_raw)
        if final != sidecars["reuseFinal"]:
            raise reuse.ReuseBindingError()
        reuse.verify_reuse_scan_execution(intent_raw=expected_intent, final_raw=final,
            attempt_raw=sidecars["reuseAttempt"], terminal_raw=sidecars["reuseTerminal"])
        spec = reuse.spec_for_reuse(old, intent_raw=expected_intent, final_raw=final)
        prior = _object(dict(old.blobs)["binding.json"])["spec"]
        return FrozenInputs(spec, sidecars, maps[0], maps[1], head, directory.name,
            prior["read_alias"], prior["online_index"], prior["online_uuid"],
            prior["online_mapping_sha256"], prior["alias_snapshot_sha256"], versions)
    except (reuse.ReuseBindingError, ComparisonRunError, KeyError, TypeError, ValueError):
        raise BLocalRunError("reuse_provenance_invalid") from None


def prepare_reuse_inputs(directory: Path) -> dict[str, object]:
    """Bind the existing immutable candidate to one new read-only comparison."""
    directory = directory.resolve()
    if (directory.parent != _STARTUP_EVIDENCE_ROOT.resolve() or directory.exists()
            or _git("branch", "--show-current") != "codex_0915"
            or _git("status", "--porcelain", "--untracked-files=no")
            or _git("status", "--porcelain", "--untracked-files=all", "--", *_EXECUTION_SOURCES)):
        raise BLocalRunError("reuse_preflight_invalid")
    head = _git("rev-parse", "HEAD")
    old = reuse.load_old_build()
    profiles = _object(old.spec.intent_raw)["profileParameters"]
    parameters = {domain: {**profiles[domain],
        "configSha256": _expected_profile_config_sha256(head, domain)} for domain in _PROFILE_IDS}
    _validate_profile_parameters(head, parameters)
    raw = reuse.freeze_new_reuse_input(old=old, run_id=directory.name, frozen_head=head,
        profile_parameters=parameters, config_raw=_git_bytes("show", f"{head}:{reuse.CONFIG_PATH}"),
        fixture_raw=_read(ROOT / reuse.FIXTURE_PATH))
    reuse.create_reuse_run(directory, raw)
    attempts: dict[str, int] = {"source": 0, "candidate": 0}

    def scan(arm: str, corpus: Any, maximum: int) -> reuse.ScanOutcome:
        if arm not in ("source", "candidate") or maximum != 64 or attempts[arm] != 0:
            raise BLocalRunError("reuse_scan_scope_invalid")
        python = ROOT / "knowledge-corpus-tools/.venv/Scripts/python.exe"
        environment = {key: os.environ[key] for key in (
            "PATH", "SystemRoot", "SystemDrive", "TEMP", "TMP",
            "USERPROFILE", "APPDATA", "LOCALAPPDATA") if key in os.environ}
        environment["PYTHONPATH"] = str(ROOT / "knowledge-corpus-tools/src")
        attempts[arm] = -1
        try:
            output = subprocess.run([str(python), str(Path(__file__).with_name(
                "rebuild_b_mapping_worker.py"))], cwd=ROOT, env=environment,
                input=_canonical({"indexName": corpus.index_name, "indexUuid": corpus.index_uuid,
                    "mappingSha256": corpus.mapping_sha256,
                    "sourceFingerprint": corpus.full_fingerprint,
                    "recordCount": corpus.record_count, "maxEsHttp": maximum}),
                capture_output=True, timeout=600, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            envelope = _object(output.stdout) if len(output.stdout) <= 16 * 1024 * 1024 else {}
            count = envelope.get("esHttp")
            attempts[arm] = count if type(count) is int and 0 <= count <= 64 else -1
            if (set(envelope) != {"status", "reason", "esHttp", "rawBase64", "mappingVersion"}
                    or envelope.get("status") != "scanned_read_only" or output.returncode != 0
                    or attempts[arm] != 64 or envelope.get("reason") is not None
                    or type(envelope.get("rawBase64")) is not str
                    or type(envelope.get("mappingVersion")) is not str):
                raise BLocalRunError("reuse_scan_failed")
            map_raw = base64.b64decode(envelope["rawBase64"], validate=True)
            return reuse.ScanOutcome(map_raw, attempts[arm], envelope["mappingVersion"])
        except (OSError, subprocess.TimeoutExpired, ValueError):
            attempts[arm] = -1
            raise BLocalRunError("reuse_scan_count_unavailable") from None

    reuse.execute_reuse_scans(directory, scan_arm=scan,
        observed_calls=lambda arm: attempts[arm])
    return {"runId": directory.name, "status": "reuse_scanned", "paid": 0,
        "sourceEsHttp": attempts["source"], "candidateEsHttp": attempts["candidate"]}


def _hash_file(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as stream:
            while part := stream.read(1024 * 1024):
                digest.update(part)
    except OSError:
        raise BLocalRunError("java_artifact_missing") from None
    return digest.hexdigest()


def _bounded_model_process(command: list[str], *, payload: bytes = b"",
                           timeout: int = 300,
                           corpus_python: bool = False) -> bytes:
    """Finite Docker/worker stdout; no credential or provider environment."""
    environment = {key: os.environ[key] for key in (
        "PATH", "SystemRoot", "SystemDrive", "TEMP", "TMP",
        "USERPROFILE", "APPDATA", "LOCALAPPDATA") if key in os.environ}
    if corpus_python:
        environment["PYTHONPATH"] = str(ROOT / "knowledge-corpus-tools/src")
    try:
        with tempfile.TemporaryFile() as output:
            result = subprocess.run(command, input=payload, stdout=output,
                stderr=subprocess.DEVNULL, cwd=ROOT, env=environment,
                timeout=timeout, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            size = output.tell()
            if result.returncode != 0 or not 0 < size <= 32768:
                raise BLocalRunError("model_identity_invalid")
            output.seek(0)
            return output.read()
    except (OSError, subprocess.TimeoutExpired, ValueError):
        raise BLocalRunError("model_identity_invalid") from None


def _rerank_container_id() -> str:
    listed = _bounded_model_process(["docker", "ps", "--filter", "publish=8909",
        "--format", "{{.ID}}"], timeout=15).decode("ascii").splitlines()
    if len(listed) != 1 or re.fullmatch(r"[a-f0-9]{12,64}", listed[0]) is None:
        raise BLocalRunError("model_identity_invalid")
    full = _bounded_model_process(["docker", "inspect", "--format", "{{.Id}}",
                                   listed[0]], timeout=15).decode("ascii").strip()
    if re.fullmatch(r"[a-f0-9]{64}", full) is None:
        raise BLocalRunError("model_identity_invalid")
    return full


def _capture_model_identity(inputs: FrozenInputs) -> dict[str, object]:
    """Freeze existing BGE bytes and current rerank bytes without inference."""
    try:
        binding_raw = (dict(reuse.load_old_build().blobs)["binding.json"]
                       if "reuseIntent" in inputs.sidecars else inputs.sidecars["binding"])
        binding = _object(binding_raw)["spec"]
        old = binding["model_snapshot"]
        old_container = old["container"]
        embedding_id = old_container["id"]
        old_model_sha = sha256(_canonical(old["model"])).hexdigest()
        if (type(embedding_id) is not str
                or re.fullmatch(r"[a-f0-9]{64}", embedding_id) is None
                or binding["model_snapshot_sha256"] != sha256(_canonical(old)).hexdigest()):
            raise BLocalRunError("model_identity_invalid")
        rerank_id = _rerank_container_id()
        python = (ROOT / "knowledge-corpus-tools/.venv/Scripts/python.exe").resolve()
        if (not python.is_file()
                or not python.is_relative_to((ROOT / "knowledge-corpus-tools/.venv").resolve())):
            raise BLocalRunError("model_identity_invalid")
        raw = _bounded_model_process([str(python), "-m",
            "knowledge_corpus_tools.b_model_identity_v1"],
            payload=_canonical({"embeddingContainerId": embedding_id,
                "rerankContainerId": rerank_id,
                "expectedEmbeddingModelSha256": old_model_sha}),
            corpus_python=True)
        current = _object(raw)
        if (set(current) != {"schemaVersion", "embedding", "rerank", "sha256"}
                or current["schemaVersion"] != 1
                or type(current["sha256"]) is not str
                or current["sha256"] != sha256(_canonical({
                    "embedding": current["embedding"],
                    "rerank": current["rerank"]})).hexdigest()
                or current["embedding"]["model"] != old["model"]
                or current["embedding"]["container"]["id"] != embedding_id
                or current["rerank"]["container"]["id"] != rerank_id
                or {key: value for key, value in current["embedding"]["container"].items()
                    if key != "started"}
                   != {key: value for key, value in old_container.items() if key != "started"}):
            raise BLocalRunError("model_identity_invalid")
        return current
    except (KeyError, TypeError, ValueError, UnicodeError, ComparisonRunError):
        raise BLocalRunError("model_identity_invalid") from None


class _PreparationTransport(httpx.HTTPTransport):
    """Second, network-level ceiling around the scoped source reader."""

    def __init__(self, *, index: str, alias: str) -> None:
        if (type(index) is not str or type(alias) is not str
                or re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", index) is None
                or re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", alias) is None
                or ".." in index or ".." in alias):
            raise BLocalRunError("preparation_scope_invalid")
        super().__init__(retries=0, trust_env=False)
        self.allowed = {("GET", f"/{index}"), ("GET", f"/_alias/{alias}"),
                        ("POST", f"/{index}/_search")}
        self.calls = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if (request.url.scheme != "http" or request.url.host != "127.0.0.1"
                or request.url.port != 9200
                or (request.method, request.url.path) not in self.allowed
                or self.calls >= 7):
            raise BLocalRunError("preparation_scope_invalid")
        self.calls += 1
        return super().handle_request(request)


def prepare_local_b_inputs(directory: Path, *, client: httpx.Client,
                           observed_calls: Callable[[], int],
                           preparer: Callable[..., Any] | None = None,
                           git_state_factory: Callable[[str], GitState] | None = None
                           ) -> dict[str, object]:
    """One scoped source preflight; no builder, BGE or model call occurs here."""
    # The corpus package has its own project venv, so the local launcher uses
    # its frozen sibling source directly rather than installing a dependency.
    if preparer is None or git_state_factory is None:
        corpus_src = str(ROOT / "knowledge-corpus-tools/src")
        if corpus_src not in sys.path:
            sys.path.insert(0, corpus_src)
        from knowledge_corpus_tools.b_assessment_prepare_v1 import (
            prepare_b_intent_v1,
        )
        from knowledge_corpus_tools.b_candidate_freeze_v1 import GitState
        preparer = prepare_b_intent_v1
        git_state_factory = lambda head: GitState(branch="codex_0915", head=head,
                                                  tracked_clean=True)

    directory = directory.resolve()
    if (not directory.is_dir()
            or any((directory / name).exists() for name in _PREPARATION_OUTPUTS)
            or _git("branch", "--show-current") != "codex_0915"
            or _git("status", "--porcelain", "--untracked-files=no")
            or _git("status", "--porcelain", "--untracked-files=all", "--", *_EXECUTION_SOURCES)):
        raise BLocalRunError("preparation_preflight_invalid")
    raw = _read(directory / "preparation.json")
    selection = _read(directory / "selection.json")
    fixture = _read(ROOT / "agent-runtime/tests/uat/knowledge_rebuild_measure.v1.json")
    manifest = _read(_PREPARATION_MANIFEST, 16 * 1024 * 1024)
    preparation = _object(raw)
    head = _git("rev-parse", "HEAD")
    if (preparation.get("runId") != directory.name
            or preparation.get("frozenHead") != head
            or preparation.get("comparisonMetadataEsHttp") != 30
            or _git_bytes("show", f"{head}:agent-runtime/tests/uat/knowledge_rebuild_measure.v1.json")
               != fixture):
        raise BLocalRunError("preparation_preflight_invalid")
    _validate_profile_parameters(head, preparation.get("profileParameters"))
    _write_once(directory / "comparison-preparation-attempt.json", {
        "schemaVersion": 1, "runId": directory.name, "frozenHead": head,
        "preparationSha256": sha256(raw).hexdigest(),
        "selectionSha256": sha256(selection).hexdigest(),
        "manifestSha256": sha256(manifest).hexdigest(),
        "fixtureSha256": sha256(fixture).hexdigest(),
        "budget": {"sourceEsHttp": 7, "comparisonMetadataEsHttp": 30,
                   "paid": 0, "retry": 0, "resume": 0},
    })
    reason: str | None = None
    prepared: Any = None
    try:
        prepared = preparer(client=client, fixture_raw=fixture,
            selection_raw=selection, asset_manifest_raw=manifest,
            preparation_raw=raw,
            git_state=git_state_factory(head))
        if prepared.scoped_es_http != 7 or prepared.scoped_es_http_max != 7:
            raise BLocalRunError("preparation_budget_drift")
        _write_bytes_once(directory / "assessment-intent.json", prepared.intent_raw)
        _write_bytes_once(directory / "preliminary-request.json", prepared.preliminary_raw)
    except Exception as exc:
        finite_reason = getattr(exc, "reason", None)
        reason = finite_reason if finite_reason in {
            "input_invalid", "source_drift", "source_record_invalid",
            "budget_exhausted", "http_failed", "binding_invalid",
        } else "preparation_unexpected_failure"
    calls = observed_calls()
    if type(calls) is not int or not 0 <= calls <= 7:
        reason = "preparation_budget_drift"
    terminal: dict[str, object] = {
        "schemaVersion": 1, "runId": directory.name,
        "status": "prepared" if reason is None else "not_prepared",
        "reason": reason, "sourceEsHttp": calls if type(calls) is int else -1,
        "paid": 0, "retry": 0, "resume": 0,
    }
    if reason is None and prepared is not None:
        terminal["assessmentIntentSha256"] = sha256(prepared.intent_raw).hexdigest()
        terminal["preliminaryRequestSha256"] = sha256(prepared.preliminary_raw).hexdigest()
    _write_once(directory / "comparison-preparation-result.json", terminal)
    return terminal


def bind_local_b_request(directory: Path, *, binder: Callable[..., bytes] | None = None
                         ) -> dict[str, object]:
    """Bind a completed full-source ID scan; never invent a placeholder hash."""
    if binder is None:
        corpus_src = str(ROOT / "knowledge-corpus-tools/src")
        if corpus_src not in sys.path:
            sys.path.insert(0, corpus_src)
        from knowledge_corpus_tools.b_assessment_prepare_v1 import (
            bind_b_request_v1,
        )
        binder = bind_b_request_v1
    directory = directory.resolve()
    if (not directory.is_dir()
            or any((directory / name).exists() for name in _BINDING_OUTPUTS)
            or _git("branch", "--show-current") != "codex_0915"
            or _git("status", "--porcelain", "--untracked-files=no")):
        raise BLocalRunError("source_binding_preflight_invalid")
    evidence = _object(_read(directory / "comparison-preparation-result.json"))
    preliminary = _read(directory / "preliminary-request.json")
    intent = _read(directory / "assessment-intent.json")
    source_map = _read(directory / "source-id-mapping.json", 16 * 1024 * 1024)
    preliminary_value = _object(preliminary)
    head = _git("rev-parse", "HEAD")
    if (evidence.get("status") != "prepared" or evidence.get("runId") != directory.name
            or evidence.get("preliminaryRequestSha256") != sha256(preliminary).hexdigest()
            or evidence.get("assessmentIntentSha256") != sha256(intent).hexdigest()
            or preliminary_value.get("runId") != directory.name
            or preliminary_value.get("frozenHead") != head
            or preliminary_value.get("assessmentIntentSha256") != sha256(intent).hexdigest()
            or evidence.get("sourceEsHttp") != 7):
        raise BLocalRunError("source_binding_preflight_invalid")
    try:
        request = binder(preliminary_raw=preliminary, source_id_mapping_raw=source_map)
    except Exception:
        raise BLocalRunError("source_binding_invalid") from None
    if type(request) is not bytes or not request.endswith(b"\n"):
        raise BLocalRunError("source_binding_invalid")
    _write_bytes_once(directory / "request.json", request)
    terminal: dict[str, object] = {"schemaVersion": 1, "runId": directory.name,
        "status": "source_bound", "requestSha256": sha256(request).hexdigest(),
        "sourceIdMappingSha256": sha256(source_map).hexdigest(),
        "paid": 0, "retry": 0, "resume": 0}
    _write_once(directory / "comparison-source-binding-result.json", terminal)
    return terminal


@contextmanager
def frozen_java_artifact(directory: Path, inputs: FrozenInputs | StartupInputs,
                         *, attestation_name: str = "comparison-java-attestation.json"
                         ) -> Iterator[tuple[Path, str]]:
    """Build the reactor from HEAD, not from a caller-supplied or locked JAR.

    The temporary archive excludes the active working tree and cannot overwrite
    target/ files used by other services. Maven runs offline; missing cached
    dependencies fail before a B attempt or any ES/BGE operation.
    """
    if (_git("rev-parse", "HEAD") != inputs.frozen_head
            or _git("status", "--porcelain", "--untracked-files=no")):
        raise BLocalRunError("frozen_code_or_fixture_drift")
    archive = _git_bytes("archive", "--format=zip", inputs.frozen_head)
    if not archive or len(archive) > 512 * 1024 * 1024:
        raise BLocalRunError("archive_invalid")
    archive_sha = sha256(archive).hexdigest()
    with tempfile.TemporaryDirectory(prefix="knowledge-b-frozen-build-") as temporary:
        build_root = Path(temporary).resolve()
        try:
            with ZipFile(BytesIO(archive)) as source:
                if sum(member.file_size for member in source.infolist()) > 1024 * 1024 * 1024:
                    raise BLocalRunError("archive_invalid")
                for member in source.infolist():
                    target = (build_root / member.filename).resolve()
                    if (not target.is_relative_to(build_root)
                            or member.file_size > 256 * 1024 * 1024):
                        raise BLocalRunError("archive_invalid")
                source.extractall(build_root)
        except (OSError, ValueError):
            raise BLocalRunError("archive_invalid") from None
        pom = build_root / "serviceCenter/pom.xml"
        jar = build_root / "es-query-service/target/es-query-service-0.0.1-SNAPSHOT.jar"
        maven = shutil.which("mvn")
        if not pom.is_file() or maven is None or not Path(maven).is_file():
            raise BLocalRunError("archive_invalid")
        _, runtime_config_hashes = _frozen_runtime_config_dir(jar, inputs.frozen_head)
        command = [maven, "--offline", "--batch-mode", "-f", str(pom),
                   "-pl", ":es-query-service", "-am", "-DskipTests", "package"]
        safe_env = {key: os.environ[key] for key in (
            "SystemRoot", "SystemDrive", "PATH", "JAVA_HOME", "TEMP", "TMP",
            "USERPROFILE", "APPDATA", "LOCALAPPDATA")
            if key in os.environ}
        try:
            built = subprocess.run(command, cwd=build_root / "serviceCenter",
                env=safe_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=900, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise BLocalRunError("frozen_java_build_failed") from None
        if built.returncode != 0 or not jar.is_file() or jar.stat().st_size <= 0:
            raise BLocalRunError("frozen_java_build_failed")
        jar_sha = _hash_file(jar)
        if attestation_name not in ("comparison-java-attestation.json",
                                    "startup-java-attestation.json"):
            raise BLocalRunError("java_artifact_invalid")
        _write_once(directory / attestation_name, {
            "schemaVersion": 1, "runId": inputs.run_id,
            "frozenHead": inputs.frozen_head, "archiveSha256": archive_sha,
            "mavenExecutableSha256": _hash_file(Path(maven)),
            "command": ["mvn", "--offline", "--batch-mode", "-f",
                        "serviceCenter/pom.xml", "-pl", ":es-query-service", "-am",
                        "-DskipTests", "package"],
            "artifactSha256": jar_sha, "artifactBytes": jar.stat().st_size,
            "buildExitCode": 0, "workingTreeTrackedClean": True,
            "runtimeConfigSha256": runtime_config_hashes,
        })
        yield jar, jar_sha


def _jwt(secret: bytes) -> str:
    def encoded(value: dict[str, object]) -> bytes:
        return base64.urlsafe_b64encode(json.dumps(value, ensure_ascii=False,
            separators=(",", ":")).encode()).rstrip(b"=")
    now = int(time.time())
    signed = encoded({"alg": "HS256", "kid": "ACTIVE"}) + b"." + encoded({
        "sub": "isolated-b-comparison", "iat": now, "exp": now + 1800,
        "token_type": "user", "role": ["VIEWER"],
    })
    return (signed + b"." + base64.urlsafe_b64encode(hmac.new(secret, signed,
        sha256).digest()).rstrip(b"=")).decode("ascii")


def _java_args(*, jar: Path, config_dir: Path, port: int, proxy_port: int,
               identity: ArmIdentity, run_id: str, policy_snapshot: str,
               law_snapshot: str) -> list[str]:
    config_location = (config_dir.as_uri().rstrip("/") + "/" if config_dir.is_absolute()
                       else "file:" + config_dir.as_posix().rstrip("/") + "/")
    return ["java", "-jar", str(jar), f"--server.port={port}", "--server.address=127.0.0.1",
        "--spring.profiles.active=datasource,es,knowledge-live,knowledge-b-isolation",
        "--spring.cloud.config.enabled=false", "--spring.cloud.discovery.enabled=false",
        "--eureka.client.enabled=false",
        f"--spring.config.additional-location={config_location}",
        "--management.endpoint.health.probes.enabled=true",
        "--management.endpoint.health.group.knowledge-validation.include=readinessState",
        f"--spring.elasticsearch.uris=http://127.0.0.1:{proxy_port}",
        "--common.security.secrets.source-order[0]=environment",
        "--common.security.secrets.allow-config-values=false",
        "--common.security.secrets.fail-fast=true",
        "--common.security.secrets.jwt.active-key-id=ACTIVE",
        "--common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE",
        "--common.security.secrets.jwt.keys.ACTIVE.value=",
        "--es.query.knowledge.b-isolation-fixed-target=true",
        f"--es.query.knowledge.b-isolation-run-id={run_id}",
        f"--es.query.knowledge.profiles.tax-policy-v1.read-alias={identity.alias}",
        f"--es.query.knowledge.profiles.tax-law-v1.read-alias={identity.alias}",
        f"--es.query.knowledge.profiles.tax-policy-v1.expected-index-name={identity.index_name}",
        f"--es.query.knowledge.profiles.tax-law-v1.expected-index-name={identity.index_name}",
        f"--es.query.knowledge.profiles.tax-policy-v1.expected-index-uuid={identity.index_uuid}",
        f"--es.query.knowledge.profiles.tax-law-v1.expected-index-uuid={identity.index_uuid}",
        f"--es.query.knowledge.profiles.tax-policy-v1.mapping-version={identity.mapping_version}",
        f"--es.query.knowledge.profiles.tax-law-v1.mapping-version={identity.mapping_version}",
        f"--es.query.knowledge.profiles.tax-policy-v1.index-snapshot-id={policy_snapshot}",
        f"--es.query.knowledge.profiles.tax-law-v1.index-snapshot-id={law_snapshot}",
    ]


def _expected_profile_config_sha256(frozen_head: str, domain: str) -> str:
    """Bind one Profile to frozen YAML and the exact fixed-target launch template.

    Arm-specific alias/index/UUID/mapping/snapshot values are separately bound
    by the assessment, Java verifier and pre/post physical checks. The template
    uses fixed sentinel values so a caller cannot supply its own config hash.
    """
    if domain not in _PROFILE_IDS or re.fullmatch(r"[0-9a-f]{40}", frozen_head) is None:
        raise BLocalRunError("profile_config_drift")
    raw_config = _git_bytes("show", f"{frozen_head}:es-query-service/src/main/resources/application-knowledge-live.yml")
    if not raw_config:
        raise BLocalRunError("profile_config_drift")
    runtime_config_hashes = _frozen_runtime_config_hashes(frozen_head)
    sentinel = ArmIdentity("baseline", "frozen-index", "frozen-uuid", "0" * 64,
                           "frozen-mapping", "b-frozen-run-" + "a" * 16 + "-read")
    template = _java_args(jar=Path("frozen-es-query-service.jar"),
        config_dir=Path("frozen-config"), port=19211, proxy_port=19311,
        identity=sentinel, run_id="frozen-run",
        policy_snapshot="frozen-policy-snapshot", law_snapshot="frozen-law-snapshot")
    return sha256(_canonical({
        "schemaVersion": 1, "profileId": _PROFILE_IDS[domain],
        "profileVersion": _PROFILE_VERSION, "readPolicyVersion": _READ_POLICY_VERSION,
        "applicationKnowledgeLiveSha256": sha256(raw_config).hexdigest(),
        "runtimeConfigSha256": runtime_config_hashes,
        "javaLaunchTemplate": template,
        "javaEnvironmentKeys": ["AGENT_KNOWLEDGE_READ_ALIAS",
            "AGENT_KNOWLEDGE_EXPECTED_INDEX_NAME", "AGENT_KNOWLEDGE_EXPECTED_INDEX_UUID",
            "AGENT_KNOWLEDGE_MAPPING_VERSION", "AGENT_KNOWLEDGE_POLICY_SNAPSHOT_ID",
            "AGENT_KNOWLEDGE_LAW_SNAPSHOT_ID", "COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE"],
    })).hexdigest()


def _validate_profile_parameters(frozen_head: str, parameters: object) -> None:
    if type(parameters) is not dict or set(parameters) != set(_PROFILE_IDS):
        raise BLocalRunError("profile_config_drift")
    for domain, profile_id in _PROFILE_IDS.items():
        item = parameters.get(domain)
        if (type(item) is not dict or set(item) != {"profileId", "profileVersion",
                "readPolicyVersion", "baselineMappingVersion",
                "candidateMappingVersion", "configSha256"}
                or item["profileId"] != profile_id
                or item["profileVersion"] != _PROFILE_VERSION
                or item["readPolicyVersion"] != _READ_POLICY_VERSION
                or any(type(item[key]) is not str or not item[key]
                       for key in ("baselineMappingVersion", "candidateMappingVersion"))
                or item["configSha256"] != _expected_profile_config_sha256(frozen_head, domain)):
            raise BLocalRunError("profile_config_drift")


def _stop_owned(processes: list[subprocess.Popen[bytes]]) -> bool:
    for process in reversed(processes):
        try:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass
    return all(process.poll() is not None for process in processes)


def _ready(processes: list[subprocess.Popen[bytes]], ports: tuple[int, int],
           observed_calls: list[int] | None = None) -> None:
    with httpx.Client(trust_env=False, follow_redirects=False, timeout=2.0) as client:
        for ordinal, (process, port) in enumerate(zip(processes, ports, strict=True)):
            for _ in range(60):
                if process.poll() is not None:
                    raise BLocalRunError("java_exited")
                try:
                    if observed_calls is not None:
                        observed_calls[ordinal] += 1
                    response = client.get(f"http://127.0.0.1:{port}/actuator/health/knowledge-validation")
                    if response.status_code == 200 and _listener_owner(port) == process.pid:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.5)
            else:
                raise BLocalRunError("java_readiness_timeout")


def _port_guard(ports: tuple[int, int, int, int]) -> None:
    if len(set(ports)) != 4 or any(type(port) is not int or not 1025 <= port <= 65535
                                   or port in (9200, 9201, 8908, 8909) for port in ports):
        raise BLocalRunError("port_binding_invalid")
    for port in ports:
        with socket.socket() as check:
            try:
                check.bind(("127.0.0.1", port))
            except OSError:
                raise BLocalRunError("port_already_owned") from None


def _listener_owner(port: int) -> int:
    """Read Windows TCP owner table without a new dependency or shell process."""
    if os.name != "nt" or type(port) is not int or not 1 <= port <= 65535:
        raise BLocalRunError("listener_owner_unavailable")
    # GetExtendedTcpTable(AF_INET, TCP_TABLE_OWNER_PID_LISTENER).
    api = ctypes.windll.iphlpapi.GetExtendedTcpTable
    size = ctypes.c_ulong(0)
    api(None, ctypes.byref(size), False, socket.AF_INET, 3, 0)
    if not 4 <= size.value <= 1024 * 1024:
        raise BLocalRunError("listener_owner_unavailable")
    buffer = ctypes.create_string_buffer(size.value)
    if api(buffer, ctypes.byref(size), False, socket.AF_INET, 3, 0) != 0:
        raise BLocalRunError("listener_owner_unavailable")
    raw = buffer.raw[:size.value]
    count = struct.unpack_from("<I", raw, 0)[0]
    if count > (len(raw) - 4) // 24:
        raise BLocalRunError("listener_owner_unavailable")
    owners: list[int] = []
    for offset in range(4, 4 + count * 24, 24):
        state, local_address, local_port, _, _, pid = struct.unpack_from("<6I", raw, offset)
        if (state == 2 and socket.ntohs(local_port & 0xFFFF) == port
                and socket.inet_ntoa(struct.pack("<I", local_address)) == "127.0.0.1"):
            owners.append(pid)
    if len(owners) != 1 or owners[0] <= 0:
        raise BLocalRunError("listener_owner_mismatch")
    return owners[0]


class _OwnedSearch:
    """No JWT leaves the runner unless the destination Java PID is still owned."""

    def __init__(self, delegate: EsKnowledgeSearchAdapter, process: subprocess.Popen[bytes],
                 port: int) -> None:
        self.delegate = delegate
        self.process = process
        self.port = port

    async def search(self, *, request: KnowledgePathRequest,
                     context: KnowledgeRetrievalContext, timeout_s: float) -> PathRetrievalResult:
        if self.process.poll() is not None or _listener_owner(self.port) != self.process.pid:
            raise BLocalRunError("listener_owner_mismatch")
        return await self.delegate.search(request=request, context=context, timeout_s=timeout_s)


def _require_owned_listeners(processes: list[subprocess.Popen[bytes]],
                             ports: tuple[int, int]) -> None:
    if len(processes) != 2:
        raise BLocalRunError("listener_owner_mismatch")
    for process, port in zip(processes, ports, strict=True):
        if process.poll() is not None or _listener_owner(port) != process.pid:
            raise BLocalRunError("listener_owner_mismatch")


def execute_startup_preflight(*, directory: Path, inputs: StartupInputs,
        jar: Path, jar_sha256: str, ports: tuple[int, int],
        proxy_ports: tuple[int, int], es: httpx.Client) -> dict[str, object]:
    """Start both fixed-target Java arms without any typed or model request."""
    attestation = _object(_read(directory / "startup-java-attestation.json"))
    if (type(inputs.input_sha256) is not str
            or _HASH.fullmatch(inputs.input_sha256) is None
            or _hash_file(directory / "startup-input.json") != inputs.input_sha256
            or set(attestation) != {"schemaVersion", "runId", "frozenHead", "archiveSha256",
                                    "mavenExecutableSha256", "command", "artifactSha256",
                                    "artifactBytes", "buildExitCode", "workingTreeTrackedClean",
                                    "runtimeConfigSha256"}
            or attestation.get("schemaVersion") != 1
            or attestation.get("runId") != inputs.run_id
            or attestation.get("frozenHead") != inputs.frozen_head
            or type(attestation.get("archiveSha256")) is not str
            or _HASH.fullmatch(attestation["archiveSha256"]) is None
            or type(attestation.get("mavenExecutableSha256")) is not str
            or _HASH.fullmatch(attestation["mavenExecutableSha256"]) is None
            or attestation.get("command") != ["mvn", "--offline", "--batch-mode", "-f",
                "serviceCenter/pom.xml", "-pl", ":es-query-service", "-am",
                "-DskipTests", "package"]
            or attestation.get("artifactSha256") != jar_sha256
            or attestation.get("artifactBytes") != jar.stat().st_size
            or attestation.get("buildExitCode") != 0
            or attestation.get("workingTreeTrackedClean") is not True
            or attestation.get("runtimeConfigSha256") != _frozen_runtime_config_hashes(inputs.frozen_head)
            or _hash_file(jar) != jar_sha256):
        raise BLocalRunError("java_artifact_invalid")
    config_dir, config_hashes = _frozen_runtime_config_dir(jar, inputs.frozen_head)
    if attestation["runtimeConfigSha256"] != config_hashes:
        raise BLocalRunError("java_artifact_invalid")
    _port_guard((*ports, *proxy_ports))
    _write_once(directory / "startup-attempt.json", {
        "schemaVersion": 1, "runId": inputs.run_id, "frozenHead": inputs.frozen_head,
        "startupInputSha256": inputs.input_sha256,
        "javaArtifactSha256": jar_sha256,
        "aliases": [identity.alias for identity in inputs.identities],
        "budget": _STARTUP_BUDGET,
    })
    lease: BIsolatedAliases | None = None
    proxies: list[PhysicalEsProxy] = []
    processes: list[subprocess.Popen[bytes]] = []
    readiness_calls = [0, 0]
    stage = "alias_open"
    reason: str | None = None
    aliases_removed = False
    stopped = False
    pre_snapshots: tuple[tuple[str, str], ...] | None = None
    post_snapshots: tuple[tuple[str, str], ...] | None = None
    try:
        lease = BIsolatedAliases(client=es, baseline=inputs.identities[0],
            candidate=inputs.identities[1], online_alias=inputs.read_alias,
            online_index=inputs.online_index, online_uuid=inputs.online_uuid,
            online_mapping_sha256=inputs.online_mapping_sha256,
            online_alias_sha256=inputs.online_alias_sha256,
            mapping_fingerprint=lambda value: sha256(_canonical(value)).hexdigest(),
            metadata_budget=18)
        pre_snapshots = lease.open()
        stage = "proxy_start"
        for identity, proxy_port in zip(inputs.identities, proxy_ports, strict=True):
            proxy = PhysicalEsProxy(identity=identity, port=proxy_port,
                maximum_metadata=6, maximum_search=0, backend=es)
            proxies.append(proxy)
            proxy.start()
        env = {key: os.environ[key] for key in (
            "SystemRoot", "SystemDrive", "PATH", "JAVA_HOME", "TEMP", "TMP",
            "USERPROFILE", "APPDATA", "LOCALAPPDATA") if key in os.environ}
        env["COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE"] = base64.b64encode(secrets.token_bytes(48)).decode()
        profiles = dict(inputs.profile_snapshots)
        stage = "java_start"
        for identity, port, proxy_port in zip(inputs.identities, ports, proxy_ports, strict=True):
            arm_profiles = dict(profiles[identity.arm])
            env_arm = dict(env)
            env_arm.update({
                "AGENT_KNOWLEDGE_READ_ALIAS": identity.alias,
                "AGENT_KNOWLEDGE_EXPECTED_INDEX_NAME": identity.index_name,
                "AGENT_KNOWLEDGE_EXPECTED_INDEX_UUID": identity.index_uuid,
                "AGENT_KNOWLEDGE_MAPPING_VERSION": identity.mapping_version,
                "AGENT_KNOWLEDGE_POLICY_SNAPSHOT_ID": arm_profiles["tax.policy"],
                "AGENT_KNOWLEDGE_LAW_SNAPSHOT_ID": arm_profiles["tax.law"],
            })
            process = subprocess.Popen(_java_args(jar=jar, config_dir=config_dir,
                port=port, proxy_port=proxy_port, identity=identity,
                run_id=inputs.run_id, policy_snapshot=arm_profiles["tax.policy"],
                law_snapshot=arm_profiles["tax.law"]),
                cwd=ROOT / "es-query-service", env=env_arm,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            processes.append(process)
        stage = "java_readiness"
        _ready(processes, ports, readiness_calls)
        _require_owned_listeners(processes, ports)
        if any(proxy.metadata_count != 6 or proxy.violations
               or proxy.physical_search_paths for proxy in proxies):
            raise BLocalRunError("java_startup_provenance_invalid")
        stage = "postcheck"
        post_snapshots = lease.postcheck()
    except BLocalRunError as exc:
        reason = exc.reason if exc.reason in {
            "java_exited", "java_readiness_timeout", "listener_owner_mismatch",
            "java_startup_provenance_invalid"} else "startup_identity_failed"
    except BLocalTransportError:
        reason = "alias_or_proxy_failed"
    except Exception:
        reason = "startup_unexpected_failure"
    finally:
        stopped = _stop_owned(processes)
        for proxy in proxies:
            try:
                proxy.close()
            except Exception:
                reason = "proxy_cleanup_failed"
        if lease is not None:
            try:
                aliases_removed = lease.close()
            except Exception:
                reason = "alias_cleanup_failed"
        else:
            aliases_removed = True
    violations = sum(proxy.violations for proxy in proxies)
    metadata = (lease.metadata_calls if lease is not None else 0)
    metadata += sum(proxy.metadata_attempts for proxy in proxies)
    searches = sum(len(proxy.physical_search_paths) for proxy in proxies)
    if not stopped:
        reason = "owned_process_cleanup_failed"
    elif not aliases_removed:
        reason = "alias_cleanup_failed"
    elif violations or searches:
        reason = "proxy_operation_forbidden"
    try:
        artifact_unchanged = _hash_file(jar) == jar_sha256
    except BLocalRunError:
        artifact_unchanged = False
    if not artifact_unchanged and reason is None:
        reason = "java_artifact_drift"
    elif (reason is None and (pre_snapshots is None or post_snapshots != pre_snapshots
            or len(processes) != 2 or metadata != 30
            or lease is None or lease.alias_writes != 4
            or any(count < 1 or count > 60 for count in readiness_calls))):
        reason = "startup_provenance_incomplete"
    return {
        "schemaVersion": 1, "runId": inputs.run_id,
        "status": "ready" if reason is None else "not_ready",
        "phase": "complete" if reason is None else stage,
        "reason": reason, "exitCode": 0 if reason is None else 1,
        "startupInputSha256": inputs.input_sha256,
        "javaArtifactSha256": jar_sha256,
        "runtimeConfigSha256": config_hashes,
        "sourceBundleSha256": sha256(_canonical(inputs.source_hashes)).hexdigest(),
        "readinessCalls": dict(zip(("baseline", "candidate"), readiness_calls, strict=True)),
        "metadataEsHttp": metadata, "aliasWrites": lease.alias_writes if lease else 0,
        "physicalSearchCount": searches, "typedSearch": 0, "queryEmbedding": 0,
        "rerank": 0, "paid": 0, "jwtHttp": 0, "retry": 0, "resume": 0,
        "ownedPids": [process.pid for process in processes],
        "ownedProcessesStopped": stopped, "aliasesRemoved": aliases_removed,
        "proxyViolations": violations,
    }


def run_startup_preflight(directory: Path, *, ports: tuple[int, int],
                          proxy_ports: tuple[int, int]) -> dict[str, object]:
    """One independent append-only startup attempt; no comparison case is loaded."""
    directory = directory.resolve()
    if (not directory.is_dir() or directory.parent != _STARTUP_EVIDENCE_ROOT.resolve()
            or any(directory.iterdir())):
        raise BLocalRunError("startup_preflight_invalid")
    phase = "port_preflight"
    inputs: StartupInputs | None = None
    terminal: dict[str, object]
    try:
        _port_guard((*ports, *proxy_ports))
        phase = "source_binding"
        inputs = prepare_startup_inputs(directory)
        phase = "frozen_java_build"
        with frozen_java_artifact(directory, inputs,
                attestation_name="startup-java-attestation.json") as (jar, jar_sha):
            phase = "startup_execution"
            with httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False,
                    follow_redirects=False, timeout=10.0) as es:
                terminal = execute_startup_preflight(directory=directory, inputs=inputs,
                    jar=jar, jar_sha256=jar_sha, ports=ports, proxy_ports=proxy_ports, es=es)
    except BLocalRunError as exc:
        terminal = {"schemaVersion": 1, "runId": directory.name, "status": "not_ready",
            "phase": phase, "reason": exc.reason if exc.reason in {
                "startup_preflight_invalid", "startup_source_invalid", "git_state_invalid",
                "frozen_code_or_fixture_drift", "archive_invalid", "frozen_java_build_failed",
                "frozen_runtime_config_invalid", "java_artifact_invalid", "java_artifact_missing",
                "port_binding_invalid", "port_already_owned", "append_only_evidence_failed"}
                else "startup_preflight_failed", "exitCode": 1,
            "startupInputSha256": inputs.input_sha256 if inputs is not None else None,
            "metadataEsHttp": 0, "aliasWrites": 0, "physicalSearchCount": 0,
            "typedSearch": 0, "queryEmbedding": 0, "rerank": 0, "paid": 0,
            "jwtHttp": 0, "retry": 0, "resume": 0,
            "readinessCalls": {"baseline": 0, "candidate": 0},
            "ownedPids": [], "ownedProcessesStopped": True,
            "aliasesRemoved": True, "proxyViolations": 0}
    except Exception:
        terminal = {"schemaVersion": 1, "runId": directory.name, "status": "not_ready",
            "phase": phase, "reason": "startup_unexpected_failure", "exitCode": 1,
            "metadataEsHttp": 0, "aliasWrites": 0, "physicalSearchCount": 0,
            "typedSearch": 0, "queryEmbedding": 0, "rerank": 0, "paid": 0,
            "jwtHttp": 0, "retry": 0, "resume": 0,
            "readinessCalls": {"baseline": 0, "candidate": 0},
            "ownedPids": [], "ownedProcessesStopped": True,
            "aliasesRemoved": True, "proxyViolations": 0}
    _write_once(directory / "startup-result.json", terminal)
    return terminal


async def execute_local_comparison(*, directory: Path, inputs: FrozenInputs,
        jar: Path, jar_sha256: str, ports: tuple[int, int],
        proxy_ports: tuple[int, int]) -> dict[str, object]:
    """Consume exactly one B window; all results are IDs/hashes/counts only."""
    attestation = _object(_read(directory / "comparison-java-attestation.json"))
    if (set(attestation) != {"schemaVersion", "runId", "frozenHead", "archiveSha256",
                             "mavenExecutableSha256", "command", "artifactSha256",
                             "artifactBytes", "buildExitCode", "workingTreeTrackedClean",
                             "runtimeConfigSha256"}
            or attestation["schemaVersion"] != 1
            or attestation["runId"] != inputs.run_id
            or attestation["frozenHead"] != inputs.frozen_head
            or type(attestation["archiveSha256"]) is not str
            or _HASH.fullmatch(attestation["archiveSha256"]) is None
            or type(attestation["mavenExecutableSha256"]) is not str
            or _HASH.fullmatch(attestation["mavenExecutableSha256"]) is None
            or attestation["command"] != ["mvn", "--offline", "--batch-mode", "-f",
                "serviceCenter/pom.xml", "-pl", ":es-query-service", "-am",
                "-DskipTests", "package"]
            or attestation["artifactSha256"] != jar_sha256
            or attestation["buildExitCode"] != 0
            or attestation["workingTreeTrackedClean"] is not True
            or type(attestation["artifactBytes"]) is not int
            or attestation["artifactBytes"] != jar.stat().st_size
            or type(jar_sha256) is not str or _HASH.fullmatch(jar_sha256) is None
            or _hash_file(jar.resolve()) != jar_sha256 or shutil.which("java") is None):
        raise BLocalRunError("java_artifact_invalid")
    config_dir, runtime_config_hashes = _frozen_runtime_config_dir(jar, inputs.frozen_head)
    if attestation["runtimeConfigSha256"] != runtime_config_hashes:
        raise BLocalRunError("java_artifact_invalid")
    _port_guard((*ports, *proxy_ports))
    spec = inputs.spec
    profiles = dict(spec.profile_snapshots)
    identities = (
        ArmIdentity("baseline", spec.source_corpus.index_name,
            spec.source_corpus.index_uuid, spec.source_corpus.mapping_sha256,
            inputs.mapping_versions[0], f"b-{inputs.run_id}-{secrets.token_hex(8)}-read"),
        ArmIdentity("candidate", spec.candidate_corpus.index_name,
            spec.candidate_corpus.index_uuid, spec.candidate_corpus.mapping_sha256,
            inputs.mapping_versions[1], f"b-{inputs.run_id}-{secrets.token_hex(8)}-read"),
    )
    secret = secrets.token_bytes(48)
    token = _jwt(secret)
    token_for_context = OpaqueUserToken.from_raw(token)
    _write_once(directory / "comparison-attempt.json", {
        "schemaVersion": 1, "status": "consumed", "runId": inputs.run_id,
        "frozenHead": inputs.frozen_head, "assessmentSha256": spec.assessment_sha256,
        "javaArtifactSha256": jar_sha256, "aliases": [identity.alias for identity in identities],
        "budget": {"typedSearch": 44, "queryEmbedding": 10, "rerank": 22,
                   "metadataEsHttp": 30, "aliasWrites": 4, "paid": 0,
                   "retry": 0, "resume": 0},
    })
    processes: list[subprocess.Popen[bytes]] = []
    proxies: list[PhysicalEsProxy] = []
    result: ComparisonRun | None = None
    failed: ComparisonRunError | None = None
    reason: str | None = None
    pre_snapshots: tuple[tuple[str, str], ...] | None = None
    post_snapshots: tuple[tuple[str, str], ...] | None = None
    model_pre: dict[str, object] | None = None
    model_post: dict[str, object] | None = None
    lease: BIsolatedAliases | None = None
    stopped = False
    aliases_removed = False
    with httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False,
            follow_redirects=False, timeout=10.0) as es:
        try:
            model_pre = _capture_model_identity(inputs)
            lease = BIsolatedAliases(client=es, baseline=identities[0], candidate=identities[1],
                online_alias=inputs.read_alias, online_index=inputs.online_index,
                online_uuid=inputs.online_uuid,
                online_mapping_sha256=inputs.online_mapping_sha256,
                online_alias_sha256=inputs.online_alias_sha256,
                mapping_fingerprint=lambda value: sha256(_canonical(value)).hexdigest())
            pre_snapshots = lease.open()
            for identity, proxy_port in zip(identities, proxy_ports, strict=True):
                proxy = PhysicalEsProxy(identity=identity, port=proxy_port,
                    maximum_metadata=6,
                    maximum_search=sum(len(case.plan.items) for case in spec.cases), backend=es)
                proxy.start()
                proxies.append(proxy)
            env = {key: os.environ[key] for key in (
                "SystemRoot", "SystemDrive", "PATH", "JAVA_HOME", "TEMP", "TMP",
                "USERPROFILE", "APPDATA", "LOCALAPPDATA") if key in os.environ}
            env["COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE"] = base64.b64encode(secret).decode()
            for identity, port, proxy_port, arm in zip(identities, ports, proxy_ports,
                    ("baseline", "candidate"), strict=True):
                env_arm = dict(env)
                env_arm.update({
                    "AGENT_KNOWLEDGE_READ_ALIAS": identity.alias,
                    "AGENT_KNOWLEDGE_EXPECTED_INDEX_NAME": identity.index_name,
                    "AGENT_KNOWLEDGE_EXPECTED_INDEX_UUID": identity.index_uuid,
                    "AGENT_KNOWLEDGE_MAPPING_VERSION": identity.mapping_version,
                    "AGENT_KNOWLEDGE_POLICY_SNAPSHOT_ID": dict(profiles[arm])["tax.policy"],
                    "AGENT_KNOWLEDGE_LAW_SNAPSHOT_ID": dict(profiles[arm])["tax.law"],
                })
                process = subprocess.Popen(_java_args(jar=jar, config_dir=config_dir,
                    port=port, proxy_port=proxy_port,
                    identity=identity, run_id=inputs.run_id,
                    policy_snapshot=dict(profiles[arm])["tax.policy"],
                    law_snapshot=dict(profiles[arm])["tax.law"]),
                    cwd=ROOT / "es-query-service", env=env_arm,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                processes.append(process)
            _ready(processes, ports)
            if any(proxy.metadata_count != 6 or proxy.violations for proxy in proxies):
                raise BLocalRunError("java_startup_provenance_invalid")
            admission = LocalRuntimeAdmission(inputs.run_id, inputs.frozen_head,
                tuple((identity.arm, identity.index_name, identity.index_uuid,
                       identity.alias, pre_hash, process.pid)
                    for identity, (_, pre_hash), process in zip(identities, pre_snapshots,
                        processes, strict=True)), jar_sha256)
            async with AsyncExitStack() as stack:
                arm_clients = [await stack.enter_async_context(build_knowledge_http_client(
                    f"http://127.0.0.1:{port}")) for port in ports]
                embed_client = await stack.enter_async_context(build_knowledge_http_client(
                    "http://127.0.0.1:8908"))
                rerank_client = await stack.enter_async_context(build_knowledge_http_client(
                    "http://127.0.0.1:8909"))
                arms = tuple(ArmEndpoint(_OwnedSearch(
                    EsKnowledgeSearchAdapter(HttpxKnowledgeTransport(client)), process, port),
                    profiles[arm], mapping) for client, process, port, arm, mapping in zip(arm_clients,
                        processes, ports,
                        ("baseline", "candidate"),
                        (inputs.baseline_map, inputs.candidate_map), strict=True))
                def context_for(case_id: str) -> KnowledgeRetrievalContext:
                    _require_owned_listeners(processes, ports)
                    return KnowledgeRetrievalContext(request_id=case_id,
                        correlation_id=f"b-{inputs.run_id}-{case_id}",
                        subject="isolated-b-comparison", user_token=token_for_context,
                        deadline_monotonic=time.monotonic() + 30,
                        cancellation=MutableCancellationSignal())
                result = await run_comparison(spec=spec, baseline=arms[0], candidate=arms[1],
                    embedding=BgeM3EmbeddingAdapter(HttpxKnowledgeTransport(embed_client)),
                    rerank=ContextualBgeRerankAdapter(HttpxKnowledgeTransport(rerank_client)),
                    context_for=context_for, provenance_sidecars=inputs.sidecars,
                    local_admission=admission)
            model_post = _capture_model_identity(inputs)
            if _canonical(model_post) != _canonical(model_pre):
                raise BLocalRunError("model_identity_changed")
            if (any(proxy.metadata_count != 6 or proxy.violations for proxy in proxies)
                    or any(process.poll() is not None for process in processes)):
                raise BLocalRunError("runtime_provenance_invalid")
            post_snapshots = lease.postcheck()
        except ComparisonRunError as exc:
            failed = exc
            reason = exc.reason
        except (BLocalTransportError, BLocalRunError, ValueError, TypeError):
            reason = "local_execution_or_identity_failed"
        except asyncio.CancelledError:
            reason = "comparison_cancelled"
        except Exception:
            # A consumed run always gets a finite terminal reason; never emit
            # an adapter/Java/HTTP exception or any response text.
            reason = "local_unexpected_failure"
        finally:
            stopped = _stop_owned(processes)
            for proxy in proxies:
                try:
                    proxy.close()
                except Exception:
                    reason = "proxy_cleanup_failed"
            if lease is not None:
                try:
                    aliases_removed = lease.close()
                except Exception:
                    reason = "alias_cleanup_failed"
    proxy_violations = sum(proxy.violations for proxy in proxies)
    if _hash_file(jar) != jar_sha256:
        reason = "java_artifact_drift"
    counts = failed.calls if failed is not None else result.calls if result is not None else CallTotals(0, 0, 0)
    if (result is not None and reason is None and pre_snapshots is not None
            and post_snapshots is not None and lease is not None):
        receipt = LocalRuntimeReceipt(inputs.run_id,
            tuple((identity.arm, proxy.physical_search_paths)
                for identity, proxy in zip(identities, proxies, strict=True)),
            post_snapshots, lease.alias_writes,
            lease.metadata_calls + sum(proxy.metadata_count for proxy in proxies),
            stopped, aliases_removed, proxy_violations,
            tuple((identity.arm, tuple(item.request_sha256 for item in proxy.requests
                if item.method == "POST"))
                for identity, proxy in zip(identities, proxies, strict=True)))
        try:
            result = admit_completed_local_run(spec=spec, run=result,
                admission=admission, receipt=receipt)
        except ComparisonRunError:
            reason = "runtime_provenance_missing"
    if result is None or reason is not None:
        terminal: dict[str, object] = {
            "schemaVersion": 1, "runId": inputs.run_id,
            "frozenHead": inputs.frozen_head, "status": "not_assessed",
            "reason": reason or "comparison_incomplete", "assessmentSha256": spec.assessment_sha256,
            "calls": asdict(counts), "aliasWrites": lease.alias_writes if lease else 0,
            "metadataEsHttp": (lease.metadata_calls if lease else 0)
                + sum(proxy.metadata_attempts for proxy in proxies),
            "ownedProcessesStopped": stopped, "aliasesRemoved": aliases_removed,
            "proxyViolations": proxy_violations, "paid": 0, "retry": 0, "resume": 0,
            "unexecutedCaseIds": (
                list(failed.unexecuted_case_ids) if failed is not None else
                [] if result is not None else [case.case_id for case in spec.cases]
            ),
            "modelIdentityPre": model_pre, "modelIdentityPost": model_post,
        }
    else:
        terminal = {
            "schemaVersion": 1, "runId": inputs.run_id,
            "frozenHead": inputs.frozen_head,
            "status": "completed_awaiting_blind_labels", "evidenceKind": result.evidence_kind,
            "assessmentSha256": spec.assessment_sha256, "uatFixtureSha256": spec.uat_fixture_sha256,
            "provenanceSha256": result.provenance_sha256,
            "comparisonSpecSha256": result.comparison_spec_sha256,
            "calls": asdict(result.calls), "aliasWrites": lease.alias_writes if lease else 0,
            "metadataEsHttp": (lease.metadata_calls if lease else 0)
                + sum(proxy.metadata_count for proxy in proxies),
            "ownedPids": [process.pid for process in processes],
            "ownedProcessesStopped": stopped, "aliasesRemoved": aliases_removed,
            "proxyViolations": proxy_violations, "paid": 0, "retry": 0, "resume": 0,
            "witness": {identity.arm: [asdict(item) for item in proxy.requests]
                        for identity, proxy in zip(identities, proxies, strict=True)},
            "traces": asdict(result)["cases"],
            "modelIdentityPre": model_pre, "modelIdentityPost": model_post,
        }
        _write_once(directory / "comparison-blind-label-pool.json", {
            "schemaVersion": 1, "runId": inputs.run_id, "armHidden": True,
            "items": [list(item) for item in blind_label_pool(result)],
        })
    _write_once(directory / "comparison-result.json", terminal)
    return terminal


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare-only", action="store_true")
    modes.add_argument("--bind-source-map", action="store_true")
    modes.add_argument("--execute-once", action="store_true")
    modes.add_argument("--startup-preflight-only", action="store_true")
    modes.add_argument("--prepare-reuse", action="store_true")
    parser.add_argument("--baseline-port", type=int)
    parser.add_argument("--candidate-port", type=int)
    parser.add_argument("--baseline-proxy-port", type=int)
    parser.add_argument("--candidate-proxy-port", type=int)
    args = parser.parse_args()
    try:
        _require_locked_python_environment(
            "comparison" if args.execute_once or args.startup_preflight_only or args.prepare_reuse
            else "preparation")
        if args.prepare_reuse:
            if any(value is not None for value in (args.baseline_port, args.candidate_port,
                    args.baseline_proxy_port, args.candidate_proxy_port)):
                raise BLocalRunError("preparation_scope_invalid")
            terminal = prepare_reuse_inputs(args.run_directory)
        elif args.prepare_only or args.bind_source_map:
            if any(value is not None for value in (
                    args.baseline_port, args.candidate_port,
                    args.baseline_proxy_port, args.candidate_proxy_port)):
                raise BLocalRunError("preparation_scope_invalid")
            if args.bind_source_map:
                terminal = bind_local_b_request(args.run_directory)
            else:
                prepared = _object(_read(args.run_directory / "preparation.json"))
                candidate = prepared.get("candidate")
                if type(candidate) is not dict:
                    raise BLocalRunError("preparation_scope_invalid")
                index = candidate.get("source_index")
                alias = candidate.get("read_alias")
                if type(index) is not str or type(alias) is not str:
                    raise BLocalRunError("preparation_scope_invalid")
                transport = _PreparationTransport(index=index, alias=alias)
                try:
                    with httpx.Client(base_url="http://127.0.0.1:9200", timeout=30.0,
                            trust_env=False, follow_redirects=False, transport=transport) as client:
                        terminal = prepare_local_b_inputs(args.run_directory, client=client,
                                                          observed_calls=lambda: transport.calls)
                finally:
                    transport.close()
        elif args.startup_preflight_only:
            ports = (args.baseline_port, args.candidate_port)
            proxy_ports = (args.baseline_proxy_port, args.candidate_proxy_port)
            if any(type(port) is not int for port in (*ports, *proxy_ports)):
                raise BLocalRunError("port_binding_invalid")
            terminal = run_startup_preflight(args.run_directory,
                ports=ports, proxy_ports=proxy_ports)
        else:
            ports = (args.baseline_port, args.candidate_port)
            proxy_ports = (args.baseline_proxy_port, args.candidate_proxy_port)
            if any(type(port) is not int for port in (*ports, *proxy_ports)):
                raise BLocalRunError("port_binding_invalid")
            inputs = load_frozen_inputs(args.run_directory)
            with frozen_java_artifact(args.run_directory.resolve(), inputs) as (jar, jar_sha):
                terminal = asyncio.run(execute_local_comparison(directory=args.run_directory.resolve(),
                    inputs=inputs, jar=jar, jar_sha256=jar_sha,
                    ports=ports, proxy_ports=proxy_ports))
    except (BLocalRunError, ComparisonRunError, reuse.ReuseBindingError, ValueError):
        print(json.dumps({"status": "preflight_failed", "paid": 0}, sort_keys=True))
        return 1
    print(json.dumps({key: terminal[key] for key in ("runId", "status", "paid")},
                     ensure_ascii=False, sort_keys=True))
    return 0 if terminal["status"] in ("prepared", "source_bound", "ready", "reuse_scanned",
                                       "completed_awaiting_blind_labels") else 1


if __name__ == "__main__":
    raise SystemExit(main())
