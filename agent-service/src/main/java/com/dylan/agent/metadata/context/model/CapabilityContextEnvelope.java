package com.dylan.agent.metadata.context.model;

import com.dylan.agent.api.context.CapabilityContextPayload;
import com.dylan.agent.api.contract.common.ContractRef;

import java.time.Instant;
import java.util.Objects;

/** typed 内存 context envelope；绝不直接发送给 Runtime。 */
public record CapabilityContextEnvelope(
        ContextRecordKey recordKey,
        ContractRef contractRef,
        CapabilityContextPayload payload,
        String sourceCapabilityId,
        String sourceInvocationId,
        String sourceDomain,
        Instant expiresAt) {
    public CapabilityContextEnvelope {
        Objects.requireNonNull(recordKey, "recordKey must not be null");
        Objects.requireNonNull(contractRef, "contractRef must not be null");
        Objects.requireNonNull(payload, "payload must not be null");
        sourceCapabilityId = requireNonBlank(sourceCapabilityId, "sourceCapabilityId");
        sourceInvocationId = requireNonBlank(sourceInvocationId, "sourceInvocationId");
        if (sourceDomain != null) {
            sourceDomain = requireNonBlank(sourceDomain, "sourceDomain");
        }
        Objects.requireNonNull(expiresAt, "expiresAt must not be null");
    }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }
}
