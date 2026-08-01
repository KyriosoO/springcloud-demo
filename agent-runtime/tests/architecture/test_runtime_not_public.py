from __future__ import annotations

from pathlib import Path

from agent_runtime.api.settings import RuntimeHttpSettings

SRC = Path(__file__).resolve().parents[2] / "src" / "agent_runtime"


def test_runtime_defaults_to_loopback_and_has_no_service_registration() -> None:
    settings = RuntimeHttpSettings()
    source = "\n".join(path.read_text(encoding="utf-8") for path in (SRC / "api").glob("*.py"))
    main_source = (SRC / "main.py").read_text(encoding="utf-8")

    assert settings.host == "127.0.0.1"
    assert "0.0.0.0" not in main_source
    assert "eureka" not in source.lower()
    assert "gateway" not in source.lower()
    assert "workers=1" in main_source
    assert 'http="h11"' in main_source
