package com.dylan.agent.employee.api.model;

import java.time.Instant;
import java.util.List;

public record AgentEmployeeQueryRequest(
		String requestId,
		List<AgentEmployeeFilter> filters,
		List<AgentEmployeeField> select,
		List<AgentEmployeeSort> sorts,
		AgentPageRequest page,
		Instant deadlineAt) {
	public AgentEmployeeQueryRequest {
		filters = filters == null ? List.of() : List.copyOf(filters);
		select = select == null ? List.of() : List.copyOf(select);
		sorts = sorts == null ? List.of() : List.copyOf(sorts);
	}
}
