"""Prepare one immutable local Knowledge measurement; no model calls or writes to ES.

Build is a separate, explicit phase after a clean commit. Freeze then reads the
current loopback ES binding and the pre-registered fixture, and creates exactly
one manifest/authorization pair. Neither phase can consume an authorization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any

import httpx

from tests.uat.knowledge_rebuild_measure_runner import (
    MeasurementError, _BUILD_COMMANDS, _DEPENDENCY_JARS, _MAX, _REQUIRED_ENV, _RUN, _SUBJECT, _TASKS,
    _exclusive_json, _read_object, _sha,
)


_SERVICES = ("auth-service", "es-query-service", "agent-service")
_JARS = {name: f"{name}/target/{name}-0.0.1-SNAPSHOT.jar" for name in _SERVICES}
_DATASET = "agent-runtime/tests/uat/knowledge_rebuild_measure.v1.json"
_ASSETS = (
    _DATASET,
    "agent-runtime/tests/uat/knowledge_rebuild_measure_runner.py",
    "agent-runtime/tests/uat/knowledge_rebuild_snapshot_preflight.py",
    "agent-runtime/tests/uat/knowledge_rebuild_measure_prepare.py",
    "agent-runtime/scripts/run-knowledge-rebuild-measure-v1.ps1",
    "agent-runtime/src/agent_runtime/bootstrap.py",
    "agent-runtime/src/agent_runtime/main.py",
    "agent-runtime/src/agent_runtime/knowledge/catalog.py",
    "agent-runtime/src/agent_runtime/knowledge/evidence/egress-policy-catalog-v3.json",
    "agent-runtime/src/agent_runtime/model/deepseek/action_selector.py",
    "agent-runtime/src/agent_runtime/knowledge/intent_task_v12.py",
    "agent-runtime/src/agent_runtime/knowledge/evidence/summary_task_v9.py",
    "auth-service/src/main/resources/auth-users.yml",
)
_ENV = {
    **_REQUIRED_ENV,
    "AGENT_KNOWLEDGE_REWRITE_MAX_CANDIDATES": "3",
    "AGENT_KNOWLEDGE_MAX_RETRIEVAL_QUERY_CHARS": "1024",
    "AGENT_KNOWLEDGE_MIN_PARTIAL_CANDIDATES": "3",
    "AGENT_KNOWLEDGE_REWRITE_TIMEOUT_MS": "8000",
    "AGENT_KNOWLEDGE_RETRIEVAL_TIMEOUT_MS": "20000",
    "AGENT_KNOWLEDGE_EVIDENCE_TIMEOUT_MS": "15000",
    "AGENT_KNOWLEDGE_EMBEDDING_DIM": "1024",
    "AGENT_KNOWLEDGE_RERANK_MODEL": "BAAI/bge-reranker-v2-m3",
    "AGENT_MODEL_ACTION_TIMEOUT_MS": "8000",
    "AGENT_MODEL_ANSWER_TIMEOUT_MS": "15000",
    "AGENT_MODEL_MAX_REQUEST_BYTES": "131072",
    "AGENT_MODEL_MAX_RESPONSE_BYTES": "262144",
    "AGENT_RUNTIME_MAX_BODY_BYTES": "32768",
    "AGENT_RUNTIME_MAX_IN_FLIGHT": "1",
    "AGENT_RUNTIME_DISCONNECT_POLL_MS": "100",
    "AGENT_RUNTIME_MAX_INCOMPLETE_EVENT_BYTES": "32768",
}


def _fail(reason: str) -> None:
    raise ValueError("knowledge.measure.prepare_" + reason)


def _clean_head(root: Path) -> str:
    try:
        branch = subprocess.check_output(["git", "-C", str(root), "branch", "--show-current"], text=True).strip()
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        status = subprocess.check_output(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
                                         text=True).splitlines()
    except (OSError, subprocess.CalledProcessError):
        _fail("git_invalid")
    if branch != "codex_0915" or not re.fullmatch(r"[0-9a-f]{40}", head) or status:
        _fail("head_not_clean")
    return head


def _running_jar(root: Path) -> bool:
    """Read Java command lines without printing them or stopping any process."""
    command = ["pwsh", "-NoProfile", "-Command",
               "Get-CimInstance Win32_Process -Filter \"name='java.exe'\" | Select-Object -ExpandProperty CommandLine"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=True)
    except (OSError, subprocess.SubprocessError):
        _fail("process_inventory_failed")
    text = result.stdout.casefold().replace("/", "\\")
    return any(str((root / path).resolve()).casefold() in text or Path(path).name.casefold() in text
               for path in _JARS.values())


def build(*, root: Path, run_dir: Path) -> dict[str, Any]:
    root, run_dir = root.resolve(), run_dir.resolve()
    run_parent = root / "agent-runtime/tests/uat"
    if (run_parent.resolve() != run_parent or run_dir.exists() or run_dir.parent != run_parent
            or not _RUN.fullmatch(run_dir.name)):
        _fail("run_directory_invalid")
    for name in ("common-security", "es-query-api", *_SERVICES):
        module = (root / name).resolve()
        target = (module / "target").resolve()
        if (module.parent != root or not (module / "pom.xml").is_file()
                or target != module / "target"):
            _fail("build_target_invalid")
    head = _clean_head(root)
    if _running_jar(root):
        _fail("jar_in_use")
    wrapper = root / "serviceCenter/mvnw.cmd"
    if not wrapper.is_file():
        _fail("maven_wrapper_missing")
    for command in _BUILD_COMMANDS:
        argv = [str(wrapper), *command[1:]]
        try:
            outcome = subprocess.run(argv, cwd=root, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, timeout=900, check=False)
        except (OSError, subprocess.SubprocessError):
            _fail("build_failed")
        if outcome.returncode != 0:
            _fail("build_failed")
    if _clean_head(root) != head:
        _fail("head_drift")
    jars = {path: _sha(root / path) for path in _JARS.values()}
    dependencies = {path: _sha(root / path) for path in _DEPENDENCY_JARS}
    run_dir.mkdir(exist_ok=False)
    attestation = {"schemaVersion": 1, "status": "built_from_clean_head", "branch": "codex_0915",
                   "head": head, "jarSha256": jars, "dependencyJarSha256": dependencies,
                   "commands": _BUILD_COMMANDS}
    _exclusive_json(run_dir / "build-attestation.json", attestation)
    return attestation


def _binding(root: Path, dataset: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    source = dataset["sourceCorpus"]
    alias_name, index_name = source["readAlias"], source["index"]
    with httpx.Client(base_url="http://127.0.0.1:9200", timeout=5.0,
                      follow_redirects=False, trust_env=False) as client:
        alias_response = client.get(f"/_alias/{alias_name}")
        definition_response = client.get(f"/{index_name}")
    if (alias_response.status_code != 200 or definition_response.status_code != 200
            or len(alias_response.content) > 65536 or len(definition_response.content) > 1024 * 1024):
        _fail("es_metadata_unavailable")
    alias = alias_response.json()
    definition = definition_response.json()
    if type(alias) is not dict or set(alias) != {index_name} or type(definition) is not dict or set(definition) != {index_name}:
        _fail("alias_drift")
    flags = alias[index_name].get("aliases", {}).get(alias_name)
    if flags not in ({}, {"is_write_index": False}):
        _fail("alias_flags_invalid")
    item = definition[index_name]
    settings = item["settings"]["index"]
    mapping = item["mappings"]
    mapping_hash = hashlib.sha256((json.dumps(mapping, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")).hexdigest()
    if (settings["uuid"] != source["indexUuid"] or mapping_hash != source["mappingSha256"]
            or not (settings.get("blocks", {}).get("write") in (True, "true")
                    or settings.get("blocks.write") in (True, "true"))):
        _fail("index_metadata_drift")
    mapping_version = mapping["_meta"]["mapping_version"]
    bindings = {}
    for domain, profile in (("tax.policy", "tax-policy-v1"), ("tax.law", "tax-law-v1")):
        canonical = "\n".join((profile, index_name, source["indexUuid"],
                                "tax-knowledge-search-v1", mapping_version))
        bindings[domain] = {"readAlias": alias_name, "indexName": index_name,
                            "indexUuid": source["indexUuid"], "mappingVersion": mapping_version,
                            "mappingSha256": mapping_hash, "fullFingerprint": source["fullFingerprint"],
                            "recordCount": source["recordCount"],
                            "snapshotId": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                            "readPolicyVersion": "tax-public-authenticated-v1"}
    return bindings, flags


def freeze(*, root: Path, run_dir: Path, run_id: str, authorization_reference: str) -> dict[str, Any]:
    root, run_dir = root.resolve(), run_dir.resolve()
    run_parent = root / "agent-runtime/tests/uat"
    if (not _RUN.fullmatch(run_id) or run_dir.name != run_id
            or run_parent.resolve() != run_parent or run_dir.parent != run_parent
            or not run_dir.is_dir() or sorted(path.name for path in run_dir.iterdir()) != ["build-attestation.json"]
            or not re.fullmatch(r"UAT_02:[A-Za-z0-9_-]{5,80}", authorization_reference)):
        _fail("run_directory_invalid")
    attestation_path = run_dir / "build-attestation.json"
    attestation = _read_object(attestation_path)
    try:
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        branch = subprocess.check_output(["git", "-C", str(root), "branch", "--show-current"], text=True).strip()
        status = subprocess.check_output(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
                                         text=True).splitlines()
    except (OSError, subprocess.CalledProcessError):
        _fail("git_invalid")
    expected_status = ["?? " + attestation_path.relative_to(root).as_posix()]
    if (head != attestation.get("head") or branch != "codex_0915" or status != expected_status
            or attestation.get("status") != "built_from_clean_head"
            or attestation.get("commands") != _BUILD_COMMANDS
            or attestation.get("jarSha256") != {path: _sha(root / path) for path in _JARS.values()}
            or attestation.get("dependencyJarSha256") != {path: _sha(root / path) for path in _DEPENDENCY_JARS}):
        _fail("build_attestation_drift")
    dataset_path = root / _DATASET
    dataset = _read_object(dataset_path)
    if len(dataset["cases"]) != 12 or len(dataset["sources"]) != 13:
        _fail("dataset_invalid")
    bindings, flags = _binding(root, dataset)
    assets = {path: _sha(root / path) for path in (*_ASSETS, *_JARS.values(), *_DEPENDENCY_JARS)}
    count = bindings["tax.policy"]["recordCount"]
    prompts = {"action_selection": assets[_ASSETS[9]], "knowledge_rewrite": assets[_ASSETS[10]],
               "knowledge_summary": assets[_ASSETS[11]]}
    manifest = {"schemaVersion": 1, "runId": run_id, "branch": branch, "frozenHead": head,
                "authorizationReference": authorization_reference, "datasetPath": _DATASET,
                "datasetSha256": assets[_DATASET], "model": "deepseek-flash",
                "taskVersions": {task.value: version for task, version in _TASKS.items()},
                "assetSha256": assets, "indexBindings": bindings,
                "policyCatalogSha256": assets[_ASSETS[8]],
                "springBaseUrl": "http://127.0.0.1:19202", "runtimePort": 19203,
                "budgets": _MAX, "runtimeEnv": _ENV, "subject": _SUBJECT, "cases": dataset["cases"],
                "sources": dataset["sources"], "humanRubric": dataset["humanRubric"],
                "answerDesign": "Summary9", "promptSha256": prompts,
                "jarBuildHead": head,
                "buildAttestationPath": attestation_path.relative_to(root).as_posix(),
                "buildAttestationSha256": _sha(attestation_path), "aliasFlags": flags,
                "snapshotPreflightEsHttpRequests": 4 + (count + 249) // 250,
                "snapshotPostflightEsHttpRequests": 4 + (count + 249) // 250,
                "runtimeMetadataEsHttpMax": 48}
    manifest_path = run_dir / "manifest.json"
    _exclusive_json(manifest_path, manifest)
    _exclusive_json(run_dir / "authorization.json", {"schemaVersion": 1,
        "status": "authorized_unconsumed", "runId": run_id, "frozenHead": head,
        "manifestSha256": _sha(manifest_path), "datasetSha256": assets[_DATASET],
        "authorizationReference": authorization_reference, "subject": _SUBJECT,
        "maximumModelRequests": 36, "singleUse": True, "retryAllowed": False})
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("build", "freeze"))
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--authorization-reference")
    args = parser.parse_args()
    try:
        if args.phase == "build":
            build(root=args.repository, run_dir=args.run_dir)
        else:
            if not args.run_id or not args.authorization_reference:
                _fail("binding_missing")
            freeze(root=args.repository, run_dir=args.run_dir, run_id=args.run_id,
                   authorization_reference=args.authorization_reference)
    except (ValueError, MeasurementError) as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
