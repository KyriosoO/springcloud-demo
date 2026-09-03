from __future__ import annotations

import hashlib
import json
import os
import unicodedata
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from .errors import ContractError, StateConflict

ModelT = TypeVar("ModelT", bound=BaseModel)


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_loads(raw: str) -> Any:
    try:
        value = json.loads(raw, object_pairs_hook=_pairs_no_duplicates)
    except (json.JSONDecodeError, ContractError) as exc:
        raise ContractError(f"invalid JSON: {exc}") from exc
    if _has_non_nfc(value):
        raise ContractError("JSON strings and keys must be NFC")
    return value


def _has_non_nfc(value: Any) -> bool:
    if isinstance(value, str):
        return value != unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return any(_has_non_nfc(item) for item in value)
    if isinstance(value, dict):
        return any(_has_non_nfc(key) or _has_non_nfc(item) for key, item in value.items())
    return False


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_model(path: Path, model: type[ModelT]) -> ModelT:
    raw = path.read_text(encoding="utf-8")
    strict_loads(raw)
    return model.model_validate_json(raw, strict=True)


def load_jsonl(path: Path, model: type[ModelT]) -> tuple[ModelT, ...]:
    items: list[ModelT] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            raise ContractError(f"blank JSONL line: {number}")
        try:
            strict_loads(line)
            items.append(model.model_validate_json(line, strict=True))
        except Exception as exc:
            raise ContractError(f"invalid JSONL line {number}: {exc}") from exc
    return tuple(items)


def exclusive_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise StateConflict(f"refusing to overwrite: {path}") from exc
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


def write_model(path: Path, value: BaseModel) -> None:
    exclusive_write(path, canonical_bytes(value.model_dump(mode="json")))


def write_jsonl(path: Path, values: Iterable[BaseModel]) -> None:
    raw = b"".join(canonical_bytes(value.model_dump(mode="json")) for value in values)
    exclusive_write(path, raw)
