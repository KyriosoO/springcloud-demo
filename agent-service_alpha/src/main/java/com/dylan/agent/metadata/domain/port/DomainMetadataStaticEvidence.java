package com.dylan.agent.metadata.domain.port;

import java.time.Instant;
import java.util.Objects;

/** Catalog 与 RegistrationSet 同批发布的不可变静态证据。 */
public record DomainMetadataStaticEvidence(
        String catalogVersion,
        String catalogDigest,
        String registrationSetVersion,
        String registrationDigest,
        Instant publishedAt) {

    public DomainMetadataStaticEvidence {
        catalogVersion = requireText(catalogVersion, "catalogVersion");
        catalogDigest = requireDigest(catalogDigest, "catalogDigest");
        registrationSetVersion = requireText(registrationSetVersion, "registrationSetVersion");
        registrationDigest = requireDigest(registrationDigest, "registrationDigest");
        Objects.requireNonNull(publishedAt, "publishedAt must not be null");
    }

    public String safeRef() {
        return DomainMetadataEvidence.sha256(DomainMetadataEvidence.canonical(
                "DMS-1", catalogVersion, catalogDigest,
                registrationSetVersion, registrationDigest, publishedAt.toString()));
    }

    static String requireText(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }

    static String requireDigest(String value, String name) {
        String normalized = requireText(value, name);
        if (!normalized.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException(name + " must be lowercase SHA-256");
        }
        return normalized;
    }
}
