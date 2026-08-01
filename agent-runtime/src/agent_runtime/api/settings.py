from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from typing import Mapping


def _read_int(environ: Mapping[str, str], key: str, default: int) -> int:
    raw = environ.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"runtime.settings_invalid:{key}") from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeHttpSettings:
    host: str = "127.0.0.1"
    port: int = 8091
    contract_version: int = 1
    max_body_bytes: int = 32768
    max_in_flight: int = 8
    disconnect_poll_ms: int = 100
    max_incomplete_event_bytes: int = 32768

    def __post_init__(self) -> None:
        try:
            address = ipaddress.ip_address(self.host)
        except ValueError as exc:
            raise ValueError("runtime.settings_invalid:AGENT_RUNTIME_HOST") from exc
        if not address.is_loopback:
            raise ValueError("runtime.settings_invalid:AGENT_RUNTIME_HOST")
        ranges = {
            "AGENT_RUNTIME_PORT": (self.port, 1, 65535),
            "AGENT_RUNTIME_MAX_BODY_BYTES": (self.max_body_bytes, 4096, 65536),
            "AGENT_RUNTIME_MAX_IN_FLIGHT": (self.max_in_flight, 1, 32),
            "AGENT_RUNTIME_DISCONNECT_POLL_MS": (self.disconnect_poll_ms, 50, 500),
        }
        for name, (value, minimum, maximum) in ranges.items():
            if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
                raise ValueError(f"runtime.settings_invalid:{name}")
        if self.contract_version != 1:
            raise ValueError("runtime.settings_invalid:AGENT_RUNTIME_CONTRACT_VERSION")
        if self.max_incomplete_event_bytes != 32768:
            raise ValueError("runtime.settings_invalid:AGENT_RUNTIME_MAX_INCOMPLETE_EVENT_BYTES")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> RuntimeHttpSettings:
        source = os.environ if environ is None else environ
        return cls(
            host=source.get("AGENT_RUNTIME_HOST", "127.0.0.1"),
            port=_read_int(source, "AGENT_RUNTIME_PORT", 8091),
            contract_version=_read_int(source, "AGENT_RUNTIME_CONTRACT_VERSION", 1),
            max_body_bytes=_read_int(source, "AGENT_RUNTIME_MAX_BODY_BYTES", 32768),
            max_in_flight=_read_int(source, "AGENT_RUNTIME_MAX_IN_FLIGHT", 8),
            disconnect_poll_ms=_read_int(source, "AGENT_RUNTIME_DISCONNECT_POLL_MS", 100),
            max_incomplete_event_bytes=_read_int(
                source,
                "AGENT_RUNTIME_MAX_INCOMPLETE_EVENT_BYTES",
                32768,
            ),
        )
