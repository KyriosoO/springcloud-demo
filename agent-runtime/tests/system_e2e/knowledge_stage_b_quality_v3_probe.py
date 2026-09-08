"""No-paid diagnostic of current retrieval/Evidence, NOT Rewrite/Summary UAT.

Manual plans are frozen before I/O. Gold is used only after ranking/selection;
it cannot change queries, scores, candidates, limits or production behavior.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import types

import httpx

from agent_runtime.api.cancellation import MutableCancellationSignal
from agent_runtime.capability_api.contracts import OpaqueUserToken
from agent_runtime.knowledge.contracts import (
    KNOWLEDGE_QUALITY_VERSION_V3, KnowledgeEvidenceInput, KnowledgeEvidenceRequirement,
    KnowledgeQuestionKind, KnowledgeRequirementKind, KnowledgeRetrievalContext,
    KnowledgeRetrievalPlan, RetrievalPath, RetrievalPlanItem, RetrievalStageKind,
)
from agent_runtime.knowledge.evidence.builder import DeterministicEvidenceSelector, EvidenceIntegrityVerifier
from agent_runtime.knowledge.evidence.catalog import KnowledgeEgressPolicyCatalog
from agent_runtime.knowledge.evidence.contracts import KnowledgeEvidenceLimits, KnowledgeRequirementSummaryInput
from agent_runtime.knowledge.evidence.policy import KnowledgeEvidenceEgressDecider
from agent_runtime.knowledge.evidence.summary_task_v6 import requirement_summary_input_json
from agent_runtime.knowledge.evidence_requirements import validate_plan_requirements, validate_requirement_focuses
from agent_runtime.knowledge.question_semantics import QuestionSemanticGuard
from agent_runtime.knowledge.retrieval.bge_embedding import BgeM3EmbeddingAdapter
from agent_runtime.knowledge.retrieval.bge_rerank import BgeRerankAdapter
from agent_runtime.knowledge.retrieval.es_adapter import EsKnowledgeSearchAdapter
from agent_runtime.knowledge.retrieval.es_adapter import _unique, _reject_constant
from agent_runtime.knowledge.retrieval.fusion import ReciprocalRankFusion
from agent_runtime.knowledge.retrieval.http import HttpxKnowledgeTransport, build_knowledge_http_client
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from agent_runtime.model.contracts import QuestionEgressDisposition
from agent_runtime.model.input_guard import QuestionEgressGuard
from tests.system_e2e.knowledge_stage_b_cases import CASES, GOLD

REPO = Path(__file__).resolve().parents[3]
HELPER = REPO / "knowledge-corpus-tools/scripts/validate-policy-vector-typed-v1.py"
HELPER_SHA = "54ec6f9a95f187c48a5dcd512373fea185358a2cef477e2fd118f11a413c191d"
BINDING_SHA = "a6d2c00eddf46827750a8100357c909bab944f27d10b41218e2c9754457f9682"
CATALOG_SHA = "87c3963a15ea98cca444438c3439094b6881bba31ceaef265db92f5caab21b00"
PER_CASE = {"search": 4, "embedding": 2, "rerank": 4}
# These are explicit offline fixture decisions, never an online intent resolver.
SPECIFICATIONS = (
    ("UAT-KB-015a", "lookup", (("tax.policy", "增值税政策 住宿服务 生活服务 定义"),),
     (("tax.policy", "subject_scope", "增值税政策中住宿服务如何定义"), ("tax.policy", "rule", "增值税政策中生活服务的住宿服务分类"))),
    ("UAT-KB-004", "lookup", (("tax.policy", "住宿服务 生活服务 政策分类"), ("tax.law", "增值税法 税率")),
     (("tax.policy", "subject_scope", "住宿服务的政策分类"), ("tax.policy", "rule", "增值税政策中住宿服务的生活服务分类"), ("tax.law", "rule", "增值税法的税率规定"))),
    ("UAT-KB-002", "applicability", (("tax.policy", "一般纳税人 一般计税 2026年 住宿服务"), ("tax.law", "2026年 增值税法 税率")),
     (("tax.policy", "subject_scope", "住宿服务的增值税分类"), ("tax.law", "rule", "一般纳税人采用一般计税方法提供住宿服务适用何种增值税税率"), ("tax.law", "temporal_scope", "2026年增值税法施行时间"))),
    ("UAT-KB-003", "lookup", (("tax.policy", "住宿服务 不动产租赁 增值税分类区别"),),
     (("tax.policy", "subject_scope", "增值税政策中住宿服务如何定义"), ("tax.policy", "rule", "不动产租赁的增值税分类和定义"))),
    ("UAT-KB-006", "applicability", (("tax.policy", "2016年 一般纳税人 一般计税 住宿服务 税率"),),
     (("tax.policy", "subject_scope", "住宿服务的增值税分类"), ("tax.policy", "rule", "2016年一般纳税人按一般计税提供住宿服务的增值税税率"), ("tax.policy", "temporal_scope", "2016年增值税政策施行时间"))),
    ("UAT-KB-015b", "applicability", (("tax.policy", "2026年 一般纳税人 一般计税 酒店住宿服务 分类依据"), ("tax.law", "2026年 增值税法 税率")),
     (("tax.policy", "subject_scope", "酒店住宿服务的增值税分类依据"), ("tax.law", "rule", "一般纳税人采用一般计税的酒店住宿服务增值税税率"), ("tax.law", "temporal_scope", "2026年增值税法施行时间"))),
    ("UAT-KB-016", "lookup", (("tax.policy", "财税〔2011〕100号 软件产品 即征即退 证明材料"),),
     (("tax.policy", "rule", "软件产品享受增值税即征即退需取得哪些证明材料"),)),
    ("UAT-KB-008", "lookup", (("tax.law", "增值税法 第十条 销售服务 税率"),),
     (("tax.law", "rule", "增值税法第十条规定销售服务适用的税率"),)),
)
LIMITS = {"search": sum(len(s[2]) * 2 for s in SPECIFICATIONS),
          "embedding": sum(len(s[2]) for s in SPECIFICATIONS),
          "rerank": sum(len(s[3]) for s in SPECIFICATIONS)}


def plan_for(spec):
    case_id, kind, queries, requirements = spec
    original = next(c["question"] for c in CASES if c["caseId"] == case_id)
    plan = KnowledgeRetrievalPlan(config_version="knowledge-flow-config-v1",
        quality_version=KNOWLEDGE_QUALITY_VERSION_V3, question_kind=KnowledgeQuestionKind(kind),
        selected_domain_ids=tuple(d for d, _ in queries),
        evidence_requirements=tuple(KnowledgeEvidenceRequirement(requirement_id=f"r{i}",
            domain_id=d, kind=KnowledgeRequirementKind(role), focus=focus)
            for i, (d, role, focus) in enumerate(requirements, 1)),
        items=tuple(RetrievalPlanItem(logical_domain_id=d, query_text=query, path=p, candidate_limit=20, ordinal=i)
            for i, (d, query, p) in enumerate(((d, q, p) for d, q in queries
                for p in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR)), 1)))
    validate_plan_requirements(quality_version=plan.quality_version, question_kind=plan.question_kind,
                              requirements=plan.evidence_requirements, domain_ids=plan.selected_domain_ids)
    validate_requirement_focuses(original_question=original, requirements=plan.evidence_requirements,
                                 semantic_guard=QuestionSemanticGuard())
    if any(QuestionEgressGuard().evaluate(text).disposition is not QuestionEgressDisposition.ALLOWED
           for text in (original, *(q for _, q in queries))):
        raise ValueError("probe_fixture_unsafe")
    return original, plan


def identity(candidate):
    return {"chunkId": candidate.chunk_id, "sha256": candidate.content_sha256}


class Budget:
    def __init__(self):
        self.total = dict.fromkeys(LIMITS, 0)
        self.current = dict.fromkeys(LIMITS, 0)
        self.stopped = False

    async def request(self, request):
        routes = {"http://127.0.0.1:19201/es/knowledge/search": "search",
                  "http://127.0.0.1:8908/embed": "embedding", "http://127.0.0.1:8909/rerank": "rerank"}
        key = routes.get(str(request.url))
        if (self.stopped or request.method != "POST" or key is None
                or key != "search" and "authorization" in request.headers
                or key is not None and (self.total[key] >= LIMITS[key] or self.current[key] >= PER_CASE[key])):
            self.stopped = True
            raise ValueError("probe_outbound_rejected")
        self.total[key] += 1
        self.current[key] += 1


class ObservedSearch:
    def __init__(self, delegate, binding, rows):
        self.delegate, self.binding, self.rows = delegate, binding, rows

    async def search(self, **kwargs):
        result = await self.delegate.search(**kwargs)
        if result.candidates and result.index_snapshot_id != self.binding[
                "policySnapshotId" if result.logical_domain_id == "tax.policy" else "lawSnapshotId"]:
            raise ValueError("probe_snapshot_changed")
        self.rows.append({"stage": "path", "domain": result.logical_domain_id, "path": result.path.value,
                          "status": result.kind.value, "candidates": [identity(c) for c in result.candidates]})
        return result


class ObservedFusion(ReciprocalRankFusion):
    def __init__(self, rows):
        self.rows = rows

    def fuse(self, values):
        result = super().fuse(values)
        self.rows.append({"stage": "fusion", "domains": list(dict.fromkeys(x.logical_domain_id for x in values)),
                          "candidates": [identity(c.candidate) for c in result]})
        return result


class ObservedRerank:
    def __init__(self, delegate, rows):
        self.delegate, self.rows = delegate, rows

    async def rerank(self, **kwargs):
        result = await self.delegate.rerank(**kwargs)
        # Observer records scores, but sorting authority remains production ranker.
        self.rows.append({"stage": "rerank", "ordinal": 1 + sum(r["stage"] == "rerank" for r in self.rows),
            "candidates": [{**identity(kwargs["candidates"][s.candidate_index]), "score": s.score} for s in result]})
        return result


def assess_sources(case_id, rows, batch, bundle, summary_input):
    expected = next(c["requiredGold"] for c in CASES if c["caseId"] == case_id)
    checks = {}
    for label in expected:
        gold = GOLD[label]
        def matches(c):
            return c.chunk_id == gold["chunk"] and c.content_sha256 == gold["sha256"] and gold["clause"] in c.content
        paths = [{"domain": r["domain"], "path": r["path"], "rank": i}
            for r in rows if r["stage"] == "path" for i, c in enumerate(r["candidates"], 1)
            if c == {"chunkId": gold["chunk"], "sha256": gold["sha256"]}]
        ranked = [c.rank for c in batch.candidates if matches(c.candidate)]
        selected = [i for i, c in enumerate(bundle.evidence, 1) if matches(c)] if bundle else []
        allowed = bool(selected) and summary_input is not None and any(
            hashlib.sha256(c.content.encode()).hexdigest() == gold["sha256"] and gold["clause"] in c.content
            for c in summary_input.evidence)
        checks[label] = {"pathRanks": paths, "finalRank": ranked[0] if ranked else None,
                         "evidenceRank": selected[0] if selected else None, "allowedOriginalClause": allowed}
    return checks


async def diagnose(binding, token, emit, budget, *, client_factory=build_knowledge_http_client):
    catalog = KnowledgeEgressPolicyCatalog.load_current_resource()
    if catalog.snapshot.source_sha256 != CATALOG_SHA:
        raise ValueError("probe_catalog_changed")
    async with client_factory("http://127.0.0.1:19201") as es, \
            client_factory("http://127.0.0.1:8908") as embedding, client_factory("http://127.0.0.1:8909") as rerank:
        for client in (es, embedding, rerank):
            client.event_hooks["request"].append(budget.request)
        complete = []
        for spec in SPECIFICATIONS:
            case_id = spec[0]
            question, plan = plan_for(spec)
            budget.current = dict.fromkeys(LIMITS, 0)
            rows = []
            stage = DefaultKnowledgeRetrievalStage(
                search=ObservedSearch(EsKnowledgeSearchAdapter(HttpxKnowledgeTransport(es)), binding, rows),
                embedding=BgeM3EmbeddingAdapter(HttpxKnowledgeTransport(embedding)),
                rerank=ObservedRerank(BgeRerankAdapter(HttpxKnowledgeTransport(rerank)), rows),
                fusion=ObservedFusion(rows))
            context = KnowledgeRetrievalContext(request_id=case_id, correlation_id=case_id, subject="admin",
                user_token=OpaqueUserToken.from_raw(token), deadline_monotonic=time.monotonic() + 30,
                cancellation=MutableCancellationSignal())
            result = await stage.execute(plan=plan, context=context, timeout_s=20)
            for row in rows:
                emit({"event": "retrieval_stage", "caseId": case_id, **row})
            if result.kind is not RetrievalStageKind.SUCCESS or budget.stopped:
                emit({"event": "case", "caseId": case_id, "status": "retrieval_failed", "kind": result.kind.value,
                      "stageCode": result.stage_code.value if result.stage_code else None, "counts": dict(budget.current)})
                raise ValueError("probe_retrieval_failed")
            value = KnowledgeEvidenceInput(original_question=question, selected_query=plan.items[0].query_text,
                selected_domain_ids=plan.selected_domain_ids, coverage=result.coverage, batch=result.batch,
                question_policy_version=QuestionEgressGuard().evaluate(question).policy_version, question_egress_denied=False,
                quality_version=plan.quality_version, question_kind=plan.question_kind,
                evidence_requirements=plan.evidence_requirements)
            selection = DeterministicEvidenceSelector().select(candidates=EvidenceIntegrityVerifier().verify(input=value),
                input=value, minimized_question=question, limits=KnowledgeEvidenceLimits.quality_v3())
            policy = KnowledgeEvidenceEgressDecider().decide(bundle=selection.bundle, catalog=catalog) if selection.bundle else None
            if policy and policy.allowed:
                projected = policy.summary_input
                payload = KnowledgeRequirementSummaryInput(schema_version=2, question=projected.question,
                    coverage=projected.coverage, evidence=projected.evidence, requirements=plan.evidence_requirements)
                if len(requirement_summary_input_json(payload).encode()) > KnowledgeEvidenceLimits.quality_v3().max_summary_input_bytes:
                    raise ValueError("probe_payload_limit")
            checks = assess_sources(case_id, rows, result.batch, selection.bundle, policy.summary_input if policy else None)
            complete.append(all(c["allowedOriginalClause"] for c in checks.values()))
            emit({"event": "case", "caseId": case_id, "status": "measured", "counts": dict(budget.current),
                "coverageComplete": result.coverage.complete, "selectionSufficient": selection.sufficient,
                "policyAllowed": policy.allowed if policy else False, "requiredSources": checks,
                "ranked": [{**identity(c.candidate), "rank": c.rank, "requirementIds": list(c.requirement_ids)}
                           for c in result.batch.candidates],
                "evidence": [identity(c) for c in selection.bundle.evidence] if selection.bundle else []})
        return {"casesMeasured": len(complete), "casesWithRequiredSources": sum(complete)}


def load_support():
    raw = HELPER.read_bytes()
    if hashlib.sha256(raw).hexdigest() != HELPER_SHA:
        raise ValueError("probe_support_changed")
    module = types.ModuleType("quality_probe_service_support")
    module.__file__ = str(HELPER)
    exec(compile(raw, str(HELPER), "exec"), module.__dict__)
    return module


def emit_line(stream, value):
    raw = (json.dumps(value, ensure_ascii=True, sort_keys=True, allow_nan=False) + "\n").encode()
    if len(raw) > 65536:
        raise ValueError("probe_result_limit")
    stream.write(raw)
    stream.flush()
    os.fsync(stream.fileno())


def artifact_hashes():
    paths = ("auth-service/target/auth-service-0.0.1-SNAPSHOT.jar", "es-query-service/target/stage-b-classpath.txt",
             "es-query-service/target/classes/com/dylan/esquery/service/KnowledgeProfileVerifier.class",
             "es-query-service/target/classes/com/dylan/esquery/service/KnowledgeSearchService.class",
             "es-query-service/target/classes/application-knowledge-live.yml")
    result = {}
    for path in paths:
        with (REPO / path).open("rb") as stream:
            result[path] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


def check_index(support, binding):
    # Operational preflight only. Online Runtime never receives physical identities.
    with httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False, follow_redirects=False,
                      timeout=5, headers={"Accept-Encoding": "identity"}) as client:
        values = []
        for path in (f'/_alias/{binding["readAlias"]}', f'/{binding["expectedIndexName"]}/_settings',
                     f'/{binding["expectedIndexName"]}/_mapping'):
            status, raw = support.bounded_request(client, "GET", path)
            if status != 200:
                raise ValueError("probe_index_http_failed")
            values.append(json.loads(raw, object_pairs_hook=_unique, parse_constant=_reject_constant))
    name = binding["expectedIndexName"]
    settings = values[1][name]["settings"]["index"]
    block = settings.get("blocks", {}).get("write")
    if (values[0] != {name: {"aliases": {binding["readAlias"]: {}}}} or set(values[1]) != {name}
            or set(values[2]) != {name} or settings["uuid"] != binding["expectedIndexUuid"]
            or not (block is True or type(block) is str and block == "true")
            or values[2][name]["mappings"]["_meta"]["mapping_version"] != binding["mappingVersion"]):
        raise ValueError("probe_index_changed")


def clean_head(expected=None):
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True).strip():
        raise ValueError("probe_worktree_dirty")
    value = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    if expected is not None and value != expected:
        raise ValueError("probe_code_changed")
    return value


def local_models():
    result = {}
    for name in ("bge-m3-service", "bge-reranker-v2-m3-service"):
        raw = subprocess.check_output(["docker", "inspect", "--format", "{{.Id}} {{.Image}} {{.State.Running}}", name],
                                      text=True, timeout=10).split()
        if (len(raw) != 3 or raw[2] != "true" or len(raw[0]) != 64 or not raw[1].startswith("sha256:")
                or len(raw[1]) != 71 or any(c not in "0123456789abcdef" for c in raw[0] + raw[1][7:])):
            raise ValueError("probe_local_models_invalid")
        result[name] = {"containerId": raw[0], "imageId": raw[1]}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--result", required=True, type=Path)
    options = parser.parse_args()
    if not options.execute or sys.flags.optimize:
        parser.error("explicit execution and non-optimized Python required")
    with options.result.open("xb") as stream:
        emit = lambda value: emit_line(stream, value)
        budget = Budget()
        terminal = {"event": "terminal", "schemaVersion": 1, "status": "failed", "modelCalls": 0,
            "businessCalls": 0, "indexWrites": 0, "retry": 0, "resume": 0,
            "limitations": ["manual_plans_not_rewrite", "no_summary", "not_functional_or_effectiveness_uat"]}
        try:
            support = load_support()
            binding = json.loads(support.checked_bytes(REPO / "serviceCenter/knowledge-runtime-binding.v2.json", BINDING_SHA))
            plans = [asdict(plan_for(spec)[1]) for spec in SPECIFICATIONS]
            artifacts = artifact_hashes()
            models = local_models()
            for port in support.PORTS:
                with socket.socket() as listener:
                    listener.bind(("127.0.0.1", port))
            head = clean_head()
            emit({"event": "prepared", "head": head,
                "bindingSha256": BINDING_SHA, "catalogSha256": CATALOG_SHA, "helperSha256": HELPER_SHA,
                "scriptSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "artifactHashes": artifacts,
                "localModelContainers": models,
                "fixtureSha256": hashlib.sha256(json.dumps(plans, sort_keys=True).encode()).hexdigest(),
                "caseIds": [s[0] for s in SPECIFICATIONS], "budgets": LIMITS,
                "notExecuted": [c["caseId"] for c in CASES if c["reason"]]})
            check_index(support, binding)
            if artifact_hashes() != artifacts:
                raise ValueError("probe_artifacts_changed")
            clean_head(head)
            with support.isolated_services(binding, binding["readAlias"], terminal) as tokens:
                terminal.update(asyncio.run(diagnose(binding, tokens["admin"], emit, budget)))
            check_index(support, binding)
            if artifact_hashes() != artifacts:
                raise ValueError("probe_artifacts_changed")
            if not all(terminal.get(key) is True for key in ("ownedProcessesStopped", "rawLogsDeleted", "secretScanPassed")):
                raise ValueError("probe_cleanup_failed")
            clean_head(head)
            if local_models() != models:
                raise ValueError("probe_local_models_changed")
            terminal["status"] = "measured"
        except Exception as error:
            # Finite errors only: never serialize raw HTTP bodies, JWT or source text.
            terminal["failureKind"] = type(error).__name__ if type(error) in (ValueError, OSError, ImportError) else "execution_failed"
            allowed = {"probe_support_changed", "probe_fixture_unsafe", "probe_catalog_changed", "probe_index_changed",
                "probe_worktree_dirty", "probe_code_changed", "probe_artifacts_changed", "probe_payload_limit",
                "probe_cleanup_failed", "probe_retrieval_failed", "probe_index_http_failed", "probe_outbound_rejected",
                "probe_local_models_invalid", "probe_local_models_changed"}
            terminal["failureReason"] = str(error) if type(error) is ValueError and str(error) in allowed else "execution_failed"
        finally:
            terminal["counts"] = budget.total
            emit(terminal)
        print(json.dumps({k: v for k, v in terminal.items() if k != "ownedPids"}), flush=True)
        return 0 if terminal["status"] == "measured" else 1


if __name__ == "__main__":
    raise SystemExit(main())
