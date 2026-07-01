package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.adapter.api.AdapterRole;

import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;

/** Immutable lookup index for adapter registrations. */
public record AdapterRegistrationSet(
        String adapterRegistrationVersion,
        Map<Key, AdapterRegistration> byRoleAndDomain) {

    public AdapterRegistrationSet {
        adapterRegistrationVersion = CanonicalFieldDefinition.requireNonBlank(
                adapterRegistrationVersion, "adapterRegistrationVersion");
        byRoleAndDomain = Map.copyOf(Objects.requireNonNull(byRoleAndDomain, "byRoleAndDomain must not be null"));
    }

    public Optional<AdapterRegistration> find(AdapterRole role, String domain) {
        return Optional.ofNullable(byRoleAndDomain.get(new Key(role, domain)));
    }

    public AdapterRegistration require(AdapterRole role, String domain) {
        return find(role, domain).orElseThrow(() ->
                new IllegalStateException("No adapter registration for " + role + "/" + domain));
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

    public record Key(AdapterRole role, String domain) {
        public Key {
            Objects.requireNonNull(role, "role must not be null");
            domain = CanonicalFieldDefinition.requireNonBlank(domain, "domain");
        }
    }
}
