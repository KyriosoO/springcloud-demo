package com.dylan.agent.employee.api.model;

import java.util.List;

public record AgentEmployeeFilter(AgentEmployeeField field, AgentQueryOperator operator, List<String> values) {
	public AgentEmployeeFilter {
		values = values == null ? List.of() : List.copyOf(values);
	}
}
