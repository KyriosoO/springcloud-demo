package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.AgentOperator;

import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

/** 单个 adapter role 声明的 field/operator/function capability。 */
public record CanonicalRoleCapability(
        AdapterRole role,
        Set<String> fields,
        Map<String, Set<AgentOperator>> operatorsByField,
        Map<String, Set<AggregateFunction>> functionsByField,
        int maxPageSize,
        int maxResultRows) {

    public CanonicalRoleCapability {
        Objects.requireNonNull(role, "role must not be null");
        fields = fields == null ? Set.of() : fields.stream()
                .map(value -> CanonicalFieldDefinition.requireNonBlank(value, "field"))
                .collect(Collectors.toUnmodifiableSet());
        operatorsByField = copyMap(operatorsByField);
        functionsByField = copyMap(functionsByField);
        if (maxPageSize < 0 || maxResultRows < 0) {
            throw new IllegalArgumentException("role limits must be non-negative");
        }
    }

    private static <T> Map<String, Set<T>> copyMap(Map<String, Set<T>> source) {
        if (source == null || source.isEmpty()) {
            return Map.of();
        }
        return source.entrySet().stream()
                .collect(Collectors.toUnmodifiableMap(
                        entry -> CanonicalFieldDefinition.requireNonBlank(entry.getKey(), "field"),
                        entry -> Set.copyOf(Objects.requireNonNull(entry.getValue(), "capability values"))));
    }
}
