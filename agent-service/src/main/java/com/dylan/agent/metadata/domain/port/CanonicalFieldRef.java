package com.dylan.agent.metadata.domain.port;

import java.util.Objects;

/** Stable canonical domain field reference. */
public record CanonicalFieldRef(String domain, String field) {
    public CanonicalFieldRef {
        domain = requireNonBlank(domain, "domain");
        field = requireNonBlank(field, "field");
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
