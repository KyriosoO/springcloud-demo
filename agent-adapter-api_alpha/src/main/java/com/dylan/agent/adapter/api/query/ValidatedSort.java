package com.dylan.agent.adapter.api.query;

import java.util.Locale;
import java.util.Objects;

/** Java 可信校验后的 QUERY 排序条件。 */
public final class ValidatedSort {

    private final String field;
    private final String direction;

    public ValidatedSort(String field, String direction) {
        this.field = requireNonBlank(field, "field");
        String normalizedDirection = requireNonBlank(direction, "direction").toUpperCase(Locale.ROOT);
        if (!"ASC".equals(normalizedDirection) && !"DESC".equals(normalizedDirection)) {
            throw new IllegalArgumentException("invalid sort direction");
        }
        this.direction = normalizedDirection;
    }

    public String getField() { return field; }
    public String getDirection() { return direction; }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }
}
