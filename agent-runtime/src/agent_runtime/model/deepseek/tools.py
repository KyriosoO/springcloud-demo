from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, cast

from agent_runtime.capability_api.contracts import CapabilityDescriptor, JsonObject, JsonValue, canonical_json_bytes
from agent_runtime.model.contracts import ModelInputDenied, StructuredToolDefinition


UNSUPPORTED_TOOL_NAME = "agent_unsupported"
_UNSAFE_SLUG_CHARACTER = re.compile(r"[^a-z0-9]+")
_EMPTY_ARGUMENTS_SCHEMA: JsonObject = {
    "type": "object",
    "properties": {},
    "required": (),
    "additionalProperties": False,
}


@dataclass(frozen=True, slots=True, kw_only=True)
class CapabilityToolProjection:
    tools: tuple[StructuredToolDefinition, ...]
    capability_by_tool: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "tools", tuple(self.tools))
        object.__setattr__(self, "capability_by_tool", MappingProxyType(dict(self.capability_by_tool)))


def _tool_name(capability_id: str) -> str:
    slug = _UNSAFE_SLUG_CHARACTER.sub("_", capability_id.casefold()).strip("_")[:36]
    if not slug:
        raise ModelInputDenied("model.invalid_capability_tool")
    digest = hashlib.sha256(capability_id.encode("utf-8")).hexdigest()[:12]
    return f"cap_{slug}_{digest}"


def project_capability_tools(
    descriptors: tuple[CapabilityDescriptor, ...],
) -> CapabilityToolProjection:
    if not 1 <= len(descriptors) <= 32:
        raise ModelInputDenied("model.invalid_capability_tools")
    if any(not isinstance(descriptor, CapabilityDescriptor) for descriptor in descriptors):
        raise ModelInputDenied("model.invalid_capability_tools")
    tools: list[StructuredToolDefinition] = []
    reverse: dict[str, str] = {}
    seen_capabilities: set[str] = set()
    for descriptor in sorted(descriptors, key=lambda item: item.capability_id):
        if descriptor.capability_id in seen_capabilities:
            raise ModelInputDenied("model.invalid_capability_tools")
        seen_capabilities.add(descriptor.capability_id)
        name = _tool_name(descriptor.capability_id)
        if name in reverse or name == UNSUPPORTED_TOOL_NAME:
            raise ModelInputDenied("model.invalid_capability_tools")
        aliases = ", ".join(descriptor.aliases)
        alias_text = f" Aliases: {aliases}." if aliases else ""
        tools.append(
            StructuredToolDefinition(
                name=name,
                description=(
                    f"{descriptor.display_name}: {descriptor.description} "
                    f"[capability={descriptor.capability_id}].{alias_text}"
                ),
                arguments_schema=_EMPTY_ARGUMENTS_SCHEMA,
            )
        )
        reverse[name] = descriptor.capability_id
    tools.append(
        StructuredToolDefinition(
            name=UNSUPPORTED_TOOL_NAME,
            description="No registered capability safely matches this request.",
            arguments_schema=_EMPTY_ARGUMENTS_SCHEMA,
        )
    )
    serialized = tuple(
        {
            "name": tool.name,
            "description": tool.description,
            "arguments_schema": tool.arguments_schema,
        }
        for tool in tools
    )
    if len(canonical_json_bytes(cast(JsonValue, serialized))) > 65536:
        raise ModelInputDenied("model.capability_tools_too_large")
    return CapabilityToolProjection(tools=tuple(tools), capability_by_tool=reverse)
