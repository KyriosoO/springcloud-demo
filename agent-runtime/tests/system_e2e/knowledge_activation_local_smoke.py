"""Current-root local integration, never live model UAT or a quality benchmark.

Only --execute-local starts isolated auth/ES services. Fixed model responses
exercise the real decoders; the summary deliberately declines to answer.
No model credentials, source bodies, tokens or raw responses are persisted.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import asdict, replace
import hashlib
import json
import socket
import subprocess
import time
from unittest.mock import patch

from agent_runtime.adapters.http_transport import HttpxBusinessDomainTransport
from agent_runtime.capability_api.contracts import CapabilityStatus, OpaqueUserToken
from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.knowledge.evidence.admission import ScoreAwareEvidenceSelector
from agent_runtime.knowledge.retrieval.http import build_knowledge_http_client
from agent_runtime.main import build_runtime
from agent_runtime.model.contracts import ModelTaskId, StructuredFinishKind, StructuredModelResponse
from agent_runtime.observation import observation_scope
from tests.evaluation.knowledge.retrieval_benchmark_dataset import load_dataset
from tests.helpers import scope
from tests.system_e2e import knowledge_stage_b_quality_v3_probe as support_source


CASE_IDS = ("KRB-006", "KRB-022")
ROUTES = {
    ("127.0.0.1", 19201, "/es/knowledge/search"): "search",
    ("127.0.0.1", 8908, "/embed"): "embedding",
    ("127.0.0.1", 8909, "/rerank"): "rerank",
}
LIMITS = {"search": 6, "embedding": 3, "rerank": 3}
ENV = {"AGENT_MODEL_PROVIDER": "stub", "AGENT_KNOWLEDGE_ENABLED": "true",
       "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,tax.law",
       "AGENT_KNOWLEDGE_ES_BASE_URL": "http://127.0.0.1:19201"}


class SmokeFailure(ValueError):
    """Only fixed reason codes cross the diagnostic boundary."""


def require(condition, reason):
    if not condition:
        raise SmokeFailure(reason)


class LocalBudget:
    def __init__(self):
        self.counts = Counter()
        self.stopped = False

    async def request(self, request):
        key = ROUTES.get((request.url.host, request.url.port, request.url.path))
        if (self.stopped or request.method != "POST" or request.url.scheme != "http" or key is None
                or request.url.query or request.url.userinfo
                or key != "search" and "authorization" in request.headers):
            self.stopped = True
            raise SmokeFailure("outbound_not_allowed")
        if self.counts[key] >= LIMITS[key]:
            self.stopped = True
            raise SmokeFailure("local_budget_exhausted")
        self.counts[key] += 1  # Failed attempts consume the same budget.


class FixedModel:
    def __init__(self, case):
        self.case = case
        self.calls = []
        self.evidence_hashes = []

    async def complete(self, request, *, call_deadline):
        require(call_deadline > asyncio.get_running_loop().time(), "fake_model_deadline")
        expected = ((ModelTaskId.ACTION_SELECTION, "action-selection-v4"),
                    (ModelTaskId.KNOWLEDGE_REWRITE, "8"), (ModelTaskId.KNOWLEDGE_SUMMARY, "7"))
        require(len(self.calls) < 3 and (request.task_id, request.task_version) == expected[len(self.calls)],
                "task_binding_changed")
        self.calls.append(request.task_id.value)
        if request.task_id is ModelTaskId.ACTION_SELECTION:
            value = {"capability_id": "knowledge.query"}
        elif request.task_id is ModelTaskId.KNOWLEDGE_REWRITE:
            # Fixture plan only: no source IDs, gold or relevance grades enter it.
            value = {"outcome": "search", "question_kind": "lookup",
                     "queries": [{"domain_id": d, "query": self.case.question} for d in self.case.domains],
                     "requirements": [asdict(r) for r in self.case.requirements], "missing_conditions": []}
        else:
            payload = json.loads(request.user_payload_json)
            require(payload["schema_version"] == 2 and 1 <= len(payload["evidence"]) <= 8,
                    "summary_projection_invalid")
            self.evidence_hashes = [hashlib.sha256(e["content"].encode()).hexdigest() for e in payload["evidence"]]
            # No generated quote or semantic quality claim. The controlled
            # insufficient outcome still exercises both production validators.
            value = {"outcome": "insufficient_evidence", "points": [], "coverage": []}
        return StructuredModelResponse(finish_kind=StructuredFinishKind.STOP,
            content=json.dumps(value, ensure_ascii=False), tool_calls=(), usage_total_tokens=0)


async def run_case(case, token, budget, *, question=None):
    model, clients, selection = FixedModel(case), [], []
    original_select = ScoreAwareEvidenceSelector.select
    before = dict(budget.counts)

    def select(self, **kwargs):
        value = original_select(self, **kwargs)
        selection.append({"version": self.VERSION, "verified": len(kwargs["candidates"]),
                          "selected": len(value.bundle.evidence) if value.bundle else 0})
        return value

    def client_factory(url):
        client = build_knowledge_http_client(url)
        client.event_hooks["request"].append(budget.request)
        clients.append(client)
        return client

    async def forbidden_business(*args, **kwargs):
        raise SmokeFailure("business_call_forbidden")

    question = case.question if question is None else question
    request_scope = scope(question, deadline_monotonic=time.monotonic() + 40)
    request_scope = RequestExecutionScope(context=replace(request_scope.context,
        user_token=OpaqueUserToken.from_raw(token)))
    runtime = None
    try:
        runtime = build_runtime(ENV, model_transport=model, knowledge_http_client_factory=client_factory)
        with patch.object(ScoreAwareEvidenceSelector, "select", select), \
                patch.object(HttpxBusinessDomainTransport, "send", forbidden_business), observation_scope() as collector:
            result = await runtime.ainvoke(question=question, scope=request_scope)
            observed = collector.snapshot()
    finally:
        if runtime is not None:
            await runtime.aclose()
        for client in clients:
            await client.aclose()
    require(all(c.is_closed for c in clients), "runtime_client_leak")
    row = {"caseId": case.id, "status": result.status.value,
           "reason": result.user_result.get("reason") if result.user_result else None,
           "failureCode": result.failure.code if result.failure else None,
           "fakeModelTasks": model.calls, "evidenceHashes": model.evidence_hashes,
           "selection": selection, "clientsClosed": True,
           "http": [{k: entry[k] for k in ("operation", "status", "httpStatus", "durationMs")}
                    for entry in observed.downstream_calls],
           "counts": {k: budget.counts[k] - before.get(k, 0) for k in LIMITS}}
    row["retrievalPathsComplete"] = (row["counts"] == {
        "search": 2 * len(case.domains), "embedding": 1, "rerank": len(case.requirements)}
        and len(row["http"]) == sum(row["counts"].values())
        and all(entry["status"] == "completed" and entry["httpStatus"] == 200 for entry in row["http"]))
    return result, row


async def checks(dataset, tokens, emit, budget):
    cases = {c.id: c for c in dataset.cases}
    sources = {s.id: s for s in dataset.sources}
    for case_id in CASE_IDS:
        case = cases[case_id]
        result, row = await run_case(case, tokens["admin"], budget)
        row["requiredSourcesPresent"] = all(sources[s].sha256 in row["evidenceHashes"] for s in case.sources)
        emit(row)
        require(result.status is CapabilityStatus.NO_RESULT and row["reason"] == "insufficient_evidence"
                and len(row["fakeModelTasks"]) == 3 and len(row["selection"]) == 1
                and row["requiredSourcesPresent"] and row["retrievalPathsComplete"]
                and not budget.stopped, "current_root_smoke_failed")
    result, row = await run_case(cases[CASE_IDS[0]], tokens["unknown"], budget)
    row["caseId"] = "denied"
    emit(row)
    require(result.status is CapabilityStatus.FORBIDDEN and len(row["fakeModelTasks"]) == 2
            and not row["selection"] and row["counts"] == {"search": 2, "embedding": 1, "rerank": 0},
            "denial_boundary_failed")
    result, row = await run_case(cases[CASE_IDS[0]], tokens["admin"], budget,
                                 question="税务查询 test@example.com")
    row["caseId"] = "sensitive"
    emit(row)
    require(result.status is CapabilityStatus.MODEL_EGRESS_DENIED and not row["fakeModelTasks"]
            and not any(row["counts"].values()), "sensitive_boundary_failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-local", action="store_true")
    args = parser.parse_args()
    if not args.execute_local:
        parser.error("Explicit local-service execution required; no model outbound is allowed")
    emit = lambda row: print(json.dumps(row, sort_keys=True), flush=True)
    terminal = {"status": "failed", "externalModelCalls": 0, "indexWrites": 0,
                "businessCalls": 0, "retry": 0, "resume": 0, "startupRerankCalls": 0,
                "limitations": ["fixed_model_not_real_llm", "not_effectiveness_uat", "no_spring_http_hop"]}
    budget = LocalBudget()
    try:
        support = support_source.load_support()
        dataset = load_dataset()
        binding = json.loads(support.checked_bytes(support_source.REPO / "serviceCenter/knowledge-runtime-binding.v2.json",
                                                   dataset.binding_sha256))
        profile = "es-query-service/src/main/resources/application-knowledge-live.yml"
        compiled = "es-query-service/target/classes/application-knowledge-live.yml"
        require((support_source.REPO / profile).read_bytes() == (support_source.REPO / compiled).read_bytes(),
                "compiled_profile_stale")
        artifacts = support_source.artifact_hashes()
        emit({"event": "prepared", "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=support_source.REPO, text=True).strip(),
            "artifactHashes": artifacts, "caseIds": CASE_IDS, "limits": LIMITS,
            "taskVersions": ["action-selection-v4", "8", "7"], "externalModelCalls": 0})
        for port in support.PORTS:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", port))
        support.java_executable()
        support_source.check_index(support, binding)
        terminal["indexSnapshotVerified"] = True
        # Reuse the existing synthetic warmup, outside user-request budgets.
        import runpy
        warmup = runpy.run_path(str(support_source.REPO / "serviceCenter/warmup-knowledge-reranker.py"))
        terminal["startupRerankCalls"] = 1
        asyncio.run(warmup["warmup"]())
        with support.isolated_services(binding, binding["readAlias"], terminal) as tokens:
            asyncio.run(checks(dataset, tokens, emit, budget))
        support_source.check_index(support, binding)
        require(support_source.artifact_hashes() == artifacts, "service_artifacts_changed")
        terminal["status"] = "passed"
    except Exception as exc:
        # Deliberately omit exception/HTTP text: only local fixed codes survive.
        terminal["failureReason"] = str(exc) if isinstance(exc, SmokeFailure) else "local_execution_failed"
    finally:
        terminal["counts"] = {k: budget.counts[k] for k in LIMITS}
        emit(terminal)
    return 0 if terminal["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
