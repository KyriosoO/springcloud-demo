from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, alias_generator=to_camel, populate_by_name=True
    )


class SubjectRef(StrictFrozenModel):
    type: str
    id: str


class TrustedIdentity(StrictFrozenModel):
    subject: SubjectRef
    tenant_ref: str
    identity_evidence_version: str
    valid_until: datetime


class AuthUpperBound(StrictFrozenModel):
    permission_codes: frozenset[str]
    allowed_capability_ids: frozenset[str]
    allowed_domains: frozenset[str]
    filterable_fields: dict[str, frozenset[str]]
    displayable_fields: dict[str, frozenset[str]]
    allowed_operators: dict[str, frozenset[str]]
    allowed_functions: dict[str, frozenset[str]]
    auth_evidence_version: str


class PlanningAuthorization(StrictFrozenModel):
    subject: SubjectRef
    tenant_ref: str
    capabilities: frozenset[str]
    domains: frozenset[str]
    filter_fields: dict[str, frozenset[str]]
    display_fields: dict[str, frozenset[str]]
    sort_fields: dict[str, frozenset[str]]
    operators: dict[str, frozenset[str]]
    identity_evidence_version: str
    auth_evidence_version: str
    policy_version: str
    valid_until: datetime


class ResourceAuthorizationFacts(StrictFrozenModel):
    tenant_ref: str
    resource_scope_mode: str
    source_version: str
    valid_until: datetime


class EffectiveAuthorization(PlanningAuthorization):
    resource_scope_mode: str
    resource_version: str
