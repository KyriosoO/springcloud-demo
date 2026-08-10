from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping

from agent_runtime.capability_api.contracts import (
    CapabilityDescriptor,
    JsonObject,
    canonical_json_bytes,
    freeze_json_object,
)


UNSUPPORTED_CAPABILITY_ID = "agent_unsupported"
MODEL_CATALOG_TEXT_POLICY_VERSION = "model-catalog-text-v1"

_CAPABILITY_ID = re.compile(r"[a-z][a-z0-9_-]*(\.[a-z][a-z0-9_-]*)+")
_SNAKE_CASE_NAME = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_CAMEL_CASE_NAME = re.compile(r"\b[a-z]+(?:[A-Z][A-Za-z0-9]*)+\b")
_URI_OR_HOST = re.compile(r"(?i)(?:\b[a-z][a-z0-9+.-]*://|\bwww\.|\blocalhost\b|\b\d{1,3}(?:\.\d{1,3}){3}\b)")
_AUTH_OR_SECRET = re.compile(
    r"(?i)(?:\brole(?:_[a-z0-9_]+)?\b|\bauthorit(?:y|ies)\b|\badmin\b|\bviewer\b|"
    r"\bjwt\b|\bbearer\b|\bapi[_ -]?key\b|\bsecret\b|\bpassword\b|\bcredential\b|\btoken\b|"
    r"\bsk-[a-z0-9_-]+\b)"
)
_PHYSICAL_OR_DSL = re.compile(
    r"(?i)(?:\belasticsearch\b|\bindex\b|\balias\b|\bcluster\b|\bdatabase\b|\btable\b|"
    r"\bendpoint\b|\bhost\b|\bport\b|\burl\b|\buri\b|\bsql\b|\bdsl\b|"
    r"\b[A-Z][A-Za-z0-9]*(?:Controller|Service|Repository|Client|Class)\b|"
    r"\b[a-z_][a-z0-9_]*\s*\()"
)
_CONCRETE_IDENTIFIER = re.compile(
    r"(?i)(?:\b\d{6,}\b|\b[0-9a-f]{8}-[0-9a-f-]{27,36}\b|\b[a-z]{1,8}-\d{3,}\b)"
)
_CONCRETE_AMOUNT = re.compile(
    r"(?i)(?:(?:[$¥￥]|\b(?:cny|usd)\b)\s*\d|\d+(?:\.\d+)?\s*(?:元|美元|人民币))"
)


class InvalidCapabilityCatalog(ValueError):
    """Raised when model-visible descriptor metadata is not safe to project."""

    def __init__(self) -> None:
        super().__init__("model.invalid_capability_catalog")


def _catalog_text(value: object, *, max_chars: int) -> str:
    if not isinstance(value, str):
        raise InvalidCapabilityCatalog
    normalized = unicodedata.normalize("NFC", value)
    if (
        not normalized
        or normalized != normalized.strip()
        or len(normalized) > max_chars
        or any(unicodedata.category(character) in {"Cc", "Cf"} for character in normalized)
        or _URI_OR_HOST.search(normalized)
        or _AUTH_OR_SECRET.search(normalized)
        or _PHYSICAL_OR_DSL.search(normalized)
        or _SNAKE_CASE_NAME.search(normalized)
        or _CAMEL_CASE_NAME.search(normalized)
        or _CONCRETE_IDENTIFIER.search(normalized)
        or _CONCRETE_AMOUNT.search(normalized)
    ):
        raise InvalidCapabilityCatalog
    return normalized


def project_capability_catalog(
    descriptors: tuple[CapabilityDescriptor, ...],
) -> JsonObject:
    if not 1 <= len(descriptors) <= 32:
        raise InvalidCapabilityCatalog
    if any(not isinstance(descriptor, CapabilityDescriptor) for descriptor in descriptors):
        raise InvalidCapabilityCatalog

    seen_capability_ids: set[str] = set()
    seen_aliases: set[str] = set()
    entries: list[JsonObject] = []
    for descriptor in sorted(descriptors, key=lambda item: item.capability_id):
        capability_id = descriptor.capability_id
        if (
            capability_id == UNSUPPORTED_CAPABILITY_ID
            or len(capability_id) > 80
            or not _CAPABILITY_ID.fullmatch(capability_id)
            or capability_id in seen_capability_ids
        ):
            raise InvalidCapabilityCatalog
        seen_capability_ids.add(capability_id)

        aliases = tuple(sorted({_catalog_text(alias, max_chars=64) for alias in descriptor.aliases}))
        if len(aliases) != len(descriptor.aliases) or len(aliases) > 8:
            raise InvalidCapabilityCatalog
        if any(alias in seen_aliases for alias in aliases):
            raise InvalidCapabilityCatalog
        seen_aliases.update(aliases)
        entries.append(
            {
                "capability_id": capability_id,
                "display_name": _catalog_text(descriptor.display_name, max_chars=80),
                "description": _catalog_text(descriptor.description, max_chars=512),
                "aliases": aliases,
            }
        )

    entries.append(
        {
            "capability_id": UNSUPPORTED_CAPABILITY_ID,
            "display_name": "Unsupported",
            "description": "当前能力目录不能处理该问题",
            "aliases": (),
        }
    )
    try:
        catalog = freeze_json_object(
            {"capabilities": tuple(entries)},
            max_bytes=65536,
            max_depth=8,
            max_collection_items=512,
        )
    except ValueError as exc:
        raise InvalidCapabilityCatalog from exc
    if len(canonical_json_bytes(catalog)) > 65536:
        raise InvalidCapabilityCatalog
    return catalog


def capability_ids_from_catalog(catalog: JsonObject) -> frozenset[str]:
    raw_entries = catalog.get("capabilities")
    if not isinstance(raw_entries, tuple):
        raise InvalidCapabilityCatalog
    identifiers: set[str] = set()
    for entry in raw_entries:
        if not isinstance(entry, Mapping):
            raise InvalidCapabilityCatalog
        capability_id = entry.get("capability_id")
        if not isinstance(capability_id, str) or capability_id in identifiers:
            raise InvalidCapabilityCatalog
        identifiers.add(capability_id)
    if UNSUPPORTED_CAPABILITY_ID not in identifiers:
        raise InvalidCapabilityCatalog
    return frozenset(identifiers)
