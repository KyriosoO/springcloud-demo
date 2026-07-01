package com.dylan.agent.metadata.crypto.model;

import java.util.Arrays;
import java.util.Objects;

/**
 * Encrypted payload envelope. Byte arrays are copied on input and output.
 */
public final class ProtectedPayload {

    private final byte[] ciphertext;
    private final String keyId;
    private final byte[] nonce;
    private final String algorithmVersion;

    public ProtectedPayload(byte[] ciphertext, String keyId, byte[] nonce, String algorithmVersion) {
        this.ciphertext = copyNonEmpty(ciphertext, "ciphertext");
        this.keyId = requireNonBlank(keyId, "keyId");
        this.nonce = copyNonEmpty(nonce, "nonce");
        this.algorithmVersion = requireNonBlank(algorithmVersion, "algorithmVersion");
    }

    public byte[] ciphertext() {
        return Arrays.copyOf(ciphertext, ciphertext.length);
    }

    public String keyId() {
        return keyId;
    }

    public byte[] nonce() {
        return Arrays.copyOf(nonce, nonce.length);
    }

    public String algorithmVersion() {
        return algorithmVersion;
    }

    private static byte[] copyNonEmpty(byte[] value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        if (value.length == 0) {
            throw new IllegalArgumentException(name + " must not be empty");
        }
        return Arrays.copyOf(value, value.length);
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
