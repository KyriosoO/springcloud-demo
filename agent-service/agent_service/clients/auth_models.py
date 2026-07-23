from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from agent_service.security.models import AuthUpperBound, TrustedIdentity


class AuthorizationResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)
    request_id: UUID = Field(alias="requestId")
    user_bearer_token: SecretStr = Field(alias="userBearerToken", repr=False)
    requested_at: datetime = Field(alias="requestedAt")
    deadline: datetime


class ResolvedAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)
    trusted_identity: TrustedIdentity = Field(alias="trustedIdentity")
    auth_upper_bound: AuthUpperBound = Field(alias="authUpperBound")
    resolved_at: datetime = Field(alias="resolvedAt")
    valid_until: datetime = Field(alias="validUntil")


class AuthErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)
    request_id: str = Field(alias="requestId")
    code: str
    message: str
    diagnostic_id: str = Field(alias="diagnosticId")
