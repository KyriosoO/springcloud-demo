package com.dylan.agent.metadata.crypto.internal;

import com.dylan.agent.metadata.crypto.port.PayloadKeyProvider;
import com.dylan.common.security.SecretMaterial;
import com.dylan.common.security.SecretMaterialException;
import com.dylan.common.security.SecretMaterialProvider;
import com.dylan.common.security.SecretProperties;
import com.dylan.common.security.SecretPropertiesValidator;
import com.dylan.common.security.SecretPurpose;
import com.dylan.common.security.SecretKeyRef;

import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

public final class SecretMaterialPayloadKeyProvider implements PayloadKeyProvider {

    private final SecretProperties properties;
    private final SecretMaterialProvider secretMaterialProvider;
    private final ConcurrentMap<String, SecretKey> keysById = new ConcurrentHashMap<>();

    public SecretMaterialPayloadKeyProvider(
            SecretProperties properties,
            SecretMaterialProvider secretMaterialProvider) {
        this.properties = Objects.requireNonNull(properties, "properties must not be null");
        this.secretMaterialProvider = Objects.requireNonNull(secretMaterialProvider,
                "secretMaterialProvider must not be null");
    }

    @Override
    public SecretKey requireKey(String keyId) {
        SecretPropertiesValidator.validateKeyId(keyId);
        return keysById.computeIfAbsent(keyId.trim(), this::resolve);
    }

    private SecretKey resolve(String keyId) {
        SecretMaterial material = secretMaterialProvider.requireSecret(ref(keyId));
        byte[] raw = material.secretValue().copyBytes();
        if (raw.length != 32) {
            throw new SecretMaterialException("Payload key must be 32 bytes for keyId " + keyId);
        }
        return new SecretKeySpec(raw, "AES");
    }

    private SecretKeyRef ref(String keyId) {
        SecretProperties.KeyProperties key = properties.getAgentPayload().getKeys().get(keyId);
        if (key == null) {
            throw new SecretMaterialException("Missing payload key config for keyId " + keyId, null, true);
        }
        return new SecretKeyRef(SecretPurpose.AGENT_PAYLOAD, keyId, key.getEnv(), key.getValue());
    }
}
