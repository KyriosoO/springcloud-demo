package com.dylan.agent.metadata.policy.model;

import java.time.Instant;
import java.util.Objects;

/** typed emergency revocation 条目。 */
public record EmergencyRevocation(
        EmergencyRevocationTarget target,
        String targetId,
        String version,
        Instant revokedAt) {
    public EmergencyRevocation {
        Objects.requireNonNull(target, "target must not be null");
        targetId = requireNonBlank(targetId, "targetId");
        version = requireNonBlank(version, "version");
        Objects.requireNonNull(revokedAt, "revokedAt must not be null");
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
