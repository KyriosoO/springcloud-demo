"""One bounded Stage B Spring-to-production-Runtime run. No automatic retries.

--prepare and --check-environment NEVER read model credentials or call a model.
--execute is the only credential-reading mode; every paid HTTP is journaled
before sending. Gold is only consulted after the production invocation.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
import socket
import subprocess
from unittest.mock import patch

import httpx
import uvicorn

from agent_runtime import bootstrap
from agent_runtime.api.app import create_app
from agent_runtime.api.settings import RuntimeHttpSettings
from agent_runtime.main import build_runtime, build_stub_runtime
from agent_runtime.knowledge.retrieval.http import build_knowledge_http_client
from agent_runtime.knowledge.retrieval.es_adapter import EsKnowledgeSearchAdapter
from agent_runtime.knowledge.retrieval.bge_rerank import BgeRerankAdapter
from agent_runtime.knowledge.retrieval.fusion import ReciprocalRankFusion
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from agent_runtime.knowledge.evidence.builder import DeterministicEvidenceSelector
from agent_runtime.model.contracts import QuestionEgressDisposition
from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.model.settings import ModelSettings
from agent_runtime.observation import observation_scope
from tests.system_e2e.knowledge_stage_b_cases import CASES, GOLD, LIMITS, assess
from tests.system_e2e.knowledge_stage_b_services import REPO, local_services

RUN_ID = "knowledge-stage-b-uat-v1-20260904-run-01"
ENV = {"AGENT_MODEL_PROVIDER": "deepseek", "AGENT_KNOWLEDGE_ENABLED": "true",
       "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,tax.law",
       "AGENT_KNOWLEDGE_ES_BASE_URL": "http://127.0.0.1:19201"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO).decode().strip()


def write_exclusive(path, value):
    with path.open("x", encoding="utf-8") as target:
        target.write(json.dumps(value, ensure_ascii=True, sort_keys=True) + "\n")
        target.flush()
        os.fsync(target.fileno())


def prepare(root):
    if git("status", "--porcelain"):
        raise ValueError("stage_b.freeze_requires_clean_worktree")
    for item in CASES:
        if QuestionEgressGuard().evaluate(item["question"]).disposition is not QuestionEgressDisposition.ALLOWED:
            raise ValueError("stage_b.fixture_not_model_safe")
    binding = json.loads((REPO / "serviceCenter/knowledge-runtime-binding.v1.json").read_text(encoding="utf-8-sig"))
    prefixes = ("agent-runtime/src/", "agent-runtime/tests/system_e2e/knowledge_stage_b_",
                "es-query-service/src/main/", "agent-service/src/main/", "agent-contracts/",
                "serviceCenter/knowledge-runtime-binding.v1.json")
    files = git("ls-files").splitlines()
    assets = {name: digest((REPO / name).read_bytes()) for name in files if name.startswith(prefixes)}
    executable_paths = [REPO / "auth-service/target/auth-service-0.0.1-SNAPSHOT.jar"]
    for module in ("agent-service", "es-query-service"):
        classpath = REPO / module / "target/stage-b-classpath.txt"
        executable_paths.append(classpath)
        executable_paths.extend(p for p in (REPO / module / "target/classes").rglob("*") if p.is_file())
        executable_paths.extend(Path(p) for p in classpath.read_text().strip().split(os.pathsep))
    executable_hashes = {str(p.resolve()): digest(p.read_bytes()) for p in executable_paths}
    manifest = {"schemaVersion": 1, "runId": RUN_ID, "frozenHead": git("rev-parse", "HEAD"),
                "authorizationReference": "P3_00:WP-KRETRIEVAL-UAT-01", "limits": LIMITS,
                "cases": CASES, "gold": GOLD, "environment": ENV, "indexBinding": binding,
                "assets": assets, "executables": executable_hashes,
                "taskVersions": {"selection": "action-selection-v4", "rewrite": "3", "summary": "4"},
                "evaluation": "manual-source-gold/exact-clause-and-domain; no model self-score; failed case stops batch"}
    root.mkdir(parents=True, exist_ok=True)
    write_exclusive(root / "manifest.json", manifest)
    return manifest


def validate_manifest(root, expected_sha=None):
    raw = (root / "manifest.json").read_bytes()
    if expected_sha is not None and digest(raw) != expected_sha:
        raise ValueError("stage_b.manifest_sha_mismatch")
    manifest = json.loads(raw)
    if (manifest["runId"] != RUN_ID or manifest["frozenHead"] != git("rev-parse", "HEAD")
            or git("status", "--porcelain") or manifest["limits"] != LIMITS
            or manifest["cases"] != list(CASES) or manifest["gold"] != GOLD
            or manifest["environment"] != ENV):
        raise ValueError("stage_b.frozen_binding_invalid")
    for name, expected in manifest["assets"].items():
        path = (REPO / name).resolve()
        if not path.is_relative_to(REPO) or digest(path.read_bytes()) != expected:
            raise ValueError("stage_b.frozen_asset_changed")
    for name, expected in manifest.get("executables", {}).items():
        if digest(Path(name).read_bytes()) != expected:
            raise ValueError("stage_b.executable_changed")
    if any((root / name).exists() for name in ("consumed.json", "journal.jsonl", "result.json")):
        raise ValueError("stage_b.retry_resume_forbidden")
    return manifest, digest(raw)


class Budget:
    def __init__(self, root, manifest_sha, emit):
        self.root, self.manifest_sha, self.emit = root, manifest_sha, emit
        self.totals = {name: 0 for name in LIMITS}
        self.current = None
        self.per_case = {}
        self.summary_evidence = []
        self.observation = None
        self.journal = (root / "journal.jsonl").open("x", encoding="utf-8")
        self.seen_tasks = set()
        self.stopped = False
        self.results = []
        self.probes = []

    def begin(self, case_spec):
        if self.stopped or self.totals["e2e"] >= LIMITS["e2e"]:
            raise ValueError("stage_b.batch_stopped")
        self.current = case_spec
        self.per_case = {name: 0 for name in LIMITS}
        self.summary_evidence, self.observation, self.seen_tasks = [], None, set()
        self.probes = []
        self.totals["e2e"] += 1

    def count(self, kind):
        per_limits = {"model": 3, "search": 4, "embedding": 2, "rerank": 2, "business": 0}
        if self.current is None or self.stopped or kind not in per_limits:
            raise ValueError("stage_b.unexpected_outbound")
        if self.totals[kind] >= LIMITS[kind] or self.per_case[kind] >= per_limits[kind]:
            self.stopped = True
            raise ValueError("stage_b.budget_exceeded")
        self.totals[kind] += 1
        self.per_case[kind] += 1

    async def model_request(self, request):
        if str(request.url) != ModelSettings.BASE_URL + "/chat/completions" or request.method != "POST":
            raise ValueError("stage_b.unexpected_model_endpoint")
        body = json.loads(request.content)
        payload = json.loads(body["messages"][1]["content"])
        fields = set(payload)
        if fields == {"question", "capabilities"}:
            task = "action_selection"
        elif fields == {"question", "domains"}:
            task = "knowledge_rewrite"
        elif fields == {"schema_version", "question", "coverage", "evidence"} and payload["schema_version"] == 1:
            task = "knowledge_summary"
        else:
            raise ValueError("stage_b.unexpected_model_task")
        expected_task = ("action_selection", "knowledge_rewrite", "knowledge_summary")[min(len(self.seen_tasks), 2)]
        if task in self.seen_tasks or task != expected_task or payload["question"] != self.current["question"]:
            self.stopped = True
            raise ValueError("stage_b.model_retry_or_input_mismatch")
        if task == "knowledge_summary":
            self.summary_evidence = [{"sha256": digest(item["content"].encode()), "content": item["content"]}
                                     for item in payload["evidence"]]
        self.count("model")
        self.seen_tasks.add(task)
        if self.totals["model"] == 1:
            write_exclusive(self.root / "consumed.json", {"runId": RUN_ID, "manifestSha256": self.manifest_sha,
                "rule": "first_model_http_attempt; no retry/resume"})
        self.journal.write(json.dumps({"caseId": self.current["caseId"], "task": task,
                                      "ordinal": self.totals["model"]}) + "\n")
        self.journal.flush()
        os.fsync(self.journal.fileno())

    async def downstream_request(self, request):
        endpoints = {"http://127.0.0.1:19201/es/knowledge/search": "search",
                     "http://127.0.0.1:8908/embed": "embedding", "http://127.0.0.1:8909/rerank": "rerank"}
        kind = endpoints.get(str(request.url))
        if request.method != "POST" or kind is None:
            raise ValueError("stage_b.unexpected_downstream")
        self.count(kind)

    async def business_request(self, *args, **kwargs):
        self.count("business")


class ObservedRuntime:
    def __init__(self, delegate, budget):
        self.delegate, self.budget = delegate, budget

    async def ainvoke(self, *, question, scope):
        with observation_scope() as collector:
            outcome = await self.delegate.ainvoke(question=question, scope=scope)
        self.budget.observation = collector.snapshot()
        return outcome

    async def aclose(self):
        await self.delegate.aclose()


async def run_server(token, emit, budget=None):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 19091))
    clients = []
    original_factory = bootstrap.build_deepseek_http_client
    original_search, original_rerank = EsKnowledgeSearchAdapter.search, BgeRerankAdapter.rerank
    original_fuse, original_stage = ReciprocalRankFusion.fuse, DefaultKnowledgeRetrievalStage.execute
    original_select = DeterministicEvidenceSelector.select

    def identities(items):
        return [{"chunkId": c.chunk_id, "sha256": c.content_sha256} for c in items]

    async def search_probe(adapter, **kwargs):
        result = await original_search(adapter, **kwargs)
        if budget:
            budget.probes.append({"stage": "path", "domain": result.logical_domain_id, "path": result.path.value,
                "status": result.kind.value, "candidates": identities(result.candidates)})
        return result

    async def rank_probe(adapter, **kwargs):
        scores = await original_rerank(adapter, **kwargs)
        if budget:
            ordered = sorted(scores, key=lambda s: (-s.score, s.candidate_index))
            budget.probes.append({"stage": "rerank", "querySha256": digest(kwargs["query"].encode()),
                "candidates": identities([kwargs["candidates"][s.candidate_index] for s in ordered])})
        return scores

    def fusion_probe(fusion, sets):
        result = original_fuse(fusion, sets)
        if budget:
            budget.probes.append({"stage": "fusion", "domains": sorted({s.logical_domain_id for s in sets}),
                "candidates": identities([c.candidate for c in result])})
        return result

    async def stage_probe(stage, **kwargs):
        result = await original_stage(stage, **kwargs)
        if budget and result.batch:
            budget.probes.append({"stage": "final_rank", "candidates": identities([c.candidate for c in result.batch.candidates])})
        return result

    def evidence_probe(selector, **kwargs):
        result = original_select(selector, **kwargs)
        if budget:
            budget.probes.append({"stage": "evidence", "sufficient": result.sufficient,
                "candidates": identities(result.bundle.evidence) if result.bundle else []})
        return result

    def model_factory(settings):
        client = original_factory(settings)
        client.event_hooks["request"].append(budget.model_request)
        clients.append(client)
        return client

    def knowledge_factory(url):
        client = build_knowledge_http_client(url)
        client.event_hooks["request"].append(budget.downstream_request)
        clients.append(client)
        return client

    def runtime_factory():
        if budget is None:
            return build_stub_runtime()
        # This is the only credential read. Never serialize the resulting mapping.
        env = {**ENV, "LLM_API_KEY": os.environ["LLM_API_KEY"]}
        return ObservedRuntime(build_runtime(env, knowledge_http_client_factory=knowledge_factory), budget)

    app = create_app(RuntimeHttpSettings(host="127.0.0.1", port=19091), runtime_factory)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=19091, access_log=False, log_config=None, log_level="critical"))
    task = None
    with (patch.object(bootstrap, "build_deepseek_http_client", model_factory), patch(
            "agent_runtime.main.HttpxBusinessDomainTransport.send", budget.business_request if budget else None),
            patch.object(EsKnowledgeSearchAdapter, "search", search_probe),
            patch.object(BgeRerankAdapter, "rerank", rank_probe), patch.object(ReciprocalRankFusion, "fuse", fusion_probe),
            patch.object(DefaultKnowledgeRetrievalStage, "execute", stage_probe),
            patch.object(DeterministicEvidenceSelector, "select", evidence_probe)):
        try:
            task = asyncio.create_task(server.serve())
            async with httpx.AsyncClient(trust_env=False, timeout=65, follow_redirects=False) as client:
                deadline = asyncio.get_running_loop().time() + 60
                while asyncio.get_running_loop().time() < deadline:
                    if task.done():
                        await task
                        raise RuntimeError("stage_b.runtime_stopped")
                    try:
                        ready = await client.get("http://127.0.0.1:18080/actuator/health/readiness", timeout=2)
                        if ready.status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    await asyncio.sleep(.3)
                else:
                    raise RuntimeError("stage_b.spring_readiness_timeout")
                emit({"stage": "spring_runtime_ready", "mode": "live" if budget else "readiness_only"})
                if budget is None:
                    probe = await client.post("http://127.0.0.1:18080/api/v1/agent/queries",
                        json={"question": "查询未知能力"}, headers={"Authorization": "Bearer " + token})
                    # Existing AgentQueryController maps UNSUPPORTED to HTTP 422.
                    if probe.status_code != 422 or probe.json().get("status") != "unsupported":
                        raise RuntimeError("stage_b.real_auth_stub_smoke_failed")
                    emit({"stage": "spring_auth_stub_smoke", "status": "unsupported", "model": 0, "knowledge": 0})
                    return []
                results = []
                for item in CASES:
                    budget.begin(item)
                    response = await client.post("http://127.0.0.1:18080/api/v1/agent/queries",
                        json={"question": item["question"]}, headers={"Authorization": "Bearer " + token,
                        "X-Correlation-Id": item["caseId"]})
                    data = response.json()
                    if budget.observation is None:
                        verdict = {"passed": False, "status": "ingress_or_runtime_failure"}
                    else:
                        verdict = assess(item, data, budget.observation, budget.summary_evidence)
                    row = {"caseId": item["caseId"], "httpStatus": response.status_code, **verdict,
                           "calls": dict(budget.per_case), "modelTasks": [
                               {key: v[key] for key in ("taskId", "taskVersion", "status", "failureKind")}
                               for v in budget.observation.model_calls] if budget.observation else [],
                           "evidenceContentHashes": [e["sha256"] for e in budget.summary_evidence]}
                    row["retrievalStages"] = list(budget.probes)
                    results.append(row)
                    budget.results.append(row)
                    emit({"stage": "case", **row})
                    if not verdict["passed"] or budget.stopped:
                        budget.stopped = True
                        break
                return results
        finally:
            server.should_exit = True
            if task is not None:
                try:
                    await asyncio.wait_for(task, timeout=10)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
            for client in clients:
                await client.aclose()
            emit({"stage": "runtime_cleanup", "clientsClosed": all(c.is_closed for c in clients)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "check-environment", "execute"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest-sha256")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    args.root.mkdir(parents=True, exist_ok=True)
    if args.mode == "prepare":
        manifest = prepare(args.root)
        print(json.dumps({"frozenHead": manifest["frozenHead"], "manifestSha256": digest((args.root / "manifest.json").read_bytes()), "limits": LIMITS}))
        return
    budget, rows, failure = None, [], None
    name = "environment.jsonl" if args.mode == "check-environment" else "evidence.jsonl"
    if args.mode == "execute":
        if not args.manifest_sha256:
            raise ValueError("stage_b.manifest_sha_required")
        _, manifest_sha = validate_manifest(args.root, args.manifest_sha256)
    with (args.root / name).open("x", encoding="utf-8") as evidence:
        def emit(value):
            evidence.write(json.dumps(value, ensure_ascii=True) + "\n")
            evidence.flush()
            os.fsync(evidence.fileno())
            print(json.dumps({k: v for k, v in value.items() if k not in {"evidenceContentHashes", "retrievalStages"}}), flush=True)
        try:
            if args.mode == "execute":
                budget = Budget(args.root, manifest_sha, emit)
            with local_services(emit, include_agent=True) as (token, binding):
                if args.mode == "execute":
                    manifest = json.loads((args.root / "manifest.json").read_bytes())
                    if binding != manifest["indexBinding"]:
                        raise ValueError("stage_b.index_binding_changed")
                rows = asyncio.run(run_server(token, emit, budget))
        except (Exception, KeyboardInterrupt) as exc:
            failure = type(exc).__name__
            emit({"stage": "failure", "kind": failure})
        finally:
            if budget:
                budget.journal.close()
                rows = budget.results
                passed = failure is None and len(rows) == len(CASES) and all(r["passed"] for r in rows)
                write_exclusive(args.root / "result.json", {"schemaVersion": 1, "runId": RUN_ID,
                    "manifestSha256": budget.manifest_sha, "status": "passed" if passed else "failed",
                    "failureKind": failure, "cases": rows, "totals": budget.totals,
                    "notExecuted": [c["caseId"] for c in CASES if c["caseId"] not in {r["caseId"] for r in rows}]})
    if failure or budget and (budget.stopped or len(rows) != len(CASES)):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
