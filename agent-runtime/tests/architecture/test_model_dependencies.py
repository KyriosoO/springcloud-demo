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


def test_core_graph_and_capability_api_do_not_depend_on_model_package() -> None:
    paths = [
        SOURCE / "capability_api" / "contracts.py",
        *(SOURCE / "core").glob("*.py"),
        *(SOURCE / "graph").glob("*.py"),
        SOURCE / "runtime.py",
        SOURCE / "settings.py",
    ]

    for path in paths:
        assert not any(name.startswith("agent_runtime.model") for name in _imports(path))


def test_provider_neutral_model_modules_do_not_import_deepseek_dto_or_http_clients() -> None:
    neutral_paths = [
        path
        for path in (SOURCE / "model").glob("*.py")
        if path.name != "__init__.py"
    ]
    forbidden = ("agent_runtime.model.deepseek", "httpx", "requests", "aiohttp", "openai", "langchain")

    for path in neutral_paths:
        imports = _imports(path)
        assert not any(name == marker or name.startswith(f"{marker}.") for name in imports for marker in forbidden)


def test_live_http_dependency_is_confined_to_deepseek_transport() -> None:
    transport_path = SOURCE / "model" / "deepseek" / "transport.py"
    assert transport_path.exists()
    all_imports = {
        name
        for path in (SOURCE / "model").rglob("*.py")
        if path != transport_path
        for name in _imports(path)
    }
    assert not any(
        name == marker or name.startswith(f"{marker}.")
        for name in all_imports
        for marker in ("httpx", "requests", "aiohttp", "openai", "langchain")
    )
    assert "httpx" in _imports(transport_path)
    bootstrap = (SOURCE / "bootstrap.py").read_text(encoding="utf-8")
    assert "model.local_composition_requires_stub" in bootstrap
    assert "DeepSeekChatTransport" not in bootstrap


def test_transport_protocol_uses_only_neutral_request_and_response() -> None:
    tree = ast.parse((SOURCE / "model" / "contracts.py").read_text(encoding="utf-8"))
    protocol = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "StructuredModelTransport"
    )
    complete = next(
        node for node in protocol.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "complete"
    )

    request_annotation = complete.args.args[1].annotation
    return_annotation = complete.returns
    assert request_annotation is not None
    assert return_annotation is not None
    assert ast.unparse(request_annotation) == "StructuredModelRequest"
    assert ast.unparse(return_annotation) == "StructuredModelResponse"


def test_model_context_binding_is_outside_core_runtime_implementation() -> None:
    runtime_text = (SOURCE / "runtime.py").read_text(encoding="utf-8")
    core_text = (SOURCE / "core" / "execution.py").read_text(encoding="utf-8")
    context_text = (SOURCE / "model" / "context.py").read_text(encoding="utf-8")

    assert "ContextVar" not in runtime_text
    assert "ContextVar" not in core_text
    assert "ContextVar" in context_text
    assert "finally:" in context_text and "reset(token)" in context_text


def test_context_projection_and_model_package_exclude_identity_domain_and_dynamic_prompt_inputs() -> None:
    context_tree = ast.parse((SOURCE / "model" / "context.py").read_text(encoding="utf-8"))
    projected_context_attributes = {
        node.attr
        for node in ast.walk(context_tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "scope"
        and node.value.attr == "context"
    }
    model_text = "\n".join(path.read_text(encoding="utf-8") for path in (SOURCE / "model").rglob("*.py"))

    assert projected_context_attributes == {"request_id", "correlation_id", "deadline_monotonic"}
    assert "OpaqueUserToken" not in model_text
    assert "domain_result" not in model_text
    assert "os.environ" not in model_text


def test_action_selector_is_id_only_and_does_not_depend_on_execution_arguments() -> None:
    selector_path = SOURCE / "model" / "deepseek" / "action_selector.py"
    tools_path = SOURCE / "model" / "deepseek" / "tools.py"
    selector_text = selector_path.read_text(encoding="utf-8")
    tools_tree = ast.parse(tools_path.read_text(encoding="utf-8"))

    assert "CapabilitySelectionDecision" in selector_text
    assert "ActionCandidate" not in selector_text
    assert "LocalActionResolver" not in selector_text
    assert "employee_identifier" not in selector_text
    assert "amount_gt" not in selector_text
    assert not any(
        isinstance(node, ast.Attribute) and node.attr == "argument_schema"
        for node in ast.walk(tools_tree)
    )
