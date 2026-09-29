"""Local, tokenizer-only length admission for versioned embedding inputs.

No embedding HTTP request is made here.  The existing local-model identity
probe binds the tokenizer bytes, service source and model snapshot before and
after counting with the container's actual tokenizer.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .errors import ContractError
from .local_vector_preparation import (
    LocalVectorPreparation,
    PreparationError,
    run_process,
)
from .retrieval_representation_v2 import (
    MAX_BODY_CODE_POINTS, MAX_INPUT_BYTES, MAX_METADATA_CODE_POINTS,
    RetrievalRepresentationV2,
)

_TOKENIZER_FILES = (
    "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
    "sentencepiece.bpe.model",
)
_TOKENIZER_COUNT = r'''
import json, os, pathlib, sys
os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", TOKENIZERS_PARALLELISM="false")
payload = json.load(sys.stdin)
root = pathlib.Path("/root/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots") / payload["revision"]
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained(str(root), local_files_only=True, trust_remote_code=False)
values = tokenizer(payload["texts"], add_special_tokens=True, truncation=False, padding=False)["input_ids"]
print(json.dumps({"max_length": tokenizer.model_max_length, "counts": [len(value) for value in values]}))
'''


@dataclass(frozen=True, slots=True)
class TokenizerPreflightResultV2:
    model_repository: str
    model_revision: str
    model_snapshot_sha256: str
    tokenizer_sha256: str
    service_sha256: str
    max_input_tokens: int
    input_token_counts: tuple[int, ...]
    input_sha256: tuple[str, ...]
    body_sha256: tuple[str, ...]
    representation_versions: tuple[str, ...]
    classification_enriched: tuple[bool, ...]


class TokenizerPreflightError(ContractError):
    def __init__(self, reason: str):
        self.reason = reason if reason in {
            "identity_invalid", "identity_changed", "input_invalid",
            "tokens_invalid", "tokens_exceeded", "process_failed",
        } else "identity_invalid"
        super().__init__(self.reason)


class LocalBgeTokenizerPreflightV2:
    """A one-use, no-network tokenizer check against the running BGE-M3 image."""

    def __init__(
        self, container: str, *,
        process: Callable[[list[str], bytes], bytes] = run_process,
    ) -> None:
        self._identity = LocalVectorPreparation(container, process=process)
        self._process = process
        self._consumed = False

    def _check(self, items: tuple[RetrievalRepresentationV2, ...]) -> TokenizerPreflightResultV2:
        if self._consumed:
            raise TokenizerPreflightError("input_invalid")
        self._consumed = True
        if (type(items) is not tuple or not 1 <= len(items) <= 1000
                or any(type(item) is not RetrievalRepresentationV2 for item in items)
                or any(not self._input_valid(item) for item in items)):
            raise TokenizerPreflightError("input_invalid")
        before = self._identity.freeze()
        model = before["model"]
        payload = json.dumps({
            "revision": model["revision"], "texts": [item.text for item in items],
        }, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        raw = self._process([
            "docker", "exec", "-i", self._identity.container, "python", "-B", "-c", _TOKENIZER_COUNT,
        ], payload)
        try:
            result: Any = json.loads(raw)
        except (ValueError, UnicodeError):
            raise TokenizerPreflightError("tokens_invalid") from None
        if (type(result) is not dict or set(result) != {"max_length", "counts"}
                or type(result["max_length"]) is not int
                or not 1 <= result["max_length"] <= 1_000_000):
            raise TokenizerPreflightError("tokens_invalid")
        counts = result["counts"]
        if (type(counts) is not list or len(counts) != len(items)
                or any(type(value) is not int or value < 1 for value in counts)):
            raise TokenizerPreflightError("tokens_invalid")
        if self._identity.snapshot() != before:
            raise TokenizerPreflightError("identity_changed")
        effective_window = min(model["max_length"], result["max_length"])
        if max(counts) > effective_window:
            raise TokenizerPreflightError("tokens_exceeded")
        tokenizer_files = {
            name: model["files"][name]["sha256"] for name in _TOKENIZER_FILES
        }
        if any(not re.fullmatch(r"[a-f0-9]{64}", value) for value in tokenizer_files.values()):
            raise TokenizerPreflightError("identity_invalid")
        tokenizer = hashlib.sha256(json.dumps(
            tokenizer_files, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        return TokenizerPreflightResultV2(
            model_repository="BAAI/bge-m3",
            model_revision=model["revision"],
            model_snapshot_sha256=self._identity.snapshot_sha256,
            tokenizer_sha256=tokenizer,
            service_sha256=model["service"]["sha256"],
            max_input_tokens=effective_window,
            input_token_counts=tuple(counts),
            input_sha256=tuple(item.input_sha256 for item in items),
            body_sha256=tuple(item.body_sha256 for item in items),
            representation_versions=tuple(item.version for item in items),
            classification_enriched=tuple(item.classification_enriched for item in items),
        )

    @staticmethod
    def _input_valid(item: RetrievalRepresentationV2) -> bool:
        if (type(item.text) is not str or "\x00" in item.text
                or type(item.input_sha256) is not str
                or type(item.body_sha256) is not str
                or type(item.input_code_points) is not int
                or type(item.input_bytes) is not int
                or not 1 <= item.input_code_points <= MAX_BODY_CODE_POINTS + MAX_METADATA_CODE_POINTS
                or not 1 <= item.input_bytes <= MAX_INPUT_BYTES
                or item.version not in (
                    "body-only-v2", "trusted-title-section-body-v2",
                    "trusted-classification-body-v2",
                )
                or type(item.classification_enriched) is not bool
                or (item.version != "trusted-classification-body-v2"
                    and item.classification_enriched)
                or re.fullmatch(r"[a-f0-9]{64}", item.body_sha256) is None):
            return False
        try:
            encoded = item.text.encode("utf-8")
        except UnicodeEncodeError:
            return False
        return (
            len(item.text) == item.input_code_points
            and len(encoded) == item.input_bytes
            and hashlib.sha256(encoded).hexdigest() == item.input_sha256
            and (item.version != "body-only-v2" or (
                item.input_code_points <= MAX_BODY_CODE_POINTS
                and hashlib.sha256(encoded).hexdigest() == item.body_sha256
            ))
        )

    def check(self, items: tuple[RetrievalRepresentationV2, ...]) -> TokenizerPreflightResultV2:
        reason = "process_failed"
        try:
            return self._check(items)
        except TokenizerPreflightError as error:
            reason = error.reason
        except PreparationError as error:
            reason = error.reason if error.reason in {
                "identity_invalid", "identity_changed", "process_failed",
            } else "identity_invalid"
        except Exception:
            pass
        # Raise outside the handler: no provider/model text in exception context.
        raise TokenizerPreflightError(reason)
