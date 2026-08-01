from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from agent_runtime.capability_api.contracts import JsonObject, freeze_json_object
from agent_runtime.model.contracts import InvalidModelOutput


def _reject_constant(_: str) -> None:
    raise InvalidModelOutput("model.json_non_finite_number")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidModelOutput("model.json_duplicate_key")
        result[key] = value
    return result


def _reject_unpaired_surrogates(value: object) -> None:
    if isinstance(value, str):
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise InvalidModelOutput("model.json_invalid_unicode")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _reject_unpaired_surrogates(key)
            _reject_unpaired_surrogates(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _reject_unpaired_surrogates(item)


def parse_unique_json_object(
    raw: bytes | str,
    *,
    max_bytes: int,
    max_depth: int,
    max_items: int,
) -> JsonObject:
    if isinstance(raw, bytes):
        if len(raw) > max_bytes:
            raise InvalidModelOutput("model.json_bytes_exceeded")
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise InvalidModelOutput("model.json_invalid_utf8") from exc
    elif isinstance(raw, str):
        if len(raw.encode("utf-8")) > max_bytes:
            raise InvalidModelOutput("model.json_bytes_exceeded")
        text = raw
    else:
        raise InvalidModelOutput("model.json_type_invalid")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except InvalidModelOutput:
        raise
    except (UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise InvalidModelOutput("model.json_invalid") from exc
    if not isinstance(value, Mapping):
        raise InvalidModelOutput("model.json_object_required")
    _reject_unpaired_surrogates(value)
    try:
        return freeze_json_object(
            value,
            max_bytes=max_bytes,
            max_depth=max_depth,
            max_collection_items=max_items,
        )
    except ValueError as exc:
        raise InvalidModelOutput("model.json_invalid") from exc
