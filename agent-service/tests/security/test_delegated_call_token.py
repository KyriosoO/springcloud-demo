import base64
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

from agent_service.capabilities.business.models import EmployeeQueryRequest
from agent_service.clients.service_token import CallTokenIssuer, canonical_request_digest
from agent_service.security.models import EffectiveAuthorization, SubjectRef


def test_employee_token_binds_target_tenant_and_digest(settings):
    now = datetime.now(UTC)
    request = EmployeeQueryRequest.model_validate(
        {
            "requestId": uuid4(),
            "filters": [],
            "select": ["position"],
            "sorts": [],
            "page": {"number": 0, "size": 20},
            "deadlineAt": now + timedelta(seconds=10),
        }
    )
    authorization = EffectiveAuthorization(
        subject=SubjectRef(type="USER", id="dylan"),
        tenantRef="tenant-main",
        capabilities={"QUERY"},
        domains={"EMPLOYEE"},
        filterFields={"EMPLOYEE": {"position"}},
        displayFields={"EMPLOYEE": {"position"}},
        sortFields={"EMPLOYEE": {"position"}},
        operators={},
        identityEvidenceVersion="identity-1",
        authEvidenceVersion="auth-1",
        policyVersion="policy-1",
        validUntil=now + timedelta(seconds=20),
        resourceScopeMode="SINGLE_TENANT_ALL",
        resourceVersion="employee-1",
    )
    token = CallTokenIssuer(settings).issue_employee_delegated_token(request, authorization, now)
    claims = jwt.decode(
        token,
        base64.b64decode(settings.jwt_hmac_key_active),
        algorithms=["HS256"],
        audience="agent-employee-adapter",
        issuer="agent-service",
    )
    assert jwt.get_unverified_header(token)["typ"] == "agent-business-delegated+jwt"
    assert claims["tenantRef"] == "tenant-main"
    assert claims["requestDigest"] == canonical_request_digest(request)


def test_employee_request_digest_matches_java_contract_fixture():
    request = EmployeeQueryRequest.model_validate(
        {
            "requestId": "00000000-0000-0000-0000-000000000001",
            "filters": [
                {
                    "field": "workBaseSi",
                    "operator": "IN",
                    "values": ["SHANGHAI", "BEIJING"],
                }
            ],
            "select": ["position", "workBaseSi"],
            "sorts": [{"field": "position", "direction": "DESC"}],
            "page": {"number": 2, "size": 25},
            "deadlineAt": "2026-07-24T00:00:00Z",
        }
    )

    assert (
        canonical_request_digest(request)
        == "ca52b4e9b06789bd86615bec954b5e5b00bdee33bed3fd7db9a004ada397b0eb"
    )
