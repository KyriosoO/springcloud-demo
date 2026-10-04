"""Offline actual Java keyword projection; no server, HTTP, inference or run writer.

Build both isolated archives from the same committed production source. Replace
only the old arm's helper blob, compare all other compiled application classes,
YAML and dependency bytes, then invoke the actual package-private body builder.
The returned hashes are preparation evidence, never real-operation authority.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
from typing import Any, Iterator
from zipfile import BadZipFile, ZipFile

from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.evaluation.knowledge.rebuild_b_local_transport import _request_hashes
from tests.evaluation.knowledge.rebuild_document_number_transport import (
    AttemptLedger, PhysicalSearchGate,
)

INSPECTOR = Path(__file__).with_name("DocumentNumberProjection.java")
CONFIG = "es-query-service/src/main/resources/application-knowledge-live.yml"
CLASS_HELPER = "BOOT-INF/classes/com/dylan/esquery/service/DocumentNumberQuery"
JAR_CONFIG = "BOOT-INF/classes/application-knowledge-live.yml"
_ENV = ("SystemRoot", "SystemDrive", "PATH", "JAVA_HOME", "TEMP", "TMP",
        "USERPROFILE", "APPDATA", "LOCALAPPDATA")
_DEVICES = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$", "CLOCK$"} | {
    prefix + number for prefix in ("COM", "LPT") for number in "123456789¹²³"}


@dataclass(frozen=True, slots=True)
class ProjectionRow:
    case_id: str
    domain: str
    raw_sha256: str
    canonical_sha256: str


@dataclass(frozen=True, slots=True)
class ProjectionProof:
    arm: str
    jar_sha256: str
    config_sha256: str
    inspector_sha256: str
    shared_classes_sha256: str
    dependencies_sha256: str
    helper_classes_sha256: str
    rows: tuple[ProjectionRow, ...]

    def for_case(self, case: p.ComparisonCase) -> tuple[tuple[str, str], ...]:
        rows = tuple((row.domain, row.canonical_sha256) for row in self.rows if row.case_id == case.case_id)
        p.require(tuple(domain for domain, _ in rows) == case.plan.selected_domain_ids,
                  "projection_case_mismatch")
        return rows


@dataclass(slots=True)
class ProjectedJavaPair:
    """Same attested binaries kept alive until owned runtime cleanup is proven.

    This lease does not authorize startup. An authorized outer executor must
    register its resources before using it and release them before lease exit.
    """
    draft: p.DraftProtocol
    java: Path
    jars: tuple[Path, ...]
    configs: tuple[Path, ...]
    proofs: tuple[ProjectionProof, ...]
    report: dict[str, object]
    resources_released: bool = True

    def verify_artifacts(self) -> None:
        p.require(len(self.jars) == len(self.proofs) == len(self.configs) == 2,
                  "offline_pair_invalid")
        for jar, proof in zip(self.jars, self.proofs, strict=True):
            p.require(jar.is_file() and not jar.is_symlink()
                      and sha256(jar.read_bytes()).hexdigest() == proof.jar_sha256,
                      "offline_runtime_artifact_drift")


def _safe_env() -> dict[str, str]:
    # No model key, JWT, Java agents/options or Maven overrides are inherited.
    return {key: os.environ[key] for key in _ENV if key in os.environ}


def _command(args: list[str], *, cwd: Path, input_raw: bytes | None = None,
             timeout: int = 60, version_output: bool = False) -> bytes:
    failed = False
    result: subprocess.CompletedProcess[bytes] | None = None
    try:
        result = subprocess.run(args, cwd=cwd, env=_safe_env(), input=input_raw,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT if version_output else subprocess.DEVNULL,
            timeout=timeout, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        failed = True
    if failed or result is None or result.returncode != 0 or len(result.stdout) > 2 * 1024 * 1024:
        raise p.ProtocolError("offline_command_failed")
    return result.stdout


def _zip_key(name: str, *, directory: bool = False) -> str:
    path = PurePosixPath(name)
    p.require(type(name) is str and bool(name) and not path.is_absolute()
        and ".." not in path.parts and name == str(path) + ("/" if directory else "")
        and all(part and part not in (".", "..") and not part.endswith((".", " "))
                and part.split(".", 1)[0].upper() not in _DEVICES
                and not any(ord(char) < 32 or char in '<>:"|?*\\' for char in part)
                for part in path.parts), "offline_archive_invalid")
    return str(path).casefold()


def _entry_map(raw: bytes) -> dict[str, bytes]:
    """Bounded ZIP reader, with no traversal, devices, links or duplicate paths."""
    p.require(type(raw) is bytes and 0 < len(raw) <= 512 * 1024 * 1024, "offline_archive_invalid")
    failed = False
    values: dict[str, bytes] = {}
    try:
        with ZipFile(BytesIO(raw)) as archive:
            entries = archive.infolist()
            p.require(len(entries) <= 50000 and sum(item.file_size for item in entries) <= 1024 * 1024 * 1024,
                      "offline_archive_invalid")
            seen: set[str] = set()
            for item in entries:
                key = _zip_key(item.filename, directory=item.is_dir())
                p.require(item.orig_filename == item.filename and key not in seen
                    and stat.S_IFMT(item.external_attr >> 16) in (0, stat.S_IFREG, stat.S_IFDIR)
                    and item.file_size <= 256 * 1024 * 1024
                    and not item.flag_bits & 1, "offline_archive_invalid")
                seen.add(key)
                if not item.is_dir():
                    values[item.filename] = archive.read(item)
    except (BadZipFile, OSError, RuntimeError, ValueError):
        failed = True
    if failed:
        raise p.ProtocolError("offline_archive_invalid")
    return values


def _extract(values: dict[str, bytes], root: Path) -> None:
    keys = tuple(_zip_key(name) for name in values)
    p.require(len(set(keys)) == len(keys), "offline_archive_invalid")
    for name, raw in values.items():
        target = root.joinpath(*PurePosixPath(name).parts)
        p.require(target.resolve().is_relative_to(root.resolve()), "offline_archive_invalid")
        target.parent.mkdir(parents=True, exist_ok=True)
        # Only generated temporary build inputs; never edit the working checkout.
        with target.open("xb") as stream:
            stream.write(raw)


def _fingerprint(values: dict[str, bytes]) -> str:
    p.require(bool(values), "offline_artifact_invalid")
    return sha256(p.canonical({name: sha256(raw).hexdigest() for name, raw in values.items()})).hexdigest()


def _artifacts(jar_raw: bytes, *, config_raw: bytes) -> tuple[dict[str, bytes], tuple[str, str, str]]:
    values = _entry_map(jar_raw)
    p.require(values.get(JAR_CONFIG) == config_raw, "offline_config_drift")
    classes = {name: raw for name, raw in values.items()
               if name.startswith("BOOT-INF/classes/") and name.endswith(".class")
               and not (name == CLASS_HELPER + ".class" or name.startswith(CLASS_HELPER + "$"))}
    helpers = {name: raw for name, raw in values.items()
               if name == CLASS_HELPER + ".class" or name.startswith(CLASS_HELPER + "$") and name.endswith(".class")}
    dependencies = {name: raw for name, raw in values.items()
                    if name.startswith("BOOT-INF/lib/") and name.endswith(".jar")}
    p.require(CLASS_HELPER + ".class" in helpers, "offline_artifact_invalid")
    return values, (_fingerprint(classes), _fingerprint(dependencies), _fingerprint(helpers))


def _parse_projection(raw: bytes, *, draft: p.DraftProtocol, arm: str) -> tuple[ProjectionRow, ...]:
    expected = tuple((case, domain) for case in draft.cases for domain in case.plan.selected_domain_ids)
    lines = raw.splitlines()
    p.require(len(lines) == len(expected) == 11 and all(lines), "offline_projection_invalid")
    rows = []
    for line, (case, domain) in zip(lines, expected, strict=True):
        value = p._decode(line)
        p.require(set(value) == {"caseId", "domain", "request"}
                  and value["caseId"] == case.case_id and value["domain"] == domain
                  and type(value["request"]) is dict, "offline_projection_invalid")
        # Do not reserialize numeric literals before the physical witness hash.
        # Inspector writes its request JSON as the exact nested value; decode
        # using a raw decoder span so this is also valid for future decimal boosts.
        text = line.decode("utf-8")
        match = re.search(r'"request"\s*:', text)
        p.require(match is not None, "offline_projection_invalid")
        assert match is not None
        start = match.end()
        while text[start].isspace():
            start += 1
        _, end = json.JSONDecoder().raw_decode(text, start)
        body = text[start:end].encode("utf-8")
        raw_hash, canonical_hash = _request_hashes("POST", body)
        row = ProjectionRow(case.case_id, domain, raw_hash, canonical_hash)
        # Reuse the existing physical shape guard, but its sender is forbidden.
        # A syntactically accepted request reaches the callback and raises this
        # private sentinel; there is no HTTP call or successful receipt.
        hashes = tuple((d, canonical_hash if d == domain else "0" * 64)
                       for d in case.plan.selected_domain_ids)
        gate = PhysicalSearchGate(case=case, arm=arm, read_alias="offline-projection",
            vector=(0.0,) * 1024, ledger=AttemptLedger((("physicalSearch", 1),)), keyword_sha256=hashes)
        called = False
        def forbidden_send(_: bytes) -> Any:
            nonlocal called
            called = True
            raise RuntimeError("offline_no_network")
        try:
            gate.forward(method="POST", path="/offline-projection/_search", body=body, send=forbidden_send)
        except p.ProtocolError as error:
            p.require(str(error) == "physical_transport_failed" and called, "offline_projection_invalid")
        else:
            raise p.ProtocolError("offline_projection_invalid")
        rows.append(row)
    return tuple(rows)


def _project(jar_raw: bytes, *, draft: p.DraftProtocol, arm: str, config_raw: bytes,
             inspector_raw: bytes, java: Path, javac: Path, root: Path) -> ProjectionProof:
    values, fingerprints = _artifacts(jar_raw, config_raw=config_raw)
    _extract(values, root)
    source = root / "DocumentNumberProjection.java"
    with source.open("xb") as stream:
        stream.write(inspector_raw)
    classes = root / "inspector-classes"
    classes.mkdir()
    classpath = os.pathsep.join((str(root / "BOOT-INF/classes"), str(root / "BOOT-INF/lib/*")))
    _command([str(javac), "-proc:none", "-encoding", "UTF-8", "-cp", classpath,
              "-d", str(classes), str(source)], cwd=root)
    inputs = [{"caseId": case.case_id, "domain": domain, "question": case.plan.original_question}
              for case in draft.cases for domain in case.plan.selected_domain_ids]
    raw = _command([str(java), "-Dfile.encoding=UTF-8", "-cp", str(classes) + os.pathsep + classpath,
        "com.dylan.esquery.service.DocumentNumberProjection", str(root / JAR_CONFIG)], cwd=root,
        input_raw=p.canonical(inputs))
    rows = _parse_projection(raw, draft=draft, arm=arm)
    return ProjectionProof(arm, sha256(jar_raw).hexdigest(), sha256(config_raw).hexdigest(),
                           sha256(inspector_raw).hexdigest(), *fingerprints, rows)


def _validate_pair(proofs: tuple[ProjectionProof, ...], draft: p.DraftProtocol) -> None:
    p.require(len(proofs) == 2 and tuple(proof.arm for proof in proofs) == p.ARMS,
              "offline_pair_invalid")
    old, current = proofs
    for field in ("config_sha256", "inspector_sha256", "shared_classes_sha256", "dependencies_sha256"):
        p.require(getattr(old, field) == getattr(current, field), "offline_pair_" + field + "_drift")
    p.require(old.helper_classes_sha256 != current.helper_classes_sha256, "offline_pair_helper_drift")
    expected = tuple((case.case_id, domain) for case in draft.cases for domain in case.plan.selected_domain_ids)
    p.require(all(tuple((row.case_id, row.domain) for row in proof.rows) == expected for proof in proofs),
              "offline_pair_invalid")
    for left, right in zip(old.rows, current.rows, strict=True):
        p.require(left.domain != "tax.law" or left.canonical_sha256 == right.canonical_sha256,
                  "offline_law_drift")


@contextmanager
def projected_java_pair(root: Path = p.ROOT) -> Iterator[ProjectedJavaPair]:
    """Build once, inspect those exact JARs, then lease them to one caller.

    Only owned build directories are removed. Failed runtime cleanup retains
    the directory; never try removing an in-use JAR or stopping an unknown PID.
    """
    draft = p.draft_from_repository(root)
    timestamp = p._git(root, "show", "-s", "--format=%ct", draft.frozen_head).decode("ascii").strip()
    p.require(re.fullmatch(r"[0-9]{10}", timestamp) is not None, "offline_timestamp_invalid")
    config_raw = p._git(root, "show", f"{draft.frozen_head}:{CONFIG}")
    inspector_raw = INSPECTOR.read_bytes()
    tool_raw = Path(__file__).read_bytes()
    p.require(0 < len(inspector_raw) <= 65536, "offline_inspector_invalid")
    archive_raw = p._git(root, "archive", "--format=zip", draft.frozen_head)
    sources = _entry_map(archive_raw)
    p.require(sources.get(CONFIG) == config_raw, "offline_config_drift")
    maven_name = shutil.which("mvn")
    java_home = Path(os.environ.get("JAVA_HOME", ""))
    p.require(maven_name is not None and java_home.is_absolute(), "offline_toolchain_unavailable")
    assert maven_name is not None
    maven = Path(maven_name).resolve(strict=True)
    java = java_home.joinpath("bin", "java.exe" if os.name == "nt" else "java").resolve(strict=True)
    javac = java.with_name("javac.exe" if os.name == "nt" else "javac").resolve(strict=True)
    p.require(all(path.is_file() for path in (maven, java, javac)), "offline_toolchain_unavailable")
    version = _command([str(java), "-version"], cwd=root, timeout=10, version_output=True)
    p.require(len(version) <= 16384
              and re.search(rb'(?:openjdk|java) version "25(?:\.|\")', version) is not None,
              "offline_toolchain_unavailable")
    maven_home = maven.parent.parent
    loaders = tuple((maven_home / "boot").glob("plexus-classworlds-*.jar"))
    maven_config = maven_home / "bin/m2.conf"
    p.require(len(loaders) == 1 and loaders[0].is_file() and maven_config.is_file(),
              "offline_toolchain_unavailable")
    proofs = []
    jars: list[Path] = []
    configs: list[Path] = []
    temporary_root = Path(tempfile.mkdtemp(prefix="knowledge-document-number-offline-")).resolve()
    temporary_parent = temporary_root.parent
    lease: ProjectedJavaPair | None = None
    try:
        for arm in p.ARMS:
            build = temporary_root / arm
            build.mkdir()
            arm_sources = dict(sources)
            arm_sources[p.HELPER] = p._git(root, "show", f"{p.OLD_HEAD if arm == 'old' else draft.frozen_head}:{p.HELPER}")
            p.require(sha256(arm_sources[p.HELPER]).hexdigest() ==
                (draft.old_helper_sha256 if arm == "old" else draft.current_helper_sha256), "offline_helper_drift")
            _extract(arm_sources, build)
            # Invoke Maven's Java launcher directly, not mvn.cmd: the checked
            # Java25 is also the build JVM, and a timeout cannot orphan the
            # normal cmd->java child process used by the Windows wrapper.
            _command([str(java), "-classpath", str(loaders[0]),
                "-Dclassworlds.conf=" + str(maven_config), "-Dmaven.home=" + str(maven_home),
                "-Dmaven.multiModuleProjectDirectory=" + str(build / "serviceCenter"),
                "org.codehaus.plexus.classworlds.launcher.Launcher",
                "--offline", "--batch-mode", "-f", str(build / "serviceCenter/pom.xml"),
                "-pl", ":es-query-service", "-am", "-DskipTests",
                "-Dproject.build.outputTimestamp=" + timestamp, "package"], cwd=build / "serviceCenter", timeout=900)
            jar = build / "es-query-service/target/es-query-service-0.0.1-SNAPSHOT.jar"
            inspect = temporary_root / (arm + "-projection")
            inspect.mkdir()
            proofs.append(_project(jar.read_bytes(), draft=draft, arm=arm, config_raw=config_raw,
                                   inspector_raw=inspector_raw, java=java, javac=javac, root=inspect))
            jars.append(jar)
            configs.append(build / "config-service/src/main/resources/config")
        pair = tuple(proofs)
        _validate_pair(pair, draft)
        p.require(p.draft_from_repository(root) == draft and INSPECTOR.read_bytes() == inspector_raw
                  and Path(__file__).read_bytes() == tool_raw, "offline_source_drift")
        report: dict[str, object] = {"kind": "document_number_offline_projection_v1", "sourceHead": draft.frozen_head,
        "sourceArchiveSha256": sha256(archive_raw).hexdigest(), "oldHelperSourceHead": p.OLD_HEAD,
        "buildOutputTimestamp": timestamp,
        "helperSha256": {"old": draft.old_helper_sha256, "current": draft.current_helper_sha256},
        "projectionToolSha256": sha256(tool_raw).hexdigest(),
        "toolchainSha256": {name: sha256(path.read_bytes()).hexdigest()
                            for name, path in (("mavenWrapperReference", maven), ("java", java), ("javac", javac),
                                               ("mavenLoader", loaders[0]), ("mavenConfig", maven_config))},
        "proofs": [asdict(proof) for proof in pair], "realExecutionAllowed": False,
        "qualityAssessment": "Not assessed", "servicesStarted": 0, "networkRequests": 0,
        "mavenTestsExecuted": False,
        "runtimeSnapshotStatus": "not_observed;projection_only"}
        lease = ProjectedJavaPair(draft, java, tuple(jars), tuple(configs), pair, report)
        lease.verify_artifacts()
        yield lease
        p.require(p.draft_from_repository(root) == draft and INSPECTOR.read_bytes() == inspector_raw
                  and Path(__file__).read_bytes() == tool_raw, "offline_source_drift")
    finally:
        if lease is None or lease.resources_released:
            # This is exactly the unique mkdtemp target, not a computed repo or
            # user directory. Revalidate identity before recursive removal.
            p.require(not temporary_root.is_symlink() and temporary_root.resolve() == temporary_root
                      and temporary_root.parent == temporary_parent
                      and temporary_root.name.startswith("knowledge-document-number-offline-"),
                      "offline_temporary_target_invalid")
            failed = False
            try:
                shutil.rmtree(temporary_root)
            except OSError:
                failed = True
            if failed:
                raise p.ProtocolError("offline_temporary_cleanup_failed") from None
        else:
            raise p.ProtocolError("offline_owned_cleanup_incomplete") from None


def offline_project_repository(root: Path = p.ROOT) -> dict[str, object]:
    """Compatibility preview: no runtime resources, release before reporting."""
    with projected_java_pair(root) as lease:
        report = dict(lease.report)
    return {**report, "temporaryBuildsRemoved": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline-project", action="store_true", required=True)
    parser.parse_args()
    print(p.canonical(offline_project_repository()).decode("utf-8"), end="")


if __name__ == "__main__":
    main()
