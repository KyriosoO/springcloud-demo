"""Integrity-first Evidence selection for the independent minimal ranked batch."""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from datetime import date

from agent_runtime.knowledge.contracts import DomainCandidateCount, FailedPath, PathFailureKind, PathRef, RetrievalCoverage
from agent_runtime.knowledge.evidence.builder import EvidenceIntegrityError, _evidence_id
from agent_runtime.knowledge.evidence.contracts import (
    EvidenceCoverage, EvidenceSelectionResult, EvidenceSource, KnowledgeEvidence,
    KnowledgeEvidenceBundle, KnowledgeEvidenceLimits, KnowledgeModeSummaryInput,
    MinimalKnowledgeEvidenceInput, QuestionEvidenceTrace, SummaryCoverageInput,
    SummaryEvidenceInput, VerifiedKnowledgeCandidate,
)
from agent_runtime.knowledge.evidence.summary_task_v8 import mode_summary_input_json
from agent_runtime.knowledge.intent_contracts import (
    KnowledgeIntentOutcome, KnowledgeQueryIntent, KnowledgeQueryIntentInput,
)
from agent_runtime.knowledge.minimal_plan import MinimalKnowledgeRetrievalPlan
from agent_runtime.knowledge.retrieval.contracts import AuthorizedKnowledgeCandidate, PathRank
from agent_runtime.knowledge.retrieval.minimal_ranking import MinimalRankedBatch, MinimalRankedCandidate


_LOWER_HEX_64 = re.compile(r"[0-9a-f]{64}")
_SAFE_ID = re.compile(r"[A-Za-z0-9._:-]{1,256}")
_PROFILE_VERSION = "tax-knowledge-search-v1"
_CONTENT_CONTROLS = frozenset({"\t", "\n", "\r"})


def _valid_text(value: object, maximum: int, *, empty: bool = False,
                controls: frozenset[str] = frozenset()) -> bool:
    return (
        type(value) is str and (empty or bool(value)) and len(value) <= maximum
        and unicodedata.normalize("NFC", value) == value
        and all(unicodedata.category(character) != "Cc" or character in controls for character in value)
    )


def _valid_candidate_source(candidate: AuthorizedKnowledgeCandidate) -> bool:
    return (
        _valid_text(candidate.document_id, 256)
        and _valid_text(candidate.chunk_id, 256)
        and _valid_text(candidate.title, 256, empty=True)
        and _valid_text(candidate.content, 4096, controls=_CONTENT_CONTROLS)
        and _valid_text(candidate.material_type, 256)
        and (candidate.source_url is None or _valid_text(candidate.source_url, 1024, empty=True))
        and (candidate.document_number is None or _valid_text(candidate.document_number, 256, empty=True))
        and (candidate.written_date is None or type(candidate.written_date) is date)
        and type(candidate.source_rank) is int and 1 <= candidate.source_rank <= 20
        and type(candidate.policy_ref) is str and _SAFE_ID.fullmatch(candidate.policy_ref) is not None
        and type(candidate.read_policy_version) is str and _SAFE_ID.fullmatch(candidate.read_policy_version) is not None
        and type(candidate.content_sha256) is str and _LOWER_HEX_64.fullmatch(candidate.content_sha256) is not None
    )


class MinimalEvidenceIntegrityVerifier:
    def verify(self, *, input: MinimalKnowledgeEvidenceInput) -> tuple[VerifiedKnowledgeCandidate, ...]:
        if (
            type(input) is not MinimalKnowledgeEvidenceInput
            or type(input.question) is not KnowledgeQueryIntentInput
            or type(input.intent) is not KnowledgeQueryIntent
            or type(input.plan) is not MinimalKnowledgeRetrievalPlan
            or type(input.coverage) is not RetrievalCoverage
            or type(input.batch) is not MinimalRankedBatch
            or type(input.question_policy_version) is not str or not input.question_policy_version
            or type(input.question_egress_denied) is not bool
        ):
            raise EvidenceIntegrityError("knowledge.evidence_integrity_failed")
        plan, intent, batch, coverage = input.plan, input.intent, input.batch, input.coverage
        if (
            intent.outcome is not KnowledgeIntentOutcome.SEARCH
            or intent.query_mode is not plan.query_mode
            or intent.selected_domain_ids != plan.selected_domain_ids
            or intent.missing_conditions
            or input.question.minimized_question != plan.original_question
            or batch.profile_version != _PROFILE_VERSION
            or type(batch.candidates) is not tuple or not 1 <= len(batch.candidates) <= 20
            or type(batch.index_snapshot_ids) is not tuple or not batch.index_snapshot_ids
            or len(set(batch.index_snapshot_ids)) != len(batch.index_snapshot_ids)
            or any(type(value) is not str or _LOWER_HEX_64.fullmatch(value) is None
                   for value in batch.index_snapshot_ids)
        ):
            raise EvidenceIntegrityError("knowledge.evidence_integrity_failed")

        if (
            type(coverage.successful_paths) is not tuple
            or type(coverage.no_result_paths) is not tuple
            or type(coverage.failed_paths) is not tuple
            or any(type(item) is not PathRef for item in (*coverage.successful_paths, *coverage.no_result_paths))
            or any(type(item) is not FailedPath or not isinstance(item.failure_kind, PathFailureKind)
                   for item in coverage.failed_paths)
        ):
            raise EvidenceIntegrityError("knowledge.evidence_integrity_failed")
        planned_paths = {(item.logical_domain_id, item.path) for item in plan.items}
        successful_paths = {(item.logical_domain_id, item.path) for item in coverage.successful_paths}
        covered_paths = (
            tuple((item.logical_domain_id, item.path) for item in coverage.successful_paths)
            + tuple((item.logical_domain_id, item.path) for item in coverage.no_result_paths)
            + tuple((item.logical_domain_id, item.path) for item in coverage.failed_paths)
        )
        if (
            len(covered_paths) != len(planned_paths)
            or set(covered_paths) != planned_paths
            or len(set(covered_paths)) != len(covered_paths)
            or type(coverage.complete) is not bool
            or coverage.complete == bool(coverage.failed_paths)
            or type(coverage.candidate_count_by_domain) is not tuple
            or tuple(item.logical_domain_id for item in coverage.candidate_count_by_domain) != plan.selected_domain_ids
            or any(type(item) is not DomainCandidateCount or type(item.count) is not int
                   or not 0 <= item.count <= 80 for item in coverage.candidate_count_by_domain)
        ):
            raise EvidenceIntegrityError("knowledge.evidence_integrity_failed")

        verified: list[VerifiedKnowledgeCandidate] = []
        identities: set[tuple[str, str]] = set()
        document_facts: dict[str, tuple[str, str, str]] = {}
        domain_snapshots: dict[str, tuple[str, str]] = {}
        for expected_rank, item in enumerate(batch.candidates, 1):
            if type(item) is not MinimalRankedCandidate or type(item.candidate) is not AuthorizedKnowledgeCandidate:
                raise EvidenceIntegrityError("knowledge.evidence_integrity_failed")
            candidate = item.candidate
            expected_domains = tuple(domain for domain in plan.selected_domain_ids if domain in item.domain_ids)
            if (
                type(item.rank) is not int or item.rank != expected_rank
                or type(item.domain_ids) is not tuple or not item.domain_ids or item.domain_ids != expected_domains
                or candidate.domain_id not in item.domain_ids
                or type(item.rerank_score) not in (int, float) or not math.isfinite(item.rerank_score)
                or type(item.path_ranks) is not tuple or not item.path_ranks
                or any(type(path) is not PathRank or (path.logical_domain_id, path.path) not in planned_paths
                       or (path.logical_domain_id, path.path) not in successful_paths
                       or path.logical_domain_id not in item.domain_ids
                       or type(path.rank) is not int or not 1 <= path.rank <= 20 for path in item.path_ranks)
                or len({(path.logical_domain_id, path.path) for path in item.path_ranks}) != len(item.path_ranks)
                or not any(path.logical_domain_id == candidate.domain_id for path in item.path_ranks)
                or candidate.index_snapshot_id not in batch.index_snapshot_ids
                or not _valid_candidate_source(candidate)
                or hashlib.sha256(unicodedata.normalize("NFC", candidate.content).encode("utf-8")).hexdigest()
                   != candidate.content_sha256
            ):
                raise EvidenceIntegrityError("knowledge.evidence_integrity_failed")
            identity = (candidate.document_id, candidate.chunk_id)
            if identity in identities:
                raise EvidenceIntegrityError("knowledge.evidence_integrity_failed")
            identities.add(identity)
            document_fact = (candidate.policy_ref, candidate.read_policy_version, candidate.index_snapshot_id)
            if candidate.document_id in document_facts and document_facts[candidate.document_id] != document_fact:
                raise EvidenceIntegrityError("knowledge.evidence_integrity_failed")
            document_facts[candidate.document_id] = document_fact
            for domain in item.domain_ids:
                snapshot = (candidate.index_snapshot_id, candidate.read_policy_version)
                if domain in domain_snapshots and domain_snapshots[domain] != snapshot:
                    raise EvidenceIntegrityError("knowledge.evidence_integrity_failed")
                domain_snapshots[domain] = snapshot
            verified.append(VerifiedKnowledgeCandidate(
                rank=item.rank, candidate=candidate, domain_ids=item.domain_ids,
                rerank_score=item.rerank_score, profile_version=batch.profile_version,
            ))
        if any(sum(domain in item.domain_ids for item in verified) > count.count
               for domain, count in ((item.logical_domain_id, item) for item in coverage.candidate_count_by_domain)):
            raise EvidenceIntegrityError("knowledge.evidence_integrity_failed")
        return tuple(verified)


def _maximal_bytes(
    *, input: MinimalKnowledgeEvidenceInput, evidence: tuple[KnowledgeEvidence, ...],
    coverage: EvidenceCoverage,
) -> int:
    payload = KnowledgeModeSummaryInput(
        schema_version=3, question=input.plan.original_question, query_mode=input.plan.query_mode,
        coverage=SummaryCoverageInput(
            retrieval_complete=coverage.retrieval_complete,
            domain_coverage_complete=not coverage.missing_domain_ids,
        ),
        evidence=tuple(SummaryEvidenceInput(
            evidence_ref=f"e{ordinal}", content=item.content, domain_ids=item.domain_ids,
            title=item.source.title, document_number=item.source.document_number,
            written_date=item.source.written_date.isoformat() if item.source.written_date else None,
            material_type=item.source.material_type,
        ) for ordinal, item in enumerate(evidence, 1)),
    )
    return len(mode_summary_input_json(payload, max_bytes=None).encode("utf-8"))


class MinimalEvidenceSelector:
    def select(
        self, *, candidates: tuple[VerifiedKnowledgeCandidate, ...],
        input: MinimalKnowledgeEvidenceInput, minimized_question: str,
        limits: KnowledgeEvidenceLimits,
    ) -> EvidenceSelectionResult:
        if limits != KnowledgeEvidenceLimits.minimal_v1() or minimized_question != input.plan.original_question:
            raise EvidenceIntegrityError("knowledge.evidence_limits_version_mismatch")
        selected: list[KnowledgeEvidence] = []
        seen: set[tuple[str, str]] = set()
        represented: set[str] = set()

        def coverage_for(items: tuple[KnowledgeEvidence, ...]) -> EvidenceCoverage:
            domains = tuple(domain for domain in input.plan.selected_domain_ids
                            if any(domain in item.domain_ids for item in items))
            return EvidenceCoverage(
                retrieval_complete=input.coverage.complete,
                selected_domain_ids=input.plan.selected_domain_ids,
                represented_domain_ids=domains,
                missing_domain_ids=tuple(domain for domain in input.plan.selected_domain_ids if domain not in domains),
                failed_paths=input.coverage.failed_paths,
            )

        def try_add(item: VerifiedKnowledgeCandidate) -> bool:
            candidate = item.candidate
            identity = (candidate.document_id, candidate.chunk_id)
            if identity in seen or len(selected) >= limits.max_evidence:
                return False
            evidence = KnowledgeEvidence(
                evidence_id=_evidence_id(candidate.document_id, candidate.chunk_id, candidate.content_sha256),
                rank=item.rank, document_id=candidate.document_id, chunk_id=candidate.chunk_id,
                domain_ids=item.domain_ids, content=candidate.content, content_sha256=candidate.content_sha256,
                source=EvidenceSource(
                    title=candidate.title, source_url=candidate.source_url,
                    document_number=candidate.document_number, written_date=candidate.written_date,
                    material_type=candidate.material_type,
                ),
                read_policy_version=candidate.read_policy_version, policy_ref=candidate.policy_ref,
                index_snapshot_id=candidate.index_snapshot_id,
            )
            provisional = tuple(sorted((*selected, evidence), key=lambda current: current.rank))
            if _maximal_bytes(input=input, evidence=provisional, coverage=coverage_for(provisional)) > limits.max_summary_input_bytes:
                return False
            selected.append(evidence)
            seen.add(identity)
            represented.update(item.domain_ids)
            return True

        # First preserve one affordable source per selected domain, then fill globally by rank.
        for domain in input.plan.selected_domain_ids:
            if domain in represented:
                continue
            for item in candidates:
                if domain in item.domain_ids and try_add(item):
                    break
            if domain not in represented:
                return EvidenceSelectionResult(bundle=None, sufficient=False)
        for item in candidates:
            if len(selected) == limits.max_evidence:
                break
            try_add(item)
        ordered = tuple(sorted(selected, key=lambda item: item.rank))
        if not ordered or len({item.evidence_id for item in ordered}) != len(ordered):
            raise EvidenceIntegrityError("knowledge.evidence_id_collision")
        coverage = coverage_for(ordered)
        return EvidenceSelectionResult(
            bundle=KnowledgeEvidenceBundle(
                question_trace=QuestionEvidenceTrace(
                    original_question=input.plan.original_question, selected_query=input.plan.original_question,
                    minimized_question=minimized_question, question_policy_version=input.question_policy_version,
                ),
                coverage=coverage, evidence=ordered, profile_version=input.batch.profile_version,
                index_snapshot_ids=input.batch.index_snapshot_ids,
                maximal_summary_input_bytes=_maximal_bytes(input=input, evidence=ordered, coverage=coverage),
            ),
            sufficient=True,
        )
