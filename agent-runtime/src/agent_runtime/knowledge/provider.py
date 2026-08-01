from __future__ import annotations

from typing import Any

from agent_runtime.capability_api.contracts import (
    CapabilityDescriptor,
    CapabilityKind,
    CapabilityRegistrationCandidate,
)
from agent_runtime.knowledge.capability import KnowledgeArgumentValidator, KnowledgeQueryCapability


def knowledge_query_descriptor() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id="knowledge.query",
        api_version=1,
        kind=CapabilityKind.QUERY,
        display_name="知识查询",
        description="查询税务政策与税收法律知识；只读且不执行聚合或写操作",
        aliases=("知识查询", "税务政策查询", "税务法律查询"),
        argument_schema={"type": "object", "properties": {}, "required": (), "additionalProperties": False},
    )


class KnowledgeCapabilityProvider:
    __slots__ = ("_enabled", "_handler")

    def __init__(self, *, enabled: bool, handler: KnowledgeQueryCapability[Any] | None) -> None:
        if enabled and handler is None:
            raise ValueError("knowledge.handler_required")
        self._enabled = enabled
        self._handler = handler

    def registrations(self) -> tuple[CapabilityRegistrationCandidate[Any], ...]:
        return (
            CapabilityRegistrationCandidate(
                descriptor=knowledge_query_descriptor(),
                enabled=self._enabled,
                argument_validator=KnowledgeArgumentValidator() if self._enabled else None,
                handler=self._handler if self._enabled else None,
            ),
        )

