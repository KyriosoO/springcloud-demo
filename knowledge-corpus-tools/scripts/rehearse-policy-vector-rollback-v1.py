"""DR-KRET-025/032: candidate -> source -> candidate, isolated alias only."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import types

REPO = Path(__file__).resolve().parents[2]
HELPER = REPO / "knowledge-corpus-tools/scripts/validate-policy-vector-typed-v1.py"
HELPER_SHA = "54ec6f9a95f187c48a5dcd512373fea185358a2cef477e2fd118f11a413c191d"
ALIAS_SHA = "b15c8bda5d935b675eec41269ee9613ac603133be66754d8d84258df5b313ad2"
BUDGET = {"typedCalls": 24, "embeddingCalls": 6}


def load_support():
    raw = HELPER.read_bytes()
    if hashlib.sha256(raw).hexdigest() != HELPER_SHA:
        raise ValueError("support_hash_changed")
    module = types.ModuleType("policy_vector_typed_support_v1")
    module.__file__ = str(HELPER)
    # Execute the exact hashed source, not a second read susceptible to drift.
    exec(compile(raw, str(HELPER), "exec"), module.__dict__)
    module.checked_bytes(REPO / "knowledge-corpus-tools/src/knowledge_corpus_tools/validation_alias.py", ALIAS_SHA)
    return module


def take(result, counter):
    if type(result[counter]) is not int or not 0 <= result[counter] < BUDGET[counter]:
        raise ValueError("rehearsal_budget_exceeded")
    result[counter] += 1


async def check_phase(support, binding, catalog_raw, tokens, total, phase):
    from agent_runtime.knowledge.evidence.catalog import KnowledgeEgressPolicyCatalog, _parse_snapshot
    from agent_runtime.knowledge.retrieval.http import build_knowledge_http_client, HttpxKnowledgeTransport
    from agent_runtime.knowledge.retrieval.es_adapter import EsKnowledgeSearchAdapter
    from agent_runtime.knowledge.retrieval.bge_embedding import BgeM3EmbeddingAdapter
    from agent_runtime.knowledge.retrieval.contracts import KnowledgePathRequest, PathResultKind
    from agent_runtime.knowledge.contracts import KnowledgeRetrievalContext, RetrievalPath
    from agent_runtime.capability_api.contracts import OpaqueUserToken
    from agent_runtime.api.cancellation import MutableCancellationSignal

    catalog = KnowledgeEgressPolicyCatalog(_parse_snapshot(catalog_raw, source_sha256=support.CATALOG_SHA))
    async with build_knowledge_http_client("http://127.0.0.1:19201") as client, \
            build_knowledge_http_client("http://127.0.0.1:8908") as embedding_client:
        adapter = EsKnowledgeSearchAdapter(HttpxKnowledgeTransport(client))
        for domain, profile, question, snapshot_key in (
            ("tax.policy", "tax-policy-v1", "住宿服务 生活服务", "policySnapshotId"),
            ("tax.law", "tax-law-v1", "增值税法", "lawSnapshotId"),
        ):
            take(total, "embeddingCalls")
            vector = await BgeM3EmbeddingAdapter(HttpxKnowledgeTransport(embedding_client)).embed(text=question, timeout_s=5)
            for path in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR):
                request = KnowledgePathRequest(logical_domain_id=domain, retrieval_profile_id=profile, path=path,
                    query_text=question if path is RetrievalPath.KEYWORD else None,
                    query_vector=vector if path is RetrievalPath.VECTOR else None, candidate_limit=20)
                context = KnowledgeRetrievalContext(request_id="rollback-rehearsal", correlation_id="rollback-rehearsal",
                    subject="isolated-validation", user_token=OpaqueUserToken.from_raw(tokens["admin"]),
                    deadline_monotonic=time.monotonic() + 10, cancellation=MutableCancellationSignal())
                take(total, "typedCalls")
                answer = await adapter.search(request=request, context=context, timeout_s=5)
                if answer.kind is not PathResultKind.CANDIDATES or answer.index_snapshot_id != binding[snapshot_key]:
                    raise ValueError("typed_result_invalid")
                verified, selected = support.evidence_check(answer.candidates, path, domain, binding[snapshot_key], catalog)
                phase["checks"].append({"domain": domain, "path": path.value, "role": "admin", "status": "passed",
                    "snapshotId": answer.index_snapshot_id, "verifiedCandidates": verified, "selectedEvidence": selected})
            for role, expected in (("unknown", 403), ("missing", 401)):
                headers = {"Content-Type": "application/json", "Accept-Encoding": "identity"}
                if tokens[role]:
                    headers["Authorization"] = "Bearer " + tokens[role]
                take(total, "typedCalls")
                async with client.stream("POST", "/es/knowledge/search", headers=headers, timeout=5, json={
                    "schemaVersion": 1, "logicalDomainId": domain, "retrievalProfileId": profile,
                    "path": "keyword", "queryText": question, "queryVector": None, "limit": 20,
                }) as response:
                    body = bytearray()
                    async for part in response.aiter_raw():
                        body.extend(part)
                        if len(body) > 2 * 1024 * 1024:
                            raise ValueError("response_size_invalid")
                    if (response.status_code != expected
                            or response.headers.get("content-encoding", "identity") != "identity"
                            or any(marker in body for marker in (b'"content"', b'"candidates"'))):
                        raise ValueError("authorization_denial_invalid")
                phase["checks"].append({"domain": domain, "path": "keyword", "role": role,
                    "status": "passed", "httpStatus": expected, "bodyReturned": False})


def emit(stream, event):
    payload = (json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    if len(payload) > 65536:
        raise ValueError("rehearsal_result_limit")
    stream.write(payload)
    stream.flush()
    os.fsync(stream.fileno())


def artifact_hashes():
    paths = [REPO / "auth-service/target/auth-service-0.0.1-SNAPSHOT.jar",
             REPO / "es-query-service/target/stage-b-classpath.txt",
             REPO / "es-query-service/target/classes/com/dylan/esquery/service/KnowledgeProfileVerifier.class",
             REPO / "es-query-service/target/classes/com/dylan/esquery/service/KnowledgeSearchService.class",
             REPO / "es-query-service/target/classes/application-knowledge-live.yml"]
    result = {}
    for path in paths:
        with path.open("rb") as stream:
            result[path.relative_to(REPO).as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


def rehearse(support, stream, total):
    candidate, source, catalog = support.preflight()
    artifacts = artifact_hashes()
    lease = support.ValidationAlias(source=support.IndexIdentity(source["expectedIndexName"], source["expectedIndexUuid"]),
        candidate=support.IndexIdentity(candidate["expectedIndexName"], candidate["expectedIndexUuid"]),
        published_alias=source["readAlias"])
    total["temporaryAlias"] = lease.name
    try:
        emit(stream, {"event": "prepared", "schemaVersion": 1, "temporaryAlias": lease.name,
            "sourceIndex": source["expectedIndexName"], "sourceUuid": source["expectedIndexUuid"],
            "candidateIndex": candidate["expectedIndexName"], "candidateUuid": candidate["expectedIndexUuid"],
            "bindingSha256": support.BINDING_SHA, "catalogSha256": support.CATALOG_SHA,
            "helperSha256": HELPER_SHA, "aliasSha256": ALIAS_SHA, "artifactHashes": artifacts,
            "launcherSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
            "budgets": {**BUDGET, "esManagementReads": 40, "validationAliasWrites": 4, "modelCalls": 0}})
        with lease as alias:
            for label, binding, target in (("candidate_initial", candidate, lease.candidate),
                                            ("source_rollback", source, lease.source),
                                            ("candidate_return", candidate, lease.candidate)):
                if label != "candidate_initial":
                    lease.move(target)
                phase = {"event": "phase", "phase": label, "status": "failed", "checks": []}
                try:
                    with support.isolated_services(binding, alias, phase) as tokens:
                        asyncio.run(check_phase(support, binding, catalog, tokens, total, phase))
                    if not all(phase.get(key) is True for key in ("profileVerifierStartupPassed",
                            "ownedProcessesStopped", "rawLogsDeleted", "secretScanPassed")):
                        raise ValueError("service_cleanup_failed")
                    phase["status"] = "passed"
                    total["phasesPassed"] += 1
                finally:
                    emit(stream, phase)
        support.checked_bytes(REPO / "serviceCenter/knowledge-runtime-binding.v1.json", support.ONLINE_SHA)
        if artifact_hashes() != artifacts:
            raise ValueError("artifact_hash_changed")
        total.update(status="passed", validationAliasRemoved=True, onlineBindingUnchanged=True)
    finally:
        try:
            lease.close()
        finally:
            total.update(esManagementReads=lease.reads, validationAliasWrites=lease.writes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    if not args.execute or sys.flags.optimize:
        parser.error("explicit --execute and non-optimized Python required")
    # One append-only file carries preparation, three phase checkpoints and the terminal.
    with args.result.open("xb") as stream:
        total = {"event": "terminal", "schemaVersion": 1, "status": "failed", "phasesPassed": 0,
            "typedCalls": 0, "embeddingCalls": 0, "modelCalls": 0, "businessCalls": 0,
            "rerankCalls": 0, "retry": 0, "resume": 0, "onlineAliasWrites": 0,
            "limitations": ["not_online_publication", "not_quality_v3_e2e", "not_real_summary"]}
        support = None
        try:
            support = load_support()
            rehearse(support, stream, total)
        except Exception as exc:
            allowed = {"support_hash_changed", "rehearsal_budget_exceeded", "rehearsal_result_limit"}
            if support is not None:
                allowed.update(support.SAFE_REASONS)
            total["reason"] = str(exc) if type(exc) is ValueError and str(exc) in allowed else "rehearsal_execution_failed"
        finally:
            emit(stream, total)
            print(json.dumps({key: total[key] for key in ("status", "phasesPassed", "typedCalls", "embeddingCalls", "modelCalls")}))
    return 0 if total["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
