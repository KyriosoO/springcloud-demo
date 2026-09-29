from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from knowledge_corpus_tools.local_vector_preparation import MODEL_FILES, SERVICE_SHA, _PROBE
from knowledge_corpus_tools.normalization_v2 import MetadataV2, asserted_field
from knowledge_corpus_tools.retrieval_representation_v2 import build_retrieval_representation_v2
from knowledge_corpus_tools.tokenizer_preflight_v2 import (
    LocalBgeTokenizerPreflightV2,
    TokenizerPreflightError,
    _TOKENIZER_COUNT,
)


CONTAINER = "a" * 64
BODY = "测试原文"
ITEM = build_retrieval_representation_v2(body=BODY, kind="body-only-v2")


class FakeTokenizerProcess:
    def __init__(self) -> None:
        digest = {"bytes": 1, "sha256": "c" * 64}
        self.identity: dict[str, Any] = {
            "id": CONTAINER, "image": "sha256:" + "b" * 64,
            "started": "2026-09-28T09:59:52.377452626Z", "running": True,
            "path": "python", "args": ["-m", "uvicorn", "embedding_server:app",
                                    "--host", "0.0.0.0", "--port", "8908"],
            "ports": {"8908/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8908"}]},
        }
        self.model: dict[str, Any] = {
            "revision": "d" * 40, "max_length": 1024,
            "cache_provenance": "single_snapshot_predates_start",
            "service": {"bytes": 1, "sha256": SERVICE_SHA},
            "implementation": digest.copy(),
            "files": {name: digest.copy() for name in MODEL_FILES},
            "packages": {"FlagEmbedding": "1.4.0", "transformers": "5.9.0", "torch": "2.6.0+cu124"},
        }
        self.count: Any = 1024
        self.tokenizer_window: Any = 8192
        self.expected_texts = [BODY]
        self.commands: list[list[str]] = []
        self.inspect_calls = 0
        self.change_after_count = False

    def __call__(self, command: list[str], payload: bytes) -> bytes:
        self.commands.append(command)
        if command[1] == "inspect":
            self.inspect_calls += 1
            result = copy.deepcopy(self.identity)
            if self.change_after_count and self.inspect_calls == 2:
                result["image"] = "sha256:" + "e" * 64
        elif command[-1] == _PROBE:
            assert "texts" not in json.loads(payload)
            result = copy.deepcopy(self.model)
        else:
            assert command[-1] == _TOKENIZER_COUNT
            data = json.loads(payload)
            assert data == {"revision": "d" * 40, "texts": self.expected_texts}
            result = {"max_length": self.tokenizer_window,
                      "counts": [self.count] * len(self.expected_texts)}
        return json.dumps(result).encode()


def test_real_tokenizer_path_is_bound_and_no_embedding_http_is_called() -> None:
    fake = FakeTokenizerProcess()
    result = LocalBgeTokenizerPreflightV2(CONTAINER, process=fake).check((ITEM,))
    assert result.model_repository == "BAAI/bge-m3"
    assert result.model_revision == "d" * 40
    tokenizer_files = {name: "c" * 64 for name in (
        "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
        "sentencepiece.bpe.model",
    )}
    assert result.tokenizer_sha256 == hashlib.sha256(json.dumps(
        tokenizer_files, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    assert result.service_sha256 == SERVICE_SHA
    assert result.max_input_tokens == 1024
    assert result.input_token_counts == (1024,)
    assert result.input_sha256 == (ITEM.input_sha256,)
    assert result.body_sha256 == (ITEM.body_sha256,)
    assert result.representation_versions == ("body-only-v2",)
    assert result.classification_enriched == (False,)
    assert len(result.model_snapshot_sha256) == 64
    assert fake.inspect_calls == 2
    assert all(command[:2] == ["docker", "inspect"] or command[:2] == ["docker", "exec"]
               for command in fake.commands)
    assert not any(command[-1] == "/embed" for command in fake.commands)


def test_exceeding_service_window_fails_without_model_inference() -> None:
    fake = FakeTokenizerProcess()
    fake.count = 1025
    with pytest.raises(TokenizerPreflightError, match="^tokens_exceeded$"):
        LocalBgeTokenizerPreflightV2(CONTAINER, process=fake).check((ITEM,))
    assert len([command for command in fake.commands if command[-1] == _TOKENIZER_COUNT]) == 1


def test_smaller_tokenizer_window_is_effective_limit() -> None:
    fake = FakeTokenizerProcess()
    fake.tokenizer_window = 512
    fake.count = 513
    with pytest.raises(TokenizerPreflightError, match="^tokens_exceeded$"):
        LocalBgeTokenizerPreflightV2(CONTAINER, process=fake).check((ITEM,))


def test_classification_overhead_is_counted_in_complete_input() -> None:
    metadata = MetadataV2.model_validate({"taxTypes": asserted_field(
        ("增值税",), origin="source", source_ref="raw:taxTypes",
        observed_at=datetime(2026, 9, 29, tzinfo=UTC),
    )})
    enriched = build_retrieval_representation_v2(
        body=BODY, kind="trusted-classification-body-v2", classification=metadata,
    )
    fake = FakeTokenizerProcess()
    fake.expected_texts = [enriched.text]
    fake.count = 1025
    with pytest.raises(TokenizerPreflightError, match="^tokens_exceeded$"):
        LocalBgeTokenizerPreflightV2(CONTAINER, process=fake).check((enriched,))
    assert fake.expected_texts[0] == BODY + "\n税种：增值税"
    accepted = FakeTokenizerProcess()
    accepted.expected_texts = [enriched.text]
    accepted.count = 16
    result = LocalBgeTokenizerPreflightV2(CONTAINER, process=accepted).check((enriched,))
    assert result.classification_enriched == (True,)
    assert result.input_sha256 == (enriched.input_sha256,)


@pytest.mark.parametrize("bad", [True, 0, -1, "8192", None])
def test_missing_or_invalid_tokenizer_window_fails_closed(bad: Any) -> None:
    fake = FakeTokenizerProcess()
    fake.tokenizer_window = bad
    with pytest.raises(TokenizerPreflightError, match="^tokens_invalid$"):
        LocalBgeTokenizerPreflightV2(CONTAINER, process=fake).check((ITEM,))


@pytest.mark.parametrize("bad", [True, 0, -1, "1024", None])
def test_invalid_token_count_fails_closed(bad: Any) -> None:
    fake = FakeTokenizerProcess()
    fake.count = bad
    with pytest.raises(TokenizerPreflightError, match="^tokens_invalid$"):
        LocalBgeTokenizerPreflightV2(CONTAINER, process=fake).check((ITEM,))


def test_snapshot_drift_fails_closed() -> None:
    fake = FakeTokenizerProcess()
    fake.change_after_count = True
    with pytest.raises(TokenizerPreflightError, match="^identity_changed$"):
        LocalBgeTokenizerPreflightV2(CONTAINER, process=fake).check((ITEM,))


def test_forged_input_hash_fails_before_tokenizer() -> None:
    fake = FakeTokenizerProcess()
    forged = replace(ITEM, input_sha256="0" * 64)
    with pytest.raises(TokenizerPreflightError, match="^input_invalid$"):
        LocalBgeTokenizerPreflightV2(CONTAINER, process=fake).check((forged,))
    assert fake.commands == []


def test_rehashed_oversized_input_fails_before_tokenizer() -> None:
    fake = FakeTokenizerProcess()
    text = "x" * 16385
    forged = replace(ITEM, text=text, input_code_points=len(text),
                     input_bytes=len(text), input_sha256=hashlib.sha256(text.encode()).hexdigest())
    with pytest.raises(TokenizerPreflightError, match="^input_invalid$"):
        LocalBgeTokenizerPreflightV2(CONTAINER, process=fake).check((forged,))
    assert fake.commands == []


def test_forged_body_only_hash_fails_before_tokenizer() -> None:
    fake = FakeTokenizerProcess()
    forged = replace(ITEM, body_sha256="a" * 64)
    with pytest.raises(TokenizerPreflightError, match="^input_invalid$"):
        LocalBgeTokenizerPreflightV2(CONTAINER, process=fake).check((forged,))
    assert fake.commands == []


@pytest.mark.parametrize("change", [
    {"input_bytes": 1}, {"body_sha256": "not-a-hash"},
    {"text": "原文\ud800"}, {"version": "legacy_unknown"},
])
def test_forged_input_contract_fails_before_tokenizer(change: dict[str, Any]) -> None:
    fake = FakeTokenizerProcess()
    forged = replace(ITEM, **change)
    with pytest.raises(TokenizerPreflightError, match="^input_invalid$"):
        LocalBgeTokenizerPreflightV2(CONTAINER, process=fake).check((forged,))
    assert fake.commands == []


def test_instance_is_one_use_and_errors_do_not_retain_original_text() -> None:
    fake = FakeTokenizerProcess()
    checker = LocalBgeTokenizerPreflightV2(CONTAINER, process=fake)
    checker.check((ITEM,))
    with pytest.raises(TokenizerPreflightError) as caught:
        checker.check((ITEM,))
    assert str(caught.value) == "input_invalid"
    assert BODY not in repr(caught.value)
    assert caught.value.__context__ is None and caught.value.__cause__ is None


def test_tokenizer_program_includes_special_tokens_and_never_truncates() -> None:
    assert "add_special_tokens=True" in _TOKENIZER_COUNT
    assert "truncation=False" in _TOKENIZER_COUNT
    assert "local_files_only=True" in _TOKENIZER_COUNT
    assert "trust_remote_code=False" in _TOKENIZER_COUNT
