from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from agent_service.security.enums import AuditMode


class SecurityAuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request_id: UUID
    subject_id: str
    capability: str | None
    result_code: str
    policy_version: str
    item_count: int


class AuditAcceptance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    event_id: UUID
    accepted_at: datetime
    mode: AuditMode
