package com.dylan.agent.adapter.api.operation;

import java.util.Objects;

/** 不携带 provider 原始异常或候选的 typed 失败。 */
public record CapabilityOperationFailure<R>(
        CapabilityOperationFailureCode code,
        String diagnosticId,
        CapabilityOperationMetadata metadata) implements CapabilityOperationOutcome<R> {

    public CapabilityOperationFailure {
        Objects.requireNonNull(code, "code must not be null");
        Objects.requireNonNull(metadata, "metadata must not be null");
        if (diagnosticId == null || diagnosticId.isBlank()) {
            throw new IllegalArgumentException("diagnosticId must not be blank");
        }
        if (metadata.termination() == CapabilityOperationTermination.SUCCEEDED) {
            throw new IllegalArgumentException("failure metadata must not be SUCCEEDED");
        }
        if (!diagnosticId.equals(metadata.diagnosticId())) {
            throw new IllegalArgumentException("failure diagnosticId must match metadata");
        }
        CapabilityOperationTermination expected = switch (code) {
            case DISABLED -> CapabilityOperationTermination.DISABLED;
            case INVALID_REQUEST, INVALID_RESPONSE, LIMIT_EXCEEDED,
                    SECURITY_REJECTED, BINDING_MISMATCH -> CapabilityOperationTermination.REJECTED;
            case PROVIDER_UNAVAILABLE, PROVIDER_TIMEOUT, PROVIDER_FAILED ->
                    CapabilityOperationTermination.FAILED;
            case DEADLINE_EXCEEDED, LATE_RESULT -> CapabilityOperationTermination.DEADLINE_EXCEEDED;
            case CANCELLED -> CapabilityOperationTermination.CANCELLED;
        };
        if (metadata.termination() != expected) {
            throw new IllegalArgumentException(
                    "failure code/termination mismatch: " + code + "/" + metadata.termination());
        }
    }
}
