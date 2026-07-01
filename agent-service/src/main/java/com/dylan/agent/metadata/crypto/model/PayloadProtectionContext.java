package com.dylan.agent.metadata.crypto.model;

import com.dylan.agent.api.contract.common.ContractRef;

import java.util.Objects;

/**
 * Authenticated additional data used for payload protection.
 */
public record PayloadProtectionContext(
        PayloadPurpose purpose,
        String recordId,
        ContractRef contractRef,
        String bindingDigest) {

    public PayloadProtectionContext {
        Objects.requireNonNull(purpose, "purpose must not be null");
        recordId = requireNonBlank(recordId, "recordId");
        Objects.requireNonNull(contractRef, "contractRef must not be null");
        bindingDigest = requireSha256Hex(bindingDigest);
    }

    public byte[] aadBytes() {
        String canonical = purpose.name() + "|"
                + recordId + "|"
                + contractRef.schema() + ":" + contractRef.version() + "|"
                + bindingDigest;
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

    private static String requireSha256Hex(String value) {
        String normalized = requireNonBlank(value, "bindingDigest");
        if (!normalized.matches("[a-f0-9]{64}")) {
            throw new IllegalArgumentException("bindingDigest must be lowercase SHA-256 hex");
        }
        return normalized;
    }
}
