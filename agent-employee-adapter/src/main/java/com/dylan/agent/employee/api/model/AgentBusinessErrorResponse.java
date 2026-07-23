package com.dylan.agent.employee.api.model;

public record AgentBusinessErrorResponse(String requestId, String code, String message, String diagnosticId) {
}
