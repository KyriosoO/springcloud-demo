from pathlib import Path

from agent_service.security.policy_models import AgentPolicySnapshot, PermissionRule


def load_policy(path: Path) -> AgentPolicySnapshot:
    del path
    return AgentPolicySnapshot(
        version="p1-employee-query-1",
        permissions={
            "agent-admin": PermissionRule(
                capabilities=frozenset({"QUERY"}),
                domains=frozenset({"EMPLOYEE"}),
                filter_fields=frozenset({"position", "workBaseSi"}),
                display_fields=frozenset({"position", "workBaseSi"}),
                sort_fields=frozenset({"position"}),
                operators=frozenset({"EQ", "IN"}),
            ),
            "agent-viewer": PermissionRule(
                capabilities=frozenset({"QUERY"}),
                domains=frozenset({"EMPLOYEE"}),
                filter_fields=frozenset({"position"}),
                display_fields=frozenset({"position"}),
                sort_fields=frozenset({"position"}),
                operators=frozenset({"EQ", "IN"}),
            ),
        },
    )


def validate_policy(snapshot: AgentPolicySnapshot) -> None:
    if not snapshot.version or not snapshot.permissions:
        raise ValueError("policy must not be empty")


class PolicyProvider:
    def __init__(self, snapshot: AgentPolicySnapshot) -> None:
        validate_policy(snapshot)
        self._snapshot = snapshot

    def current(self) -> AgentPolicySnapshot:
        return self._snapshot
