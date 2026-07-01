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
        Map<String, Set<AdapterRole>> availableRolesByDomain) {

    public DomainAvailabilitySnapshot {
        Objects.requireNonNull(evidence, "evidence must not be null");
        if (availableRolesByDomain == null || availableRolesByDomain.isEmpty()) {
            availableRolesByDomain = Map.of();
        } else {
            availableRolesByDomain = availableRolesByDomain.entrySet().stream()
                    .collect(java.util.stream.Collectors.toUnmodifiableMap(
                            Map.Entry::getKey,
                            entry -> Set.copyOf(entry.getValue())));
        }
    }
}
