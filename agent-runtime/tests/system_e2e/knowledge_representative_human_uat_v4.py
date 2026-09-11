"""One bounded current-root batch with real human review before the next case."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
import json
import logging
import os
import runpy
from unittest.mock import patch

from tests.system_e2e import knowledge_representative_uat_v1 as original_cases
from tests.system_e2e import knowledge_representative_uat_v3 as base
from tests.system_e2e.knowledge_human_review import FIELDS, ReviewPortal, ReviewSession
from tests.system_e2e.knowledge_representative_human_uat_v1 import HumanBudget as PreviousHumanBudget, assess
from agent_runtime.knowledge.rewrite_v10 import KnowledgeRewriteTaskV10
from tests.system_e2e.knowledge_model_failure_probe_v3 import DETAILS, observe_failures

RUN_ID = "knowledge-representative-human-uat-v4-20260911-07"
ROOT = base.REPO / "agent-runtime/target" / RUN_ID
REFERENCE = "UAT_01:14.62"
SELECTION = original_cases.SELECTION
TASKS = (("action_selection", "action-selection-v4"), ("knowledge_rewrite", "10"), ("knowledge_summary", "7"))
LIMITS = dict(e2e=10, model=30, search=40, embedding=20, rerank=40, business=0, retry=0, resume=0)


@contextmanager
def batch():
    # Only versioned test orchestration is adapted; no production decision is replaced.
    with patch.multiple(base, RUN_ID=RUN_ID, ROOT=ROOT, REFERENCE=REFERENCE,
                        LIMITS=LIMITS, SELECTION=SELECTION, TASKS=TASKS,
                        KnowledgeRewriteTaskV9=KnowledgeRewriteTaskV10, observe_failures=observe_failures):
        yield


def manifest():
    with batch():
        value = base.manifest()
    names = base.service_run.git("ls-files", "agent-runtime/tests/system_e2e/knowledge_human_review.*",
        "agent-runtime/tests/system_e2e/test_knowledge_human_review*",
        "agent-runtime/tests/system_e2e/test_knowledge_representative_human_uat_v1.py",
        "agent-runtime/tests/system_e2e/test_knowledge_representative_human_uat_v4.py",
        "agent-runtime/tests/system_e2e/test_knowledge_model_failure_probe_v2.py",
        "agent-runtime/tests/system_e2e/test_knowledge_model_failure_probe_v3.py",
        "agent-runtime/tests/integration/knowledge/test_rewrite_v9_period_lookup_diagnosis.py").splitlines()
    value["assets"].update({p: base.digest((base.REPO / p).read_bytes()) for p in names})
    value.update(knownBefore=dict(e2e=41, model=107), cumulativeLimits=dict(e2e=51, model=137),
        humanReview=dict(version=1, method="user_interactive", caseTimeoutSeconds=600,
                         totalWaitSeconds=1800, fields=list(FIELDS), required=True))
    request = KnowledgeRewriteTaskV10.definition().build_request(base.KnowledgeSemanticPlanInput(
        minimized_question="税务政策定义", enabled_domain_ids=("tax.policy", "tax.law")))
    payload = base.project_deepseek_request(request).payload
    base.require(base.service_run.ModelSettings.MODEL_NAME == "deepseek-flash", "model_changed")
    value["modelWire"] = dict(model="deepseek-flash",
        rewritePath="/beta/chat/completions", otherTaskPath="/chat/completions",
        outputToolsSha256=base.digest(base.canonical_json_bytes(payload["tools"])))
    value["failureDiagnostics"] = dict(version=3, details=list(DETAILS))
    return value


def validate_frozen(expected_sha):
    base.require(ROOT.is_dir() and {p.name for p in ROOT.iterdir()} == {"manifest.json"}, "retry_resume_forbidden")
    raw = (ROOT / "manifest.json").read_bytes()
    frozen = base.strict_json(raw)
    base.require(base.digest(raw) == expected_sha
        and base.canonical_json_bytes(frozen) == base.canonical_json_bytes(manifest()), "binding_changed")
    return frozen

class HumanBudget(PreviousHumanBudget):
    """Apply the current task-specific wire boundary before the paid request."""

    async def model_request(self, request):
        if self.pending is None or self.pending[1] or self.stopped or not 0 <= self.task_count < len(TASKS):
            self.stopped = True
            raise ValueError("representative.unexpected_model_wire")
        path = "/beta/chat/completions" if TASKS[self.task_count][0] == "knowledge_rewrite" else "/chat/completions"
        if (request.method != "POST"
                or str(request.url) != base.service_run.ModelSettings.BASE_URL + path
                or request.content != self.pending[0]):
            self.stopped = True
            raise ValueError("representative.unexpected_model_wire")
        self.count("model")
        if self.totals["model"] == 1:
            base.save(self.root / "consumed.json", dict(runId=RUN_ID, manifestSha256=self.manifest_sha))
        event = dict(caseId=self.current["caseId"], task=TASKS[self.task_count][0],
            ordinal=self.totals["model"], requestSha256=base.digest(request.content))
        self.journal.write(json.dumps(event) + "\n")
        self.journal.flush()
        os.fsync(self.journal.fileno())
        self.pending = (self.pending[0], True)
        self.task_count += 1


def execute(expected_sha, session):
    frozen = validate_frozen(expected_sha)
    # Human confirmation precedes credential access, warmup and all owned services.
    base.require(session.wait_ready(), "human_not_ready")
    base.save(ROOT / "authorization.json", dict(runId=RUN_ID, frozenHead=frozen["frozenHead"],
        manifestSha256=expected_sha, reference=REFERENCE, limits=LIMITS, cumulativeLimits=dict(e2e=51, model=137)))
    base.save(ROOT / "started.json", dict(runId=RUN_ID, manifestSha256=expected_sha))
    terminal = dict(runId=RUN_ID, manifestSha256=expected_sha, status="failed", startupRerank=0,
                    indexWrites=0, answer=0, failureReason=None)
    events = []

    def emit(row):
        events.append(row)
        base.save(ROOT / f"event-{len(events):03d}.json", row)
        if row["stage"] == "case":
            print(json.dumps({k: row[k] for k in ("caseId", "passed", "status", "calls")}), flush=True)

    budget = None
    with batch():
        try:
            # 先封存本次尝试；依赖预检失败也不得从同一批次恢复执行。
            base.preflight(frozen)
            terminal["startupRerank"] = 1
            base.save(ROOT / "warmup-attempt.json", dict(rerank=1))
            asyncio.run(runpy.run_path(str(base.REPO / "serviceCenter/warmup-knowledge-reranker.py"))["warmup"]())
            with base.bindings(), base.services.local_services(emit, include_agent=True) as (token, binding):
                base.require(binding == frozen["indexBinding"], "index_changed")
                asyncio.run(base.service_run.run_server(token, emit, None))
                budget = HumanBudget(ROOT, expected_sha, emit, session=session)
                budget.check_reviewer()
                with base.bindings(budget), patch.object(base.service_run, "assess",
                        lambda spec, response, obs, unused: assess(spec, response, obs, budget, session)):
                    rows = asyncio.run(base.service_run.run_server(token, emit, budget))
                base.require(len(rows) == len(SELECTION) and all(r["passed"] and r["httpStatus"] == 200 for r in rows), "case_failed")
            base.require(base.canonical_json_bytes(manifest()) == base.canonical_json_bytes(frozen), "final_binding_changed")
            base.support.check_index(base.support.load_support(), frozen["indexBinding"])
            base.require(any(e.get("stage") == "cleanup" and all(e.get(k) is True for k in
                ("ownedProcessesStopped", "rawLogsDeleted", "secretScanPassed")) for e in events), "cleanup_failed")
            terminal["status"] = "passed"
        except BaseException as error:
            terminal["failureReason"] = "interrupted" if isinstance(error, (KeyboardInterrupt, asyncio.CancelledError)) else "execution_or_case_failed"
        finally:
            session.close()
            if budget:
                budget.journal.close()
                if budget.current is not None and budget.current["caseId"] not in {r["caseId"] for r in budget.results}:
                    row = dict(caseId=budget.current["caseId"], passed=False, status="request_incomplete",
                        httpStatus=None, calls=dict(budget.per_case), validation=budget.validation,
                        modelFailure=budget.model_failures(), humanReview=dict(status="not_assessed", reason="interrupted"))
                    budget.results.append(row)
                    emit(dict(stage="case", **row))
            terminal.update(cases=budget.results if budget else [], totals=budget.totals if budget else dict.fromkeys(LIMITS, 0))
            terminal["notExecuted"] = [c["caseId"] for c in base.cases() if c["caseId"] not in {r["caseId"] for r in terminal["cases"]}]
            terminal["cleanup"] = [e for e in events if e["stage"] in {"cleanup", "runtime_cleanup"}]
            base.save(ROOT / "result.json", terminal)
    return terminal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "execute"))
    parser.add_argument("--manifest-sha256")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    with base.java_environment():
        if args.mode == "prepare":
            base.require(not ROOT.exists(), "run_exists")
            value = manifest()
            ROOT.mkdir(parents=True)
            base.save(ROOT / "manifest.json", value)
            print(json.dumps(dict(runId=RUN_ID, frozenHead=value["frozenHead"],
                manifestSha256=base.digest((ROOT / "manifest.json").read_bytes()), limits=LIMITS)))
        else:
            base.require(bool(args.manifest_sha256), "manifest_hash_required")
            with ReviewPortal(ReviewSession()) as portal:
                base.require(portal.open_browser(), "review_browser_unavailable")
                print("Waiting for the human reviewer in the local browser; no paid request before readiness.", flush=True)
                result = execute(args.manifest_sha256, portal.session)
            print(json.dumps(dict(status=result["status"], totals=result["totals"], notExecuted=result["notExecuted"])))
            return 0 if result["status"] == "passed" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
