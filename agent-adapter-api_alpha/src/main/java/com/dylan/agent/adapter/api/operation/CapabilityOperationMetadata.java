package com.dylan.agent.adapter.api.operation;


/** 本地 client boundary 生成的安全 operation metadata。 */
public record CapabilityOperationMetadata(
        String operationId,
        CapabilityOperationType operationType,
        ProviderSafeIdentity provider,
        int providerAttempts,
        long durationMs,
        CapabilityOperationTermination termination,
        String diagnosticId,
        ResourceLimitReference resourceLimitReference,
        boolean limitTouched,
        boolean deadlineTouched,
        boolean cancellationObserved) {

    public CapabilityOperationMetadata {
        requireText(operationId, "operationId");
        requireText(diagnosticId, "diagnosticId");
        if (operationType == null || provider == null || termination == null || resourceLimitReference == null) {
            throw new IllegalArgumentException("operation metadata references must not be null");
        }
        if (providerAttempts < 0 || providerAttempts > 1) {
            throw new IllegalArgumentException("providerAttempts must be 0 or 1");
        }
        if (durationMs < 0) {
            throw new IllegalArgumentException("durationMs must be non-negative");
        }
        if (termination == CapabilityOperationTermination.DISABLED && providerAttempts != 0) {
            throw new IllegalArgumentException("disabled operation must have zero provider attempts");
        }
        if (termination == CapabilityOperationTermination.SUCCEEDED && providerAttempts != 1) {
            throw new IllegalArgumentException("successful operation must have one provider attempt");
        }
        if (termination == CapabilityOperationTermination.SUCCEEDED
                && (deadlineTouched || cancellationObserved)) {
            throw new IllegalArgumentException(
                    "successful operation must not observe deadline or cancellation");
        }
    }

    private static void requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " must not be blank");
        }
    }
}
