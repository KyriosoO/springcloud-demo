package com.dylan.agent.employee.api.model;

import com.fasterxml.jackson.annotation.JsonInclude;

@JsonInclude(JsonInclude.Include.NON_NULL)
public record AgentEmployeeItem(String position, String workBaseSi) {
}
