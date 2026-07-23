from collections import deque
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from agent_service.observability.audit_models import AuditAcceptance, SecurityAuditEvent
from agent_service.security.enums import AuditMode


class SecurityAuditSink(Protocol):
    def accept(self, event: SecurityAuditEvent) -> AuditAcceptance: ...


class BoundedLocalAuditSink:
    def __init__(self, capacity: int = 1024) -> None:
        if capacity < 1:
            raise ValueError("audit capacity must be positive")
        self._events: deque[SecurityAuditEvent] = deque(maxlen=capacity)

    def accept(self, event: SecurityAuditEvent) -> AuditAcceptance:
        if len(self._events) == self._events.maxlen:
            raise RuntimeError("local audit sink is full")
        self._events.append(event)
        return AuditAcceptance(
            event_id=uuid4(), accepted_at=datetime.now(UTC), mode=AuditMode.LOCAL_ACCEPTED
        )
