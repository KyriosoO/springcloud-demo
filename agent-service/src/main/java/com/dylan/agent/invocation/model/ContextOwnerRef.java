package com.dylan.agent.invocation.model;

import java.util.Objects;

/**
 * Context Owner 引用。
 */
public record ContextOwnerRef(String type, String id) {
    public ContextOwnerRef {
        Objects.requireNonNull(type);
        Objects.requireNonNull(id);
        if (type.isBlank()) throw new IllegalArgumentException("type must not be blank");
        if (id.isBlank()) throw new IllegalArgumentException("id must not be blank");
    }
}
