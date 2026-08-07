from __future__ import annotations

import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "src" / "agent_runtime"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    return names


def test_capability_api_and_core_have_no_domain_or_framework_reverse_dependency() -> None:
    forbidden = ("knowledge", "employee", "transaction", "deepseek", "fastapi", "pydantic")
    for path in [SOURCE / "capability_api" / "contracts.py", *(SOURCE / "core").glob("*.py")]:
        imports = _imports(path)
        assert not any(any(marker in name for marker in forbidden) for name in imports)
    assert not any(name.startswith("langgraph") for name in _imports(SOURCE / "capability_api" / "contracts.py"))
    assert not any(name.startswith("langgraph") for name in _imports(SOURCE / "core" / "execution.py"))


def test_only_execution_core_imports_private_registered_call_types() -> None:
    importers: set[str] = set()
    for path in SOURCE.rglob("*.py"):
        if path.name == "registry.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "ValidatedCapabilityCall" in text or "RegisteredCapability" in text:
            importers.add(path.relative_to(SOURCE).as_posix())

    assert importers == {"core/execution.py"}


def test_graph_compile_has_no_persistence_or_dynamic_plugin_configuration() -> None:
    bootstrap = (SOURCE / "bootstrap.py").read_text(encoding="utf-8")

    assert "checkpointer=" not in bootstrap
    assert "store=" not in bootstrap
    assert "import_module" not in bootstrap
    assert "entry_points" not in bootstrap
    assert "scan" not in bootstrap


def test_only_capability_node_accepts_langgraph_runtime() -> None:
    tree = ast.parse((SOURCE / "graph" / "nodes.py").read_text(encoding="utf-8"))
    runtime_functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(argument.arg == "runtime" for argument in node.args.args)
    }

    assert runtime_functions == {"execute_capability_node"}


def test_model_protocols_keep_narrow_inputs_and_decisions() -> None:
    tree = ast.parse((SOURCE / "graph" / "nodes.py").read_text(encoding="utf-8"))
    expected = {
        "ActionSelectionNode": ("ActionSelectionInput", "ActionSelectionDecision"),
        "AnswerGenerationNode": ("AnswerGenerationInput", "AnswerGenerationDecision"),
    }

    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name not in expected:
            continue
        call = next(
            item
            for item in node.body
            if isinstance(item, ast.AsyncFunctionDef) and item.name == "__call__"
        )
        input_type, return_type = expected[node.name]
        assert len(call.args.args) == 2
        assert call.args.args[1].annotation is not None
        assert ast.unparse(call.args.args[1].annotation) == input_type
        assert call.returns is not None and ast.unparse(call.returns) == return_type

    resolution_tree = ast.parse((SOURCE / "graph" / "action_resolution.py").read_text(encoding="utf-8"))
    capability_protocol = next(
        node
        for node in resolution_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "CapabilitySelectionNode"
    )
    capability_call = next(
        item
        for item in capability_protocol.body
        if isinstance(item, ast.AsyncFunctionDef) and item.name == "__call__"
    )
    assert len(capability_call.args.args) == 2
    assert capability_call.args.args[1].annotation is not None
    assert ast.unparse(capability_call.args.args[1].annotation) == "CapabilitySelectionInput"
    assert capability_call.returns is not None
    assert ast.unparse(capability_call.returns) == "CapabilitySelectionDecision"


def test_registry_resolution_has_one_execution_owner() -> None:
    callers: set[str] = set()
    for path in SOURCE.rglob("*.py"):
        if path.name == "registry.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "resolve"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "_registry"
            for node in ast.walk(tree)
        ):
            callers.add(path.relative_to(SOURCE).as_posix())

    assert callers == {"core/execution.py"}


def test_core_modules_have_no_http_domain_or_provider_specific_dependency() -> None:
    forbidden_imports = ("fastapi", "starlette", "uvicorn", "httpx", "requests", "aiohttp", "deepseek")
    core_paths = [
        SOURCE / "capability_api" / "contracts.py",
        *(SOURCE / "core").glob("*.py"),
        *(SOURCE / "graph").glob("*.py"),
        SOURCE / "runtime.py",
        SOURCE / "settings.py",
    ]
    for path in core_paths:
        assert not any(
            name == marker or name.startswith(f"{marker}.")
            for name in _imports(path)
            for marker in forbidden_imports
        )
    assert (SOURCE / "api").is_dir()
