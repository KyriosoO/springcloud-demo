"""One authorized current-root Spring batch; never replay historical runners.

Only source/citation expectations are reused. They are evaluated after requests,
not supplied to the online model, planner, retriever or ranking components.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
from dataclasses import asdict
import json
import logging
import os
from pathlib import Path
import runpy
import socket
import subprocess
import sys
import tempfile
from unittest.mock import patch

from agent_runtime.capability_api.contracts import canonical_json_bytes
from agent_runtime.knowledge.contracts import KNOWLEDGE_QUALITY_VERSION_V3
from agent_runtime.knowledge.evidence.requirement_validation import RequirementCoverageValidator
from agent_runtime.knowledge.evidence.summary_task_v7 import SUMMARY_PROMPT_V7
from agent_runtime.knowledge.retrieval.bge_rerank_context import ContextualBgeRerankAdapter
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput
from agent_runtime.knowledge.rewrite_v9 import KnowledgeRewriteTaskV9
from agent_runtime.model.deepseek.action_selector import ACTION_SELECTION_SYSTEM_INSTRUCTION
from agent_runtime.model.deepseek.dto import project_deepseek_request
from agent_runtime.model.deepseek.transport import DeepSeekChatTransport
from tests.evaluation.knowledge.retrieval_benchmark_dataset import load_dataset
from tests.system_e2e import knowledge_stage_b_uat as service_run
from tests.system_e2e import knowledge_stage_b_services as services
from tests.system_e2e import knowledge_stage_b_quality_v3_probe as support
from tests.system_e2e.knowledge_stage_b_citation_check_v2 import check_citations
from tests.system_e2e.knowledge_stage_b_uat_v11 import java_environment, java_binding
from tests.system_e2e.knowledge_summary_diagnostic_v1 import save, validation_observer

REPO = service_run.REPO
RUN_ID = "knowledge-representative-uat-v1-20260910-01"
ROOT = REPO / "agent-runtime/target" / RUN_ID
REFERENCE = "UAT_01:14.51"
LIMITS = dict(e2e=10, model=30, search=40, embedding=20, rerank=40, business=0, retry=0, resume=0)
PER_CASE = dict(model=3, search=4, embedding=2, rerank=4, business=0)
TASKS = (("action_selection", "action-selection-v4"), ("knowledge_rewrite", "9"), ("knowledge_summary", "7"))
SELECTION = (
    ("KRB-015", (("software", 3), ("vat_rate", 1))),
    ("KRB-006", (("small_2022", 1), ("small_2023", 2))),
    ("KRB-004", (("software", 2),)), ("KRB-010", (("iit_deductions", 1),)),
    ("KRB-011", (("declaration", 1),)), ("KRB-012", (("resource_use", 1),)),
    ("KRB-017", (("vehicle_price", 1),)), ("KRB-019", (("environment", 2),)),
    ("KRB-021", (("stamp_price", 1),)), ("KRB-023", (("lost_invoice", 1),)),
)
digest = service_run.digest


def require(condition, reason):
    if not condition:
        raise ValueError("representative." + reason)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate_key")
            result[key] = value
        return result
    def constant(value):
        raise ValueError("representative.nonfinite")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def cases():
    dataset = load_dataset()
    by_id, sources = {c.id: c for c in dataset.cases}, {s.id: s for s in dataset.sources}
    rows = []
    for case_id, anchors in SELECTION:
        case = by_id[case_id]
        required = {}
        for name, ordinal in anchors:
            require(name in case.sources and 1 <= ordinal <= len(sources[name].anchors), "gold_binding_invalid")
            source = sources[name]
            required[f"{name}_{ordinal}"] = dict(chunk=source.chunk_id, sha256=source.sha256,
                                                 clause=source.anchors[ordinal - 1])
        rows.append(dict(caseId=case.id, question=case.question, domains=list(case.domains),
                         split=case.split, required=required))
    return rows


def prompt_hashes():
    rewrite = KnowledgeRewriteTaskV9.definition().build_request(KnowledgeSemanticPlanInput(
        minimized_question="税务政策定义", enabled_domain_ids=("tax.policy", "tax.law")))
    return {task: digest(text.encode()) for (task, _), text in zip(TASKS,
        (ACTION_SELECTION_SYSTEM_INSTRUCTION, rewrite.system_instruction, SUMMARY_PROMPT_V7), strict=True)}


class ServiceRoot:
    """Adapt only the historical helper's binding filename, not service behavior."""
    def __truediv__(self, path):
        if path == "serviceCenter/knowledge-runtime-binding.v1.json":
            path = "serviceCenter/knowledge-runtime-binding.v2.json"
        return REPO / path


def manifest():
    source_root = (REPO / "agent-runtime/src").resolve()
    require(not sys.flags.optimize, "optimized_execution_forbidden")
    for name, module in tuple(sys.modules.items()):
        if name == "agent_runtime" or name.startswith("agent_runtime."):
            path = getattr(module, "__file__", None)
            require(path is not None and Path(path).resolve().is_relative_to(source_root), "import_source_invalid")
    # Reuse the exhaustive source/Java executable freezer, never its live main.
    with tempfile.TemporaryDirectory(prefix="codex-representative-freeze-") as temp, \
            patch.multiple(service_run, RUN_ID=RUN_ID, CASES=cases(), LIMITS=LIMITS, REPO=ServiceRoot()):
        # git() needs the real directory, not the path adapter.
        with patch.object(service_run, "git", lambda *args: support.clean_head() if args == ("rev-parse", "HEAD")
                          else subprocess.check_output(["git", *args], cwd=REPO).decode().strip()):
            value = service_run.prepare(Path(temp))
    names = service_run.git("ls-files", "agent-runtime/tests/system_e2e/knowledge*",
        "agent-runtime/tests/system_e2e/test_knowledge_representative_uat_v1.py",
        "agent-runtime/tests/evaluation/knowledge/retrieval_benchmark*",
        "common-security/src/main", "auth-service/src/main", "config-service/src/main/resources/config",
        "serviceCenter/knowledge-runtime-binding.v2.json", "serviceCenter/warmup-knowledge-reranker.py",
        "knowledge-corpus-tools/scripts/validate-policy-vector-typed-v1.py",
        "docs/plans/UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md").splitlines()
    value["assets"].update({p: digest((REPO / p).read_bytes()) for p in names})
    # Do not duplicate the old lodging gold/old task versions as current authority.
    value.pop("gold")
    value["cases"] = [dict(caseId=c["caseId"], split=c["split"], domains=c["domains"],
        questionSha256=digest(c["question"].encode()), requiredSha256=digest(canonical_json_bytes(c["required"])))
        for c in cases()]
    value.update(authorizationReference=REFERENCE, taskVersions=dict(TASKS), promptHashes=prompt_hashes(),
        qualityVersion=KNOWLEDGE_QUALITY_VERSION_V3, datasetSha256=load_dataset().sha256,
        java=java_binding(), localModels=support.local_models(),
        knownBefore=dict(e2e=23, model=57), cumulativeLimits=dict(e2e=33, model=87),
        startupRerankLimit=1, runRoot=str(ROOT.resolve()))
    return value


class Budget(service_run.Budget):
    def begin(self, case):
        require(self.totals["e2e"] < len(cases()) and case == cases()[self.totals["e2e"]], "case_order_invalid")
        super().begin(case)
        self.per_case["e2e"] = 1
        self.bundle = self.summary_input = self.plan = None
        self.pending = None
        self.task_count = 0
        self.validation = dict(phases=[], failures=[])

    def count(self, kind):
        if (self.current is None or self.stopped or kind not in PER_CASE
                or self.totals[kind] >= LIMITS[kind] or self.per_case[kind] >= PER_CASE[kind]):
            self.stopped = True
            raise ValueError("representative.budget_exceeded")
        self.totals[kind] += 1
        self.per_case[kind] += 1

    async def model_request(self, request):
        if (self.pending is None or self.pending[1] or self.stopped
                or request.method != "POST" or str(request.url) != service_run.ModelSettings.BASE_URL + "/chat/completions"
                or request.content != self.pending[0]):
            self.stopped = True
            raise ValueError("representative.unexpected_model_wire")
        self.count("model")
        if self.totals["model"] == 1:
            save(self.root / "consumed.json", dict(runId=RUN_ID, manifestSha256=self.manifest_sha))
        event = dict(caseId=self.current["caseId"], task=TASKS[self.task_count][0],
                     ordinal=self.totals["model"], requestSha256=digest(request.content))
        self.journal.write(json.dumps(event) + "\n")
        self.journal.flush()
        os.fsync(self.journal.fileno())
        self.pending = (self.pending[0], True)
        self.task_count += 1

    async def downstream_request(self, request):
        try:
            require(request.url.port == 19201 or "authorization" not in request.headers, "local_auth_leak")
            await super().downstream_request(request)
        except BaseException:
            self.stopped = True
            raise


@contextmanager
def observe(budget):
    complete = DeepSeekChatTransport.complete
    validate = RequirementCoverageValidator.validate
    retrieve = DefaultKnowledgeRetrievalStage.execute
    rank = ContextualBgeRerankAdapter.rerank

    async def checked_complete(transport, request, *, call_deadline):
        try:
            require(budget.pending is None and budget.task_count < 3 and not budget.stopped, "task_repeated")
            require((request.task_id.value, request.task_version) == TASKS[budget.task_count], "task_changed")
            require(digest(request.system_instruction.encode()) == prompt_hashes()[request.task_id.value], "prompt_changed")
            payload = strict_json(request.user_payload_json)
            require(payload["question"] == budget.current["question"], "question_changed")
            if request.task_id.value == "knowledge_summary":
                budget.summary_evidence = [dict(sha256=digest(e["content"].encode()), content=e["content"])
                                           for e in payload["evidence"]]
            budget.pending = (canonical_json_bytes(project_deepseek_request(request).payload), False)
            return await complete(transport, request, call_deadline=call_deadline)
        except BaseException:
            budget.stopped = True
            raise
        finally:
            budget.pending = None

    def captured_validate(self, **kwargs):
        budget.bundle, budget.summary_input = kwargs["bundle"], kwargs["summary_input"]
        return validate(self, **kwargs)

    async def captured_plan(self, **kwargs):
        require(budget.plan is None, "second_plan")
        budget.plan = kwargs["plan"]
        return await retrieve(self, **kwargs)

    async def captured_rank(self, **kwargs):
        scores = await rank(self, **kwargs)
        budget.probes.append(dict(stage="requirement_rerank", querySha256=digest(kwargs["query"].encode()),
            candidates=[dict(chunkId=kwargs["candidates"][s.candidate_index].chunk_id,
                             sha256=kwargs["candidates"][s.candidate_index].content_sha256)
                        for s in sorted(scores, key=lambda s: (-s.score, s.candidate_index))]))
        return scores

    # validation_observer wraps the captured original, never substitutes a verdict.
    with (patch.object(DeepSeekChatTransport, "complete", checked_complete),
          patch.object(RequirementCoverageValidator, "validate", captured_validate),
          patch.object(DefaultKnowledgeRetrievalStage, "execute", captured_plan),
          patch.object(ContextualBgeRerankAdapter, "rerank", captured_rank)):
        # Each begin resets the dict; the forwarding object follows the current case.
        class CurrentValidation:
            def __getitem__(self, key): return budget.validation[key]
        with validation_observer(CurrentValidation()):
            yield


def assess(case, response, observation, budget):
    points = (response.get("result") or {}).get("points", [])
    check = check_citations(bundle=budget.bundle, summary_input=budget.summary_input,
                           points=points, required=case["required"]) if budget.summary_input is not None else None
    actual_tasks = [(r["taskId"], r["taskVersion"]) for r in observation.model_calls]
    tasks_ok = actual_tasks == list(TASKS) and all(r["status"] == "succeeded" for r in observation.model_calls)
    plan = budget.plan
    domains = list(plan.selected_domain_ids) if plan else []
    expected = (dict(search=len(plan.items), embedding=len({i.query_text for i in plan.items if i.path.value == "vector"}),
                     rerank=len(plan.evidence_requirements)) if plan else {})
    http = observation.downstream_calls
    complete = bool(plan and domains == case["domains"] and plan.quality_version == KNOWLEDGE_QUALITY_VERSION_V3
        and all(budget.per_case[k] == v for k, v in expected.items())
        and len(http) == sum(expected.values())
        and all(r["status"] == "completed" and r["httpStatus"] == 200 for r in http))
    source_ok = check is not None and check.binding_valid and all(v for _, v in check.required_clauses)
    passed = (response.get("status") == "success" and response.get("capabilityId") == "knowledge.query"
        and tasks_ok and complete and source_ok and budget.validation == dict(phases=["coverage", "extractive"], failures=[])
        and not budget.stopped)
    status = response.get("status")
    stage_hits = {}
    for stage in ("path", "final_rank", "evidence"):
        identities = {(c["chunkId"], c["sha256"]) for p in budget.probes if p["stage"] == stage for c in p["candidates"]}
        stage_hits[stage] = {name: (gold["chunk"], gold["sha256"]) in identities for name, gold in case["required"].items()}
    return dict(passed=passed, status=status if status in {"success", "no_result", "downstream_failure", "forbidden",
        "model_egress_denied", "timeout", "unsupported", "invalid_request"} else "unexpected_status",
        taskBindingValid=tasks_ok, retrievalComplete=complete, domains=domains,
        planSha256=digest(canonical_json_bytes([dict(domain=i.logical_domain_id, query=i.query_text, path=i.path.value)
                                               for i in plan.items])) if plan else None,
        validation=budget.validation, sourceCheck=asdict(check) if check else None,
        requiredSourcesByStage=stage_hits, manualUsefulness="not_assessed")


@contextmanager
def bindings(budget=None):
    send = service_run.httpx.AsyncClient.send
    async def checked_send(client, request, **kwargs):
        response = await send(client, request, **kwargs)
        if budget is not None and str(request.url) == "http://127.0.0.1:18080/api/v1/agent/queries" and response.status_code != 200:
            budget.stopped = True
        return response
    with patch.multiple(service_run, RUN_ID=RUN_ID, CASES=cases(), LIMITS=LIMITS,
                        assess=lambda spec, response, obs, unused: assess(spec, response, obs, budget)), \
            patch.object(services, "REPO", ServiceRoot()), \
            patch.object(service_run.httpx.AsyncClient, "send", checked_send):
        if budget is None:
            yield
        else:
            with observe(budget): yield


def validate_frozen(expected_sha):
    require(ROOT.is_dir() and {p.name for p in ROOT.iterdir()} == {"manifest.json"}, "retry_resume_forbidden")
    raw = (ROOT / "manifest.json").read_bytes()
    frozen = strict_json(raw)
    require(digest(raw) == expected_sha and canonical_json_bytes(frozen) == canonical_json_bytes(manifest()), "binding_changed")
    return frozen


def preflight(frozen):
    for port in (18090, 19201, 18080, 19091):
        with socket.socket() as listener: listener.bind(("127.0.0.1", port))
    require((REPO / "es-query-service/src/main/resources/application-knowledge-live.yml").read_bytes()
            == (REPO / "es-query-service/target/classes/application-knowledge-live.yml").read_bytes(), "compiled_profile_stale")
    support.check_index(support.load_support(), frozen["indexBinding"])
    with service_run.httpx.Client(trust_env=False, follow_redirects=False, timeout=5) as client:
        for port in (8908, 8909):
            require(client.get(f"http://127.0.0.1:{port}/health").status_code == 200, "local_model_not_ready")


def execute(expected_sha):
    frozen = validate_frozen(expected_sha)
    preflight(frozen)
    save(ROOT / "authorization.json", dict(runId=RUN_ID, frozenHead=frozen["frozenHead"],
        manifestSha256=expected_sha, reference=REFERENCE, limits=LIMITS, cumulativeLimits=dict(e2e=33, model=87)))
    save(ROOT / "started.json", dict(runId=RUN_ID, manifestSha256=expected_sha))
    terminal = dict(runId=RUN_ID, manifestSha256=expected_sha, status="failed", startupRerank=0,
                    indexWrites=0, answer=0, failureReason=None)
    events = []
    def emit(row):
        events.append(row)
        save(ROOT / f"event-{len(events):03d}.json", row)
        if row["stage"] == "case": print(json.dumps({k: row[k] for k in ("caseId", "passed", "status", "calls")}), flush=True)
    budget = None
    try:
        terminal["startupRerank"] = 1
        save(ROOT / "warmup-attempt.json", dict(rerank=1))
        asyncio.run(runpy.run_path(str(REPO / "serviceCenter/warmup-knowledge-reranker.py"))["warmup"]())
        with bindings(), services.local_services(emit, include_agent=True) as (token, binding):
            require(binding == frozen["indexBinding"], "index_changed")
            asyncio.run(service_run.run_server(token, emit, None))
            budget = Budget(ROOT, expected_sha, emit)
            with bindings(budget):
                rows = asyncio.run(service_run.run_server(token, emit, budget))
            require(len(rows) == 10 and all(r["passed"] and r["httpStatus"] == 200 for r in rows), "case_failed")
        require(manifest() == frozen, "final_binding_changed")
        support.check_index(support.load_support(), frozen["indexBinding"])
        require(any(e.get("stage") == "cleanup" and all(e.get(k) is True for k in
                    ("ownedProcessesStopped", "rawLogsDeleted", "secretScanPassed")) for e in events), "cleanup_failed")
        terminal["status"] = "passed"
    except BaseException as error:
        terminal["failureReason"] = "interrupted" if isinstance(error, (KeyboardInterrupt, asyncio.CancelledError)) else "execution_or_case_failed"
    finally:
        if budget:
            budget.journal.close()
            if budget.current is not None and budget.current["caseId"] not in {r["caseId"] for r in budget.results}:
                # A lost HTTP response is an attempted case, not an unexecuted one.
                row = dict(caseId=budget.current["caseId"], passed=False, status="request_incomplete",
                           httpStatus=None, calls=dict(budget.per_case), validation=budget.validation)
                budget.results.append(row)
                emit(dict(stage="case", **row))
        terminal.update(cases=budget.results if budget else [], totals=budget.totals if budget else dict.fromkeys(LIMITS, 0))
        terminal["notExecuted"] = [c["caseId"] for c in cases() if c["caseId"] not in {r["caseId"] for r in terminal["cases"]}]
        terminal["cleanup"] = [e for e in events if e["stage"] in {"cleanup", "runtime_cleanup"}]
        save(ROOT / "result.json", terminal)
    return terminal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "execute"))
    parser.add_argument("--manifest-sha256")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    with java_environment():
        if args.mode == "prepare":
            require(not ROOT.exists(), "run_exists")
            value = manifest()
            ROOT.mkdir(parents=True)
            save(ROOT / "manifest.json", value)
            print(json.dumps(dict(runId=RUN_ID, frozenHead=value["frozenHead"],
                                  manifestSha256=digest((ROOT / "manifest.json").read_bytes()), limits=LIMITS)))
        else:
            require(bool(args.manifest_sha256), "manifest_hash_required")
            result = execute(args.manifest_sha256)
            print(json.dumps(dict(status=result["status"], totals=result["totals"], notExecuted=result["notExecuted"])))
            return 0 if result["status"] == "passed" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
