package com.dylan.agent.metadata.result;

import com.dylan.agent.api.response.AgentQueryFilterParameter;
import com.dylan.agent.mask.FieldMaskerRegistry;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.model.MaskType;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/** 统一执行 ResultSecurity 字段裁剪和值级脱敏。 */
public final class ResultValueMaskingSupport {

    private final FieldMaskerRegistry fieldMaskerRegistry;

    public ResultValueMaskingSupport(FieldMaskerRegistry fieldMaskerRegistry) {
        this.fieldMaskerRegistry = Objects.requireNonNull(
                fieldMaskerRegistry, "fieldMaskerRegistry must not be null");
    }

    public Set<String> allowedFields(String domain, ExecutionScope scope) {
        Objects.requireNonNull(scope, "scope must not be null");
        return scope.allowedFields().getOrDefault(requireNonBlank(domain, "domain"), Set.of());
    }

    public Map<String, Object> filterAndMaskRow(
            String domain,
            Map<String, Object> row,
            ExecutionScope scope) {
        if (row == null) {
            return null;
        }
        if (row.isEmpty()) {
            return new LinkedHashMap<>();
        }
        Set<String> allowedFields = allowedFields(domain, scope);
        Map<String, Object> filtered = new LinkedHashMap<>();
        row.forEach((field, value) -> {
            if (field != null && allowedFields.contains(field)) {
                filtered.put(field, maskValue(domain, field, value, scope));
            }
        });
        return filtered;
    }

    public List<String> filterFields(String domain, List<String> fields, ExecutionScope scope) {
        if (fields == null) {
            return null;
        }
        if (fields.isEmpty()) {
            return List.of();
        }
        Set<String> allowedFields = allowedFields(domain, scope);
        return fields.stream()
                .filter(allowedFields::contains)
                .toList();
    }

    public AgentQueryFilterParameter filterAndMaskFilter(
            String domain,
            AgentQueryFilterParameter filter,
            ExecutionScope scope) {
        if (filter == null || isBlank(filter.getField())) {
            return null;
        }
        Set<String> allowedFields = allowedFields(domain, scope);
        if (!allowedFields.contains(filter.getField())) {
            return null;
        }
        AgentQueryFilterParameter target = new AgentQueryFilterParameter();
        target.setField(filter.getField());
        target.setOperator(filter.getOperator());
        target.setValue(maskStringValue(domain, filter.getField(), filter.getValue(), scope));
        target.setValues(filter.getValues() == null ? null : filter.getValues().stream()
                .map(value -> maskStringValue(domain, filter.getField(), value, scope))
                .toList());
        return target;
    }

    public Object maskValue(String domain, String field, Object value, ExecutionScope scope) {
        Objects.requireNonNull(scope, "scope must not be null");
        if (value == null) {
            return null;
        }
        MaskType maskType = scope.fieldMasks().get(maskKey(domain, field));
        if (maskType == null || maskType == MaskType.NONE) {
            return value;
        }
        return fieldMaskerRegistry.mask(maskType, value);
    }

    public String maskStringValue(String domain, String field, String value, ExecutionScope scope) {
        Object masked = maskValue(domain, field, value, scope);
        return Objects.toString(masked, null);
    }

    public static String maskKey(String domain, String field) {
        return requireNonBlank(domain, "domain") + "." + requireNonBlank(field, "field");
    }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }

    private static boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }
}
