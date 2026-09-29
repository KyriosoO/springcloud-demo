from __future__ import annotations

import hashlib
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import Any

import pytest

from knowledge_corpus_tools.errors import ContractError
from knowledge_corpus_tools.normalization_v2 import (
    FieldAssertion,
    FieldOrigin,
    MetadataV2,
    asserted_field,
)
from knowledge_corpus_tools.retrieval_representation_v2 import (
    TrustedContextText,
    build_retrieval_representation_v2,
)


def _context(text: str, origin: str = "source") -> TrustedContextText:
    return TrustedContextText(text=text, origin=origin, source_ref="parsed-source-v2:sha256")  # type: ignore[arg-type]


NOW = datetime(2026, 9, 29, tzinfo=UTC)


def _metadata(
    *, document_type: str | None = None,
    tax_types: tuple[str, ...] | None = None,
) -> MetadataV2:
    values: dict[str, Any] = {}
    if document_type is not None:
        values["documentType"] = asserted_field(
            document_type, origin="source", source_ref="raw:documentType", observed_at=NOW,
        )
    if tax_types is not None:
        values["taxTypes"] = asserted_field(
            tax_types, origin="manual_verified", source_ref="official:taxTypes", observed_at=NOW,
        )
    return MetadataV2.model_validate(values)


def test_body_only_is_exact_quotable_body_with_independent_hash() -> None:
    body = "  第三条\r\n不得减免e\u0301。 "
    result = build_retrieval_representation_v2(body=body, kind="body-only-v2")
    assert result.text == body
    assert result.body_sha256 == hashlib.sha256(body.encode()).hexdigest()
    assert result.input_sha256 == result.body_sha256
    assert result.version == "body-only-v2"
    assert result.input_code_points == len(body)
    assert result.input_bytes == len(body.encode())
    assert "第三条" not in repr(result)
    with pytest.raises(FrozenInstanceError):
        setattr(result, "text", "改写")


def test_trusted_title_and_section_are_separate_context_not_body() -> None:
    body = "该税款不得抵扣。"
    title = _context("可信标题")
    section = _context("第三章 / 第二节", "parsed_verified")
    result = build_retrieval_representation_v2(
        body=body, kind="trusted-title-section-body-v2", title=title, section=section,
    )
    assert result.text == "可信标题\n第三章 / 第二节\n" + body
    assert result.body_sha256 == hashlib.sha256(body.encode()).hexdigest()
    assert result.input_sha256 == hashlib.sha256(result.text.encode()).hexdigest()
    assert result.body_sha256 != result.input_sha256
    assert result.input_code_points == len(result.text)
    assert result.input_bytes == len(result.text.encode())


@pytest.mark.parametrize("value", [None, False, 1, [], {}, b"bytes", "", " \r\n"])
def test_bad_body_is_rejected_without_coercion(value: Any) -> None:
    with pytest.raises(ContractError, match="^retrieval_body_invalid$"):
        build_retrieval_representation_v2(body=value, kind="body-only-v2")


@pytest.mark.parametrize("value", ["原文\x00", "原文\ud800", "原文\udfff"])
def test_invalid_unicode_is_rejected_without_raw_text(value: str) -> None:
    with pytest.raises(ContractError) as caught:
        build_retrieval_representation_v2(body=value, kind="body-only-v2")
    assert str(caught.value) == "retrieval_text_invalid"
    assert "原文" not in repr(caught.value)
    assert caught.value.__context__ is None and caught.value.__cause__ is None


@pytest.mark.parametrize("origin", ["inferred", "unknown", "legacy_unknown", ""])
def test_untrusted_context_is_rejected(origin: str) -> None:
    with pytest.raises(ContractError, match="^retrieval_context_invalid$"):
        _context("推断分类", origin)


def test_source_title_and_verified_section_have_distinct_admission() -> None:
    body = "原文"
    with pytest.raises(ContractError, match="^retrieval_context_invalid$"):
        build_retrieval_representation_v2(
            body=body, kind="trusted-title-section-body-v2",
            title=_context("标题", "parsed_verified"),
        )
    with pytest.raises(ContractError, match="^retrieval_context_invalid$"):
        build_retrieval_representation_v2(
            body=body, kind="trusted-title-section-body-v2",
            section=_context("章节", "source"),
        )


def test_mode_cannot_silently_discard_context_or_mislabel_body() -> None:
    with pytest.raises(ContractError, match="^retrieval_context_invalid$"):
        build_retrieval_representation_v2(
            body="原文", kind="body-only-v2", title=_context("标题"),
        )
    with pytest.raises(ContractError, match="^retrieval_context_invalid$"):
        build_retrieval_representation_v2(body="原文", kind="trusted-title-section-body-v2")


def test_character_byte_and_metadata_limits_do_not_truncate() -> None:
    body = "𠀀" * 4096
    assert build_retrieval_representation_v2(body=body, kind="body-only-v2").input_bytes == 16384
    with pytest.raises(ContractError, match="^retrieval_input_limit_exceeded$"):
        build_retrieval_representation_v2(
            body=body, kind="trusted-title-section-body-v2", title=_context("标题"),
        )
    with pytest.raises(ContractError, match="^retrieval_body_invalid$"):
        build_retrieval_representation_v2(body="字" * 4097, kind="body-only-v2")
    assert build_retrieval_representation_v2(
        body="原文", kind="trusted-title-section-body-v2", title=_context("字" * 511),
    ).input_code_points == 514
    with pytest.raises(ContractError, match="^retrieval_input_limit_exceeded$"):
        build_retrieval_representation_v2(
            body="原文", kind="trusted-title-section-body-v2", title=_context("字" * 512),
        )


def test_context_hash_changes_but_body_hash_does_not() -> None:
    a = build_retrieval_representation_v2(
        body="原文", kind="trusted-title-section-body-v2", title=_context("标题A"),
    )
    b = build_retrieval_representation_v2(
        body="原文", kind="trusted-title-section-body-v2", title=_context("标题B"),
    )
    assert a.body_sha256 == b.body_sha256
    assert a.input_sha256 != b.input_sha256


def test_classification_uses_only_two_trusted_dimensions_in_frozen_order() -> None:
    body = "第一条 原文。"
    metadata = _metadata(document_type="policy", tax_types=("增值税", "企业所得税"))
    result = build_retrieval_representation_v2(
        body=body, kind="trusted-classification-body-v2", classification=metadata,
    )
    assert result.text == body + "\n文档类型：policy\n税种：增值税、企业所得税"
    assert result.classification_enriched is True
    assert result.version == "trusted-classification-body-v2"
    assert result.body_sha256 == hashlib.sha256(body.encode()).hexdigest()
    assert result.input_sha256 == hashlib.sha256(result.text.encode()).hexdigest()
    assert result.input_sha256 != result.body_sha256
    assert "raw:documentType" not in result.text
    assert "official:taxTypes" not in result.text


def test_missing_or_untrusted_classification_falls_back_to_body_with_selected_version() -> None:
    for metadata in (None, MetadataV2()):
        result = build_retrieval_representation_v2(
            body="原文", kind="trusted-classification-body-v2", classification=metadata,
        )
        assert result.text == "原文"
        assert result.input_sha256 == result.body_sha256
        assert result.version == "trusted-classification-body-v2"
        assert result.classification_enriched is False


def test_literal_unknown_values_never_enter_classification_and_tax_dimension_is_atomic() -> None:
    metadata = _metadata(document_type="unknown", tax_types=("增值税", "UNKNOWN", "企业所得税"))
    result = build_retrieval_representation_v2(
        body="原文", kind="trusted-classification-body-v2", classification=metadata,
    )
    assert result.text == "原文"
    assert result.classification_enriched is False
    for placeholder in ("unknown", "UNKNOWN", "未知", " unknown "):
        metadata = _metadata(document_type="law", tax_types=("增值税", placeholder))
        result = build_retrieval_representation_v2(
            body="原文", kind="trusted-classification-body-v2", classification=metadata,
        )
        assert result.text == "原文\n文档类型：law"
        assert "税种：" not in result.text
    for placeholder in ("unknown", "UNKNOWN", "未知"):
        forged = FieldAssertion.model_construct(
            value=placeholder, origin=FieldOrigin.SOURCE,
            source_ref="raw:documentType", observed_at=NOW,
        )
        metadata = MetadataV2().model_copy(update={"document_type": forged})
        result = build_retrieval_representation_v2(
            body="原文", kind="trusted-classification-body-v2", classification=metadata,
        )
        assert result.text == "原文"
        assert result.classification_enriched is False


@pytest.mark.parametrize("origin", [FieldOrigin.UNKNOWN, FieldOrigin.INFERRED])
def test_untrusted_origin_never_enters_classification(origin: FieldOrigin) -> None:
    forged = FieldAssertion.model_construct(
        value="law", origin=origin, source_ref="raw:type", observed_at=NOW,
    )
    metadata = MetadataV2().model_copy(update={"document_type": forged})
    result = build_retrieval_representation_v2(
        body="原文", kind="trusted-classification-body-v2", classification=metadata,
    )
    assert result.text == "原文"
    assert result.classification_enriched is False


@pytest.mark.parametrize("source_ref,observed", [
    (None, NOW), ("", NOW), (" ", NOW), ("raw:type", datetime(2026, 9, 29)),
    ("raw:type", None),
])
def test_missing_source_or_aware_time_cannot_enrich(source_ref: Any, observed: Any) -> None:
    forged = FieldAssertion.model_construct(
        value="law", origin=FieldOrigin.SOURCE, source_ref=source_ref, observed_at=observed,
    )
    metadata = MetadataV2().model_copy(update={"document_type": forged})
    result = build_retrieval_representation_v2(
        body="原文", kind="trusted-classification-body-v2", classification=metadata,
    )
    assert result.text == "原文"
    assert result.classification_enriched is False


def test_nfc_metadata_is_used_but_body_is_never_normalized() -> None:
    body = "正文e\u0301"
    metadata = _metadata(tax_types=("e\u0301", "增值税"))
    result = build_retrieval_representation_v2(
        body=body, kind="trusted-classification-body-v2", classification=metadata,
    )
    assert result.text == body + "\n税种：é、增值税"
    assert result.body_sha256 == hashlib.sha256(body.encode()).hexdigest()
    forged = FieldAssertion.model_construct(
        value=("e\u0301",), origin=FieldOrigin.SOURCE,
        source_ref="raw:taxTypes", observed_at=NOW,
    )
    bad = MetadataV2().model_copy(update={"tax_types": forged})
    with pytest.raises(ContractError, match="^retrieval_classification_invalid$"):
        build_retrieval_representation_v2(
            body="正文", kind="trusted-classification-body-v2", classification=bad,
        )


def test_classification_budgets_are_independent_and_never_truncate() -> None:
    metadata = _metadata(tax_types=("增值税",))
    assert build_retrieval_representation_v2(
        body="字" * 4096, kind="trusted-classification-body-v2", classification=metadata,
    ).classification_enriched
    with pytest.raises(ContractError, match="^retrieval_body_invalid$"):
        build_retrieval_representation_v2(
            body="字" * 4097, kind="trusted-classification-body-v2", classification=metadata,
        )
    with pytest.raises(ContractError, match="^retrieval_input_limit_exceeded$"):
        build_retrieval_representation_v2(
            body="𠀀" * 4096, kind="trusted-classification-body-v2", classification=metadata,
        )
    long_metadata = _metadata(tax_types=tuple("税" * 30 + str(index) for index in range(18)))
    with pytest.raises(ContractError, match="^retrieval_input_limit_exceeded$"):
        build_retrieval_representation_v2(
            body="正文", kind="trusted-classification-body-v2", classification=long_metadata,
        )


def test_classification_mode_never_accepts_title_or_section_and_other_modes_reject_metadata() -> None:
    metadata = _metadata(document_type="law")
    with pytest.raises(ContractError, match="^retrieval_context_invalid$"):
        build_retrieval_representation_v2(
            body="正文", kind="trusted-classification-body-v2",
            classification=metadata, title=_context("标题"),
        )
    with pytest.raises(ContractError, match="^retrieval_context_invalid$"):
        build_retrieval_representation_v2(
            body="正文", kind="body-only-v2", classification=metadata,
        )
