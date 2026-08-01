from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Protocol

from agent_runtime.knowledge.contracts import KnowledgeRetrievalContext, RetrievalPath


class PathResultKind(StrEnum):
    CANDIDATES = "candidates"
    NO_RESULT = "no_result"
    FORBIDDEN = "forbidden"
    TIMEOUT = "timeout"
    FAILURE = "failure"


class PathResultFailure(StrEnum):
    READ_DECISION_UNVERIFIABLE = "read_decision_unverifiable"
    READ_AUTHORITY_FAILURE = "read_authority_failure"
    RETRIEVAL_FAILURE = "retrieval_failure"
    INVALID_PROVIDER_RESULT = "invalid_provider_result"


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgePathRequest:
    logical_domain_id: str
    retrieval_profile_id: str
    path: RetrievalPath
    query_text: str | None
    query_vector: tuple[float, ...] | None
    candidate_limit: int

    def __post_init__(self) -> None:
        expected = {"tax.policy": "tax-policy-v1", "tax.law": "tax-law-v1"}
        if expected.get(self.logical_domain_id) != self.retrieval_profile_id or not 5 <= self.candidate_limit <= 20:
            raise ValueError("knowledge.invalid_path_request")
        if self.path is RetrievalPath.KEYWORD:
            if not isinstance(self.query_text, str) or not 1 <= len(self.query_text) <= 1024 or self.query_vector is not None:
                raise ValueError("knowledge.invalid_path_request")
        elif self.path is RetrievalPath.VECTOR:
            if self.query_text is not None or self.query_vector is None or len(self.query_vector) != 1024:
                raise ValueError("knowledge.invalid_path_request")
            if any(not math.isfinite(value) for value in self.query_vector):
                raise ValueError("knowledge.invalid_path_request")
        else:
            raise ValueError("knowledge.invalid_path_request")


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthorizedKnowledgeCandidate:
    document_id: str
    chunk_id: str
    domain_id: str
    title: str
    content: str
    source_url: str | None
    document_number: str | None
    written_date: date | None
    material_type: str
    source_rank: int
    content_sha256: str
    read_policy_version: str
    policy_ref: str
    index_snapshot_id: str

    def __post_init__(self) -> None:
        required = (self.document_id, self.chunk_id, self.domain_id, self.title, self.content, self.material_type, self.read_policy_version, self.policy_ref, self.index_snapshot_id)
        if any(not isinstance(value, str) or not value for value in required):
            raise ValueError("knowledge.invalid_candidate")
        if self.domain_id not in {"tax.policy", "tax.law"} or not 1 <= self.source_rank <= 20:
            raise ValueError("knowledge.invalid_candidate")
        if len(self.title) > 256 or len(self.content) > 4096 or len(self.document_id) > 256 or len(self.chunk_id) > 256:
            raise ValueError("knowledge.invalid_candidate")
        if len(self.content_sha256) != 64 or any(character not in "0123456789abcdef" for character in self.content_sha256):
            raise ValueError("knowledge.invalid_candidate")
        for name in ("document_id", "chunk_id", "title", "content", "material_type"):
            value = getattr(self, name)
            object.__setattr__(self, name, unicodedata.normalize("NFC", value))


@dataclass(frozen=True, slots=True, kw_only=True)
class PathRetrievalResult:
    kind: PathResultKind
    logical_domain_id: str
    retrieval_profile_id: str
    path: RetrievalPath
    profile_version: str | None = None
    index_snapshot_id: str | None = None
    read_policy_version: str | None = None
    truncated: bool = False
    candidates: tuple[AuthorizedKnowledgeCandidate, ...] = ()
    failure: PathResultFailure | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class PathRank:
    logical_domain_id: str
    path: RetrievalPath
    rank: int


@dataclass(frozen=True, slots=True, kw_only=True)
class PathCandidateSet:
    logical_domain_id: str
    retrieval_profile_id: str
    path: RetrievalPath
    profile_version: str
    index_snapshot_id: str
    read_policy_version: str
    truncated: bool
    candidates: tuple[AuthorizedKnowledgeCandidate, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class FusedCandidate:
    candidate: AuthorizedKnowledgeCandidate
    domain_ids: tuple[str, ...]
    path_ranks: tuple[PathRank, ...]
    rrf_score: float


@dataclass(frozen=True, slots=True, kw_only=True)
class RerankScore:
    candidate_index: int
    score: float


@dataclass(frozen=True, slots=True, kw_only=True)
class RankedKnowledgeCandidate:
    candidate: AuthorizedKnowledgeCandidate
    domain_ids: tuple[str, ...]
    rerank_score: float
    rank: int


@dataclass(frozen=True, slots=True, kw_only=True)
class RankedKnowledgeBatch:
    candidates: tuple[RankedKnowledgeCandidate, ...]
    profile_version: str
    index_snapshot_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not 1 <= len(self.candidates) <= 20:
            raise ValueError("knowledge.invalid_ranked_batch")
        if tuple(item.rank for item in self.candidates) != tuple(range(1, len(self.candidates) + 1)):
            raise ValueError("knowledge.invalid_ranked_batch")


class KnowledgeSearchPort(Protocol):
    async def search(
        self,
        *,
        request: KnowledgePathRequest,
        context: KnowledgeRetrievalContext,
        timeout_s: float,
    ) -> PathRetrievalResult: ...


class EmbeddingPort(Protocol):
    async def embed(self, *, text: str, timeout_s: float) -> tuple[float, ...]: ...


class RerankPort(Protocol):
    async def rerank(
        self,
        *,
        query: str,
        candidates: tuple[AuthorizedKnowledgeCandidate, ...],
        timeout_s: float,
    ) -> tuple[RerankScore, ...]: ...

