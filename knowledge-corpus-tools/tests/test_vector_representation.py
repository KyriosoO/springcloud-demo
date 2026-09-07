from __future__ import annotations

import ast
import hashlib
import inspect
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from knowledge_corpus_tools import vector_representation
from knowledge_corpus_tools.errors import ContractError
from knowledge_corpus_tools.vector_representation import build_vector_representation


def test_exact_source_bytes_and_independent_hashes() -> None:
    content = "  原文\r\n第二行e\u0301\t。 "
    result = build_vector_representation(content=content, title="标题", section="章节")
    assert result.text == "标题\n章节\n" + content
    assert result.content_sha256 == hashlib.sha256(content.encode()).hexdigest()
    assert result.input_sha256 == hashlib.sha256(result.text.encode()).hexdigest()
    assert result.input_sha256 != result.content_sha256
    assert result.version == "policy-title-section-body-v1"
    assert content == "  原文\r\n第二行e\u0301\t。 "


@pytest.mark.parametrize(
    ("title", "section", "expected"),
    [
        ("", "", "原文"),
        ("标题", "", "标题\n原文"),
        ("", "章节", "章节\n原文"),
        ("标题", "标题", "标题\n原文"),
        ("原文", "章节", "章节\n原文"),
        ("标题", "原文", "标题\n原文"),
        ("原文", "原文", "原文"),
        (" 标题", "标题 ", " 标题\n标题 \n原文"),
        (" ", "", " \n原文"),
    ],
)
def test_only_exact_metadata_deduplication(
    title: str, section: str, expected: str
) -> None:
    result = build_vector_representation(content="原文", title=title, section=section)
    assert result.text == expected


@pytest.mark.parametrize("name", ["content", "title", "section"])
@pytest.mark.parametrize("value", [None, False, 1, [], {}, b"bytes"])
def test_wrong_types_are_rejected_without_coercion(name: str, value: Any) -> None:
    arguments = {"content": "原文", name: value}
    with pytest.raises(ContractError, match="^vector_input_type_invalid$"):
        build_vector_representation(**arguments)


@pytest.mark.parametrize("content", ["", " ", "\r\n\t", "\u3000"])
def test_empty_content_rejected(content: str) -> None:
    with pytest.raises(ContractError, match="^vector_input_text_invalid$"):
        build_vector_representation(content=content)


@pytest.mark.parametrize("name", ["content", "title", "section"])
@pytest.mark.parametrize("value", ["秘密\x00", "秘密\ud800", "秘密\udfff"])
def test_invalid_text_uses_only_a_finite_error(name: str, value: str) -> None:
    arguments = {"content": "原文", name: value}
    with pytest.raises(ContractError) as caught:
        build_vector_representation(**arguments)
    assert str(caught.value) == "vector_input_text_invalid"
    assert "秘密" not in repr(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@pytest.mark.parametrize(("name", "limit"), [("content", 4096), ("title", 512), ("section", 512)])
def test_character_limits_are_inclusive(name: str, limit: int) -> None:
    arguments = {"content": "原文", name: "字" * limit}
    result = build_vector_representation(**arguments)
    assert "字" * limit in result.text
    arguments[name] += "字"
    with pytest.raises(ContractError, match="^vector_input_limit_exceeded$"):
        build_vector_representation(**arguments)


def test_byte_limit_does_not_truncate_or_drop_context() -> None:
    content = "𠀀" * 4096
    assert len(build_vector_representation(content=content).text.encode()) == 16384
    with pytest.raises(ContractError, match="^vector_input_limit_exceeded$"):
        build_vector_representation(content=content, title="t")


def test_output_is_immutable_and_repr_has_no_source_text() -> None:
    result = build_vector_representation(content="原文秘密", title="标题秘密", section="章节秘密")
    assert "秘密" not in repr(result)
    with pytest.raises(FrozenInstanceError):
        setattr(result, "text", "changed")
    with pytest.raises(FrozenInstanceError):
        setattr(result, "version", "changed")


def test_determinism_and_each_input_bound_to_hash() -> None:
    baseline = build_vector_representation(content="原文", title="标题", section="章节")
    assert baseline == build_vector_representation(content="原文", title="标题", section="章节")
    for field in ("content", "title", "section"):
        arguments = {"content": "原文", "title": "标题", "section": "章节"}
        arguments[field] += "变化"
        changed = build_vector_representation(**arguments)
        assert changed.input_sha256 != baseline.input_sha256
        assert (changed.content_sha256 != baseline.content_sha256) == (field == "content")


def test_no_question_or_inference_parameters_and_no_io_imports() -> None:
    signature = inspect.signature(build_vector_representation)
    assert list(signature.parameters) == ["content", "title", "section"]
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in signature.parameters.values())
    tree = ast.parse(inspect.getsource(vector_representation))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module)
    assert imports == {"__future__", "hashlib", "dataclasses", "knowledge_corpus_tools.errors"}
