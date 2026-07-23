import base64
import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import jwt

from agent_service.config.models import Settings
from agent_service.graph.deadline import Deadline
from agent_service.security.models import EffectiveAuthorization


class CallTokenIssuer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._key = base64.b64decode(settings.jwt_hmac_key_active, validate=True)
        if len(self._key) < 32:
            raise ValueError("Agent service JWT key must decode to at least 32 bytes")

    async def issue_service_token(self, request_id: UUID, deadline: Deadline) -> str:
        now = datetime.now(UTC)
        deadline.require_remaining(now)
        claims = {
            "iss": self._settings.service_issuer,
            "sub": self._settings.service_subject,
            "aud": "auth-service",
            "iat": now,
            "exp": min(deadline.at, now.replace(microsecond=0) + __import__("datetime").timedelta(seconds=30)),
            "jti": str(request_id),
            "token_type": "service",
            "scope": "agent.permission.resolve",
        }
        return jwt.encode(
            claims,
            self._key,
            algorithm="HS256",
            headers={"kid": self._settings.service_active_key_id, "typ": "JWT"},
        )

    def issue_employee_delegated_token(
        self,
        request: Any,
        authorization: EffectiveAuthorization,
        now: datetime,
    ) -> str:
        claims = {
            "iss": self._settings.service_issuer,
            "sub": self._settings.service_subject,
            "aud": "agent-employee-adapter",
            "iat": now,
            "exp": min(request.deadline_at, authorization.valid_until),
            "jti": str(request.request_id),
            "requestId": str(request.request_id),
            "token_type": "delegated",
            "scope": "employee.query",
            "domain": "EMPLOYEE",
            "capability": "QUERY",
            "subjectRef": authorization.subject.model_dump(),
            "tenantRef": authorization.tenant_ref,
            "resourceScopeMode": authorization.resource_scope_mode,
            "requestDigest": canonical_request_digest(request),
            "identityEvidenceVersion": authorization.identity_evidence_version,
            "authEvidenceVersion": authorization.auth_evidence_version,
            "resourceVersion": authorization.resource_version,
        }
        return jwt.encode(
            claims,
            self._key,
            algorithm="HS256",
            headers={
                "kid": self._settings.service_active_key_id,
                "typ": "agent-business-delegated+jwt",
            },
        )


def canonical_request_digest(request: Any) -> str:
    payload = request.model_dump(by_alias=True, mode="json")
    canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()
