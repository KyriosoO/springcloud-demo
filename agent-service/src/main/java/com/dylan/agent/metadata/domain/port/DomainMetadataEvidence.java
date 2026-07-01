package com.dylan.agent.metadata.domain.port;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.HexFormat;
import java.util.Objects;

/**
 * Version evidence captured from one D04 metadata/availability view.
 */
public record DomainMetadataEvidence(
        String catalogVersion,
        String adapterRegistrationVersion,
        String availabilityDigest,
        Instant capturedAt) {

    public DomainMetadataEvidence {
        catalogVersion = requireNonBlank(catalogVersion, "catalogVersion");
        adapterRegistrationVersion = requireNonBlank(
                adapterRegistrationVersion, "adapterRegistrationVersion");
        availabilityDigest = requireNonBlank(availabilityDigest, "availabilityDigest");
        Objects.requireNonNull(capturedAt, "capturedAt must not be null");
    }

    public String safeRef() {
        String canonical = catalogVersion + "|"
                + adapterRegistrationVersion + "|"
                + availabilityDigest + "|"
                + capturedAt.toString();
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(canonical.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
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
