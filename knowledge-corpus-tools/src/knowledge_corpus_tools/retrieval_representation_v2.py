"""Versioned offline embedding inputs, separate from quotable chunk content.

This module has no search, model, or source-reading authority.  A caller must
establish that context belongs to the same admitted source as ``body``.
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from .errors import ContractError
from .normalization_v2 import FieldAssertion, FieldOrigin, MetadataV2


RepresentationKind = Literal[
    "body-only-v2", "trusted-title-section-body-v2", "trusted-classification-body-v2",
]
ContextOrigin = Literal["source", "manual_verified", "parsed_verified"]

MAX_BODY_CODE_POINTS = 4096
MAX_METADATA_CODE_POINTS = 512
MAX_INPUT_BYTES = 16384


@dataclass(frozen=True, slots=True)
class TrustedContextText:
    text: str = field(repr=False)
    origin: ContextOrigin
    source_ref: str

    def __post_init__(self) -> None:
        if (type(self.text) is not str or not self.text or len(self.text) > MAX_METADATA_CODE_POINTS
                or type(self.source_ref) is not str or not self.source_ref
                or len(self.source_ref) > 2048 or self.origin not in (
                    "source", "manual_verified", "parsed_verified")):
            raise ContractError("retrieval_context_invalid")
        _encode(self.text)
        _encode(self.source_ref)


@dataclass(frozen=True, slots=True)
class RetrievalRepresentationV2:
    text: str = field(repr=False)
    body_sha256: str
    input_sha256: str
    version: RepresentationKind
    input_code_points: int
    input_bytes: int
    classification_enriched: bool


def _encode(value: str) -> bytes:
    if "\x00" in value:
        raise ContractError("retrieval_text_invalid")
    try:
        return value.encode("utf-8")
    except UnicodeEncodeError:
        # Do not retain source text in an exception chain.
        pass
    raise ContractError("retrieval_text_invalid")


def _trusted_assertion(assertion: FieldAssertion) -> bool:
    if type(assertion) is not FieldAssertion:
        return False
    observed = assertion.observed_at
    return (
        assertion.origin in (FieldOrigin.SOURCE, FieldOrigin.MANUAL_VERIFIED)
        and type(assertion.source_ref) is str and bool(assertion.source_ref.strip())
        and type(observed) is datetime and observed.utcoffset() is not None
    )


def _placeholder(value: str) -> bool:
    return value.strip().casefold() == "unknown" or value.strip() == "未知"


def _classification_lines(metadata: MetadataV2) -> tuple[str, ...]:
    lines: list[str] = []
    document_type = metadata.document_type
    if _trusted_assertion(document_type):
        value = document_type.value
        if type(value) is str and value in (
            "law", "regulation", "policy", "interpretation", "other",
        ) and not _placeholder(value):
            if not unicodedata.is_normalized("NFC", value):
                raise ContractError("retrieval_classification_invalid")
            lines.append(f"文档类型：{value}")
    tax_types = metadata.tax_types
    if _trusted_assertion(tax_types):
        values = tax_types.value
        if (type(values) is tuple and values
                and all(type(value) is str and value.strip() for value in values)
                and not any(_placeholder(value) for value in values)):
            if any(not unicodedata.is_normalized("NFC", value) for value in values):
                raise ContractError("retrieval_classification_invalid")
            lines.append("税种：" + "、".join(values))
    return tuple(lines)


def build_retrieval_representation_v2(
    *, body: str, kind: RepresentationKind,
    title: TrustedContextText | None = None,
    section: TrustedContextText | None = None,
    classification: MetadataV2 | None = None,
) -> RetrievalRepresentationV2:
    """Construct one exact input; metadata is never substituted for body."""
    if type(body) is not str or not body.strip() or len(body) > MAX_BODY_CODE_POINTS:
        raise ContractError("retrieval_body_invalid")
    body_bytes = _encode(body)
    if type(kind) is not str or kind not in (
        "body-only-v2", "trusted-title-section-body-v2", "trusted-classification-body-v2",
    ):
        raise ContractError("retrieval_kind_invalid")
    if title is not None and type(title) is not TrustedContextText:
        raise ContractError("retrieval_context_invalid")
    if section is not None and type(section) is not TrustedContextText:
        raise ContractError("retrieval_context_invalid")
    if classification is not None and type(classification) is not MetadataV2:
        raise ContractError("retrieval_classification_invalid")
    if kind == "body-only-v2":
        if title is not None or section is not None or classification is not None:
            raise ContractError("retrieval_context_invalid")
        text = body
        classification_enriched = False
    elif kind == "trusted-title-section-body-v2":
        if classification is not None:
            raise ContractError("retrieval_context_invalid")
        if title is None and section is None:
            raise ContractError("retrieval_context_invalid")
        if title is not None and title.origin not in ("source", "manual_verified"):
            raise ContractError("retrieval_context_invalid")
        if section is not None and section.origin not in ("parsed_verified", "manual_verified"):
            raise ContractError("retrieval_context_invalid")
        context = [value.text for value in (title, section) if value is not None]
        if sum(map(len, context)) + len(context) > MAX_METADATA_CODE_POINTS:
            raise ContractError("retrieval_input_limit_exceeded")
        text = "\n".join((*context, body))
        classification_enriched = False
    else:
        if title is not None or section is not None:
            raise ContractError("retrieval_context_invalid")
        lines = _classification_lines(classification) if classification is not None else ()
        if sum(len(line) + 1 for line in lines) > MAX_METADATA_CODE_POINTS:
            raise ContractError("retrieval_input_limit_exceeded")
        text = "\n".join((body, *lines))
        classification_enriched = bool(lines)
    encoded = _encode(text)
    if len(encoded) > MAX_INPUT_BYTES:
        raise ContractError("retrieval_input_limit_exceeded")
    return RetrievalRepresentationV2(
        text=text,
        body_sha256=hashlib.sha256(body_bytes).hexdigest(),
        input_sha256=hashlib.sha256(encoded).hexdigest(),
        version=kind,
        input_code_points=len(text),
        input_bytes=len(encoded),
        classification_enriched=classification_enriched,
    )
