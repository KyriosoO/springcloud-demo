package com.dylan.agent.metadata.catalog;

import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;

import java.time.Instant;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

/** 不可变的请求级 capability catalog 结果。 */
public record AvailableCapabilitySnapshot(
        String requestCorrelationId,
        String authorizationEvidenceDigest,
        DomainMetadataEvidence domainMetadataEvidence,
        List<AvailableCapability> capabilities,
        Instant createdAt) {
    public AvailableCapabilitySnapshot {
        requestCorrelationId = requireNonBlank(requestCorrelationId, "requestCorrelationId");
        authorizationEvidenceDigest = requireNonBlank(authorizationEvidenceDigest, "authorizationEvidenceDigest");
        Objects.requireNonNull(domainMetadataEvidence, "domainMetadataEvidence must not be null");
        capabilities = List.copyOf(Objects.requireNonNull(capabilities, "capabilities must not be null"));
        Objects.requireNonNull(createdAt, "createdAt must not be null");
    }

    public boolean contains(String capabilityId) {
        return capabilities.stream().anyMatch(capability -> capability.capabilityId().equals(capabilityId));
    }

    public AvailableCapability getRequired(String capabilityId) {
        return capabilities.stream()
                .filter(capability -> capability.capabilityId().equals(capabilityId))
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("capability not available: " + capabilityId));
    }

    public Set<String> capabilityIds() {
        return capabilities.stream().map(AvailableCapability::capabilityId).collect(Collectors.toUnmodifiableSet());
    }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }
}
