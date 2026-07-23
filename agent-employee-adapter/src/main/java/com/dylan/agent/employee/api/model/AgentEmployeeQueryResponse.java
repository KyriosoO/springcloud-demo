package com.dylan.agent.employee.api.model;

import java.time.Instant;
import java.util.List;

public record AgentEmployeeQueryResponse(
		String requestId,
		List<AgentEmployeeItem> items,
		AgentPageRequest page,
		Long total,
		Instant observedAt,
		String sourceVersion) {
}
