"""Validate the Summary7-only fix on the original cases and immutable sources."""
from contextlib import contextmanager
from unittest.mock import patch

from agent_runtime.knowledge.evidence.summary_task_v7 import SUMMARY_PROMPT_V7
from tests.system_e2e import knowledge_stage_b_uat_v11 as previous
from tests.system_e2e.test_knowledge_stage_b_run_11_history import ROOT, HASHES

v10 = previous.previous
v9 = v10.previous
v8 = v9.previous
RUN_ID = "knowledge-stage-b-uat-v12-20260909-run-12"
REFERENCE = "P3_00:WP-KRETRIEVAL-UAT-01/run-12"
TASKS = {**v9.TASKS, "knowledge_summary": "7"}
TOTAL_LIMITS = dict(e2e=30, model=76, search=61, embedding=31, rerank=51, business=0, retry=0, resume=0)
_manifest, _prior, _prompts = previous.current_manifest, v10.prior_bindings, v8.prompt_hashes


def prior_bindings():
    rows = _prior()
    if {p.name for p in ROOT.iterdir()} != set(HASHES) or any(
            v9.legacy.digest((ROOT / name).read_bytes()) != sha for name, sha in HASHES.items()):
        raise ValueError("stage_b.prior_run_changed")
    result = v9.strict_json((ROOT / "result.json").read_bytes())
    if result["status"] != "failed" or set(result["totals"]) != set(v9.LIMITS):
        raise ValueError("stage_b.prior_status_invalid")
    rows.append(dict(runId=result["runId"], hashes=HASHES, calls=result["totals"], startupCalls=dict(rerank=1)))
    for key, maximum in TOTAL_LIMITS.items():
        used = sum(row["calls"][key] + row["startupCalls"].get(key, 0) for row in rows)
        # run-10 failed before E2E, but did one startup rerank.
        if used + (1 if key == "rerank" else 0) + v9.LIMITS[key] + v9.STARTUP_LIMITS.get(key, 0) > maximum:
            raise ValueError("stage_b.cumulative_budget_invalid")
    return rows


def prompt_hashes():
    return {**_prompts(), "knowledge_summary": v9.legacy.digest(SUMMARY_PROMPT_V7.encode())}


def current_manifest(root):
    value = _manifest(root)
    value.update(schemaVersion=12, taskVersions=dict(selection="action-selection-v4", rewrite="8", summary="7"))
    return value


@contextmanager
def overrides():
    with (patch.multiple(previous, RUN_ID=RUN_ID, REFERENCE=REFERENCE, TOTAL_LIMITS=TOTAL_LIMITS,
                         current_manifest=current_manifest),
          patch.object(v10, "prior_bindings", prior_bindings),
          patch.object(v9, "TASKS", TASKS), patch.object(v8, "prompt_hashes", prompt_hashes), previous.overrides()):
        yield


@contextmanager
def bindings(manifest=None):
    with overrides(), v9.bindings(manifest):
        yield


if __name__ == "__main__":
    with previous.java_environment(), overrides():
        v9.main()
