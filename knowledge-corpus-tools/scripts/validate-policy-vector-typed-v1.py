"""One-shot, no-LLM candidate typed verification; never publishes the online alias."""
from __future__ import annotations

import argparse
import asyncio
import base64
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time

import httpx

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "knowledge-corpus-tools/src"))
sys.path.insert(0, str(REPO / "agent-runtime/src"))
from knowledge_corpus_tools.validation_alias import IndexIdentity, ValidationAlias

PENDING = Path("D:/codex-data/knowledge-policy-vector/publication-preparation-20260907-b2")
BINDING_SHA = "a6d2c00eddf46827750a8100357c909bab944f27d10b41218e2c9754457f9682"
CATALOG_SHA = "87c3963a15ea98cca444438c3439094b6881bba31ceaef265db92f5caab21b00"
ONLINE_SHA = "f71cd90680cddd4b167b0a9a242e7f2b730dce78d15804e6a6aa6bdd81b22a9a"
PORTS = (18090, 19201)
SAFE_REASONS = frozenset({
    "java_home_invalid",
    "artifact_size_invalid", "artifact_hash_changed", "service_artifact_missing", "service_exited", "readiness_timeout",
    "auth_token_missing", "cleanup_path_invalid", "service_cleanup_failed", "response_encoding_invalid",
    "response_size_invalid", "typed_budget_exceeded", "typed_result_invalid", "authorization_denial_invalid",
    "evidence_selection_failed", "egress_binding_failed", "unknown_snapshot_accepted", "citation_validation_failed",
    "duplicate_citation_accepted", "validation_binding_invalid", "validation_index_changed",
    "validation_published_alias_changed", "validation_alias_exists", "validation_alias_owner_changed",
    "validation_alias_confirmation_failed", "validation_cleanup_failed", "validation_transport_failed",
    "validation_response_invalid", "validation_response_limit", "validation_read_budget", "validation_write_budget",
})


def java_executable():
    location = os.environ.get("JAVA_HOME")
    if not location:
        raise ValueError("java_home_invalid")
    root = Path(location).resolve()
    executable = root / "bin/java.exe"
    release = root / "release"
    if not executable.is_file() or not release.is_file():
        raise ValueError("java_home_invalid")
    match = re.search(r'^JAVA_VERSION="([0-9]+)\.', release.read_text(), re.MULTILINE)
    if match is None or int(match[1]) != 25:
        raise ValueError("java_home_invalid")
    return str(executable)


def checked_bytes(path, expected, maximum=4 * 1024 * 1024):
    if path.stat().st_size > maximum:
        raise ValueError("artifact_size_invalid")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("artifact_hash_changed")
    return raw


def preflight():
    binding = json.loads(checked_bytes(PENDING / "runtime-binding.pending.json", BINDING_SHA))
    online = json.loads(checked_bytes(REPO / "serviceCenter/knowledge-runtime-binding.v1.json", ONLINE_SHA))
    catalog = checked_bytes(PENDING / "egress-policy-catalog-v3.json", CATALOG_SHA)
    for port in PORTS:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", port))
    for path in (REPO / "auth-service/target/auth-service-0.0.1-SNAPSHOT.jar",
                 REPO / "es-query-service/target/stage-b-classpath.txt",
                 REPO / "es-query-service/target/classes/com/dylan/esquery/service/KnowledgeProfileVerifier.class"):
        if not path.is_file():
            raise ValueError("service_artifact_missing")
    java_executable()
    return binding, online, catalog


def sign_token(secret, role, kind="user"):
    def encoded(value):
        return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).rstrip(b"=")
    now = int(time.time())
    value = encoded({"alg": "HS256", "kid": "ACTIVE"}) + b"." + encoded({
        "sub": "isolated-validation", "iat": now, "exp": now + 600,
        "token_type": kind, "role": [role],
    })
    return (value + b"." + base64.urlsafe_b64encode(hmac.new(base64.b64decode(secret), value,
                                                         hashlib.sha256).digest()).rstrip(b"=")).decode()


def bounded_request(client, method, url, **kwargs):
    with client.stream(method, url, **kwargs) as response:
        if response.headers.get("content-encoding", "identity") != "identity":
            raise ValueError("response_encoding_invalid")
        body = bytearray()
        for chunk in response.iter_raw():
            body.extend(chunk)
            if len(body) > 2 * 1024 * 1024:
                raise ValueError("response_size_invalid")
        return response.status_code, bytes(body)


def stop_owned(processes):
    for process in reversed(processes):
        try:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass  # All owned PIDs are attempted; aggregate failure is fatal below.
    return all(process.poll() is not None for process in processes)


def scan_log(path, root, protected):
    if path.resolve().parent != root.resolve():
        raise ValueError("cleanup_path_invalid")
    leaked, markers, tail = False, set(), b""
    with path.open("rb") as stream:
        while chunk := stream.read(65536):
            raw = tail + chunk
            leaked |= any(value.encode() in raw for value in protected if value)
            markers.update(marker for marker in ("APPLICATION FAILED TO START", "knowledge.profile",
                                                 "Could not resolve placeholder") if marker.encode() in raw)
            tail = raw[-16384:]
    path.unlink()
    return leaked, markers


@contextmanager
def isolated_services(binding, alias, result):
    secret = base64.b64encode(secrets.token_bytes(48)).decode()
    tokens = {}
    env = {key: os.environ[key] for key in ("SystemRoot", "SystemDrive", "PATH", "JAVA_HOME", "TEMP", "TMP",
                                          "USERPROFILE", "APPDATA", "LOCALAPPDATA") if key in os.environ}
    env["COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE"] = secret
    for name, key in (("READ_ALIAS", "readAlias"), ("EXPECTED_INDEX_NAME", "expectedIndexName"),
                      ("EXPECTED_INDEX_UUID", "expectedIndexUuid"), ("MAPPING_VERSION", "mappingVersion"),
                      ("POLICY_SNAPSHOT_ID", "policySnapshotId"), ("LAW_SNAPSHOT_ID", "lawSnapshotId")):
        env["AGENT_KNOWLEDGE_" + name] = alias if key == "readAlias" else binding[key]
    common = ["--server.address=127.0.0.1", "--spring.cloud.config.enabled=false",
              "--spring.config.additional-location=optional:file:D:/codex/config-service/src/main/resources/config/",
              "--eureka.client.enabled=false", "--common.security.secrets.source-order[0]=environment",
              "--common.security.secrets.allow-config-values=false", "--common.security.secrets.fail-fast=true",
              "--common.security.secrets.jwt.active-key-id=ACTIVE",
              "--common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE",
              "--common.security.secrets.jwt.keys.ACTIVE.value="]
    classpath = (REPO / "es-query-service/target/stage-b-classpath.txt").read_text().strip()
    launches = [
        ("auth-service", 18090, ["-jar", str(REPO / "auth-service/target/auth-service-0.0.1-SNAPSHOT.jar")], []),
        ("es-query-service", 19201, ["-cp", str(REPO / "es-query-service/target/classes") + os.pathsep + classpath,
                                   "com.dylan.esquery.EsQueryServiceApplication"],
         ["--spring.profiles.active=datasource,es,knowledge-live", "--spring.elasticsearch.uris=http://127.0.0.1:9200",
          "--es.query.total-hits-threshold=10000", "--es.query.rebuild-source-allowed-hosts[0]=localhost",
          "--es.query.rebuild-max-batch-size=500"]),
    ]
    processes, streams = [], []
    with tempfile.TemporaryDirectory(prefix="codex-policy-typed-") as directory:
        root = Path(directory).resolve()
        try:
            for module, port, command, extra in launches:
                stream = (root / f"{module}.log").open("xb")
                streams.append(stream)
                processes.append(subprocess.Popen([java_executable(), *command, f"--server.port={port}", *common, *extra],
                    cwd=REPO / module, env=env, stdout=stream, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW))
            result["ownedPids"] = [process.pid for process in processes]
            with httpx.Client(trust_env=False, follow_redirects=False, timeout=3,
                              headers={"Accept-Encoding": "identity"}) as client:
                for process, url in zip(processes, ("http://127.0.0.1:18090/public/test",
                                                    "http://127.0.0.1:19201/actuator/health"), strict=True):
                    for _ in range(100):
                        if process.poll() is not None:
                            raise ValueError("service_exited")
                        try:
                            if bounded_request(client, "GET", url)[0] == 200:
                                break
                        except httpx.HTTPError:
                            pass
                        time.sleep(0.5)
                    else:
                        raise ValueError("readiness_timeout")
                status, _ = bounded_request(client, "POST", "http://127.0.0.1:18090/login",
                                            json={"userId": "admin", "password": "123456"})
                tokens["admin"] = client.cookies.get("AUTH_TOKEN") or ""
                if status != 200 or not tokens["admin"]:
                    raise ValueError("auth_token_missing")
            tokens.update(viewer=sign_token(secret, "VIEWER"), unknown=sign_token(secret, "UNKNOWN"),
                          service=sign_token(secret, "ADMIN", "service"), malformed="not-a-jwt", missing="")
            result["profileVerifierStartupPassed"] = True
            yield tokens
        finally:
            stopped = stop_owned(processes)
            for stream in streams:
                stream.close()
            leaked = False
            markers = set()
            for log in root.glob("*.log"):
                leak, found = scan_log(log, root, (secret, *tokens.values()))
                leaked |= leak
                markers.update(found)
            result.update(ownedProcessesStopped=stopped, rawLogsDeleted=True, secretScanPassed=not leaked,
                          startupMarkers=sorted(markers))
            if leaked or not stopped:
                raise ValueError("service_cleanup_failed")


def evidence_check(candidates, path, domain, snapshot, catalog):
    # This verifies boundary compatibility, not quality-v3 ranking or a model answer.
    from agent_runtime.knowledge.contracts import (KnowledgeEvidenceInput, RetrievalCoverage, PathRef,
                                                 DomainCandidateCount)
    from agent_runtime.knowledge.retrieval.contracts import RankedKnowledgeBatch, RankedKnowledgeCandidate
    from agent_runtime.knowledge.evidence.builder import EvidenceIntegrityVerifier, DeterministicEvidenceSelector
    from agent_runtime.knowledge.evidence.contracts import KnowledgeEvidenceLimits, KnowledgeSummaryOutput, KnowledgeSummaryPoint, SummaryOutcome
    from agent_runtime.knowledge.evidence.policy import KnowledgeEvidenceEgressDecider
    from agent_runtime.knowledge.evidence.summary_validation import ExtractiveSummaryValidator, InvalidSummary
    from dataclasses import replace
    batch = RankedKnowledgeBatch(candidates=tuple(RankedKnowledgeCandidate(candidate=c, domain_ids=(domain,),
        rerank_score=0.0, rank=n) for n, c in enumerate(candidates, 1)),
        profile_version="tax-knowledge-search-v1", index_snapshot_ids=(snapshot,))
    value = KnowledgeEvidenceInput(original_question="公开知识检索验证", selected_query="公开知识检索验证",
        selected_domain_ids=(domain,), question_policy_version="knowledge-question-egress-v1", question_egress_denied=False,
        batch=batch, coverage=RetrievalCoverage(successful_paths=(PathRef(logical_domain_id=domain, path=path),),
            no_result_paths=(), failed_paths=(), candidate_count_by_domain=(DomainCandidateCount(logical_domain_id=domain,
                count=len(candidates)),), complete=False))
    verified = EvidenceIntegrityVerifier().verify(input=value)
    selected = DeterministicEvidenceSelector().select(candidates=verified, input=value,
        minimized_question="公开知识检索验证", limits=KnowledgeEvidenceLimits.v1())
    if not selected.sufficient or selected.bundle is None:
        raise ValueError("evidence_selection_failed")
    bundle = selected.bundle
    if not KnowledgeEvidenceEgressDecider().decide(bundle=bundle, catalog=catalog).allowed:
        raise ValueError("egress_binding_failed")
    bad = replace(bundle, evidence=(replace(bundle.evidence[0], index_snapshot_id="0" * 64),))
    if KnowledgeEvidenceEgressDecider().decide(bundle=bad, catalog=catalog).allowed:
        raise ValueError("unknown_snapshot_accepted")
    quote = next((part[:100] for part in re.split(r"[\x00-\x1f\x7f]", bundle.evidence[0].content) if part), "")
    output = KnowledgeSummaryOutput(outcome=SummaryOutcome.ANSWER, points=(KnowledgeSummaryPoint(evidence_ref="e1", quote=quote),))
    checked = ExtractiveSummaryValidator().validate(output=output, bundle=bundle, limits=KnowledgeEvidenceLimits.v1())
    if checked.insufficient or checked.domain_result is None:
        raise ValueError("citation_validation_failed")
    try:
        ExtractiveSummaryValidator().validate(output=replace(output, points=output.points * 2), bundle=bundle,
                                              limits=KnowledgeEvidenceLimits.v1())
    except InvalidSummary:
        return len(verified), len(bundle.evidence)
    raise ValueError("duplicate_citation_accepted")


async def typed_checks(binding, catalog_raw, tokens, result):
    from agent_runtime.knowledge.evidence.catalog import KnowledgeEgressPolicyCatalog, _parse_snapshot
    from agent_runtime.knowledge.retrieval.http import build_knowledge_http_client, HttpxKnowledgeTransport
    from agent_runtime.knowledge.retrieval.es_adapter import EsKnowledgeSearchAdapter
    from agent_runtime.knowledge.retrieval.contracts import KnowledgePathRequest, PathResultKind
    from agent_runtime.knowledge.contracts import KnowledgeRetrievalContext, RetrievalPath
    from agent_runtime.capability_api.contracts import OpaqueUserToken
    from agent_runtime.api.cancellation import MutableCancellationSignal
    catalog = KnowledgeEgressPolicyCatalog(_parse_snapshot(catalog_raw, source_sha256=CATALOG_SHA))
    async with build_knowledge_http_client("http://127.0.0.1:19201") as client, \
            build_knowledge_http_client("http://127.0.0.1:8908") as embedding_client:
        transport = HttpxKnowledgeTransport(client)
        adapter = EsKnowledgeSearchAdapter(transport)
        for domain, query, key in (("tax.policy", "住宿服务 生活服务", "policySnapshotId"),
                                   ("tax.law", "增值税法", "lawSnapshotId")):
            from agent_runtime.knowledge.retrieval.bge_embedding import BgeM3EmbeddingAdapter
            result["embeddingCalls"] += 1
            vector = await BgeM3EmbeddingAdapter(HttpxKnowledgeTransport(embedding_client)).embed(text=query, timeout_s=5)
            for role in ("admin", "viewer"):
                for path in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR):
                    if result["typedCalls"] >= 24:
                        raise ValueError("typed_budget_exceeded")
                    request = KnowledgePathRequest(logical_domain_id=domain,
                        retrieval_profile_id="tax-policy-v1" if domain == "tax.policy" else "tax-law-v1",
                        path=path, query_text=query if path is RetrievalPath.KEYWORD else None,
                        query_vector=vector if path is RetrievalPath.VECTOR else None, candidate_limit=20)
                    context = KnowledgeRetrievalContext(request_id="isolated-typed", correlation_id="isolated-typed",
                        subject="isolated-validation", user_token=OpaqueUserToken.from_raw(tokens[role]),
                        deadline_monotonic=time.monotonic() + 10, cancellation=MutableCancellationSignal())
                    result["typedCalls"] += 1
                    result["activeCase"] = {"domain": domain, "role": role, "path": path.value}
                    answer = await adapter.search(request=request, context=context, timeout_s=5)
                    if answer.kind is not PathResultKind.CANDIDATES or answer.index_snapshot_id != binding[key]:
                        raise ValueError("typed_result_invalid")
                    counts = evidence_check(answer.candidates, path, domain, binding[key], catalog)
                    result["checks"].append({"domain": domain, "role": role, "path": path.value,
                        "status": "passed", "verifiedCandidates": counts[0], "selectedEvidence": counts[1]})
            for role, expected in (("unknown", 403), ("service", 401), ("malformed", 401), ("missing", 401)):
                body = json.dumps({"schemaVersion": 1, "logicalDomainId": domain,
                    "retrievalProfileId": "tax-policy-v1" if domain == "tax.policy" else "tax-law-v1",
                    "path": "keyword", "queryText": query, "queryVector": None, "limit": 20}).encode()
                headers = (("Content-Type", "application/json"), ("Accept-Encoding", "identity"))
                if tokens[role]:
                    headers += (("Authorization", "Bearer " + tokens[role]),)
                result["typedCalls"] += 1
                result["activeCase"] = {"domain": domain, "role": role, "path": "keyword"}
                # The production transport intentionally rejects missing credentials locally.
                # Send negative security cases directly to the real Java boundary, never relax it.
                async with client.stream("POST", "/es/knowledge/search", headers=headers, content=body, timeout=5) as denied:
                    denied_body = bytearray()
                    async for chunk in denied.aiter_raw():
                        denied_body.extend(chunk)
                        if len(denied_body) > 2 * 1024 * 1024:
                            raise ValueError("response_size_invalid")
                    if (denied.status_code != expected
                            or denied.headers.get("content-encoding", "identity") != "identity"
                            or any(marker in denied_body for marker in (b'"candidates"', b'"content"'))):
                        raise ValueError("authorization_denial_invalid")
                result["checks"].append({"domain": domain, "role": role, "path": "keyword", "status": "passed",
                                         "httpStatus": denied.status_code, "bodyReturned": False})
    result.pop("activeCase", None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    if not args.execute:
        parser.error("explicit --execute required")
    # Exclusive reservation prevents accidental replay and retains a marker after a hard crash.
    with args.result.open("x", encoding="utf-8") as output:
        result = {"schemaVersion": 1, "status": "failed", "kind": "isolated_typed_compatibility",
                  "modelCalls": 0, "businessCalls": 0, "rerankCalls": 0, "retry": 0, "resume": 0,
                  "typedCalls": 0, "embeddingCalls": 0, "checks": [], "onlineAliasWrites": 0,
                  "bindingSha256": BINDING_SHA, "catalogSha256": CATALOG_SHA,
                  "limitations": ["not_online_publication", "not_quality_v3_e2e", "not_real_summary", "rollback_not_rehearsed"]}
        lease = None
        try:
            binding, online, catalog = preflight()
            result["head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
            result["launcherSha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            result["javaMajor"] = 25
            result["artifactHashes"] = {str(path.relative_to(REPO)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (REPO / "knowledge-corpus-tools/src/knowledge_corpus_tools/validation_alias.py",
                             REPO / "auth-service/target/auth-service-0.0.1-SNAPSHOT.jar",
                             REPO / "es-query-service/target/classes/com/dylan/esquery/service/KnowledgeProfileVerifier.class",
                             REPO / "es-query-service/target/classes/com/dylan/esquery/service/KnowledgeSearchService.class",
                             REPO / "es-query-service/target/classes/application-knowledge-live.yml")}
            lease = ValidationAlias(source=IndexIdentity(online["expectedIndexName"], online["expectedIndexUuid"]),
                candidate=IndexIdentity(binding["expectedIndexName"], binding["expectedIndexUuid"]),
                published_alias=online["readAlias"])
            result["temporaryAlias"] = lease.name
            with lease as alias:
                with isolated_services(binding, alias, result) as tokens:
                    asyncio.run(typed_checks(binding, catalog, tokens, result))
            checked_bytes(REPO / "serviceCenter/knowledge-runtime-binding.v1.json", ONLINE_SHA)
            result.update(status="passed", validationAliasRemoved=True, onlineBindingUnchanged=True)
        except Exception as exc:
            # Never serialize raw exception context, provider response, token or corpus content.
            reason = str(exc) if type(exc) is ValueError and str(exc) in SAFE_REASONS else "validation_execution_failed"
            result["reason"] = reason
            result["causes"] = []
            context = exc.__context__
            while context is not None and len(result["causes"]) < 3:
                if type(context) is ValueError and str(context) in SAFE_REASONS:
                    result["causes"].append(str(context))
                context = context.__context__
        finally:
            if lease is not None:
                result.update(esManagementReads=lease.reads, validationAliasWrites=lease.writes)
            output.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
            output.flush()
            print(json.dumps({"status": result["status"], "reason": result.get("reason"),
                              "typedCalls": result["typedCalls"], "modelCalls": result["modelCalls"]}))
        return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
