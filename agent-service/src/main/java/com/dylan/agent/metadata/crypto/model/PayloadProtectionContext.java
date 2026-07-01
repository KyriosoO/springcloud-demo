package com.dylan.agent.metadata.crypto.model;

import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;

import java.util.Objects;
import java.util.Optional;

/**
 * Authenticated additional data used for payload protection.
 */
public record PayloadProtectionContext(
        PayloadPurpose purpose,
        String ownerType,
        String ownerId,
        Optional<RuntimeContextType> contextType,
        ContractRef contractRef,
        String sourceInvocationId) {

    public PayloadProtectionContext {
        Objects.requireNonNull(purpose, "purpose must not be null");
        ownerType = requireNonBlank(ownerType, "ownerType");
        ownerId = requireNonBlank(ownerId, "ownerId");
        contextType = Objects.requireNonNull(contextType, "contextType must not be null");
        Objects.requireNonNull(contractRef, "contractRef must not be null");
        sourceInvocationId = requireNonBlank(sourceInvocationId, "sourceInvocationId");
    }

    public byte[] aadBytes() {
        String canonical = purpose.name() + "|"
                + ownerType + "|"
                + ownerId + "|"
                + contextType.map(Enum::name).orElse("") + "|"
                + contractRef.schema() + ":" + contractRef.version() + "|"
                + sourceInvocationId;
        return canonical.getBytes(java.nio.charset.StandardCharsets.UTF_8);
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
