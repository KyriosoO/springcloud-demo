from pathlib import Path
import base64

from pydantic import AnyHttpUrl, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from agent_service.security.enums import AuditMode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENT_", extra="ignore")
    auth_authorization_url: AnyHttpUrl = AnyHttpUrl(
        "http://127.0.0.1:8090/internal/agent/authorization/resolve"
    )
    employee_query_url: AnyHttpUrl = AnyHttpUrl(
        "http://127.0.0.1:9220/internal/agent/employee/query"
    )
    service_issuer: str = "agent-service"
    service_subject: str = "agent-service"
    service_active_key_id: str = "ACTIVE"
    service_previous_key_id: str = "PREVIOUS"
    jwt_hmac_key_active: str = Field(alias="AGENT_SERVICE_JWT_HMAC_KEY_ACTIVE", repr=False)
    jwt_hmac_key_previous: str = Field(alias="AGENT_SERVICE_JWT_HMAC_KEY_PREVIOUS", repr=False)
    policy_path: Path = Path("config/policy.yml")
    max_timeout_ms: int = 30000
    audit_mode: AuditMode = AuditMode.LOCAL_ACCEPTED
    employee_query_enabled: bool = False
    single_tenant_ref: str = "tenant-main"

    @model_validator(mode="after")
    def validate_isolation(self) -> "Settings":
        try:
            active = base64.b64decode(self.jwt_hmac_key_active, validate=True)
            previous = base64.b64decode(self.jwt_hmac_key_previous, validate=True)
        except ValueError as exc:
            raise ValueError("Agent service keys must use standard Base64") from exc
        if len(active) < 32 or len(previous) < 32:
            raise ValueError("Agent service keys must decode to at least 32 bytes")
        if active == previous:
            raise ValueError("active and previous Agent service keys must differ")
        if self.audit_mode is AuditMode.PRE_RELEASE_DURABLE:
            raise ValueError("PRE_RELEASE_DURABLE is not approved in P1")
        return self
