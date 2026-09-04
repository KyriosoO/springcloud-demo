"""Opt-in read-only Stage B diagnosis; never imported by the production object graph.

Uses real local authorized retrieval/BGE, no external model, no corpus writes.
Printed records contain only public fixture IDs, ranks, hashes and finite checks.
The fixture checks are diagnostic hypotheses, NOT gold or online ranking signals.
"""
from __future__ import annotations

import asyncio
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time
from typing import TextIO

import httpx

from agent_runtime.capability_api.contracts import CancellationSource, OpaqueUserToken
from agent_runtime.knowledge.contracts import (
    DomainCandidateCount, KnowledgeEvidenceInput, KnowledgeRetrievalContext,
    PathRef, RetrievalCoverage, RetrievalPath,
)
from agent_runtime.knowledge.evidence.builder import DeterministicEvidenceSelector, EvidenceIntegrityVerifier
from agent_runtime.knowledge.evidence.contracts import KnowledgeEvidenceLimits
from agent_runtime.knowledge.retrieval.bge_embedding import BgeM3EmbeddingAdapter
from agent_runtime.knowledge.retrieval.bge_rerank import BgeRerankAdapter
from agent_runtime.knowledge.retrieval.contracts import (
    AuthorizedKnowledgeCandidate, KnowledgePathRequest, PathCandidateSet, PathResultKind,
    RankedKnowledgeBatch, RankedKnowledgeCandidate,
)
from agent_runtime.knowledge.retrieval.es_adapter import EsKnowledgeSearchAdapter
from agent_runtime.knowledge.retrieval.fusion import ReciprocalRankFusion
from agent_runtime.knowledge.retrieval.http import (
    BoundedHttpRequest, BoundedHttpResponse, HttpxKnowledgeTransport, build_knowledge_http_client,
)


REPO = Path(__file__).resolve().parents[3]
# Fixed local diagnostic budget: 10 embeddings, 40 searches, 10 reranks, 0 LLM.
QUERIES = (
    ("hotel_original", "酒店行业的住宿费用，适用哪种税率？"),
    ("hotel_service", "住宿服务增值税税率"),
    ("hotel_classification", "住宿服务生活服务"),
    ("hotel_general", "一般纳税人提供住宿服务适用什么增值税税率？"),
    ("hotel_small", "小规模纳税人提供住宿服务适用什么征收率？"),
    ("hotel_law", "增值税法销售服务税率"),
    ("rent_boundary", "住宿服务与不动产租赁的增值税分类有什么区别？"),
    ("explicit_cross_domain", "住宿服务的政策分类和增值税法税率规定是什么？"),
    ("historical", "2016年一般纳税人提供住宿服务的增值税税率是多少？"),
    ("holdout", "软件产品增值税即征即退的适用条件是什么？"),
)
DOMAINS = (("tax.policy", "tax-policy-v1"), ("tax.law", "tax-law-v1"))
_evidence: TextIO | None = None


def emit(record: dict[str, object]) -> None:
    # Only already-projected finite records reach this append-only evidence stream.
    if _evidence is not None and not _evidence.closed:
        _evidence.write(json.dumps(record, ensure_ascii=True) + "\n")
        _evidence.flush()
    brief = {key: value for key, value in record.items() if key != "matches"}
    matches = record.get("matches")
    if isinstance(matches, list):
        brief["matchedCount"] = len(matches)
    print(json.dumps(brief, ensure_ascii=True), flush=True)


class NeverCancelled:
    def is_cancelled(self) -> bool:
        return False

    async def wait_cancelled(self) -> CancellationSource:
        return await asyncio.Future[CancellationSource]()


class OfflineTimingTransport:
    """Measure one local call beyond the production deadline; never a passing E2E."""
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def send(self, *, request: BoundedHttpRequest, timeout_s: float) -> BoundedHttpResponse:
        if request.relative_path != "/rerank":
            raise ValueError("probe.unexpected_path")
        started = time.monotonic()
        try:
            async with self.client.stream("POST", "/rerank", content=request.body,
                                          headers=dict(request.headers), timeout=45) as response:
                body = bytearray()
                async for chunk in response.aiter_raw():
                    body.extend(chunk)
                    if len(body) > request.max_response_bytes:
                        raise ValueError("probe.response_too_large")
                return BoundedHttpResponse(status_code=response.status_code,
                                           content_type=response.headers.get("content-type", "").split(";")[0],
                                           content_encoding=response.headers.get("content-encoding"), body=bytes(body))
        finally:
            elapsed = time.monotonic() - started
            emit({"stage": "offline_timing", "milliseconds": round(elapsed * 1000),
                  "productionDeadlineMet": elapsed <= timeout_s})


def checks(candidate: AuthorizedKnowledgeCandidate) -> list[str]:
    """Finite offline content-presence checks; no claim of legal applicability."""
    text = candidate.content
    result = []
    for label, phrase in (("lodging", "住宿服务"), ("living", "生活服务"),
                          ("rent", "不动产租赁"), ("general", "一般纳税人"),
                          ("small", "小规模纳税人"), ("software", "软件产品")):
        if phrase in text:
            result.append(label)
    if any(phrase in text for phrase in ("6%", "6％", "百分之六")):
        result.append("rate_six")
    if "提供住宿场所" in text:
        result.append("lodging_definition")
    return result


def finite(candidate: AuthorizedKnowledgeCandidate, rank: int) -> dict[str, object]:
    return {"rank": rank, "documentId": candidate.document_id, "chunkId": candidate.chunk_id,
            "contentSha256": candidate.content_sha256, "checks": checks(candidate)}


async def diagnose(token: str, *, paths_only: bool, calibration: bool) -> None:
    counts = {"search": 0, "embedding": 0, "rerank": 0, "model": 0}
    async with (
        build_knowledge_http_client("http://127.0.0.1:19201") as es_client,
        build_knowledge_http_client("http://127.0.0.1:8908") as embed_client,
        build_knowledge_http_client("http://127.0.0.1:8909") as rank_client,
    ):
        search = EsKnowledgeSearchAdapter(HttpxKnowledgeTransport(es_client))
        embedding = BgeM3EmbeddingAdapter(HttpxKnowledgeTransport(embed_client))
        rerank = BgeRerankAdapter(OfflineTimingTransport(rank_client) if calibration else HttpxKnowledgeTransport(rank_client))
        context = KnowledgeRetrievalContext(
            request_id="stage-b-probe", correlation_id="stage-b-probe", subject="admin",
            user_token=OpaqueUserToken.from_raw(token), deadline_monotonic=time.monotonic() + 600,
            cancellation=NeverCancelled(),
        )
        try:
            selected_queries = QUERIES[:1] if calibration else QUERIES
            for case_id, question in selected_queries:
                counts["embedding"] += 1
                vector = await embedding.embed(text=question, timeout_s=3)
                paths = []
                for domain, profile in DOMAINS:
                    for path in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR):
                        counts["search"] += 1
                        result = await search.search(
                            request=KnowledgePathRequest(
                                logical_domain_id=domain, retrieval_profile_id=profile, path=path,
                                query_text=question if path is RetrievalPath.KEYWORD else None,
                                query_vector=vector if path is RetrievalPath.VECTOR else None, candidate_limit=20,
                            ), context=context, timeout_s=5,
                        )
                        if result.kind not in (PathResultKind.CANDIDATES, PathResultKind.NO_RESULT):
                            emit({"caseId": case_id, "domain": domain, "path": path.value,
                                  "status": result.kind.value, "reason": result.failure.value if result.failure else None})
                            raise RuntimeError("probe.path_failed")
                        paths.append(PathCandidateSet(
                            logical_domain_id=domain, retrieval_profile_id=profile, path=path,
                            profile_version=result.profile_version or "tax-knowledge-search-v1",
                            index_snapshot_id=result.index_snapshot_id or "",
                            read_policy_version=result.read_policy_version or "",
                            truncated=result.truncated, candidates=result.candidates,
                        ))
                        emit({"caseId": case_id, "stage": "path", "domain": domain,
                              "path": path.value, "count": len(result.candidates), "truncated": result.truncated,
                              "matches": [finite(c, c.source_rank) for c in result.candidates if checks(c)]})
                if paths_only:
                    continue
                fused = ReciprocalRankFusion().fuse(tuple(paths))
                if not fused:
                    continue
                counts["rerank"] += 1
                scores = await rerank.rerank(query=question, candidates=tuple(c.candidate for c in fused), timeout_s=5)
                by_index = {score.candidate_index: score.score for score in scores}
                ordered = sorted(enumerate(fused), key=lambda pair: (
                    -by_index[pair[0]], -pair[1].rrf_score, pair[1].candidate.chunk_id))
                ranked = tuple(RankedKnowledgeCandidate(
                    candidate=item.candidate, domain_ids=item.domain_ids, rerank_score=by_index[index], rank=rank,
                ) for rank, (index, item) in enumerate(ordered[:20], 1))
                coverage = RetrievalCoverage(
                    successful_paths=tuple(PathRef(logical_domain_id=p.logical_domain_id, path=p.path)
                                           for p in paths if p.candidates),
                    no_result_paths=tuple(PathRef(logical_domain_id=p.logical_domain_id, path=p.path)
                                          for p in paths if not p.candidates), failed_paths=(),
                    candidate_count_by_domain=tuple(DomainCandidateCount(
                        logical_domain_id=d, count=sum(d in c.domain_ids for c in ranked)) for d, _ in DOMAINS),
                    complete=True,
                )
                evidence_input = KnowledgeEvidenceInput(
                    original_question=question, selected_query=question,
                    selected_domain_ids=tuple(d for d, _ in DOMAINS), coverage=coverage,
                    question_policy_version="probe", question_egress_denied=False,
                    batch=RankedKnowledgeBatch(candidates=ranked, profile_version="tax-knowledge-search-v1",
                                              index_snapshot_ids=tuple(dict.fromkeys(c.candidate.index_snapshot_id for c in ranked))),
                )
                verified = EvidenceIntegrityVerifier().verify(input=evidence_input)
                selection = DeterministicEvidenceSelector().select(
                    candidates=verified, input=evidence_input, minimized_question=question, limits=KnowledgeEvidenceLimits.v1())
                selected = {e.chunk_id for e in selection.bundle.evidence} if selection.bundle else set()
                emit({"caseId": case_id, "stage": "fusion_rerank_evidence", "fusedCount": len(fused),
                      "matches": [dict(finite(item.candidate, rank), fusionRank=index + 1,
                                       evidenceSelected=item.candidate.chunk_id in selected)
                                  for rank, (index, item) in enumerate(ordered, 1) if checks(item.candidate)],
                      "evidenceCount": len(selected)})
        finally:
            emit({"stage": "counts", **counts})


def main() -> None:
    global _evidence
    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument("--paths-only", action="store_true", help="diagnose retrieval without repeating a failed rerank")
    arguments.add_argument("--rerank-calibration", action="store_true", help="one offline local timing probe, 45 second ceiling, NOT production success")
    arguments.add_argument("--output", type=Path, help="new append-only finite JSONL, existing files refused")
    options = arguments.parse_args()
    if options.paths_only and options.rerank_calibration:
        raise ValueError("probe.conflicting_modes")
    for port in (18090, 19201):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", port))
    binding = json.loads((REPO / "serviceCenter/knowledge-runtime-binding.v1.json").read_text(encoding="utf-8-sig"))
    secret = base64.b64encode(secrets.token_bytes(48)).decode()
    # No environment enumeration or API-key access. Children inherit their normal local configuration.
    updates = {"COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE": secret}
    for env_name, key in (("READ_ALIAS", "readAlias"), ("EXPECTED_INDEX_NAME", "expectedIndexName"),
                          ("EXPECTED_INDEX_UUID", "expectedIndexUuid"), ("MAPPING_VERSION", "mappingVersion"),
                          ("POLICY_SNAPSHOT_ID", "policySnapshotId"), ("LAW_SNAPSHOT_ID", "lawSnapshotId")):
        updates["AGENT_KNOWLEDGE_" + env_name] = binding[key]
    previous = {key: os.environ.get(key) for key in updates}
    if options.output is not None:
        _evidence = options.output.open("x", encoding="utf-8", newline="\n")
    os.environ.update(updates)
    processes: list[subprocess.Popen[bytes]] = []
    streams = []
    token = ""
    try:
        with tempfile.TemporaryDirectory(prefix="codex-kstage-b-probe-") as directory:
            run_root = Path(directory)
            try:
                common = ["--spring.cloud.config.enabled=false",
                          "--spring.config.additional-location=optional:file:D:/codex/config-service/src/main/resources/config/",
                          "--eureka.client.enabled=false", "--common.security.secrets.source-order[0]=environment",
                          "--common.security.secrets.allow-config-values=false", "--common.security.secrets.fail-fast=true",
                          "--common.security.secrets.jwt.active-key-id=ACTIVE",
                          "--common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE",
                          "--common.security.secrets.jwt.keys.ACTIVE.value="]
                for module, port, extra in (
                    ("auth-service", 18090, []),
                    ("es-query-service", 19201, ["--spring.profiles.active=datasource,es,knowledge-live",
                                               "--spring.elasticsearch.uris=http://127.0.0.1:9200",
                                               "--es.query.total-hits-threshold=10000",
                                               "--es.query.rebuild-source-allowed-hosts[0]=localhost",
                                               "--es.query.rebuild-max-batch-size=500"]),
                ):
                    jar = REPO / module / "target" / f"{module}-0.0.1-SNAPSHOT.jar"
                    stream = (run_root / f"{module}.log").open("xb")
                    streams.append(stream)
                    processes.append(subprocess.Popen(
                        ["java", "-jar", str(jar), f"--server.port={port}", *extra, *common],
                        cwd=REPO / module, stdout=stream, stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    ))
                with httpx.Client(trust_env=False, follow_redirects=False, timeout=3) as client:
                    for process, url in zip(processes, ("http://127.0.0.1:18090/public/test", "http://127.0.0.1:19201/actuator/health"), strict=True):
                        deadline = time.monotonic() + 90
                        while time.monotonic() < deadline:
                            if process.poll() is not None:
                                raise RuntimeError("probe.service_exited")
                            try:
                                if client.get(url).status_code == 200:
                                    break
                            except httpx.HTTPError:
                                pass
                            time.sleep(0.5)
                        else:
                            raise RuntimeError("probe.readiness_timeout")
                    alias = client.get(f"http://127.0.0.1:9200/_alias/{binding['readAlias']}")
                    alias.raise_for_status()
                    if list(alias.json()) != [binding["expectedIndexName"]]:
                        raise RuntimeError("probe.index_binding_changed")
                    response = client.post("http://127.0.0.1:18090/login", json={"userId": "admin", "password": "123456"})
                    response.raise_for_status()
                    token = client.cookies.get("AUTH_TOKEN") or ""
                    if not token:
                        raise RuntimeError("probe.auth_token_missing")
                emit({"stage": "ready", "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
                      "probeSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      "indexUuid": binding["expectedIndexUuid"], "budgets": {"embedding": 1 if options.rerank_calibration else 10, "search": 4 if options.rerank_calibration else 40, "rerank": 0 if options.paths_only else (1 if options.rerank_calibration else 10), "model": 0}})
                asyncio.run(diagnose(token, paths_only=options.paths_only, calibration=options.rerank_calibration))
            finally:
                for process in reversed(processes):
                    # Popen owns these exact process handles; never stop by port or process name.
                    if process.poll() is None:
                        process.terminate()
                    process.wait(timeout=20)
                for stream in streams:
                    stream.close()
                leaked = False
                for log in run_root.glob("*.log"):
                    raw = log.read_bytes()
                    leaked |= secret.encode() in raw or bool(token and token.encode() in raw)
                    if log.resolve().parent != run_root.resolve():
                        raise RuntimeError("probe.cleanup_path_invalid")
                    log.unlink()
                emit({"stage": "cleanup", "ownedProcessesStopped": all(p.poll() is not None for p in processes),
                      "rawLogsDeleted": True, "secretScanPassed": not leaked})
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if _evidence is not None:
            _evidence.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Never print exception details containing HTTP bodies, tokens or local connection settings.
        print(json.dumps({"status": "failed", "exceptionType": type(error).__name__}), flush=True)
        raise SystemExit(1) from None
