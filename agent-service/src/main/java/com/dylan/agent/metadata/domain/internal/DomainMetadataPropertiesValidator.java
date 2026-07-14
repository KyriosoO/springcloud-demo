package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.AgentAdapterPort;
import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.metadata.domain.port.DomainMetadataStaticEvidence;
import com.dylan.agent.metadata.domain.port.CanonicalRoleCapabilityRef;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Clock;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 构建一个不可变 D04 快照，并执行启动门禁。
 *
 * <p>该校验器不读取 Profile/Policy/UserPermission；这些请求级交集
 * 由后续 port 消费。</p>
 */
public final class DomainMetadataPropertiesValidator {

    private DomainMetadataPropertiesValidator() {
    }

    public static DomainMetadataStaticBundle build(
            DomainMetadataProperties properties,
            Map<String, AgentAdapterPort> adapterPorts,
            Clock clock) {
        Objects.requireNonNull(properties, "properties must not be null");
        Objects.requireNonNull(adapterPorts, "adapterPorts must not be null");
        Objects.requireNonNull(clock, "clock must not be null");

        CanonicalDomainCatalog catalog = buildCatalog(properties);
        AdapterRegistrationSet registrations = buildRegistrations(properties, catalog, adapterPorts);
        DomainMetadataStaticEvidence evidence = new DomainMetadataStaticEvidence(
                catalog.catalogVersion(),
                catalog.canonicalDigest(),
                registrations.adapterRegistrationVersion(),
                registrations.canonicalDigest(),
                clock.instant());
        return new DomainMetadataStaticBundle(catalog, registrations, evidence);
    }

    private static CanonicalDomainCatalog buildCatalog(DomainMetadataProperties properties) {
        String catalogVersion = requireNonBlank(properties.getCatalogVersion(), "catalogVersion");
        Map<String, DomainMetadataProperties.DomainProperties> source =
                Objects.requireNonNull(properties.getDomains(), "agent.domain-metadata.domains must not be null");
        if (source.isEmpty()) {
            throw new IllegalStateException("agent.domain-metadata.domains must not be empty");
        }
        Map<String, CanonicalDomainDefinition> domains = new LinkedHashMap<>();
        for (var entry : source.entrySet()) {
            String domainId = requireDomainId(entry.getKey());
            if (domains.containsKey(domainId)) {
                throw new IllegalStateException("duplicate domain: " + domainId);
            }
            domains.put(domainId, buildDomain(domainId, entry.getValue()));
        }
        String digest = DomainMetadataCanonicalizer.catalogDigest(catalogVersion, domains);
        return new CanonicalDomainCatalog(catalogVersion, domains, digest);
    }

    private static CanonicalDomainDefinition buildDomain(
            String domainId,
            DomainMetadataProperties.DomainProperties source) {
        Objects.requireNonNull(source, "domain properties must not be null");
        if (source.getAliases() == null || source.getAliases().isEmpty()) {
            throw new IllegalStateException("domain aliases must not be empty: " + domainId);
        }
        Map<String, CanonicalFieldDefinition> fields = new LinkedHashMap<>();
        for (var entry : nonEmpty(source.getFields(), "fields").entrySet()) {
            String fieldId = requireNonBlank(entry.getKey(), "field");
            DomainMetadataProperties.FieldProperties fp = Objects.requireNonNull(entry.getValue(), "field properties");
            CanonicalFieldDefinition previous = fields.putIfAbsent(fieldId, new CanonicalFieldDefinition(
                    fieldId,
                    uniqueOrdered(fp.getAliases(), "field alias"),
                    requireNonBlank(fp.getDescription(), "field description"),
                    Objects.requireNonNull(fp.getType(), "field type must not be null"),
                    Optional.ofNullable(trimToNull(fp.getUnit())),
                    Optional.ofNullable(trimToNull(fp.getValueFormat())),
                    Optional.ofNullable(fp.getMaxLength()),
                    Optional.ofNullable(fp.getPrecision()),
                    Optional.ofNullable(fp.getScale())));
            if (previous != null) {
                throw new IllegalStateException("duplicate canonical field: " + fieldId);
            }
        }

        Map<AdapterRole, CanonicalRoleCapability> capabilities = new LinkedHashMap<>();
        for (var entry : nonEmpty(source.getRoleCapabilities(), "roleCapabilities").entrySet()) {
            AdapterRole role = AdapterRole.of(entry.getKey());
            DomainMetadataProperties.RoleCapabilityProperties cp =
                    Objects.requireNonNull(entry.getValue(), "role capability properties");
            Set<String> capabilityFields = cp.getFields() == null
                    ? Set.of()
                    : cp.getFields().stream().map(value -> requireKnownField(fields, value)).collect(Collectors.toCollection(LinkedHashSet::new));
            if (capabilityFields.isEmpty()) {
                throw new IllegalStateException("role capability fields must not be empty: " + domainId + "/" + role);
            }
            validateCapabilityMaps(domainId, role, fields, capabilityFields, cp);
            Set<String> sortFields = cp.getSortFields() == null
                    ? Set.of()
                    : cp.getSortFields().stream()
                    .map(value -> requireKnownField(fields, value))
                    .collect(Collectors.toCollection(LinkedHashSet::new));
            if (!capabilityFields.containsAll(sortFields)) {
                throw new IllegalStateException("sortFields must be role capability fields subset: " + domainId + "/" + role);
            }
            if (role != AdapterRole.QUERYABLE && role != AdapterRole.DOCUMENT_RETRIEVABLE && !sortFields.isEmpty()) {
                throw new IllegalStateException("sortFields only allowed for QUERYABLE/DOCUMENT_RETRIEVABLE role: "
                        + domainId + "/" + role);
            }
            CanonicalRoleCapability previous = capabilities.putIfAbsent(role, new CanonicalRoleCapability(
                    role,
                    capabilityFields,
                    sortFields,
                    cp.getOperatorsByField(),
                    cp.getFunctionsByField()));
            if (previous != null) {
                throw new IllegalStateException("duplicate role capability: " + domainId + "/" + role);
            }
        }

        Map<AdapterRole, java.util.List<String>> defaultSelect = new LinkedHashMap<>();
        if (source.getDefaultSelectFieldsByRole() != null) {
            for (var entry : source.getDefaultSelectFieldsByRole().entrySet()) {
                AdapterRole role = AdapterRole.of(entry.getKey());
                java.util.List<String> values = uniqueOrdered(entry.getValue(), "defaultSelectField").stream()
                        .map(value -> requireKnownField(fields, value)).toList();
                if (!capabilities.containsKey(role)) {
                    throw new IllegalStateException("defaultSelectFieldsByRole references missing role: " + role);
                }
                if (!capabilities.get(role).fields().containsAll(values)) {
                    throw new IllegalStateException("defaultSelect fields must be role capability subset: " + role);
                }
                if (defaultSelect.putIfAbsent(role, values) != null) {
                    throw new IllegalStateException("duplicate defaultSelect role: " + role);
                }
            }
        }
        return new CanonicalDomainDefinition(
                domainId,
                uniqueOrdered(source.getAliases(), "alias"),
                requireNonBlank(source.getDescription(), "domain description"),
                defaultSelect,
                fields,
                capabilities);
    }

    private static AdapterRegistrationSet buildRegistrations(
            DomainMetadataProperties properties,
            CanonicalDomainCatalog catalog,
            Map<String, AgentAdapterPort> adapterPorts) {
        String registrationVersion = requireNonBlank(
                properties.getAdapterRegistrationVersion(), "adapterRegistrationVersion");
        if (properties.getRegistrations() == null || properties.getRegistrations().isEmpty()) {
            throw new IllegalStateException("agent.domain-metadata.registrations must not be empty");
        }
        Map<AdapterRegistrationSet.Key, AdapterRegistration> registrations = new LinkedHashMap<>();
        Set<String> registrationIds = new LinkedHashSet<>();
        for (DomainMetadataProperties.RegistrationProperties source : properties.getRegistrations()) {
            AdapterRole role = AdapterRole.of(requireNonBlank(source.getRole(), "registration role"));
            if (!AdapterRolePortTypes.isKnown(role)) {
                throw new IllegalStateException("unknown adapter role: " + role);
            }
            String domain = requireDomainId(source.getDomain());
            if (!catalog.supportsRole(domain, role)) {
                throw new IllegalStateException("registration references missing catalog role capability: "
                        + role + "/" + domain);
            }
            Class<? extends AgentAdapterPort> expectedType = AdapterRolePortTypes.requirePortType(role);
            AgentAdapterPort port = adapterPorts.get(source.getPortBeanName());
            if (port == null || !expectedType.isInstance(port)) {
                throw new IllegalStateException("registration port bean missing or incompatible: "
                        + source.getPortBeanName());
            }
            String registrationId = requireNonBlank(source.getRegistrationId(), "registrationId");
            if (!registrationIds.add(registrationId)) {
                throw new IllegalStateException("duplicate registrationId: " + registrationId);
            }
            AdapterRegistration registration = new AdapterRegistration(
                    registrationId,
                    role,
                    domain,
                    source.getPortBeanName(),
                    requireNonBlank(source.getRegistrationVersion(), "registrationVersion"));
            if (!registration.registrationVersion().equals(registrationVersion)) {
                throw new IllegalStateException("registration version must match current D04 versions");
            }
            AdapterRegistration previous = registrations.put(
                    new AdapterRegistrationSet.Key(role, domain), registration);
            if (previous != null) {
                throw new IllegalStateException("duplicate adapter registration for " + role + "/" + domain);
            }
        }
        Set<AdapterRegistrationSet.Key> requiredKeys = catalog.domains().values().stream()
                .flatMap(domain -> domain.roleCapabilities().keySet().stream()
                        .map(role -> new AdapterRegistrationSet.Key(role, domain.domain())))
                .collect(Collectors.toUnmodifiableSet());
        if (!registrations.keySet().equals(requiredKeys)) {
            throw new IllegalStateException("adapter registration coverage must exactly match catalog capabilities");
        }
        Map<AdapterRegistrationSet.Key, CanonicalRoleCapabilityRef> capabilityRefs = new LinkedHashMap<>();
        registrations.keySet().stream().sorted().forEach(key -> capabilityRefs.put(key,
                new CanonicalRoleCapabilityRef(
                        catalog.catalogVersion(), catalog.canonicalDigest(), key.domain(), key.role())));
        String digest = DomainMetadataCanonicalizer.registrationDigest(
                registrationVersion, registrations, capabilityRefs);
        return new AdapterRegistrationSet(registrationVersion, registrations, capabilityRefs, digest);
    }

    private static void validateCapabilityMaps(
            String domainId,
            AdapterRole role,
            Map<String, CanonicalFieldDefinition> fields,
            Set<String> capabilityFields,
            DomainMetadataProperties.RoleCapabilityProperties cp) {
        for (var entry : cp.getOperatorsByField().entrySet()) {
            String field = requireKnownField(fields, entry.getKey());
            if (!capabilityFields.contains(field)) {
                throw new IllegalStateException("operatorsByField key must be capability field: " + field);
            }
            for (AgentOperator operator : entry.getValue()) {
                if (!operatorSupports(operator, fields.get(field).type())) {
                    throw new IllegalStateException("operator " + operator + " incompatible with "
                            + domainId + "." + field + " for role " + role);
                }
            }
        }
        for (String field : cp.getFunctionsByField().keySet()) {
            String known = requireKnownField(fields, field);
            if (!capabilityFields.contains(known)) {
                throw new IllegalStateException("functionsByField key must be capability field: " + known);
            }
        }
    }

    private static boolean operatorSupports(AgentOperator operator, AgentFieldType type) {
        return switch (operator) {
            case EQ, IN -> true;
            case CONTAINS, CONTAINS_ANY, STARTS_WITH, STARTS_WITH_ANY -> type == AgentFieldType.STRING;
            case GT, LT -> type == AgentFieldType.DECIMAL || type == AgentFieldType.INSTANT;
        };
    }

    private static String requireKnownField(Map<String, CanonicalFieldDefinition> fields, String field) {
        String normalized = requireNonBlank(field, "field");
        if (!fields.containsKey(normalized)) {
            throw new IllegalStateException("unknown field: " + normalized);
        }
        return normalized;
    }

    private static String requireDomainId(String value) {
        String normalized = requireNonBlank(value, "domain");
        if (!normalized.matches("[a-z][a-z0-9_]*")) {
            throw new IllegalStateException("domain must be lower snake case: " + normalized);
        }
        return normalized;
    }

    private static String requireNonBlank(String value, String name) {
        return CanonicalFieldDefinition.requireNonBlank(value, name);
    }

    private static <K, V> Map<K, V> nonEmpty(Map<K, V> map, String name) {
        if (map == null || map.isEmpty()) {
            throw new IllegalStateException(name + " must not be empty");
        }
        return map;
    }

    private static String trimToNull(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return value.trim();
    }

    private static java.util.List<String> uniqueOrdered(java.util.List<String> values, String name) {
        if (values == null || values.isEmpty()) {
            throw new IllegalStateException(name + " values must not be empty");
        }
        LinkedHashSet<String> unique = new LinkedHashSet<>();
        for (String value : values) {
            String normalized = requireNonBlank(value, name);
            if (!unique.add(normalized)) {
                throw new IllegalStateException("duplicate " + name + ": " + normalized);
            }
        }
        return java.util.List.copyOf(unique);
    }

    private static int nonNegative(Integer value) {
        if (value == null) {
            return 0;
        }
        if (value < 0) {
            throw new IllegalStateException("numeric limits must not be negative");
        }
        return value;
    }
}
