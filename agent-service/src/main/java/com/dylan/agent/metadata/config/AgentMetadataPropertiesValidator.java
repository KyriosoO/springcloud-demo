package com.dylan.agent.metadata.config;

import com.dylan.agent.metadata.crypto.port.PayloadKeyProvider;
import com.dylan.common.security.SecretPropertiesValidator;

import java.time.Duration;
import java.util.Arrays;
import java.util.Objects;

import javax.crypto.SecretKey;

/** metadata instance config 的启动和 reload 校验。 */
public final class AgentMetadataPropertiesValidator {

    private AgentMetadataPropertiesValidator() {
    }

    public static void validate(AgentMetadataProperties properties) {
        Objects.requireNonNull(properties, "properties must not be null");
        requireNonBlank(properties.getBundleVersion(), "agent.metadata.bundle-version");
        requireNonBlank(properties.getDefaultProfileId(), "agent.metadata.default-profile-id");
        Duration timeout = Objects.requireNonNull(
                properties.getReloadValidationTimeout(),
                "agent.metadata.reload-validation-timeout must not be null");
        if (timeout.compareTo(Duration.ofMillis(100)) < 0 || timeout.compareTo(Duration.ofSeconds(30)) > 0) {
            throw new IllegalStateException("agent.metadata.reload-validation-timeout must be between 100ms and 30s");
        }
    }

    public static void validate(AgentMetadataBundle bundle, PayloadKeyProvider payloadKeyProvider) {
        Objects.requireNonNull(bundle, "bundle must not be null");
        validate(bundle.securitySettings(), payloadKeyProvider);
    }

    public static void validate(AgentSecuritySettings securitySettings, PayloadKeyProvider payloadKeyProvider) {
        Objects.requireNonNull(securitySettings, "securitySettings must not be null");
        Objects.requireNonNull(payloadKeyProvider, "payloadKeyProvider must not be null");
        SecretPropertiesValidator.validateKeyId(securitySettings.activePayloadKeyId());
        SecretKey key = Objects.requireNonNull(
                payloadKeyProvider.requireKey(securitySettings.activePayloadKeyId()),
                "payload key must not be null");
        if (!"AES".equalsIgnoreCase(key.getAlgorithm())) {
            throw new IllegalStateException("agent payload active key must use AES algorithm");
        }
        byte[] encoded = key.getEncoded();
        try {
            if (encoded == null || encoded.length != 32) {
                throw new IllegalStateException("agent payload active key must be an AES-256 key");
            }
        } finally {
            if (encoded != null) {
                Arrays.fill(encoded, (byte) 0);
            }
        }
    }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalStateException(name + " must not be blank");
        }
        return normalized;
    }
}
