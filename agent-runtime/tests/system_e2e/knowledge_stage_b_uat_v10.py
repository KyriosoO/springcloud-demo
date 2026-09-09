"""One current-root batch with finite failure observation; old runs remain immutable."""
from contextlib import contextmanager
from dataclasses import asdict
import importlib
from pathlib import Path
import sys
from unittest.mock import patch

from agent_runtime.model import gateway
from tests.system_e2e import knowledge_stage_b_uat_v9 as previous
from tests.system_e2e.knowledge_model_failure_probe_v1 import project_failure
from tests.system_e2e.knowledge_rewrite_diagnostic_v1 import throw_site

RUN_ID = "knowledge-stage-b-uat-v10-20260909-run-10"
REFERENCE = "P3_00:WP-KRETRIEVAL-UAT-01/run-10"
TOTAL_LIMITS = dict(e2e=28, model=71, search=59, embedding=30, rerank=48, business=0, retry=0, resume=0)
DIAGNOSTIC = Path(__file__).with_name("knowledge_rewrite_diagnostic_01")
DIAGNOSTIC_HASHES = {
    "manifest.json": "dca59ed52e9dd007c41aa1c0f273a158404a1f6cd4fb89b5d89d4c49d49d29ac",
    "consumed.json": "ddbc568439ffc60c49df1a90b7bea5ca3244a630ce1ba3f191207c39924c18cc",
    "journal.jsonl": "e7ae793da4323f815317e3a75cbdd8440ccf3b3a8af1ca21e2246cf6d3240cbe",
    "result.json": "a3e428211df506cbaf1af01004a1c385d317fa051f80c94d0681d5d55007ae8f",
}
_manifest, _run_server = previous.current_manifest, previous.run_server


def prior_bindings():
    rows = []
    for ordinal in range(1, 10):
        history = importlib.import_module(f"tests.system_e2e.test_knowledge_stage_b_run_{ordinal:02}_history")
        root = Path(__file__).with_name(f"knowledge_stage_b_run_{ordinal:02}")
        if any(previous.legacy.digest((root / name).read_bytes()) != sha for name, sha in history.HASHES.items()):
            raise ValueError("stage_b.prior_run_changed")
        value = previous.strict_json((root / "result.json").read_bytes())
        if value["status"] != "failed" or set(value["totals"]) != set(previous.LIMITS):
            raise ValueError("stage_b.prior_status_invalid")
        rows.append(dict(runId=value["runId"], hashes=history.HASHES, calls=value["totals"],
                         startupCalls=dict(rerank=1) if ordinal == 9 else {}))
    for key, maximum in TOTAL_LIMITS.items():
        counts = [row["calls"][key] for row in rows]
        if (any(type(c) is not int or c < 0 for c in counts)
                or sum(counts) + sum(row["startupCalls"].get(key, 0) for row in rows)
                + previous.LIMITS[key] + previous.STARTUP_LIMITS.get(key, 0) > maximum):
            raise ValueError("stage_b.cumulative_budget_invalid")
    return rows


def current_manifest(root):
    if set(DIAGNOSTIC_HASHES) != {"manifest.json", "consumed.json", "journal.jsonl", "result.json"} or any(
            previous.legacy.digest((DIAGNOSTIC / name).read_bytes()) != sha for name, sha in DIAGNOSTIC_HASHES.items()):
        raise ValueError("stage_b.diagnostic_binding_invalid")
    value = _manifest(root)
    for name in ("knowledge_rewrite_diagnostic_v1.py", "knowledge_model_failure_probe_v1.py",
                 "test_knowledge_rewrite_diagnostic_v1.py", "test_knowledge_model_failure_probe_v1.py"):
        path = Path(__file__).with_name(name)
        value["assets"][path.relative_to(previous.legacy.REPO).as_posix()] = previous.legacy.digest(path.read_bytes())
    value.update(schemaVersion=10, failureObservationVersion="finite-throw-site-v1",
                 diagnostic=dict(runId="knowledge-rewrite-diagnostic-v1-20260909-01", hashes=DIAGNOSTIC_HASHES, model=1))
    return value


async def run_server(token, emit, budget=None):
    if budget is None:
        return await _run_server(token, emit, None)
    original = gateway.model_call_failed
    recorded = {}

    def failed(sequence, kind):
        if kind == "invalid_output" and budget.current is not None:
            case_id = budget.current["caseId"]
            count = recorded.get(case_id, 0)
            if count < 3:
                error = sys.exception()
                tasks = [name for name in previous.TASKS if name in budget.seen_tasks]
                row = dict(stage="model_failure_diagnostic", caseId=case_id,
                           taskId=tasks[-1] if tasks else "unknown", **asdict(project_failure(error)),
                           throwSite=throw_site(error))
                budget.probes.append(row)
                emit(row)
                recorded[case_id] = count + 1
        original(sequence, kind)

    with patch.object(gateway, "model_call_failed", failed):
        return await _run_server(token, emit, budget)


@contextmanager
def overrides():
    with patch.multiple(previous, RUN_ID=RUN_ID, REFERENCE=REFERENCE, TOTAL_LIMITS=TOTAL_LIMITS,
                        prior_bindings=prior_bindings, current_manifest=current_manifest, run_server=run_server):
        yield


@contextmanager
def bindings():
    with overrides(), previous.bindings():
        yield


if __name__ == "__main__":
    with overrides():
        previous.main()
