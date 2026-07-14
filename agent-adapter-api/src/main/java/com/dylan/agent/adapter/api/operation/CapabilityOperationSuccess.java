package com.dylan.agent.adapter.api.operation;

import java.util.Objects;

/** typed 成功候选；仍需 Handler 与 Result Security 后续校验。 */
public record CapabilityOperationSuccess<R>(R candidate, CapabilityOperationMetadata metadata)
        implements CapabilityOperationOutcome<R> {

    public CapabilityOperationSuccess {
        Objects.requireNonNull(candidate, "candidate must not be null");
        Objects.requireNonNull(metadata, "metadata must not be null");
        if (metadata.termination() != CapabilityOperationTermination.SUCCEEDED) {
            throw new IllegalArgumentException("success metadata termination must be SUCCEEDED");
        }
    }
}
