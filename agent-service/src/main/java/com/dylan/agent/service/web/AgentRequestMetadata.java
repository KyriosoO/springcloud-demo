package com.dylan.agent.service.web;

public record AgentRequestMetadata(String requestId, String correlationId, long receivedMonotonicNanos) {
}
