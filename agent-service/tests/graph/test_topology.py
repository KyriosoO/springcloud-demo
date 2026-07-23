from agent_service.graph.builder import build_agent_graph
from agent_service.graph.types import GraphDependencies
from agent_service.observability.security_audit import BoundedLocalAuditSink
from agent_service.planning.planner import P1RuleBasedPlanner
from agent_service.security.policy import PolicyProvider, load_policy


class UnusedEmployeeClient:
    async def query(self, request, authorization, deadline):
        raise AssertionError("query must not run during topology inspection")


def test_fixed_graph_has_no_checkpointer_or_bypass(settings):
    graph = build_agent_graph(
        GraphDependencies(
            settings=settings,
            policy_provider=PolicyProvider(load_policy(settings.policy_path)),
            planner=P1RuleBasedPlanner(),
            employee_client=UnusedEmployeeClient(),
            audit_sink=BoundedLocalAuditSink(),
        )
    )
    assert graph.checkpointer is False
    edges = {(edge.source, edge.target) for edge in graph.get_graph().edges}
    assert ("query", "result_security") in edges
    assert ("safe_response", "result_security") in edges
    assert all(target != "__end__" or source == "result_security" for source, target in edges)
