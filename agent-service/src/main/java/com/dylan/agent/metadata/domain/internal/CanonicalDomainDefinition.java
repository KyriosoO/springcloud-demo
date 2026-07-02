package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.adapter.api.AdapterRole;

import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

/** 不可变 canonical domain facts；不存储 permission 或 adapter endpoint 数据。 */
public record CanonicalDomainDefinition(
        String domain,
        List<String> aliases,
        String description,
        Map<AdapterRole, List<String>> defaultSelectFieldsByRole,
        Map<String, CanonicalFieldDefinition> fields,
        Map<AdapterRole, CanonicalRoleCapability> roleCapabilities) {

    public CanonicalDomainDefinition {
        domain = CanonicalFieldDefinition.requireNonBlank(domain, "domain");
        aliases = List.copyOf(aliases == null ? List.of() : aliases);
        description = CanonicalFieldDefinition.requireNonBlank(description, "description");
        defaultSelectFieldsByRole = copyDefaultSelect(defaultSelectFieldsByRole);
        fields = Map.copyOf(Objects.requireNonNull(fields, "fields must not be null"));
        roleCapabilities = Map.copyOf(Objects.requireNonNull(roleCapabilities, "roleCapabilities must not be null"));
    }

    public Set<String> fieldsFor(AdapterRole role) {
        CanonicalRoleCapability capability = roleCapabilities.get(role);
        return capability == null ? Set.of() : capability.fields();
    }

    private static Map<AdapterRole, List<String>> copyDefaultSelect(Map<AdapterRole, List<String>> source) {
        if (source == null || source.isEmpty()) {
            return Map.of();
        }
        return source.entrySet().stream()
                .collect(Collectors.toUnmodifiableMap(
                        entry -> Objects.requireNonNull(entry.getKey(), "role must not be null"),
                        entry -> List.copyOf(Objects.requireNonNull(entry.getValue(), "default select fields"))));
    }
}
