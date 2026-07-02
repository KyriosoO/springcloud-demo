package com.dylan.agent.kernel.port.model;

import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentOperator;

import java.util.Objects;
import java.util.Optional;
import java.util.Set;

/** 单个 canonical field 的安全执行 projection。 */
public final class ExecutionFieldRule {

    private final String field;
    private final AgentFieldType fieldType;
    private final Set<AgentOperator> allowedOperators;
    private final Set<AggregateFunction> allowedFunctions;
    private final Optional<Integer> maxLength;
    private final Optional<Integer> precision;
    private final Optional<Integer> scale;
    private final Optional<String> valueFormat;

    public ExecutionFieldRule(String field,
                              AgentFieldType fieldType,
                              Set<AgentOperator> allowedOperators,
                              Set<AggregateFunction> allowedFunctions,
                              Integer maxLength,
                              Integer precision,
                              Integer scale,
                              String valueFormat) {
        this.field = requireField(field);
        this.fieldType = Objects.requireNonNull(fieldType, "fieldType must not be null");
        this.allowedOperators = Set.copyOf(allowedOperators == null ? Set.of() : allowedOperators);
        this.allowedFunctions = Set.copyOf(allowedFunctions == null ? Set.of() : allowedFunctions);
        this.maxLength = Optional.ofNullable(maxLength);
        this.precision = Optional.ofNullable(precision);
        this.scale = Optional.ofNullable(scale);
        this.valueFormat = Optional.ofNullable(valueFormat)
                .map(String::trim)
                .filter(value -> !value.isEmpty());
    }

    private static String requireField(String field) {
        Objects.requireNonNull(field, "field must not be null");
        String normalized = field.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException("field must not be blank");
        }
        return normalized;
    }

    public String field() { return field; }
    public AgentFieldType fieldType() { return fieldType; }
    public Set<AgentOperator> allowedOperators() { return allowedOperators; }
    public Set<AggregateFunction> allowedFunctions() { return allowedFunctions; }
    public Optional<Integer> maxLength() { return maxLength; }
    public Optional<Integer> precision() { return precision; }
    public Optional<Integer> scale() { return scale; }
    public Optional<String> valueFormat() { return valueFormat; }
}
