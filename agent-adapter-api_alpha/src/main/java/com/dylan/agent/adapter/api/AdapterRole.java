package com.dylan.agent.adapter.api;

import java.util.Objects;

/**
 * Stable adapter role value object.
 *
 * <p>It is intentionally not an enum so new roles can be added by adapter
 * registration without changing shared execution flow branches.</p>
 */
public final class AdapterRole {

    public static final AdapterRole QUERYABLE = new AdapterRole("QUERYABLE");
    public static final AdapterRole AGGREGATABLE = new AdapterRole("AGGREGATABLE");
    public static final AdapterRole DOCUMENT_RETRIEVABLE = new AdapterRole("DOCUMENT_RETRIEVABLE");

    private final String value;

    private AdapterRole(String value) {
        this.value = validate(value);
    }

    public static AdapterRole of(String value) {
        if (QUERYABLE.value.equals(value)) {
            return QUERYABLE;
        }
        if (AGGREGATABLE.value.equals(value)) {
            return AGGREGATABLE;
        }
        if (DOCUMENT_RETRIEVABLE.value.equals(value)) {
            return DOCUMENT_RETRIEVABLE;
        }
        return new AdapterRole(value);
    }

    public String value() {
        return value;
    }

    private static String validate(String candidate) {
        Objects.requireNonNull(candidate, "adapter role must not be null");
        String normalized = candidate.trim();
        if (!normalized.matches("[A-Z][A-Z0-9_]*")) {
            throw new IllegalArgumentException("adapter role must be upper snake case: " + candidate);
        }
        return normalized;
    }

    @Override
    public boolean equals(Object other) {
        return this == other
                || (other instanceof AdapterRole role && value.equals(role.value));
    }

    @Override
    public int hashCode() {
        return value.hashCode();
    }

    @Override
    public String toString() {
        return value;
    }
}
