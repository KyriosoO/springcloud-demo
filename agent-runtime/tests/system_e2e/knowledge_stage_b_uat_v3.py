"""Explicitly authorized run-03. Adds finite diagnostics, not acceptance rules."""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from tests.system_e2e import knowledge_stage_b_uat as legacy
from tests.system_e2e import knowledge_stage_b_uat_v2 as prior
from tests.system_e2e import knowledge_stage_b_failure_diagnostics as diagnostics
from tests.system_e2e.test_knowledge_stage_b_run_02_history import HASHES as RUN02_HASHES

RUN_ID = "knowledge-stage-b-uat-v3-20260904-run-03"
REFERENCE = "P3_00:WP-KRETRIEVAL-UAT-01/run-03"
_run_server = legacy.run_server


def prior_bindings():
    rows = [prior.prior_binding()]
    root = Path(__file__).with_name("knowledge_stage_b_run_02")
    if any(legacy.digest((root / name).read_bytes()) != expected for name, expected in RUN02_HASHES.items()):
        raise ValueError("stage_b.prior_run_changed")
    result = json.loads((root / "result.json").read_bytes())
    if result["status"] != "failed" or result["runId"] != prior.RUN_ID:
        raise ValueError("stage_b.prior_status_invalid")
    rows.append({"runId": result["runId"], "hashes": RUN02_HASHES, "calls": result["totals"]})
    for key, limit in prior.TOTAL_LIMITS.items():
        calls = [row["calls"][key] for row in rows]
        if (any(type(value) is not int or value < 0 for value in calls)
                or sum(calls) + legacy.LIMITS[key] > limit):
            raise ValueError("stage_b.cumulative_budget_invalid")
    return rows


def prepare(root):
    with tempfile.TemporaryDirectory(prefix="codex-stage-b-run03-freeze-") as directory:
        manifest = prior.prepare(Path(directory))
    manifest.pop("priorRun")
    manifest.update(schemaVersion=3, runId=RUN_ID, authorizationReference=REFERENCE,
                    priorRuns=prior_bindings(), runRoot=str(root.resolve()), diagnosticVersion=diagnostics.VERSION)
    root.mkdir(parents=True, exist_ok=True)
    legacy.write_exclusive(root / "manifest.json", manifest)
    return manifest


def validate_manifest(root, expected_sha=None):
    with patch.object(legacy, "RUN_ID", RUN_ID):
        manifest, sha = prior._validate(root, expected_sha)
    keys = {"schemaVersion", "runId", "frozenHead", "authorizationReference", "limits", "cases", "gold",
            "environment", "indexBinding", "assets", "executables", "taskVersions", "evaluation",
            "promptHashes", "priorRuns", "cumulativeLimits", "runRoot", "diagnosticVersion"}
    if (set(manifest) != keys or type(manifest["schemaVersion"]) is not int or manifest["schemaVersion"] != 3
            or manifest["authorizationReference"] != REFERENCE or manifest["diagnosticVersion"] != diagnostics.VERSION
            or manifest["taskVersions"] != prior.TASK_VERSIONS or manifest["promptHashes"] != prior.prompt_hashes()
            or manifest["priorRuns"] != prior_bindings() or manifest["cumulativeLimits"] != prior.TOTAL_LIMITS
            or manifest["runRoot"] != str(root.resolve())):
        raise ValueError("stage_b.run_03_binding_invalid")
    if any((root / name).exists() for name in ("evidence.jsonl", "consumed.json", "journal.jsonl", "result.json")):
        raise ValueError("stage_b.retry_resume_forbidden")
    return manifest, sha


class Run03Budget(prior.Run02Budget):
    def begin(self, case_spec):
        super().begin(case_spec)
        self.model_failures = []


def assess(case_spec, response, observation, summary_evidence):
    verdict = prior.assess(case_spec, response, observation, summary_evidence)
    verdict["modelFailures"] = diagnostics.failure_rows(observation)
    return verdict


async def run_server(token, emit, budget):
    if budget is None:
        return await _run_server(token, emit, None)
    with diagnostics.diagnostic_scope(budget):
        return await _run_server(token, emit, budget)


@contextmanager
def run_03_bindings():
    with patch.multiple(legacy, RUN_ID=RUN_ID, Budget=Run03Budget, prepare=prepare,
                        validate_manifest=validate_manifest, assess=assess, run_server=run_server):
        yield


def main():
    with run_03_bindings():
        legacy.main()


if __name__ == "__main__":
    main()
