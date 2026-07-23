from datetime import UTC, datetime, timedelta

import pytest

from agent_service.api.errors import AgentFailure
from agent_service.security.authorization import (
    build_planning_authorization,
    resolve_effective_authorization,
)
from agent_service.security.models import (
    AuthUpperBound,
    ResourceAuthorizationFacts,
    SubjectRef,
    TrustedIdentity,
)
from agent_service.security.policy import load_policy


def _inputs():
    now = datetime.now(UTC)
    identity = TrustedIdentity(
        subject=SubjectRef(type="USER", id="dylan"),
        tenantRef="tenant-main",
        identityEvidenceVersion="identity-1",
        validUntil=now + timedelta(minutes=1),
    )
    upper = AuthUpperBound(
        permissionCodes={"agent-admin"},
        allowedCapabilityIds={"query.search"},
        allowedDomains={"employee"},
        filterableFields={"employee": {"position", "workBaseSi"}},
        displayableFields={"employee": {"position", "workBaseSi"}},
        allowedOperators={"employee.position": {"EQ", "IN"}},
        allowedFunctions={},
        authEvidenceVersion="auth-1",
    )
    return now, identity, upper


def test_two_stage_intersection_never_adds_scope():
    now, identity, upper = _inputs()
    planning = build_planning_authorization(identity, upper, load_policy(None), now)
    effective = resolve_effective_authorization(
        planning,
        ResourceAuthorizationFacts(
            tenantRef="tenant-main",
            resourceScopeMode="SINGLE_TENANT_ALL",
            sourceVersion="employee-1",
            validUntil=now + timedelta(minutes=1),
        ),
        "QUERY",
        "EMPLOYEE",
        now,
    )
    assert effective.capabilities <= {"QUERY"}
    assert effective.display_fields["EMPLOYEE"] <= {"position", "workBaseSi"}


def test_tenant_conflict_fails_closed():
    now, identity, upper = _inputs()
    planning = build_planning_authorization(identity, upper, load_policy(None), now)
    with pytest.raises(AgentFailure):
        resolve_effective_authorization(
            planning,
            ResourceAuthorizationFacts(
                tenantRef="tenant-other",
                resourceScopeMode="SINGLE_TENANT_ALL",
                sourceVersion="employee-1",
                validUntil=now + timedelta(minutes=1),
            ),
            "QUERY",
            "EMPLOYEE",
            now,
        )
