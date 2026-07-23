from pydantic import BaseModel, ConfigDict


class PermissionRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    capabilities: frozenset[str]
    domains: frozenset[str]
    filter_fields: frozenset[str]
    display_fields: frozenset[str]
    sort_fields: frozenset[str]
    operators: frozenset[str]


class AgentPolicySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: str
    permissions: dict[str, PermissionRule]
