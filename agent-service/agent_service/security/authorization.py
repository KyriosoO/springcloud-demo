from datetime import UTC, datetime
from collections.abc import Sequence

from agent_service.api.errors import AgentError, AgentErrorCode, AgentFailure
from agent_service.security.models import (
    AuthUpperBound,
    EffectiveAuthorization,
    PlanningAuthorization,
    ResourceAuthorizationFacts,
    TrustedIdentity,
)
from agent_service.security.policy_models import AgentPolicySnapshot
from agent_service.security.policy_models import PermissionRule


def build_planning_authorization(
    identity: TrustedIdentity,
    auth: AuthUpperBound,
    policy: AgentPolicySnapshot,
    now: datetime,
) -> PlanningAuthorization:
    if identity.valid_until <= now.astimezone(UTC):
        raise _forbidden("AUTH_EXPIRED")
    rules = [policy.permissions[code] for code in auth.permission_codes if code in policy.permissions]
    if not rules:
        raise _forbidden("POLICY_UNKNOWN")
    capabilities = set().union(*(rule.capabilities for rule in rules))
    if auth.allowed_capability_ids:
        mapped = {"QUERY"} if {"query.search", "query.preview"} & auth.allowed_capability_ids else set()
        capabilities &= mapped
    domains = set().union(*(rule.domains for rule in rules))
    domains &= {value.upper() for value in auth.allowed_domains}
    filter_fields = _domain_fields(rules, "filter_fields", auth.filterable_fields)
    display_fields = _domain_fields(rules, "display_fields", auth.displayable_fields)
    sort_fields = {
        "EMPLOYEE": frozenset().union(*(rule.sort_fields for rule in rules))
        & display_fields.get("EMPLOYEE", frozenset())
    }
    operators = {
        key.upper(): frozenset(value)
        for key, value in auth.allowed_operators.items()
        if key.lower().startswith("employee.")
    }
    if not capabilities or not domains:
        raise _forbidden("AUTHORIZATION_EMPTY")
    return PlanningAuthorization(
        subject=identity.subject,
        tenant_ref=identity.tenant_ref,
        capabilities=frozenset(capabilities),
        domains=frozenset(domains),
        filter_fields=filter_fields,
        display_fields=display_fields,
        sort_fields=sort_fields,
        operators=operators,
        identity_evidence_version=identity.identity_evidence_version,
        auth_evidence_version=auth.auth_evidence_version,
        policy_version=policy.version,
        valid_until=identity.valid_until,
    )


def resolve_effective_authorization(
    planning: PlanningAuthorization,
    resource_facts: ResourceAuthorizationFacts,
    capability: str,
    domain: str,
    now: datetime,
) -> EffectiveAuthorization:
    if (
        planning.valid_until <= now
        or resource_facts.valid_until <= now
        or planning.tenant_ref != resource_facts.tenant_ref
        or capability not in planning.capabilities
        or domain not in planning.domains
        or resource_facts.resource_scope_mode != "SINGLE_TENANT_ALL"
    ):
        raise _forbidden("RESOURCE_SCOPE_INVALID")
    return EffectiveAuthorization(
        **planning.model_dump(),
        resource_scope_mode=resource_facts.resource_scope_mode,
        resource_version=resource_facts.source_version,
    )


def revalidate_authorization(effective: EffectiveAuthorization, now: datetime) -> None:
    if effective.valid_until <= now:
        raise _forbidden("AUTH_EXPIRED")


def _domain_fields(
    rules: Sequence[PermissionRule], attribute: str, auth_fields: dict[str, frozenset[str]]
) -> dict[str, frozenset[str]]:
    allowed = frozenset().union(*(getattr(rule, attribute) for rule in rules))
    employee = auth_fields.get("employee", frozenset())
    return {"EMPLOYEE": allowed & employee}


def _forbidden(reason: str) -> AgentFailure:
    return AgentFailure(
        AgentError(
            code=AgentErrorCode.FORBIDDEN,
            message="Request is not authorized.",
            reason_code=reason,
        )
    )
