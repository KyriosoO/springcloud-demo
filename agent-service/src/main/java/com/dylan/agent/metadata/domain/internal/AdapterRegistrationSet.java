package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.metadata.domain.port.CanonicalRoleCapabilityRef;

import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;

/** adapter registrations 的不可变 lookup index。 */
public record AdapterRegistrationSet(
        String adapterRegistrationVersion,
        Map<Key, AdapterRegistration> byRoleAndDomain,
        Map<Key, CanonicalRoleCapabilityRef> capabilityRefs,
        String canonicalDigest) {

    public AdapterRegistrationSet {
        adapterRegistrationVersion = CanonicalFieldDefinition.requireNonBlank(
                adapterRegistrationVersion, "adapterRegistrationVersion");
        byRoleAndDomain = Map.copyOf(Objects.requireNonNull(byRoleAndDomain, "byRoleAndDomain must not be null"));
        capabilityRefs = Map.copyOf(Objects.requireNonNull(capabilityRefs, "capabilityRefs must not be null"));
        canonicalDigest = DomainMetadataCanonicalizer.requireDigest(canonicalDigest, "canonicalDigest");
        if (!byRoleAndDomain.keySet().equals(capabilityRefs.keySet())) {
            throw new IllegalArgumentException("registration capability reference keys must match registrations");
        }
        if (!canonicalDigest.equals(DomainMetadataCanonicalizer.registrationDigest(
                adapterRegistrationVersion, byRoleAndDomain, capabilityRefs))) {
            throw new IllegalArgumentException("canonicalDigest does not match registration content");
        }
    }

    public Optional<AdapterRegistration> find(AdapterRole role, String domain) {
        return Optional.ofNullable(byRoleAndDomain.get(new Key(role, domain)));
    }

    public AdapterRegistration require(AdapterRole role, String domain) {
        return find(role, domain).orElseThrow(() ->
                new IllegalStateException("No adapter registration for " + role + "/" + domain));
    }

    public CanonicalRoleCapabilityRef requireCapabilityRef(AdapterRole role, String domain) {
        CanonicalRoleCapabilityRef reference = capabilityRefs.get(new Key(role, domain));
        if (reference == null) {
            throw new IllegalStateException("No capability reference for " + role + "/" + domain);
        }
        return reference;
    }

    public Set<AdapterRole> roles() {
        return byRoleAndDomain.keySet().stream().map(Key::role).collect(Collectors.toUnmodifiableSet());
    }

    public Set<String> domains(AdapterRole role) {
        return byRoleAndDomain.keySet().stream()
                .filter(key -> key.role().equals(role))
                .map(Key::domain)
                .collect(Collectors.toUnmodifiableSet());
    }

    public List<AdapterRegistration> sortedRegistrations() {
        return byRoleAndDomain.values().stream()
                .sorted(Comparator.comparing((AdapterRegistration r) -> r.role().value())
                        .thenComparing(AdapterRegistration::domain)
                        .thenComparing(AdapterRegistration::registrationId))
                .toList();
    }

    public record Key(AdapterRole role, String domain) implements Comparable<Key> {
        public Key {
            Objects.requireNonNull(role, "role must not be null");
            domain = CanonicalFieldDefinition.requireNonBlank(domain, "domain");
        }

        @Override
        public int compareTo(Key other) {
            int roleOrder = role.value().compareTo(other.role.value());
            return roleOrder != 0 ? roleOrder : domain.compareTo(other.domain);
        }
    }
}
