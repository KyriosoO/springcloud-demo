package com.dylan.agent.metadata.domain.port;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.HexFormat;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

/** 静态 metadata 与本次请求 availability 捕获形成的不可变证据。 */
public record DomainMetadataEvidence(
        DomainMetadataStaticEvidence staticEvidence,
        Set<DomainAdapterKey> evaluatedKeys,
        String evaluatedKeysDigest,
        String availabilityDigest,
        Instant capturedAt) {

    public DomainMetadataEvidence {
        Objects.requireNonNull(staticEvidence, "staticEvidence must not be null");
        evaluatedKeys = Set.copyOf(Objects.requireNonNull(evaluatedKeys, "evaluatedKeys must not be null"));
        evaluatedKeysDigest = DomainMetadataStaticEvidence.requireDigest(
                evaluatedKeysDigest, "evaluatedKeysDigest");
        availabilityDigest = DomainMetadataStaticEvidence.requireDigest(
                availabilityDigest, "availabilityDigest");
        Objects.requireNonNull(capturedAt, "capturedAt must not be null");
        if (!evaluatedKeysDigest.equals(keysDigest(evaluatedKeys))) {
            throw new IllegalArgumentException("evaluatedKeysDigest does not match evaluatedKeys");
        }
    }

    public String catalogVersion() {
        return staticEvidence.catalogVersion();
    }

    public String adapterRegistrationVersion() {
        return staticEvidence.registrationSetVersion();
    }

    public String safeRef() {
        return sha256(canonical(
                "DME-1",
                staticEvidence.safeRef(),
                evaluatedKeysDigest,
                availabilityDigest,
                capturedAt.toString()));
    }

    public static String keysDigest(Set<DomainAdapterKey> keys) {
        String values = keys.stream().sorted()
                .map(key -> canonical(key.role().value(), key.domain()))
                .collect(Collectors.joining());
        return sha256(canonical("DMK-1", values));
    }

    static String canonical(String... values) {
        StringBuilder result = new StringBuilder();
        for (String value : values) {
            String checked = Objects.requireNonNull(value, "canonical value must not be null");
            int bytes = checked.getBytes(StandardCharsets.UTF_8).length;
            result.append(bytes).append(':').append(checked);
        }
        return result.toString();
    }

    static String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }
}
