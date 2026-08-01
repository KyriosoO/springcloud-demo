package com.dylan.agent.service.contract;

public record RuntimeInvokeRequest(
        int contractVersion,
        String requestId,
        String correlationId,
        String question,
        RuntimeSubject subject,
        long deadlineEpochMs,
        int remainingTimeoutMs) {
}
