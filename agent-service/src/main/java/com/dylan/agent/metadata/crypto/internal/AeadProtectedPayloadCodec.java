package com.dylan.agent.metadata.crypto.internal;

import com.dylan.agent.metadata.config.AgentSecuritySettingsRegistry;
import com.dylan.agent.metadata.crypto.model.PayloadProtectionContext;
import com.dylan.agent.metadata.crypto.model.ProtectedPayload;
import com.dylan.agent.metadata.crypto.port.PayloadKeyProvider;
import com.dylan.agent.metadata.crypto.port.ProtectedPayloadCodec;

import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import java.security.SecureRandom;
import java.util.Objects;

/**
 * AES-256-GCM payload codec. The active key id is read at each encryption.
 */
public final class AeadProtectedPayloadCodec implements ProtectedPayloadCodec {

    public static final String ALGORITHM_VERSION = "AES-256-GCM:v1";
    private static final int NONCE_BYTES = 12;
    private static final int TAG_BITS = 128;

    private final AgentSecuritySettingsRegistry settingsRegistry;
    private final PayloadKeyProvider keyProvider;
    private final SecureRandom secureRandom;

    public AeadProtectedPayloadCodec(
            AgentSecuritySettingsRegistry settingsRegistry,
            PayloadKeyProvider keyProvider) {
        this(settingsRegistry, keyProvider, new SecureRandom());
    }

    AeadProtectedPayloadCodec(
            AgentSecuritySettingsRegistry settingsRegistry,
            PayloadKeyProvider keyProvider,
            SecureRandom secureRandom) {
        this.settingsRegistry = Objects.requireNonNull(settingsRegistry);
        this.keyProvider = Objects.requireNonNull(keyProvider);
        this.secureRandom = Objects.requireNonNull(secureRandom);
    }

    @Override
    public ProtectedPayload encrypt(byte[] plaintext, PayloadProtectionContext context) {
        Objects.requireNonNull(plaintext, "plaintext must not be null");
        Objects.requireNonNull(context, "context must not be null");
        String keyId = settingsRegistry.current().activePayloadKeyId();
        byte[] nonce = new byte[NONCE_BYTES];
        secureRandom.nextBytes(nonce);
        return new ProtectedPayload(crypt(Cipher.ENCRYPT_MODE, keyId, nonce, plaintext, context),
                keyId, nonce, ALGORITHM_VERSION);
    }

    @Override
    public byte[] decrypt(ProtectedPayload payload, PayloadProtectionContext context) {
        Objects.requireNonNull(payload, "payload must not be null");
        Objects.requireNonNull(context, "context must not be null");
        if (!ALGORITHM_VERSION.equals(payload.algorithmVersion())) {
            throw new IllegalArgumentException("unsupported payload algorithm: "
                    + payload.algorithmVersion());
        }
        return crypt(Cipher.DECRYPT_MODE, payload.keyId(), payload.nonce(), payload.ciphertext(), context);
    }

    private byte[] crypt(
            int mode,
            String keyId,
            byte[] nonce,
            byte[] input,
            PayloadProtectionContext context) {
        try {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(mode, keyProvider.requireKey(keyId), new GCMParameterSpec(TAG_BITS, nonce));
            cipher.updateAAD(context.aadBytes());
            return cipher.doFinal(input);
        } catch (Exception ex) {
            throw new IllegalStateException("protected payload cryptographic operation failed", ex);
        }
    }
}
