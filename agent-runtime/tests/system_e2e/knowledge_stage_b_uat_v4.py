"""Authorized independent V5 run; immutable cases, acceptance and prior runs."""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from agent_runtime.knowledge.rewrite_v5 import INSTRUCTION, KnowledgeRewriteTaskV5
from agent_runtime.knowledge.evidence.summary_task_v5 import SUMMARY_PROMPT_V5
from agent_runtime.model.deepseek.action_selector import ACTION_SELECTION_SYSTEM_INSTRUCTION
from tests.system_e2e import knowledge_stage_b_uat as legacy
from tests.system_e2e import knowledge_stage_b_uat_v2 as v2
from tests.system_e2e import knowledge_stage_b_uat_v3 as v3
from tests.system_e2e import knowledge_stage_b_failure_diagnostics as diagnostics
from tests.system_e2e.test_knowledge_stage_b_run_03_history import HASHES as RUN03_HASHES

RUN_ID = "knowledge-stage-b-uat-v4-20260904-run-04"
REFERENCE = "P3_00:WP-KRETRIEVAL-UAT-01/run-04"
TASK_VERSIONS = {"selection": "action-selection-v4", "rewrite": "5", "summary": "5"}
DIAGNOSTIC_VERSION = "stage-b-failure-diagnostics-v2"
DIAGNOSTIC_TASKS = {"action_selection": "action-selection-v4", "knowledge_rewrite": "5", "knowledge_summary": "5"}


def prompt_hashes():
    return {name: legacy.digest(value.encode("utf-8")) for name, value in (
        ("action_selection", ACTION_SELECTION_SYSTEM_INSTRUCTION),
        ("knowledge_rewrite", INSTRUCTION), ("knowledge_summary", SUMMARY_PROMPT_V5))}


def prior_bindings():
    rows = v3.prior_bindings()
    root = Path(__file__).with_name("knowledge_stage_b_run_03")
    if any(legacy.digest((root / name).read_bytes()) != expected for name, expected in RUN03_HASHES.items()):
        raise ValueError("stage_b.prior_run_changed")
    result = json.loads((root / "result.json").read_bytes())
    if result["status"] != "failed" or result["runId"] != v3.RUN_ID:
        raise ValueError("stage_b.prior_status_invalid")
    rows.append({"runId": result["runId"], "hashes": RUN03_HASHES, "calls": result["totals"]})
    for key, limit in v2.TOTAL_LIMITS.items():
        calls = [row["calls"][key] for row in rows]
        if (any(type(value) is not int or value < 0 for value in calls)
                or sum(calls) + legacy.LIMITS[key] > limit):
            raise ValueError("stage_b.cumulative_budget_invalid")
    return rows


def prepare(root):
    with tempfile.TemporaryDirectory(prefix="codex-stage-b-run04-freeze-") as directory:
        manifest = v2.prepare(Path(directory))
    manifest.pop("priorRun")
    manifest.update(schemaVersion=4, runId=RUN_ID, authorizationReference=REFERENCE,
                    taskVersions=TASK_VERSIONS, promptHashes=prompt_hashes(), priorRuns=prior_bindings(),
                    runRoot=str(root.resolve()), diagnosticVersion=DIAGNOSTIC_VERSION)
    root.mkdir(parents=True, exist_ok=True)
    legacy.write_exclusive(root / "manifest.json", manifest)
    return manifest


def validate_manifest(root, expected_sha=None):
    with patch.object(legacy, "RUN_ID", RUN_ID):
        manifest, sha = v2._validate(root, expected_sha)
    keys = {"schemaVersion", "runId", "frozenHead", "authorizationReference", "limits", "cases", "gold",
            "environment", "indexBinding", "assets", "executables", "taskVersions", "evaluation",
            "promptHashes", "priorRuns", "cumulativeLimits", "runRoot", "diagnosticVersion"}
    if (set(manifest) != keys or type(manifest["schemaVersion"]) is not int or manifest["schemaVersion"] != 4
            or manifest["authorizationReference"] != REFERENCE or manifest["diagnosticVersion"] != DIAGNOSTIC_VERSION
            or manifest["taskVersions"] != TASK_VERSIONS or manifest["promptHashes"] != prompt_hashes()
            or manifest["priorRuns"] != prior_bindings() or manifest["cumulativeLimits"] != v2.TOTAL_LIMITS
            or manifest["runRoot"] != str(root.resolve())):
        raise ValueError("stage_b.run_04_binding_invalid")
    if any((root / name).exists() for name in ("evidence.jsonl", "consumed.json", "journal.jsonl", "result.json")):
        raise ValueError("stage_b.retry_resume_forbidden")
    return manifest, sha


def assess(case_spec, response, observation, summary_evidence):
    # The frozen source-clause/domain verdict remains the single acceptance rule.
    verdict = v2._assess(case_spec, response, observation, summary_evidence)
    expected = [("action_selection", "action-selection-v4"), ("knowledge_rewrite", "5")]
    if not case_spec["reason"]:
        expected.append(("knowledge_summary", "5"))
    actual = [(item["taskId"], item["taskVersion"]) for item in observation.model_calls]
    valid = actual == expected and all(item["status"] == "succeeded" for item in observation.model_calls)
    verdict["taskBindingValid"] = valid
    zero_retrieval = not case_spec["reason"] or not observation.downstream_calls
    verdict["zeroRetrievalValid"] = zero_retrieval
    verdict["passed"] = verdict["passed"] and valid and zero_retrieval
    verdict["modelFailures"] = diagnostics.failure_rows(observation)
    return verdict


@contextmanager
def run_04_bindings():
    # Exclusive CLI scope: update only versioned test bindings, never frozen bytes.
    # V5 still delegates to the unchanged V3 decoder; diagnostics run after rejection.
    with (patch.multiple(v2, TASK_VERSIONS=TASK_VERSIONS, prompt_hashes=prompt_hashes),
          patch.multiple(diagnostics, VERSION=DIAGNOSTIC_VERSION, TASKS=DIAGNOSTIC_TASKS,
                         KnowledgeRewriteTaskV4=KnowledgeRewriteTaskV5),
          patch.multiple(legacy, RUN_ID=RUN_ID, Budget=v3.Run03Budget, prepare=prepare,
                         validate_manifest=validate_manifest, assess=assess, run_server=v3.run_server)):
        yield


def main():
    with run_04_bindings():
        legacy.main()


if __name__ == "__main__":
    main()
