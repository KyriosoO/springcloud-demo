from __future__ import annotations

from collections.abc import Iterator, Mapping

import pytest

from agent_runtime.model.settings import ModelApiKey, ModelProvider, ModelSettings


class TrackingEnvironment(Mapping[str, str]):
    def __init__(self, **values: str) -> None:
        self._values = dict(values)
        self.read_keys: list[str] = []

    def __getitem__(self, key: str) -> str:
        self.read_keys.append(key)
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


def test_stub_mode_does_not_read_api_key() -> None:
    env = TrackingEnvironment(AGENT_MODEL_PROVIDER="stub", LLM_API_KEY="sentinel-secret")

    settings = ModelSettings.from_env(env)

    assert settings.provider is ModelProvider.STUB
    assert settings.api_key is None
    assert "LLM_API_KEY" not in env.read_keys
    assert "sentinel-secret" not in repr(settings)


def test_deepseek_mode_requires_non_empty_api_key() -> None:
    with pytest.raises(ValueError, match="model.api_key_required"):
        ModelSettings.from_env({"AGENT_MODEL_PROVIDER": "deepseek"})


def test_api_key_repr_and_str_are_redacted() -> None:
    secret = "sentinel-secret"
    key = ModelApiKey(secret)

    assert repr(key) == "<redacted>"
    assert str(key) == "<redacted>"
    assert secret not in repr(key)
    assert key.reveal_for_authorization_header() == secret
    with pytest.raises(TypeError):
        hash(key)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("AGENT_MODEL_MAX_CONCURRENCY", "0"),
        ("AGENT_MODEL_ACTION_TIMEOUT_MS", "999"),
        ("AGENT_MODEL_ANSWER_TIMEOUT_MS", "30001"),
        ("AGENT_MODEL_MAX_REQUEST_BYTES", "not-an-int"),
        ("AGENT_MODEL_MAX_RESPONSE_BYTES", "100"),
    ],
)
def test_invalid_model_settings_fail_startup(key: str, value: str) -> None:
    with pytest.raises(ValueError, match="model.settings_invalid"):
        ModelSettings.from_env({"AGENT_MODEL_PROVIDER": "stub", key: value})


def test_stub_settings_reject_accidental_secret_retention() -> None:
    with pytest.raises(ValueError, match="model.stub_api_key_forbidden"):
        ModelSettings(provider=ModelProvider.STUB, api_key=ModelApiKey("sentinel"))
