"""One-shot Spring -> Runtime Knowledge measurement. Never import this from production.

The manifest and authorization are created only after the final code and jars are
frozen. This runner refuses an existing output directory; there is no resume path.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Mapping, cast

import httpx
import uvicorn

from agent_runtime.api.app import create_app
from agent_runtime.api.settings import RuntimeHttpSettings
from agent_runtime.knowledge.contracts import RetrievalStageResult
from agent_runtime.knowledge.minimal_plan import MinimalKnowledgeRetrievalPlan
from agent_runtime.knowledge.settings import KnowledgeSettings
from agent_runtime.knowledge.retrieval.http import BoundedHttpRequest, BoundedHttpResponse, KnowledgeHttpTransport
from agent_runtime.knowledge.retrieval.minimal_ranking import MinimalRankedBatch
from agent_runtime.knowledge.retrieval.settings import KnowledgeRetrievalSettings
from agent_runtime.model.contracts import ModelTaskId, StructuredModelRequest, StructuredModelResponse, StructuredModelTransport
from agent_runtime.model.settings import ModelSettings
from agent_runtime.main import build_runtime


_SHA = re.compile(r"[0-9a-f]{64}\Z")
_HEAD = re.compile(r"[0-9a-f]{40}\Z")
_RUN = re.compile(r"[a-z0-9][a-z0-9-]{5,100}\Z")
_TASKS = {
    ModelTaskId.ACTION_SELECTION: "action-selection-v4",
    ModelTaskId.KNOWLEDGE_REWRITE: "12",
    ModelTaskId.KNOWLEDGE_SUMMARY: "9",
}
_PATHS = {"search": "/es/knowledge/search", "embedding": "/embed", "rerank": "/rerank"}
_MAX = {"cases": 12, "model": 36, "search": 48, "embedding": 12, "rerank": 24}
_PER_CASE = {"model": 3, "search": 4, "embedding": 1, "rerank": 2}
_REVIEW_MAX_BYTES = 4 * 1024 * 1024
_SUBJECT = {"userId": "viewer_t", "role": "VIEWER"}
_BUILD_COMMANDS = (
    [["serviceCenter/mvnw.cmd", "--batch-mode", "-f", f"{name}/pom.xml", "-DskipTests", "clean", "install"]
     for name in ("common-security", "es-query-api")]
    + [["serviceCenter/mvnw.cmd", "--batch-mode", "-f", f"{name}/pom.xml", "-DskipTests", "clean", "package"]
       for name in ("auth-service", "es-query-service", "agent-service")]
)
_DEPENDENCY_JARS = {f"{name}/target/{name}-0.0.1-SNAPSHOT.jar"
                    for name in ("common-security", "es-query-api")}
_FROZEN_ENV_KEYS = frozenset({
    "AGENT_KNOWLEDGE_ENABLED", "AGENT_KNOWLEDGE_ENABLED_DOMAINS",
    "AGENT_KNOWLEDGE_REWRITE_MAX_CANDIDATES", "AGENT_KNOWLEDGE_ALLOW_ORIGINAL_FALLBACK",
    "AGENT_KNOWLEDGE_MAX_RETRIEVAL_QUERY_CHARS", "AGENT_KNOWLEDGE_PER_PATH_CANDIDATES",
    "AGENT_KNOWLEDGE_MIN_PARTIAL_CANDIDATES", "AGENT_KNOWLEDGE_REWRITE_TIMEOUT_MS",
    "AGENT_KNOWLEDGE_RETRIEVAL_TIMEOUT_MS", "AGENT_KNOWLEDGE_EVIDENCE_TIMEOUT_MS",
    "AGENT_KNOWLEDGE_ES_BASE_URL", "AGENT_KNOWLEDGE_PROFILE_VERSION",
    "AGENT_KNOWLEDGE_EMBEDDING_BASE_URL", "AGENT_KNOWLEDGE_RERANK_BASE_URL",
    "AGENT_KNOWLEDGE_EMBEDDING_DIM", "AGENT_KNOWLEDGE_RERANK_MODEL",
    "AGENT_KNOWLEDGE_FINAL_CANDIDATES", "AGENT_MODEL_PROVIDER",
    "AGENT_MODEL_MAX_CONCURRENCY", "AGENT_MODEL_ACTION_TIMEOUT_MS",
    "AGENT_MODEL_ANSWER_TIMEOUT_MS", "AGENT_MODEL_MAX_REQUEST_BYTES",
    "AGENT_MODEL_MAX_RESPONSE_BYTES", "AGENT_RUNTIME_HOST", "AGENT_RUNTIME_PORT",
    "AGENT_RUNTIME_CONTRACT_VERSION", "AGENT_RUNTIME_MAX_BODY_BYTES",
    "AGENT_RUNTIME_MAX_IN_FLIGHT", "AGENT_RUNTIME_DISCONNECT_POLL_MS",
    "AGENT_RUNTIME_MAX_INCOMPLETE_EVENT_BYTES", "AGENT_EMPLOYEE_BASE_URL",
    "AGENT_TRANSACTION_BASE_URL",
})
_REQUIRED_ENV = {
    "AGENT_KNOWLEDGE_ENABLED": "true",
    "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,tax.law",
    "AGENT_KNOWLEDGE_ALLOW_ORIGINAL_FALLBACK": "false",
    "AGENT_KNOWLEDGE_PER_PATH_CANDIDATES": "20",
    "AGENT_KNOWLEDGE_FINAL_CANDIDATES": "20",
    "AGENT_KNOWLEDGE_ES_BASE_URL": "http://127.0.0.1:19201",
    "AGENT_KNOWLEDGE_PROFILE_VERSION": "tax-knowledge-search-v1",
    "AGENT_KNOWLEDGE_EMBEDDING_BASE_URL": "http://127.0.0.1:8908",
    "AGENT_KNOWLEDGE_RERANK_BASE_URL": "http://127.0.0.1:8909",
    "AGENT_MODEL_PROVIDER": "deepseek",
    "AGENT_MODEL_MAX_CONCURRENCY": "1",
    "AGENT_RUNTIME_HOST": "127.0.0.1",
    "AGENT_RUNTIME_PORT": "19203",
    "AGENT_RUNTIME_CONTRACT_VERSION": "1",
    "AGENT_EMPLOYEE_BASE_URL": "http://127.0.0.1:1",
    "AGENT_TRANSACTION_BASE_URL": "http://127.0.0.1:2",
}


class MeasurementError(RuntimeError):
    pass


def _fail(code: str) -> None:
    raise MeasurementError(f"knowledge.measure.{code}")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for part in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(part)
    except OSError:
        _fail("asset_missing")
    return digest.hexdigest()


def _read_object(path: Path) -> dict[str, Any]:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                _fail("duplicate_json_key")
            result[key] = value
        return result

    try:
        value = json.loads(path.read_bytes(), object_pairs_hook=unique,
                           parse_constant=lambda _: _fail("nonfinite_json"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        _fail("invalid_json")
    if type(value) is not dict:
        _fail("invalid_json")
    return cast(dict[str, Any], value)


def _exclusive_json(path: Path, value: Mapping[str, Any]) -> None:
    encoded = (json.dumps(value, ensure_ascii=True, sort_keys=True,
                          separators=(",", ":")) + "\n").encode("utf-8")
    with path.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def _journal(path: Path, value: Mapping[str, Any]) -> None:
    encoded = (json.dumps(value, ensure_ascii=True, sort_keys=True,
                          separators=(",", ":")) + "\n").encode("utf-8")
    with path.open("ab") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def _bound_path(root: Path, relative: object) -> Path:
    if type(relative) is not str or not relative or "/" not in relative and relative.startswith("."):
        _fail("asset_path_invalid")
    path = Path(cast(str, relative))
    if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        _fail("asset_path_invalid")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        _fail("asset_missing")
    return resolved


def _run_directories(root: Path, run_id: str) -> tuple[Path, Path]:
    asset_parent = root / "agent-runtime/tests/uat"
    result_parent = asset_parent / "results"
    if asset_parent.resolve() != asset_parent or result_parent.resolve() != result_parent:
        _fail("run_path_invalid")
    return asset_parent / run_id, result_parent / run_id


def frozen_preflight(*, root: Path, manifest_path: Path, authorization_path: Path,
                     output_dir: Path, environ: Mapping[str, str]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Check every static binding before the API key is read or any outbound can happen."""
    root = root.resolve()
    manifest = _read_object(manifest_path)
    authorization = _read_object(authorization_path)
    expected_keys = {"schemaVersion", "runId", "branch", "frozenHead", "authorizationReference",
                     "datasetPath", "datasetSha256", "model", "taskVersions", "assetSha256",
                     "indexBindings", "policyCatalogSha256", "springBaseUrl", "runtimePort", "budgets",
                     "runtimeEnv", "subject", "cases", "sources", "humanRubric", "answerDesign", "promptSha256",
                     "jarBuildHead", "buildAttestationPath", "buildAttestationSha256",
                     "aliasFlags", "snapshotPreflightEsHttpRequests",
                     "snapshotPostflightEsHttpRequests", "runtimeMetadataEsHttpMax"}
    if set(manifest) != expected_keys or manifest["schemaVersion"] != 1:
        _fail("manifest_invalid")
    run_id = manifest["runId"]
    if type(run_id) is not str or not _RUN.fullmatch(run_id):
        _fail("run_id_invalid")
    run_asset_dir, expected_output = _run_directories(root, run_id)
    if (manifest_path.resolve() != run_asset_dir / "manifest.json"
            or authorization_path.resolve() != run_asset_dir / "authorization.json"
            or output_dir.resolve() != expected_output):
        _fail("run_path_invalid")
    if _bound_path(root, manifest["buildAttestationPath"]) != run_asset_dir / "build-attestation.json":
        _fail("run_path_invalid")
    if output_dir.exists():
        _fail("run_already_exists")
    if not expected_output.parent.is_dir():
        _fail("result_parent_missing")
    if (manifest["branch"] != "codex_0915" or type(manifest["frozenHead"]) is not str
            or not _HEAD.fullmatch(manifest["frozenHead"]) or manifest["model"] != ModelSettings.MODEL_NAME
            or manifest["taskVersions"] != {task.value: version for task, version in _TASKS.items()}
            or manifest["budgets"] != _MAX or manifest["springBaseUrl"] != "http://127.0.0.1:19202"
            or manifest["runtimePort"] != 19203 or manifest["answerDesign"] != "Summary9"
            or manifest["subject"] != _SUBJECT
            or manifest["jarBuildHead"] != manifest["frozenHead"]
            or manifest["aliasFlags"] not in ({}, {"is_write_index": False})
            or manifest["runtimeMetadataEsHttpMax"] != 48):
        _fail("manifest_binding_invalid")
    try:
        branch = subprocess.check_output(["git", "-C", str(root), "branch", "--show-current"], text=True).strip()
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        changed = subprocess.run(["git", "-C", str(root), "diff", "--quiet", "HEAD", "--"], check=False)
        status = subprocess.check_output(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
                                         text=True).splitlines()
    except (OSError, subprocess.CalledProcessError):
        _fail("git_preflight_failed")
    if branch != manifest["branch"] or head != manifest["frozenHead"] or changed.returncode != 0:
        _fail("git_binding_drift")
    try:
        allowed = {"?? " + manifest_path.resolve().relative_to(root).as_posix(),
                   "?? " + authorization_path.resolve().relative_to(root).as_posix(),
                   "?? " + _bound_path(root, manifest["buildAttestationPath"]).relative_to(root).as_posix()}
    except ValueError:
        _fail("run_assets_outside_repository")
    if set(status) != allowed or len(status) != 3:
        _fail("worktree_not_frozen")
    build_attestation_path = _bound_path(root, manifest["buildAttestationPath"])
    if manifest["buildAttestationSha256"] != _sha(build_attestation_path):
        _fail("build_attestation_drift")
    build_attestation = _read_object(build_attestation_path)
    jar_paths = {f"{service}/target/{service}-0.0.1-SNAPSHOT.jar"
                 for service in ("agent-service", "auth-service", "es-query-service")}
    if (set(build_attestation) != {"schemaVersion", "status", "branch", "head", "jarSha256",
                                  "dependencyJarSha256", "commands"}
            or build_attestation["schemaVersion"] != 1 or build_attestation["status"] != "built_from_clean_head"
            or build_attestation["branch"] != manifest["branch"]
            or build_attestation["head"] != manifest["frozenHead"]
            or build_attestation["commands"] != _BUILD_COMMANDS
            or set(build_attestation["jarSha256"]) != jar_paths
            or set(build_attestation["dependencyJarSha256"]) != _DEPENDENCY_JARS):
        _fail("build_attestation_invalid")
    asset_hashes = manifest["assetSha256"]
    if type(asset_hashes) is not dict or not asset_hashes or len(asset_hashes) > 128:
        _fail("manifest_assets_invalid")
    required = {
        "agent-runtime/tests/uat/knowledge_rebuild_measure.v1.json",
        "agent-runtime/src/agent_runtime/bootstrap.py",
        "agent-runtime/src/agent_runtime/main.py",
        "agent-runtime/src/agent_runtime/knowledge/evidence/egress-policy-catalog-v3.json",
        "agent-runtime/src/agent_runtime/knowledge/catalog.py",
        "agent-runtime/src/agent_runtime/model/deepseek/action_selector.py",
        "agent-runtime/src/agent_runtime/knowledge/intent_task_v12.py",
        "agent-runtime/src/agent_runtime/knowledge/evidence/summary_task_v9.py",
        "auth-service/src/main/resources/auth-users.yml",
        "agent-service/target/agent-service-0.0.1-SNAPSHOT.jar",
        "auth-service/target/auth-service-0.0.1-SNAPSHOT.jar",
        "es-query-service/target/es-query-service-0.0.1-SNAPSHOT.jar",
        *_DEPENDENCY_JARS,
    }
    if not required.issubset(asset_hashes):
        _fail("manifest_assets_missing")
    for relative, expected in asset_hashes.items():
        if type(expected) is not str or not _SHA.fullmatch(expected) or _sha(_bound_path(root, relative)) != expected:
            _fail("asset_hash_drift")
    if {path: asset_hashes[path] for path in jar_paths} != build_attestation["jarSha256"]:
        _fail("jar_build_drift")
    if {path: asset_hashes[path] for path in _DEPENDENCY_JARS} != build_attestation["dependencyJarSha256"]:
        _fail("dependency_build_drift")
    dataset_path = _bound_path(root, manifest["datasetPath"])
    if (manifest["datasetPath"] != "agent-runtime/tests/uat/knowledge_rebuild_measure.v1.json"
            or manifest["datasetSha256"] != _sha(dataset_path)):
        _fail("dataset_drift")
    dataset = _read_object(dataset_path)
    cases = manifest["cases"]
    if (type(cases) is not list or cases != dataset.get("cases") or manifest["sources"] != dataset.get("sources")
            or manifest["humanRubric"] != dataset.get("humanRubric")
            or len(cases) != 12 or len({case.get("caseId") for case in cases if type(case) is dict}) != 12):
        _fail("dataset_cases_invalid")
    source_ids = {item.get("id") for item in manifest["sources"] if type(item) is dict}
    if len(source_ids) != len(manifest["sources"]) or not source_ids:
        _fail("dataset_sources_invalid")
    for case in cases:
        if (type(case) is not dict or not set({"caseId", "question", "queryMode", "expectedDomains",
                                               "necessarySources", "expectedPublicStatus", "obligations"}).issubset(case)
                or not re.fullmatch(r"UAT-KM-[0-9]{3}", case["caseId"])
                or type(case["question"]) is not str or not 1 <= len(case["question"]) <= 1024
                or case["queryMode"] not in {"lookup", "explanation", "applicability"}
                or case["expectedPublicStatus"] not in {"success", "no_result"}
                or type(case["expectedDomains"]) is not list
                or not set(case["expectedDomains"]).issubset({"tax.policy", "tax.law"})
                or type(case["necessarySources"]) is not list
                or not set(case["necessarySources"]).issubset(source_ids)
                or type(case["obligations"]) is not list):
            _fail("dataset_cases_invalid")
    prompt_paths = {
        "action_selection": "agent-runtime/src/agent_runtime/model/deepseek/action_selector.py",
        "knowledge_rewrite": "agent-runtime/src/agent_runtime/knowledge/intent_task_v12.py",
        "knowledge_summary": "agent-runtime/src/agent_runtime/knowledge/evidence/summary_task_v9.py",
    }
    if manifest["promptSha256"] != {key: asset_hashes[path] for key, path in prompt_paths.items()}:
        _fail("prompt_hash_drift")
    if (type(manifest["policyCatalogSha256"]) is not str or not _SHA.fullmatch(manifest["policyCatalogSha256"])
            or type(manifest["indexBindings"]) is not dict
            or set(manifest["indexBindings"]) != {"tax.policy", "tax.law"}):
        _fail("snapshot_binding_invalid")
    catalog_path = "agent-runtime/src/agent_runtime/knowledge/evidence/egress-policy-catalog-v3.json"
    if manifest["policyCatalogSha256"] != asset_hashes[catalog_path]:
        _fail("policy_catalog_drift")
    for item in manifest["indexBindings"].values():
        if (type(item) is not dict or set(item) != {"readAlias", "indexName", "indexUuid", "mappingVersion", "mappingSha256",
                                                   "fullFingerprint", "recordCount", "snapshotId", "readPolicyVersion"}
                or any(type(item[key]) is not str or not item[key] for key in item if key != "recordCount")
                or any(not _SHA.fullmatch(item[key]) for key in ("mappingSha256", "fullFingerprint", "snapshotId"))
                or type(item["recordCount"]) is not int or item["recordCount"] < 1):
            _fail("snapshot_binding_invalid")
    policy_binding = manifest["indexBindings"]["tax.policy"]
    law_binding = manifest["indexBindings"]["tax.law"]
    if any(policy_binding[key] != law_binding[key] for key in ("readAlias", "indexName", "indexUuid",
                  "mappingVersion", "mappingSha256", "fullFingerprint", "recordCount")):
        _fail("profile_corpus_mismatch")
    count = manifest["indexBindings"]["tax.policy"]["recordCount"]
    if (manifest["snapshotPreflightEsHttpRequests"] != 4 + (count + 249) // 250
            or manifest["snapshotPostflightEsHttpRequests"] != 4 + (count + 249) // 250):
        _fail("snapshot_budget_invalid")
    auth_keys = {"schemaVersion", "status", "runId", "frozenHead", "manifestSha256",
                 "datasetSha256", "authorizationReference", "subject", "maximumModelRequests",
                 "singleUse", "retryAllowed"}
    if (set(authorization) != auth_keys or authorization["schemaVersion"] != 1
            or authorization["status"] != "authorized_unconsumed"
            or authorization["runId"] != run_id
            or authorization["frozenHead"] != head
            or authorization["manifestSha256"] != _sha(manifest_path)
            or authorization["datasetSha256"] != manifest["datasetSha256"]
            or authorization["authorizationReference"] != manifest["authorizationReference"]
            or authorization["subject"] != _SUBJECT
            or authorization["maximumModelRequests"] != 36
            or authorization["singleUse"] is not True or authorization["retryAllowed"] is not False):
        _fail("authorization_binding_invalid")
    if any(environ.get(key) != value for key, value in _REQUIRED_ENV.items()):
        _fail("runtime_configuration_drift")
    forbidden_env = {key for key in environ if key.startswith(("AGENT_KNOWLEDGE_", "AGENT_MODEL_", "AGENT_RUNTIME_"))
                     and key not in _FROZEN_ENV_KEYS}
    forbidden_env.update(key for key in environ if key.startswith("AGENT_BUSINESS_"))
    frozen_env = {key: value for key, value in environ.items() if key in _FROZEN_ENV_KEYS}
    if (forbidden_env or type(manifest["runtimeEnv"]) is not dict
            or not set(manifest["runtimeEnv"]).issubset(_FROZEN_ENV_KEYS)
            or frozen_env != manifest["runtimeEnv"]
            or any(type(value) is not str for value in frozen_env.values())):
        _fail("runtime_configuration_drift")
    try:
        knowledge_settings = KnowledgeSettings.from_env(environ)
        retrieval_settings = KnowledgeRetrievalSettings.from_env(environ, enabled=True)
    except ValueError:
        _fail("runtime_configuration_drift")
    if (not knowledge_settings.enabled or knowledge_settings.enabled_domain_ids != ("tax.policy", "tax.law")
            or knowledge_settings.allow_original_fallback
            or knowledge_settings.per_path_candidate_limit != 20
            or retrieval_settings.final_candidates != 20):
        _fail("runtime_configuration_drift")
    return manifest, authorization, dataset


def frozen_postflight(*, root: Path, manifest_path: Path, authorization_path: Path,
                      output_dir: Path, environ: Mapping[str, str]) -> dict[str, Any]:
    """Recheck the static freeze after outbound, allowing only this run's finite evidence."""
    root = root.resolve()
    manifest = _read_object(manifest_path)
    run_id = manifest.get("runId")
    if type(run_id) is not str or not _RUN.fullmatch(run_id):
        _fail("run_id_invalid")
    run_id = cast(str, run_id)
    run_asset_dir, expected_output = _run_directories(root, run_id)
    if (manifest_path.resolve() != run_asset_dir / "manifest.json"
            or authorization_path.resolve() != run_asset_dir / "authorization.json"
            or _bound_path(root, manifest.get("buildAttestationPath")) != run_asset_dir / "build-attestation.json"
            or output_dir.resolve() != expected_output or not output_dir.is_dir()):
        _fail("postflight_run_missing")
    try:
        branch = subprocess.check_output(["git", "-C", str(root), "branch", "--show-current"], text=True).strip()
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        changed = subprocess.run(["git", "-C", str(root), "diff", "--quiet", "HEAD", "--"], check=False)
        status = subprocess.check_output(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
                                         text=True).splitlines()
        run_relative = output_dir.relative_to(root).as_posix()
        allowed = {"?? " + manifest_path.relative_to(root).as_posix(),
                   "?? " + authorization_path.relative_to(root).as_posix(),
                   "?? " + _bound_path(root, manifest["buildAttestationPath"]).relative_to(root).as_posix()}
    except (OSError, ValueError, subprocess.CalledProcessError):
        _fail("git_postflight_failed")
    if branch != manifest.get("branch") or head != manifest.get("frozenHead") or changed.returncode != 0:
        _fail("git_binding_drift")
    base_allowed = set(allowed)
    evidence_names = {"authorization.consumed.json", "attempts.jsonl", "cases.jsonl",
                      "measurement.json", "failure.json", "launcher-failure.json", "result.json",
                      "snapshot-preflight.json", "snapshot-postflight.json"}
    allowed.update("?? " + run_relative + "/" + name for name in evidence_names if (output_dir / name).is_file())
    if not base_allowed.issubset(status) or not set(status).issubset(allowed):
        _fail("worktree_postflight_drift")
    for relative, expected in manifest["assetSha256"].items():
        if _sha(_bound_path(root, relative)) != expected:
            _fail("asset_hash_drift")
    if _sha(_bound_path(root, manifest["buildAttestationPath"])) != manifest["buildAttestationSha256"]:
        _fail("build_attestation_drift")
    if _sha(manifest_path) != _read_object(authorization_path).get("manifestSha256"):
        _fail("manifest_hash_drift")
    measurement_path = output_dir / "measurement.json"
    if not measurement_path.is_file() or _read_object(measurement_path).get("authorizationSha256") != _sha(authorization_path):
        _fail("authorization_drift")
    forbidden_env = {key for key in environ if key.startswith(("AGENT_KNOWLEDGE_", "AGENT_MODEL_", "AGENT_RUNTIME_"))
                     and key not in _FROZEN_ENV_KEYS}
    forbidden_env.update(key for key in environ if key.startswith("AGENT_BUSINESS_"))
    frozen_env = {key: value for key, value in environ.items() if key in _FROZEN_ENV_KEYS}
    if forbidden_env or frozen_env != manifest["runtimeEnv"]:
        _fail("runtime_configuration_drift")
    return manifest


async def _alias_check(manifest: Mapping[str, Any], client: httpx.AsyncClient) -> None:
    policy = manifest["indexBindings"]["tax.policy"]
    response = await client.get(f"/_alias/{policy['readAlias']}", timeout=5.0)
    if response.status_code != 200 or len(response.content) > 65536:
        _fail("alias_drift")
    alias = response.json()
    if (type(alias) is not dict or set(alias) != {policy["indexName"]}
            or alias[policy["indexName"]].get("aliases", {}).get(policy["readAlias"]) != manifest["aliasFlags"]):
        _fail("alias_drift")
    definition_response = await client.get(f"/{policy['indexName']}", timeout=5.0)
    if definition_response.status_code != 200 or len(definition_response.content) > 1024 * 1024:
        _fail("index_metadata_drift")
    definition = definition_response.json()
    if type(definition) is not dict or set(definition) != {policy["indexName"]}:
        _fail("index_metadata_drift")
    try:
        item = definition[policy["indexName"]]
        settings = item["settings"]["index"]
        mapping = item["mappings"]
        write_blocked = settings.get("blocks", {}).get("write") in (True, "true") or settings.get("blocks.write") in (True, "true")
        mapping_sha = hashlib.sha256((json.dumps(mapping, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")).hexdigest()
        if (settings["uuid"] != policy["indexUuid"] or not write_blocked
                or mapping["_meta"]["mapping_version"] != policy["mappingVersion"]
                or mapping_sha != policy["mappingSha256"]):
            _fail("index_metadata_drift")
    except (KeyError, TypeError, AttributeError, ValueError):
        _fail("index_metadata_drift")


def _owned_ports_match(*, es_pid: int, agent_pid: int) -> None:
    """Check Windows listener ownership immediately before sending a bearer token."""
    if os.name != "nt" or es_pid < 1 or agent_pid < 1:
        _fail("owned_port_binding_invalid")
    command = (
        "$ErrorActionPreference='Stop'; "
        "$rows=@(Get-NetTCPConnection -State Listen -LocalPort 19201,19202 | "
        "Select-Object LocalPort,OwningProcess); "
        "ConvertTo-Json -InputObject $rows -Compress"
    )
    try:
        raw = subprocess.check_output(["pwsh", "-NoProfile", "-Command", command],
                                      text=True, timeout=8)
        rows = json.loads(raw)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        _fail("owned_port_check_failed")
    expected = {19201: es_pid, 19202: agent_pid}
    if (type(rows) is not list or len(rows) < 2
            or {row.get("LocalPort") for row in rows if type(row) is dict} != set(expected)
            or any(type(row) is not dict or set(row) != {"LocalPort", "OwningProcess"}
                   or type(row["LocalPort"]) is not int or type(row["OwningProcess"]) is not int
                   or row["OwningProcess"] != expected.get(row["LocalPort"]) for row in rows)):
        _fail("owned_port_mismatch")


async def _post_spring_owned(*, client: httpx.AsyncClient, question: str, case_id: str,
                             token: str, es_pid: int, agent_pid: int) -> httpx.Response:
    await asyncio.to_thread(_owned_ports_match, es_pid=es_pid, agent_pid=agent_pid)
    return await client.post("/api/v1/agent/queries", json={"question": question},
                             headers={"Authorization": f"Bearer {token}",
                                      "X-Correlation-Id": case_id}, timeout=45.0)


class OneShotLedger:
    """All reservations happen synchronously before each awaited network send."""

    def __init__(self, *, output_dir: Path, manifest: Mapping[str, Any], manifest_sha256: str) -> None:
        output_dir.mkdir(parents=False, exist_ok=False)
        self.output_dir = output_dir
        self.manifest = manifest
        self.manifest_sha256 = manifest_sha256
        self.active: str | None = None
        self.question: str | None = None
        self.seen: set[str] = set()
        self.runtime_invocations = 0
        self.total = {key: 0 for key in _PER_CASE}
        self.case_counts = {key: 0 for key in _PER_CASE}
        self.case_tasks: set[ModelTaskId] = set()
        self.fatal: str | None = None
        self.ranked: list[dict[str, Any]] = []
        self.snapshot_ids: set[str] = set()
        self.planned_domains: list[str] | None = None
        self.planned_query_mode: str | None = None
        self.consumed = False

    def begin(self, case_id: str, question: str) -> None:
        if self.active is not None or case_id in self.seen or self.fatal is not None:
            _fail("attempt_overlap_or_resume")
        self.active, self.question = case_id, question
        self.seen.add(case_id)
        self.runtime_invocations = 0
        self.case_counts = {key: 0 for key in _PER_CASE}
        self.case_tasks.clear()
        self.ranked = []
        self.snapshot_ids = set()
        self.planned_domains = None
        self.planned_query_mode = None

    def end(self) -> None:
        if self.active is None or self.runtime_invocations != 1:
            self.fatal = "runtime_invocation_mismatch"
            _fail(self.fatal)
        self.active = self.question = None

    def claim_runtime(self, *, correlation_id: str, question: str) -> None:
        if self.active != correlation_id or self.question != question or self.runtime_invocations != 0:
            self.fatal = "runtime_scope_mismatch"
            _fail(self.fatal)
        self.runtime_invocations = 1

    def _reserve(self, kind: str, *, task: ModelTaskId | None = None) -> int:
        if self.active is None or self.fatal is not None:
            _fail("inactive_or_terminal")
        if self.total[kind] >= _MAX[kind] or self.case_counts[kind] >= _PER_CASE[kind]:
            self.fatal = "budget_exhausted"
            _fail(self.fatal)
        if task is not None:
            if task not in _TASKS or task in self.case_tasks:
                self.fatal = "task_forbidden_or_retry"
                _fail(self.fatal)
            self.case_tasks.add(task)
        self.total[kind] += 1
        self.case_counts[kind] += 1
        ordinal = self.total[kind]
        _journal(self.output_dir / "attempts.jsonl", {"caseId": self.active, "kind": kind,
                 "ordinal": ordinal, "taskId": task.value if task else None, "event": "started"})
        return ordinal

    def consume(self) -> None:
        if not self.consumed:
            _exclusive_json(self.output_dir / "authorization.consumed.json", {
                "schemaVersion": 1, "status": "consumed", "runId": self.manifest["runId"],
                "frozenHead": self.manifest["frozenHead"], "manifestSha256": self.manifest_sha256,
                "authorizationReference": self.manifest["authorizationReference"],
                "maximumModelRequests": 36, "retryAllowed": False,
            })
            self.consumed = True

    def model(self, delegate: StructuredModelTransport) -> StructuredModelTransport:
        owner = self

        class GuardedModel:
            async def complete(self, request: StructuredModelRequest, *, call_deadline: float) -> StructuredModelResponse:
                if request.task_id not in _TASKS or request.task_version != _TASKS.get(request.task_id):
                    owner.fatal = "task_binding_drift"
                    _fail(owner.fatal)
                owner.consume()  # exclusive + fsync before even the started journal or HTTP send
                ordinal = owner._reserve("model", task=request.task_id)
                try:
                    response = await delegate.complete(request, call_deadline=call_deadline)
                except BaseException:
                    owner.fatal = "model_failure"
                    _journal(owner.output_dir / "attempts.jsonl", {"caseId": owner.active, "kind": "model",
                             "ordinal": ordinal, "event": "terminal", "status": "failed"})
                    raise
                _journal(owner.output_dir / "attempts.jsonl", {"caseId": owner.active, "kind": "model",
                         "ordinal": ordinal, "event": "terminal", "status": "completed"})
                return response

        return GuardedModel()

    def transport(self, name: str, delegate: KnowledgeHttpTransport) -> KnowledgeHttpTransport:
        if name not in _PATHS:
            _fail("transport_invalid")
        owner = self

        class GuardedTransport:
            async def send(self, *, request: BoundedHttpRequest, timeout_s: float) -> BoundedHttpResponse:
                if request.relative_path != _PATHS[name] or request.method != "POST":
                    owner.fatal = "transport_binding_drift"
                    _fail(owner.fatal)
                ordinal = owner._reserve(name)
                try:
                    response = await delegate.send(request=request, timeout_s=timeout_s)
                except BaseException:
                    owner.fatal = "downstream_failure"
                    _journal(owner.output_dir / "attempts.jsonl", {"caseId": owner.active, "kind": name,
                             "ordinal": ordinal, "event": "terminal", "status": "failed"})
                    raise
                _journal(owner.output_dir / "attempts.jsonl", {"caseId": owner.active, "kind": name,
                         "ordinal": ordinal, "event": "terminal", "status": "completed", "httpStatus": response.status_code})
                if response.status_code != 200:
                    owner.fatal = "downstream_http_failure"
                return response

        return GuardedTransport()

    def retrieval(self, delegate: Any) -> Any:
        owner = self

        class GuardedRetrieval:
            async def execute(self, *, plan: Any, context: Any, timeout_s: float) -> RetrievalStageResult[MinimalRankedBatch]:
                if owner.active != context.correlation_id:
                    owner.fatal = "retrieval_scope_mismatch"
                    _fail(owner.fatal)
                if type(plan) is not MinimalKnowledgeRetrievalPlan or owner.planned_domains is not None:
                    owner.fatal = "retrieval_plan_invalid_or_repeated"
                    _fail(owner.fatal)
                owner.planned_domains = list(plan.selected_domain_ids)
                owner.planned_query_mode = plan.query_mode.value
                result: RetrievalStageResult[MinimalRankedBatch] = await delegate.execute(
                    plan=plan, context=context, timeout_s=timeout_s)
                if result.batch is not None:
                    bindings = owner.manifest["indexBindings"]
                    expected_snapshots = {item["snapshotId"] for item in bindings.values()}
                    expected_sources = {item["chunkId"]: item for item in owner.manifest["sources"]}
                    if not set(result.batch.index_snapshot_ids).issubset(expected_snapshots):
                        owner.fatal = "index_snapshot_drift"
                        _fail(owner.fatal)
                    for item in result.batch.candidates:
                        candidate = item.candidate
                        if (candidate.index_snapshot_id not in expected_snapshots
                                or candidate.read_policy_version != "tax-public-authenticated-v1"):
                            owner.fatal = "candidate_policy_drift"
                            _fail(owner.fatal)
                        expected = expected_sources.get(candidate.chunk_id)
                        if expected is not None and (candidate.document_id != expected["documentId"]
                                                     or candidate.content_sha256 != expected["contentSha256"]):
                            owner.fatal = "necessary_source_drift"
                            _fail(owner.fatal)
                    owner.snapshot_ids.update(result.batch.index_snapshot_ids)
                    owner.ranked = [{"rank": item.rank, "chunkId": item.candidate.chunk_id,
                                     "documentId": item.candidate.document_id,
                                     "contentSha256": item.candidate.content_sha256,
                                     "domainIds": list(item.domain_ids)} for item in result.batch.candidates]
                return result

        return GuardedRetrieval()


def _finite_response(response: Mapping[str, Any]) -> dict[str, Any]:
    error = response.get("error")
    result = response.get("result")
    points = result.get("points", []) if type(result) is dict else []
    return {"status": response.get("status"), "capabilityId": response.get("capabilityId"),
            "errorCode": error.get("code") if type(error) is dict else None,
            "answerSha256": hashlib.sha256(str(response.get("answer", "")).encode("utf-8")).hexdigest(),
            "citations": [{"evidenceId": item.get("citation", {}).get("evidenceId"),
                           "quoteSha256": hashlib.sha256(str(item.get("quote", "")).encode("utf-8")).hexdigest()}
                          for item in points if type(item) is dict and type(item.get("citation")) is dict]}


def _public_review(case: Mapping[str, Any], response: Mapping[str, Any]) -> dict[str, Any]:
    """Only the already-authorized public answer, never a provider response or raw ES body."""
    def bounded(value: object, limit: int) -> str:
        if type(value) is not str or len(value.encode("utf-8")) > limit:
            _fail("public_review_invalid")
        return cast(str, value)

    result = response.get("result")
    summary = ""
    points: list[dict[str, Any]] = []
    if result is not None:
        if type(result) is not dict:
            _fail("public_review_invalid")
        summary = bounded(result.get("answerSummary", ""), 16_384)
        raw_points = result.get("points", [])
        if type(raw_points) is not list or len(raw_points) > 5:
            _fail("public_review_invalid")
        for item in raw_points:
            if type(item) is not dict or type(item.get("citation")) is not dict:
                _fail("public_review_invalid")
            citation = item["citation"]
            points.append({"quote": bounded(item.get("quote"), 8192),
                           "citation": {key: bounded(citation.get(key, ""), 2048)
                                        for key in ("evidenceId", "title", "sourceUrl", "documentNumber", "writtenDate")}})
    return {"caseId": case["caseId"], "question": bounded(case["question"], 4096),
            "obligations": case["obligations"], "status": response.get("status"),
            "answer": bounded(response.get("answer", ""), 16_384),
            "answerSummary": summary, "points": points}


def _plan_comparison(*, expected_mode: str, expected_domains: list[str],
                     observed_mode: str | None, observed_domains: list[str] | None) -> dict[str, bool | None]:
    # Clarification may correctly terminate before a RetrievalPlan exists. In that
    # case the model's query mode is not observable from the retrieval seam.
    return {"queryModeDiffers": None if observed_domains is None else observed_mode != expected_mode,
            "selectedDomainsDiffer": bool(expected_domains) if observed_domains is None
                                     else observed_domains != expected_domains}


def _checked_public_review_size(value: Mapping[str, Any], *, secrets: tuple[str, ...]) -> int:
    encoded = (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n")
    if (any(secret and secret in encoded for secret in secrets)
            or re.search(r"(?i)LLM_API_KEY|COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE|Bearer\s+eyJ", encoded)):
        _fail("sensitive_public_review")
    return len(encoded.encode("utf-8"))


async def run_once(*, manifest: dict[str, Any], output_dir: Path, review_dir: Path,
                   token: str, environ: Mapping[str, str], client: httpx.AsyncClient,
                   es_pid: int, agent_pid: int, server_factory: Any = uvicorn.Server) -> None:
    """The client must target the isolated Spring agent-service, never Runtime directly."""
    if client.base_url != httpx.URL(manifest["springBaseUrl"]):
        _fail("spring_origin_invalid")
    review_dir.mkdir(parents=False, exist_ok=False)
    ledger = OneShotLedger(output_dir=output_dir, manifest=manifest, manifest_sha256=manifest["_sha256"])
    settings = RuntimeHttpSettings(host="127.0.0.1", port=19203, max_in_flight=1)

    class GuardedRuntime:
        def __init__(self, delegate: Any) -> None:
            self.delegate = delegate

        async def ainvoke(self, *, question: str, scope: Any) -> Any:
            ledger.claim_runtime(correlation_id=scope.context.correlation_id, question=question)
            return await self.delegate.ainvoke(question=question, scope=scope)

        async def aclose(self) -> None:
            await self.delegate.aclose()

    def runtime_factory() -> GuardedRuntime:
        return GuardedRuntime(build_runtime(environ,
            model_transport_wrapper=ledger.model,
            knowledge_transport_wrapper=ledger.transport,
            knowledge_retrieval_wrapper=ledger.retrieval))

    server = server_factory(uvicorn.Config(create_app(settings, runtime_factory), host="127.0.0.1",
                                           port=19203, workers=1, access_log=False, log_level="warning"))
    server_task = asyncio.create_task(server.serve())
    records: list[dict[str, Any]] = []
    alias_checks = 0
    review_bytes = 0
    try:
        for _ in range(100):
            if server.started:
                break
            if server_task.done():
                _fail("runtime_start_failed")
            await asyncio.sleep(0.05)
        else:
            _fail("runtime_start_timeout")
        health = await client.get("/actuator/health/readiness", timeout=5.0)
        if health.status_code != 200:
            _fail("spring_not_ready")
        async with httpx.AsyncClient(base_url="http://127.0.0.1:9200", trust_env=False,
                                     follow_redirects=False) as es_client:
            for case in manifest["cases"]:
                case_id, question = case["caseId"], case["question"]
                await _alias_check(manifest, es_client)
                alias_checks += 1
                ledger.begin(case_id, question)
                try:
                    response = await _post_spring_owned(client=client, question=question, case_id=case_id,
                                                        token=token, es_pid=es_pid, agent_pid=agent_pid)
                    body = response.json()
                    await _alias_check(manifest, es_client)
                    alias_checks += 1
                    if (type(body) is not dict or body.get("correlationId") != case_id
                            or not (body.get("capabilityId") == "knowledge.query"
                                    or body.get("status") == "unsupported" and body.get("capabilityId") is None)
                            or body.get("status") not in {"success", "no_result", "unsupported"}
                            or response.status_code >= 500 or ledger.fatal is not None):
                        _fail("case_technical_failure")
                    ledger.end()
                    ranked_ids = {item["chunkId"] for item in ledger.ranked}
                    necessary = {item["id"]: item["chunkId"] for item in manifest["sources"]
                                 if item["id"] in case["necessarySources"]}
                    represented = set().union(*(set(item["domainIds"]) for item in ledger.ranked))
                    record = {"caseId": case_id, "httpStatus": response.status_code,
                              "response": _finite_response(body), "counts": dict(ledger.case_counts),
                              "runtimeInvocations": ledger.runtime_invocations,
                              "observedPlan": {"planPresent": ledger.planned_domains is not None,
                                               "queryMode": ledger.planned_query_mode,
                                               "selectedDomainIds": ledger.planned_domains},
                              "rankedTop20": ledger.ranked, "indexSnapshotIds": sorted(ledger.snapshot_ids),
                              "frozenExpectation": {"queryMode": case["queryMode"],
                                                    "publicStatus": case["expectedPublicStatus"],
                                                    "domains": case["expectedDomains"],
                                                    "necessarySources": case["necessarySources"]},
                              "observedDifference": {
                                  "publicStatusDiffers": body["status"] != case["expectedPublicStatus"],
                                  **_plan_comparison(expected_mode=case["queryMode"],
                                                     expected_domains=case["expectedDomains"],
                                                     observed_mode=ledger.planned_query_mode,
                                                     observed_domains=ledger.planned_domains),
                                  "missingExpectedDomainsInTop20": sorted(set(case["expectedDomains"]) - represented),
                                  "missingNecessarySourcesInTop20": sorted(
                                      source_id for source_id, chunk_id in necessary.items() if chunk_id not in ranked_ids)}}
                    review_item = _public_review(case, body)
                    review_size = _checked_public_review_size(review_item, secrets=(token,
                        environ.get("LLM_API_KEY", ""), environ.get("COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE", "")))
                    if review_bytes + review_size > _REVIEW_MAX_BYTES:
                        ledger.fatal = "public_review_budget_exhausted"
                        _fail(ledger.fatal)
                    _journal(review_dir / "public-review.jsonl", review_item)
                    review_bytes += review_size
                    _journal(output_dir / "cases.jsonl", record)
                    records.append(record)
                except BaseException as exc:
                    if ledger.fatal is None:
                        ledger.fatal = (str(exc).removeprefix("knowledge.measure.")
                                        if isinstance(exc, MeasurementError) else "case_technical_failure")
                    raise
        _exclusive_json(output_dir / "measurement.json", {"schemaVersion": 1, "runId": manifest["runId"],
                        "status": "completed_pending_postflight", "caseCount": len(records),
                        "counts": ledger.total, "aliasChecks": alias_checks,
                        "modelAuthorizedConsumed": ledger.consumed,
                        "authorizationSha256": manifest["_authorizationSha256"],
                        "modelRequestsReservedUpperBound": ledger.total["model"],
                        "publicStatusMismatches": sum(item["observedDifference"]["publicStatusDiffers"] for item in records),
                        "humanRubric": "not_assessed"})
    except BaseException:
        _exclusive_json(output_dir / "failure.json", {"schemaVersion": 1, "runId": manifest["runId"],
                        "status": "failed_consumed" if ledger.consumed else "failed_unconsumed",
                        "completedCases": len(records), "counts": ledger.total, "aliasChecks": alias_checks,
                        "reason": ledger.fatal or "runner_failure"})
        raise
    finally:
        server.should_exit = True
        await server_task


async def _main(args: argparse.Namespace) -> None:
    root = Path(args.repository).resolve()
    manifest_path = Path(args.manifest).resolve()
    authorization_path = Path(args.authorization).resolve()
    output_dir = Path(args.output).resolve()
    if args.phase == "postflight":
        frozen_postflight(root=root, manifest_path=manifest_path,
                          authorization_path=authorization_path, output_dir=output_dir,
                          environ=os.environ)
        return
    manifest, _, _ = frozen_preflight(root=root, manifest_path=manifest_path,
        authorization_path=authorization_path, output_dir=output_dir, environ=os.environ)
    if args.phase == "static":
        return
    manifest["_sha256"] = _sha(manifest_path)
    manifest["_authorizationSha256"] = _sha(authorization_path)
    if not args.snapshot_attestation:
        _fail("snapshot_attestation_missing")
    attestation = _read_object(Path(args.snapshot_attestation))
    policy = manifest["indexBindings"]["tax.policy"]
    if (set(attestation) != {"schemaVersion", "status", "runId", "manifestSha256", "indexName",
                             "indexUuid", "fullFingerprint", "recordCount", "createdAtUnixMs"}
            or attestation["schemaVersion"] != 1 or attestation["status"] != "passed"
            or attestation["runId"] != manifest["runId"] or attestation["manifestSha256"] != manifest["_sha256"]
            or any(attestation[key] != policy[key] for key in ("indexName", "indexUuid", "fullFingerprint", "recordCount"))
            or type(attestation["createdAtUnixMs"]) is not int
            or not 0 <= (time.time_ns() // 1_000_000) - attestation["createdAtUnixMs"] <= 120_000
            or os.environ.get("KNOWLEDGE_MEASURE_LAUNCHER_ATTESTED") != manifest["_sha256"]):
        _fail("launcher_attestation_missing")
    token = os.environ.get("KNOWLEDGE_MEASURE_USER_JWT", "")
    if not token or len(token) > 16384:
        _fail("user_token_missing")
    try:
        es_pid = int(os.environ["KNOWLEDGE_MEASURE_OWNED_ES_PID"])
        agent_pid = int(os.environ["KNOWLEDGE_MEASURE_OWNED_AGENT_PID"])
    except (KeyError, ValueError):
        _fail("owned_port_binding_invalid")
    if es_pid < 1 or agent_pid < 1:
        _fail("owned_port_binding_invalid")
    # ModelSettings.from_env is deliberately delayed until all non-live gates above.
    ModelSettings.from_env(os.environ)
    if not args.review_dir:
        _fail("review_path_missing")
    review_dir = Path(args.review_dir).resolve()
    expected_review_parent = root / ".tmp" / "knowledge-measure-review"
    if expected_review_parent.resolve() != expected_review_parent:
        _fail("review_path_invalid")
    if review_dir.parent != expected_review_parent or review_dir.name != manifest["runId"] or review_dir.exists():
        _fail("review_path_invalid")
    async with httpx.AsyncClient(base_url=manifest["springBaseUrl"], follow_redirects=False,
                                 trust_env=False) as client:
        await run_once(manifest=manifest, output_dir=output_dir, review_dir=review_dir,
                       token=token, environ=os.environ, client=client,
                       es_pid=es_pid, agent_pid=agent_pid)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--phase", choices=("static", "run", "postflight"), default="run")
    parser.add_argument("--snapshot-attestation")
    parser.add_argument("--review-dir")
    try:
        asyncio.run(_main(parser.parse_args()))
    except MeasurementError as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
