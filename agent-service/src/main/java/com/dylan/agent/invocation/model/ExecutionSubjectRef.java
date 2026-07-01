package com.dylan.agent.invocation.model;

import java.util.Objects;

/**
 * Execution 主体引用。
 */
public record ExecutionSubjectRef(String type, String id) {
    public ExecutionSubjectRef {
        Objects.requireNonNull(type);
        Objects.requireNonNull(id);
        if (type.isBlank()) throw new IllegalArgumentException("type must not be blank");
        if (id.isBlank()) throw new IllegalArgumentException("id must not be blank");
    }
}
