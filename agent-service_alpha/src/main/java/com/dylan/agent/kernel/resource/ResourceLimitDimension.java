package com.dylan.agent.kernel.resource;

import java.util.Objects;

/** Capability 资源限额中的稳定维度标识。 */
public record ResourceLimitDimension(String value) {

    public ResourceLimitDimension {
        Objects.requireNonNull(value, "value must not be null");
        if (!value.matches("[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*")) {
            throw new IllegalArgumentException("invalid resource limit dimension: " + value);
        }
    }
}
