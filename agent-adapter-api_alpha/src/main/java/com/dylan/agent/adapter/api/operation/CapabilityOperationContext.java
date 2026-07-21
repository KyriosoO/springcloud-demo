package com.dylan.agent.adapter.api.operation;

import java.time.Instant;

/** Adapter/provider 单次调用的最小、不可变执行上下文。 */
public record CapabilityOperationContext(
        String invocationId,
        String requestCorrelationId,
        String capabilityId,
        String operationId,
        CapabilityOperationType operationType,
        Instant absoluteDeadline,
        CancellationSignal cancellation,
        CapabilityResourceLimitView resourceLimits) {

    public CapabilityOperationContext {
        requireText(invocationId, "invocationId");
        requireText(requestCorrelationId, "requestCorrelationId");
        requireText(capabilityId, "capabilityId");
        requireText(operationId, "operationId");
        if (operationType == null || absoluteDeadline == null || cancellation == null || resourceLimits == null) {
            throw new IllegalArgumentException("operationType/deadline/cancellation/resourceLimits must not be null");
        }
    }

    private static void requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " must not be blank");
        }
    }
}
