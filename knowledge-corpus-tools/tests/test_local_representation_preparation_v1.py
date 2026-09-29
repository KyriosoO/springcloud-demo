from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path
import httpx
import pytest

from knowledge_corpus_tools.local_representation_preparation_v1 import (
    LocalRepresentationVectorPreparationV1,
)
from knowledge_corpus_tools.local_vector_preparation import PreparationError, _TOKENS
from knowledge_corpus_tools.rechunk_candidate_v1 import (
    CandidateSpec, RechunkCandidateError, RepresentationScopeV1,
    build_rechunk_candidate_v1,
)
from knowledge_corpus_tools.retrieval_representation_v2 import (
    RetrievalRepresentationV2, build_retrieval_representation_v2,
)
from knowledge_corpus_tools.tokenizer_preflight_v2 import (
    LocalBgeTokenizerPreflightV2, _TOKENIZER_COUNT,
)
from knowledge_corpus_tools.vector_candidate import canonical_bytes

from test_rechunk_candidate_v1 import FakeES, REP_TARGET
from test_tokenizer_preflight_v2 import FakeTokenizerProcess


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class FakeModel(FakeTokenizerProcess):
    def __init__(self) -> None:
        super().__init__()
        self.second_count: int | None = None
        self.drift_at_inspect: int | None = None
        self.embedding_requests: list[httpx.Request] = []
        self.embedding_mode = "normal"

    def __call__(self, command: list[str], payload: bytes) -> bytes:
        if command[-1] == _TOKENS:
            self.commands.append(command)
            texts = json.loads(payload)["texts"]
            assert texts == self.expected_texts
            return json.dumps([self.count if self.second_count is None
                               else self.second_count] * len(texts)).encode()
        raw = super().__call__(command, payload)
        if (command[1] == "inspect" and self.drift_at_inspect is not None
                and self.inspect_calls >= self.drift_at_inspect):
            identity = json.loads(raw)
            identity["image"] = "sha256:" + "e" * 64
            return json.dumps(identity).encode()
        return raw

    def embed(self, request: httpx.Request) -> httpx.Response:
        self.embedding_requests.append(request)
        assert str(request.url) == "http://127.0.0.1:8908/embed"
        texts = json.loads(request.content)["texts"]
        previous = sum(len(json.loads(earlier.content)["texts"])
                       for earlier in self.embedding_requests[:-1])
        assert texts == self.expected_texts[previous:previous + len(texts)]
        assert 1 <= len(texts) <= 32
        if self.embedding_mode == "timeout":
            raise httpx.ReadTimeout("private response", request=request)
        if self.embedding_mode == "invalid":
            return httpx.Response(200, json={"dim": 1024, "vectors": [[True] * 1024]})
        return httpx.Response(200, json={"dim": 1024,
                                         "vectors": [[0.25] * 1024] * len(texts)})


def prepared_scope(tmp_path: Path) -> tuple[FakeES, FakeModel, CandidateSpec,
                                            RetrievalRepresentationV2]:
    es = FakeES("f" * 64, target=REP_TARGET)
    model = FakeModel()
    body = es.source["old-1"]["content"]
    item = build_retrieval_representation_v2(body=body, kind="body-only-v2")
    model.expected_texts = [body]
    current = {"container": copy.deepcopy(model.identity), "model": copy.deepcopy(model.model)}
    baseline = copy.deepcopy(current)
    baseline["container"]["started"] = "2026-09-07T00:48:23.858361985Z"
    es.source["old-1"]["vectorModelSnapshotSha256"] = sha(canonical_bytes(baseline))
    tokenizer_files = {name: model.model["files"][name]["sha256"] for name in (
        "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
        "sentencepiece.bpe.model",
    )}
    tokenizer_sha = sha(json.dumps(tokenizer_files, sort_keys=True,
                                   separators=(",", ":")).encode())
    binding = sha(canonical_bytes([["old-1", item.version,
                                    item.input_sha256, item.body_sha256]]))
    base = es.spec(tmp_path, mode="representation", representation_binding=binding)
    spec = replace(
        base, baseline_model_snapshot=canonical_bytes(baseline),
        baseline_model_snapshot_sha256=sha(canonical_bytes(baseline)),
        model_snapshot=canonical_bytes(current),
        model_snapshot_sha256=sha(canonical_bytes(current)),
        tokenizer_sha256=tokenizer_sha,
    )
    return es, model, spec, item


def adapter(spec: CandidateSpec, model: FakeModel) -> LocalRepresentationVectorPreparationV1:
    return LocalRepresentationVectorPreparationV1(
        spec, container=model.identity["id"], process=model,
        transport=httpx.MockTransport(model.embed),
    )


def test_real_path_adapter_binds_preflight_and_builds_fake_candidate(tmp_path: Path) -> None:
    es, model, spec, item = prepared_scope(tmp_path)
    source_before = copy.deepcopy(es.source)
    with es.client() as client:
        result = build_rechunk_candidate_v1(
            spec, client=client, prepare_vectors=adapter(spec, model),
            representations=(item,),
        )
    assert result.updated_count == 1 and result.embedding_requests == 1
    assert es.source == source_before
    assert es.candidate is not None
    changed = es.candidate["old-1"]
    assert changed["vectorRepresentationVersion"] == "body-only-v2"
    assert changed["vectorInputSha256"] == item.input_sha256
    assert changed["vectorBodySha256"] == item.body_sha256
    assert changed["vectorModelSnapshotSha256"] == spec.model_snapshot_sha256
    assert changed["embedding"] == [0.25] * 1024
    assert len(model.embedding_requests) == 1
    assert sum(command[-1] == _TOKENIZER_COUNT for command in model.commands) == 1
    assert sum(command[-1] == _TOKENS for command in model.commands) == 1
    assert model.inspect_calls == 5


def test_prepared_result_exactly_matches_real_preflight(tmp_path: Path) -> None:
    _, model, spec, item = prepared_scope(tmp_path)
    prepare = adapter(spec, model)
    result = prepare((item,))
    assert result.input_sha256 == (item.input_sha256,)
    assert result.body_sha256 == (item.body_sha256,)
    assert result.representation_versions == ("body-only-v2",)
    assert result.token_counts == (1024,)
    assert result.max_input_tokens == 1024
    assert result.model_snapshot_sha256 == spec.model_snapshot_sha256
    assert result.tokenizer_sha256 == spec.tokenizer_sha256
    assert result.embedding_requests == 1
    with pytest.raises(PreparationError, match="^already_consumed$"):
        prepare((item,))
    assert len(model.embedding_requests) == 1


def test_two_batch_request_count_is_exact_and_bounded(tmp_path: Path) -> None:
    _, model, base, item = prepared_scope(tmp_path)
    identifiers = tuple(f"old-{n}" for n in range(33))
    original_scope = base.representation_scope[0]
    scopes = tuple(RepresentationScopeV1(
        identifier, original_scope.document_id, original_scope.parent_document_id,
        original_scope.asset_id, original_scope.asset_version,
    ) for identifier in identifiers)
    binding = sha(canonical_bytes([[identifier, item.version,
                                    item.input_sha256, item.body_sha256]
                                   for identifier in identifiers]))
    spec = replace(base, update_ids=identifiers, representation_scope=scopes,
                   representation_binding_sha256=binding,
                   max_embedding_requests=2)
    model.expected_texts = [item.text] * 33
    result = adapter(spec, model)((item,) * 33)
    assert result.embedding_requests == 2
    assert len(result.vectors) == 33
    assert [len(json.loads(request.content)["texts"])
            for request in model.embedding_requests] == [32, 1]


def test_wrong_frozen_request_budget_stops_before_tokenizer(tmp_path: Path) -> None:
    _, model, spec, item = prepared_scope(tmp_path)
    spec = replace(spec, max_embedding_requests=2)
    with pytest.raises(PreparationError, match="^input_invalid$"):
        adapter(spec, model)((item,))
    assert model.commands == [] and model.embedding_requests == []


@pytest.mark.parametrize("failure", [
    "binding", "tokenizer", "model", "tokens_exceeded", "tokens_changed",
    "identity_changed", "identity_changed_after", "invalid_response", "timeout",
])
def test_failed_preparation_is_finite_and_never_builds_candidate(
    tmp_path: Path, failure: str,
) -> None:
    es, model, spec, item = prepared_scope(tmp_path)
    if failure == "binding":
        spec = replace(spec, representation_binding_sha256="0" * 64)
    elif failure == "tokenizer":
        spec = replace(spec, tokenizer_sha256="0" * 64)
    elif failure == "model":
        current = json.loads(spec.model_snapshot)
        current["container"]["started"] = "2026-09-29T00:00:00Z"
        spec = replace(spec, model_snapshot=canonical_bytes(current),
                       model_snapshot_sha256=sha(canonical_bytes(current)))
    elif failure == "tokens_exceeded":
        model.count = 1025
    elif failure == "tokens_changed":
        model.second_count = 1023
    elif failure == "identity_changed":
        model.drift_at_inspect = 3
    elif failure == "identity_changed_after":
        model.drift_at_inspect = 5
    elif failure == "invalid_response":
        model.embedding_mode = "invalid"
    else:
        model.embedding_mode = "timeout"
    with es.client() as client:
        with pytest.raises(RechunkCandidateError) as caught:
            build_rechunk_candidate_v1(
                spec, client=client, prepare_vectors=adapter(spec, model),
                representations=(item,),
            )
    assert "第一条 旧资料内容。" not in str(caught.value)
    assert es.candidate is None
    assert not any(path.endswith("_clone/" + spec.candidate_index) for _, path in es.calls)
    assert len(model.embedding_requests) == (1 if failure in {
        "identity_changed_after", "invalid_response", "timeout",
    } else 0)


@pytest.mark.parametrize("changed", [
    {"input_sha256": ("0" * 64,)},
    {"body_sha256": ("0" * 64,)},
    {"representation_versions": ("other",)},
    {"model_snapshot_sha256": "0" * 64},
    {"tokenizer_sha256": "0" * 64},
    {"max_input_tokens": 1},
    {"input_token_counts": (1023,)},
])
def test_forged_preflight_result_cannot_authorize_embedding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed: dict[str, object],
) -> None:
    _, model, spec, item = prepared_scope(tmp_path)
    genuine = LocalBgeTokenizerPreflightV2(model.identity["id"], process=model).check((item,))
    model.commands.clear()
    monkeypatch.setattr(LocalBgeTokenizerPreflightV2, "check",
                        lambda self, values: replace(genuine, **changed))
    with pytest.raises(PreparationError):
        adapter(spec, model)((item,))
    assert model.embedding_requests == []


def test_local_v1_path_still_rejects_v2_without_explicit_preflight(tmp_path: Path) -> None:
    from knowledge_corpus_tools.local_vector_preparation import LocalVectorPreparation

    _, model, _, item = prepared_scope(tmp_path)
    old = LocalVectorPreparation(model.identity["id"], process=model,
                                 transport=httpx.MockTransport(model.embed))
    old.freeze()
    with pytest.raises(PreparationError, match="^input_invalid$"):
        old((item,))  # type: ignore[arg-type]
    assert model.embedding_requests == []
