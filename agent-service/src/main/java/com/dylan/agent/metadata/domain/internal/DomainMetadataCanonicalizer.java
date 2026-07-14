package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.metadata.domain.port.CanonicalRoleCapabilityRef;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.function.Function;
import java.util.stream.Collectors;

/** DCF-1/DRS-1 元数据 canonical form 的唯一实现。 */
final class DomainMetadataCanonicalizer {

    private DomainMetadataCanonicalizer() {
    }

    static String catalogDigest(String catalogVersion, Map<String, CanonicalDomainDefinition> domains) {
        String domainValues = domains.values().stream()
                .sorted(java.util.Comparator.comparing(CanonicalDomainDefinition::domain))
                .map(DomainMetadataCanonicalizer::domainCanonical)
                .collect(Collectors.joining());
        return digest("DCF-1", catalogVersion, domainValues);
    }

    static String registrationDigest(
            String registrationVersion,
            Map<AdapterRegistrationSet.Key, AdapterRegistration> registrations,
            Map<AdapterRegistrationSet.Key, CanonicalRoleCapabilityRef> capabilityRefs) {
        String values = registrations.entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .map(entry -> {
                    AdapterRegistration registration = entry.getValue();
                    CanonicalRoleCapabilityRef capabilityRef = capabilityRefs.get(entry.getKey());
                    return canonical(
                            registration.registrationId(),
                            registration.role().value(),
                            registration.domain(),
                            registration.portBeanName(),
                            registration.registrationVersion(),
                            capabilityRef.safeRef());
                })
                .collect(Collectors.joining());
        return digest("DRS-1", registrationVersion, values);
    }

    static String digest(String... values) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(canonical(values).getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }

    static String requireDigest(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        if (!value.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException(name + " must be lowercase SHA-256");
        }
        return value;
    }

    static String canonical(String... values) {
        StringBuilder result = new StringBuilder();
        for (String value : values) {
            String checked = Objects.requireNonNull(value, "canonical value must not be null");
            result.append(checked.getBytes(StandardCharsets.UTF_8).length)
                    .append(':').append(checked);
        }
        return result.toString();
    }

    private static String domainCanonical(CanonicalDomainDefinition domain) {
        return canonical(
                domain.domain(),
                declared(domain.aliases(), Function.identity()),
                domain.description(),
                orderedMap(domain.defaultSelectFieldsByRole(), role -> role.value(),
                        values -> declared(values, Function.identity())),
                orderedMap(domain.fields(), Function.identity(), DomainMetadataCanonicalizer::fieldCanonical),
                orderedMap(domain.roleCapabilities(), role -> role.value(),
                        DomainMetadataCanonicalizer::roleCapabilityCanonical));
    }

    private static String fieldCanonical(CanonicalFieldDefinition field) {
        return canonical(
                field.field(),
                declared(field.aliases(), Function.identity()),
                field.description(),
                field.type().name(),
                field.unit().orElse(""),
                field.valueFormat().orElse(""),
                field.maxLength().map(String::valueOf).orElse(""),
                field.precision().map(String::valueOf).orElse(""),
                field.scale().map(String::valueOf).orElse(""));
    }

    private static String roleCapabilityCanonical(CanonicalRoleCapability capability) {
        return canonical(
                capability.role().value(),
                ordered(capability.fields(), Function.identity()),
                ordered(capability.sortFields(), Function.identity()),
                orderedMap(capability.operatorsByField(), Function.identity(),
                        values -> ordered(values, Enum::name)),
                orderedMap(capability.functionsByField(), Function.identity(),
                        values -> ordered(values, AggregateFunction::name)));
    }

    private static <T> String ordered(java.util.Collection<T> values, Function<T, String> mapper) {
        return values.stream().map(mapper).sorted().map(value -> canonical(value))
                .collect(Collectors.joining());
    }

    private static <T> String declared(java.util.Collection<T> values, Function<T, String> mapper) {
        return values.stream().map(mapper).map(value -> canonical(value))
                .collect(Collectors.joining());
    }

    private static <K, V> String orderedMap(
            Map<K, V> values,
            Function<K, String> keyMapper,
            Function<V, String> valueMapper) {
        return values.entrySet().stream()
                .sorted(java.util.Comparator.comparing(entry -> keyMapper.apply(entry.getKey())))
                .map(entry -> canonical(keyMapper.apply(entry.getKey()), valueMapper.apply(entry.getValue())))
                .collect(Collectors.joining());
    }
}
