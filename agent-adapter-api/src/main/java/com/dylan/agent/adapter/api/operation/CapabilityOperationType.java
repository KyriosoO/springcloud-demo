package com.dylan.agent.adapter.api.operation;

import java.util.Locale;
import java.util.Objects;

/** capability 自己声明的受控 UPPER_SNAKE_CASE operation 类型。 */
public record CapabilityOperationType(String value) {

    public CapabilityOperationType {
        Objects.requireNonNull(value, "value must not be null");
        if (!value.matches("[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*")) {
            throw new IllegalArgumentException("operation type must be UPPER_SNAKE_CASE");
        }
    }

    public static CapabilityOperationType of(String value) {
        Objects.requireNonNull(value, "value must not be null");
        return new CapabilityOperationType(value.trim().toUpperCase(Locale.ROOT));
    }
}
