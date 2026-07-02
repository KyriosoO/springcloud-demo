package com.dylan.agent.metadata.authorization.model;

import java.util.Objects;

/** Exact delegation constraint reference; CHAT may use the built-in all scope. */
public record DelegationConstraintRef(String constraintId, String version) {
    public static final DelegationConstraintRef CHAT_ALL =
            new DelegationConstraintRef("chat-all", "1.0.0");

    public DelegationConstraintRef {
        constraintId = requireNonBlank(constraintId, "constraintId");
        version = requireNonBlank(version, "version");
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
