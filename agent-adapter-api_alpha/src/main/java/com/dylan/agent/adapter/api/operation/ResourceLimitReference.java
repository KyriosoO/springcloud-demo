package com.dylan.agent.adapter.api.operation;

import com.dylan.agent.api.contract.common.ContractRef;

import java.util.Objects;

/** 不暴露实际限额值的安全绑定引用。 */
public record ResourceLimitReference(
        ContractRef contractRef,
        String canonicalDigest,
        String invocationId,
        String registrationIdentity) {

    public ResourceLimitReference {
        Objects.requireNonNull(contractRef, "contractRef must not be null");
        requireText(canonicalDigest, "canonicalDigest");
        requireText(invocationId, "invocationId");
        requireText(registrationIdentity, "registrationIdentity");
        if (!canonicalDigest.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException("canonicalDigest must be lowercase SHA-256 hex");
        }
    }

    private static void requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " must not be blank");
        }
    }
}
