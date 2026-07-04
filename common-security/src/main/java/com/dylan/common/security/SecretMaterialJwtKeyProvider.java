package com.dylan.common.security;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;

import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;

public final class SecretMaterialJwtKeyProvider implements JwtKeyProvider {

	private final SecretProperties properties;
	private final SecretMaterialProvider secretMaterialProvider;
	private volatile JwtKeySet cached;

	public SecretMaterialJwtKeyProvider(SecretProperties properties, SecretMaterialProvider secretMaterialProvider) {
		this.properties = Objects.requireNonNull(properties, "properties must not be null");
		this.secretMaterialProvider = Objects.requireNonNull(secretMaterialProvider,
				"secretMaterialProvider must not be null");
	}

	@Override
	public JwtKeySet current() {
		JwtKeySet current = cached;
		if (current == null) {
			synchronized (this) {
				current = cached;
				if (current == null) {
					current = build();
					cached = current;
				}
			}
		}
		return current;
	}

	private JwtKeySet build() {
		String activeKeyId = properties.getJwt().getActiveKeyId();
		Map<String, SecretKey> verificationKeys = new LinkedHashMap<>();
		SecretKey activeKey = resolve(activeKeyId);
		verificationKeys.put(activeKeyId, activeKey);
		for (String previousKeyId : properties.getJwt().getPreviousKeyIds()) {
			verificationKeys.put(previousKeyId, resolve(previousKeyId));
		}
		return new JwtKeySet(activeKeyId, activeKey, verificationKeys);
	}

	private SecretKey resolve(String keyId) {
		SecretMaterial material = secretMaterialProvider.requireSecret(ref(keyId));
		byte[] raw = material.secretValue().copyBytes();
		if (raw.length < 32) {
			throw new SecretMaterialException("JWT HMAC key must be at least 32 bytes for keyId " + keyId);
		}
		return new SecretKeySpec(raw, "HmacSHA256");
	}

	private SecretKeyRef ref(String keyId) {
		SecretProperties.KeyProperties key = properties.getJwt().getKeys().get(keyId);
		if (key == null) {
			throw new SecretMaterialException("Missing JWT key config for keyId " + keyId, null, true);
		}
		return new SecretKeyRef(SecretPurpose.JWT_HMAC, keyId, key.getEnv(), key.getValue());
	}
}
