package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.adapter.api.AdapterRole;

import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;

/** Immutable D04 canonical catalog snapshot. */
public record CanonicalDomainCatalog(
        String catalogVersion,
        Map<String, CanonicalDomainDefinition> domains) {

    public CanonicalDomainCatalog {
        catalogVersion = CanonicalFieldDefinition.requireNonBlank(catalogVersion, "catalogVersion");
        domains = Map.copyOf(Objects.requireNonNull(domains, "domains must not be null"));
    }

    public CanonicalDomainDefinition requireDomain(String domain) {
        CanonicalDomainDefinition definition = domains.get(domain);
        if (definition == null) {
            throw new IllegalArgumentException("Unknown domain: " + domain);
        }
        return definition;
    }

    public Optional<CanonicalDomainDefinition> findDomain(String domain) {
        return Optional.ofNullable(domains.get(domain));
    }

    public List<String> domainIds() {
        return domains.keySet().stream().sorted(Comparator.naturalOrder()).toList();
    }

    public boolean supportsRole(String domain, AdapterRole role) {
        CanonicalDomainDefinition definition = domains.get(domain);
        return definition != null && definition.roleCapabilities().containsKey(role);
    }

    public Set<AdapterRole> roles() {
        return domains.values().stream()
                .flatMap(domain -> domain.roleCapabilities().keySet().stream())
                .collect(java.util.stream.Collectors.toUnmodifiableSet());
    }
}
