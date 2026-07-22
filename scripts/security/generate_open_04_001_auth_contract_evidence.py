#!/usr/bin/env python3
"""Generate closed Auth-contract evidence from actual Surefire XML reports and source hashes."""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

try:
    from open_04_001_evidence_io import (
        AUTH_CONTRACTS, atomic_write_bytes_new, atomic_write_json_new, sha256_file,
    )
except ModuleNotFoundError:  # importlib-based unit tests run from repository root
    from scripts.security.open_04_001_evidence_io import (
        AUTH_CONTRACTS, atomic_write_bytes_new, atomic_write_json_new, sha256_file,
    )


SCHEMA = "open-04-001-auth-contract-verification-v0.1"
REPORTS = (
    "auth-service/target/surefire-reports/TEST-com.dylan.authcenter.agent.permission.AgentPermissionInternalControllerTest.xml",
    "auth-service/target/surefire-reports/TEST-com.dylan.authcenter.agent.permission.AgentPermissionProjectionServiceTest.xml",
    "auth-service/target/surefire-reports/TEST-com.dylan.authcenter.agent.permission.AgentPermissionServiceTokenSecurityTest.xml",
    "auth-service/target/surefire-reports/TEST-com.dylan.authcenter.agent.permission.AgentPermissionSpringContextTest.xml",
    "agent-service/target/surefire-reports/TEST-com.dylan.baseline.agent.security.authorization.AuthPermissionAuthorityAdapterTest.xml",
    "agent-service/target/surefire-reports/TEST-com.dylan.baseline.agent.security.authorization.internal.HttpAuthPermissionAuthorityAdapterTest.xml",
    "agent-service/target/surefire-reports/TEST-com.dylan.baseline.agent.security.authorization.internal.AuthPermissionCrossServiceIntegrationTest.xml",
    "agent-service/target/surefire-reports/TEST-com.dylan.baseline.agent.security.migration.AuthFieldMigrationVerifierTest.xml",
)
SOURCE_REFS = (
    "auth-service/src/main/java/com/dylan/authcenter/agent/permission/api/AgentPermissionResolveResponse.java",
    "auth-service/src/main/java/com/dylan/authcenter/agent/permission/AgentPermissionProjectionService.java",
    "auth-service/src/main/resources/agent-rbac.yml",
    "agent-service/src/main/java/com/dylan/baseline/agent/security/authorization/internal/AuthPermissionAuthorityAdapter.java",
    "agent-service/src/main/java/com/dylan/baseline/agent/security/authorization/internal/AuthPermissionWireResponse.java",
    "agent-service/src/main/java/com/dylan/baseline/agent/security/migration/AuthFieldMigrationComparator.java",
    "agent-service/src/main/java/com/dylan/baseline/agent/security/migration/AuthFieldMigrationResolution.java",
)
def generate(root: Path, repository_revision: str, report_snapshot_dir: str) -> dict:
    if re.fullmatch(r"[0-9a-f]{40}", repository_revision) is None:
        raise ValueError("repositoryRevision must be a full lowercase Git commit SHA")
    if not report_snapshot_dir or "\\" in report_snapshot_dir or Path(report_snapshot_dir).is_absolute():
        raise ValueError("report snapshot directory must be a canonical repository-relative path")
    resolved_root = root.resolve()
    snapshot_dir = (resolved_root / report_snapshot_dir).resolve()
    try:
        snapshot_dir.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("report snapshot directory escapes repository root") from exc
    if snapshot_dir.exists():
        raise FileExistsError("report snapshot directory already exists")
    tests = failures = errors = skipped = 0
    reports = []
    for relative in REPORTS:
        path = root / relative
        if not path.is_file():
            raise ValueError(f"required Surefire report is missing: {relative}")
        suite = ET.parse(path).getroot()
        tests += int(suite.attrib.get("tests", "0"))
        failures += int(suite.attrib.get("failures", "0"))
        errors += int(suite.attrib.get("errors", "0"))
        skipped += int(suite.attrib.get("skipped", "0"))
        reports.append((path, Path(relative).name))
    source_hashes = {}
    for relative in SOURCE_REFS:
        path = root / relative
        if not path.is_file():
            raise ValueError(f"required Auth contract source is missing: {relative}")
        source_hashes[relative] = sha256_file(path)
    passed = tests > 0 and failures == 0 and errors == 0 and skipped == 0
    if not passed:
        raise ValueError("Auth contract test reports are not a complete pass")
    snapshot_dir.mkdir()
    report_hashes = {}
    for source, name in reports:
        relative = (Path(report_snapshot_dir) / name).as_posix()
        target = resolved_root / relative
        atomic_write_bytes_new(target, source.read_bytes())
        report_hashes[relative] = sha256_file(target)
    return {
        "schemaVersion": SCHEMA,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "repositoryRevision": repository_revision,
        "passed": True,
        "testsRun": tests,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "validatedContracts": list(AUTH_CONTRACTS),
        "reportHashes": dict(sorted(report_hashes.items())),
        "sourceHashes": dict(sorted(source_hashes.items())),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--repository-revision", required=True)
    parser.add_argument("--report-snapshot-dir", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        atomic_write_json_new(args.output, generate(
            args.root.resolve(), args.repository_revision, args.report_snapshot_dir))
    except (OSError, ValueError, ET.ParseError) as exc:
        print(f"OPEN-04-001 AUTH CONTRACT EVIDENCE BLOCKED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
