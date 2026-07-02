package com.dylan.agent.metadata.crypto.internal;

import com.dylan.agent.metadata.crypto.port.PayloadKeyProvider;

import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import java.util.Base64;
import java.util.Locale;
import java.util.Objects;
import java.util.function.Function;

/**
 * 从 environment-style secret lookup 加载 AES-256 payload key。
 */
public final class EnvironmentPayloadKeyProvider implements PayloadKeyProvider {

    private final Function<String, String> secretLookup;

    public EnvironmentPayloadKeyProvider() {
        this(System::getenv);
    }

    public EnvironmentPayloadKeyProvider(Function<String, String> secretLookup) {
        this.secretLookup = Objects.requireNonNull(secretLookup);
    }

    @Override
    public SecretKey requireKey(String keyId) {
        String envName = "AGENT_PAYLOAD_KEY_" + normalizeKeyId(keyId);
        String encoded = secretLookup.apply(envName);
        if (encoded == null || encoded.isBlank()) {
            throw new IllegalStateException("Missing payload key secret: " + envName);
        }
        byte[] raw = Base64.getDecoder().decode(encoded);
        if (raw.length != 32) {
            throw new IllegalStateException("Payload key must be 32 bytes for keyId " + keyId);
        }
        return new SecretKeySpec(raw, "AES");
    }

    private static String normalizeKeyId(String keyId) {
        Objects.requireNonNull(keyId, "keyId must not be null");
        String normalized = keyId.trim().toUpperCase(Locale.ROOT);
        if (!normalized.matches("[A-Z0-9_]+")) {
            throw new IllegalArgumentException("keyId must be upper env-token compatible: " + keyId);
        }
        return normalized;
    }
}
