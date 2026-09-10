"""UAT_01 14.49: one current-root request, three real model tasks, no replay.

Source expectations are post-execution checks, never planner/ranker inputs.
Only finite observations survive; production validators run unchanged once.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
from dataclasses import asdict
import json
import logging
import os
import runpy
import socket
from unittest.mock import patch

from agent_runtime import bootstrap
from agent_runtime.capability_api.contracts import canonical_json_bytes
from agent_runtime.knowledge.evidence.requirement_validation import RequirementCoverageValidator
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from agent_runtime.model.contracts import ModelTaskId
from agent_runtime.model.deepseek.dto import project_deepseek_request
from agent_runtime.model.deepseek.transport import DeepSeekChatTransport, build_deepseek_http_client
from agent_runtime.model.settings import ModelSettings
from tests.evaluation.knowledge.retrieval_benchmark_dataset import load_dataset
from tests.system_e2e import knowledge_activation_local_smoke as smoke
from tests.system_e2e import knowledge_summary_diagnostic_v1 as support_tools
from tests.system_e2e.knowledge_stage_b_citation_check_v2 import check_citations

REPO = support_tools.REPO
RUN_ID = "knowledge-current-chain-v1-20260910-01"
ROOT = REPO / "agent-runtime/target" / RUN_ID
REFERENCE = "UAT_01:14.49"
CASE_ID = "KRB-015"
TASKS = ((ModelTaskId.ACTION_SELECTION, "action-selection-v4"),
         (ModelTaskId.KNOWLEDGE_REWRITE, "8"), (ModelTaskId.KNOWLEDGE_SUMMARY, "7"))
LOCAL_LIMITS = {"search": 4, "embedding": 2, "rerank": 4}
LIMITS = {**LOCAL_LIMITS, "model": 3, "runtime": 1, "warmup": 1,
          "business": 0, "answer": 0, "retry": 0, "resume": 0, "indexWrites": 0}
digest, save, require = support_tools.digest, support_tools.save, smoke.require
_TRANSPORT_COMPLETE = DeepSeekChatTransport.complete


def required_sources(dataset, case):
    sources = {s.id: s for s in dataset.sources}
    required = {f"{name}_{i}": {"chunk": sources[name].chunk_id, "sha256": sources[name].sha256,
                              "clause": anchor}
                for name in case.sources for i, anchor in enumerate(sources[name].anchors, 1)}
    require(1 <= len(required) <= 5 and all(0 < len(v["clause"]) <= 512 for v in required.values()),
            "source_expectations_invalid")
    return required


def manifest():
    # Reuse the existing read-only source/artifact freezer, not its execution.
    base = support_tools.manifest()
    path = "agent-runtime/tests/system_e2e/test_knowledge_current_chain_v1.py"
    base["assets"][path] = digest((REPO / path).read_bytes())
    dataset = load_dataset()  # Includes safe-question and source contract checks.
    case = next(c for c in dataset.cases if c.id == CASE_ID)
    return {"schemaVersion": 1, "runId": RUN_ID, "authorizationReference": REFERENCE,
        "frozenHead": base["frozenHead"], "assets": base["assets"], "artifacts": base["artifacts"],
        "localModels": smoke.support_source.local_models(),
        "datasetSha256": dataset.sha256, "caseId": CASE_ID, "limits": LIMITS,
        "tasks": [{"id": t.value, "version": v} for t, v in TASKS],
        "model": ModelSettings.MODEL_NAME, "requiredSourcesSha256": digest(canonical_json_bytes(required_sources(dataset, case))),
        "knownPaidBefore": 55, "knownEndToEndBefore": 22}


def verify_compiled_profile():
    require((REPO / "es-query-service/src/main/resources/application-knowledge-live.yml").read_bytes()
        == (REPO / "es-query-service/target/classes/application-knowledge-live.yml").read_bytes(), "compiled_profile_stale")


class CurrentModel:
    """One sequential invocation per task; journals are written before HTTP."""
    def __init__(self, root, binding, settings, *, client_factory=build_deepseek_http_client):
        self.root, self.binding, self.settings = root, binding, settings
        self.calls, self.evidence_hashes = [], []
        self.paid, self.expected, self.inflight = 0, None, False
        self.client = client_factory(settings)
        self.client.event_hooks["request"] = [self.outbound]

    async def outbound(self, request):
        require(self.inflight and self.paid < 3 and self.paid == len(self.calls) - 1
            and request.method == "POST" and str(request.url) == ModelSettings.BASE_URL + "/chat/completions"
            and request.content == self.expected, "model_outbound_forbidden")
        ordinal = self.paid + 1
        if ordinal == 1:
            save(self.root / "consumed.json", {"runId": RUN_ID, "manifestSha256": self.binding, "modelAttempts": 1})
        task, version = TASKS[self.paid]
        save(self.root / f"journal-{ordinal:03d}.json", {"ordinal": ordinal, "taskId": task.value,
            "taskVersion": version, "requestSha256": digest(request.content), "manifestSha256": self.binding})
        self.paid = ordinal

    async def complete(self, request, *, call_deadline, transport=None):
        require(not self.inflight and len(self.calls) == self.paid and self.paid < 3
            and (request.task_id, request.task_version) == TASKS[self.paid], "model_task_forbidden")
        self.calls.append(request.task_id.value)
        if request.task_id is ModelTaskId.KNOWLEDGE_SUMMARY:
            payload = json.loads(request.user_payload_json)
            require(payload["schema_version"] == 2 and 1 <= len(payload["evidence"]) <= 8
                and payload["coverage"]["retrieval_complete"] is True
                and payload["coverage"]["domain_coverage_complete"] is True, "partial_retrieval_not_measured")
            self.evidence_hashes = [digest(e["content"].encode()) for e in payload["evidence"]]
        self.expected = canonical_json_bytes(project_deepseek_request(request).payload)
        self.inflight = True
        try:
            active = transport or DeepSeekChatTransport(settings=self.settings, client=self.client)
            return await _TRANSPORT_COMPLETE(active, request, call_deadline=call_deadline)
        finally:
            self.inflight, self.expected = False, None

    async def close(self):
        await self.client.aclose()


async def measure(case, token, root, binding, budget, settings, required, *, client_factory=build_deepseek_http_client):
    model = CurrentModel(root, binding, settings, client_factory=client_factory)
    diagnostics, states, plans, captured = {"phases": [], "failures": []}, [], [], {}
    original_scope = smoke.observation_scope
    original_execute = DefaultKnowledgeRetrievalStage.execute
    original_validate = RequirementCoverageValidator.validate
    original_build = smoke.build_runtime

    def build_managed_runtime(environ, *, model_transport, knowledge_http_client_factory):
        require(model_transport is model, "unexpected_model_fixture")
        # Deepseek owns transport construction. Never switch to stub to make
        # injected transport acceptable; keep the actual production branch.
        return original_build(environ, knowledge_http_client_factory=knowledge_http_client_factory)

    def managed_client(active_settings):
        require(active_settings.provider == settings.provider
            and active_settings.api_key.reveal_for_authorization_header() == settings.api_key.reveal_for_authorization_header(),
            "model_settings_changed")
        return model.client

    async def observe_transport(self, request, *, call_deadline):
        return await model.complete(request, call_deadline=call_deadline, transport=self)

    @contextmanager
    def observe():
        with original_scope() as collector:
            try:
                yield collector
            finally:
                states.extend({k: entry[k] for k in ("taskId", "taskVersion", "status", "failureKind")}
                              for entry in collector.snapshot().model_calls)

    async def execute_stage(self, **kwargs):
        require(not plans, "second_retrieval_forbidden")
        plans.append(kwargs["plan"])
        return await original_execute(self, **kwargs)

    def capture_validation(self, **kwargs):
        captured.update(bundle=kwargs["bundle"], summary_input=kwargs["summary_input"])
        return original_validate(self, **kwargs)

    try:
        # Gold/domain fixtures are not read by this transport or the root.
        environ = {**smoke.ENV, "AGENT_MODEL_PROVIDER": "deepseek",
                   "LLM_API_KEY": settings.api_key.reveal_for_authorization_header()}
        with patch.object(smoke, "ENV", environ), patch.object(smoke, "LIMITS", LOCAL_LIMITS), \
                patch.object(smoke, "build_runtime", build_managed_runtime), \
                patch.object(bootstrap, "build_deepseek_http_client", managed_client), \
                patch.object(DeepSeekChatTransport, "complete", observe_transport), \
                patch.object(smoke, "FixedModel", lambda unused: model), \
                patch.object(smoke, "observation_scope", observe), \
                patch.object(DefaultKnowledgeRetrievalStage, "execute", execute_stage), \
                patch.object(RequirementCoverageValidator, "validate", capture_validation), \
                support_tools.validation_observer(diagnostics):
            result, row = await smoke.run_case(case, token, budget)
        row.pop("fakeModelTasks")
        row.update(modelTaskStates=states, validation=diagnostics, externalModelCalls=model.paid,
                   capabilityId=result.capability_id, plan=None, sourceCheck=None)
        row["retrievalPathsComplete"] = False
        if len(plans) == 1:
            plan = plans[0]
            row["plan"] = {"sha256": digest(canonical_json_bytes(asdict(plan))),
                "domains": list(plan.selected_domain_ids), "items": len(plan.items),
                "requirements": [{"id": r.requirement_id, "domain": r.domain_id, "kind": r.kind.value}
                                 for r in plan.evidence_requirements]}
            expected_counts = {"search": len(plan.items), "rerank": len(plan.evidence_requirements),
                               "embedding": len({i.query_text for i in plan.items if i.path.value == "vector"})}
            row["retrievalPathsComplete"] = (row["counts"] == expected_counts
                and len(row["http"]) == sum(expected_counts.values())
                and all(e["status"] == "completed" and e["httpStatus"] == 200 for e in row["http"]))
        if captured and result.user_result:
            # Match the public JSON shape; Runtime internally freezes maps and
            # arrays. Serialization stays in memory and never logs the points.
            points = json.loads(canonical_json_bytes(result.user_result)).get("points")
            row["sourceCheck"] = asdict(check_citations(**captured, points=points, required=required))
        plan = row["plan"]
        row["passed"] = bool(row["status"] == "success" and row["capabilityId"] == "knowledge.query"
            and model.paid == 3 and len(states) == 3 and all(s["status"] == "succeeded" for s in states)
            and plan and plan["domains"] == ["tax.policy", "tax.law"] and plan["items"] == 4
            and {r["domain"] for r in plan["requirements"]} == {"tax.policy", "tax.law"}
            and row["retrievalPathsComplete"] and not budget.stopped
            and diagnostics == {"phases": ["coverage", "extractive"], "failures": []}
            and row["sourceCheck"] and row["sourceCheck"]["binding_valid"]
            and all(hit for _, hit in row["sourceCheck"]["required_clauses"]))
        return row
    finally:
        await model.close()


def execute(expected_sha):
    require({p.name for p in ROOT.iterdir()} == {"manifest.json"}, "retry_resume_forbidden")
    raw = (ROOT / "manifest.json").read_bytes()
    frozen = json.loads(raw)
    require(digest(raw) == expected_sha and frozen == manifest(), "binding_changed")
    save(ROOT / "started.json", {"runId": RUN_ID, "manifestSha256": expected_sha})
    terminal = {"schemaVersion": 1, "runId": RUN_ID, "manifestSha256": expected_sha, "status": "failed",
        "warmupCalls": 0, "runtimeCalls": 0, "business": 0, "answer": 0, "retry": 0, "resume": 0,
        "indexWrites": 0, "case": None, "limitations": ["single_case_not_stage_b", "no_spring_http_hop", "not_independent_usefulness"]}
    budget = smoke.LocalBudget()
    try:
        dataset = load_dataset()
        case = next(c for c in dataset.cases if c.id == CASE_ID)
        required = required_sources(dataset, case)
        support = smoke.support_source.load_support()
        binding = json.loads(support.checked_bytes(REPO / "serviceCenter/knowledge-runtime-binding.v2.json", dataset.binding_sha256))
        verify_compiled_profile()
        for port in support.PORTS:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", port))
        support.java_executable()
        smoke.support_source.check_index(support, binding)
        terminal["warmupCalls"] = 1
        asyncio.run(runpy.run_path(str(REPO / "serviceCenter/warmup-knowledge-reranker.py"))["warmup"]())
        with support.isolated_services(binding, binding["readAlias"], terminal) as tokens:
            # First credential access, after the safe fixture and local readiness.
            settings = ModelSettings.from_env({"AGENT_MODEL_PROVIDER": "deepseek", "LLM_API_KEY": os.environ.get("LLM_API_KEY", "")})
            terminal["runtimeCalls"] = 1
            terminal["case"] = asyncio.run(measure(case, tokens["admin"], ROOT, expected_sha, budget, settings, required))
        smoke.support_source.check_index(support, binding)
        require(support_tools.artifacts() == frozen["artifacts"], "artifacts_changed")
        require(smoke.support_source.local_models() == frozen["localModels"], "local_models_changed")
        require(all(terminal.get(k) is True for k in ("ownedProcessesStopped", "rawLogsDeleted", "secretScanPassed")), "cleanup_failed")
        require(terminal["case"]["passed"], "case_failed")
        terminal["status"] = "passed"
    except BaseException as error:
        terminal["failureReason"] = "interrupted" if isinstance(error, (KeyboardInterrupt, asyncio.CancelledError)) else "execution_failed"
    finally:
        terminal["counts"] = {key: budget.counts[key] for key in LOCAL_LIMITS}
        terminal["modelAttempts"] = max(int((ROOT / "consumed.json").exists()), len(list(ROOT.glob("journal-*.json"))))
        save(ROOT / "result.json", terminal)
    return terminal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "execute"))
    parser.add_argument("--manifest-sha256")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    try:
        if args.operation == "prepare":
            value = manifest()
            ROOT.mkdir(parents=True, exist_ok=False)
            save(ROOT / "manifest.json", value)
            print(json.dumps({"runId": RUN_ID, "frozenHead": value["frozenHead"],
                              "manifestSha256": digest((ROOT / "manifest.json").read_bytes())}))
            return 0
        require(bool(args.manifest_sha256), "binding_required")
        result = execute(args.manifest_sha256)
        print(json.dumps({k: result[k] for k in ("runId", "status", "modelAttempts", "counts")}))
        return 0 if result["status"] == "passed" else 1
    except Exception:
        raise SystemExit("current_chain.preflight_or_persistence_failed") from None


if __name__ == "__main__":
    raise SystemExit(main())
