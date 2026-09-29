"""One-use local BGE preparation for the representation-only candidate mode.

The tokenizer and embedding service are checked against the same frozen
container snapshot. No text, vector or provider response is persisted here.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import cast

import httpx

from .local_vector_preparation import LocalVectorPreparation, PreparationError, run_process
from .rechunk_candidate_v1 import CandidateSpec, PreparedVectorsV1, Representation
from .retrieval_representation_v2 import RetrievalRepresentationV2
from .tokenizer_preflight_v2 import LocalBgeTokenizerPreflightV2, TokenizerPreflightError
from .vector_candidate import canonical_bytes


class LocalRepresentationVectorPreparationV1:
    """A preflighted callback for ``build_rechunk_candidate_v1`` representation mode."""

    def __init__(
        self, spec: CandidateSpec, *, container: str,
        process: Callable[[list[str], bytes], bytes] = run_process,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if type(spec) is not CandidateSpec or spec.mode != "representation":
            raise PreparationError("input_invalid")
        self._spec = spec
        self._container = container
        self._process = process
        self._transport = transport
        self._consumed = False

    def _prepare(self, items: tuple[Representation, ...]) -> PreparedVectorsV1:
        if self._consumed:
            raise PreparationError("already_consumed")
        self._consumed = True
        spec = self._spec
        if (type(items) is not tuple or len(items) != len(spec.update_ids)
                or any(type(item) is not RetrievalRepresentationV2
                       or item.version != "body-only-v2" for item in items)
                or (len(items) + 31) // 32 != spec.max_embedding_requests):
            raise PreparationError("input_invalid")
        v2_items = cast(tuple[RetrievalRepresentationV2, ...], items)
        binding = [[identifier, item.version, item.input_sha256, item.body_sha256]
                   for identifier, item in zip(spec.update_ids, v2_items, strict=True)]
        if hashlib.sha256(canonical_bytes(binding)).hexdigest() != spec.representation_binding_sha256:
            raise PreparationError("input_invalid")

        preflight = LocalBgeTokenizerPreflightV2(
            self._container, process=self._process,
        ).check(v2_items)
        frozen_model = json.loads(spec.model_snapshot)["model"]
        if (preflight.model_repository != "BAAI/bge-m3"
                or preflight.model_revision != frozen_model["revision"]
                or preflight.model_snapshot_sha256 != spec.model_snapshot_sha256
                or preflight.tokenizer_sha256 != spec.tokenizer_sha256
                or preflight.service_sha256 != frozen_model["service"]["sha256"]
                or preflight.input_sha256 != tuple(item.input_sha256 for item in v2_items)
                or preflight.body_sha256 != tuple(item.body_sha256 for item in v2_items)
                or preflight.representation_versions != tuple(item.version for item in v2_items)
                or preflight.classification_enriched != (False,) * len(v2_items)
                or type(preflight.max_input_tokens) is not int
                or not 1 <= preflight.max_input_tokens <= frozen_model["max_length"]
                or type(preflight.input_token_counts) is not tuple
                or len(preflight.input_token_counts) != len(items)
                or any(type(count) is not int or not 1 <= count <= preflight.max_input_tokens
                       for count in preflight.input_token_counts)):
            raise PreparationError("identity_invalid")

        preparation = LocalVectorPreparation(
            self._container, process=self._process, transport=self._transport,
        )
        snapshot = preparation.freeze()
        if (canonical_bytes(snapshot) != spec.model_snapshot
                or preparation.snapshot_sha256 != preflight.model_snapshot_sha256):
            raise PreparationError("identity_changed")
        vectors = preparation._prepare_retrieval_v2(
            v2_items, expected_token_counts=preflight.input_token_counts,
        )
        if (preparation.http_calls != spec.max_embedding_requests
                or preparation.text_count != len(items)
                or preparation.max_tokens != max(preflight.input_token_counts)):
            raise PreparationError("embedding_invalid")
        return PreparedVectorsV1(
            vectors=vectors,
            input_sha256=preflight.input_sha256,
            body_sha256=preflight.body_sha256,
            representation_versions=preflight.representation_versions,
            token_counts=preflight.input_token_counts,
            max_input_tokens=preflight.max_input_tokens,
            model_snapshot_sha256=preflight.model_snapshot_sha256,
            tokenizer_sha256=preflight.tokenizer_sha256,
            embedding_requests=preparation.http_calls,
        )

    def __call__(self, items: tuple[Representation, ...]) -> PreparedVectorsV1:
        reason = "embedding_invalid"
        try:
            return self._prepare(items)
        except (PreparationError, TokenizerPreflightError) as error:
            reason = error.reason
        except Exception:
            pass
        # Never retain a container or provider exception carrying input text.
        raise PreparationError(reason)
