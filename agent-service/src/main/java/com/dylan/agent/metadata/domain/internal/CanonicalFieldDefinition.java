package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.api.enums.AgentFieldType;

import java.util.List;
import java.util.Objects;
import java.util.Optional;

/** Immutable canonical field facts owned by D04. */
public record CanonicalFieldDefinition(
        String field,
        List<String> aliases,
        String description,
        AgentFieldType type,
        Optional<String> unit,
        Optional<String> valueFormat,
        Optional<Integer> maxLength,
        Optional<Integer> precision,
        Optional<Integer> scale) {

    public CanonicalFieldDefinition {
        field = requireNonBlank(field, "field");
        aliases = List.copyOf(aliases == null ? List.of() : aliases);
        description = requireNonBlank(description, "description");
        Objects.requireNonNull(type, "type must not be null");
        unit = Objects.requireNonNull(unit, "unit must not be null");
        valueFormat = Objects.requireNonNull(valueFormat, "valueFormat must not be null");
        maxLength = Objects.requireNonNull(maxLength, "maxLength must not be null");
        precision = Objects.requireNonNull(precision, "precision must not be null");
        scale = Objects.requireNonNull(scale, "scale must not be null");
    }

    static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }
}
