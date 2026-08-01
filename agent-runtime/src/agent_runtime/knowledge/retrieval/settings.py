from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Self
from urllib.parse import urlsplit


class KnowledgeRetrievalConfigurationError(ValueError):
    pass


_KNOWN = frozenset(
    {
        "AGENT_KNOWLEDGE_ES_BASE_URL",
        "AGENT_KNOWLEDGE_PROFILE_VERSION",
        "AGENT_KNOWLEDGE_EMBEDDING_BASE_URL",
        "AGENT_KNOWLEDGE_RERANK_BASE_URL",
        "AGENT_KNOWLEDGE_EMBEDDING_DIM",
        "AGENT_KNOWLEDGE_RERANK_MODEL",
        "AGENT_KNOWLEDGE_FINAL_CANDIDATES",
    }
)
_OWNED_PREFIXES = (
    "AGENT_KNOWLEDGE_ES_",
    "AGENT_KNOWLEDGE_PROFILE_",
    "AGENT_KNOWLEDGE_EMBEDDING_",
    "AGENT_KNOWLEDGE_RERANK_",
    "AGENT_KNOWLEDGE_FINAL_",
)


def _origin(raw: str, *, loopback_only: bool) -> str:
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise KnowledgeRetrievalConfigurationError("knowledge.retrieval_settings_invalid") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise KnowledgeRetrievalConfigurationError("knowledge.retrieval_settings_invalid")
    if loopback_only and parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
        raise KnowledgeRetrievalConfigurationError("knowledge.retrieval_settings_invalid")
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    canonical = f"{parsed.scheme}://{host}" + (f":{port}" if port is not None else "")
    if raw.rstrip("/") != canonical:
        raise KnowledgeRetrievalConfigurationError("knowledge.retrieval_settings_invalid")
    return canonical


def _exact_integer(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key, str(default))
    if not raw or not raw.isascii() or not raw.isdecimal() or raw != str(int(raw)):
        raise KnowledgeRetrievalConfigurationError("knowledge.retrieval_settings_invalid")
    return int(raw)


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeRetrievalSettings:
    es_base_url: str | None
    profile_version: str
    embedding_base_url: str
    rerank_base_url: str
    embedding_dimension: int
    rerank_model: str
    final_candidates: int

    @classmethod
    def from_env(cls, env: Mapping[str, str], *, enabled: bool) -> Self:
        if any(
            key.startswith(_OWNED_PREFIXES) and key not in _KNOWN
            for key in env
        ):
            raise KnowledgeRetrievalConfigurationError("knowledge.retrieval_settings_unknown_key")
        raw_es = env.get("AGENT_KNOWLEDGE_ES_BASE_URL")
        if enabled and not raw_es:
            raise KnowledgeRetrievalConfigurationError("knowledge.retrieval_es_base_url_required")
        es_base_url = _origin(raw_es, loopback_only=False) if raw_es else None
        profile_version = env.get("AGENT_KNOWLEDGE_PROFILE_VERSION", "tax-knowledge-search-v1")
        embedding_base_url = _origin(
            env.get("AGENT_KNOWLEDGE_EMBEDDING_BASE_URL", "http://127.0.0.1:8908"),
            loopback_only=True,
        )
        rerank_base_url = _origin(
            env.get("AGENT_KNOWLEDGE_RERANK_BASE_URL", "http://127.0.0.1:8909"),
            loopback_only=True,
        )
        embedding_dimension = _exact_integer(env, "AGENT_KNOWLEDGE_EMBEDDING_DIM", 1024)
        rerank_model = env.get("AGENT_KNOWLEDGE_RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
        final_candidates = _exact_integer(env, "AGENT_KNOWLEDGE_FINAL_CANDIDATES", 20)
        if (
            profile_version != "tax-knowledge-search-v1"
            or embedding_dimension != 1024
            or rerank_model != "BAAI/bge-reranker-v2-m3"
            or not 3 <= final_candidates <= 20
        ):
            raise KnowledgeRetrievalConfigurationError("knowledge.retrieval_settings_invalid")
        return cls(
            es_base_url=es_base_url,
            profile_version=profile_version,
            embedding_base_url=embedding_base_url,
            rerank_base_url=rerank_base_url,
            embedding_dimension=embedding_dimension,
            rerank_model=rerank_model,
            final_candidates=final_candidates,
        )
