from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any, Literal, cast

from tests.integration.adapters.business_egress_live_bootstrap import (
    BootstrapBinding,
    load_strict_json,
    sha256_file,
)


_COMMIT = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")


def materialize_manifest_at_commit(
    manifest: Mapping[str, object],
    *,
    repository_root: Path,
    destination: Path,
    source_commit: str,
    collection_names: Sequence[str],
) -> Path:
    """Build a temporary repository view for strict historical manifest validation."""
    if _COMMIT.fullmatch(source_commit) is None:
        raise AssertionError("invalid frozen source commit")
    destination.mkdir(parents=True, exist_ok=True)
    expected_by_path = _manifest_hashes(manifest, collection_names=collection_names)
    for relative, expected_sha256 in expected_by_path.items():
        completed = subprocess.run(
            ["git", "show", f"{source_commit}:{relative}"],
            cwd=repository_root,
            check=False,
            capture_output=True,
        )
        if completed.returncode != 0:
            raise AssertionError(f"frozen asset missing at source commit: {relative}")
        payload = _match_checkout_payload(completed.stdout, expected_sha256)
        if payload is None:
            raise AssertionError(f"frozen asset hash mismatch: {relative}")
        target = _safe_target(destination, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    return destination


def bind_historical_bootstrap(
    *,
    repository_root: Path,
    manifest_path: Path,
    authorization_path: Path,
    destination: Path,
    executable_paths: frozenset[str],
) -> BootstrapBinding:
    """Validate immutable history without requiring a rebuildable historical JAR."""
    manifest = load_strict_json(manifest_path)
    authorization = load_strict_json(authorization_path)
    assert set(manifest) == {
        "schemaVersion",
        "status",
        "runId",
        "authorizationReference",
        "domain",
        "wrapperSourceCommit",
        "candidate",
        "buildProvenance",
        "assetHashes",
        "executableHashes",
        "historyHashes",
        "executionBoundary",
    }
    assert manifest["schemaVersion"] == 2
    assert manifest["status"] == "prepared_unconsumed"
    candidate = manifest["candidate"]
    assert isinstance(candidate, Mapping)
    assert set(candidate) == {
        "runId",
        "manifestPath",
        "manifestSha256",
        "authorizationPath",
        "authorizationSha256",
    }
    manifest_sha256 = sha256_file(manifest_path)
    binding = BootstrapBinding(
        run_id=str(manifest["runId"]),
        manifest_sha256=manifest_sha256,
        authorization_reference=str(manifest["authorizationReference"]),
        domain=cast(Literal["employee", "transaction"], manifest["domain"]),
        wrapper_source_commit=str(manifest["wrapperSourceCommit"]),
        candidate_run_id=str(candidate["runId"]),
        candidate_manifest_sha256=str(candidate["manifestSha256"]),
        candidate_authorization_sha256=str(candidate["authorizationSha256"]),
    )
    binding.validate()
    assert authorization == {
        "schemaVersion": 2,
        "runId": binding.run_id,
        "manifestSha256": binding.manifest_sha256,
        "authorizationReference": binding.authorization_reference,
        "liveExecutionAuthorized": False,
    }
    build = manifest["buildProvenance"]
    assert isinstance(build, Mapping)
    assert set(build) == {"sourceCommit", "command", "javaVersion", "mavenVersion"}
    assert build["sourceCommit"] == binding.wrapper_source_commit
    assert isinstance(build["command"], str) and build["command"]
    assert isinstance(build["javaVersion"], str) and build["javaVersion"].startswith("25.")
    assert isinstance(build["mavenVersion"], str) and build["mavenVersion"].startswith("3.")
    assert manifest["executionBoundary"] == {
        "liveExecutionAuthorized": False,
        "sideEffectsAllowed": False,
        "candidateInvocationsMaximum": 1,
        "retryAllowed": False,
        "resumeAllowed": False,
    }
    materialize_manifest_at_commit(
        manifest,
        repository_root=repository_root,
        destination=destination,
        source_commit=binding.wrapper_source_commit,
        collection_names=("assetHashes", "historyHashes"),
    )
    assert frozenset(
        _manifest_hashes(manifest, collection_names=("executableHashes",))
    ) == executable_paths
    materialize_current_hash_bindings(
        {
            str(candidate["manifestPath"]): binding.candidate_manifest_sha256,
            str(candidate["authorizationPath"]): binding.candidate_authorization_sha256,
        },
        repository_root=repository_root,
        destination=destination,
    )
    return binding


def write_manifest_bound_to_current_tree(
    manifest: Mapping[str, object],
    *,
    repository_root: Path,
    destination: Path,
    collection_names: Sequence[str],
) -> Path:
    """Create a non-live temporary manifest for testing current preflight behavior."""
    rebound = copy.deepcopy(dict(manifest))
    for collection_name in collection_names:
        rows = rebound.get(collection_name)
        if not isinstance(rows, list) or not rows:
            raise AssertionError(f"invalid manifest collection: {collection_name}")
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
                raise AssertionError(f"invalid manifest row: {collection_name}")
            relative = row["path"]
            if not isinstance(relative, str):
                raise AssertionError(f"invalid manifest path: {collection_name}")
            source = _safe_target(repository_root, relative)
            if not source.is_file():
                raise AssertionError(f"current asset missing: {relative}")
            row["sha256"] = _sha256_file(source)
    destination.write_text(
        json.dumps(rebound, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return destination


def materialize_manifest_from_current_hashes(
    manifest: Mapping[str, object],
    *,
    repository_root: Path,
    destination: Path,
    collection_names: Sequence[str],
) -> Path:
    """Copy still-exact non-source assets, such as a locally built frozen JAR."""
    destination.mkdir(parents=True, exist_ok=True)
    expected_by_path = _manifest_hashes(manifest, collection_names=collection_names)
    for relative, expected_sha256 in expected_by_path.items():
        source = _safe_target(repository_root, relative)
        if not source.is_file() or _sha256_file(source) != expected_sha256:
            raise AssertionError(f"current frozen asset hash mismatch: {relative}")
        target = _safe_target(destination, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    return destination


def materialize_current_hash_bindings(
    bindings: Mapping[str, str],
    *,
    repository_root: Path,
    destination: Path,
) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    for relative, expected_sha256 in bindings.items():
        if _SHA256.fullmatch(expected_sha256) is None:
            raise AssertionError(f"invalid current hash binding: {relative}")
        source = _safe_target(repository_root, relative)
        if not source.is_file() or _sha256_file(source) != expected_sha256:
            raise AssertionError(f"current frozen asset hash mismatch: {relative}")
        target = _safe_target(destination, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    return destination


def _manifest_hashes(
    manifest: Mapping[str, object], *, collection_names: Sequence[str]
) -> dict[str, str]:
    result: dict[str, str] = {}
    for collection_name in collection_names:
        rows = manifest.get(collection_name)
        if not isinstance(rows, list) or not rows:
            raise AssertionError(f"invalid manifest collection: {collection_name}")
        for row_value in rows:
            if (
                not isinstance(row_value, Mapping)
                or "path" not in row_value
                or "sha256" not in row_value
            ):
                raise AssertionError(f"invalid manifest row: {collection_name}")
            relative = row_value["path"]
            expected_sha256 = row_value["sha256"]
            if (
                not isinstance(relative, str)
                or not isinstance(expected_sha256, str)
                or _SHA256.fullmatch(expected_sha256) is None
            ):
                raise AssertionError(f"invalid manifest hash binding: {collection_name}")
            prior = result.setdefault(relative, expected_sha256)
            if prior != expected_sha256:
                raise AssertionError(f"conflicting manifest hash binding: {relative}")
    return result


def _safe_target(root: Path, relative: str) -> Path:
    posix = PurePosixPath(relative)
    if posix.is_absolute() or ".." in posix.parts:
        raise AssertionError(f"unsafe manifest path: {relative}")
    resolved_root = root.resolve()
    target = resolved_root.joinpath(*posix.parts).resolve()
    if target != resolved_root and resolved_root not in target.parents:
        raise AssertionError(f"manifest path escapes root: {relative}")
    return target


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _match_checkout_payload(payload: bytes, expected_sha256: str) -> bytes | None:
    normalized = payload.replace(b"\r\n", b"\n")
    variants = [normalized, normalized.replace(b"\n", b"\r\n")]
    if normalized.endswith(b"\n"):
        variants.extend(
            (
                normalized[:-1],
                normalized[:-1].replace(b"\n", b"\r\n") + b"\n",
                normalized[:-1].replace(b"\n", b"\r\n"),
            )
        )
    for candidate in variants:
        if hashlib.sha256(candidate).hexdigest() == expected_sha256:
            return candidate
    return None
