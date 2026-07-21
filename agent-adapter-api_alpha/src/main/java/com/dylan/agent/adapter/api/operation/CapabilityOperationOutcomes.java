package com.dylan.agent.adapter.api.operation;

import java.util.Objects;

/** Capability-local Handler 对 typed outcome 执行的统一绑定门禁。 */
public final class CapabilityOperationOutcomes {

    private CapabilityOperationOutcomes() {
    }

    public static <T> T requireBoundSuccess(
            CapabilityOperationOutcome<T> outcome,
            CapabilityOperationContext expectedContext) {
        Objects.requireNonNull(outcome, "outcome must not be null");
        Objects.requireNonNull(expectedContext, "expectedContext must not be null");
        if (outcome instanceof CapabilityOperationFailure<T> failure) {
            throw new IllegalStateException("capability operation failed: " + failure.code());
        }
        if (!(outcome instanceof CapabilityOperationSuccess<T> success)) {
            throw new IllegalStateException("capability operation returned unknown outcome");
        }
        CapabilityOperationMetadata metadata = success.metadata();
        if (!metadata.operationId().equals(expectedContext.operationId())
                || !metadata.operationType().equals(expectedContext.operationType())
                || !metadata.resourceLimitReference().equals(
                        expectedContext.resourceLimits().reference())) {
            throw new IllegalStateException("capability operation success binding mismatch");
        }
        if (expectedContext.cancellation().isCancelled()) {
            throw new IllegalStateException("capability operation success observed after cancellation");
        }
        return success.candidate();
    }
}
