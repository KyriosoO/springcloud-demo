package com.dylan.agent.metadata.domain.port;

import com.dylan.agent.adapter.api.AdapterRole;

import java.util.Map;
import java.util.Objects;
import java.util.Set;

/**
 * Request-time D04 availability projection. It carries no field catalog facts.
 */
public record DomainAvailabilitySnapshot(
        DomainMetadataEvidence evidence,
        Map<AdapterRole, Set<String>> availableDomains) {

    public DomainAvailabilitySnapshot {
        Objects.requireNonNull(evidence, "evidence must not be null");
        if (availableDomains == null || availableDomains.isEmpty()) {
            availableDomains = Map.of();
        } else {
            availableDomains = availableDomains.entrySet().stream()
                    .collect(java.util.stream.Collectors.toUnmodifiableMap(
                            entry -> Objects.requireNonNull(entry.getKey(), "adapterRole must not be null"),
                            entry -> Set.copyOf(Objects.requireNonNull(entry.getValue(), "domains must not be null"))));
        }
    }
}
