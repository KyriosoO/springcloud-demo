package com.dylan.agent.metadata.config;

import com.dylan.agent.metadata.crypto.port.PayloadKeyProvider;
import com.dylan.common.security.SecretPropertiesValidator;

import java.util.Arrays;
import java.util.Objects;

import javax.crypto.SecretKey;

/** metadata instance config 的启动和 reload 校验。 */
public final class AgentMetadataPropertiesValidator {

    private AgentMetadataPropertiesValidator() {
    }

    public static void validate(String activePayloadKeyId, PayloadKeyProvider payloadKeyProvider) {
        requireNonBlank(activePayloadKeyId, "common.security.secrets.agent-payload.active-key-id");
        Objects.requireNonNull(payloadKeyProvider, "payloadKeyProvider must not be null");
        SecretPropertiesValidator.validateKeyId(activePayloadKeyId);
        SecretKey key = Objects.requireNonNull(
                payloadKeyProvider.requireKey(activePayloadKeyId),
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
