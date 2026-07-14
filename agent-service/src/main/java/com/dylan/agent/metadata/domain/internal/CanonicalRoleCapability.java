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
        Set<String> sortFields,
        Map<String, Set<AgentOperator>> operatorsByField,
        Map<String, Set<AggregateFunction>> functionsByField) {

    public CanonicalRoleCapability {
        Objects.requireNonNull(role, "role must not be null");
        fields = fields == null ? Set.of() : fields.stream()
                .map(value -> CanonicalFieldDefinition.requireNonBlank(value, "field"))
                .collect(Collectors.toUnmodifiableSet());
        sortFields = sortFields == null ? Set.of() : sortFields.stream()
                .map(value -> CanonicalFieldDefinition.requireNonBlank(value, "sortField"))
                .collect(Collectors.toUnmodifiableSet());
        if (!fields.containsAll(sortFields)) {
            throw new IllegalArgumentException("sortFields must be capability fields subset");
        }
        operatorsByField = copyMap(operatorsByField);
        functionsByField = copyMap(functionsByField);
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
