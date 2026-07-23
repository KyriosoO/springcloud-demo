from dataclasses import dataclass
from enum import StrEnum

from agent_service.clients.employee import EmployeeClient
from agent_service.config.models import Settings
from agent_service.observability.security_audit import SecurityAuditSink
from agent_service.planning.planner import Planner
from agent_service.security.policy import PolicyProvider


class GraphRoute(StrEnum):
    AUTHORIZE = "AUTHORIZE"
    QUERY = "QUERY"
    CLARIFY = "CLARIFY"
    REJECT = "REJECT"


@dataclass(frozen=True)
class GraphDependencies:
    settings: Settings
    policy_provider: PolicyProvider
    planner: Planner
    employee_client: EmployeeClient
    audit_sink: SecurityAuditSink
