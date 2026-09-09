"""DR-KEV-034: real-byte, offline same-pool verification, never live UAT.

Read only sources present in the frozen, previously authorized typed retrieval.
Reuse saved scores, production fusion/ranking/verification/selection/egress.
No fresh service authorization, retrieval inference, Summary, or relevance grade
is claimed. Source bodies and projected model payloads remain in process memory.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import unicodedata

import httpx
import yaml

from agent_runtime.knowledge.contracts import (
    DomainCandidateCount, KnowledgeEvidenceInput, KnowledgeQuestionKind,
    KnowledgeRetrievalPlan, PathRef, RetrievalCoverage, RetrievalPath,
    RetrievalPlanItem, KNOWLEDGE_QUALITY_VERSION_V3,
)
from agent_runtime.knowledge.evidence.admission import ScoreAwareEvidenceSelector
from agent_runtime.knowledge.retrieval.contracts import (
    KnowledgePathRequest, PathCandidateSet, RankedKnowledgeBatch, RerankScore,
)
from agent_runtime.knowledge.retrieval.quality_ranking_v3 import rank_requirement_candidates
from tests.evaluation.knowledge.retrieval_benchmark_dataset import load_dataset
from tests.system_e2e import knowledge_retrieval_benchmark_v1 as benchmark
from tests.system_e2e import knowledge_stage_b_quality_v3_probe as base

REPO = base.REPO
RESULT = REPO / "agent-runtime/tests/evaluation/knowledge/evidence_admission.source_replay.result.v1.jsonl"
SAVED = RESULT.with_name("retrieval_benchmark.document_number.result.v1.jsonl")
SAVED_SHA = "b50ee584b09dc3b8d724886240a25b0e9de23e046d5245ef5ef395b81e865299"
PROFILE = REPO / "es-query-service/src/main/resources/application-knowledge-live.yml"
SOURCE_FIELDS = ("documentId", "chunkId", "title", "content", "sourceUrl", "documentNo",
                 "writtenDate", "materialType", "aclRef", "channel")
LIMITATIONS = ["offline_source_replay_not_fresh_read_authorization", "saved_scores_not_new_inference",
              "manual_plans_not_rewrite", "no_summary", "ungraded_relevance", "not_uat_or_production_enablement"]
FAILURE_REASONS = frozenset({
    "saved_result_changed", "saved_run_invalid", "saved_cases_invalid", "saved_path_invalid",
    "saved_identity_conflict", "source_pool_limit", "source_profile_changed", "source_projection_changed",
    "source_read_budget", "source_http_failed", "source_pool_incomplete", "source_search_incomplete",
    "source_count_changed", "source_fields_invalid", "source_identity_changed", "source_hash_changed",
    "source_metadata_invalid", "network_forbidden", "source_domain_changed", "score_query_changed",
    "score_pool_changed", "rank_replay_changed", "question_denied", "payload_limit", "worktree_dirty",
    "catalog_changed", "legacy_selection_changed", "source_metadata_changed",
    "execution_source_changed", "snapshot_read_budget",
})


class ReplayError(ValueError):
    """Only static, finite reason strings may cross the operational boundary."""


def require(condition, reason):
    if not condition:
        raise ReplayError(reason)


class SnapshotReader:
    def __init__(self, support, binding):
        self.support, self.reads = support, 0
        self.paths = {f'/_alias/{binding["readAlias"]}', f'/{binding["expectedIndexName"]}/_settings',
                      f'/{binding["expectedIndexName"]}/_mapping'}

    def bounded_request(self, client, method, path):
        require(method == "GET" and path in self.paths and self.reads < 6, "snapshot_read_budget")
        self.reads += 1
        return self.support.bounded_request(client, method, path)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(",", ":")).encode()


def load_inputs():
    with SAVED.open("rb") as stream:
        raw = stream.read(2 * 1024 * 1024 + 1)
    require(len(raw) <= 2 * 1024 * 1024 and digest(raw) == SAVED_SHA, "saved_result_changed")
    rows = [json.loads(line, object_pairs_hook=base._unique, parse_constant=base._reject_constant)
            for line in raw.splitlines()]
    dataset = load_dataset()
    require(rows[0]["datasetSha256"] == dataset.sha256 and rows[-1]["status"] == "measured"
            and rows[-1]["casesMeasured"] == 24, "saved_run_invalid")
    require([r["caseId"] for r in rows if r["event"] == "case"] == [c.id for c in dataset.cases],
            "saved_cases_invalid")
    pool = {}
    for row in rows:
        if row.get("stage") != "path":
            continue
        require(row["status"] == "candidates" and 1 <= len(row["candidates"]) <= 20, "saved_path_invalid")
        for item in row["candidates"]:
            identity = (item["sha256"], row["domain"])
            require(item["chunkId"] not in pool or pool[item["chunkId"]] == identity, "saved_identity_conflict")
            pool[item["chunkId"]] = identity
    require(1 <= len(pool) <= 1080, "source_pool_limit")
    profile_raw = PROFILE.read_bytes()
    require(digest(profile_raw) == rows[0]["artifactHashes"]["es-query-service/target/classes/application-knowledge-live.yml"],
            "source_profile_changed")
    profiles = yaml.safe_load(profile_raw)["es"]["query"]["knowledge"]["profiles"]
    for profile in profiles.values():
        require(set(profile["source-fields"].values()) | {profile["category-field"]} == set(SOURCE_FIELDS),
                "source_projection_changed")
    return rows, dataset, pool, profiles


class SourceReader:
    """Bounded read-only operational audit, not an Agent/Adapter ES shortcut."""

    def __init__(self, support, binding, maximum):
        self.support, self.binding, self.maximum = support, binding, maximum
        self.reads = 0

    def read_pool(self, pool):
        result = {}
        ids = sorted(pool)
        with httpx.Client(base_url="http://127.0.0.1:9200", timeout=5, trust_env=False,
                          follow_redirects=False, headers={"Accept-Encoding": "identity"}) as client:
            for start in range(0, len(ids), 40):
                require(self.reads < self.maximum, "source_read_budget")
                batch = ids[start:start + 40]
                self.reads += 1  # An unsuccessful attempt still consumes budget.
                status, raw = self.support.bounded_request(client, "POST", f'/{self.binding["expectedIndexName"]}/_search',
                    json={"size": len(batch), "track_total_hits": True, "_source": list(SOURCE_FIELDS),
                          "query": {"terms": {"chunkId": batch}}})
                require(status == 200, "source_http_failed")
                value = json.loads(raw, object_pairs_hook=base._unique, parse_constant=base._reject_constant)
                result.update(validate_hits(value, batch, pool))
        require(set(result) == set(pool), "source_pool_incomplete")
        return result


def validate_hits(value, batch, pool):
    require(value.get("timed_out") is False and type(value["_shards"]["failed"]) is int
            and value["_shards"]["failed"] == 0, "source_search_incomplete")
    hits = value["hits"]
    require(type(hits["total"]["value"]) is int and hits["total"] == {"value": len(batch), "relation": "eq"}
            and len(hits["hits"]) == len(batch), "source_count_changed")
    result = {}
    for hit in hits["hits"]:
        source = hit["_source"]
        require(type(source) is dict and set(source) <= set(SOURCE_FIELDS), "source_fields_invalid")
        key, content = source["chunkId"], source["content"]
        require(key in batch and key not in result and type(content) is str, "source_identity_changed")
        require(content == unicodedata.normalize("NFC", content) and digest(content.encode()) == pool[key][0],
                "source_hash_changed")
        require(all(type(v) is str and v == unicodedata.normalize("NFC", v) for v in source.values() if v is not None),
                "source_metadata_invalid")
        result[key] = source
    return result


class NoTransport:
    async def send(self, **kwargs):
        raise ReplayError("network_forbidden")


def path_set(row, sources, binding, profiles):
    domain, path = row["domain"], RetrievalPath(row["path"])
    profile_id = "tax-policy-v1" if domain == "tax.policy" else "tax-law-v1"
    profile, candidates = profiles[profile_id], []
    snapshot = binding["policySnapshotId" if domain == "tax.policy" else "lawSnapshotId"]
    for rank, item in enumerate(row["candidates"], 1):
        s = sources[item["chunkId"]]
        require(s["channel"] in profile["category-values"], "source_domain_changed")
        require(digest(s["content"].encode()) == item["sha256"], "source_hash_changed")
        candidates.append({"documentId": s["documentId"], "chunkId": s["chunkId"], "logicalDomainId": domain,
            "title": s["title"], "content": s["content"], "sourceUrl": s.get("sourceUrl"),
            "documentNumber": s.get("documentNo"), "writtenDate": s.get("writtenDate"),
            "materialType": s["materialType"], "sourceRank": rank, "contentSha256": item["sha256"], "policyRef": s["aclRef"]})
    # Decoder-only envelope: the vector is never used or sent. Preserve exact
    # real source metadata; prior typed result supplies authorization provenance.
    request = KnowledgePathRequest(logical_domain_id=domain, retrieval_profile_id=profile_id, path=path,
        query_text="offline replay" if path is RetrievalPath.KEYWORD else None,
        query_vector=(0.0,) * 1024 if path is RetrievalPath.VECTOR else None, candidate_limit=20)
    result = base.EsKnowledgeSearchAdapter(NoTransport())._decode(request, "application/json", None, canonical({
        "schemaVersion": 1, "logicalDomainId": domain, "retrievalProfileId": profile_id, "path": path.value,
        "profileVersion": profile["profile-version"], "readPolicyVersion": profile["read-policy-version"],
        "indexSnapshotId": snapshot, "truncated": False, "candidates": candidates}))
    return PathCandidateSet(logical_domain_id=domain, retrieval_profile_id=profile_id, path=path,
        profile_version=result.profile_version, read_policy_version=result.read_policy_version,
        index_snapshot_id=snapshot, truncated=False, candidates=result.candidates)


async def replay_case(case, rows, sources, binding, profiles):
    part = [r for r in rows if r.get("caseId") == case.id]
    sets = tuple(path_set(r, sources, binding, profiles) for r in part if r.get("stage") == "path")
    plan = KnowledgeRetrievalPlan(config_version="knowledge-flow-config-v1", quality_version=KNOWLEDGE_QUALITY_VERSION_V3,
        question_kind=KnowledgeQuestionKind.LOOKUP, selected_domain_ids=case.domains, evidence_requirements=case.requirements,
        items=tuple(RetrievalPlanItem(logical_domain_id=d, query_text=case.question, path=p, candidate_limit=20, ordinal=i)
            for i, (d, p) in enumerate(((d, p) for d in case.domains for p in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR)), 1)))
    score_rows = sorted((r for r in part if r.get("stage") == "rerank"), key=lambda r: r["ordinal"])

    class Scores:
        n = 0

        async def rerank(self, *, query, candidates, timeout_s):
            require(self.n < len(score_rows) and query == case.requirements[self.n].focus, "score_query_changed")
            scored = {(c["chunkId"], c["sha256"]): c["score"] for c in score_rows[self.n]["candidates"]}
            self.n += 1
            require(set(scored) == {(c.chunk_id, c.content_sha256) for c in candidates}, "score_pool_changed")
            return tuple(RerankScore(candidate_index=i, score=scored[(c.chunk_id, c.content_sha256)]) for i, c in enumerate(candidates))

    scores, fusion = Scores(), base.ReciprocalRankFusion()
    ranked = await rank_requirement_candidates(plan=plan, sets=sets, fused=fusion.fuse(sets), fusion=fusion,
        rerank=scores, deadline=asyncio.get_running_loop().time() + 5, final_candidates=20)
    saved = next(r for r in part if r["event"] == "case")
    projection = [{**base.identity(c.candidate), "rank": c.rank, "requirementIds": list(c.requirement_ids)} for c in ranked]
    require(scores.n == len(case.requirements) and projection == saved["ranked"], "rank_replay_changed")
    guard = base.QuestionEgressGuard().evaluate(case.question)
    require(guard.disposition is base.QuestionEgressDisposition.ALLOWED, "question_denied")
    value = KnowledgeEvidenceInput(original_question=case.question, selected_query=case.question,
        selected_domain_ids=case.domains, quality_version=plan.quality_version, question_kind=plan.question_kind,
        evidence_requirements=case.requirements, question_policy_version=guard.policy_version, question_egress_denied=False,
        batch=RankedKnowledgeBatch(candidates=ranked, profile_version="tax-knowledge-search-v1",
            index_snapshot_ids=tuple(dict.fromkeys(s.index_snapshot_id for s in sets))),
        coverage=RetrievalCoverage(successful_paths=tuple(PathRef(logical_domain_id=s.logical_domain_id, path=s.path) for s in sets),
            no_result_paths=(), failed_paths=(), complete=True,
            candidate_count_by_domain=tuple(DomainCandidateCount(logical_domain_id=d, count=sum(d in c.domain_ids for c in ranked)) for d in case.domains)))
    return value, saved


def evaluate(value, selector, catalog, case, dataset):
    selection = selector.select(candidates=base.EvidenceIntegrityVerifier().verify(input=value), input=value,
        minimized_question=case.question, limits=base.KnowledgeEvidenceLimits.quality_v3())
    policy = base.KnowledgeEvidenceEgressDecider().decide(bundle=selection.bundle, catalog=catalog) if selection.bundle else None
    payload_bytes = 0
    if policy and policy.allowed:
        p = policy.summary_input
        payload = base.KnowledgeRequirementSummaryInput(schema_version=2, question=p.question,
            coverage=p.coverage, evidence=p.evidence, requirements=case.requirements)
        payload_bytes = len(base.requirement_summary_input_json(payload).encode())
        require(payload_bytes <= base.KnowledgeEvidenceLimits.quality_v3().max_summary_input_bytes, "payload_limit")
    evidence = [base.identity(c) for c in selection.bundle.evidence] if selection.bundle else []
    # Gold is used only after selection/policy, never as an admission signal.
    refs = [s for s in dataset.sources if s.id in case.sources]
    coverage = all(any(e == {"chunkId": s.chunk_id, "sha256": s.sha256} for e in evidence) and
        policy is not None and policy.allowed and any(digest(e.content.encode()) == s.sha256
            and all(a in e.content for a in s.anchors) for e in policy.summary_input.evidence) for s in refs)
    return {"sufficient": selection.sufficient, "policyAllowed": bool(policy and policy.allowed),
        "policyFingerprint": policy.snapshot_fingerprint if policy and policy.allowed else None,
        "payloadBytes": payload_bytes, "evidence": evidence, "requiredSourcesPreserved": coverage,
        "metrics": benchmark.measure_case(case, dataset, [base.identity(c.candidate) for c in value.batch.candidates], evidence)}


def current_head():
    raw = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=REPO, text=True)
    allowed = "?? " + RESULT.relative_to(REPO).as_posix()
    require(all(line == allowed for line in raw.splitlines()), "worktree_dirty")
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    if not parser.parse_args().execute:
        parser.error("explicit --execute required")
    terminal = {"event": "terminal", "status": "failed", "casesMeasured": 0, "requiredSourcesPreserved": 0,
        "modelCalls": 0, "embeddingCalls": 0, "rerankCalls": 0, "businessCalls": 0, "indexWrites": 0,
        "retry": 0, "resume": 0, "sourceReads": 0, "snapshotReads": 0, "rawContentPersisted": False,
        "limitations": LIMITATIONS}
    reader = snapshots = None
    # Exclusive create: this verification cannot overwrite or resume itself.
    with RESULT.open("xb") as stream:
        try:
            head = current_head()
            rows, dataset, pool, profiles = load_inputs()
            support = base.load_support()
            binding = json.loads(support.checked_bytes(REPO / "serviceCenter/knowledge-runtime-binding.v2.json", base.BINDING_SHA))
            catalog = base.KnowledgeEgressPolicyCatalog.load_current_resource()
            require(catalog.snapshot.source_sha256 == base.CATALOG_SHA, "catalog_changed")
            maximum = 2 * ((len(pool) + 39) // 40)
            base.emit_line(stream, {"event": "prepared", "head": head, "sourceResultSha256": SAVED_SHA,
                "datasetSha256": dataset.sha256, "bindingSha256": base.BINDING_SHA, "catalogSha256": base.CATALOG_SHA,
                "scriptSha256": digest(Path(__file__).read_bytes()), "selectorVersion": ScoreAwareEvidenceSelector.VERSION,
                "selectorSha256": digest((REPO / "agent-runtime/src/agent_runtime/knowledge/evidence/admission.py").read_bytes()),
                "rerankInputVersion": rows[0]["rerankInputVersion"],
                "scoreModelProvenance": rows[0]["localModelContainers"], "sourcePoolCount": len(pool),
                "sourceReadBudget": maximum, "snapshotReadBudget": 6, "limitations": LIMITATIONS})
            snapshots = SnapshotReader(support, binding)
            base.check_index(snapshots, binding)
            reader = SourceReader(support, binding, maximum)
            sources = reader.read_pool(pool)
            fingerprint = digest(canonical(sources))
            for case in dataset.cases:
                value, saved = asyncio.run(replay_case(case, rows, sources, binding, profiles))
                old = evaluate(value, base.DeterministicEvidenceSelector(), catalog, case, dataset)
                require(old["evidence"] == saved["evidence"] and old["sufficient"] == saved["selectionSufficient"]
                        and old["policyAllowed"] == saved["policyAllowed"], "legacy_selection_changed")
                new = evaluate(value, ScoreAwareEvidenceSelector(), catalog, case, dataset)
                base.emit_line(stream, {"event": "case", "caseId": case.id, "split": case.split, "legacy": old, "candidate": new})
                terminal["casesMeasured"] += 1
                terminal["requiredSourcesPreserved"] += bool(new["requiredSourcesPreserved"])
            require(digest(canonical(reader.read_pool(pool))) == fingerprint, "source_metadata_changed")
            base.check_index(snapshots, binding)
            require(current_head() == head and digest(SAVED.read_bytes()) == SAVED_SHA, "execution_source_changed")
            terminal.update(status="measured", sourcePoolCount=len(pool), sourceMetadataFingerprint=fingerprint)
        except Exception as error:
            # Do not serialize HTTP errors, model/body text, exception locals or traceback.
            terminal["failureReason"] = str(error) if type(error) is ReplayError and str(error) in FAILURE_REASONS else "execution_failed"
        finally:
            terminal["sourceReads"] = reader.reads if reader else 0
            terminal["snapshotReads"] = snapshots.reads if snapshots else 0
            base.emit_line(stream, terminal)
        print(json.dumps(terminal), flush=True)
    return 0 if terminal["status"] == "measured" else 1


if __name__ == "__main__":
    raise SystemExit(main())
