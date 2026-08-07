from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

import pytest

from agent_runtime.capability_api.action_resolution import (
    LocalActionInvalidReason,
    LocalActionResolution,
    LocalActionResolutionKind,
    LocalActionResolver,
)


class PureResolver:
    @property
    def capability_id(self) -> str:
        return "test.query"

    def resolve(self, question: str) -> LocalActionResolution:
        del question
        return LocalActionResolution(kind=LocalActionResolutionKind.NO_MATCH)


def test_resolution_contract_has_three_mutually_exclusive_branches() -> None:
    no_match = LocalActionResolution(kind=LocalActionResolutionKind.NO_MATCH)
    candidate = LocalActionResolution(
        kind=LocalActionResolutionKind.CANDIDATE,
        arguments={"value": "x"},
    )
    invalid = LocalActionResolution(
        kind=LocalActionResolutionKind.INVALID,
        reason=LocalActionInvalidReason.MISSING_REQUIRED,
    )

    assert no_match.arguments is None and no_match.reason is None
    assert candidate.arguments == {"value": "x"} and candidate.reason is None
    assert invalid.arguments is None and invalid.reason is LocalActionInvalidReason.MISSING_REQUIRED
    assert {item.name for item in fields(LocalActionResolution)} == {"kind", "arguments", "reason"}
    assert not hasattr(candidate, "capability_id")


@pytest.mark.parametrize(
    "resolution",
    [
        {"kind": LocalActionResolutionKind.NO_MATCH, "arguments": {}},
        {"kind": LocalActionResolutionKind.CANDIDATE},
        {
            "kind": LocalActionResolutionKind.CANDIDATE,
            "arguments": {},
            "reason": LocalActionInvalidReason.MALFORMED_VALUE,
        },
        {"kind": LocalActionResolutionKind.INVALID},
        {
            "kind": LocalActionResolutionKind.INVALID,
            "reason": "free text",
        },
    ],
)
def test_invalid_branch_combinations_are_rejected(resolution: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="core.invalid_local_action_resolution"):
        LocalActionResolution(**resolution)  # type: ignore[arg-type]


def test_resolver_is_a_sync_provider_neutral_protocol() -> None:
    resolver = PureResolver()

    assert isinstance(resolver, LocalActionResolver)
    assert resolver.resolve("question").kind is LocalActionResolutionKind.NO_MATCH

    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "agent_runtime"
        / "capability_api"
        / "action_resolution.py"
    )
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    forbidden = ("asyncio", "logging", "httpx", "requests", "jwt", "deepseek", "employee", "transaction")
    assert not any(any(marker in name for marker in forbidden) for name in imports)
