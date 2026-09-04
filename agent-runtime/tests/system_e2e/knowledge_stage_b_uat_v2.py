"""Newly authorized run-02; reuse the frozen harness without editing run-01.

Only the CLI execution scope changes harness bindings. Production routing,
case order, source gold, validators and HTTP endpoints remain unchanged.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from agent_runtime.knowledge.rewrite_v4 import INSTRUCTION
from agent_runtime.knowledge.evidence.summary_task_v4 import SUMMARY_PROMPT_V4
from agent_runtime.model.deepseek.action_selector import ACTION_SELECTION_SYSTEM_INSTRUCTION
from tests.system_e2e import knowledge_stage_b_uat as legacy
from tests.system_e2e.test_knowledge_stage_b_run_01_history import HASHES as PRIOR_HASHES

RUN_ID = "knowledge-stage-b-uat-v2-20260904-run-02"
REFERENCE = "P3_00:WP-KRETRIEVAL-UAT-01/run-02"
TASK_VERSIONS = {"selection": "action-selection-v4", "rewrite": "4", "summary": "4"}
TOTAL_LIMITS = {"e2e": 20, "model": 60, "search": 80, "embedding": 40,
                "rerank": 40, "business": 0, "retry": 0, "resume": 0}
PRIOR_ROOT = Path(__file__).with_name("knowledge_stage_b_run_01")
_prepare = legacy.prepare
_validate = legacy.validate_manifest
_assess = legacy.assess
_Budget = legacy.Budget


def prompt_hashes():
    return {name: legacy.digest(value.encode("utf-8")) for name, value in (
        ("action_selection", ACTION_SELECTION_SYSTEM_INSTRUCTION),
        ("knowledge_rewrite", INSTRUCTION), ("knowledge_summary", SUMMARY_PROMPT_V4))}


def prior_binding():
    for name, expected in PRIOR_HASHES.items():
        if legacy.digest((PRIOR_ROOT / name).read_bytes()) != expected:
            raise ValueError("stage_b.prior_run_changed")
    result = json.loads((PRIOR_ROOT / "result.json").read_bytes())
    if result["status"] != "failed" or any(
        type(result["totals"][key]) is not int or result["totals"][key] < 0
        or result["totals"][key] + legacy.LIMITS[key] > limit
        for key, limit in TOTAL_LIMITS.items()
    ):
        raise ValueError("stage_b.cumulative_budget_invalid")
    return {"runId": result["runId"], "hashes": PRIOR_HASHES, "calls": result["totals"]}


def prepare(root):
    # Capture the reusable freeze in a disposable non-repository directory.
    # Only the final, fully-bound manifest is written to the new run root.
    with tempfile.TemporaryDirectory(prefix="codex-stage-b-freeze-") as directory:
        manifest = _prepare(Path(directory))
    manifest.update(schemaVersion=2, runId=RUN_ID, authorizationReference=REFERENCE,
                    taskVersions=TASK_VERSIONS, promptHashes=prompt_hashes(),
                    priorRun=prior_binding(), cumulativeLimits=TOTAL_LIMITS, runRoot=str(root.resolve()))
    extra_prefixes = ("config-service/src/main/resources/config/", "common-security/src/main/",
                      "auth-service/src/main/", "agent-runtime/tests/system_e2e/test_knowledge_stage_b_")
    for name in legacy.git("ls-files").splitlines():
        if name.startswith(extra_prefixes):
            manifest["assets"][name] = legacy.digest((legacy.REPO / name).read_bytes())
    root.mkdir(parents=True, exist_ok=True)
    legacy.write_exclusive(root / "manifest.json", manifest)
    return manifest


def validate_manifest(root, expected_sha=None):
    with patch.object(legacy, "RUN_ID", RUN_ID):
        manifest, sha = _validate(root, expected_sha)
    expected_keys = {"schemaVersion", "runId", "frozenHead", "authorizationReference", "limits",
                     "cases", "gold", "environment", "indexBinding", "assets", "executables",
                     "taskVersions", "evaluation", "promptHashes", "priorRun", "cumulativeLimits", "runRoot"}
    if (set(manifest) != expected_keys or type(manifest["schemaVersion"]) is not int
            or manifest["schemaVersion"] != 2 or manifest["authorizationReference"] != REFERENCE
            or manifest["taskVersions"] != TASK_VERSIONS or manifest["promptHashes"] != prompt_hashes()
            or manifest["priorRun"] != prior_binding() or manifest["cumulativeLimits"] != TOTAL_LIMITS
            or manifest["runRoot"] != str(root.resolve())):
        raise ValueError("stage_b.run_02_binding_invalid")
    if any((root / name).exists() for name in ("evidence.jsonl", "consumed.json", "journal.jsonl", "result.json")):
        raise ValueError("stage_b.retry_resume_forbidden")
    return manifest, sha


class Run02Budget(_Budget):
    def begin(self, case_spec):
        ordinal = self.totals["e2e"]
        if ordinal >= len(legacy.CASES) or case_spec != legacy.CASES[ordinal]:
            raise ValueError("stage_b.case_order_invalid")
        super().begin(case_spec)
        self.per_case["e2e"] = 1

    async def model_request(self, request):
        try:
            body = json.loads(request.content)
            system = body["messages"][0]
            next_task = ("action_selection", "knowledge_rewrite", "knowledge_summary")[min(len(self.seen_tasks), 2)]
            if (system["role"] != "system" or type(system["content"]) is not str
                    or legacy.digest(system["content"].encode("utf-8")) != prompt_hashes()[next_task]):
                raise ValueError("stage_b.prompt_changed")
            await super().model_request(request)
        except (KeyError, IndexError, TypeError, ValueError):
            self.stopped = True
            raise ValueError("stage_b.model_request_rejected") from None


def assess(case_spec, response, observation, summary_evidence):
    verdict = _assess(case_spec, response, observation, summary_evidence)
    expected = [("action_selection", "action-selection-v4"), ("knowledge_rewrite", "4")]
    if not case_spec["reason"]:
        expected.append(("knowledge_summary", "4"))
    actual = [(item["taskId"], item["taskVersion"]) for item in observation.model_calls]
    valid = actual == expected and all(item["status"] == "succeeded" for item in observation.model_calls)
    verdict["taskBindingValid"] = valid
    zero_retrieval = not case_spec["reason"] or not observation.downstream_calls
    verdict["zeroRetrievalValid"] = zero_retrieval
    verdict["passed"] = verdict["passed"] and valid and zero_retrieval
    return verdict


@contextmanager
def run_02_bindings():
    # A single CLI process owns this scope; bindings are restored on all exits.
    with patch.multiple(legacy, RUN_ID=RUN_ID, Budget=Run02Budget, prepare=prepare,
                        validate_manifest=validate_manifest, assess=assess):
        yield


def main():
    with run_02_bindings():
        legacy.main()


if __name__ == "__main__":
    main()
