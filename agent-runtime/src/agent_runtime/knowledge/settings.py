from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Self

from agent_runtime.knowledge.catalog import build_tax_domain_catalog
from agent_runtime.knowledge.errors import KnowledgeConfigurationError

_PREFIX = "AGENT_KNOWLEDGE_"
_KNOWN = frozenset(
    {
        "AGENT_KNOWLEDGE_ENABLED",
        "AGENT_KNOWLEDGE_ENABLED_DOMAINS",
        "AGENT_KNOWLEDGE_REWRITE_MAX_CANDIDATES",
        "AGENT_KNOWLEDGE_ALLOW_ORIGINAL_FALLBACK",
        "AGENT_KNOWLEDGE_MAX_RETRIEVAL_QUERY_CHARS",
        "AGENT_KNOWLEDGE_PER_PATH_CANDIDATES",
        "AGENT_KNOWLEDGE_MIN_PARTIAL_CANDIDATES",
        "AGENT_KNOWLEDGE_REWRITE_TIMEOUT_MS",
        "AGENT_KNOWLEDGE_RETRIEVAL_TIMEOUT_MS",
        "AGENT_KNOWLEDGE_EVIDENCE_TIMEOUT_MS",
        "AGENT_KNOWLEDGE_ES_BASE_URL",
        "AGENT_KNOWLEDGE_PROFILE_VERSION",
        "AGENT_KNOWLEDGE_EMBEDDING_BASE_URL",
        "AGENT_KNOWLEDGE_RERANK_BASE_URL",
        "AGENT_KNOWLEDGE_EMBEDDING_DIM",
        "AGENT_KNOWLEDGE_RERANK_MODEL",
        "AGENT_KNOWLEDGE_FINAL_CANDIDATES",
    }
)


def _boolean(env: Mapping[str, str], key: str, default: bool) -> bool:
    raw = env.get(key)
    if raw is None:
        return default
    if raw == "true":
        return True
    if raw == "false":
        return False
    raise KnowledgeConfigurationError(f"knowledge.settings_invalid:{key}")


def _integer(env: Mapping[str, str], key: str, default: int, minimum: int, maximum: int) -> int:
    raw = env.get(key)
    if raw is None:
        value = default
    elif raw and raw.isascii() and raw.isdecimal() and raw == str(int(raw)):
        value = int(raw)
    else:
        raise KnowledgeConfigurationError(f"knowledge.settings_invalid:{key}")
    if not minimum <= value <= maximum:
        raise KnowledgeConfigurationError(f"knowledge.settings_invalid:{key}")
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeSettings:
    enabled: bool
    enabled_domain_ids: tuple[str, ...]
    rewrite_max_candidates: int
    allow_original_fallback: bool
    max_retrieval_query_chars: int
    per_path_candidate_limit: int
    min_partial_candidates: int
    rewrite_timeout_ms: int
    retrieval_timeout_ms: int
    evidence_timeout_ms: int
    config_version: str = "knowledge-flow-config-v1"

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Self:
        unknown = sorted(key for key in env if key.startswith(_PREFIX) and key not in _KNOWN)
        if unknown:
            raise KnowledgeConfigurationError("knowledge.settings_unknown_key")
        enabled = _boolean(env, "AGENT_KNOWLEDGE_ENABLED", False)
        raw_domains = env.get("AGENT_KNOWLEDGE_ENABLED_DOMAINS", "")
        known_order = tuple(item.domain_id for item in build_tax_domain_catalog().domains)
        if raw_domains == "":
            requested: tuple[str, ...] = ()
        else:
            parts = tuple(raw_domains.split(","))
            if any(not item or item not in known_order for item in parts) or len(set(parts)) != len(parts):
                raise KnowledgeConfigurationError("knowledge.settings_invalid:AGENT_KNOWLEDGE_ENABLED_DOMAINS")
            requested = tuple(item for item in known_order if item in parts)
        if enabled and not requested:
            raise KnowledgeConfigurationError("knowledge.enabled_domains_required")
        per_path = _integer(env, "AGENT_KNOWLEDGE_PER_PATH_CANDIDATES", 20, 5, 20)
        partial = _integer(env, "AGENT_KNOWLEDGE_MIN_PARTIAL_CANDIDATES", 3, 3, 20)
        if partial > per_path:
            raise KnowledgeConfigurationError("knowledge.partial_threshold_unreachable")
        return cls(
            enabled=enabled,
            enabled_domain_ids=requested,
            rewrite_max_candidates=_integer(env, "AGENT_KNOWLEDGE_REWRITE_MAX_CANDIDATES", 3, 1, 3),
            allow_original_fallback=_boolean(env, "AGENT_KNOWLEDGE_ALLOW_ORIGINAL_FALLBACK", True),
            max_retrieval_query_chars=_integer(env, "AGENT_KNOWLEDGE_MAX_RETRIEVAL_QUERY_CHARS", 1024, 128, 1024),
            per_path_candidate_limit=per_path,
            min_partial_candidates=partial,
            rewrite_timeout_ms=_integer(env, "AGENT_KNOWLEDGE_REWRITE_TIMEOUT_MS", 8000, 1000, 8000),
            retrieval_timeout_ms=_integer(env, "AGENT_KNOWLEDGE_RETRIEVAL_TIMEOUT_MS", 20000, 3000, 20000),
            evidence_timeout_ms=_integer(env, "AGENT_KNOWLEDGE_EVIDENCE_TIMEOUT_MS", 15000, 3000, 15000),
        )
