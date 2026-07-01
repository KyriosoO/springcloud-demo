package com.dylan.agent.metadata.authorization.model;

import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;

import java.time.Instant;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/**
 * 外部权威系统返回的当前用户权限投影。
 *
 * <p>该值不保存 JWT、本地角色或完整外部响应体。所有集合和 Map 在构造时
 * defensive-copy，避免请求级权限事实被后续调用方改写。</p>
 */
public record UserPermission(
        ExecutionSubjectRef subject,
        String evidenceId,
        String version,
        Set<String> allowedCapabilityIds,
        Set<String> allowedDomains,
        Map<String, Set<String>> filterableFields,
        Map<String, Set<String>> displayableFields,
        Map<String, Set<AgentOperator>> allowedOperators,
        Map<String, Set<String>> allowedFunctions,
        Set<String> readableContextTypes,
        Set<String> writableContextTypes,
        Map<String, String> attributes,
        Instant resolvedAt) {

    public UserPermission {
        Objects.requireNonNull(subject, "subject must not be null");
        evidenceId = requireNonBlank(evidenceId, "evidenceId");
        version = requireNonBlank(version, "version");
        allowedCapabilityIds = copyStringSet(allowedCapabilityIds);
        allowedDomains = copyStringSet(allowedDomains);
        filterableFields = copyNestedStringSetMap(filterableFields);
        displayableFields = copyNestedStringSetMap(displayableFields);
        allowedOperators = copyOperatorMap(allowedOperators);
        allowedFunctions = copyNestedStringSetMap(allowedFunctions);
        readableContextTypes = copyStringSet(readableContextTypes);
        writableContextTypes = copyStringSet(writableContextTypes);
        attributes = Map.copyOf(attributes == null ? Map.of() : attributes);
        Objects.requireNonNull(resolvedAt, "resolvedAt must not be null");
    }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }

    private static Set<String> copyStringSet(Set<String> values) {
        return Set.copyOf(values == null ? Set.of() : values);
    }

    private static Map<String, Set<String>> copyNestedStringSetMap(Map<String, Set<String>> values) {
        if (values == null || values.isEmpty()) {
            return Map.of();
        }
        return values.entrySet().stream()
                .collect(java.util.stream.Collectors.toUnmodifiableMap(
                        Map.Entry::getKey,
                        entry -> Set.copyOf(entry.getValue())));
    }

    private static Map<String, Set<AgentOperator>> copyOperatorMap(
            Map<String, Set<AgentOperator>> values) {
        if (values == null || values.isEmpty()) {
            return Map.of();
        }
        return values.entrySet().stream()
                .collect(java.util.stream.Collectors.toUnmodifiableMap(
                        Map.Entry::getKey,
                        entry -> Set.copyOf(entry.getValue())));
    }
}
