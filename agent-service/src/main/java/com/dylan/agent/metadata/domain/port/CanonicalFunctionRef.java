package com.dylan.agent.metadata.domain.port;

import java.util.Objects;

/** Canonical aggregate/function reference scoped to a canonical field. */
public record CanonicalFunctionRef(CanonicalFieldRef fieldRef, String functionId) {
    public CanonicalFunctionRef {
        Objects.requireNonNull(fieldRef, "fieldRef must not be null");
        functionId = requireNonBlank(functionId);
    }

    private static String requireNonBlank(String value) {
        Objects.requireNonNull(value, "functionId must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException("functionId must not be blank");
        }
        return normalized;
    }
}
