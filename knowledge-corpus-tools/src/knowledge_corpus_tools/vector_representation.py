"""Pure, versioned retrieval input; never replace the original citation text."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from knowledge_corpus_tools.errors import ContractError


REPRESENTATION_VERSION = "policy-title-section-body-v1"
MAX_CONTENT_CHARACTERS = 4096
MAX_METADATA_CHARACTERS = 512
MAX_INPUT_BYTES = 16384


@dataclass(frozen=True, slots=True)
class VectorRepresentation:
    text: str = field(repr=False)
    content_sha256: str
    input_sha256: str
    version: str = field(default=REPRESENTATION_VERSION, init=False)


def _validate_text(value: str, *, maximum: int, required: bool) -> bytes:
    if type(value) is not str:
        raise ContractError("vector_input_type_invalid")
    if len(value) > maximum:
        raise ContractError("vector_input_limit_exceeded")
    if "\x00" in value or (required and not value.strip()):
        raise ContractError("vector_input_text_invalid")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        pass
    else:
        return encoded
    # Raise outside the handler so __context__ cannot retain the original text.
    raise ContractError("vector_input_text_invalid")


def build_vector_representation(
    *, content: str, title: str = "", section: str = ""
) -> VectorRepresentation:
    """Use only existing fields from one authorized record, without inference."""
    content_bytes = _validate_text(
        content, maximum=MAX_CONTENT_CHARACTERS, required=True
    )
    _validate_text(title, maximum=MAX_METADATA_CHARACTERS, required=False)
    _validate_text(section, maximum=MAX_METADATA_CHARACTERS, required=False)

    headings: list[str] = []
    for value in (title, section):
        if value and value != content and value not in headings:
            headings.append(value)
    text = "\n".join([*headings, content])
    encoded = text.encode("utf-8")
    if len(encoded) > MAX_INPUT_BYTES:
        raise ContractError("vector_input_limit_exceeded")
    return VectorRepresentation(
        text=text,
        content_sha256=hashlib.sha256(content_bytes).hexdigest(),
        input_sha256=hashlib.sha256(encoded).hexdigest(),
    )
