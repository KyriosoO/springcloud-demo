from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class CoreRuntimeSettings:
    max_capabilities: int = 32
    max_descriptor_bytes: int = 8192
    max_question_chars: int = 4096
    max_argument_bytes: int = 16384
    max_domain_result_bytes: int = 262144
    max_model_payload_bytes: int = 65536
    max_json_depth: int = 8
    max_collection_items: int = 256

    def __post_init__(self) -> None:
        ranges = {
            "max_capabilities": (self.max_capabilities, 1, 128),
            "max_descriptor_bytes": (self.max_descriptor_bytes, 1024, 32768),
            "max_question_chars": (self.max_question_chars, 256, 16384),
            "max_argument_bytes": (self.max_argument_bytes, 1024, 65536),
            "max_domain_result_bytes": (self.max_domain_result_bytes, 16384, 1048576),
            "max_model_payload_bytes": (self.max_model_payload_bytes, 4096, 262144),
            "max_json_depth": (self.max_json_depth, 2, 16),
            "max_collection_items": (self.max_collection_items, 16, 2048),
        }
        for name, (value, minimum, maximum) in ranges.items():
            if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
                raise ValueError(f"core.settings_invalid:{name}")
