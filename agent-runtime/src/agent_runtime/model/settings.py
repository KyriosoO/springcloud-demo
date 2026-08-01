from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, Self


class ModelProvider(StrEnum):
    STUB = "stub"
    DEEPSEEK = "deepseek"


class ModelApiKey:
    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("model.api_key_required")
        self._value = value

    def reveal_for_authorization_header(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "<redacted>"

    __str__ = __repr__

    def __hash__(self) -> int:
        raise TypeError("unhashable type: ModelApiKey")


def _parse_integer(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"model.settings_invalid:{key}") from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelSettings:
    provider: ModelProvider = ModelProvider.STUB
    api_key: ModelApiKey | None = None
    max_concurrency: int = 4
    action_timeout_ms: int = 8000
    answer_timeout_ms: int = 15000
    max_request_bytes: int = 131072
    max_response_bytes: int = 262144

    BASE_URL = "https://api.deepseek.com"
    MODEL_NAME = "deepseek-v4-pro"

    def __post_init__(self) -> None:
        ranges = {
            "max_concurrency": (self.max_concurrency, 1, 8),
            "action_timeout_ms": (self.action_timeout_ms, 1000, 15000),
            "answer_timeout_ms": (self.answer_timeout_ms, 3000, 30000),
            "max_request_bytes": (self.max_request_bytes, 65536, 262144),
            "max_response_bytes": (self.max_response_bytes, 16384, 524288),
        }
        for name, (value, minimum, maximum) in ranges.items():
            if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
                raise ValueError(f"model.settings_invalid:{name}")
        if self.provider is ModelProvider.STUB and self.api_key is not None:
            raise ValueError("model.stub_api_key_forbidden")
        if self.provider is ModelProvider.DEEPSEEK and not isinstance(self.api_key, ModelApiKey):
            raise ValueError("model.api_key_required")

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Self:
        raw_provider = env.get("AGENT_MODEL_PROVIDER", ModelProvider.STUB.value)
        try:
            provider = ModelProvider(raw_provider)
        except ValueError as exc:
            raise ValueError("model.settings_invalid:AGENT_MODEL_PROVIDER") from exc
        api_key = None
        if provider is ModelProvider.DEEPSEEK:
            api_key = ModelApiKey(env.get("LLM_API_KEY", ""))
        return cls(
            provider=provider,
            api_key=api_key,
            max_concurrency=_parse_integer(env, "AGENT_MODEL_MAX_CONCURRENCY", 4),
            action_timeout_ms=_parse_integer(env, "AGENT_MODEL_ACTION_TIMEOUT_MS", 8000),
            answer_timeout_ms=_parse_integer(env, "AGENT_MODEL_ANSWER_TIMEOUT_MS", 15000),
            max_request_bytes=_parse_integer(env, "AGENT_MODEL_MAX_REQUEST_BYTES", 131072),
            max_response_bytes=_parse_integer(env, "AGENT_MODEL_MAX_RESPONSE_BYTES", 262144),
        )

