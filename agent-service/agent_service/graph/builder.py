from datetime import UTC, datetime
from typing import Any

from langgraph.graph import END, START, StateGraph

from agent_service.api.errors import AgentError, AgentErrorCode, AgentFailure
from agent_service.capabilities.business.validators import (
    project_employee_result,
    validate_employee_query_payload,
)
from agent_service.graph.state import AgentGraphInput, AgentGraphOutput, AgentState
from agent_service.graph.types import GraphDependencies
from agent_service.observability.audit_models import SecurityAuditEvent
from agent_service.planning.models import PlanDisposition
from agent_service.security.authorization import (
    build_planning_authorization,
    resolve_effective_authorization,
    revalidate_authorization,
)
from agent_service.security.models import ResourceAuthorizationFacts


def build_agent_graph(dependencies: GraphDependencies) -> Any:
    async def auth_context(state: AgentState) -> dict[str, object]:
        planning = build_planning_authorization(
            state["trusted_identity"],
            state["auth_upper_bound"],
            dependencies.policy_provider.current(),
            datetime.now(UTC),
        )
        return {"planning_authorization": planning}

    async def plan(state: AgentState) -> dict[str, object]:
        candidate = await dependencies.planner.plan(
            state["request_input"], state["planning_authorization"]
        )
        return {"plan_candidate": candidate}

    def validate(state: AgentState) -> dict[str, object]:
        candidate = state["plan_candidate"]
        if candidate.outcome is not PlanDisposition.EXECUTE:
            code = (
                AgentErrorCode.UNSUPPORTED
                if candidate.outcome is PlanDisposition.REJECT
                else AgentErrorCode.INVALID_REQUEST
            )
            return {
                "error": AgentError(
                    code=code,
                    message="Additional information is required."
                    if candidate.outcome is PlanDisposition.CLARIFY
                    else "Request is not supported.",
                    reason_code=candidate.reason_code,
                )
            }
        if candidate.capability != "QUERY" or candidate.domain != "EMPLOYEE":
            return {
                "error": AgentError(
                    code=AgentErrorCode.UNSUPPORTED,
                    message="Request is not supported.",
                    reason_code="P1_CAPABILITY_ONLY",
                )
            }
        query = validate_employee_query_payload(
            candidate.payload,
            state["planning_authorization"],
            state["request_id"],
            state["deadline_at"],
        )
        return {"validated_query": query}

    def route_validation(state: AgentState) -> str:
        return "safe_response" if "error" in state else "authorize"

    def authorize(state: AgentState) -> dict[str, object]:
        now = datetime.now(UTC)
        if not dependencies.settings.employee_query_enabled:
            raise AgentFailure(
                AgentError(
                    code=AgentErrorCode.UPSTREAM_UNAVAILABLE,
                    message="Employee query is disabled.",
                    reason_code="CAPABILITY_DISABLED",
                )
            )
        facts = ResourceAuthorizationFacts(
            tenant_ref=dependencies.settings.single_tenant_ref,
            resource_scope_mode="SINGLE_TENANT_ALL",
            source_version="employee-single-tenant-p1",
            valid_until=state["planning_authorization"].valid_until,
        )
        effective = resolve_effective_authorization(
            state["planning_authorization"], facts, "QUERY", "EMPLOYEE", now
        )
        return {"effective_authorization": effective}

    async def query(state: AgentState) -> dict[str, object]:
        from agent_service.graph.deadline import Deadline

        response = await dependencies.employee_client.query(
            state["validated_query"],
            state["effective_authorization"],
            Deadline(state["deadline_at"]),
        )
        return {"employee_result": response}

    def safe_response(state: AgentState) -> dict[str, object]:
        error = state["error"]
        if error.code is AgentErrorCode.INVALID_REQUEST:
            return {
                "safe_response": {
                    "type": "CLARIFICATION",
                    "capability": None,
                    "data": {"reasonCode": error.reason_code},
                    "citations": (),
                    "warnings": (),
                }
            }
        return {"safe_error": error}

    def result_security(state: AgentState) -> dict[str, object]:
        if "safe_error" in state:
            result_code = state["safe_error"].code.value
            item_count = 0
            capability = None
        elif "safe_response" in state:
            result_code = "CLARIFICATION"
            item_count = 0
            capability = None
        else:
            revalidate_authorization(state["effective_authorization"], datetime.now(UTC))
            data = project_employee_result(
                state["employee_result"],
                state["effective_authorization"],
                state["validated_query"].select,
            )
            secured: dict[str, object] = {
                "type": "RESULT",
                "capability": "QUERY",
                "data": data,
                "citations": (),
                "warnings": (),
            }
            state = {**state, "secured_result": secured}
            result_code = "SUCCESS"
            item_count = len(state["employee_result"].items)
            capability = "QUERY"
        dependencies.audit_sink.accept(
            SecurityAuditEvent(
                request_id=state["request_id"],
                subject_id=state["trusted_identity"].subject.id,
                capability=capability,
                result_code=str(result_code),
                policy_version=state["planning_authorization"].policy_version,
                item_count=item_count,
            )
        )
        if "safe_error" in state:
            return {"request_id": state["request_id"], "safe_error": state["safe_error"]}
        if "safe_response" in state:
            return {"request_id": state["request_id"], "secured_result": state["safe_response"]}
        return {"request_id": state["request_id"], "secured_result": state["secured_result"]}

    graph = StateGraph(
        AgentState,
        input_schema=AgentGraphInput,
        output_schema=AgentGraphOutput,
    )
    graph.add_node("auth_context", auth_context)
    graph.add_node("plan", plan)
    graph.add_node("validate", validate)
    graph.add_node("authorize", authorize)
    graph.add_node("query", query)
    graph.add_node("safe_response", safe_response)
    graph.add_node("result_security", result_security)
    graph.add_edge(START, "auth_context")
    graph.add_edge("auth_context", "plan")
    graph.add_edge("plan", "validate")
    graph.add_conditional_edges(
        "validate", route_validation, {"safe_response": "safe_response", "authorize": "authorize"}
    )
    graph.add_edge("authorize", "query")
    graph.add_edge("query", "result_security")
    graph.add_edge("safe_response", "result_security")
    graph.add_edge("result_security", END)
    compiled = graph.compile(checkpointer=False)
    assert_graph_topology(compiled)
    return compiled


def assert_graph_topology(graph: Any) -> None:
    nodes = set(graph.get_graph().nodes)
    expected = {
        "__start__",
        "auth_context",
        "plan",
        "validate",
        "authorize",
        "query",
        "safe_response",
        "result_security",
        "__end__",
    }
    if nodes != expected:
        raise RuntimeError(f"Unexpected graph topology: {nodes}")
