"""One authorized seven-case batch; reuse evidence without replaying old runs."""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

from tests.system_e2e import knowledge_stage_b_uat as legacy
from tests.system_e2e import knowledge_stage_b_uat_v2 as v2
from tests.system_e2e import knowledge_stage_b_uat_v6 as previous
from tests.system_e2e.knowledge_stage_b_cases import CASES as FULL_CASES
from tests.system_e2e.test_knowledge_stage_b_run_06_history import HASHES as RUN06_HASHES, HEAD as RUN06_HEAD

RUN_ID = "knowledge-stage-b-uat-v7-20260907-run-07"
REFERENCE = "P3_00:WP-KRETRIEVAL-UAT-01/run-07"
CASES = FULL_CASES[3:]
LIMITS = dict(e2e=7, model=21, search=28, embedding=14, rerank=14, business=0, retry=0, resume=0)
TOTAL_LIMITS = {**v2.TOTAL_LIMITS, "e2e": 21}
COMPATIBLE_HEAD = "550b012ad390463816372054d1c87f5877209f40"
COMPATIBLE_CHANGES = (
    "agent-runtime/src/agent_runtime/bootstrap.py",
    "agent-runtime/src/agent_runtime/knowledge/semantic_planner.py",
    "agent-runtime/src/agent_runtime/knowledge/tax_question_semantics.py",
)
PRODUCTION_PREFIXES = (
    "agent-runtime/src/", "es-query-service/src/main/", "agent-service/src/main/",
    "agent-contracts/", "common-security/src/main/", "auth-service/src/main/",
    "config-service/src/main/resources/config/", "serviceCenter/knowledge-runtime-binding.v1.json",
)
REUSED_EVIDENCE = dict(
    runId=previous.RUN_ID, frozenHead=RUN06_HEAD, resultSha256=RUN06_HASHES["result.json"],
    caseIds=[item["caseId"] for item in FULL_CASES[:3]],
    compatibilityVersion="stage-b-guard-reuse-v1", compatibleSourceCommit=COMPATIBLE_HEAD,
)


def same_json(left, right):
    # bool与整数、小数与整数不能凭Python等值比较互相冒充。
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def strict_json(raw):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("stage_b.manifest_json_invalid")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("stage_b.manifest_json_invalid")

    value = json.loads(raw, object_pairs_hook=object_pairs, parse_constant=invalid_constant)
    if type(value) is not dict:
        raise ValueError("stage_b.manifest_json_invalid")
    return value


@contextmanager
def input_bindings():
    with (patch.multiple(legacy, RUN_ID=RUN_ID, CASES=CASES, LIMITS=LIMITS),
          patch.object(v2, "TOTAL_LIMITS", TOTAL_LIMITS)):
        yield


def run06_assets():
    root = Path(__file__).with_name("knowledge_stage_b_run_06")
    if any(legacy.digest((root / name).read_bytes()) != sha for name, sha in RUN06_HASHES.items()):
        raise ValueError("stage_b.prior_run_changed")
    return json.loads((root / "manifest.json").read_bytes()), json.loads((root / "result.json").read_bytes())


def prior_bindings():
    with input_bindings():
        rows = previous.prior_bindings()
    _, result = run06_assets()
    if result["status"] != "failed" or result["runId"] != previous.RUN_ID:
        raise ValueError("stage_b.prior_status_invalid")
    rows.append(dict(runId=result["runId"], hashes=RUN06_HASHES, calls=result["totals"]))
    for key, maximum in TOTAL_LIMITS.items():
        counts = [row["calls"][key] for row in rows]
        if any(type(count) is not int or count < 0 for count in counts) or sum(counts) + LIMITS[key] > maximum:
            raise ValueError("stage_b.cumulative_budget_invalid")
    return rows


def validate_reuse(manifest):
    old, result = run06_assets()
    if (not same_json(old["cases"], FULL_CASES) or old["frozenHead"] != RUN06_HEAD
            or [row["caseId"] for row in result["cases"][:3]] != REUSED_EVIDENCE["caseIds"]
            or not all(row["passed"] is True for row in result["cases"][:3])):
        raise ValueError("stage_b.reuse_source_invalid")
    for key in ("environment", "indexBinding", "taskVersions", "promptHashes", "gold", "evaluation", "executables"):
        if not same_json(manifest[key], old[key]):
            raise ValueError("stage_b.reuse_snapshot_changed")
    expected = {name: sha for name, sha in old["assets"].items() if name.startswith(PRODUCTION_PREFIXES)}
    for name in COMPATIBLE_CHANGES:
        source = subprocess.check_output(["git", "show", f"{COMPATIBLE_HEAD}:{name}"], cwd=legacy.REPO)
        expected[name] = legacy.digest(source)
    actual = {name: sha for name, sha in manifest["assets"].items() if name.startswith(PRODUCTION_PREFIXES)}
    if actual != expected:
        raise ValueError("stage_b.reuse_source_changed")


def prepare(root):
    with input_bindings(), tempfile.TemporaryDirectory(prefix="codex-stage-b-run07-freeze-") as directory:
        with patch.multiple(v2, TASK_VERSIONS=previous.TASK_VERSIONS, prompt_hashes=previous.prompt_hashes):
            manifest = v2.prepare(Path(directory))
    manifest.pop("priorRun")
    manifest.update(schemaVersion=7, runId=RUN_ID, authorizationReference=REFERENCE,
                    taskVersions=previous.TASK_VERSIONS, promptHashes=previous.prompt_hashes(),
                    priorRuns=prior_bindings(), cumulativeLimits=TOTAL_LIMITS, runRoot=str(root.resolve()),
                    diagnosticVersion=previous.DIAGNOSTIC_VERSION,
                    qualityVersion=previous.KNOWLEDGE_QUALITY_VERSION_V2,
                    downstreamDiagnosticVersion=previous.DOWNSTREAM_DIAGNOSTIC_VERSION,
                    reusedEvidence=REUSED_EVIDENCE)
    validate_reuse(manifest)
    root.mkdir(parents=True, exist_ok=True)
    legacy.write_exclusive(root / "manifest.json", manifest)
    return manifest


def validate_manifest(root, expected_sha=None):
    raw = (root / "manifest.json").read_bytes()
    parsed = strict_json(raw)
    with input_bindings():
        manifest, sha = v2._validate(root, expected_sha)
    required = dict(schemaVersion=7, runId=RUN_ID, authorizationReference=REFERENCE,
        limits=LIMITS, cases=CASES, gold=legacy.GOLD, environment=legacy.ENV,
        taskVersions=previous.TASK_VERSIONS, promptHashes=previous.prompt_hashes(), priorRuns=prior_bindings(),
        cumulativeLimits=TOTAL_LIMITS, runRoot=str(root.resolve()), diagnosticVersion=previous.DIAGNOSTIC_VERSION,
        qualityVersion=previous.KNOWLEDGE_QUALITY_VERSION_V2,
        downstreamDiagnosticVersion=previous.DOWNSTREAM_DIAGNOSTIC_VERSION, reusedEvidence=REUSED_EVIDENCE)
    if (set(parsed) != set(required) | {"frozenHead", "indexBinding", "assets", "executables", "evaluation"}
            or sha != legacy.digest(raw) or not same_json(parsed, manifest)
            or any(not same_json(parsed[key], value) for key, value in required.items())):
        raise ValueError("stage_b.run_07_binding_invalid")
    validate_reuse(manifest)
    if any((root / name).exists() for name in ("evidence.jsonl", "consumed.json", "journal.jsonl", "result.json")):
        raise ValueError("stage_b.retry_resume_forbidden")
    return manifest, sha


@contextmanager
def run_07_bindings():
    # 单独CLI拥有绑定；无论失败或取消均恢复旧模块，不改历史文件。
    with previous.run_06_bindings(), input_bindings(), patch.multiple(
        legacy, prepare=prepare, validate_manifest=validate_manifest,
    ):
        yield


def main():
    with run_07_bindings():
        legacy.main()


if __name__ == "__main__":
    main()
