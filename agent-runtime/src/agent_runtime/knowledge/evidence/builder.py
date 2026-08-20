from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata

from agent_runtime.knowledge.contracts import KnowledgeEvidenceInput
from agent_runtime.knowledge.evidence.contracts import (
    EvidenceCoverage,
    EvidenceSelectionResult,
    EvidenceSource,
    KnowledgeEvidence,
    KnowledgeEvidenceBundle,
    KnowledgeEvidenceLimits,
    QuestionEvidenceTrace,
    VerifiedKnowledgeCandidate,
)
from agent_runtime.knowledge.retrieval.contracts import RankedKnowledgeBatch


class EvidenceIntegrityError(ValueError):
    pass


_LOWER_HEX_64 = re.compile(r"[0-9a-f]{64}")


class EvidenceIntegrityVerifier:
    def verify(
        self,
        *,
        input: KnowledgeEvidenceInput[RankedKnowledgeBatch],
    ) -> tuple[VerifiedKnowledgeCandidate, ...]:
        batch = input.batch
        if not isinstance(batch, RankedKnowledgeBatch):
            raise EvidenceIntegrityError("knowledge.invalid_ranked_batch")
        if (
            batch.profile_version != "tax-knowledge-search-v1"
            or not input.selected_domain_ids
            or len(set(input.selected_domain_ids)) != len(input.selected_domain_ids)
            or any(domain not in {"tax.policy", "tax.law"} for domain in input.selected_domain_ids)
        ):
            raise EvidenceIntegrityError("knowledge.evidence_integrity_failed")
        verified: list[VerifiedKnowledgeCandidate] = []
        document_facts: dict[str, tuple[str, str, str]] = {}
        identities: set[tuple[str, str]] = set()
        for expected_rank, item in enumerate(batch.candidates, 1):
            candidate = item.candidate
            expected_domains = tuple(domain for domain in input.selected_domain_ids if domain in item.domain_ids)
            if (
                item.rank != expected_rank
                or item.domain_ids != expected_domains
                or candidate.domain_id not in item.domain_ids
                or type(item.rerank_score) not in (int, float)
                or isinstance(item.rerank_score, bool)
                or not math.isfinite(item.rerank_score)
            ):
                raise EvidenceIntegrityError("knowledge.evidence_integrity_failed")
            if any(domain not in input.selected_domain_ids for domain in item.domain_ids):
                raise EvidenceIntegrityError("knowledge.evidence_integrity_failed")
            if hashlib.sha256(unicodedata.normalize("NFC", candidate.content).encode("utf-8")).hexdigest() != candidate.content_sha256:
                raise EvidenceIntegrityError("knowledge.evidence_integrity_failed")
            identity = (candidate.document_id, candidate.chunk_id)
            if identity in identities:
                raise EvidenceIntegrityError("knowledge.evidence_integrity_failed")
            identities.add(identity)
            document_fact = (candidate.policy_ref, candidate.read_policy_version, candidate.index_snapshot_id)
            if candidate.document_id in document_facts and document_facts[candidate.document_id] != document_fact:
                raise EvidenceIntegrityError("knowledge.evidence_integrity_failed")
            document_facts[candidate.document_id] = document_fact
            verified.append(
                VerifiedKnowledgeCandidate(
                    rank=item.rank,
                    candidate=candidate,
                    domain_ids=tuple(domain for domain in input.selected_domain_ids if domain in item.domain_ids),
                    rerank_score=item.rerank_score,
                    profile_version=batch.profile_version,
                )
            )
        snapshots = batch.index_snapshot_ids
        if (
            not snapshots
            or len(set(snapshots)) != len(snapshots)
            or any(type(item) is not str or _LOWER_HEX_64.fullmatch(item) is None for item in snapshots)
            or any(item.candidate.index_snapshot_id not in snapshots for item in batch.candidates)
        ):
            raise EvidenceIntegrityError("knowledge.evidence_integrity_failed")
        return tuple(verified)


def _evidence_id(document_id: str, chunk_id: str, content_sha256: str) -> str:
    material = f"{unicodedata.normalize('NFC', document_id)}\n{unicodedata.normalize('NFC', chunk_id)}\n{content_sha256}"
    return "ev-" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def _maximal_bytes(question: str, evidence: tuple[KnowledgeEvidence, ...], coverage: EvidenceCoverage) -> int:
    value = {
        "schema_version": 1,
        "question": question,
        "coverage": {
            "retrieval_complete": coverage.retrieval_complete,
            "domain_coverage_complete": not coverage.missing_domain_ids,
        },
        "evidence": [
            {
                "evidence_ref": f"e{index}", "content": item.content, "domain_ids": item.domain_ids,
                "title": item.source.title, "document_number": item.source.document_number,
                "written_date": item.source.written_date.isoformat() if item.source.written_date else None,
                "material_type": item.source.material_type,
            }
            for index, item in enumerate(evidence, 1)
        ],
    }
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


class DeterministicEvidenceSelector:
    def select(
        self,
        *,
        candidates: tuple[VerifiedKnowledgeCandidate, ...],
        input: KnowledgeEvidenceInput[RankedKnowledgeBatch],
        minimized_question: str,
        limits: KnowledgeEvidenceLimits,
    ) -> EvidenceSelectionResult:
        required = {
            item.logical_domain_id
            for item in input.coverage.candidate_count_by_domain
            if item.count > 0
        }
        selected: list[KnowledgeEvidence] = []
        per_document: dict[str, int] = {}
        covered: set[str] = set()

        def try_add(item: VerifiedKnowledgeCandidate) -> str:
            candidate = item.candidate
            if len(selected) >= limits.max_evidence:
                return "full"
            if per_document.get(candidate.document_id, 0) >= limits.max_per_document:
                return "document_limit"
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
            provisional = tuple(selected + [evidence])
            represented = tuple(domain for domain in input.selected_domain_ids if any(domain in current.domain_ids for current in provisional))
            coverage = EvidenceCoverage(
                retrieval_complete=input.coverage.complete,
                selected_domain_ids=input.selected_domain_ids,
                represented_domain_ids=represented,
                missing_domain_ids=tuple(domain for domain in input.selected_domain_ids if domain not in represented),
                failed_paths=input.coverage.failed_paths,
            )
            if _maximal_bytes(minimized_question, provisional, coverage) > limits.max_summary_input_bytes:
                return "byte_limit"
            selected.append(evidence)
            per_document[candidate.document_id] = per_document.get(candidate.document_id, 0) + 1
            covered.update(item.domain_ids)
            return "added"

        for item in candidates:
            if required - covered and (required - covered) & set(item.domain_ids):
                try_add(item)
        if required - covered:
            return EvidenceSelectionResult(bundle=None, sufficient=False)
        for item in candidates:
            if any(existing.evidence_id == _evidence_id(item.candidate.document_id, item.candidate.chunk_id, item.candidate.content_sha256) for existing in selected):
                continue
            outcome = try_add(item)
            if outcome in {"full", "byte_limit"}:
                break
        if not selected:
            return EvidenceSelectionResult(bundle=None, sufficient=False)
        if len({item.evidence_id for item in selected}) != len(selected):
            raise EvidenceIntegrityError("knowledge.evidence_id_collision")
        represented = tuple(domain for domain in input.selected_domain_ids if any(domain in item.domain_ids for item in selected))
        coverage = EvidenceCoverage(
            retrieval_complete=input.coverage.complete,
            selected_domain_ids=input.selected_domain_ids,
            represented_domain_ids=represented,
            missing_domain_ids=tuple(domain for domain in input.selected_domain_ids if domain not in represented),
            failed_paths=input.coverage.failed_paths,
        )
        evidence_tuple = tuple(selected)
        byte_count = _maximal_bytes(minimized_question, evidence_tuple, coverage)
        return EvidenceSelectionResult(
            sufficient=True,
            bundle=KnowledgeEvidenceBundle(
                question_trace=QuestionEvidenceTrace(
                    original_question=input.original_question, selected_query=input.selected_query,
                    minimized_question=minimized_question, question_policy_version=input.question_policy_version,
                ),
                coverage=coverage, evidence=evidence_tuple,
                profile_version=candidates[0].profile_version,
                index_snapshot_ids=input.batch.index_snapshot_ids,
                maximal_summary_input_bytes=byte_count,
            ),
        )
