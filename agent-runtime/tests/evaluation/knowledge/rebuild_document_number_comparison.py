"""Private document-number comparison DRAFT and in-memory replay, never a launcher.

This is not A, B, MEASURE, or a real-run authorization. Both arms use the same
corpus and production MinimalKnowledgeRetrievalStage. Only a future attested
Java helper may differ. No HTTP, inference, service startup, or run-asset writer
is provided here. Fresh full-record snapshots and a separately authorized real
transport/cleanup protocol are still required before any external execution.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import subprocess
from typing import Any

from agent_runtime.capability_api.contracts import CancellationSource, OpaqueUserToken
from agent_runtime.knowledge.contracts import KnowledgeRetrievalContext, RetrievalPath, RetrievalStageKind
from agent_runtime.knowledge.intent_contracts import (
    KnowledgeIntentOutcome, KnowledgeQueryIntent, KnowledgeQueryIntentInput, KnowledgeQueryMode,
)
from agent_runtime.knowledge.minimal_plan import (
    MinimalKnowledgePlanBuilder, MinimalKnowledgeRetrievalPlan, MinimalRetrievalSettings,
)
from agent_runtime.knowledge.retrieval.contracts import (
    AuthorizedKnowledgeCandidate, FusedCandidate, KnowledgePathRequest, PathCandidateSet, PathResultKind,
    PathRetrievalResult, RerankScore,
)
from agent_runtime.knowledge.retrieval.fusion import ReciprocalRankFusion
from agent_runtime.knowledge.retrieval.minimal_ranking import domain_pool, order_domain, round_robin
from agent_runtime.knowledge.retrieval.minimal_stage import MinimalKnowledgeRetrievalStage, _candidate_set

ROOT = Path(__file__).resolve().parents[4]
FIXTURE = "agent-runtime/tests/uat/knowledge_rebuild_measure.v1.json"
FIXTURE_SHA = "04a437d215ab242ea5e69eed95d109f47cf617135778f4d2cf5a13f6cddce26a"
OLD_HEAD = "a1ba290e8b2d78da71d46bc1f39018be502c7347"
HELPER = "es-query-service/src/main/java/com/dylan/esquery/service/DocumentNumberQuery.java"
SOURCE_SCOPE = ("es-query-service/src/main", "es-query-service/pom.xml", "es-query-api",
                "common-security", "serviceCenter/pom.xml", "config-service/src/main/resources/config")
CASE_IDS = tuple(f"UAT-KM-{i:03d}" for i in (1, 2, 3, 5, 6, 7, 8, 9, 11, 12))
ARMS = ("old", "current")
LIMITS = {"typedSearch": 44, "queryEmbedding": 10, "rerank": 22}
FORBIDDEN = ("model", "business", "indexWrites", "aliasWrites", "retry", "resume")
UNRESOLVED = ("fresh_full_record_pre_and_postflight", "actual_profile_policy_model_snapshots",
              "physical_http_witness_and_budget", "startup_health_prewarm_budget",
              "owned_process_and_proxy_cleanup", "exclusive_window", "independent_real_authorization")


class ProtocolError(ValueError):
    """Finite reason only; never include question, body, vectors, or exception text."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ProtocolError(reason)


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


@dataclass(frozen=True, slots=True, order=True)
class CandidateRef:
    document_id: str
    chunk_id: str
    content_sha256: str

    def __post_init__(self) -> None:
        require(all(type(value) is str and re.fullmatch(r"[A-Za-z0-9._:@#-]{1,256}", value) is not None
                    for value in (self.document_id, self.chunk_id))
                and type(self.content_sha256) is str
                and re.fullmatch(r"[0-9a-f]{64}", self.content_sha256) is not None, "reference_invalid")

    @classmethod
    def from_candidate(cls, item: AuthorizedKnowledgeCandidate) -> CandidateRef:
        return cls(item.document_id, item.chunk_id, item.content_sha256)


@dataclass(frozen=True, slots=True)
class ComparisonCase:
    case_id: str
    plan: MinimalKnowledgeRetrievalPlan = field(repr=False)
    necessary_sources: tuple[CandidateRef, ...]
    core: bool
    retained: bool

    def __post_init__(self) -> None:
        require(type(self.plan) is MinimalKnowledgeRetrievalPlan
                and type(self.case_id) is str and self.case_id in CASE_IDS
                and type(self.necessary_sources) is tuple and 1 <= len(self.necessary_sources) <= 16
                and all(type(ref) is CandidateRef for ref in self.necessary_sources)
                and len(set(self.necessary_sources)) == len(self.necessary_sources)
                and type(self.core) is bool and type(self.retained) is bool, "case_invalid")
        self.plan.validate(self.plan.settings)


def plan_fingerprint(plan: MinimalKnowledgeRetrievalPlan) -> str:
    return sha256(canonical(asdict(plan))).hexdigest()


@dataclass(frozen=True, slots=True)
class StageRanks:
    domain_id: str
    path: str
    ranked: tuple[CandidateRef, ...]


@dataclass(frozen=True, slots=True)
class ArmTrace:
    arm: str
    keyword: tuple[StageRanks, ...]
    keyword_es_ids: tuple[tuple[str, tuple[str, ...]], ...]
    vector: tuple[StageRanks, ...]
    fused: tuple[CandidateRef, ...]
    reranked: tuple[StageRanks, ...]
    final20: tuple[CandidateRef, ...]
    read_policy_by_domain: tuple[tuple[str, str], ...]
    # Never interpreted as real latency; replay does not measure service timing.
    latency_seconds: float


@dataclass(frozen=True, slots=True)
class CaseTrace:
    case_id: str
    baseline: ArmTrace
    candidate: ArmTrace


def _decode(raw: bytes) -> dict[str, Any]:
    require(type(raw) is bytes and 0 < len(raw) <= 2 * 1024 * 1024, "fixture_invalid")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            require(key not in value, "duplicate_json_key")
            value[key] = item
        return value

    def constant(_: str) -> None:
        raise ProtocolError("nonfinite_json")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=constant)
        require(type(value) is dict, "fixture_invalid")
        return dict(value)
    except (UnicodeError, json.JSONDecodeError):
        raise ProtocolError("fixture_invalid") from None


@dataclass(frozen=True, slots=True)
class DraftProtocol:
    frozen_head: str
    old_helper_sha256: str
    current_helper_sha256: str
    cases: tuple[ComparisonCase, ...] = field(repr=False)

    def __post_init__(self) -> None:
        require(type(self.frozen_head) is str and re.fullmatch(r"[0-9a-f]{40}", self.frozen_head) is not None
                and all(type(item) is str and re.fullmatch(r"[0-9a-f]{64}", item) is not None
                        for item in (self.old_helper_sha256, self.current_helper_sha256))
                and self.old_helper_sha256 != self.current_helper_sha256, "source_binding_invalid")
        require(type(self.cases) is tuple and all(type(case) is ComparisonCase for case in self.cases)
                and tuple(case.case_id for case in self.cases) == CASE_IDS
                and all(case.retained and case.plan.settings == MinimalRetrievalSettings()
                        for case in self.cases), "cases_invalid")
        require(sum(len(case.plan.items) for case in self.cases) * 2 == LIMITS["typedSearch"]
                and len(self.cases) == LIMITS["queryEmbedding"]
                and sum(len(case.plan.selected_domain_ids) for case in self.cases) * 2 == LIMITS["rerank"],
                "budget_plan_mismatch")

    def preview(self) -> dict[str, object]:
        return {"schemaVersion": 1, "kind": "document_number_chain_draft_v1",
            "status": "non_live_only", "realExecutionAllowed": False, "runId": None,
            "frozenHead": self.frozen_head, "oldHelperSourceHead": OLD_HEAD,
            "helperSha256": {"old": self.old_helper_sha256, "current": self.current_helper_sha256},
            "fixtureSha256": FIXTURE_SHA, "corpusSelection": "same_b2_full_competitive_pool",
            "actualCorpusSnapshot": "requires_fresh_snapshot;not_inherited_from_fixture",
            "caseIds": list(CASE_IDS), "planSha256": {case.case_id: plan_fingerprint(case.plan)
                                                      for case in self.cases},
            "evaluation": "keyword,vector,RRF,rerank,final20;no_answer_or_UAT_verdict",
            "plannedRetrievalUpperBounds": {**LIMITS, "physicalSearch": 44},
            "forbidden": dict.fromkeys(FORBIDDEN, 0), "unresolvedBeforeRealExecution": list(UNRESOLVED),
            "qualityRules": {"macroRecallMustStrictlyImprove": True, "precisionMayNotDecrease": True,
                "medianLatencyRatioMax": 1.10, "coreAndRetainedCoverageMayNotDecrease": True,
                "missingBlindLabels": "Not assessed", "sourceIdsAreNotRelevanceLabels": True}}


def draft_from_bytes(*, fixture_raw: bytes, head: str, old_helper: bytes, current_helper: bytes,
                     changed_paths: tuple[str, ...]) -> DraftProtocol:
    """Only local committed inputs; no original fingerprint is reused as current."""
    require(changed_paths == (HELPER,) and old_helper != current_helper
            and 0 < len(old_helper) <= 128 * 1024 and 0 < len(current_helper) <= 128 * 1024,
            "single_variable_unproven")
    require(sha256(fixture_raw).hexdigest() == FIXTURE_SHA, "fixture_drift")
    fixture = _decode(fixture_raw)
    require(fixture.get("schemaVersion") == 1 and fixture.get("datasetId") == "knowledge-rebuild-measure-v1",
            "fixture_invalid")
    sources = {item["id"]: item for item in fixture["sources"]}
    core = fixture["thresholds"]["uat"]["coreCases"]
    selected = tuple(item for item in fixture["cases"] if item["retrievalDenominator"] is True)
    require(tuple(item["caseId"] for item in selected) == CASE_IDS, "cases_invalid")
    cases = []
    for item in selected:
        plan = MinimalKnowledgePlanBuilder().build(
            question=KnowledgeQueryIntentInput(minimized_question=item["question"]),
            intent=KnowledgeQueryIntent(outcome=KnowledgeIntentOutcome.SEARCH,
                query_mode=KnowledgeQueryMode(item["queryMode"]),
                selected_domain_ids=tuple(item["expectedDomains"]), missing_conditions=()),
            settings=MinimalRetrievalSettings())
        refs = tuple(CandidateRef(sources[key]["documentId"], sources[key]["chunkId"],
                                  sources[key]["contentSha256"]) for key in item["necessarySources"])
        cases.append(ComparisonCase(item["caseId"], plan, refs, item["caseId"] in core, True))
    return DraftProtocol(head, sha256(old_helper).hexdigest(), sha256(current_helper).hexdigest(), tuple(cases))


def _git(root: Path, *args: str) -> bytes:
    try:
        return subprocess.run(["git", *args], cwd=root, check=True, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        raise ProtocolError("local_source_unavailable") from None


def draft_from_repository(root: Path = ROOT) -> DraftProtocol:
    require(_git(root, "branch", "--show-current").strip() == b"codex_0915", "branch_invalid")
    require(not _git(root, "status", "--porcelain", "--untracked-files=no").strip(), "tracked_tree_dirty")
    head = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    changed = _git(root, "diff", "--name-only", OLD_HEAD, head, "--", *SOURCE_SCOPE)
    result = draft_from_bytes(fixture_raw=_git(root, "show", f"{head}:{FIXTURE}"), head=head,
        old_helper=_git(root, "show", f"{OLD_HEAD}:{HELPER}"),
        current_helper=_git(root, "show", f"{head}:{HELPER}"),
        changed_paths=tuple(changed.decode("utf-8").splitlines()))
    require(_git(root, "rev-parse", "HEAD").decode("ascii").strip() == head
            and not _git(root, "status", "--porcelain", "--untracked-files=no").strip(), "source_drift")
    return result


@dataclass(frozen=True, slots=True)
class ReplayArm:
    paths: tuple[PathRetrievalResult, ...] = field(repr=False)
    # Scores must already be keyed by exact production domain-pool identities.
    scores: tuple[tuple[str, tuple[tuple[CandidateRef, float], ...]], ...] = field(repr=False)


@dataclass(frozen=True, slots=True)
class CaseReplay:
    case_id: str
    old: ReplayArm = field(repr=False)
    current: ReplayArm = field(repr=False)
    shared_vector: tuple[float, ...] = field(repr=False)


class ReplayError(ProtocolError):
    def __init__(self, reason: str, counts: dict[str, int], completed: tuple[CaseTrace, ...],
                 case_id: str | None) -> None:
        super().__init__(reason)
        self.counts = dict(counts)
        self.completed = completed
        self.case_id = case_id
        self.unexecuted = CASE_IDS[len(completed):]


class _Budget:
    def __init__(self) -> None:
        self.counts = dict.fromkeys(LIMITS, 0)

    def reserve(self, kind: str) -> None:
        require(kind in LIMITS and self.counts[kind] < LIMITS[kind], "replay_budget_exceeded")
        self.counts[kind] += 1


class _Cancellation:
    def is_cancelled(self) -> bool:
        return False

    async def wait_cancelled(self) -> CancellationSource:
        return await asyncio.Future[CancellationSource]()


class _Ports:
    """Concrete in-memory data only: no injectable outbound callback or transport."""
    def __init__(self, case: ComparisonCase, arm: ReplayArm, vector: tuple[float, ...], budget: _Budget,
                 context: KnowledgeRetrievalContext) -> None:
        self.case, self.arm, self.vector, self.budget, self.context = case, arm, vector, budget, context
        self.used: set[tuple[str, RetrievalPath]] = set()
        self.embedding_used = False
        self.reranks: list[tuple[tuple[AuthorizedKnowledgeCandidate, ...], tuple[RerankScore, ...]]] = []

    async def embed(self, *, text: str, timeout_s: float) -> tuple[float, ...]:
        require(text == self.case.plan.original_question and not self.embedding_used and timeout_s > 0,
                "embedding_request_drift")
        self.embedding_used = True
        return self.vector  # Shared once-counted query vector, never a new inference.

    async def search(self, *, request: KnowledgePathRequest, context: KnowledgeRetrievalContext,
                     timeout_s: float) -> PathRetrievalResult:
        key = (request.logical_domain_id, request.path)
        require(context is self.context and timeout_s > 0 and key not in self.used
                and key in {(item.logical_domain_id, item.path) for item in self.case.plan.items}
                and request.candidate_limit == 20 and
                (request.query_text == self.case.plan.original_question if request.path is RetrievalPath.KEYWORD
                 else request.query_vector is self.vector), "search_request_drift")
        self.used.add(key)
        self.budget.reserve("typedSearch")  # Attempts count, including failed replay responses.
        return next(item for item in self.arm.paths if (item.logical_domain_id, item.path) == key)

    async def rerank(self, *, query: str, candidates: tuple[AuthorizedKnowledgeCandidate, ...],
                     timeout_s: float) -> tuple[RerankScore, ...]:
        require(query == self.case.plan.original_question and bool(candidates) and timeout_s > 0,
                "rerank_request_drift")
        self.budget.reserve("rerank")
        domain = candidates[0].domain_id
        records = dict(dict(self.arm.scores).get(domain, ()))
        require(set(records) == {CandidateRef.from_candidate(item) for item in candidates}, "rerank_pool_drift")
        scores = tuple(RerankScore(candidate_index=i, score=records[CandidateRef.from_candidate(item)])
                       for i, item in enumerate(candidates))
        self.reranks.append((candidates, scores))
        return scores


def _validate_pair(case: ComparisonCase, replay: CaseReplay) -> None:
    require(type(replay) is CaseReplay and replay.case_id == case.case_id
            and type(replay.shared_vector) is tuple and len(replay.shared_vector) == 1024
            and all(type(value) is float and math.isfinite(value) for value in replay.shared_vector),
            "replay_input_invalid")
    expected = tuple((item.logical_domain_id, item.path) for item in case.plan.items)
    records_by_id: dict[tuple[str, str, str], AuthorizedKnowledgeCandidate] = {}
    domain_bindings: dict[str, tuple[str | None, str | None, str | None]] = {}
    score_by_id: dict[tuple[str, CandidateRef], float] = {}
    for arm in (replay.old, replay.current):
        require(type(arm) is ReplayArm and type(arm.paths) is tuple
                and all(type(item) is PathRetrievalResult for item in arm.paths)
                and tuple((item.logical_domain_id, item.path) for item in arm.paths) == expected,
                "replay_paths_invalid")
        require(type(arm.scores) is tuple and len(dict(arm.scores)) == len(arm.scores)
                and all(domain in case.plan.selected_domain_ids and type(rows) is tuple
                    and len(dict(rows)) == len(rows) and all(type(ref) is CandidateRef
                        and type(score) is float and math.isfinite(score) for ref, score in rows)
                    for domain, rows in arm.scores), "replay_scores_invalid")
        for domain, rows in arm.scores:
            for ref, score in rows:
                require(score_by_id.setdefault((domain, ref), score) == score, "replay_score_drift")
        for item in arm.paths:
            require(item.kind in (PathResultKind.CANDIDATES, PathResultKind.NO_RESULT), "replay_path_failed")
            require(item.profile_version == "tax-knowledge-search-v1"
                    and item.read_policy_version == "tax-public-authenticated-v1"
                    and type(item.index_snapshot_id) is str
                    and re.fullmatch(r"[0-9a-f]{64}", item.index_snapshot_id) is not None,
                    "replay_snapshot_invalid")
            binding = (item.index_snapshot_id, item.profile_version, item.read_policy_version)
            require(domain_bindings.setdefault(item.logical_domain_id, binding) == binding,
                    "replay_binding_drift")
            _candidate_set(item, limit=20)
            for candidate in item.candidates:
                key = (candidate.document_id, candidate.chunk_id)
                normalized = replace(candidate, source_rank=1)
                require(records_by_id.setdefault((item.logical_domain_id, *key), normalized) == normalized,
                        "replay_body_or_metadata_drift")
                for gold in case.necessary_sources:
                    require((gold.document_id, gold.chunk_id) != key or gold.content_sha256 == candidate.content_sha256,
                            "necessary_source_hash_drift")
    for old, current in zip(replay.old.paths, replay.current.paths, strict=True):
        require((old.index_snapshot_id, old.profile_version, old.read_policy_version)
                == (current.index_snapshot_id, current.profile_version, current.read_policy_version),
                "replay_binding_drift")
        # Same Java/config/corpus except helper: vector and law paths cannot differ.
        if old.path is RetrievalPath.VECTOR or old.logical_domain_id == "tax.law":
            require(old == current, "unrelated_path_drift")


def _trace(arm: str, case: ComparisonCase, ports: _Ports, final: tuple[CandidateRef, ...]) -> ArmTrace:
    sets: tuple[PathCandidateSet, ...] = tuple(_candidate_set(item, limit=20) for item in ports.arm.paths)
    keyword: list[StageRanks] = []
    vector: list[StageRanks] = []
    reranked: list[StageRanks] = []
    queues: list[tuple[tuple[FusedCandidate, float], ...]] = []
    for item in sets:
        ranks = StageRanks(item.logical_domain_id, item.path.value,
                           tuple(CandidateRef.from_candidate(c) for c in item.candidates))
        (keyword if item.path is RetrievalPath.KEYWORD else vector).append(ranks)
    fused = ReciprocalRankFusion().fuse(sets)
    calls = iter(ports.reranks)
    for domain in case.plan.selected_domain_ids:
        pool = domain_pool(sets, domain)
        if pool:
            candidates, scores = next(calls)
            require(candidates == tuple(item.candidate for item in pool), "trace_pool_drift")
            queue = order_domain(pool, scores)
            queues.append(queue)
            reranked.append(StageRanks(domain, "rerank", tuple(CandidateRef.from_candidate(c.candidate)
                                                               for c, _ in queue)))
    require(next(calls, None) is None, "trace_rerank_drift")
    require(final == tuple(CandidateRef.from_candidate(c.candidate)
        for c in round_robin(tuple(queues), fused, limit=20)), "trace_final_drift")
    return ArmTrace(arm, tuple(keyword), (), tuple(vector),
        tuple(CandidateRef.from_candidate(c.candidate) for c in fused), tuple(reranked), final,
        tuple((domain, "tax-public-authenticated-v1") for domain in case.plan.selected_domain_ids), 0.0)


@dataclass(frozen=True, slots=True)
class ReplayResult:
    cases: tuple[CaseTrace, ...]
    simulated_calls: tuple[tuple[str, int], ...]
    draft_sha256: str
    evidence_kind: str = "synthetic_non_live_replay"
    quality_conclusion: str = "Not assessed"
    real_outbound: int = 0


class ReplaySession:
    """Single attempt per session. Replays never become real measurement evidence."""
    def __init__(self) -> None:
        self.attempted = False

    async def evaluate(self, protocol: DraftProtocol, replays: tuple[CaseReplay, ...]) -> ReplayResult:
        require(not self.attempted, "replay_session_already_attempted")
        self.attempted = True
        protocol.__post_init__()
        require(type(replays) is tuple and tuple(item.case_id for item in replays) == CASE_IDS,
                "replay_cases_invalid")
        budget = _Budget()
        completed: list[CaseTrace] = []
        case_id: str | None = None
        try:
            for number, (case, replay) in enumerate(zip(protocol.cases, replays, strict=True)):
                case_id = case.case_id
                _validate_pair(case, replay)
                budget.reserve("queryEmbedding")
                context = KnowledgeRetrievalContext(request_id=case_id, correlation_id=case_id,
                    subject="non-live-replay", user_token=OpaqueUserToken.from_raw("synthetic-no-outbound"),
                    deadline_monotonic=asyncio.get_running_loop().time() + 30, cancellation=_Cancellation())
                traces: dict[str, ArmTrace] = {}
                for arm in (ARMS if number % 2 == 0 else tuple(reversed(ARMS))):
                    ports = _Ports(case, getattr(replay, arm), replay.shared_vector, budget, context)
                    result = await MinimalKnowledgeRetrievalStage(search=ports, embedding=ports, rerank=ports,
                        settings=case.plan.settings).execute(plan=case.plan, context=context, timeout_s=20)
                    require(result.kind in (RetrievalStageKind.SUCCESS, RetrievalStageKind.NO_RESULT)
                            and result.coverage is not None and result.coverage.complete
                            and not result.coverage.failed_paths and ports.embedding_used
                            and len(ports.used) == len(case.plan.items), "replay_stage_failed")
                    final = () if result.batch is None else tuple(CandidateRef.from_candidate(c.candidate)
                                                                 for c in result.batch.candidates)
                    traces[arm] = _trace(arm, case, ports, final)
                completed.append(CaseTrace(case_id, traces["old"], traces["current"]))
            return ReplayResult(tuple(completed), tuple(budget.counts.items()), sha256(canonical(protocol.preview())).hexdigest())
        except ProtocolError as error:
            raise ReplayError(str(error), budget.counts, tuple(completed), case_id) from None
        except (ValueError, StopIteration):
            raise ReplayError("replay_provider_invalid", budget.counts, tuple(completed), case_id) from None
        except asyncio.CancelledError:
            raise ReplayError("replay_cancelled", budget.counts, tuple(completed), case_id) from None


def replay_metrics(protocol: DraftProtocol, result: ReplayResult) -> dict[str, object]:
    """Exercise source-coverage math, not quality, adoption, or release approval."""
    require(type(result) is ReplayResult and result.evidence_kind == "synthetic_non_live_replay"
            and result.real_outbound == 0 and result.quality_conclusion == "Not assessed"
            and result.draft_sha256 == sha256(canonical(protocol.preview())).hexdigest()
            and tuple(case.case_id for case in result.cases) == CASE_IDS, "replay_metric_binding_invalid")
    rows = []
    totals: dict[str, list[float]] = {arm: [] for arm in ARMS}
    for case, trace in zip(protocol.cases, result.cases, strict=True):
        arms: dict[str, object] = {}
        for name, arm in (("old", trace.baseline), ("current", trace.candidate)):
            require(arm.arm == name, "trace_arm_invalid")
            stages = {"keyword": tuple(ref for ranks in arm.keyword for ref in ranks.ranked),
                      "vector": tuple(ref for ranks in arm.vector for ref in ranks.ranked),
                      "RRF": arm.fused,
                      "rerank": tuple(ref for ranks in arm.reranked for ref in ranks.ranked),
                      "final20": arm.final20}
            coverage = {stage: sum(ref in ranked for ref in case.necessary_sources) / len(case.necessary_sources)
                        for stage, ranked in stages.items()}
            totals[name].append(coverage["final20"])
            arms[name] = coverage
        rows.append({"caseId": case.case_id, "core": case.core, "retained": case.retained,
                     "simulatedNecessarySourceCoverage": arms})
    return {"kind": "synthetic_non_live_replay_metrics", "qualityConclusion": "Not assessed",
            "realExecutionAllowed": False, "adoptionAllowed": False, "releaseAllowed": False,
            "precisionAt20": None, "medianLatencyRatio": None,
            "simulatedMacroRecallAt20": {arm: sum(values) / len(values) for arm, values in totals.items()},
            "cases": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline draft preview only; no execute mode")
    parser.add_argument("--preview", action="store_true", required=True)
    parser.parse_args()
    try:
        print(canonical(draft_from_repository().preview()).decode("utf-8"), end="")
    except ProtocolError as error:
        parser.exit(2, f"document_number_comparison:{error}\n")


if __name__ == "__main__":
    main()
