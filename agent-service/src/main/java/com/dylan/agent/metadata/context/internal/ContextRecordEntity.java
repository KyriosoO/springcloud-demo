package com.dylan.agent.metadata.context.internal;

import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.metadata.context.model.ContextRecordKey;
import com.dylan.agent.metadata.crypto.model.ProtectedPayload;

import java.time.Instant;
import java.util.Objects;

/** Persistence-facing context record value. */
public record ContextRecordEntity(
        String contextId,
        ContextRecordKey recordKey,
        ContractRef contractRef,
        ProtectedPayload protectedPayload,
        String sourceCapabilityId,
        String sourceInvocationId,
        String sourceDomain,
        Instant expiresAt) {

    public ContextRecordEntity {
        contextId = requireNonBlank(contextId, "contextId");
        Objects.requireNonNull(recordKey, "recordKey must not be null");
        Objects.requireNonNull(contractRef, "contractRef must not be null");
        Objects.requireNonNull(protectedPayload, "protectedPayload must not be null");
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
