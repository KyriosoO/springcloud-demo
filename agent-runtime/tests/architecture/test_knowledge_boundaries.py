from __future__ import annotations

import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "src" / "agent_runtime"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }


def test_core_has_no_knowledge_reverse_dependency() -> None:
    for path in [SOURCE / "capability_api" / "contracts.py", *(SOURCE / "core").glob("*.py")]:
        assert not any(name.startswith("agent_runtime.knowledge") for name in _imports(path))


def test_flow_does_not_import_provider_specific_dtos() -> None:
    for path in (SOURCE / "knowledge").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "httpx" not in text
        assert "elasticsearch" not in text
        assert "deepseek" not in text

